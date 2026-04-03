#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import sys
import socket
import urllib.request
import urllib.error
import urllib.parse
import logging
import subprocess
import time
import functools
import hashlib
import shlex
from typing import List, Optional, Dict
from pathlib import Path

# 配置日志
logger = logging.getLogger("HostnameResolver")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 缓存TTL（秒）
CACHE_TTL = 300  # 5分钟
CACHE_ID_SUFFIX = os.getenv("CACHE_INVALIDATOR", str(time.time()))

def cached_result(func):
    """带缓存的装饰器，支持TTL刷新"""
    cache = {}
    last_refresh = {}
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 创建唯一缓存键
        arg_hash = hashlib.md5()
        arg_hash.update(str(args).encode())
        arg_hash.update(str(kwargs).encode())
        arg_hash.update(CACHE_ID_SUFFIX.encode())
        key = f"{func.__name__}_{arg_hash.hexdigest()}"
        
        # 检查缓存有效性
        current_time = time.time()
        if last_refresh.get(key, 0) + CACHE_TTL > current_time and key in cache:
            return cache[key]
        
        # 更新缓存
        try:
            result = func(*args, **kwargs)
            cache[key] = result
            last_refresh[key] = current_time
            return result
        except Exception as e:
            logger.error(f"执行 {func.__name__} 失败: {str(e)}")
            raise
    
    return wrapper

class HostnameResolver:
    """高级主机名解析服务
    
    提供多重主机名识别机制：
    1. 自定义脚本解析（支持自定义逻辑）
    2. 云提供商元数据服务（AWS等）
    3. 系统内置方法（socket.getfqdn）
    4. 配置驱动解析（静态配置）
    """
    
    def __init__(self, config: Dict = None):
        """初始化解析器"""
        self.config = config or {}
        self.fqdn_cache = None
        self.public_hostname_cache = None
        self.server_hostnames_cache = []
        self._cache_timestamps = {}
        self._setup_logger()
        logger.info(f"主机名解析器初始化完成 | {self.system_fingerprint()}")

    def system_fingerprint(self) -> str:
        """生成系统唯一标识"""
        uname = os.uname()
        uid = hashlib.md5(f"{uname.nodename}_{uname.machine}".encode()).hexdigest()[:8]
        return f"{uid}@{uname.sysname}-{uname.release}"

    def _setup_logger(self):
        """配置日志级别"""
        log_level = self.config.get("logging", {}).get("level", "INFO")
        try:
            logger.setLevel(getattr(logging, log_level.upper()))
        except ValueError:
            logger.setLevel(logging.INFO)

    @cached_result
    def hostname(self) -> str:
        """获取本地主机名（FQDN格式）"""
        logger.debug("获取本地主机名...")
        
        # 方法1: 使用自定义脚本
        script_path = self.config.get("agent", {}).get("hostname_script")
        if script_path:
            try:
                result = self._run_command(script_path)
                if result and result.strip():
                    fqdn = result.strip().lower()
                    logger.info(f"从自定义脚本 '{script_path}' 获取主机名: {fqdn}")
                    return fqdn
            except Exception as e:
                logger.warning(f"自定义脚本执行失败但已恢复: {str(e)}")
        
        # 方法2: 使用系统FQDN
        try:
            fqdn = socket.getfqdn().lower()
            logger.info(f"使用系统方法获取主机名: {fqdn}")
            return fqdn
        except Exception as e:
            logger.error(f"系统主机名获取失败: {str(e)}")
            # 最终回退
            hostname = os.uname().nodename.lower()
            logger.warning(f"使用系统主机名降级方案: {hostname}")
            return hostname

    @cached_result
    def public_hostname(self) -> str:
        """获取公共主机名（面向外网）"""
        logger.debug("获取公共主机名...")
        
        # 方法1: 自定义脚本
        script_path = self.config.get("agent", {}).get("public_hostname_script")
        if script_path:
            try:
                result = self._run_command(script_path)
                if result and result.strip():
                    public_hostname = result.strip().lower()
                    logger.info(f"从自定义脚本 '{script_path}' 获取公共主机名: {public_hostname}")
                    return public_hostname
            except Exception as e:
                logger.warning(f"公共主机名脚本执行失败: {str(e)}")
        
        # 方法2: 云服务提供商元数据
        try:
            cloud_hostname = self._get_cloud_metadata_hostname()
            if cloud_hostname:
                logger.info(f"从云元数据服务获取公共主机名: {cloud_hostname}")
                return cloud_hostname
        except Exception as e:
            logger.info(f"云主机名不可用: {str(e)}")
        
        # 方法3: 使用本地主机名作为回退
        try:
            fqdn = self.hostname()
            logger.info(f"回退到本地主机名作为公共主机名: {fqdn}")
            return fqdn
        except:
            # 最终回退
            logger.error("无法获取有效公共主机名")
            return "unknown-host"

    @cached_result
    def server_hostnames(self) -> List[str]:
        """获取集群服务器主机名列表"""
        logger.debug("获取服务器主机名列表...")
        
        # 方法1: 自定义脚本
        script_path = self.config.get("server", {}).get("hostname_script")
        if script_path:
            try:
                result = self._run_command(script_path)
                if result and result.strip():
                    hosts = self._parse_csv_hosts(result)
                    logger.info(f"从自定义脚本 '{script_path}' 获取服务器主机: {hosts}")
                    return hosts
            except Exception as e:
                logger.warning(f"服务器主机名脚本执行失败: {str(e)}")
        
        # 方法2: 静态配置
        static_hosts = self.config.get("server", {}).get("hostname", "")
        if static_hosts:
            try:
                hosts = self._parse_csv_hosts(static_hosts)
                logger.info(f"从静态配置获取服务器主机: {hosts}")
                return hosts
            except Exception as e:
                logger.error(f"服务器主机名解析失败: {str(e)}")
        
        # 最终回退
        logger.error("无法获取任何服务器主机名")
        return ["localhost"]

    def _run_command(self, command: str, timeout: int = 5) -> str:
        """安全执行外部命令"""
        try:
            # 验证命令路径
            if not command:
                raise ValueError("空命令")
                
            if not os.path.exists(command):
                raise FileNotFoundError(f"命令路径不存在: {command}")
                
            # 安全执行命令
            result = subprocess.run(
                [command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=True
            )
            
            # 检查命令返回值
            if result.returncode != 0:
                error_msg = result.stderr.strip() or f"命令返回错误代码: {result.returncode}"
                raise RuntimeError(error_msg)
                
            return result.stdout
        except FileNotFoundError as fnf:
            logger.error(f"脚本文件未找到: {command}", exc_info=fnf)
            raise
        except subprocess.TimeoutExpired:
            logger.warning(f"命令执行超时: {command}")
            raise RuntimeError("命令执行超时")
        except Exception as e:
            logger.error(f"命令执行发生未知错误: {command}", exc_info=e)
            raise RuntimeError(str(e))

    def _parse_csv_hosts(self, csv_str: str) -> List[str]:
        """解析逗号分隔的主机名列表"""
        if not csv_str:
            return []
            
        normalized_hosts = [
            host.strip().lower() 
            for host in csv_str.split(",") 
            if host.strip()
        ]
        
        # 验证主机名格式
        invalid_hosts = []
        for host in normalized_hosts:
            if not self._validate_hostname(host):
                invalid_hosts.append(host)
                logger.warning(f"无效主机名格式: {host}")
        
        # 移除无效主机名
        valid_hosts = [host for host in normalized_hosts if host not in invalid_hosts]
        
        if not valid_hosts:
            logger.error("未找到有效主机名")
            raise ValueError("有效主机名列表为空")
            
        return valid_hosts

    def _validate_hostname(self, hostname: str) -> bool:
        """验证主机名格式"""
        try:
            # 基础长度验证
            if len(hostname) > 255 or len(hostname) == 0:
                return False
                
            # RFC 1123 规范验证
            if not all(c.isalnum() or c in ['-', '.', '_'] for c in hostname):
                return False
                
            # 不允许双点号或开头/结尾特殊字符
            if ".." in hostname or hostname.startswith(".") or hostname.endswith("."):
                return False
                
            return True
        except:
            return False

    def _get_cloud_metadata_hostname(self) -> Optional[str]:
        """从云服务商元数据获取主机名"""
        # 支持的多云元数据端点
        metadata_endpoints = [
            "http://169.254.169.254/latest/meta-data/public-hostname",  # AWS
            "http://metadata.google.internal/computeMetadata/v1/instance/hostname",  # GCP
            "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2020-09-01"  # Azure
        ]
        
        headers = {
            "Metadata-Flavor": "Google",
            "User-Agent": "CloudHostnameResolver/1.0"
        }
        
        # 尝试每个端点
        for endpoint in metadata_endpoints:
            try:
                request = urllib.request.Request(
                    endpoint, 
                    headers=headers,
                    timeout=2
                )
                
                with urllib.request.urlopen(request) as response:
                    if 200 <= response.status < 300:
                        hostname = response.read().decode().strip().lower()
                        endpoint_name = endpoint.split('/')[2]
                        logger.debug(f"从 {endpoint_name} 获取云主机名: {hostname}")
                        return hostname
            except urllib.error.URLError as e:
                logger.debug(f"元数据端点不可达: {endpoint} - {str(e.reason)}")
            except Exception as e:
                logger.debug(f"元数据提取失败: {endpoint} - {str(e)}")
                
        return None

# 配置示例
DEFAULT_CONFIG = {
    "agent": {
        "hostname_script": "/opt/cloud/bin/hostname-resolver.sh",
        "public_hostname_script": "/opt/cloud/bin/public-hostname-resolver.sh"
    },
    "server": {
        "hostname_script": "/opt/cloud/bin/server-resolver.sh",
        "hostname": "server1.example.com,server2.example.com"
    },
    "logging": {
        "level": "INFO"
    }
}

def main():
    """主函数演示如何使用解析器"""
    logger.info("Cloud主机名解析服务启动")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 测试缓存性能
        resolver = HostnameResolver(DEFAULT_CONFIG)
        print("缓存性能测试 (连续5次调用):")
        
        test_cases = [
            ("主机名", resolver.hostname),
            ("公共主机名", resolver.public_hostname),
            ("服务器主机名", resolver.server_hostnames)
        ]
        
        for name, method in test_cases:
            print(f"\n{name} 测试:")
            start_time = time.time()
            for i in range(5):
                start_call = time.time()
                result = method()
                end_call = time.time() * 1000
                print(f"  调用 {i+1}: 结果={result[:15]}{'...' if len(str(result))>15 else ''} | 耗时: {(end_call - start_call):.2f}ms")
            end_time = time.time()
            print(f"  总耗时: {(end_time - start_time)*1000:.2f}ms")
    else:
        # 正常使用
        resolver = HostnameResolver(DEFAULT_CONFIG)
        
        try:
            host_info = {
                "hostname": resolver.hostname(),
                "public_hostname": resolver.public_hostname(),
                "server_hostnames": resolver.server_hostnames()
            }
            
            print("主机名解析结果:")
            print(json.dumps(host_info, indent=2))
        except KeyboardInterrupt:
            logger.info("用户中断操作")
        except Exception as e:
            logger.critical(f"致命错误: {str(e)}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    import json
    main()
