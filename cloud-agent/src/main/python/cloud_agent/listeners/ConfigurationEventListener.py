#!/usr/bin/env python3
"""
高级配置事件监听器 - 用于分布式系统中配置的动态更新与管理
提供集群配置的实时同步、配置版本控制和恢复管理机制
"""

import logging
import copy
from typing import Dict, Any, Optional, Set

# 导入必要的模块
from cloud_agent.listeners import EventListener
from cloud_agent import Constants
from cloud_agent.caching import ConfigurationsCache
from cloud_agent.recovery import RecoveryManager

# 获取日志记录器
logger = logging.getLogger(__name__)


class ConfigurationEventListener(EventListener):
    """
    配置事件监听器 - 负责处理集群配置变更的实时更新
    
    核心功能：
        1. 监听集群配置变更事件
        2. 维护配置的本地缓存
        3. 触发配置相关的恢复管理
        4. 支持多集群配置管理
        5. 自动处理超大配置的日志记录
    """
    
    # 不需要日志详情的配置类型
    _SUPPRESSED_CONFIG_TYPES: Set[str] = {
        "raw_content", "credentials", "passwords", "tokens"
    }
    
    # 需要截断显示的内容长度阈值
    _TRUNCATION_THRESHOLD: int = 100
    
    def __init__(self, initializer_module: Any):
        """
        初始化配置监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.configurations_cache: ConfigurationsCache = initializer_module.configurations_cache
        self.recovery_manager: RecoveryManager = initializer_module.recovery_manager
        logger.info("配置事件监听器已初始化")

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理集群配置变更事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        try:
            # 提取并更新配置时间戳
            if timestamp := message.pop("timestamp", None):
                self.configurations_cache.timestamp = timestamp
                logger.debug("配置时间戳更新: %s", timestamp)
            
            # 处理空消息（哈希未变更）
            if not message or message == {}:
                logger.debug("配置状态未变更，跳过更新")
                return
            
            # 提取集群配置
            clusters_data = message.get("clusters", {})
            config_hash = message.get("hash", "")
            
            # 重写配置缓存
            self.configurations_cache.rewrite_cache(clusters_data, config_hash)
            logger.info("配置缓存更新成功，集群数: %d, 版本: %s", len(clusters_data), config_hash[:8])
            
            # 处理集群配置更新
            if clusters_data:
                self._process_clusters_update(clusters_data)
                
        except Exception as e:
            logger.error(
                "处理配置事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )

    def _process_clusters_update(self, clusters_data: Dict[str, Dict]) -> None:
        """
        处理集群配置更新
        
        Args:
            clusters_data: 集群配置字典
        """
        logger.info("处理 %d 个集群的配置更新", len(clusters_data))
        
        # 如果支持多集群，则处理所有配置变更
        if self.recovery_manager.supports_multi_cluster:
            for cluster_id in clusters_data:
                self._update_cluster_recovery(cluster_id)
        # 否则只处理第一个集群
        else:
            if cluster_ids := list(clusters_data.keys()):
                primary_cluster = cluster_ids[0]
                logger.warning(
                    "恢复管理器不支持多集群, 仅更新首个集群 (%s)", 
                    primary_cluster
                )
                self._update_cluster_recovery(primary_cluster)
            else:
                logger.warning("集群配置更新为空，跳过恢复管理器更新")

    def _update_cluster_recovery(self, cluster_id: str) -> None:
        """
        更新单个集群的恢复管理器
        
        Args:
            cluster_id: 集群ID
        """
        logger.info("更新集群 %s 的恢复管理器", cluster_id)
        self.recovery_manager.set_current_cluster(cluster_id)
        self.recovery_manager.on_config_update()

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.CONFIGURATIONS_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成配置事件的精简日志字符串
        
        Args:
            headers: 消息头
            message_json: 消息内容
            
        Returns:
            格式化的日志字符串
        """
        try:
            # 创建消息副本避免改变原始数据
            log_message = copy.deepcopy(message_json)
            clusters = log_message.get("clusters", {})
            
            # 遍历所有集群和配置类型
            for cluster_config in clusters.values():
                if configs := cluster_config.get("configurations"):
                    self._truncate_configurations(configs)
            
            return super().get_log_message(headers, log_message)
        
        except Exception as e:
            logger.error("构建日志消息失败: %s", e, exc_info=True)
            return super().get_log_message(headers, message_json)

    def _truncate_configurations(self, configs: Dict[str, Any]) -> None:
        """
        截断配置内容以便日志展示
        
        Args:
            configs: 配置字典
        """
        for config_type, config_data in configs.items():
            if not isinstance(value, dict):
                continue
            
            # 处理敏感配置类型
            if key in self._SUPPRESSED_CONFIG_TYPES:
                configs[key] = "***SENSITIVE_DATA_SUPPRESSED***"
                continue
            
            # 递归处理嵌套配置
            if "properties" in value and isinstance(value["properties"], dict):
                self._truncate_config_properties(value["properties"])
            
            # 截断过长的内容
            if "content" in value and len(value["content"]) > self._TRUNCATION_THRESHOLD:
                value["content"] = value["content"][:self._TRUNCATION_THRESHOLD] + "..."

    def _truncate_config_properties(self, properties: Dict[str, Any]) -> None:
        """
        截断配置属性以便日志展示
        
        Args:
            properties: 配置属性字典
        """
        for key, value in properties.items():
            # 处理敏感属性
            if "password" in key.lower() or "secret" in key.lower():
                properties[key] = "***SENSITIVE_DATA_SUPPRESSED***"
                continue
            
            # 截断过长值
            if isinstance(value, str) and len(value) > self._TRUNCATION_THRESHOLD:
                properties[key] = value[:self._TRUNCATION_THRESHOLD] + "..."
