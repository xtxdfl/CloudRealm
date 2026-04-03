#!/usr/bin/env python3
"""
高级主机级参数监听器 - 用于分布式系统中主机级别参数的动态更新与管理
提供集群配置的实时同步、配置版本控制和恢复管理机制
"""

import logging
from typing import Dict, Any, List, Optional

# 导入必要的模块
from cloud_agent.listeners import EventListener
from cloud_agent import Constants
from cloud_agent.caching import HostLevelParamsCache
from cloud_agent.recovery import RecoveryManager

# 获取日志记录器
logger = logging.getLogger(__name__)


class HostLevelParamsEventListener(EventListener):
    """
    主机级参数监听器 - 负责处理主机级别配置参数的实时更新
    
    核心功能：
        1. 监听主机级参数配置变更事件
        2. 维护主机级参数的本地缓存
        3. 同步恢复管理器的配置
        4. 支持多集群参数管理
        5. 保证参数更新的原子性
    """
    
    def __init__(self, initializer_module: Any):
        """
        初始化主机级参数监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.host_level_params_cache: HostLevelParamsCache = initializer_module.host_level_params_cache
        self.recovery_manager: RecoveryManager = initializer_module.recovery_manager
        logger.info("主机级参数监听器已初始化")

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理主机级参数变更事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        # 处理心跳/空更新事件
        if not message or message == {}:
            logger.debug("收到主机级参数心跳信号, 配置状态未变更")
            return
        
        try:
            # 提取配置集群和哈希版本
            clusters_data = message.get("clusters", {})
            config_hash = message.get("hash", "")
            
            # 重写缓存
            success = self.host_level_params_cache.rewrite_cache(clusters_data, config_hash)
            if not success:
                logger.error("主机级参数缓存更新失败")
                return
            
            # 处理集群恢复配置
            self._process_cluster_recovery_configs(clusters_data)
            
            logger.info(
                "成功更新主机级参数缓存, 集群数: %d, 版本: %s",
                len(clusters_data), config_hash
            )
        
        except Exception as e:
            logger.error(
                "处理主机级参数事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )

    def _process_cluster_recovery_configs(self, clusters_data: Dict[str, Dict]) -> None:
        """
        处理集群的恢复配置更新
        
        Args:
            clusters_data: 集群配置数据字典
        """
        # 筛选出带有恢复配置的集群
        clusters_with_recovery = [
            cluster_id for cluster_id, cluster_config in clusters_data.items()
            if cluster_config and "recoveryConfig" in cluster_config
        ]
        
        if not clusters_with_recovery:
            logger.debug("未检测到集群恢复配置更新")
            return
        
        logger.info("检测到 %d 个集群的恢复配置变更", len(clusters_with_recovery))
        
        # 遍历所有需要更新的集群
        for cluster_id in clusters_with_recovery:
            recovery_config = clusters_data[cluster_id]["recoveryConfig"]
            
            # 验证恢复配置有效性
            if not self._validate_recovery_config(recovery_config):
                logger.warning("集群 %s 的恢复配置无效", cluster_id)
                continue
            
            # 更新恢复管理器
            self.recovery_manager.set_current_cluster(cluster_id)
            self.recovery_manager.update_recovery_config(recovery_config)

    def _validate_recovery_config(self, recovery_config: Dict[str, Any]) -> bool:
        """
        验证恢复配置的完整性
        
        Args:
            recovery_config: 恢复配置字典
            
        Returns:
            配置是否有效
        """
        required_keys = {"policy", "monitoringInterval", "maxFailures"}
        return required_keys.issubset(recovery_config.keys())

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.HOST_LEVEL_PARAMS_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成主机级参数事件的日志字符串
        
        Args:
            headers: 消息头
            message_json: 消息内容
            
        Returns:
            格式化的日志字符串
        """
        cluster_count = len(message_json.get("clusters", {}))
        recovery_count = sum(
            1 for config in message_json.get("clusters", {}).values()
            if "recoveryConfig" in config
        )
        return f"主机级参数更新 (集群数: {cluster_count}, 含恢复配置: {recovery_count})"
