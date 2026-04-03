#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级警报定义事件监听器 - 用于分布式系统中警报定义的动态管理
提供警报配置的实时同步、缓存优化和调度更新机制
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

# 导入必要的模块
from listeners import EventListener
from cloud_agent import Constants
from alerting import AlertDefinitionsCache, AlertSchedulerHandler

# 获取日志记录器
logger = logging.getLogger(__name__)


class AlertEventType(Enum):
    """警报事件类型枚举"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SYNC = "SYNC"


class AlertDefinitionsEventListener(EventListener):
    """
    警报定义事件监听器 - 负责处理警报定义的创建、更新和删除
    
    核心功能：
        1. 监听警报定义变更事件
        2. 维护警报定义的本地缓存
        3. 支持全量同步(CREATE)与增量变更(UPDATE/DELETE)
        4. 触发警报调度器更新
        5. 自动处理日志中的敏感信息
    """
    
    # 需要脱敏的警报定义字段
    _REDACT_FIELDS = {"source", "check_content", "description", "command", "script_content"}
    
    def __init__(self, initializer_module: Any):
        """
        初始化警报定义监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.alert_definitions_cache: AlertDefinitionsCache = initializer_module.alert_definitions_cache
        self.alert_scheduler_handler: AlertSchedulerHandler = initializer_module.alert_scheduler_handler
        logger.info("警报定义事件监听器已初始化")
        
        # 事件类型处理器映射
        self.event_handlers = {
            AlertEventType.CREATE.value: self.handle_create,
            AlertEventType.UPDATE.value: self.handle_update,
            AlertEventType.DELETE.value: self.handle_delete,
            AlertEventType.SYNC.value: self.handle_sync
        }

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理警报定义变更事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        # 忽略空消息
        if not message or message == {}:
            logger.debug("收到空警报事件, 视为心跳信号")
            return
            
        try:
            event_type = message.get("eventType")
            logger.info("处理警报定义事件: 类型=%s", event_type)
            
            # 验证事件类型有效性
            handler = self.event_handlers.get(event_type)
            if not handler:
                logger.error("未知事件类型 '%s'", event_type)
                return
            
            # 调用事件处理器
            handler(message)
            
            # 通知调度器更新
            self.alert_scheduler_handler.update_definitions(event_type)
            logger.info("警报调度器已更新")
                
        except Exception as e:
            logger.error(
                "处理警报定义事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )

    def handle_create(self, message: Dict[str, Any]) -> None:
        """处理全量更新/创建事件"""
        self.alert_definitions_cache.rewrite_cache(
            message["clusters"], 
            message.get("hash", "unknown")
        )
        logger.info("全量更新警报定义缓存, 集群数: %d", len(message.get("clusters", {})))

    def handle_update(self, message: Dict[str, Any]) -> None:
        """处理增量更新事件"""
        if "clusters" not in message:
            logger.warning("增量更新事件缺少集群数据")
            return
            
        self.alert_definitions_cache.cache_update(
            message["clusters"], 
            message.get("hash", "unknown")
        )
        logger.info("增量更新警报定义缓存, 影响集群: %d", len(message["clusters"]))

    def handle_delete(self, message: Dict[str, Any]) -> None:
        """处理删除事件"""
        if "clusters" not in message:
            logger.warning("删除事件缺少集群数据")
            return
            
        self.alert_definitions_cache.cache_delete(
            message["clusters"], 
            message.get("hash", "unknown")
        )
        logger.info("删除警报定义, 影响集群: %d", len(message["clusters"]))

    def handle_sync(self, message: Dict[str, Any]) -> None:
        """处理配置同步事件"""
        logger.info("接收配置同步请求, 启动完整同步流程")
        self.initializer_module.config_manager.request_full_sync()

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.ALERTS_DEFINITIONS_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成警报定义事件的精简日志字符串
        
        Args:
            headers: 消息头
            message_json: 消息内容
            
        Returns:
            格式化的日志字符串
        """
        try:
            # 提取基本信息
            event_type = message_json.get("eventType", "UNKNOWN")
            cluster_count = len(message_json.get("clusters", {}))
            
            # 构造简短描述
            log_text = f"警报定义事件 ({event_type}, 影响集群数: {cluster_count})"
            
            # 针对不同事件类型添加额外信息
            if event_type in [AlertEventType.UPDATE.value, AlertEventType.DELETE.value]:
                definition_ids = self._extract_changed_ids(message_json["clusters"])
                if definition_ids:
                    log_text += f", 变更ID数: {len(definition_ids)}"
                    if len(definition_ids) <= 10:
                        log_text += f", ID示例: {', '.join(definition_ids[:3])}..."
            
            return log_text
        
        except Exception as e:
            logger.error("构建警报日志消息失败: %s", e)
            return super().get_log_message(headers, message_json)

    def _extract_changed_ids(self, clusters: Dict[str, Dict]) -> list:
        """从集群数据中提取变更的警报定义ID"""
        changed_ids = []
        for cluster_data in clusters.values():
            if definitions := cluster_data.get("alertDefinitions", []):
                for definition in definitions:
                    if "id" in definition:
                        changed_ids.append(definition["id"])
        return changed_ids
