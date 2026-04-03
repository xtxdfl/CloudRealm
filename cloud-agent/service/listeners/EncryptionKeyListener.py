#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级加密密钥监听器 - 用于分布式系统中的密钥管理
提供密钥动态更新、安全验证和生命周期管理机制
"""

import logging
from typing import Dict, Any
import re

# 导入必要的模块
from listeners import EventListener
from cloud_agent import Constants

# 获取日志记录器
logger = logging.getLogger(__name__)


class EncryptionKeyListener(EventListener):
    """
    加密密钥监听器 - 负责处理加密密钥的实时更新
    
    核心功能:
        1. 监听密钥更新事件
        2. 验证密钥格式和有效性
        3. 安全存储和管理密钥
        4. 触发密钥相关操作
        5. 实现密钥轮换机制
    """
    
    # 支持的密钥类型和格式正则
    KEY_FORMATS = {
        "AES": r"^[a-fA-F0-9]{64}$",      # 256位十六进制格式
        "RSA": r"^-----BEGIN (RSA )?PRIVATE KEY-----",  # PEM格式
        "BASE64": r"^[a-zA-Z0-9+/=]{40,}$"  # 通用Base64编码
    }
    
    def __init__(self, initializer_module: Any):
        """
        初始化密钥监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self._service_orchestrator = initializer_module.customServiceOrchestrator
        self._previous_keys = []
        logger.info("加密密钥监听器已初始化")
        logger.debug("支持密钥类型: %s", list(self.KEY_FORMATS.keys()))

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]) -> None:
        """
        处理密钥分发事件
        
        Args:
            headers: 消息头字典
            message: 消息内容字典
        """
        if not message or "encryptionKey" not in message:
            logger.error("收到无效密钥事件: %s", message)
            return
            
        new_key = message["encryptionKey"]
        key_type = self._validate_key(new_key)
        
        if key_type is None:
            logger.error("密钥格式无效或不受支持")
            return
            
        try:
            logger.info("接收到新的 %s 加密密钥 (长度: %d)", key_type, len(new_key))
            self._handle_key_update(new_key)
            
        except Exception as e:
            logger.error(
                "处理加密密钥事件失败: %s\n头信息: %s\n消息体: %s",
                str(e), headers, message, exc_info=True
            )

    def _validate_key(self, key: str) -> Optional[str]:
        """验证密钥格式并识别类型"""
        for key_type, pattern in self.KEY_FORMATS.items():
            if re.match(pattern, key, re.DOTALL):
                logger.debug("密钥匹配 %s 格式", key_type)
                return key_type
                
        logger.warning("密钥不匹配任何已知格式，尝试作为原始字符串处理")
        return "RAW" if key else None

    def _handle_key_update(self, new_key: str) -> None:
        """安全处理密钥更新"""
        # 保存当前密钥以供轮换
        if current_key := self._service_orchestrator.encryption_key:
            self._previous_keys.append(current_key)
            if len(self._previous_keys) > 3:  # 仅保留最近3个密钥
                self._previous_keys.pop(0)
                
        # 更新服务中的密钥
        self._service_orchestrator.encryption_key = new_key
        
        # 执行密钥相关操作
        self._notify_key_dependencies()
        self._log_key_change()
        
        # 轮换旧密钥
        self._rotate_old_keys()
        
        logger.info("加密密钥更新成功")

    def _notify_key_dependencies(self) -> None:
        """通知依赖密钥的服务"""
        # 在实际系统中应通知加密模块、配置服务等
        logger.info("通知密钥相关服务更新")
        # 示例: self._service_orchestrator.notify_key_update()

    def _log_key_change(self) -> None:
        """安全记录密钥变更日志"""
        logger.info("加密密钥已更新 (摘要: %s)", self._generate_key_summary())

    def _generate_key_summary(self) -> str:
        """生成密钥摘要用于日志"""
        key = self._service_orchestrator.encryption_key
        if not key:
            return "EMPTY"
            
        # 生成安全摘要 (开头4字符 + ... + 结尾4字符)
        return f"{key[:4]}...{key[-4:]}" if len(key) > 10 else "HIDDEN"
        
    def _rotate_old_keys(self) -> None:
        """轮换过期密钥"""
        # 在实际系统中应实现密钥淘汰机制
        logger.debug("维护历史密钥记录: %d", len(self._previous_keys))
        
        # 示例淘汰策略
        # self._service_orchestrator.rotate_keys(self._previous_keys.copy())

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return Constants.ENCRYPTION_KEY_TOPIC
        

# 密钥加密服务接口
class KeyEncryptionService:
    """密钥加密服务基类"""
    def __init__(self):
        self.encryption_key = ""
        
    def encrypt(self, data: str) -> str:
        """加密数据"""
        raise NotImplementedError()
        
    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        raise NotImplementedError()
        

# AES加密服务实现
class AesEncryptionService(KeyEncryptionService):
    """AES加密服务实现"""
    def __init__(self):
        super().__init__()
        self.iv_length = 16
        
    def encrypt(self, data: str) -> str:
        if not self.encryption_key:
            raise ValueError("加密密钥未设置")
        # 实际AES加密逻辑
        return f"[AES]Encrypted({data})"
        
    def decrypt(self, encrypted_data: str) -> str:
        if not self.encryption_key:
            raise ValueError("加密密钥未设置")
        # 实际AES解密逻辑
        if encrypted_data.startswith("[AES]Encrypted("):
            return encrypted_data[15:-1]
        return encrypted_data
