#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级拓扑事件监听器 - 用于分布式系统中集群拓扑的动态管理
提供集群拓扑的实时同步、缓存优化和拓扑感知服务
"""

import logging
import copy
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum, auto

# 导入必要的模块
from listeners import EventListener
from cloud_agent import Constants
from topology import TopologyCache

# 获取日志记录器
logger = logging.getLogger(__name__)


class TopologyEventType(Enum):
    """拓扑事件类型枚举"""
    CREATE = auto()
    UPDATE = auto()
    DELETE = auto()
    SYNC = auto()


class TopologyEventListener(EventListener):
    """
    拓扑事件监听器 - 负责处理集群拓扑结构的创建、更新和删除
    
    核心功能：
        1. 监听集群拓扑变更事件
        2. 维护拓扑结构的本地缓存
        3. 支持全量同步(CREATE)与增量变更(UPDATE/DELETE)
        4. 提供拓扑结构日志简化
        5. 支持拓扑感知服务
    """
    
    # 需要脱敏的拓扑字段
    _REDACT_FIELDS = {"componentLevelParams", "commandParams", "credentials", "secrets", "sslCert"}
    
    # 组件类型分组
    _COMPONENT_GROUPS = {
        "storage": ["DATANODE", "NAMENODE", "JOURNALNODE"],
        "compute": ["NODEMANAGER", "RESOURCEMANAGER", "REGIONSERVER"],
        "db": ["HIVESERVER", "HBASEMASTER", "ZOOKEEPER_SERVER"],
        "gateway": ["KAFKA_BROKER", "NIFI_NODE", "FLINK_HISTORYSERVER"]
    }
    
    def __init__(self, initializer_module: Any):
        """
        初始化拓扑监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.topology_cache: TopologyCache = initializer_module.topology_cache
        self._event_handlers = {
            "CREATE": self._handle_create,
            "UPDATE": self._handle_update,
            "DELETE": self._handle_delete,
            "SYNC": self._handle_sync
        }
        logger.info("拓扑事件监听器已初始化")

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理拓扑变更事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        # 忽略空消息
        if not message:
            logger.debug("收到空拓扑事件, 视为心跳信号")
            return
            
        try:
            event_type = message.get("eventType")
            logger.info("处理拓扑事件: 类型=%s", event_type)
            
            # 验证事件类型有效性
            handler = self._event_handlers.get(event_type)
            if not handler:
                logger.error("未知事件类型 '%s'", event_type)
                return
            
            # 调用事件处理器
            handler(message)
            
            logger.info("拓扑处理完成: 类型=%s", event_type)
        except Exception as e:
            logger.error(
                "处理拓扑事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )

    def _handle_create(self, message: Dict[str, Any]) -> None:
        """处理全量更新/创建事件"""
        self.topology_cache.rewrite_cache(
            message["clusters"], 
            message.get("hash", "N/A")
        )
        logger.info("全量更新拓扑缓存, 集群数: %d", len(message.get("clusters", {})))

    def _handle_update(self, message: Dict[str, Any]) -> None:
        """处理增量更新事件"""
        if "clusters" not in message:
            logger.warning("增量更新事件缺少集群数据")
            return
            
        self.topology_cache.cache_update(
            message["clusters"], 
            message.get("hash", "N/A")
        )
        logger.info("增量更新拓扑缓存, 影响集群: %d", len(message["clusters"]))

    def _handle_delete(self, message: Dict[str, Any]) -> None:
        """处理删除事件"""
        if "clusters" not in message:
            logger.warning("删除事件缺少集群数据")
            return
            
        self.topology_cache.cache_delete(
            message["clusters"], 
            message.get("hash", "N/A")
        )
        logger.info("删除拓扑数据, 影响集群: %d", len(message["clusters"]))

    def _handle_sync(self, message: Dict[str, Any]) -> None:
        """处理配置同步事件"""
        logger.info("接收拓扑同步请求, 启动完整同步流程")
        self.initializer_module.topology_manager.request_full_sync()

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.TOPOLOGIES_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成拓扑事件的精简日志字符串
        
        Args:
            headers: 消息头
            message_json: 消息内容
            
        Returns:
            格式化的日志字符串
        """
        try:
            event_type = message_json.get("eventType", "UNKNOWN")
            clusters = message_json.get("clusters", {})
            
            # 构造基本信息
            log_msg = f"拓扑事件 ({event_type}, 集群数: {len(clusters)})"
            
            # 添加拓扑摘要信息
            topology_summary = self._generate_topology_summary(clusters)
            if topology_summary:
                log_msg += f", 摘要: {topology_summary}"
                
            return log_msg
        
        except Exception as e:
            logger.error("构建拓扑日志消息失败: %s", e)
            return super().get_log_message(headers, message_json)

    def _generate_topology_summary(self, clusters: Dict[str, Dict]) -> str:
        """
        生成拓扑摘要信息
        
        Args:
            clusters: 集群拓扑数据
            
        Returns:
            拓扑摘要字符串
        """
        summary = []
        
        for cluster_id, cluster_data in clusters.items():
            components = cluster_data.get("components", [])
            
            # 组件统计
            component_counts = self._count_component_types(components)
            component_summary = ", ".join(f"{k}:{v}" for k, v in component_counts.items())
            
            # 主机分布
            host_info = self._extract_host_info(components)
            
            cluster_summary = f"{cluster_id}[组件:{component_summary}, 主机:{host_info}]"
            if len(summary) < 3:  # 只显示前3个集群的详细信息
                summary.append(cluster_summary)
        
        if len(clusters) > 3:
            summary.append(f"...其他{len(clusters)-3}个集群")
            
        return "; ".join(summary)

    def _count_component_types(self, components: List[Dict]) -> Dict[str, int]:
        """
        统计各类组件数量
        
        Args:
            components: 组件列表
            
        Returns:
            组件类型统计字典
        """
        type_mapping = {}
        for comp_type, group in self._COMPONENT_GROUPS.items():
            for name in group:
                type_mapping[name] = comp_type
                
        counts = {group: 0 for group in self._COMPONENT_GROUPS}
        counts["other"] = 0
        
        for comp in components:
            comp_name = comp.get("name", "UNKNOWN")
            comp_type = type_mapping.get(comp_name, "other")
            counts[comp_type] += 1
            
        # 移除统计为0的分组
        return {k: v for k, v in counts.items() if v > 0}

    def _extract_host_info(self, components: List[Dict]) -> str:
        """
        提取主机分布信息
        
        Args:
            components: 组件列表
            
        Returns:
            主机分布信息字符串
        """
        hosts = {}
        for comp in components:
            host_components = comp.get("hostLevelParams", {}).get("hosts", [])
            for host in host_components:
                hostname = host.get("name")
                if not hostname:
                    continue
                    
                if hostname not in hosts:
                    hosts[hostname] = {
                        "roles": set(),
                        "status": "未知"
                    }
                
                hosts[hostname]["roles"].add(comp.get("name", "unknown"))
                hosts[hostname]["status"] = host.get("status", "未知")
        
        # 返回简要主机信息
        host_count = len(hosts)
        active_hosts = sum(1 for h in hosts.values() if h["status"] == "ACTIVE")
        return f"共{host_count}台({active_hosts}活动)"
