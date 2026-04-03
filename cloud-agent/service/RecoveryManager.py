#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import copy
import time
import threading
import pprint
from typing import Dict, List, Optional, Tuple

from ActionQueue import ActionQueue
from LiveStatus import LiveStatus
from models.commands import (
    CommandStatus,
    RoleCommand,
    CustomCommand,
    AgentCommand,
)

logger = logging.getLogger(__name__)

class RecoveryManager:
    """
    管理和执行Hadoop集群组件的自动恢复功能
    主要功能：
    - 监控组件的当前状态和期望状态
    - 根据状态差异生成恢复命令
    - 实现恢复操作的限制策略
    - 管理从集群配置加载恢复策略
    """
    
    # 状态常量
    BLUEPRINT_STATE_IN_PROGRESS = "IN_PROGRESS"
    COMPONENT_STATE_STARTED = "STARTED"
    COMPONENT_STATE_INSTALLED = "INSTALLED"
    COMPONENT_STATE_INIT = "INIT"
    COMPONENT_STATE_INSTALL_FAILED = "INSTALL_FAILED"
    COMPONENT_STATE_DEAD = LiveStatus.DEAD_STATUS
    COMPONENT_STATE_LIVE = LiveStatus.LIVE_STATUS
    
    # 命令类型常量
    COMMAND_TYPE = "commandType"
    ROLE_COMMAND = "roleCommand"
    ROLE = "role"
    TASK_ID = "taskId"
    CLUSTER_ID = "clusterId"
    
    # 恢复类型常量
    RECOVERY_DISABLED = "DISABLED"
    RECOVERY_AUTO_START = "AUTO_START"
    RECOVERY_AUTO_INSTALL_START = "AUTO_INSTALL_START"
    RECOVERY_FULL = "FULL"
    
    # 恢复报告状态
    REPORT_RECOVERABLE = "RECOVERABLE"
    REPORT_DISABLED = "DISABLED"
    REPORT_PARTIALLY_RECOVERABLE = "PARTIALLY_RECOVERABLE"
    REPORT_UNRECOVERABLE = "UNRECOVERABLE"
    
    # 默认值
    DEFAULT_MAX_COUNT = 6
    DEFAULT_WINDOW_MIN = 60
    DEFAULT_RETRY_GAP = 5
    DEFAULT_MAX_LIFETIME_COUNT = 12
    
    # 文件名
    RECOVERY_FILE_NAME = "recovery.json"

    def __init__(
        self,
        initializer_module,
        recovery_enabled: bool = False,
        auto_start_only: bool = False,
        auto_install_start: bool = False,
    ):
        # 初始化核心参数
        self.initializer_module = initializer_module
        self.host_level_params_cache = initializer_module.host_level_params_cache
        self.configurations_cache = initializer_module.configurations_cache
        
        # 恢复相关参数
        self.recovery_enabled = recovery_enabled
        self.auto_start_only = auto_start_only
        self.auto_install_start = auto_install_start
        
        # 状态和操作跟踪
        self.statuses: Dict[str, Dict] = {}  # 组件状态字典
        self.actions: Dict[str, Dict] = {}   # 恢复操作跟踪
        self.component_service_map: Dict[str, str] = {}  # 组件到服务映射
        
        # 恢复限制参数
        self.max_count = self.DEFAULT_MAX_COUNT
        self.window_min = self.DEFAULT_WINDOW_MIN
        self.retry_gap = self.DEFAULT_RETRY_GAP
        self.max_lifetime_count = self.DEFAULT_MAX_LIFETIME_COUNT
        self.window_sec = self.window_min * 60
        self.retry_gap_sec = self.retry_gap * 60
        
        # 集群ID跟踪
        self.cluster_id: Optional[str] = None
        self.id = int(time.time())  # 用于生成唯一任务ID
        
        # 状态锁 - 保证状态更新的线程安全
        self.status_lock = threading.RLock()
        
        # 初始化集群配置
        self._initialize_cluster_config()
        
        # 设置允许的状态转换
        self._set_allowed_states()
    
    def _initialize_cluster_config(self):
        """从缓存中初始化集群配置"""
        # 尝试从配置缓存获取集群ID
        if self.configurations_cache:
            self.cluster_id = next(iter(self.configurations_cache.keys()), None)
        
        # 如果从配置缓存未获取到集群ID，尝试从主机级别参数获取
        if not self.cluster_id and self.host_level_params_cache:
            self.cluster_id = next(iter(self.host_level_params_cache.keys()), None)
        
        # 应用恢复配置
        if self.cluster_id:
            if self.configurations_cache and self.cluster_id in self.configurations_cache:
                self.on_config_update()
            
            if self.host_level_params_cache and self.cluster_id in self.host_level_params_cache:
                self.update_recovery_config(self.host_level_params_cache[self.cluster_id])
    
    def _set_allowed_states(self):
        """根据恢复类型设置允许的状态转换"""
        self.allowed_desired_states = [self.COMPONENT_STATE_STARTED, self.COMPONENT_STATE_INSTALLED]
        self.allowed_current_states = [
            self.COMPONENT_STATE_INIT,
            self.COMPONENT_STATE_INSTALL_FAILED,
            self.COMPONENT_STATE_INSTALLED,
            self.COMPONENT_STATE_STARTED
        ]
        
        if self.auto_start_only:
            self.allowed_desired_states = [self.COMPONENT_STATE_STARTED]
            self.allowed_current_states = [self.COMPONENT_STATE_INSTALLED]
        elif self.auto_install_start:
            self.allowed_desired_states = [self.COMPONENT_STATE_INSTALLED, self.COMPONENT_STATE_STARTED]
            self.allowed_current_states = [self.COMPONENT_STATE_INSTALL_FAILED, self.COMPONENT_STATE_INSTALLED]
    
    def enabled(self) -> bool:
        """检查恢复功能是否启用"""
        return self.recovery_enabled and self.cluster_id is not None
    
    def update_config(
        self,
        max_count: int,
        window_min: int,
        retry_gap: int,
        max_lifetime_count: int,
        recovery_enabled: bool,
        auto_start_only: bool,
        auto_install_start: bool,
    ):
        """
        更新恢复配置参数
        """
        # 验证配置有效性
        invalid_config = False
        
        if max_count <= 0:
            logger.warning("恢复已禁用: max_count 必须为正数")
            invalid_config = True
        
        if window_min <= 0:
            logger.warning("恢复已禁用: window_min 必须为正数")
            invalid_config = True
        
        if retry_gap < 1:
            logger.warning("恢复已禁用: retry_gap 必须为至少1的正数")
            invalid_config = True
        
        if retry_gap >= window_min:
            logger.warning("恢复已禁用: retry_gap 必须小于 window_min")
            invalid_config = True
        
        if max_lifetime_count < 0 or max_lifetime_count < max_count:
            logger.warning("恢复已禁用: max_lifetime_count 必须大于0且大于等于max_count")
            invalid_config = True
        
        # 更新配置
        if not invalid_config:
            self.max_count = max_count
            self.window_min = window_min
            self.retry_gap = retry_gap
            self.window_sec = window_min * 60
            self.retry_gap_sec = retry_gap * 60
            self.max_lifetime_count = max_lifetime_count
            self.recovery_enabled = recovery_enabled
            self.auto_start_only = auto_start_only
            self.auto_install_start = auto_install_start
        else:
            self.recovery_enabled = False
        
        # 重新设置允许的状态
        self._set_allowed_states()
    
    def update_recovery_config(self, cluster_config: Dict):
        """从集群配置更新恢复设置"""
        recovery_config = cluster_config.get("recoveryConfig", {})
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("恢复配置: %s", pprint.pformat(recovery_config))
        
        # 更新启用的组件
        enabled_components = []
        components = recovery_config.get("components", [])
        
        for item in components:
            service_name = item["service_name"]
            component_name = item["component_name"]
            desired_state = item["desired_state"]
            
            enabled_components.append(component_name)
            self.update_desired_status(component_name, desired_state)
            
            # 维护组件到服务的映射
            self.component_service_map[component_name] = service_name
        
        self.enabled_components = enabled_components
        
        logger.info("更新后的恢复组件: %s", self.enabled_components)
    
    def on_config_update(self):
        """当集群配置更新时调用"""
        if self.cluster_id not in self.configurations_cache:
            return
        
        cluster_cache = self.configurations_cache[self.cluster_id]
        config_env = cluster_cache.get("configurations", {}).get("cluster-env", {})
        
        # 获取恢复类型
        recovery_type = config_env.get("recovery_type", "DISABLED").upper()
        recovery_enabled = recovery_type not in ["", "DISABLED"]
        auto_start_only = recovery_type == self.RECOVERY_AUTO_START
        auto_install_start = recovery_type == self.RECOVERY_AUTO_INSTALL_START
        
        # 如果未设置恢复类型，但启用了恢复
        if not recovery_type and config_env.get("recovery_enabled", "").lower() == "true":
            recovery_enabled = True
        
        # 获取恢复参数
        max_count = self._get_int_config(config_env, "recovery_max_count", self.DEFAULT_MAX_COUNT)
        window_min = self._get_int_config(config_env, "recovery_window_in_minutes", self.DEFAULT_WINDOW_MIN)
        retry_gap = self._get_int_config(config_env, "recovery_retry_interval", self.DEFAULT_RETRY_GAP)
        max_lifetime = self._get_int_config(config_env, "recovery_lifetime_max_count", self.DEFAULT_MAX_LIFETIME_COUNT)
        
        # 更新配置
        self.update_config(
            max_count=max_count,
            window_min=window_min,
            retry_gap=retry_gap,
            max_lifetime_count=max_lifetime,
            recovery_enabled=recovery_enabled,
            auto_start_only=auto_start_only,
            auto_install_start=auto_install_start
        )
    
    def _get_int_config(self, config: Dict, key: str, default: int) -> int:
        """从配置项安全获取整数值"""
        try:
            return int(config.get(key, default))
        except (TypeError, ValueError):
            logger.warning("配置项 %s 不是有效整数，使用默认值 %d", key, default)
            return default
    
    def update_current_status(self, component: str, state: str):
        """更新组件的当前状态"""
        with self.status_lock:
            if component not in self.statuses:
                self.statuses[component] = {
                    "current": state,
                    "desired": "",
                    "stale_config": False
                }
                logger.info("为新组件 %s 设置当前状态: %s", component, state)
            else:
                if self.statuses[component]["current"] != state:
                    logger.info("更新 %s 的当前状态: %s -> %s", 
                               component, self.statuses[component]["current"], state)
                    self.statuses[component]["current"] = state
    
    def update_desired_status(self, component: str, state: str):
        """更新组件的期望状态"""
        with self.status_lock:
            if component not in self.statuses:
                self.statuses[component] = {
                    "current": "",
                    "desired": state,
                    "stale_config": False
                }
                logger.info("为新组件 %s 设置期望状态: %s", component, state)
            else:
                if self.statuses[component]["desired"] != state:
                    logger.info("更新 %s 的期望状态: %s -> %s", 
                               component, self.statuses[component]["desired"], state)
                    self.statuses[component]["desired"] = state
    
    def update_config_staleness(self, component: str, is_stale: bool):
        """更新组件的配置陈旧状态"""
        with self.status_lock:
            if component not in self.statuses:
                self.statuses[component] = {
                    "current": "",
                    "desired": "",
                    "stale_config": is_stale
                }
            else:
                self.statuses[component]["stale_config"] = is_stale
    
    def requires_recovery(self, component: str) -> bool:
        """
        确定组件是否需要恢复操作
        
        组件需要恢复的几种情况：
        1. 组件启用了恢复功能
        2. 组件的当前状态与期望状态不匹配
        3. 组件的配置已过时需要更新
        """
        # 基本检查：功能启用、组件在恢复列表、状态存在
        if not self.enabled():
            return False
        
        if component not in self.enabled_components:
            return False
        
        if component not in self.statuses:
            return False
        
        status = self.statuses[component]
        
        # 检查是否正在蓝图部署中
        if self.is_blueprint_provisioning(component):
            logger.debug("组件 %s 正在蓝图部署中，跳过恢复", component)
            return False
        
        # 状态一致性检查
        current_state = status["current"]
        desired_state = status["desired"]
        
        # 自动启动模式只处理特定状态变化
        if self.auto_start_only or self.auto_install_start:
            if desired_state not in self.allowed_desired_states:
                logger.debug("组件 %s 的期望状态 %s 不允许在自动模式下恢复", component, desired_state)
                return False
            
            if current_state == desired_state and not status["stale_config"]:
                logger.debug("组件 %s 的状态一致且配置未过时，不需要恢复", component)
                return False
        else:
            # 完整模式 - 检查状态一致性和配置过时
            if current_state == desired_state and not status["stale_config"]:
                logger.debug("组件 %s 的状态一致且配置未过时，不需要恢复", component)
                return False
        
        # 状态有效性检查
        if desired_state not in self.allowed_desired_states:
            logger.info("组件 %s 的期望状态 %s 不允许恢复", component, desired_state)
            return False
        
        if current_state not in self.allowed_current_states:
            logger.info("组件 %s 的当前状态 %s 不允许恢复", component, current_state)
            return False
        
        logger.info("组件 %s 需要恢复操作 (当前状态: %s, 期望状态: %s)", 
                   component, current_state, desired_state)
        return True
    
    def is_blueprint_provisioning(self, component: str) -> bool:
        """检查组件是否正在蓝图部署中"""
        try:
            blueprint_state = self.host_level_params_cache[self.cluster_id][
                "blueprint_provisioning_state"
            ].get(component, "NONE")
            return blueprint_state == self.BLUEPRINT_STATE_IN_PROGRESS
        except (KeyError, TypeError):
            return False
    
    def get_recovery_commands(self) -> List[Dict]:
        """获取所有需要恢复的组件的恢复命令"""
        recovery_commands = []
        
        with self.status_lock:
            for component in self.statuses.keys():
                if not self.requires_recovery(component):
                    continue
                
                if not self.may_execute(component):
                    logger.debug("当前不允许对 %s 执行恢复操作", component)
                    continue
                
                # 获取恢复命令
                command = self._build_recovery_command(component)
                if command:
                    self.execute(component)
                    logger.info("为组件 %s 创建恢复命令: %s", component, command[self.COMMAND_ID])
                    recovery_commands.append(command)
        
        return recovery_commands
    
    def _build_recovery_command(self, component: str) -> Optional[Dict]:
        """根据组件状态构建恢复命令"""
        status = self.statuses.get(component, {})
        current_state = status.get("current", "")
        desired_state = status.get("desired", "")
        
        logger.debug("为组件 %s 构建恢复命令 (当前状态: %s, 期望状态: %s)", 
                   component, current_state, desired_state)
        
        # 自动启动模式 (仅START)
        if self.auto_start_only:
            if current_state == self.COMPONENT_STATE_INSTALLED and desired_state == self.COMPONENT_STATE_STARTED:
                return self._build_start_command(component)
        
        # 自动安装启动模式 (INSTALL->START)
        elif self.auto_install_start:
            if current_state == self.COMPONENT_STATE_INSTALLED and desired_state == self.COMPONENT_STATE_STARTED:
                return self._build_start_command(component)
            elif current_state == self.COMPONENT_STATE_INSTALL_FAILED and desired_state == self.COMPONENT_STATE_STARTED:
                return self._build_install_command(component)
            elif current_state == self.COMPONENT_STATE_INSTALL_FAILED and desired_state == self.COMPONENT_STATE_INSTALLED:
                return self._build_install_command(component)
        
        # 完全恢复模式
        else:
            # 状态转换处理
            if desired_state != current_state:
                # 从安装状态到启动状态
                if current_state == self.COMPONENT_STATE_INSTALLED and desired_state == self.COMPONENT_STATE_STARTED:
                    return self._build_start_command(component)
                
                # 从初始化状态到安装状态
                elif current_state == self.COMPONENT_STATE_INIT and desired_state == self.COMPONENT_STATE_INSTALLED:
                    return self._build_install_command(component)
                
                # 从失败状态到安装/启动状态
                elif current_state == self.COMPONENT_STATE_INSTALL_FAILED:
                    if desired_state == self.COMPONENT_STATE_STARTED:
                        return self._build_install_command(component)
                    elif desired_state == self.COMPONENT_STATE_INSTALLED:
                        return self._build_install_command(component)
                
                # 从启动状态到安装状态 (停止后再安装)
                elif current_state == self.COMPONENT_STATE_STARTED and desired_state == self.COMPONENT_STATE_INSTALLED:
                    return self._build_stop_command(component)
            
            # 配置过时需要重新安装/重启
            else:
                if current_state == self.COMPONENT_STATE_INSTALLED and status["stale_config"]:
                    return self._build_install_command(component)
                elif current_state == self.COMPONENT_STATE_STARTED and status["stale_config"]:
                    return self._build_restart_command(component)
        
        logger.debug("没有找到组件 %s 的适用恢复命令", component)
        return None
    
    def may_execute(self, action: str) -> bool:
        """检查是否允许执行恢复操作"""
        if not action:
            return False
        
        # 维护操作计数器
        with self.status_lock:
            if action not in self.actions:
                self.actions[action] = self._create_action_counter()
            
            action_counter = self.actions[action]
        
        # 检查操作限制
        now = int(time.time())
        last_attempt_sec = now - action_counter["lastAttempt"]
        
        # 是否超过生命周期限制
        if action_counter["lifetimeCount"] >= self.max_lifetime_count:
            if not action_counter["warnedThresholdReached"]:
                logger.warning(
                    "操作 %s 已达到生命周期限制 %d，将跳过恢复",
                    action, self.max_lifetime_count
                )
                action_counter["warnedThresholdReached"] = True
            return False
        
        # 是否在计数限制内
        if action_counter["count"] < self.max_count:
            # 检查是否满足重试间隔要求
            if last_attempt_sec > self.retry_gap_sec:
                return True
            else:
                if not action_counter["warnedLastAttempt"]:
                    logger.info(
                        "操作 %s 仍需等待 %d 秒才能重试 (上次尝试距今 %d 秒)",
                        action, self.retry_gap_sec, last_attempt_sec
                    )
                    action_counter["warnedLastAttempt"] = True
                return False
        
        # 检查时间窗口是否已重置可用
        last_reset_sec = now - action_counter["lastReset"]
        return last_reset_sec > self.window_sec
    
    def execute(self, action: str) -> bool:
        """执行恢复操作并更新计数器状态"""
        if not action:
            return False
        
        with self.status_lock:
            if action not in self.actions:
                self.actions[action] = self._create_action_counter()
            
            action_counter = self.actions[action]
            now = int(time.time())
            seconds_since_last_attempt = now - action_counter["lastAttempt"]
            
            # 如果超过时间窗口，重置计数器
            if seconds_since_last_attempt > self.window_sec:
                action_counter["count"] = 0
                action_counter["lastReset"] = now
                action_counter["warnedLastReset"] = False
            
            # 执行操作计数更新
            if action_counter["count"] < self.max_count:
                if seconds_since_last_attempt > self.retry_gap_sec:
                    action_counter["count"] += 1
                    action_counter["lifetimeCount"] += 1
                    action_counter["lastAttempt"] = now
                    action_counter["warnedLastAttempt"] = False
                    
                    # 第一次执行时设置上次重置时间
                    if action_counter["count"] == 1:
                        action_counter["lastReset"] = now
                    
                    logger.debug("执行操作 %s (当前计数: %d)", action, action_counter["count"])
                    return True
            else:
                # 在时间窗口内达到最大尝试次数
                if now - action_counter["lastReset"] > self.window_sec:
                    action_counter["count"] = 1
                    action_counter["lifetimeCount"] += 1
                    action_counter["lastAttempt"] = now
                    action_counter["lastReset"] = now
                    action_counter["warnedLastReset"] = False
                    
                    logger.debug("重置窗口后执行操作 %s", action)
                    return True
                else:
                    if not action_counter["warnedLastReset"]:
                        logger.warning(
                            "操作 %s 已达到窗口内最大尝试次数 %d (窗口: %d分钟)",
                            action, self.max_count, self.window_min
                        )
                        action_counter["warnedLastReset"] = True
            
            return False
    
    def _create_action_counter(self) -> Dict:
        """创建新的操作计数器"""
        return {
            "lastAttempt": 0,
            "count": 0,
            "lastReset": 0,
            "lifetimeCount": 0,
            "warnedLastAttempt": False,
            "warnedLastReset": False,
            "warnedThresholdReached": False,
        }
    
    def get_unique_task_id(self) -> int:
        """生成唯一的任务ID"""
        self.id += 1
        return self.id
    
    def _build_command(self, component: str, role_command: str, custom_command: Optional[str] = None) -> Dict:
        """构建命令字典的基础方法"""
        if not self.cluster_id:
            logger.warning("没有找到集群ID，无法构建恢复命令")
            return None
        
        command_id = self.get_unique_task_id()
        
        command = {
            self.CLUSTER_ID: self.cluster_id,
            self.ROLE_COMMAND: role_command,
            self.COMMAND_TYPE: AgentCommand.auto_execution,
            self.TASK_ID: command_id,
            self.ROLE: component,
            self.COMMAND_ID: command_id,
        }
        
        # 从映射中获取服务名称
        service_name = self.component_service_map.get(component)
        if service_name:
            command["serviceName"] = service_name
        
        # 添加自定义命令类型
        if custom_command:
            command["custom_command"] = custom_command
        
        return command
    
    def _build_start_command(self, component: str) -> Dict:
        """构建启动命令"""
        return self._build_command(component, RoleCommand.start)
    
    def _build_stop_command(self, component: str) -> Dict:
        """构建停止命令"""
        return self._build_command(component, RoleCommand.stop)
    
    def _build_install_command(self, component: str) -> Dict:
        """构建安装命令"""
        return self._build_command(component, RoleCommand.install)
    
    def _build_restart_command(self, component: str) -> Dict:
        """构建重启命令"""
        return self._build_command(component, RoleCommand.custom_command, custom_command=CustomCommand.restart)
    
    def process_execution_command(self, command: Dict):
        """处理接收到的执行命令，更新期望状态"""
        if not self.enabled():
            return
        
        # 仅处理执行命令类型
        if command.get(self.COMMAND_TYPE) != AgentCommand.execution:
            return
        
        component = command.get(self.ROLE)
        if not component or not self.configured_for_recovery(component):
            return
        
        role_command = command.get(self.ROLE_COMMAND)
        
        # 处理STOP/INSTALL命令
        if role_command in (RoleCommand.stop, RoleCommand.install):
            self.update_desired_status(component, LiveStatus.DEAD_STATUS)
            logger.info(
                "处理 %s 命令 (%s), 更新 %s 的期望状态为 DEAD", 
                role_command, command.get(self.TASK_ID, "unknown"), component
            )
        
        # 处理START命令
        elif role_command == RoleCommand.start:
            self.update_desired_status(component, LiveStatus.LIVE_STATUS)
            logger.info(
                "处理 START 命令 (%s), 更新 %s 的期望状态为 LIVE", 
                command.get(self.TASK_ID, "unknown"), component
            )
        
        # 处理自定义重启命令
        elif (
            role_command == RoleCommand.custom_command 
            and command.get("custom_command") == CustomCommand.restart
        ):
            self.update_desired_status(component, LiveStatus.LIVE_STATUS)
            logger.info(
                "处理 RESTART 命令 (%s), 更新 %s 的期望状态为 LIVE", 
                command.get(self.TASK_ID, "unknown"), component
            )
    
    def process_execution_command_result(self, command: Dict, status: str):
        """处理执行命令的结果，更新当前状态"""
        if not self.enabled() or command.get(self.ROLE_COMMAND) is None:
            return
        
        component = command.get(self.ROLE)
        if not self.configured_for_recovery(component):
            return
        
        role_command = command.get(self.ROLE_COMMAND)
        task_id = command.get(self.TASK_ID, "unknown")
        
        logger.debug("处理 %s 命令 (%s) 的结果: %s", role_command, task_id, status)
        
        # 启动命令成功
        if (
            status == CommandStatus.completed 
            and role_command == RoleCommand.start
        ):
            self.update_current_status(component, LiveStatus.LIVE_STATUS)
            logger.info(
                "启动命令成功，更新 %s 的当前状态为 LIVE", component
            )
        
        # 停止/安装命令成功
        elif (
            status == CommandStatus.completed 
            and role_command in (RoleCommand.stop, RoleCommand.install)
        ):
            self.update_current_status(component, LiveStatus.DEAD_STATUS)
            logger.info(
                "停止/安装命令成功，更新 %s 的当前状态为 DEAD", component
            )
        
        # 重启命令成功
        elif (
            status == CommandStatus.completed 
            and role_command == RoleCommand.custom_command 
            and command.get("custom_command") == CustomCommand.restart
        ):
            self.update_current_status(component, LiveStatus.LIVE_STATUS)
            logger.info(
                "重启命令成功，更新 %s 的当前状态为 LIVE", component
            )
        
        # 安装命令失败
        elif (
            status == CommandStatus.failed 
            and role_command == RoleCommand.install
        ):
            self.update_current_status(component, self.COMPONENT_STATE_INSTALL_FAILED)
            logger.warning(
                "安装命令失败，更新 %s 的当前状态为 INSTALL_FAILED", component
            )
    
    def configured_for_recovery(self, component: str) -> bool:
        """检查组件是否配置了恢复"""
        return component in self.enabled_components
    
    def get_recovery_report(self) -> Dict:
        """生成恢复状态报告"""
        if not self.enabled():
            return {"summary": self.REPORT_DISABLED}
        
        report = {"summary": self.REPORT_RECOVERABLE}
        component_reports = []
        recovery_states = []
        non_recoverable_count = 0
        
        with self.status_lock:
            for component, action_counter in self.actions.items():
                limit_reached = action_counter["lifetimeCount"] >= self.max_lifetime_count
                recovery_state = {
                    "name": component,
                    "numAttempts": action_counter["lifetimeCount"],
                    "limitReached": limit_reached
                }
                recovery_states.append(recovery_state)
                
                if limit_reached:
                    non_recoverable_count += 1
        
        report["componentReports"] = recovery_states
        
        # 根据不可恢复组件数量确定总体状态
        if non_recoverable_count == len(recovery_states):
            report["summary"] = self.REPORT_UNRECOVERABLE
        elif non_recoverable_count > 0:
            report["summary"] = self.REPORT_PARTIALLY_RECOVERABLE
        
        return report
