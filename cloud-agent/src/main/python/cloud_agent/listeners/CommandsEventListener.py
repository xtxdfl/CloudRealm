#!/usr/bin/env python3
"""
高级命令事件监听器 - 用于分布式系统中命令的动态分发与执行管理
提供集群操作指令的实时处理、命令队列管理和任务取消机制
"""

import logging
import copy
from typing import Dict, List, Any, Optional, Tuple

# 导入必要的模块
from cloud_agent.listeners import EventListener
from cloud_agent import Constants
from cloud_agent.queue import ActionQueue

# 获取日志记录器
logger = logging.getLogger(__name__)


class CommandsEventListener(EventListener):
    """
    命令事件监听器 - 负责处理集群操作命令的分发和执行
    
    核心功能：
        1. 监听命令分发事件
        2. 提取命令和取消指令
        3. 将命令添加到操作队列
        4. 取消指定的任务
        5. 自动处理敏感数据的日志记录
    """
    
    # 命令字段简写映射
    _ALIASES = {
        "repo": "repositoryFile",
        "params": "commandParams",
        "hosts": "clusterHostInfo",
        "versions": "componentVersionMap"
    }
    
    # 需要截断的敏感字段
    _REDACT_FIELDS = {
        "repositoryFile", "commandParams", 
        "clusterHostInfo", "componentVersionMap",
        "credentials", "secrets", "sshKeys"
    }
    
    # 最大截断长度
    _TRUNCATE_LENGTH = 50
    
    def __init__(self, initializer_module: Any):
        """
        初始化命令监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.action_queue: ActionQueue = initializer_module.action_queue
        logger.info("命令事件监听器已初始化")

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理命令事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        # 忽略空消息或无效格式
        if not message.get("clusters"):
            logger.debug("收到空命令事件, 忽略")
            return
            
        try:
            # 添加时间戳上下文
            config_timestamp = message.get("requiredConfigTimestamp")
            
            # 处理命令事件
            commands, cancel_commands = self._process_message(
                message["clusters"], 
                config_timestamp
            )
            
            # 处理取消命令
            cancel_count = len(cancel_commands)
            if cancel_count > 0:
                with self.action_queue.lock:
                    self.action_queue.cancel(cancel_commands)
                logger.info("已取消 %d 个命令", cancel_count)
            
            # 添加新命令到队列
            command_count = len(commands)
            if command_count > 0:
                with self.action_queue.lock:
                    self.action_queue.put(commands)
                logger.info("已添加 %d 个命令到操作队列", command_count)
                
        except Exception as e:
            logger.error(
                "处理命令事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )

    def _process_message(
        self, 
        clusters: Dict[str, Dict], 
        config_timestamp: Optional[int] = None
    ) -> Tuple[List[Dict], List[str]]:
        """
        处理消息中的集群命令数据
        
        Args:
            clusters: 集群命令字典
            config_timestamp: 所需配置时间戳
            
        Returns:
            (命令列表, 取消命令ID列表)
        """
        commands = []
        cancel_commands = []
        
        # 遍历所有集群
        for cluster_id, cluster_data in clusters.items():
            # 添加取消命令
            if cancel_cmds := cluster_data.get("cancelCommands", []):
                cancel_commands.extend(cancel_cmds)
            
            # 添加新命令
            if new_commands := cluster_data.get("commands", []):
                # 添加元数据到命令
                for command in new_commands:
                    command["cluster_id"] = cluster_id
                    if config_timestamp:
                        command["requiredConfigTimestamp"] = config_timestamp
                commands.extend(new_commands)
        
        return commands, cancel_commands

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.COMMANDS_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成命令事件的精简日志字符串
        
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
            
            # 精简日志内容
            self._simplify_commands(clusters)
            
            # 返回父类日志方法
            return super().get_log_message(headers, log_message)
        
        except Exception as e:
            logger.error("构建命令日志消息失败: %s", e)
            return super().get_log_message(headers, message_json)

    def _simplify_commands(self, clusters: Dict[str, Dict]) -> None:
        """
        简化集群命令数据以便日志展示
        
        Args:
            clusters: 集群命令字典
        """
        for cluster_data in clusters.values():
            # 处理commands列表
            if commands := cluster_data.get("commands"):
                for command in commands:
                    self._truncate_command_fields(command)
            
            # 简化cancelCommands列表
            if cancel_cmds := cluster_data.get("cancelCommands"):
                cluster_data["cancelCommands"] = [
                    self._truncate_id(cmd_id) for cmd_id in cancel_cmds
                ]

    def _truncate_command_fields(self, command: Dict[str, Any]) -> None:
        """
        截断命令字段以避免日志过大和敏感信息泄露
        
        Args:
            command: 命令字典
        """
        # 标准化别名
        self._convert_aliases(command)
        
        # 截断大型字段
        for field in self._REDACT_FIELDS:
            if field in command and isinstance(command[field], str) and len(command[field]) > self._TRUNCATE_LENGTH:
                command[field] = command[field][:self._TRUNCATE_LENGTH] + "..." 
            elif field in command and isinstance(command[field], dict):
                command[field] = f"dict<{len(command[field])} items>"

    def _convert_aliases(self, command: Dict[str, Any]) -> None:
        """
        转换命令别名为正式字段名
        
        Args:
            command: 命令字典
        """
        # 处理别名
        for alias, official in self._ALIASES.items():
            if alias in command and official not in command:
                command[official] = command.pop(alias)
        
        # 移除所有别名
        for alias in self._ALIASES:
            command.pop(alias, None)

    def _truncate_id(self, cmd_id: str) -> str:
        """
        截断命令ID用于日志展示
        
        Args:
            cmd_id: 命令ID
            
        Returns:
            截断后的ID
        """
        return f"{cmd_id[:8]}...{cmd_id[-4:]}" if len(cmd_id) > 16 else cmd_id
