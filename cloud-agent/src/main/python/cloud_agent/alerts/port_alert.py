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
import socket
import time
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum

from alerts.base_alert import BaseAlert, AlertState
from resource_management.libraries.functions.url_utils import (
    get_port_from_url,
    get_host_from_url,
    extract_hosts_from_uri_value
)
from cloud_commons.inet_utils import (
    resolve_address, 
    is_ipv6_address,
    validate_port_number,
    calculate_connection_timeout,
    log_host_resolution
)

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 常量定义
DEFAULT_WARNING_TIMEOUT = 1.5  # 默认警告阈值（秒）
DEFAULT_CRITICAL_TIMEOUT = 5.0  # 默认严重阈值（秒）
MAX_ALLOWED_TIMEOUT = 30.0  # 最大允许超时时间（秒）
DEFAULT_PORT_COMMAND_TIMEOUT = 3.0  # 端口命令操作默认超时时间

class SocketCommandMode(Enum):
    """端口命令模式枚举"""
    NONE = "NONE"
    SEND_ONLY = "SEND_ONLY"
    SEND_RECEIVE = "SEND_RECEIVE"

@dataclass
class PortAlertConfig:
    """端口告警配置数据类"""
    uri: Optional[str] = None
    default_port: Optional[int] = None
    warning_timeout: float = DEFAULT_WARNING_TIMEOUT
    critical_timeout: float = DEFAULT_CRITICAL_TIMEOUT
    socket_command: Optional[bytes] = None
    command_mode: SocketCommandMode = SocketCommandMode.NONE
    expected_response: Optional[bytes] = None

class PortAlert(BaseAlert):
    """TCP端口连通性与响应时间监控告警类"""
    
    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        初始化端口监控告警
        
        Args:
            alert_meta: 告警元数据
            alert_source_meta: 告警来源元数据
            config: 配置对象
        """
        super().__init__(alert_meta, alert_source_meta, config)
        
        # 解析并验证配置
        self.config = self._parse_alert_source_config(alert_source_meta)
        self._validate_timeout_thresholds()
        
    def _parse_alert_source_config(self, alert_source_meta: Dict) -> PortAlertConfig:
        """解析并构建端口监控配置"""
        config = PortAlertConfig()
        
        # 基础URI配置
        config.uri = alert_source_meta.get("uri")
        
        # 默认端口配置
        if "default_port" in alert_source_meta:
            port = alert_source_meta["default_port"]
            if isinstance(port, str) and port.strip().isdigit():
                config.default_port = int(port)
            elif isinstance(port, int):
                config.default_port = port
        
        # 设置告警阈值
        reporting = alert_source_meta.get("reporting", {})
        state_warning = AlertState.WARNING.name.lower()
        state_critical = AlertState.CRITICAL.name.lower()
        
        if state_warning in reporting and "value" in reporting[state_warning]:
            config.warning_timeout = float(reporting[state_warning]["value"])
        
        if state_critical in reporting and "value" in reporting[state_critical]:
            config.critical_timeout = float(reporting[state_critical]["value"])
        
        # 处理端口命令参数
        if "parameters" in alert_source_meta:
            for param in alert_source_meta["parameters"]:
                name, value = param.get("name"), param.get("value")
                
                if name == "socket.command" and value:
                    config.socket_command = value.encode('utf-8')
                    config.command_mode = SocketCommandMode.SEND_ONLY
                
                if name == "socket.command.response" and value:
                    config.expected_response = value.encode('utf-8')
                    if config.socket_command:
                        config.command_mode = SocketCommandMode.SEND_RECEIVE
                        
        return config
    
    def _validate_timeout_thresholds(self) -> None:
        """验证并修正超时阈值设置"""
        alert_name = self.get_name()
        
        # 验证警告阈值
        if not (0 < self.config.warning_timeout <= MAX_ALLOWED_TIMEOUT):
            logger.warning(
                f"[警报][{alert_name}] 无效警告阈值 {self.config.warning_timeout}秒，重置为默认值 {DEFAULT_WARNING_TIMEOUT}秒"
            )
            self.config.warning_timeout = DEFAULT_WARNING_TIMEOUT
        
        # 验证严重阈值
        if not (0 < self.config.critical_timeout <= MAX_ALLOWED_TIMEOUT):
            logger.warning(
                f"[警报][{alert_name}] 无效严重阈值 {self.config.critical_timeout}秒，重置为默认值 {DEFAULT_CRITICAL_TIMEOUT}秒"
            )
            self.config.critical_timeout = DEFAULT_CRITICAL_TIMEOUT
        
        # 确保警告阈值小于严重阈值
        if self.config.warning_timeout >= self.config.critical_timeout:
            logger.warning(
                f"[警报][{alert_name}] 警告阈值({self.config.warning_timeout})不能大于等于严重阈值({self.config.critical_timeout})"
            )
            self.config.warning_timeout = self.config.critical_timeout * 0.75
    
    def _collect(self) -> Tuple[AlertState, List]:
        """
        执行端口监控并收集结果
        
        Returns:
            元组 (告警状态, 结果详情)
        """
        # 获取配置
        configurations = self.configuration_builder.get_configuration(self.cluster_id)
        uri_value = self._get_config_value(configurations)
        
        # 解析主机地址和端口
        host_candidates = self._resolve_host_candidates(uri_value)
        port = self._resolve_port(uri_value)
        
        # 验证端口
        if not validate_port_number(port):
            return AlertState.UNKNOWN, [f"无效端口号: {port}"]
        
        # 尝试连接所有候选主机
        result = self._test_connection_to_hosts(host_candidates, port)
        return result if result else (AlertState.CRITICAL, ["所有连接尝试失败"])
    
    def _get_config_value(self, configurations: Dict) -> Optional[str]:
        """获取端口配置值"""
        if not self.config.uri:
            logger.debug(f"[警报][{self.get_name()}] 使用主机名: {self.host_name}")
            return self.host_name
        
        # 尝试获取配置值
        value = self._get_configuration_value(configurations, self.config.uri)
        if not value:
            logger.debug(f"[警报][{self.get_name()}] 未指定URI, 使用主机名: {self.host_name}")
            return self.host_name
        
        return value
    
    def _resolve_host_candidates(self, uri_value: str) -> List[str]:
        """解析需要监控的主机候选地址"""
        host_not_specified = False
        hosts = []
        
        # 解析URI值
        if uri_value:
            parsed_hosts = extract_hosts_from_uri_value(uri_value, self.host_name)
            
            if parsed_hosts:
                hosts.extend(parsed_hosts)
                host_not_specified = all(
                    host in ["0.0.0.0", "localhost", self.host_name] 
                    for host in parsed_hosts
                )
        
        # 如果没有指定主机，添加当前主机和公共主机
        if host_not_specified or not hosts:
            hosts.append(self.host_name)
            if self.public_host_name and self.public_host_name != self.host_name:
                hosts.append(self.public_host_name)
        
        # 记录日志
        log_host_resolution(self.get_name(), hosts)
        return hosts
    
    def _resolve_port(self, uri_value: str) -> int:
        """从URI值或配置中解析端口号"""
        # 尝试从URI中获取端口
        try:
            port_val = get_port_from_url(uri_value)
            if port_val and port_val.isdigit():
                return int(port_val)
        except Exception:
            pass
        
        # 使用默认端口
        if self.config.default_port is not None:
            return self.config.default_port
        
        # 没有找到有效端口
        logger.error(f"[警报][{self.get_name()}] 无法从URI或配置中解析端口")
        return 0
    
    def _test_connection_to_hosts(self, hosts: List[str], port: int) -> Optional[Tuple[AlertState, List]]:
        """尝试连接一组主机并测试响应时间"""
        last_exception = None
        
        for host in hosts:
            try:
                resolution_info = ""
                
                # IPv6特殊处理
                if is_ipv6_address(host):
                    logger.debug(f"[警报][{self.get_name()}] 检测到IPv6地址 {host}")
                    resolution_info = f"IPv6地址 {host}"
                else:
                    resolved_host = host
                    
                    # 在Windows上需要解析0.0.0.0
                    if host in ["0.0.0.0"]:
                        resolved_host = resolve_address(host)
                        resolution_info = f"已解析 {host} → {resolved_host}"
                
                # 尝试连接
                result = self._test_host_connection(resolved_host, port)
                
                # 记录成功日志
                if result[0] == AlertState.OK:
                    logger.debug(
                        f"[警报][{self.get_name()}] {host}:{port} 连接成功 "
                        f"(响应时间: {result[1][0]:.4f}秒) {resolution_info}"
                    )
                else:
                    logger.warning(
                        f"[警报][{self.get_name()}] {host}:{port} 连接问题 - {result[0].name}: {result[1][0]}"
                    )
                
                return result
                
            except Exception as e:
                last_exception = str(e)
                logger.debug(f"[警报][{self.get_name()}] {host}:{port} 连接失败: {str(e)}")
                
        # 所有主机都失败
        return AlertState.CRITICAL, [
            f"所有连接失败: {last_exception or '未知错误'}", 
            hosts[0] if hosts else "无主机", 
            port
        ]
    
    def _test_host_connection(self, host: str, port: int) -> Tuple[AlertState, List]:
        """测试单个主机的连接"""
        # 设置连接超时（包含命令操作的额外时间）
        timeout = calculate_connection_timeout(
            base_timeout=self.config.critical_timeout,
            command_mode=self.config.command_mode
        )
        
        # 创建socket
        address_family = socket.AF_INET6 if ":" in host else socket.AF_INET
        sock = socket.socket(address_family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        try:
            # 测量连接时间
            start_time = time.perf_counter()
            sock.connect((host, port))
            
            # 处理端口命令
            if self.config.command_mode != SocketCommandMode.NONE:
                self._handle_socket_command(sock)
                
            # 计算总响应时间
            elapsed_time = time.perf_counter() - start_time
            
            # 基于响应时间确定状态
            if elapsed_time >= self.config.critical_timeout:
                return AlertState.CRITICAL, ["响应超时", host, port]
            
            state = AlertState.WARNING if elapsed_time >= self.config.warning_timeout else AlertState.OK
            return state, [elapsed_time, host, port]
            
        finally:
            try:
                sock.close()
            except Exception:
                pass
    
    def _handle_socket_command(self, sock: socket.socket) -> None:
        """处理端口命令和响应验证"""
        # 发送命令
        if self.config.socket_command:
            sock.sendall(self.config.socket_command)
        
        # 等待并验证响应
        if self.config.command_mode == SocketCommandMode.SEND_RECEIVE:
            data = sock.recv(1024)
            
            if self.config.expected_response and data != self.config.expected_response:
                raise Exception(
                    f"预期响应: {self.config.expected_response!r}, 实际响应: {data!r}"
                )
    
    def _get_reporting_text(self, state: AlertState) -> str:
        """
        获取告警报告文本模板
        
        Args:
            state: 告警状态
            
        Returns:
            报告文本模板字符串
        """
        if state == AlertState.OK:
            return "TCP OK - {0:.4f} 秒内响应于 {1}:{2}"
        
        if state == AlertState.WARNING:
            return "TCP 警告 - {0:.4f} 秒响应于 {1}:{2}"
            
        return "连接失败: {0} 位置 {1}:{2}"

