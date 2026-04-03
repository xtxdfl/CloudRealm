#!/usr/bin/env python3

# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import ssl
import json
import gzip
import socket
import logging
import platform
import subprocess
import threading
import traceback
import urllib.request
import urllib.error
import urllib.parse
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from socket import error as socket_error

import cloud_stomp
from cloud_stomp.adapter.websocket import WsConnection
from cloud_agent import hostname
from cloud_agent.config import ConfigManager

logger = logging.getLogger(__name__)

# 常量定义
DEFAULT_KEY_PERMISSION = 0o600  # 私钥文件权限 (rw-------)
OPENSSL_CMD_FORMAT = (
    'openssl req -new -newkey rsa:2048 -nodes -keyout "{key_path}" '
    '-subj "/CN={hostname}" -out "{csr_path}"'
)


class SecurityConnectionManager:
    """管理与服务器的安全连接"""
    
    def __init__(self, config: ConfigManager, server_host: str):
        self.config = config
        self.server_host = server_host
        self.secure_port = self._get_secure_port()
        self.connection_url = self._build_connection_url()
        self.two_way_ssl = config.is_two_way_ssl_connection(server_host)
        
        logger.info(
            f"安全连接管理器初始化: 服务器={server_host}, 端口={self.secure_port}, "
            f"双向SSL={self.two_way_ssl}"
        )
    
    def create_secure_connection(self) -> WsConnection:
        """创建并返回安全连接"""
        logger.info("正在创建到 %s 的安全连接", self.server_host)
        
        ssl_context = None
        if self.two_way_ssl:
            logger.info("启用双向SSL认证")
            ssl_context = self._create_two_way_ssl_context()
        else:
            logger.info("使用单向SSL认证")
        
        # 创建并启动连接
        connection = self._create_stomp_connection(ssl_context)
        self._establish_connection(connection)
        
        return connection
    
    def _get_secure_port(self) -> int:
        """获取安全端口配置"""
        try:
            port = self.config.getint("server", "secured_url_port")
            logger.debug("使用端口号: %d", port)
            return port
        except ValueError:
            raise ValueError(f"无效的端口配置: {self.config.get('server', 'secured_url_port')}")
    
    def _build_connection_url(self) -> str:
        """构建完整连接URL"""
        return f"wss://{self.server_host}:{self.secure_port}/agent"
    
    def _create_two_way_ssl_context(self) -> ssl.SSLContext:
        """创建双向SSL上下文"""
        cert_manager = CertificateManager(self.config, self.server_host)
        cert_manager.initialize_security()
        
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.load_cert_chain(
            certfile=cert_manager.agent_crt_path,
            keyfile=cert_manager.agent_key_path
        )
        
        # 加载服务器CA证书
        ca_cert_path = cert_manager.ca_cert_path
        if not os.path.exists(ca_cert_path):
            raise FileNotFoundError(f"CA证书文件不存在: {ca_cert_path}")
        
        ssl_context.load_verify_locations(cafile=ca_cert_path)
        return srl_context
    
    def _create_stomp_connection(self, ssl_context: Optional[ssl.SSLContext]) -> WsConnection:
        """创建STOMP连接"""
        ssl_options = {"context": ssl_context} if ssl_context else None
        return CloudStompConnection(self.connection_url, ssl_options=ssl_options)
    
    def _establish_connection(self, connection: WsConnection):
        """建立并验证连接"""
        logger.debug("尝试建立连接...")
        try:
            connection.start()
            connection.connect(wait=True)
            logger.info("安全连接成功建立")
        except (socket_error, cloud_stomp.exception.ConnectFailedException) as e:
            # 连接级别的错误
            logger.error("连接失败: %s", e)
            self._safe_disconnect(connection)
            raise ConnectionError(f"无法连接到服务器: {e}") from e
        except ssl.SSLError as e:
            # SSL认证错误
            logger.critical(
                "SSL认证失败: %s\n"
                "可能原因: 1.服务器和代理证书由不同CA签发 "
                "2.证书不匹配\n"
                "解决方案: "
                "- 确保证书由相同CA签发 "
                "- 删除证书文件重新生成 "
                "- 在服务器配置中关闭双向SSL认证",
                e
            )
            self._safe_disconnect(connection)
            raise SecurityException("SSL认证失败") from e
        except Exception as e:
            # 其他意外错误
            logger.exception("连接过程中发生意外错误")
            self._safe_disconnect(connection)
            raise RuntimeError(f"连接异常: {e}") from e
    
    def _safe_disconnect(self, connection: WsConnection):
        """安全断开连接"""
        try:
            if connection.is_connected():
                connection.disconnect()
                logger.debug("连接已安全断开")
        except Exception as e:
            logger.error("断开连接时出错: %s", e, exc_info=True)


class CloudStompConnection(WsConnection):
    """扩展的STOMP连接实现，提供线程安全的消息发送和日志记录"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.correlation_counter = 0
        self.correlation_lock = threading.RLock()
    
    def send(
        self,
        destination: str,
        message: Dict,
        content_type: str = "application/json",
        headers: Optional[Dict] = None,
        sensitive_fields: Tuple = ("passphrase", "keys"),
        **keyword_headers
    ) -> int:
        """发送消息到指定目标，返回关联ID
        
        Args:
            destination: 消息目标地址
            message: 消息内容字典
            content_type: 内容类型，默认为JSON
            headers: 额外头信息
            sensitive_fields: 需要脱敏的敏感字段
            keyword_headers: 其他关键字参数头
        
        Returns:
            correlation_id: 消息关联ID
        """
        # 生成关联ID
        with self.correlation_lock:
            self.correlation_counter += 1
            correlation_id = self.correlation_counter
        
        # 创建安全的消息日志
        log_message = self._create_log_message(message, sensitive_fields)
        logger.info(
            "发送消息到 %s (correlation_id=%d): %s", 
            destination, correlation_id, log_message
        )
        
        # 序列化消息体
        body = json.dumps(message)
        
        # 准备头信息
        headers = headers or {}
        headers.update(correlationId=str(correlation_id))
        
        # 发送消息
        super().send(
            destination, 
            body, 
            content_type=content_type, 
            headers=headers, 
            **keyword_headers
        )
        
        return correlation_id
    
    def _create_log_message(self, message: Dict, sensitive_fields: Tuple) -> str:
        """创建用于日志的消息，敏感字段进行脱敏"""
        try:
            log_message = message.copy()
            for field in sensitive_fields:
                if field in log_message:
                    log_message[field] = "*****"
            return json.dumps(log_message, indent=2)
        except Exception:
            return "<无法序列化的消息>"
    
    def add_listener(self, listener):
        """添加STOMP消息监听器"""
        listener_name = f"{listener.__class__.__name__}_{id(listener)}"
        self.set_listener(listener_name, listener)


class ConnectionCache:
    """管理服务器连接缓存"""
    
    def __init__(self, config: ConfigManager, server_host: str):
        self.config = config
        self.server_host = server_host
        self._manager = SecurityConnectionManager(config, server_host)
        self._connection: Optional[WsConnection] = None
    
    def get_connection(self) -> WsConnection:
        """获取活动连接，如果不可用则创建新连接"""
        if self._connection is None or not self._connection.is_connected():
            logger.info("建立新连接到 %s", self.server_host)
            self._connection = self._manager.create_secure_connection()
        return self._connection
    
    def clear_cache(self):
        """清除当前连接缓存"""
        if self._connection:
            try:
                if self._connection.is_connected():
                    self._connection.disconnect()
            except Exception as e:
                logger.warning("断开连接时出错: %s", e)
            finally:
                self._connection = None
        logger.info("连接缓存已清除")


class CertificateManager:
    """管理SSL证书和密钥的生命周期"""
    
    def __init__(self, config: ConfigManager, server_host: str):
        self.config = config
        self.server_host = server_host
        self.keys_dir = Path(self.config.get("security", "keysdir")).resolve()
        
        # 构建文件路径
        hostname_str = hostname.hostname(self.config)
        self.agent_key_path = self.keys_dir / f"{hostname_str}.key"
        self.agent_crt_path = self.keys_dir / f"{hostname_str}.crt"
        self.agent_csr_path = self.keys_dir / f"{hostname_str}.csr"
        self.ca_cert_path = self.keys_dir / "ca.crt"
        
        # 服务端URL
        self.server_url = (
            f"https://{server_host}:{config.getint('server', 'url_port')}"
        )
        
        logger.info(f"证书管理器初始化: 密钥目录={self.keys_dir}")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保密钥目录存在并有适当权限"""
        if not self.keys_dir.exists():
            logger.info("创建密钥目录: %s", self.keys_dir)
            self.keys_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 设置目录权限为700
            self.keys_dir.chmod(0o700)
        except OSError as e:
            logger.warning("无法设置密钥目录权限: %s", e)
    
    @property
    def security_is_initialized(self) -> bool:
        """检查安全设置是否完整初始化"""
        return all([
            self.agent_key_path.exists(),
            self.agent_crt_path.exists(),
            self.ca_cert_path.exists()
        ])
    
    def initialize_security(self):
        """初始化安全环境，确保所有证书文件就绪"""
        try:
            if not self.security_is_initialized:
                self._download_ca_certificate()
                self._ensure_agent_key()
                self._ensure_agent_certificate()
            else:
                logger.info("安全证书和密钥已存在且有效")
        except Exception as e:
            logger.critical("安全初始化失败: %s", e)
            raise
    
    def _download_ca_certificate(self):
        """确保CA根证书存在"""
        if not self.ca_cert_path.exists():
            logger.info("下载CA证书")
            self._download_ca_cert()
        else:
            logger.info("CA证书已存在")
    
    def _ensure_agent_key(self):
        """确保代理私钥存在"""
        if not self.agent_key_path.exists():
            logger.info("生成新的代理密钥对")
            self._generate_agent_key_pair()
            # 设置密钥权限为600
            try:
                self.agent_key_path.chmod(DEFAULT_KEY_PERMISSION)
            except OSError as e:
                logger.error("无法设置密钥权限: %s", e)
        else:
            logger.info("代理私钥已存在")
    
    def _ensure_agent_certificate(self):
        """确保代理证书存在"""
        if not self.agent_crt_path.exists():
            logger.info("需要签名代理证书")
            self._request_certificate_signing()
        else:
            logger.info("代理证书已存在")
    
    def _download_ca_cert(self):
        """从服务器下载CA根证书"""
        url = f"{self.server_url}/cert/ca/"
        logger.info("从 %s 下载CA证书", url)
        
        try:
            with urllib.request.urlopen(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"下载失败: 状态码 {response.status}")
                
                # 保存CA证书
                cert_data = response.read()
                with open(self.ca_cert_path, "wb") as f:
                    f.write(cert_data)
                logger.info("CA证书保存到 %s", self.ca_cert_path)
        except urllib.error.URLError as e:
            raise ConnectionError(f"无法下载CA证书: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"下载CA证书失败: {e}") from e
    
    def _generate_agent_key_pair(self):
        """生成代理密钥对和证书签名请求(CSR)"""
        # 准备openssl命令
        command = OPENSSL_CMD_FORMAT.format(
            key_path=self.agent_key_path,
            hostname=hostname.hostname(self.config),
            csr_path=self.agent_csr_path
        )
        
        logger.info("执行openssl命令: %s", command)
        
        # 使用子进程执行
        try:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"openssl命令失败 (code={result.returncode}):\n"
                    f"输出: {result.stdout}\n"
                    f"错误: {result.stderr}"
                )
            
            logger.info("成功生成密钥和证书请求")
        except (subprocess.CalledProcessError, OSError) as e:
            raise RuntimeError(f"openssl命令执行错误: {e}") from e
    
    def _request_certificate_signing(self):
        """向服务器发送签名请求"""
        # 读取CSR文件内容
        with open(self.agent_csr_path, "r") as f:
            csr_content = f.read()
        
        # 获取密码短语
        passphrase_env_var = self.config.get("security", "passphrase_env_var_name")
        passphrase = os.getenv(passphrase_env_var)
        if not passphrase:
            raise ValueError(f"未设置密码短语环境变量 {passphrase_env_var}")
        
        # 准备请求数据
        request_data = {
            "csr": csr_content,
            "passphrase": passphrase
        }
        
        url = f"{self.server_url}/certs/{hostname.hostname(self.config)}"
        logger.info("发送签名请求到 %s", url)
        
        try:
            # 创建并发送请求
            request = urllib.request.Request(
                url,
                data=json.dumps(request_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(request) as response:
                # 检查响应状态
                if response.status != 200:
                    raise RuntimeError(f"服务器响应状态码 {response.status}")
                
                # 处理响应
                response_data = json.loads(response.read().decode("utf-8"))
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("服务器签名响应: %s", response_data)
                
                # 处理服务器响应
                if response_data.get("result") == "OK":
                    self._save_agent_certificate(response_data["signedCa"])
                else:
                    error_msg = response_data.get("message", "未指定错误")
                    raise SecurityError(f"证书签名请求失败: {error_msg}")
        except urllib.error.HTTPError as e:
            raise ConnectionError(f"HTTP错误 {e.code}: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"无效的服务器响应JSON: {e}") from e
        except Exception as e:
            logger.exception("签名请求失败")
            raise RuntimeError(f"签名请求错误: {e}") from e
    
    def _save_agent_certificate(self, cert_data: str):
        """保存代理证书"""
        with open(self.agent_crt_path, "w") as f:
            f.write(cert_data)
        logger.info("代理证书保存到 %s", self.agent_crt_path)


# 自定义异常类
class SecurityError(Exception):
    """安全相关异常基类"""
    pass

class CertificateError(SecurityError):
    """证书相关异常"""
    pass

class ConnectionError(SecurityError):
    """连接相关异常"""
    pass

class SecurityException(Exception):
    """安全相关异常"""
    pass
