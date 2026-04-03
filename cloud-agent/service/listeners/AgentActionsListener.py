#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级代理动作监听器 - 用于分布式系统中的代理管理
提供代理操作指令的接收、验证和执行机制
"""

import logging
from typing import Dict, Any

from listeners import EventListener
from Utils import Utils
from cloud_agent import Constants

logger = logging.getLogger(__name__)


class AgentActionsListener(EventListener):
    """
    代理动作监听器 - 负责处理服务器发来的代理管理指令
    
    核心功能:
        1. 监听代理动作指令
        2. 验证指令完整性和权限
        3. 执行多种代理操作
        4. 提供操作回执
        5. 实现操作安全机制
    """
    
    # 预定义动作类型
    ACTION_NAME = "actionName"
    ACTION_PARAMS = "actionParams"
    ACTION_ID = "actionId"
    
    RESTART_AGENT_ACTION = "RESTART_AGENT"
    CLEAR_CACHE_ACTION = "CLEAR_CACHE"
    RECONFIG_ACTION = "RECONFIG"
    UPDATE_ACTION = "UPDATE_AGENT"
    SERVICE_COMMAND = "SERVICE_COMMAND"
    
    def __init__(self, initializer_module: Any):
        """
        初始化动作监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.stop_event = initializer_module.stop_event
        self.response_producer = initializer_module.response_producer
        
        # 动作处理器映射
        self.action_handlers = {
            self.RESTART_AGENT_ACTION: self.handle_restart_agent,
            self.CLEAR_CACHE_ACTION: self.handle_clear_cache,
            self.RECONFIG_ACTION: self.handle_reconfig,
            self.UPDATE_ACTION: self.handle_update_agent,
            self.SERVICE_COMMAND: self.handle_service_command,
        }
        
        logger.info("代理动作监听器已初始化")
        
    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理代理动作事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        action_name = message.get(self.ACTION_NAME)
        if not action_name:
            logger.error("无效代理动作: 缺少动作名称")
            return
            
        # 获取操作ID用于追踪
        action_id = message.get(self.ACTION_ID, "unknown")
        
        # 验证操作签名
        if not self.validate_action_signature(message):
            logger.warning("动作 '%s'(ID:%s)验证失败, 拒绝执行", action_name, action_id)
            self.send_action_response("REJECTED", action_id, "
