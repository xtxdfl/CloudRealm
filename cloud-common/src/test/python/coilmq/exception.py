#!/usr/bin/env python3

from dataclasses import dataclass
import json
import logging
import uuid
from typing import Optional, Dict, Any, Union
import sentry_sdk

__authors__ = ['"Hans Lellelid" <hans@xmpl.org>', '异常处理小组 <errors@coilmq.org>']
__copyright__ = "Copyright 2023 CoilMQ 异常架构"
__license__ = """Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

# 异常记录器
exc_log = logging.getLogger('coilmq.exceptions')
sentry_sdk.init(dsn="https://your-sentry-dsn.ingest.sentry.io/your-project-id")

@dataclass(frozen=True)
class ErrorMetadata:
    """异常元数据载体（结构化上下文存储）"""
    error_code: str
    http_status: int
    severity: str  # 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL'
    recommendation: str
    doc_url: str

class CoilMQBaseException(Exception):
    """所有CoilMQ异常的基类（支持结构化元数据）"""
    
    # 预定义元数据表
    METADATA_REGISTRY = {}
    
    def __init__(self, 
                 message: str, 
                 context: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        @param message: 人类可读的错误描述
        @param context: 机器可读的错误上下文(JSON)
        @param cause: 原始触发异常(用于链式追踪)
        """
        super().__init__(message)
        self.uuid = uuid.uuid4()  # 唯一异常ID
        self.timestamp = int(time.time()*1000)  # 毫秒时间戳
        self.context = context or {}
        self.cause = cause
        
        # 自动采集元数据
        self.metadata = self.METADATA_REGISTRY.get(self.__class__.__name__, None)
        if not self.metadata:
            self.metadata = ErrorMetadata(
                error_code='UNK-999',
                http_status=500,
                severity='ERROR',
                recommendation="检查系统日志并联系支持团队",
                doc_url="https://docs.coilmq.org/errors/unknown"
            )
        
        # 结构化日志
        exc_log.error(self.as_structured_log(), exc_info=True)
        
        # 发送到Sentry
        sentry_sdk.set_context("coilmq_context", self.context)
        sentry_sdk.capture_exception(self)
    
    def as_structured_log(self) -> Dict[str, Any]:
        """生成结构化错误报告"""
        return {
            'exception_id': str(self.uuid),
            'timestamp': self.timestamp,
            'type': self.__class__.__name__,
            'message': str(self),
            'metadata': {
                'error_code': self.metadata.error_code,
                'http_status': self.metadata.http_status,
                'severity': self.metadata.severity,
                'recommendation': self.metadata.recommendation,
                'doc_url': self.metadata.doc_url,
            },
            'context': self.context,
            'cause_type': type(self.cause).__name__ if self.cause else None,
            'cause_message': str(self.cause) if self.cause else None,
        }
    
    def as_json(self) -> str:
        """获取JSON格式的错误报告"""
        return json.dumps(self.as_structured_log(), indent=2, ensure_ascii=False)

# --- 错误元数据注册装饰器 ---
def error_metadata(
    error_code: str,
    http_status: Optional[int] = 500,
    severity: str = "ERROR",
    recommendation: str = "请检查系统日志并联系支持团队",
    doc_url: str = None
):
    """异常元数据注册装饰器"""
    def decorator(cls):
        CoilMQBaseException.METADATA_REGISTRY[cls.__name__] = ErrorMetadata(
            error_code=error_code,
            http_status=http_status,
            severity=severity,
            recommendation=recommendation,
            doc_url=doc_url or f"https://errors.coilmq.org/{error_code}"
        )
        return cls
    return decorator

# ======================
# 异常类别体系 (现代化架构)
# ======================

# ----------------------
# 协议层错误 (100-199)
# ----------------------
@error_metadata(
    error_code="PROTO-101",
    http_status=400,
    recommendation="验证帧头格式是否符合STOMP规范"
)
class ProtocolError(CoilMQBaseException):
    """表示STOMP协议层面的基本错误"""
    pass

@error_metadata(
    error_code="PROTO-102",
    http_status=400,
    recommendation="检查帧头结构并确保存在必要属性"
)
class MissingHeaderError(ProtocolError):
    """缺失关键帧头错误（如destination）"""
    def __init__(self, header_name: str, context: dict = None):
        super().__init__(
            message=f"缺失关键帧头: {header_name}",
            context={'missing_header': header_name, **context or {}}
        )

@error_metadata(
    error_code="PROTO-103",
    http_status=400,
    recommendation="参照STOMP协议验证命令"
)
class InvalidCommandError(ProtocolError):
    """非法STOMP命令错误"""

@error_metadata(
    error_code="PROTO-104",
    http_status=400,
    recommendation="在ACK中包含正确的message-id并确保其关联有效消息"
)
class InvalidMessageAckError(ProtocolError):
    """非法消息确认错误（如未知message-id）"""

# ----------------------
# 配置错误 (200-299)
# ----------------------
@error_metadata(
    error_code="CONFIG-201",
    http_status=500,
    severity="FATAL",
    recommendation="重新加载配置并检查格式"
)
class ConfigError(CoilMQBaseException):
    """系统配置错误基本类别"""

@error_metadata(
    error_code="CONFIG-202",
    http_status=500,
    severity="FATAL",
    recommendation="确保证书存在且权限正确"
)
class TLSCertError(ConfigError):
    """TLS证书配置错误"""

@error_metadata(
    error_code="CONFIG-203",
    http_status=500,
    recommendation="验证存储后端配置并检查连接"
)
class StorageConfigError(ConfigError):
    """存储配置错误（如Redis设置不正确）"""

# ----------------------
# 认证授权错误 (300-399)
# ----------------------
@error_metadata(
    error_code="AUTH-301",
    http_status=401,
    recommendation="检查凭据有效性并重试"
)
class AuthError(CoilMQBaseException):
    """基础认证授权失败"""

@error_metadata(
    error_code="AUTH-302",
    http_status=401,
    recommendation="确保证书有效且未过期"
)
class CertificateAuthError(AuthError):
    """证书认证失败"""

@error_metadata(
    error_code="AUTH-303",
    http_status=403,
    recommendation="检查用户角色和权限设置"
)
class PermissionDeniedError(AuthError):
    """应用级权限拒绝"""

# ----------------------
# 连接与网络错误 (400-499)
# ----------------------
@error_metadata(
    error_code="NET-401",
    http_status=400,
    severity="WARN",
    recommendation="检查网络安全配置"
)
class NetworkProtocolError(CoilMQBaseException):
    """网络层协议错误"""

@error_metadata(
    error_code="NET-402",
    http_status=200,
    severity="INFO",
    recommendation="正常客户端断开行为，无需操作"
)
class ClientDisconnected(CoilMQBaseException):
    """客户端正常断开连接信号（非错误）"""

@error_metadata(
    error_code="NET-403",
    http_status=504,
    severity="ERROR",
    recommendation="检查网络路由并重试"
)
class ConnectionTimeout(NetworkProtocolError):
    """连接超时错误"""

# ----------------------
# 系统内部错误 (500-599)
# ----------------------
@error_metadata(
    error_code="SYS-501",
    http_status=503,
    severity="FATAL",
    recommendation="重启服务并查看资源监控"
)
class ResourceExhaustedError(CoilMQBaseException):
    """关键资源耗尽（如内存、连接数）"""

@error_metadata(
    error_code="SYS-502",
    http_status=503,
    severity="FATAL",
    recommendation="检查集群健康并执行故障转移"
)
class HighAvailabilityError(CoilMQBaseException):
    """高可用系统故障（集群仲裁丢失）"""

@error_metadata(
    error_code="SYS-503",
    http_status=500,
    severity="WARN",
    recommendation="清理存储并增加磁盘空间"
)
class StorageFullError(CoilMQBaseException):
    """持久化存储空间不足"""

# ======================
# 异常工具函数
# ======================

def exception_to_json_response(exc: CoilMQBaseException) -> Dict[str, Any]:
    """转换异常为WSGI/ASGI兼容的错误响应"""
    return {
        "status": exc.metadata.http_status,
        "type": exc.metadata.error_code,
        "title": exc.__class__.__name__,
        "detail": str(exc),
        "instance": f"error:{exc.uuid}",
        "recommendation": exc.metadata.recommendation,
        "documentation_url": exc.metadata.doc_url,
        "trace_id": sentry_sdk.get_trace_id() or str(uuid.uuid4())
    }

def configure_errors(report_to_sentry: bool = True):
    """全局错误处理器配置"""
    if report_to_sentry:
        sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
        logger.info("Sentry error reporting enabled")
    else:
        sentry_sdk.init(dsn="")  # 禁用Sentry
