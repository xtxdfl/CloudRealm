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

class AgentException(Exception):
    """
    Custom exception class for Agent-related errors.
    
    Features:
    1. Enhanced error context tracking
    2. Support for error chaining (caused-by relationships)
    3. Rich representation for logging and debugging
    4. Structured error codes
    5. Integration points for localization
    
    >>> raise AgentException("File not found", code=404, context={"file": "/path/to/file.conf"})
    """
    
    # Standard error codes for common scenarios
    GENERIC_ERROR = 500
    CONFIG_ERROR = 501
    IO_ERROR = 502
    NETWORK_ERROR = 503
    PERMISSION_ERROR = 504
    TIMEOUT_ERROR = 505
    VALIDATION_ERROR = 506
    
    __ERROR_MESSAGES = {
        GENERIC_ERROR: "Unexpected error occurred",
        CONFIG_ERROR: "Configuration error",
        IO_ERROR: "Input/output error",
        NETWORK_ERROR: "Network communication error",
        PERMISSION_ERROR: "Insufficient permissions",
        TIMEOUT_ERROR: "Operation timed out",
        VALIDATION_ERROR: "Validation failed"
    }
    
    def __init__(self, message, code=None, context=None, cause=None, location=None):
        """
        Initializes a new AgentException.
        
        :param message: Human-readable error message (required)
        :param code: Numeric error code or standard error constant (optional)
        :param context: Dictionary providing additional context about the error (optional)
        :param cause: The original exception that caused this one (optional)
        :param location: Where the error occurred (file:line or function name) (optional)
        """
        assert isinstance(message, str), "Error message must be a string"
        
        # Error code resolution
        if code is None:
            self._code = self.GENERIC_ERROR
        elif isinstance(code, int) and 100 <= code <= 599:
            self._code = code
        else:
            self._code = int(code) if str(code).isdigit() else self.GENERIC_ERROR
        
        # Contextual information
        self._message = message
        self._context = context if isinstance(context, dict) else {}
        self._cause = cause
        self._location = str(location) if location else None
        
        # Store standard message if none provided
        if not message and self._code in self.__ERROR_MESSAGES:
            self._message = self.__ERROR_MESSAGES[self._code]
        
        # Prepare base exception message
        super_msg = f"{self._code}: {self._message}" 
        if self._context:
            super_msg += f" (context: {self.context_summary})"
        
        # Initialize superclass with combined message
        if cause:
            super().__init__(super_msg, cause)
        else:
            super().__init__(super_msg)
    
    @property
    def code(self):
        """Return the error code for programmatic handling"""
        return self._code
    
    @property
    def context(self):
        """Return the context dictionary with error details"""
        return self._context.copy()
    
    @property
    def primary_message(self):
        """Return the main error message"""
        return self._message
    
    @property
    def location(self):
        """Return the location of the error"""
        return self._location
    
    @property
    def context_summary(self):
        """Return a compact string representation of context"""
        if not self._context:
            return "None"
        
        items = [f"{k}={v}" for k, v in self._context.items()]
        return ", ".join(items)
    
    def __str__(self):
        """Return detailed error representation for user-facing messages"""
        components = [
            self.primary_message,
            self._format_context(),
            self._format_location(),
            self._format_cause()
        ]
        
        # Filter out empty components
        components = [c for c in components if c]
        
        # Join available components
        return ". ".join(components) + f" (code: {self.code})"
    
    def __repr__(self):
        """Return developer representation for debugging"""
        return (f"AgentException(message={repr(self.primary_message)}, "
                f"code={self.code}, "
                f"context={repr(self._context)}, "
                f"location={repr(self._location)}, "
                f"cause={repr(self._cause)})")
    
    def to_dict(self):
        """Return the exception as a structured dictionary"""
        return {
            "code": self.code,
            "message": self.primary_message,
            "context": self._context if self._context else {},
            "location": self._location,
            "cause": repr(self._cause) if self._cause else None
        }
    
    def _format_context(self):
        """Format context for display"""
        if not self._context:
            return None
        return f"Additional info: {self.context_summary}"
    
    def _format_location(self):
        """Format location for display"""
        if not self._location:
            return None
        return f"Location: {self._location}"
    
    def _format_cause(self):
        """Format cause for display"""
        if not self._cause:
            return None
        return f"Original error: {str(self._cause)}"

# Specialized exception classes for common scenarios
class ConfigException(AgentException):
    """Specialized exception for configuration issues"""
    def __init__(self, message, context=None, cause=None, location=None):
        super().__init__(message, 
                         code=AgentException.CONFIG_ERROR, 
                         context=context, 
                         cause=cause, 
                         location=location)

class NetworkException(AgentException):
    """Specialized exception for network issues"""
    def __init__(self, message, context=None, cause=None, location=None):
        super().__init__(message, 
                         code=AgentException.NETWORK_ERROR, 
                         context=context, 
                         cause=cause, 
                         location=location)

class PermissionException(AgentException):
    """Specialized exception for permission issues"""
    def __init__(self, message, context=None, cause=None, location=None):
        super().__init__(message, 
                         code=AgentException.PERMISSION_ERROR, 
                         context=context, 
                         cause=cause, 
                         location=location)

class TimeoutException(AgentException):
    """Specialized exception for timeouts"""
    def __init__(self, message, context=None, cause=None, location=None):
        super().__init__(message, 
                         code=AgentException.TIMEOUT_ERROR, 
                         context=context, 
                         cause=cause, 
                         location=location)

class ValidationException(AgentException):
    """Specialized exception for validation failures"""
    def __init__(self, message, context=None, cause=None, location=None):
        super().__init__(message, 
                         code=AgentException.VALIDATION_ERROR, 
                         context=context, 
                         cause=cause, 
                         location=location)

class SecurityException(AgentException):
    """Specialized exception for security violations"""
    SECURITY_ERROR = 507
    
    def __init__(self, message, context=None, cause=None, location=None):
        super().__init__(message, 
                         code=self.SECURITY_ERROR, 
                         context=context, 
                         cause=cause, 
                         location=location)
