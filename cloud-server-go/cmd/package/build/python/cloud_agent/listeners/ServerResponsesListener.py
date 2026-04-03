#!/usr/bin/env python3
"""
高级服务响应监听器 - 用于分布式系统中客户端与服务器间的异步通信
负责处理服务器响应消息的路由、回调管理和状态转换
提供完整的请求-响应生命周期管理机制
"""

import logging
from typing import Callable, Dict, Any, Optional, Tuple
from threading import RLock

# 导入必要的模块
from .stomp_adapter import StompClient
from .events import EventListener
from .utils import BlockingDictionary
from .constants import (
    CORRELATION_ID_KEY,
    SERVER_RESPONSES_TOPIC,
    RESPONSE_STATUS_KEY,
    RESPONSE_SUCCESS_STATUS
)

# 获取日志记录器
logger = logging.getLogger(__name__)


class ResponseHandler:
    """
    响应处理器 - 封装响应处理和回调机制
    
    属性:
        on_success (Optional[Callable]): 响应成功时的回调函数
        on_error (Optional[Callable]): 响应错误时的回调函数
        logging_handler (Optional[Callable]): 自定义日志处理函数
    """
    
    __slots__ = ("on_success", "on_error", "logging_handler")
    
    def __init__(
        self,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        logging_handler: Optional[Callable] = None
    ):
        """
        初始化响应处理器
        
        Args:
            on_success: 成功回调函数(header, message)
            on_error: 错误回调函数(header, message)
            logging_handler: 日志处理函数(header, message)
        """
        self.on_success = on_success
        self.on_error = on_error
        self.logging_handler = logging_handler


class ServerResponsesListener(EventListener):
    """
    服务器响应监听器 - 处理所有从服务器返回的响应消息
    
    核心功能:
        1. 通过关联ID(correlation_id)匹配请求和响应
        2. 支持多路回调(成功/错误/通用)
        3. 消息日志的自定义格式化
        4. 线程安全的数据处理
        5. 可重置的响应状态跟踪
    """
    
    def __init__(self, initializer_module: Any):
        """
        初始化响应监听器
        
        Args:
            initializer_module: 初始化模块提供上下文
        """
        super().__init__(initializer_module)
        self.lock = RLock()  # 线程安全的锁
        self.reset_responses()  # 初始化响应数据结构

    def on_event(self, headers: Dict[str, Any], message: Dict[str, Any]):
        """
        处理来自服务器的响应事件
        
        Args:
            headers: 消息头部字典
            message: 消息内容字典
        """
        correlation_id = headers.get(CORRELATION_ID_KEY)
        
        if not correlation_id:
            logger.warning(
                "收到来自服务器的无关联ID消息, 忽略\n头信息: %s\n消息体: %s",
                headers, message
            )
            return
        
        try:
            correlation_id = int(correlation_id)
        except ValueError:
            logger.error(
                "无效的关联ID格式: %s (应为整型值), 忽略消息",
                correlation_id
            )
            return
        
        with self.lock:
            # 存储原始响应
            self.responses.put(correlation_id, (headers, message))
            
            # 获取关联的处理程序(如果存在)
            handler = self.handlers.get(correlation_id)
            
            # 执行通用回调(无论成功/失败)
            self._execute_generic_handler(correlation_id, headers, message)
            
            # 根据响应状态执行不同回调
            response_status = message.get(RESPONSE_STATUS_KEY)
            if response_status == RESPONSE_SUCCESS_STATUS:
                self._execute_success_handler(correlation_id, headers, message, handler)
            else:
                self._execute_error_handler(correlation_id, headers, message, handler)
            
            # 清理已完成处理的关联资源
            self._cleanup_handler(correlation_id)
            
            logger.info(
                "处理服务器响应 [关联ID: %d] 状态: %s",
                correlation_id,
                "成功" if response_status == RESPONSE_SUCCESS_STATUS else "失败"
            )

    def _execute_generic_handler(
        self,
        correlation_id: int,
        headers: Dict[str, Any],
        message: Dict[str, Any]
    ) -> None:
        """执行通用消息处理回调"""
        if correlation_id in self.generic_handlers:
            try:
                self.generic_handlers[correlation_id](headers, message)
            except Exception as e:
                logger.error(
                    "通用回调处理异常 (关联ID: %d): %s",
                    correlation_id, str(e), exc_info=True
                )

    def _execute_success_handler(
        self,
        correlation_id: int,
        headers: Dict[str, Any],
        message: Dict[str, Any],
        handler: Optional[ResponseHandler]
    ) -> None:
        """执行成功状态处理回调"""
        # 特定于correlation_id的处理程序
        if handler and handler.on_success:
            try:
                handler.on_success(headers, message)
            except Exception as e:
                logger.error(
                    "成功回调处理异常 (关联ID: %d): %s",
                    correlation_id, str(e), exc_info=True
                )
        
        # 通用成功处理程序
        if correlation_id in self.success_handlers:
            try:
                self.success_handlers[correlation_id](headers, message)
            except Exception as e:
                logger.error(
                    "独立成功回调处理异常 (关联ID: %d): %s",
                    correlation_id, str(e), exc_info=True
                )

    def _execute_error_handler(
        self,
        correlation_id: int,
        headers: Dict[str, Any],
        message: Dict[str, Any],
        handler: Optional[ResponseHandler]
    ) -> None:
        """执行错误状态处理回调"""
        # 从消息中提取错误信息
        error_details = message.get("statusDetail") or "无详细错误信息"
        logger.error("服务器返回错误响应 (关联ID: %d): %s", correlation_id, error_details)
        
        # 特定于correlation_id的处理程序
        if handler and handler.on_error:
            try:
                handler.on_error(headers, message)
            except Exception as e:
                logger.error(
                    "错误回调处理异常 (关联ID: %d): %s",
                    correlation_id, str(e), exc_info=True
                )
        
        # 通用错误处理程序
        if correlation_id in self.error_handlers:
            try:
                self.error_handlers[correlation_id](headers, message)
            except Exception as e:
                logger.error(
                    "独立错误回调处理异常 (关联ID: %d): %s",
                    correlation_id, str(e), exc_info=True
                )

    def _cleanup_handler(self, correlation_id: int) -> None:
        """清理已完成处理的关联资源"""
        # 清理特定处理程序
        if correlation_id in self.handlers:
            del self.handlers[correlation_id]
        
        # 清理独立处理程序
        for handler_type in (
            self.generic_handlers,
            self.success_handlers,
            self.error_handlers
        ):
            if correlation_id in handler_type:
                del handler_type[correlation_id]
        
        # 清理日志处理器
        if correlation_id in self.logging_handlers:
            del self.logging_handlers[correlation_id]

    def get_handled_path(self) -> str:
        """获取监听器处理的主题路径"""
        return SERVER_RESPONSES_TOPIC

    def get_log_message(self, headers: Dict[str, Any], message_json: Dict[str, Any]) -> str:
        """
        生成响应消息的日志字符串
        
        Args:
            headers: 消息头
            message_json: 消息内容
            
        Returns:
            格式化的日志字符串
        """
        correlation_id = headers.get(CORRELATION_ID_KEY)
        if not correlation_id:
            return f"无关联ID消息: {message_json}"
        
        try:
            correlation_id = int(correlation_id)
        except ValueError:
            return f"无效关联ID消息: {correlation_id} | {message_json}"
        
        # 应用自定义日志格式化（如果存在）
        if correlation_id in self.logging_handlers:
            try:
                log_text = self.logging_handlers[correlation_id](headers, message_json)
                if log_text.startswith(" :"):
                    log_text = log_text[2:]
                return log_text
            except Exception as e:
                logger.error(
                    "日志处理器执行错误 (关联ID: %d): %s",
                    correlation_id, str(e), exc_info=True
                )
                del self.logging_handlers[correlation_id]
        
        # 默认日志格式
        return f"响应消息 (关联ID={correlation_id}): {message_json}"

    def reset_responses(self) -> None:
        """
        重置响应状态
        在关联ID重置（如重新注册）时调用
        """
        with self.lock:
            # 存储原始响应的线程安全字典
            self.responses = BlockingDictionary()
            
            # 三种类型的独立回调处理程序
            self.generic_handlers: Dict[int, Callable] = {}
            self.success_handlers: Dict[int, Callable] = {}
            self.error_handlers: Dict[int, Callable] = {}
            
            # 组合响应处理器
            self.handlers: Dict[int, ResponseHandler] = {}
            
            # 日志格式化处理器
            self.logging_handlers: Dict[int, Callable] = {}
        
        logger.info("响应状态已重置, 准备处理新请求流")

    def register_handler(
        self,
        correlation_id: int,
        handler: Optional[ResponseHandler] = None,
        **kwargs
    ) -> None:
        """
        注册响应处理器
        
        Args:
            correlation_id: 关联ID
            handler: 响应处理器对象
            
        关键词参数(用于便捷注册):
            on_success: 成功回调函数
            on_error: 错误回调函数
            on_any: 通用回调函数
            logging_handler: 日志处理函数
        """
        with self.lock:
            # 创建新的处理器或合并参数
            if not handler:
                handler = ResponseHandler()
            
            # 更新处理器设置
            if "on_success" in kwargs:
                handler.on_success = kwargs["on_success"]
            if "on_error" in kwargs:
                handler.on_error = kwargs["on_error"]
            if "logging_handler" in kwargs:
                handler.logging_handler = kwargs["logging_handler"]
            
            self.handlers[correlation_id] = handler
            
            # 注册独立处理程序（如果存在）
            if "on_any" in kwargs:
                self.generic_handlers[correlation_id] = kwargs["on_any"]
            if "on_success_ind" in kwargs:
                self.success_handlers[correlation_id] = kwargs["on_success_ind"]
            if "on_error_ind" in kwargs:
                self.error_handlers[correlation_id] = kwargs["on_error_ind"]

    def wait_for_response(
        self,
        correlation_id: int,
        timeout: float = 30.0
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        阻塞等待特定关联ID的响应
        
        Args:
            correlation_id: 要等待的关联ID
            timeout: 超时时间(秒)
            
        Returns:
            (headers, message) 元组，超时则为(None, None)
        """
        try:
            return self.responses.get(correlation_id, timeout=timeout)
        except TimeoutError:
            logger.warning(
                "等待关联ID %d 的响应超时 (等待时间 %.1f秒)",
                correlation_id, timeout
            )
            return None, None
        except Exception as e:
            logger.error(
                "等待响应时发生错误 (关联ID %d): %s",
                correlation_id, str(e), exc_info=True
            )
            return None, None

    def register_logging_handler(
        self,
        correlation_id: int,
        log_formatter: Callable[[Dict, Dict], str]
    ) -> None:
        """
        注册自定义日志格式化函数
        
        Args:
            correlation_id: 关联ID
            log_formatter: 自定义格式化函数(接受headers和message, 返回字符串)
        """
        with self.lock:
            self.logging_handlers[correlation_id] = log_formatter
