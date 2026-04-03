#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket 协议完整异常体系
基于 RFC6455 和 WebSocket 规范设计
包含 7 大类 28 种异常，覆盖协议所有错误场景
"""

__all__ = [
    # 基础异常
    "WebSocketError",
    
    # 连接异常
    "ConnectionError",
    "HandshakeError",
    "ConnectionClosed",
    
    # 协议异常
    "ProtocolViolation",
    "InvalidOpcodeError",
    "ReservedBitsError",
    "InvalidFrameOrder",
    "ControlFrameTooLarge",
    
    # 帧异常
    "FrameTooLarge",
    "FramePayloadError",
    "FrameEncodingError",
    "MaskValidationError",
    
    # 消息异常
    "MessageTooLarge",
    "MessageFragmentationError",
    "TextMessageEncodingError",
    "BinaryMessageError",
    
    # 数据异常
    "DataValidationError",
    "UTF8ValidationError",
    
    # 扩展异常
    "ExtensionNegotiationError",
    "UnsupportedExtension",
    
    # 子协议异常
    "SubprotocolError",
    "UnsupportedSubprotocol",
    
    # 操作异常
    "StreamClosed",
    "InvalidStateOperation",
    "SecurityError",
    "RateLimitExceeded",
    "TimeoutError",
    "ResourceExhausted"
]

class WebSocketError(Exception):
    """WebSocket 异常基类
    
    属性:
        error_code: 错误码 (可选)
        reason: 错误描述
    """
    ERROR_CODE = 1000
    DEFAULT_REASON = "WebSocket generic error"
    
    def __init__(self, reason=None, error_code=None):
        self.reason = reason or self.DEFAULT_REASON
        self.error_code = error_code or self.ERROR_CODE
        super().__init__(self.reason)
    
    def __str__(self):
        return f"Error {self.error_code}: {self.reason}"

#
# 连接相关异常 (1000-1015)
#
class ConnectionError(WebSocketError):
    """连接级异常基类"""
    ERROR_CODE = 1000
    DEFAULT_REASON = "Connection error"

class HandshakeError(ConnectionError):
    """握手失败异常"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Handshake failed"
    
    def __init__(self, http_status=400, http_headers=None, ws_details=None):
        """
        参数:
            http_status: HTTP 状态码 (默认400)
            http_headers: 关联的HTTP头部
            ws_details: WebSocket 特定错误详情
        """
        super().__init__()
        self.http_status = http_status
        self.http_headers = http_headers or {}
        self.ws_details = ws_details
        self.error_code = self.ERROR_CODE

class ConnectionClosed(ConnectionError):
    """连接已关闭异常"""
    ERROR_CODE = 1001
    DEFAULT_REASON = "Connection is closed"
    
    def __init__(self, close_code=1000, reason=None):
        super().__init__(reason=reason, error_code=close_code)
        self.close_code = close_code

#
# 协议相关异常 (1002-1008)
#
class ProtocolError(WebSocketError):
    """协议异常基类"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Protocol violation"

class ProtocolViolation(ProtocolError):
    """协议违规操作"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Protocol violation"

class InvalidOpcodeError(ProtocolError):
    """无效操作码异常"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Invalid frame opcode"
    
    def __init__(self, opcode):
        reason = f"Opcode {opcode:#x} is invalid or reserved"
        super().__init__(reason=reason)

class ReservedBitsError(ProtocolError):
    """保留位使用异常"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Reserved bits (RSV) are set"
    
    def __init__(self, rsv1=0, rsv2=0, rsv3=0):
        reason = f"Reserved bits set: RSV1={rsv1}, RSV2={rsv2}, RSV3={rsv3}"
        if (rsv1 or rsv2 or rsv3):
            reason += " (not zero as required)"
        super().__init__(reason=reason)

class InvalidFrameOrder(ProtocolError):
    """帧顺序错误异常"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Invalid frame sequence"
    
    def __init__(self, expectation, actual):
        reason = f"Expected {expectation} frame, received {actual}"
        super().__init__(reason=reason)

class ControlFrameTooLarge(ProtocolError):
    """控制帧过大异常"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Control frame payload too large (>125 bytes)"
    
    def __init__(self, size):
        super().__init__(reason=f"Control frame size {size} exceeds maximum (125 bytes)")

#
# 帧处理异常 (1007-1009)
#
class FrameProcessingError(WebSocketError):
    """帧处理异常基类"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Frame processing error"

class FrameTooLarge(FrameProcessingError):
    """帧过大异常"""
    ERROR_CODE = 1009
    DEFAULT_REASON = "Frame payload too large"
    
    def __init__(self, size, limit):
        reason = f"Frame size {size} exceeds limit of {limit}"
        super().__init__(reason=reason)

class FramePayloadError(FrameProcessingError):
    """帧数据错误"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Invalid frame payload"
    
    def __init__(self, issue):
        super().__init__(reason=f"Frame payload error: {issue}")

class FrameEncodingError(FrameProcessingError):
    """帧编码异常"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Frame encoding error"
    
    def __init__(self, encoding, details):
        reason = f"Invalid {encoding} encoding: {details}"
        super().__init__(reason=reason)

class MaskValidationError(FrameProcessingError):
    """掩码验证失败"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Frame mask validation failed"
    
    def __init__(self, actual, expected=None):
        if expected:
            reason = f"Mask does not match: expected {expected}, got {actual}"
        else:
            reason = f"Invalid mask: {actual}"
        super().__init__(reason=reason)

#
# 消息相关异常 (1003-1007)
#
class MessageError(WebSocketError):
    """消息处理异常基类"""
    ERROR_CODE = 1003
    DEFAULT_REASON = "Message processing error"

class MessageTooLarge(MessageError):
    """消息过大异常"""
    ERROR_CODE = 1009
    DEFAULT_REASON = "Message too large"
    
    def __init__(self, size, max_size):
        reason = f"Message size {size} exceeds maximum of {max_size}"
        super().__init__(reason=reason)

class MessageFragmentationError(MessageError):
    """消息分片错误"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Message fragmentation error"
    
    def __init__(self, issue):
        super().__init__(reason=f"Message fragmentation issue: {issue}")

class TextMessageEncodingError(MessageError):
    """文本消息编码异常"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Text message encoding error"
    
    def __init__(self, position, char=None):
        if char:
            reason = f"Invalid UTF-8 byte {char:#x} at position {position}"
        else:
            reason = f"Invalid UTF-8 data at position {position}"
        super().__init__(reason=reason)

class BinaryMessageError(MessageError):
    """二进制消息错误"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Binary message data error"
    
    def __init__(self, issue):
        super().__init__(reason=f"Binary message data invalid: {issue}")

#
# 数据验证异常
#
class DataValidationError(WebSocketError):
    """数据验证异常基类"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Data validation failed"

class UTF8ValidationError(DataValidationError):
    """UTF-8 验证失败异常"""
    ERROR_CODE = 1007
    DEFAULT_REASON = "Invalid UTF-8 data"
    
    def __init__(self, pos, byte):
        reason = f"Invalid UTF-8 byte {byte:#04x} at position {pos}"
        super().__init__(reason=reason)

#
# 扩展相关异常
#
class ExtensionError(WebSocketError):
    """扩展异常基类"""
    ERROR_CODE = 1010
    DEFAULT_REASON = "Extension related error"

class ExtensionNegotiationError(ExtensionError):
    """扩展协商失败"""
    ERROR_CODE = 1010
    DEFAULT_REASON = "Extension negotiation failed"
    
    def __init__(self, extension, details):
        reason = f"Extension {extension} error: {details}"
        super().__init__(reason=reason)

class UnsupportedExtension(ExtensionError):
    """不支持的扩展"""
    ERROR_CODE = 1010
    DEFAULT_REASON = "Unsupported extension"
    
    def __init__(self, extension):
        reason = f"Extension {extension} is not supported"
        super().__init__(reason=reason)

#
# 子协议相关异常
#
class SubprotocolError(WebSocketError):
    """子协议异常基类"""
    ERROR_CODE = 1003
    DEFAULT_REASON = "Subprotocol related error"

class UnsupportedSubprotocol(SubprotocolError):
    """不支持的子协议"""
    ERROR_CODE = 1003
    DEFAULT_REASON = "Unsupported subprotocol"
    
    def __init__(self, protocol):
        reason = f"Subprotocol {protocol} is not supported"
        super().__init__(reason=reason)

#
# 操作相关异常
#
class OperationError(WebSocketError):
    """操作异常基类"""
    ERROR_CODE = 1000
    DEFAULT_REASON = "Operation error"

class StreamClosed(OperationError):
    """流已关闭异常"""
    ERROR_CODE = 1001
    DEFAULT_REASON = "Stream is closed"
    
    def __init__(self, cause="Connection closed", code=1001):
        super().__init__(reason=cause, error_code=code)

class InvalidStateOperation(OperationError):
    """无效状态操作"""
    ERROR_CODE = 1002
    DEFAULT_REASON = "Invalid operation for current state"
    
    def __init__(self, state, operation):
        reason = f"Operation '{operation}' not allowed in state '{state}'"
        super().__init__(reason=reason)

class SecurityError(OperationError):
    """安全策略违规"""
    ERROR_CODE = 1008
    DEFAULT_REASON = "Security policy violation"
    
    def __init__(self, policy, details):
        reason = f"Security policy '{policy}' violation: {details}"
        super().__init__(reason=reason)

class RateLimitExceeded(OperationError):
    """速率限制异常"""
    ERROR_CODE = 1008
    DEFAULT_REASON = "Rate limit exceeded"
    
    def __init__(self, limit):
        reason = f"Operation rate exceeds limit of {limit}/sec"
        super().__init__(reason=reason)

class TimeoutError(OperationError):
    """操作超时异常"""
    ERROR_CODE = 1001
    DEFAULT_REASON = "Operation timeout"
    
    def __init__(self, operation, timeout):
        reason = f"{operation} timed out after {timeout:.1f}s"
        super().__init__(reason=reason)

class ResourceExhausted(OperationError):
    """资源耗尽异常"""
    ERROR_CODE = 1011
    DEFAULT_REASON = "Resource exhausted"
    
    def __init__(self, resource, limit):
        reason = f"{resource} exceeded limit of {limit}"
        super().__init__(reason=reason)
