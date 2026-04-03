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

import time
import logging
from typing import Any, Dict, Optional

from cloud_agent import hostname
from Hardware import Hardware
from HostInfo import HostInfo
from Utils import Utils
from config import ConfigManager


class Register:
    """负责收集主机信息和构建注册数据结构
    
    主要功能：
    1. 收集主机元数据（主机名、公共主机名）
    2. 获取硬件配置信息
    3. 收集环境变量信息
    4. 读取代理版本信息
    5. 构建完整的注册数据结构
    """
    
    def __init__(self, config: ConfigManager):
        """
        初始化注册构建器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 缓存代理启动时间（毫秒）
        self._agent_start_time_ms = int(1000 * time.time())
        
        # 初始化硬件信息收集器
        self._hardware_collector = Hardware(self.config)
        
        # 缓存不会频繁变化的配置值
        self._ping_port = self._get_ping_port(default=8670)
        self._agent_prefix = self.config.get("agent", "prefix", fallback="")
        
        # 缓存版本信息（假设运行时不会改变）
        self._agent_version = Utils.read_agent_version(self.config)
        
        self.logger.debug("Register 初始化完成，代理启动时间: %d", self._agent_start_time_ms)
    
    def build(self, response_id: Optional[str] = "-1") -> Dict[str, Any]:
        """
        构建注册数据结构
        
        Args:
            response_id: 服务器响应ID（默认为"-1"）
        
        Returns:
            完整注册数据字典
        """
        timestamp_ms = int(time.time() * 1000)
        self.logger.debug("开始构建注册数据，时间戳: %d", timestamp_ms)
        
        # 收集主机环境信息
        agent_env = self._collect_agent_environment()
        
        # 构建注册数据结构
        registration_data = {
            "id": int(response_id) if response_id != "-1" else response_id,
            "timestamp": timestamp_ms,
            "hostname": self._get_hostname(),
            "publicHostname": self._get_public_hostname(),
            "currentPingPort": self._ping_port,
            "hardwareProfile": self._hardware_collector.get(),
            "agentEnv": agent_env,
            "agentVersion": self._agent_version,
            "prefix": self._agent_prefix,
            "agentStartTime": self._agent_start_time_ms,
        }
        
        self.logger.debug("注册数据构建完成，详细信息: %s", registration_data.keys())
        return registration_data
    
    def _get_hostname(self) -> str:
        """获取主机名（带缓存）"""
        try:
            return hostname.hostname(self.config)
        except Exception as e:
            self.logger.error("获取主机名失败: %s", str(e))
            return "unknown-host"
    
    def _get_public_hostname(self) -> str:
        """获取公共主机名（带缓存）"""
        try:
            return hostname.public_hostname(self.config)
        except Exception as e:
            self.logger.warning("获取公共主机名失败: %s", str(e))
            return self._get_hostname()  # 回退到私有主机名
    
    def _collect_agent_environment(self) -> Dict[str, Any]:
        """收集代理环境信息"""
        host_info = HostInfo(self.config)
        agent_env = {}
        
        try:
            # 标记为第一次注册，运行所有检查
            host_info.register(agent_env, runExpensiveChecks=True)
            self.logger.debug("收集到 %d 项环境信息", len(agent_env))
        except Exception as e:
            self.logger.error("收集环境信息失败: %s", str(e))
        
        return agent_env
    
    def _get_ping_port(self, default: int = 8670) -> int:
        """安全获取ping端口配置"""
        try:
            port_str = self.config.get("agent", "ping_port", fallback=str(default))
            return int(port_str)
        except (TypeError, ValueError) as e:
            self.logger.warning("无效的ping端口配置，使用默认值 %d: %s", default, str(e))
            return default

