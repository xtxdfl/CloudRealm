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
import datetime
from typing import Dict, Any, Tuple, Optional
from alerts.base_alert import BaseAlert

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 默认恢复操作阈值
DEFAULT_WARNING_THRESHOLD = 2
DEFAULT_CRITICAL_THRESHOLD = 4

# 默认组件名称
UNKNOWN_COMPONENT = "UNKNOWN_COMPONENT"

class RecoveryAlert(BaseAlert):
    """恢复操作告警类：监控组件的恢复操作次数并触发告警"""
    
    def __init__(
        self, 
        alert_meta: Dict, 
        alert_source_meta: Dict, 
        config: Any, 
        recovery_manager: Any
    ):
        """
        初始化恢复告警
        
        Args:
            alert_meta: 告警元数据
            alert_source_meta: 告警源数据
            config: 全局配置
            recovery_manager: 恢复管理器
        """
        super().__init__(alert_meta, alert_source_meta, config)
        
        # 存储恢复管理器实例
        self.recovery_manager = recovery_manager
        
        # 初始化警告和严重阈值
        self.warning_threshold = DEFAULT_WARNING_THRESHOLD
        self.critical_threshold = DEFAULT_CRITICAL_THRESHOLD
        
        # 从配置中加载自定义阈值
        self._load_recovery_thresholds(alert_source_meta)
        
        # 验证阈值设置是否合理
        if self.critical_threshold <= self.warning_threshold:
            logger.warning(
                f"[告警][{self.get_name()}] 严重阈值({self.critical_threshold})必须大于警告阈值({self.warning_threshold})"
            )
    
    def _load_recovery_thresholds(self, alert_source_meta: Dict) -> None:
        """
        从配置中加载恢复操作阈值
        
        Args:
            alert_source_meta: 告警源数据
        """
        # 检查配置中是否有报告定义
        reporting_config = alert_source_meta.get("reporting", {})
        
        # 获取警告阈值
        if BaseAlert.RESULT_WARNING.lower() in reporting_config:
            warning_config = reporting_config[BaseAlert.RESULT_WARNING.lower()]
            if "count" in warning_config:
                self.warning_threshold = warning_config["count"]
        
        # 获取严重阈值
        if BaseAlert.RESULT_CRITICAL.lower() in reporting_config:
            critical_config = reporting_config[BaseAlert.RESULT_CRITICAL.lower()]
            if "count" in critical_config:
                self.critical_threshold = critical_config["count"]
    
    def _collect(self) -> Tuple[str, list]:
        """
        收集恢复操作的统计信息并确定告警状态
        
        Returns:
            元组 (告警状态, 报告数据)
        """
        # 从元数据中获取组件名称，默认为UNKNOWN_COMPONENT
        component_name = self.alert_meta.get("componentName", UNKNOWN_COMPONENT)
        
        # 记录调试日志
        logger.debug(
            f"[告警][{self.get_name()}] 检查组件恢复操作: {component_name}"
        )
        
        # 获取该组件的恢复操作信息
        try:
            recovery_info = self._get_recovery_info(component_name)
        except Exception as e:
            logger.error(f"[告警][{self.get_name()}] 获取恢复信息失败: {str(e)}")
            return BaseAlert.RESULT_UNKNOWN, [f"系统错误: {str(e)}"]
        
        # 提取恢复信息
        recovered_times = recovery_info.get("count", 0)
        last_reset = recovery_info.get("lastReset")
        warned_threshold_reached = recovery_info.get("warnedThresholdReached", False)
        
        # 格式化重置时间
        last_reset_text = ""
        if last_reset:
            last_reset_dt = datetime.datetime.fromtimestamp(last_reset)
            last_reset_text = f"自上次重置后 ({last_reset_dt.strftime('%Y-%m-%d %H:%M')})"
        
        # 确定告警状态
        alert_state = self._determine_alert_state(
            recovered_times, 
            warned_threshold_reached
        )
        
        # 返回告警结果
        return alert_state, [
            last_reset_text,
            recovered_times,
            component_name
        ]
    
    def _get_recovery_info(self, component_name: str) -> Dict:
        """
        获取组件的恢复操作信息
        
        Args:
            component_name: 组件名称
            
        Returns:
            恢复操作信息的字典
        """
        # 获取所有组件的恢复操作副本
        all_recovery_actions = self.recovery_manager.get_actions_copy()
        
        # 获取特定组件的恢复信息
        component_info = all_recovery_actions.get(component_name, {})
        
        # 检查恢复信息是否过期
        is_stale = self._is_recovery_info_stale(component_name)
        
        # 如果信息已过期且未达到警告阈值，则重置计数和时间戳
        if is_stale and not component_info.get("warnedThresholdReached", False):
            return {"count": 0, "lastReset": int(time.time())}
        
        # 返回组件信息
        return component_info
    
    def _is_recovery_info_stale(self, component_name: str) -> bool:
        """
        检查恢复信息是否过期
        
        Args:
            component_name: 组件名称
            
        Returns:
            是否过期
        """
        try:
            return self.recovery_manager.is_action_info_stale(component_name)
        except Exception as e:
            logger.error(f"[告警][{self.get_name()}] 检查过期状态失败: {str(e)}")
            return False
    
    def _determine_alert_state(
        self, 
        recovered_count: int, 
        warned_threshold_reached: bool
    ) -> str:
        """
        根据恢复次数确定告警状态
        
        Args:
            recovered_count: 恢复操作次数
            warned_threshold_reached: 警告阈值是否已触发
            
        Returns:
            告警状态字符串
        """
        # 如果已达到警告阈值并且超过最大生命周期计数，直接返回CRITICAL
        if warned_threshold_reached:
            logger.debug(f"[告警][{self.get_name()}] 警告阈值已达上限")
            return BaseAlert.RESULT_CRITICAL
        
        # 比较恢复次数与阈值
        if recovered_count >= self.critical_threshold:
            return BaseAlert.RESULT_CRITICAL
        elif recovered_count >= self.warning_threshold:
            return BaseAlert.RESULT_WARNING
        elif recovered_count < self.warning_threshold:
            return BaseAlert.RESULT_OK
        else:
            # 未知情况，应记录警告
            logger.warning(
                f"[告警][{self.get_name()}] 无法确定状态: {recovered_count}次恢复"
            )
            return BaseAlert.RESULT_UNKNOWN
    
    def get_reporting_text(self, state: str) -> str:
        """
        根据状态获取报告文本模板
        
        Args:
            state: 告警状态
            
        Returns:
            报告文本模板字符串
        """
        if state == BaseAlert.RESULT_OK:
            return "组件 `{2}` 运行正常{0}，恢复操作次数: {1}"
        else:
            return "{1}次恢复操作{0}发生在组件 `{2}` 上"

