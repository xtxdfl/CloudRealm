#!/usr/bin/env python3
"""
增强型 STOMP 协议错误处理系统
包含 12 种专业错误分类和上下文诊断信息
支持自动化重连策略和根因分析
"""

import logging
import socket
import time
from typing import Optional, Dict, Any, List

# 配置错误日志
log = logging.getLogger("stomp.errors")
log.addHandler(logging.StreamHandler())
log.setLevel(logging.WARNING)

# 错误代码映射表 (标准STOMP扩展)
ERROR_CODES = {
    100: "CONNECTION_INTERRUPTED",     # 网络中断
    101: "CONNECTION_TIMEOUT",         # 连接超时
    200: "AUTHENTICATION_FAILURE",     # 认证失败
    201: "PERMISSION_DENIED",          # 权限不足
    300: "PROTOCOL_VIOLATION",         # 协议违规
    301: "FRAME_FORMAT_ERROR",         # 帧格式错误
    400: "SUBSCRIPTION_FAILURE",       # 订阅失败
    401: "TRANSACTION_ABORTED",        # 事务中止
    500: "BROKER_RESOURCE_LIMIT",      # 资源不足
    600: "APPLICATION_ERROR"           # 应用层错误
}

# 错误恢复策略
RECOVERY_RETRY_FLAGS = {
    100: True,    # 网络错误可重试
    101: True,
    200: True,    # 认证失败需要新凭证
    201: False,   # 权限错误不可重试
    300: False,   # 协议错误不可重试
    301: False,
    400: True,    # 订阅失败可重试
    401: True,
    500: True,    # 资源错误可重试
    600: False
}


class StompException(Exception):
    """STOMP 协议异常基类，所有具体异常均继承此类"""
    
    def __init__(self, message: str, 
                 error_code: Optional[int] = None,
                 frame: Optional[Dict[str, Any]] = None,
                 connection_params: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        :param message: 异常描述信息
        :param error_code: STOMP扩展错误码
        :param frame: 关联的错误帧数据
        :param connection_params: 当前连接配置
        :param cause: 引起此异常的原始异常
        """
        super().__init__(message)
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.error_code = error_code
        self.frame = frame
        self.connection_params = connection_params or {}
        self.cause = cause
        self.auto_log()
        
        # 诊断标记
        self.recoverable = self.determine_recoverable()
        self.automatic_recovery = False
        self.connection_closed = False
    
    def auto_log(self) -> None:
        """自动记录异常信息到日志系统"""
        log_msg = f"{self.timestamp} - {self.__class__.__name__}: {self.args[0]}"
        if self.error_code:
            log_msg += f" [Code: {self.error_code}, Reason: {ERROR_CODES.get(self.error_code, 'UNKNOWN')}]"
        log.error(log_msg, exc_info=True)
        
        # 网络诊断信息
        if hasattr(self, 'network_diagnose'):
            log.debug("Network diagnostics: %s", self.network_diagnose)
    
    def determine_recoverable(self) -> bool:
        """确定错误是否可自动恢复"""
        if self.error_code is not None:
            return RECOVERY_RETRY_FLAGS.get(self.error_code, False)
        return False
    
    @property
    def recovery_strategy(self) -> str:
        """获取推荐的恢复策略"""
        if self.determine_recoverable():
            retry_delay = self._calculate_retry_delay()
            return f"应用重试策略: 等待 {retry_delay:.1f} 秒后自动重连"
        return "需要人工干预: 不可自动恢复的错误"
    
    def _calculate_retry_delay(self) -> float:
        """计算指数退避的重试间隔"""
        failed_attempts = self.connection_params.get('failed_attempts', 0)
        base_delay = self.connection_params.get('base_retry_delay', 1.0)
        max_delay = self.connection_params.get('max_retry_delay', 30.0)
        retry_delay = min(max_delay, base_delay * (2 ** min(failed_attempts, 5)))
        return retry_delay
    
    def to_dict(self) -> dict:
        """转换异常信息为诊断字典"""
        return {
            "type": self.__class__.__name__,
            "message": self.args[0],
            "code": self.error_code,
            "code_desc": ERROR_CODES.get(self.error_code, "UNKNOWN"),
            "timestamp": self.timestamp,
            "recoverable": self.determine_recoverable(),
            "recovery_strategy": self.recovery_strategy,
            "frame_snippet": self.format_frame_snippet(),
            "cause": str(self.cause) if self.cause else None
        }
    
    def format_frame_snippet(self, max_lines: int = 5) -> Optional[str]:
        """格式化错误帧摘要"""
        if not self.frame:
            return None
        command = self.frame.get('command')
        headers = ['%s: %s' % (k, v) for k, v in self.frame.get('headers', {})[:max_lines]]
        return f"{command}\n" + "\n".join(headers)
    
    def __str__(self):
        return self.format_detailed_message()
    
    def format_detailed_message(self) -> str:
        """生成带诊断信息的详细错误报告"""
        parts = [
            f"{self.__class__.__name__} [{self.timestamp}]",
            f"Message: {self.args[0]}"
        ]
        if self.error_code:
            parts.append(f"Error Code: {self.error_code} ({ERROR_CODES.get(self.error_code, 'UNKNOWN')})")
        if self.cause:
            parts.append(f"Caused by: {type(self.cause).__name__}: {str(self.cause)}")
        parts.append(f"Recovery: {self.recovery_strategy}")
        if self.frame:
            parts.append(f"Related Frame:\n{self.format_frame_snippet()}")
        return "\n".join(parts)


class ConnectionClosedException(StompException):
    """当服务器主动关闭连接时抛出"""
    
    def __init__(self, message="连接已被服务器关闭", 
                 error_code: int = 100,
                 server_message: Optional[str] = None,
                 frame: Optional[Dict[str, Any]] = None,
                 **kwargs):
        if server_message:
            message += f": {server_message}"
        super().__init__(message=message, error_code=error_code, frame=frame, **kwargs)
        self.connection_closed = True
        self.server_message = server_message
        self.network_diagnose = self._perform_network_diagnose()
    
    def _perform_network_diagnose(self) -> Dict[str, Any]:
        """执行网络诊断"""
        return {
            "local_address": get_local_address(),
            "remote_disconnected": True,
            "dns_status": check_dns_resolution(self.connection_params.get('host', '')),
            "port_status": check_port_status(
                self.connection_params.get('host', ''), 
                self.connection_params.get('port', 0)
            )
        }


class NotConnectedException(StompException):
    """当在未建立连接的状态下尝试操作时抛出"""
    
    def __init__(self, message="无有效连接: 操作被拒绝", 
                 action: str = "unknown",
                 **kwargs):
        message += f" [Action: {action}]"
        super().__init__(message=message, error_code=100, **kwargs)
        self.action = action


class ConnectFailedException(StompException):
    """当达到最大重连次数后仍无法建立连接时抛出"""
    
    def __init__(self, message="连接建立失败: 超过最大重试次数", 
                 error_code: int = 101,
                 failure_stats: Optional[Dict[str, int]] = None,
                 **kwargs):
        if failure_stats:
            message += f" ({failure_stats['attempts']} 次尝试, {failure_stats['duration']:.1f}秒)"
        super().__init__(message=message, error_code=error_code, **kwargs)
        self.failure_stats = failure_stats or {}
        self.automatic_recovery = False
        self.network_diagnose = {
            "failed_endpoints": [f"{h}:{p}" for h, p in self.failure_stats.get('tried_hosts', [])],
            "errors_by_type": failure_stats.get('error_counts', {}),
            "last_error": str(failure_stats.get('last_error'))
        }


class InterruptedException(StompException):
    """当数据读取被异常中断时抛出"""
    
    def __init__(self, message="操作被中断", 
                 error_code: int = 600,
                 operation: str = "receive",
                 **kwargs):
        message += f" [Operation: {operation}]"
        super().__init__(message=message, error_code=error_code, **kwargs)
        self.operation = operation


class AuthenticationFailure(StompException):
    """认证信息错误"""
    
    def __init__(self, message="认证失败", 
                 error_code: int = 200,
                 username: Optional[str] = None,
                 **kwargs):
        if username:
            message = f"用户 '{username}' {message}"
        super().__init__(message, error_code=error_code, **kwargs)
        self.username = username


class AuthorizationViolation(StompException):
    """权限不足错误"""
    
    def __init__(self, message="权限不足", 
                 error_code: int = 201,
                 resource: Optional[str] = None,
                 **kwargs):
        if resource:
            message += f" [Resource: {resource}]"
        super().__init__(message, error_code=error_code, **kwargs)
        self.resource = resource


class ProtocolViolation(StompException):
    """协议格式错误"""
    
    def __init__(self, message="协议格式错误", 
                 error_code: int = 300,
                 violation: Optional[str] = None,
                 **kwargs):
        if violation:
            message += f": {violation}"
        super().__init__(message, error_code=error_code, **kwargs)
        self.violation = violation


class IllegalFrameFormat(StompException):
    """帧格式非法"""
    
    def __init__(self, message="帧格式非法", 
                 error_code: int = 301,
                 frame_data: Optional[str] = None,
                 **kwargs):
        super().__init__(message, error_code=error_code, **kwargs)
        self.frame_data = frame_data[:512] if frame_data else None


class SubscriptionFailure(StompException):
    """订阅操作失败"""
    
    def __init__(self, message="订阅创建失败", 
                 error_code: int = 400,
                 destination: Optional[str] = None,
                 subscription_id: Optional[str] = None,
                 **kwargs):
        message += f" [{destination}]" if destination else ""
        if subscription_id:
            message += f" [ID: {subscription_id}]"
        super().__init__(message, error_code=error_code, **kwargs)
        self.destination = destination
        self.subscription_id = subscription_id


class TransactionAborted(StompException):
    """事务中止异常"""
    
    def __init__(self, message="事务中止", 
                 error_code: int = 401,
                 transaction_id: Optional[str] = None,
                 **kwargs):
        if transaction_id:
            message += f" [TX: {transaction_id}]"
        super().__init__(message, error_code=error_code, **kwargs)
        self.transaction_id = transaction_id


class ResourceLimitExceeded(StompException):
    """服务器资源不足"""
    
    def __init__(self, message="服务器资源不足", 
                 error_code: int = 500,
                 resource_type: str = "memory",
                 limit: Optional[int] = None,
                 **kwargs):
        if limit:
            message += f" [{resource_type} limit: {limit}]"
        super().__init__(message, error_code=error_code, **kwargs)
        self.resource_type = resource_type
        self.limit = limit


class MessagingException(StompException):
    """通用消息处理异常"""
    
    def __init__(self, message="消息处理错误", 
                 error_code: int = 600,
                 message_id: Optional[str] = None,
                 destination: Optional[str] = None,
                 **kwargs):
        if message_id and destination:
            message += f" [MsgID: {message_id} @ {destination}]"
        super().__init__(message, error_code=error_code, **kwargs)
        self.message_id = message_id
        self.destination = destination


# 实用诊断函数
def get_local_address() -> str:
    """获取本地网络地址信息"""
    try:
        return socket.gethostbyname(socket.gethostname())
    except socket.error:
        return "127.0.0.1"


def check_dns_resolution(hostname: str) -> List[str]:
    """检查DNS解析结果"""
    try:
        _, _, addresses = socket.gethostbyname_ex(hostname)
        return addresses
    except socket.error as e:
        return [f"resolution failed: {str(e)}"]


def check_port_status(host: str, port: int) -> str:
    """检查目标端口状态"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        result = s.connect_ex((host, port))
        return "open" if result == 0 else f"closed (error {result})"
    except Exception as e:
        return f"error: {str(e)}"
    finally:
        s.close()


class ExceptionRecoveryManager:
    """
    错误恢复管理器
    自动化处理可恢复的异常并进行智能重试
    """
    
    def __init__(self, reconnect_func, reconnect_params: Dict):
        self.reconnect_func = reconnect_func
        self.params = reconnect_params
        self.failure_stats = {
            'attempts': 0,
            'last_error': None,
            'error_counts': {},
            'tried_hosts': [],
            'start_time': time.time()
        }
    
    def handle_exception(self, exception: StompException) -> bool:
        """处理异常并执行恢复策略"""
        self._record_failure(exception)
        
        if exception.recoverable:
            return self._attempt_recovery(exception)
        
        return False
    
    def _record_failure(self, exception: StompException) -> None:
        """记录失败统计信息"""
        self.failure_stats['attempts'] += 1
        self.failure_stats['last_error'] = exception
        error_type = type(exception).__name__
        self.failure_stats['error_counts'][error_type] = self.failure_stats['error_counts'].get(error_type, 0) + 1
        
        if (exception.connection_params.get('host') and 
            exception.connection_params.get('port')):
            endpoint = (exception.connection_params['host'], exception.connection_params['port'])
            if endpoint not in self.failure_stats['tried_hosts']:
                self.failure_stats['tried_hosts'].append(endpoint)
        
        # 更新持续失败时间
        self.failure_stats['duration'] = time.time() - self.failure_stats['start_time']
    
    def _attempt_recovery(self, exception: StompException) -> bool:
        """执行恢复操作"""
        self.params['failed_attempts'] = self.failure_stats['attempts']
        
        if self._should_execute_recovery(exception):
            # 等待指数退避时间
            delay = exception._calculate_retry_delay()
            log.warning(
                "尝试 %d 自动恢复: 等待 %.1f 秒后重连...",
                self.failure_stats['attempts'], delay
            )
            
            time.sleep(delay)
            
            try:
                log.info("执行自动重新连接...")
                self.reconnect_func()
                return True
            except StompException as e:
                log.error("自动恢复失败: %s", str(e))
                self._record_failure(e)
        
        return False
    
    def _should_execute_recovery(self, exception: StompException) -> bool:
        """确定是否执行自动恢复"""
        max_attempts = self.params.get('max_retry_attempts', 5)
        
        # 检查是否达到最大尝试次数
        if self.failure_stats['attempts'] > max_attempts:
            log.critical("已达到最大恢复尝试次数 (%d)", max_attempts)
            return False
        
        # 检查是否可恢复的异常类型
        if not exception.recoverable:
            log.warning("跳过不可恢复的错误: %s", type(exception).__name__)
            return False
        
        return True
    
    def reset(self):
        """重置失败统计计数器"""
        self.failure_stats = {
            'attempts': 0,
            'last_error': None,
            'error_counts': {},
            'tried_hosts': [],
            'start_time': time.time()
        }


# -------------------- 错误测试工具 -------------------- 
if __name__ == "__main__":
    import json
    
    # 模拟连接参数
    conn_params = {
        'host': 'broker.example.com',
        'port': 61613,
        'username': 'user123',
        'reconnect': True,
        'failed_attempts': 0,
        'base_retry_delay': 1.0,
        'max_retry_delay': 30.0,
        'max_retry_attempts': 5
    }
    
    # 创建连接关闭异常
    closed_exc = ConnectionClosedException(
        "Broker disconnected after idle timeout",
        error_code=101,
        frame={
            'command': 'ERROR',
            'headers': {
                'message': 'Heartbeat timeout',
                'connection': 'close-requested'
            }
        },
        connection_params=conn_params
    )
    
    print("1. 连接关闭异常示例:")
    print(f"异常类型: {type(closed_exc).__name__}")
    print(f"错误信息: {closed_exc.args[0]}")
    print(f"恢复建议: {closed_exc.recovery_strategy}")
    print(f"诊断信息:\n{json.dumps(closed_exc.to_dict(), indent=2)}")
    
    # 模拟认证失败
    auth_exc = AuthenticationFailure(
        "Invalid credentials",
        error_code=200,
        username=conn_params['username'],
        connection_params=conn_params
    )
    
    print("\n2. 认证失败异常示例:")
    print(f"恢复建议: {auth_exc.recovery_strategy}")
    print(f"错误描述: {auth_exc.format_detailed_message()}")
    
    # 恢复管理器演示
    def reconnect_callback():
        print("\n[模拟] 执行重新连接操作...")
    
    mgr = ExceptionRecoveryManager(reconnect_callback, conn_params)
    
    print("\n3. 自动恢复流程演示:")
    for seq in range(1, 4):
        print(f"\n失败 #{seq}:")
        result = mgr.handle_exception(closed_exc)
        print(f"恢复状态: {'成功' if result else '失败'}")
        print(f"失败统计: {mgr.failure_stats}")

