#!/usr/bin/env python3

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

import logging
import time
from typing import Dict, Any, Tuple, Optional, NamedTuple, Union
from collections import namedtuple
from urllib import request, error as urllib_error, parse
from tempfile import gettempdir
import ssl

from alerts.base_alert import BaseAlert
from alerts.exceptions import WebAlertException
from alerts.alert_utils import format_url_status_message
from cloud_agent.service.resource_management.libraries.functions.url_utils import (
    get_port_from_url,
    get_path_from_url,
    get_host_from_url,
    build_full_url
)
from cloud_agent.service.resource_management.libraries.functions.security_utils import SecurityConfig
from cloud_common.cloud_commons import OSCheck
from cloud_common.cloud_commons.inet_utils import (
    resolve_address,
    ensure_secure_transport,
)
from cloud_common.cloud_commons.constants import AGENT_TMP_DIR
from cloud_agent.service.cloudConfig import cloudConfig

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置常量
DEFAULT_CONNECTION_TIMEOUT = 5  # 默认连接超时时间（秒�?DEFAULT_KINIT_TIMEOUT = 14400  # 默认 Kerberos 票据超时时间�?小时�?DEFAULT_SSL_PROTOCOL = "PROTOCOL_TLSv1_2"  # 默认 SSL 协议版本
DEFAULT_CA_CERT_PATH = "/etc/cloud-agent/ssl/ca_certs.pem"  # 默认 CA 证书路径

# 定义命名元组
WebResponse = namedtuple("WebResponse", "status_code time_millis error_msg")

class URIStructure(NamedTuple):
    """表示监控URI的结构化信息"""
    uri: str
    is_ssl_enabled: bool
    kerberos_principal: Optional[str] = None
    kerberos_keytab: Optional[str] = None
    acceptable_codes: Optional[Tuple[int]] = None
    connection_timeout: int = DEFAULT_CONNECTION_TIMEOUT

class WebAlert(BaseAlert):
    """通过HTTP/HTTPS监控Web服务可用性的告警"""
    
    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        初始化Web监控告警
        
        Args:
            alert_meta: 告警元数据
            alert_source_meta: 告警来源元数据
            config: 配置对象
        """
        super().__init__(alert_meta, alert_source_meta, config)
        
        # 确保安全传输配置
        self._ensure_secure_transport()
        
        # 处理URI配置
        self.uri_structure = self._process_uri_config(alert_source_meta)
        
        # 初始化Kerberos配置
        self.security_config = SecurityConfig(config)
        
        # 初始化连接超时设�?        self.connection_timeout = self.uri_structure.connection_timeout
        self.kinit_timeout = config.get("agent", "alert_kinit_timeout", DEFAULT_KINIT_TIMEOUT)

    def _ensure_secure_transport(self) -> None:
        """确保SSL/TLS协议和CA证书配置正确"""
        try:
            ssl_protocol = cloudConfig.get_resolved_config().get_force_https_protocol_name() or DEFAULT_SSL_PROTOCOL
            ca_cert_path = cloudConfig.get_resolved_config().get_ca_cert_file_path() or DEFAULT_CA_CERT_PATH
            ensure_secure_transport(ssl_protocol, ca_cert_path)
        except Exception as e:
            logger.error(f"安全传输配置失败: {str(e)}")
            raise WebAlertException(f"安全传输配置失败: {str(e)}")

    def _process_uri_config(self, alert_source_meta: Dict) -> URIStructure:
        """处理和解析URI配置信息"""
        if "uri" not in alert_source_meta:
            logger.error("告警源元数据中缺�?'uri' 字段")
            raise ValueError("告警源元数据中缺�?'uri' 字段")
            
        uri_meta = alert_source_meta["uri"]
        try:
            # 提取URI基础信息
            uri = uri_meta.get("value", "")
            is_ssl_enabled = uri_meta.get("ssl", False)
            
            # 提取可选配�?            kerberos_principal = uri_meta.get("kerberos_principal")
            kerberos_keytab = uri_meta.get("kerberos_keytab")
            acceptable_codes = tuple(uri_meta.get("acceptable_codes", []))
            connection_timeout = uri_meta.get("connection_timeout", DEFAULT_CONNECTION_TIMEOUT)
            
            return URIStructure(
                uri=uri,
                is_ssl_enabled=is_ssl_enabled,
                kerberos_principal=kerberos_principal,
                kerberos_keytab=kerberos_keytab,
                acceptable_codes=acceptable_codes,
                connection_timeout=connection_timeout
            )
        except Exception as e:
            logger.error(f"解析URI配置时出�? {str(e)}")
            raise WebAlertException(f"解析URI配置时出�? {str(e)}")

    def _collect(self) -> Tuple[str, list]:
        """
        执行Web服务检查并收集结果
        
        Returns:
            元组，包含状态代码和结果详情
        """
        try:
            # 构建最终监控URL
            target_url = self._build_monitoring_url()
            logger.debug(f"[Alarm][{self.get_name()}] 监控URL: {target_url}")
            
            # 执行Web请求
            response = self._execute_web_request(target_url)
            status_code = response.status_code
            elapsed_time = response.time_millis / 1000.0  # 转换为秒
            
            # 根据响应状态确定告警级�?            if status_code == 0:
                # 无法访问
                message = format_url_status_message(target_url, status_code, error_msg=response.error_msg)
                return self.RESULT_CRITICAL, [status_code, target_url, elapsed_time, message]
            
            # 检查是否在可接受状态码列表�?            if self.uri_structure.acceptable_codes and status_code in self.uri_structure.acceptable_codes:
                message = format_url_status_message(target_url, status_code, elapsed_time)
                return self.RESULT_OK, [status_code, target_url, elapsed_time, message]
            
            # 根据标准HTTP状态码分类
            if 200 <= status_code < 400:
                message = format_url_status_message(target_url, status_code, elapsed_time)
                return self.RESULT_OK, [status_code, target_url, elapsed_time, message]
            else:
                message = format_url_status_message(target_url, status_code, elapsed_time, error_msg=response.error_msg)
                return self.RESULT_WARNING, [status_code, target_url, elapsed_time, message]
                
        except Exception as e:
            logger.exception(f"[Alarm][{self.get_name()}] 收集监控数据时出�?)
            message = f"监控过程出现异常: {str(e)}"
            return self.RESULT_CRITICAL, [0, "", 0, message]

    def _build_monitoring_url(self) -> str:
        """构建最终监控URL"""
        try:
            # 处理URI模板
            resolved_uri = self._resolve_uri_template()
            
            # 如果是完整URL则直接返�?            if resolved_uri.startswith(("http://", "https://")):
                return self._resolve_host_address(resolved_uri)
            
            # 构建完整URL
            return build_full_url(
                uri=resolved_uri,
                is_ssl=self.uri_structure.is_ssl_enabled,
                host=self.host_name,
                default_port=443 if self.uri_structure.is_ssl_enabled else 80
            )
        except Exception as e:
            logger.error(f"构建监控URL失败: {str(e)}")
            raise WebAlertException(f"构建监控URL失败: {str(e)}")

    def _resolve_host_address(self, url: str) -> str:
        """解析URL中的主机地址"""
        host = get_host_from_url(url)
        if host in ["0.0.0.0", "127.0.0.1", "localhost"]:
            resolved_host = resolve_address(host) if OSCheck.is_windows_family() else self.host_name
            return url.replace(host, resolved_host)
        return url

    def _execute_web_request(self, url: str) -> WebResponse:
        """
        执行Web请求
        
        Args:
            url: 要访问的URL
            
        Returns:
            WebResponse对象包含响应信息
        """
        # 获取Kerberos配置
        principal_expr = self.uri_structure.kerberos_principal
        keytab_expr = self.uri_structure.kerberos_keytab
        
        # 检查是否启用Kerberos
        if principal_expr and keytab_expr and self.security_config.is_kerberos_enabled():
            # 执行Kerberos认证的请�?            return self._make_krb_web_request(
                url,
                principal=principal_expr.replace("_HOST", self.host_name),
                keytab=keytab_expr
            )
        
        # 执行普通HTTP请求
        return self._make_regular_web_request(url)

    def _make_krb_web_request(self, url: str, principal: str, keytab: str) -> WebResponse:
        """执行Kerberos认证的Web请求"""
        try:
            from resource_management.libraries.functions.kerberos_utils import KerberosWebRequestHelper
            
            # 创建助手对象
            helper = KerberosWebRequestHelper(
                tmp_dir=AGENT_TMP_DIR or gettempdir(),
                kinit_timeout=self.kinit_timeout,
                agent_name=self.get_name()
            )
            
            # 执行请求
            status, error_msg, elapsed_time = helper.execute_kerberos_request(
                url=url,
                keytab_path=keytab,
                principal=principal,
                request_type="GET",
                timeout=self.connection_timeout,
                label="web_alert",
                security_enabled=True,
                smokeuser=self.security_config.smokeuser()
            )
            
            return WebResponse(status, elapsed_time, error_msg)
            
        except ImportError:
            logger.warning("Kerberos支持不可用，回退到普通请求")
            return self._make_regular_web_request(url)
        except Exception as e:
            logger.exception("Kerberos请求失败")
            return WebResponse(0, 0, f"Kerberos请求失败: {str(e)}")

    def _make_regular_web_request(self, url: str) -> WebResponse:
        """执行普通HTTP/HTTPS请求"""
        start_time = time.monotonic()
        response = None
        status_code = 0
        error_msg = ""
        
        try:
            # 创建请求对象
            req = request.Request(url, method="GET")
            
            # 执行请求并测量时�?            response = request.urlopen(req, timeout=self.connection_timeout)
            status_code = response.status
            
            # 即使成功响应也要检查内�?            if status_code >= 400:
                error_msg = f"HTTP错误 {status_code}"
            else:
                # 快速读取响应头以确保连接完�?                response.read(1)
                
        except urllib_error.HTTPError as e:
            # 处理HTTP错误
            status_code = e.code
            error_msg = f"HTTP错误: {e.code} - {e.reason}"
            
        except urllib_error.URLError as e:
            # 处理URL错误（如连接问题�?            error_msg = f"URL错误: {str(e.reason)}"
            
        except ssl.SSLError as e:
            # 处理SSL错误
            error_msg = f"SSL错误: {str(e)}"
            
        except TimeoutError as e:
            # 处理超时
            error_msg = f"连接超时: {str(e)}"
        
        except Exception as e:
            # 其他未知异常
            error_msg = f"未知错误: {str(e)}"
        
        finally:
            # 确保关闭连接
            if response:
                try:
                    response.close()
                except Exception:
                    pass
            
            # 计算响应时间
            elapsed_ms = (time.monotonic() - start_time) * 1000
            
        return WebResponse(status_code, elapsed_ms, error_msg)
