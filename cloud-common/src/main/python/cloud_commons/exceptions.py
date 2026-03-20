#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

class cloudExceptionBase(Exception):
    """Base class for all cloud framework exceptions"""
    def __init__(self, message, **context):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        if 'code' in self.context:
            self.code = self.context['code']
    
    def __str__(self):
        base = f"{self.__class__.__name__}: {self.message}"
        if self.context:
            details = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base += f" [{details}]"
        return base
    
    def with_context(self, **additional_context):
        """Return new exception instance with additional context"""
        new_context = {**self.context, **additional_context}
        return self.__class__(self.message, **new_context)


class FatalException(cloudExceptionBase):
    """
    Represents unrecoverable errors requiring immediate process termination.
    
    Attributes:
        code: Required exit code (default: 1)
        action: Recommended remediation action
    """
    def __init__(self, message, code=1, **context):
        context.setdefault('code', code)
        super().__init__(message, **context)
        self.code = code
        
    RETRYABLE_CD = 2             # Retry after backoff
    CONFIG_ERROR_CD = 3          # Configuration issue
    PERMISSION_DENIED_CD = 4     # Access rights problem
    DEPENDENCY_FAILED_CD = 5     # Service dependency failure


class NonFatalException(cloudExceptionBase):
    """
    Represents recoverable errors allowing continued execution.
    
    Attributes:
        retry_after: Recommended retry delay in seconds (default: 60)
        transient: Indicates if error is temporary (default: True)
    """
    def __init__(self, message, retry_after=60, transient=True, **context):
        context.setdefault('retry_after', retry_after)
        context.setdefault('transient', transient)
        super().__init__(message, **context)
        self.retry_after = retry_after
        self.transient = transient


class TimeoutException(cloudExceptionBase):
    """
    Represents operation timeouts with actionable diagnostics.
    
    Attributes:
        duration: Timeout threshold in seconds
        operation: Name of timed out operation
    """
    def __init__(self, message, duration=None, operation=None, **context):
        base_msg = f"Operation timed out: {operation or 'unknown'}"
        if message:
            base_msg += f" - {message}"
            
        context.setdefault('duration', duration)
        context.setdefault('operation', operation)
        super().__init__(base_msg, **context)
        self.duration = duration
        self.operation = operation


# =====================
# Protocol Exceptions
# =====================
class ApiError(NonFatalException):
    """API communication errors (transient)"""
    RETRY_LIMIT = 5
    BACKOFF_BASE = 10


class ValidationError(FatalException):
    """Data validation failures (non-recoverable)"""
    def __init__(self, message, errors=None, **context):
        context['errors'] = errors or []
        super().__init__(message, code=FatalException.CONFIG_ERROR_CD, **context)
        self.errors = errors


class SecurityError(FatalException):
    """Security-related failures (non-recoverable)"""
    def __init__(self, message, **context):
        super().__init__(message, code=FatalException.PERMISSION_DENIED_CD, **context)


# =====================
# Error Categorization
# =====================
def is_transient_error(error: BaseException) -> bool:
    """Check if error can be retried after backoff"""
    if isinstance(error, NonFatalException):
        return error.transient
    return False

def is_retriable_error(error: BaseException) -> bool:
    """Check if error is eligible for retry"""
    if isinstance(error, (TimeoutException, ApiError)):
        return True
    if isinstance(error, NonFatalException):
        return error.transient
    return False

def suggest_remediation(error: BaseException) -> str:
    """Generate human-readable remediation guidance"""
    if isinstance(error, FatalException):
        codes = {
            FatalException.PERMISSION_DENIED_CD: "检查权限配置和访问凭证",
            FatalException.CONFIG_ERROR_CD: "验证配置文件语法和参�?,
            FatalException.DEPENDENCY_FAILED_CD: "确保所有依赖服务正常运�?
        }
        return codes.get(error.code, "查阅系统日志并联系支持团�?)
    
    if isinstance(error, ValidationError):
        return f"修复以下{len(error.errors)}个配置错�?
    
    if isinstance(error, TimeoutException):
        return f"增加超时阈值或优化操作: {error.operation}" 
    
    if isinstance(error, NonFatalException):
        return f"{error.retry_after}秒后重试"
    
    return "检查系统状态并查阅文档"
