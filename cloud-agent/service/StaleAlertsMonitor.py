#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import time
import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

# 定义默认陈旧阈值系数
DEFAULT_STALE_THRESHOLD_MULTIPLIER = 3.0

class StaleAlertsMonitor:
    """
    监控长时间未执行的告警，并将这些"陈旧告警"报告给服务器
    
    主要功能:
    1. 跟踪每个告警的最后执行时间
    2. 根据告警定义计算陈旧超时阈值
    3. 定期扫描陈旧的告警并报告
    
    设计目标:
    - 高效识别长期未执行的告警
    - 灵活适应不同的告警定义和集群配置
    - 避免误报和漏报
    - 提供详细的日志记录便于故障排查
    """
    
    def __init__(self, initializer_module):
        """
        初始化陈旧告警监控器
        
        Args:
            initializer_module: 初始化模块，提供告警定义缓存的访问
        """
        self.alert_definitions_cache = initializer_module.alert_definitions_cache
        self.alert_last_run_times = {}  # {alert_id: last_run_timestamp}
        self.cluster_stale_multipliers = {}  # 缓存各集群的陈旧阈值系数
        
        # 统计指标
        self.metrics = {
            "last_check_time": 0.0,
            "last_stale_count": 0,
            "total_stale_reports": 0
        }
        logger.info("陈旧告警监控器已初始化")

    def save_executed_alerts(self, alerts: List[Dict[str, Any]]):
        """
        保存已执行告警的时间戳
        
        当告警成功执行时调用此方法更新最后执行时间
        
        Args:
            alerts: 已执行告警的列表，每个告警应包含'timestamp'和'definitionId'
        """
        if not alerts:
            return
            
        update_count = 0
        for alert in alerts:
            try:
                # 告警信息有效性检查
                if "timestamp" not in alert or "definitionId" not in alert:
                    logger.warning("无效的告警记录: %s", alert)
                    continue
                    
                # 转换时间戳格式 (ms -> s)
                alert_id = alert["definitionId"]
                timestamp = alert["timestamp"] / 1000.0
                
                # 更新告警最后执行时间
                self.alert_last_run_times[alert_id] = timestamp
                update_count += 1
            except (ValueError, TypeError) as e:
                logger.error("更新告警执行时间出错: %s, 告警数据: %s", e, alert)
        
        logger.debug("为 %d 个告警更新了最后执行时间", update_count)

    def get_stale_alerts(self) -> List[Dict[str, Any]]:
        """
        获取陈旧的告警列表
        
        计算逻辑:
        1. 根据告警定义的间隔时间计算陈旧阈值
            陈旧阈值 = 告警间隔 × 陈旧阈值系数
        2. 当前时间超过最后执行时间+陈旧阈值的告警视为陈旧
        
        Returns:
            包含陈旧告警信息的列表: [{"id": alert_id, "timestamp": last_run_time_ms}]
        """
        if not self.alert_definitions_cache:
            return []
        
        current_time = time.time()
        stale_alerts = []
        
        # 统计指标计数器
        alerts_checked = 0
        stale_detected = 0
        
        for cluster_id, command in self.alert_definitions_cache.items():
            if not command or not command.get("alertDefinitions"):
                logger.debug("集群 %s 没有告警定义", cluster_id)
                continue
                
            # 获取集群的陈旧阈值系数
            stale_multiplier = self._get_cluster_stale_multiplier(cluster_id, command)
            
            for definition in command["alertDefinitions"]:
                alerts_checked += 1
                try:
                    # 获取告警基本信息
                    alert_id = definition["definitionId"]
                    alert_name = definition.get("name", f"unnamed_{alert_id}")
                    interval_minutes = definition.get("interval", 0)
                    
                    # 无效告警定义检查
                    if not alert_id or interval_minutes <= 0:
                        logger.warning("无效的告警定义: %s", definition)
                        continue
                    
                    # 转换为秒
                    interval_seconds = interval_minutes * 60
                    stale_threshold = interval_seconds * stale_multiplier
                    
                    # 获取最后执行时间
                    last_run = self.alert_last_run_times.get(alert_id)
                    if last_run is None:
                        # 对于新告警，记录当前时间为初始值
                        last_run = self._initialize_last_run_time(alert_id)
                    
                    # 计算时间差
                    time_since_last_run = current_time - last_run
                    
                    # 检查是否陈旧
                    if time_since_last_run > stale_threshold:
                        # 转换为毫秒以保持一致格式
                        last_run_ms = int(last_run * 1000)
                        stale_alerts.append({
                            "id": alert_id,
                            "name": alert_name,
                            "timestamp": last_run_ms,
                            "cluster": cluster_id,
                            "interval_minutes": interval_minutes
                        })
                        stale_detected += 1
                        logger.warning(
                            "告警检测为陈旧: [%s] %s (已过期 %.1f 分钟)",
                            alert_id, alert_name, (time_since_last_run - interval_seconds) / 60
                        )
                        
                except KeyError as e:
                    logger.error("告警定义缺少必要字段 %s: %s", e, definition)
                except ValueError as e:
                    logger.error("处理告警定义出错: %s, 数据: %s", e, definition)
        
        # 更新统计指标
        self.metrics.update({
            "last_check_time": current_time,
            "last_stale_count": stale_detected,
            "total_stale_reports": self.metrics.get("total_stale_reports", 0) + stale_detected
        })
        
        logger.info(
            "完成陈旧告警扫描: 检查了 %d 个告警，发现 %d 个陈旧告警",
            alerts_checked, stale_detected
        )
        
        return stale_alerts

    def _get_cluster_stale_multiplier(self, cluster_id: str, command: Dict[str, Any]) -> float:
        """获取集群的告警陈旧阈值系数"""
        # 如果已缓存则直接返回
        if cluster_id in self.cluster_stale_multipliers:
            return self.cluster_stale_multipliers[cluster_id]
        
        # 从配置获取或使用默认值
        multiplier = command.get("staleIntervalMultiplier", DEFAULT_STALE_THRESHOLD_MULTIPLIER)
        
        # 验证系数值
        if not isinstance(multiplier, (int, float)) or multiplier < 1.5:
            logger.warning(
                "集群 %s 的陈旧告警系数无效: %s, 使用默认值 %.1f",
                cluster_id, multiplier, DEFAULT_STALE_THRESHOLD_MULTIPLIER
            )
            multiplier = DEFAULT_STALE_THRESHOLD_MULTIPLIER
        
        # 缓存并返回
        self.cluster_stale_multipliers[cluster_id] = multiplier
        logger.debug(
            "集群 %s 告警陈旧阈值系数: %.1f", 
            cluster_id, multiplier
        )
        return multiplier

    def _initialize_last_run_time(self, alert_id: str) -> float:
        """初始化新告警的最后执行时间"""
        # 设置为当前时间减去一个小偏移，避免立即触发陈旧检测
        initial_time = time.time() - 60  # 减去60秒避免误判
        self.alert_last_run_times[alert_id] = initial_time
        logger.info("为新告警初始化最后执行时间: %s", alert_id)
        return initial_time

    def get_monitor_metrics(self) -> Dict[str, Any]:
        """获取监控器指标数据，用于健康检查"""
        return {
            # 告警统计
            "total_tracked_alerts": len(self.alert_last_run_times),
            "last_stale_count": self.metrics.get("last_stale_count", 0),
            "total_stale_reports": self.metrics.get("total_stale_reports", 0),
            "last_check_time": self.metrics.get("last_check_time", 0),
            "stale_threshold_multipliers": dict(self.cluster_stale_multipliers),
            
            # 告警定义统计
            "clusters_with_alerts": len(self.alert_definitions_cache),
            "clusters_with_stale_multiplier": len(self.cluster_stale_multipliers)
        }
