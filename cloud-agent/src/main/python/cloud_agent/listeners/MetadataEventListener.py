#!/usr/bin/env python3
"""
高级元数据事件监听器 - 用于分布式系统中元数据的实时同步与缓存管理
提供元数据集群的增量更新、版本管理和缓存一致性保证
"""

import logging
import enum
from typing import Dict, Any, Optional

# 导入必要的模块
from cloud_agent.listeners import EventListener
from cloud_agent import Constants
from cloud_agent.caching import MetadataCache

# 获取日志记录器
logger = logging.getLogger(__name__)


class MetadataEventType(enum.Enum):
    """元数据操作类型枚举"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    INVALIDATE = "INVALIDATE"
    REFRESH = "REFRESH"


class MetadataEventListener(EventListener):
    """
    元数据事件监听器 - 负责处理来自主控服务器的元数据变更通知
    
    核心功能:
        1. 监听元数据变更事件
        2. 实时更新本地元数据缓存
        3. 处理全部/增量数据更新
        4. 支持多种变更类型（创建、更新、删除）
        5. 提供缓存一致性保证
    """
    
    def __init__(self, initializer_module: Any):
        """
        初始化元数据监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.metadata_cache: MetadataCache = initializer_module.metadata_cache
        logger.info("元数据监听器已初始化, 缓存版本: %s", self.metadata_cache.current_hash)

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理来自服务器的元数据变更事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        # 处理空消息和心跳事件
        if not message or message == {}:
            logger.debug("收到元数据心跳信号, 缓存状态正常")
            return
        
        try:
            # 解析事件类型和元数据集群信息
            event_type_name = message.get("eventType", "").upper()
            clusters = message.get("clusters", [])
            new_hash = message.get("hash", "")
            
            # 将事件类型字符串转换为枚举
            event_type = self._parse_event_type(event_type_name, headers, message)
            
            # 根据事件类型处理元数据
            if event_type == MetadataEventType.CREATE:
                self._handle_create_event(new_hash, clusters)
            elif event_type == MetadataEventType.UPDATE:
                self._handle_update_event(new_hash, clusters)
            elif event_type == MetadataEventType.DELETE:
                self._handle_delete_event(new_hash, clusters)
            elif event_type == MetadataEventType.INVALIDATE:
                self._handle_invalidate_event()
            elif event_type == MetadataEventType.REFRESH:
                self._handle_refresh_event()
            else:
                logger.warning("收到未知类型事件: %s", event_type_name)
            
            logger.info(
                "处理元数据 %s 事件完成, 新缓存版本: %s",
                event_type_name,
                self.metadata_cache.current_hash
            )
        
        except Exception as e:
            logger.error(
                "处理元数据事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )
            # TODO: 添加重试或错误上报机制

    def _parse_event_type(
        self, 
        event_name: str, 
        headers: Dict[str, Any],
        message: Dict[str, Any]
    ) -> Optional[MetadataEventType]:
        """解析事件类型字符串为枚举值"""
        try:
            return MetadataEventType(event_name)
        except ValueError:
            logger.error(
                "非法元数据事件类型: %s\n消息ID: %s\n完整消息: %s",
                event_name,
                headers.get(Constants.CORRELATION_ID_KEY, "N/A"),
                message
            )
            return None

    def _handle_create_event(self, new_hash: str, clusters: list) -> None:
        """处理元数据创建事件"""
        if not self.metadata_cache.is_empty():
            logger.warning(
                "收到CREATE事件但缓存不为空, 将完全覆盖缓存 "
                "(当前版本: %s, 新版本: %s)",
                self.metadata_cache.current_hash, new_hash
            )
        
        success = self.metadata_cache.rewrite_cache(clusters, new_hash)
        if success:
            logger.info(
                "成功初始化元数据缓存, 集群数: %d, 版本: %s",
                len(clusters), new_hash
            )
        else:
            logger.error("元数据缓存初始化失败")

    def _handle_update_event(self, new_hash: str, clusters: list) -> None:
        """处理元数据更新事件"""
        if self.metadata_cache.is_empty():
            logger.warning(
                "收到UPDATE事件但缓存为空, 将转换为CREATE事件 "
                "(新版本: %s)",
                new_hash
            )
            self.metadata_cache.rewrite_cache(clusters, new_hash)
            return
        
        success = self.metadata_cache.cache_update(clusters, new_hash)
        if success:
            logger.info(
                "成功更新元数据缓存, 更新集群数: %d, 新版本: %s",
                len(clusters), new_hash
            )
        else:
            logger.error("元数据缓存更新失败")
            # 更新失败时可能需要请求完整数据
            self._request_full_metadata()

    def _handle_delete_event(self, new_hash: str, clusters: list) -> None:
        """处理元数据删除事件"""
        if self.metadata_cache.is_empty():
            logger.warning(
                "收到DELETE事件但缓存为空 (新版本: %s)",
                new_hash
            )
            return
        
        # 提取待删除的集群ID
        cluster_ids = [cluster.get("id") for cluster in clusters]
        
        success = self.metadata_cache.cache_delete(cluster_ids, new_hash)
        if success:
            logger.info(
                "成功删除 %d 个元数据集群, 新版本: %s",
                len(cluster_ids), new_hash
            )
        else:
            logger.error(
                "部分集群删除失败, 请求完整元数据 (新版本: %s)",
                new_hash
            )
            # 删除失败时请求完整数据
            self._request_full_metadata()

    def _handle_invalidate_event(self) -> None:
        """处理元数据失效事件"""
        logger.warning("收到元数据失效通知, 清除所有缓存")
        self.metadata_cache.clear_cache()
        self._request_full_metadata()

    def _handle_refresh_event(self) -> None:
        """处理元数据刷新事件"""
        logger.info("收到强制刷新通知, 请求完整元数据")
        self._request_full_metadata()

    def _request_full_metadata(self) -> None:
        """向服务器请求完整元数据"""
        # 实际实现中应调用客户端方法请求完整数据
        logger.info("向服务器请求完整元数据...")
        # 示例: self.initializer_module.request_full_metadata()
        # 这将触发新的CREATE事件

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.METADATA_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成元数据事件的日志字符串
        
        Args:
            headers: 消息头
            message_json: 消息内容
            
        Returns:
            格式化的日志字符串
        """
        event_type = message_json.get("eventType", "UNKNOWN")
        cluster_count = len(message_json.get("clusters", []))
        return f"元数据 {event_type} 事件 (集群数: {cluster_count})"
