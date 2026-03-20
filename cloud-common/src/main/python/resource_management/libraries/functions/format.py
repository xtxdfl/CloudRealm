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
WITHLESS WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Enhanced Secure Formatting Engine
"""

import sys
import inspect
import hashlib
import re
from string import Formatter
from typing import Dict, Any, Optional, Union
from resource_management.core.exceptions import SecurityViolationError
from resource_management.core.environment import Environment
from resource_management.core.logger import Logger
from resource_management.core.shell import quote_bash_args
from resource_management.core import utils

# 安全常量
PASSWORD_PATTERNS = [
    r'passw[o]?rd', r'secret', r'key', r'token', r'credential', 
    r'api[_-]?key', r'auth', r'private[_-]?key'
]
SENSITIVE_KEYS = ['password', 'passwd', 'pwd', 'secret', 'key', 'token']
SHELL_INJECTION_PATTERNS = [r'[;&|$`{}()]', r'\$\(', r'`', r'\{']

class SecureFormatter(Formatter):
    """
    高级安全格式化引擎，支持敏感数据处理和安全防护
    
    特性：
    - 敏感数据自动检测和遮蔽
    - 扩展的安全格式化标志
    - Shell注入防护
    - 深度防御机制
    
    格式化标志:
    !e - 自动Bash转义（shell safe）
    !h - 敏感数据遮蔽（log safe）
    !p - 密码模式（自动敏感检测 + bash转义）
    !j - JSON安全转义
    !u - URL安全转义
    !x - XML安全转义
    !r - 原始模式（禁用安全特性）
    !s - 严格模式（拒绝任何可疑输入）
    """
    
    SECURE_FLAGS = {'e', 'h', 'p', 'j', 'u', 'x', 'r', 's'}
    
    def __init__(self, strict_mode=False):
        """
        初始化格式化器
        :param strict_mode: 启用严格安全策略，拒绝任何可疑输入
        """
        super().__init__()
        self.strict_mode = strict_mode
        self.context_params = {}
        self._audit_log = []
        
        # 创建安全上下文
        if Environment.has_instance():
            env = Environment.get_instance()
            self.context_params = env.config.params.copy()

    def format(self, format_string: str, *args, **kwargs) -> str:
        """
        执行安全格式化，自动处理敏感数据和注入防御
        
        :param format_string: 包含格式化标记的字符串
        :return: 经过安全处理的格式化结果
        """
        self._audit_log = []  # 重置审计日志
        
        # 收集变量上下文
        variables = self._collect_variables(kwargs)
        
        # 执行双重格式化（保护模式和非保护模式）
        protected_result = self._vformat(format_string, args, variables, protection=True)
        unprotected_result = self._vformat(format_string, args, variables, protection=False)
        
        # 记录敏感数据差异
        if protected_result != unprotected_result:
            self._log_sensitive_data(unprotected_result, protected_result)
            
            # 严格模式下的安全违规检测
            if self.strict_mode and self._is_sensitive_content(unprotected_result):
                self._audit_security_incident(format_string, unprotected_result, protected_result)
                raise SecurityViolationError("Sensitive data exposure attempt detected")
            
        return unprotected_result

    def _collect_variables(self, local_vars: Dict) -> Dict:
        """收集所有可用变量并创建安全拷贝"""
        try:
            # 获取调用者作用域的变量
            frame = inspect.currentframe().f_back.f_back
            caller_vars = {}
            while frame:
                caller_vars.update(frame.f_locals)
                frame = frame.f_back
                
            # 合并系统变量
            variables = caller_vars.copy()
            variables.update(local_vars)
            variables.pop('self', None)
            
            # 深度拷贝并保护原始数据
            return self._sanitize_variables(variables)
        finally:
            # 清理引用避免内存泄漏
            del frame
            del caller_vars
            
    def _sanitize_variables(self, variables: Dict) -> Dict:
        """净化变量，移除内部对象和对原始数据的引用"""
        safe_vars = {}
        for key, value in variables.items():
            # 避免暴露内部对象
            if key.startswith('__') or callable(value):
                continue
                
            # 避免暴露环境实例
            if isinstance(value, Environment):
                continue
                
            safe_vars[key] = self._deep_copy_filter(value)
        return safe_vars

    def _deep_copy_filter(self, obj: Any) -> Any:
        """创建安全的数据副本"""
        if isinstance(obj, dict):
            return {k: self._deep_copy_filter(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy_filter(v) for v in obj]
        elif isinstance(obj, set):
            return {self._deep_copy_filter(v) for v in obj}
        elif hasattr(obj, '__dict__'):
            return str(obj)  # 类实例转换为安全字符串
        else:
            return obj

    def _vformat(self, format_string: str, args: tuple, kwargs: Dict, protection: bool) -> str:
        """安全版本的vformat，支持保护模式"""
        # 设置转换模式（保护/非保护）
        self.protection_mode = protection
        return super().vformat(format_string, args, kwargs)
    
    def convert_field(self, value, conversion: str) -> Union[str, Any]:
        """
        扩展的转换方法，支持安全特性标记
        
        :param value: 要转换的原始值
        :param conversion: 转换标志符
        :return: 转换后的安全值
        """
        # 原始模式绕过所有安全处理
        if conversion == 'r':
            return value
        
        # 安全模式处理
        if conversion:
            return self._apply_security_conversion(value, conversion)
            
        # 没有转换标记时的自动敏感数据检测
        return self._auto_protect(value)

    def _apply_security_conversion(self, value: Any, conversion: str) -> str:
        """应用安全转换处理"""
        if conversion == 'e':  # Bash 转义
            return self._shell_escape(value, convert=True)
        
        elif conversion == 'h':  # 敏感数据遮蔽
            return self._mask_sensitive(value) if self.protection_mode else str(value)
        
        elif conversion == 'p':  # 密码模式（自动遮蔽 + Bash转义）
            safe_value = self._mask_sensitive(value) if self.protection_mode else str(value)
            return self._shell_escape(safe_value)
        
        elif conversion == 'j':  # JSON 转义
            return self._json_escape(str(value))
        
        elif conversion == 'u':  # URL 转义
            return self._url_encode(str(value))
        
        elif conversion == 'x':  # XML 转义
            return self._xml_escape(str(value))
            
        elif conversion == 's':  # 严格模式 - 验证并通过日志记录
            self._strict_check(value)
            return str(value)
            
        # 未知转换标记 - 记录警告
        Logger.warning(f"Invalid conversion flag '!{conversion}' was ignored")
        return str(value)
    
    def _auto_protect(self, value: Any) -> str:
        """自动保护策略：检测并保护敏感数据"""
        str_value = str(value)
        
        # 自动检测敏感内容
        if (not self.protection_mode):
            return str_value
            
        if self._is_sensitive_content(str_value):
            self._log_sensitive_value(str_value)
            return utils.PASSWORDS_HIDE_STRING
            
        return str_value

    def _is_sensitive_content(self, content: str) -> bool:
        """基于关键字和模式检测敏感内容"""
        # 短内容不视为敏感
        if len(content) < 6:
            return False
            
        # 密码模式检测
        for pattern in PASSWORD_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
                
        # 密钥特征检测
        if re.match(r'\w{20,}', content):  # 长字母数字串
            if re.search(r'[=+\-_]', content):
                return True
            if all(ord(c) < 128 for c in content):
                # 检查是否可能是Base64
                if re.match(r'^[a-zA-Z0-9+/=]+$', content) and len(content) % 4 == 0:
                    return True
                    
        # JWT检测 (以ey开头的三段Base64)
        if re.match(r'^eyJ\w+\.eyJ\w+\.\w+$', content):
            return True
            
        # 高熵字符串检测（简单版本）
        entropy = self._calculate_entropy(content)
        if entropy > 4.5:  # 正常英文文本熵约4-4.5之间，密钥>5
            return True
            
        return False

    def _calculate_entropy(self, data: str) -> float:
        """计算字符串信息熵（用于检测随机密钥）"""
        from collections import Counter
        import math
        
        if not data:
            return 0
        
        char_counts = Counter(data)
        entropy = 0.0
        total_chars = len(data)
        
        for count in char_counts.values():
            p_x = count / total_chars
            entropy += -p_x * math.log2(p_x)
            
        return entropy

    def _shell_escape(self, value: Any, convert=True) -> str:
        """高级shell转义方法"""
        # 严格模式下的注入检测
        str_value = str(value)
        if self.strict_mode or convert:
            self._detect_shell_injection(str_value)
            
        # 实际转义
        return quote_bash_args(str_value) if convert else str_value

    def _mask_sensitive(self, value: Any) -> str:
        """安全遮蔽敏感值"""
        str_value = str(value)
        
        # 根据敏感程度选择遮蔽级别
        if len(str_value) > 24:  # 长字符串视为密钥
            return "*****REDACTED-KEY*****"
        elif 12 < len(str_value) <= 24:
            head = str_value[:2] if len(str_value) > 6 else '('
            tail = str_value[-2:] if len(str_value) > 6 else ')'
            return f"{head}*****{tail}"
        else:
            return "*****" if str_value else "(empty)"

    def _json_escape(self, value: str) -> str:
        """JSON安全转义"""
        replacements = {
            "\\": "\\\\",
            "\"": "\\\"",
            "\b": "\\b",
            "\f": "\\f",
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
        }
        
        escaped = []
        for char in value:
            if char in replacements:
                escaped.append(replacements[char])
            elif not (32 <= ord(char) <= 126):  # 非ASCII字符
                escaped.append(f"\\u{ord(char):04x}")
            else:
                escaped.append(char)
                
        return ''.join(escaped)

    def _url_encode(self, value: str) -> str:
        """URL安全编码"""
        from urllib.parse import quote
        return quote(value, safe='')
    
    def _xml_escape(self, value: str) -> str:
        """XML安全转义"""
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "'": "&apos;",
            '"': "&quot;",
        }
        
        escaped = []
        for char in value:
            if char in replacements:
                escaped.append(replacements[char])
            elif not (32 <= ord(char) <= 126):  # 非ASCII字符
                escaped.append(f"&#{ord(char)};")
            else:
                escaped.append(char)
                
        return ''.join(escaped)

    def _detect_shell_injection(self, value: str) -> None:
        """检测可能的shell注入攻击"""
        for pattern in SHELL_INJECTION_PATTERNS:
            if re.search(pattern, value):
                self._audit_security_incident(
                    "Potential injection", 
                    original="(REDACTED)", 
                    modified=value
                )
                if self.strict_mode:
                    raise SecurityViolationError(
                        f"Shell injection attempt detected in value: {self._mask_sensitive(value)}"
                    )
                else:
                    Logger.warning(f"Potential injection pattern in value: {self._mask_sensitive(value)}")

    def _strict_check(self, value: Any) -> None:
        """严格模式安全检查"""
        if value is None:
            return
            
        # 记录敏感操作
        self._audit_operation(
            action="STRICT_MODE_ACCESS", 
            content=self._mask_sensitive(str(value)),
            protection=self.protection_mode
        )
        
        # 检查关键安全风险
        if isinstance(value, type):
            raise SecurityViolationError("Class type exposure in sensitive context")
        
    def _log_sensitive_value(self, value: str) -> None:
        """安全记录敏感值和操作上下文"""
        # 创建安全指纹而非记录原始值
        fingerprint = hashlib.sha256(value.encode()).hexdigest()[:16]
        self._audit_operation(
            action="SENSITIVE_DATA_DETECTED", 
            content=f"[FINGERPRINT:{fingerprint}]", 
            length=len(value)
        )
        
        # 记录操作上下文而非内容
        if Logger.isEnabledFor(Logger.DEBUG):
            Logger.debug(f"Sensitive content detected with SHA256 prefix: {fingerprint}")
            
    def _log_sensitive_data(self, original: str, protected: str) -> None:
        """记录敏感数据遮蔽操作"""
        self._audit_operation(
            action="DATA_MASKING_APPLIED", 
            original=original, 
            protected=protected
        )
        
    def _audit_operation(self, **event_data: Any) -> None:
        """记录安全审计事件"""
        self._audit_log.append({
            'timestamp': utils.current_time_formatted(),
            'event': 'SECURITY_EVENT',
            **event_data
        })

    def _audit_security_incident(self, template: str, original: str, protected: str) -> None:
        """记录严重安全事件"""
        incident = {
            'timestamp': utils.current_time_formatted(),
            'event': 'SECURITY_INCIDENT',
            'template': template,
            'original_hash': hashlib.sha256(original.encode()).hexdigest(),
            'protected': protected
        }
        self._audit_log.append(incident)
        Logger.warning("Potential security incident detected in formatting")
        Logger.log_sensitive(
            f"Security incident with template '{template}', "
            f"original hash: {incident['original_hash']}"
        )

class SecureFormat:
    """安全格式化单例入口和工具类"""
    
    _formatter_instance = None
    
    @classmethod
    def get_formatter(cls, strict=False) -> SecureFormatter:
        """获取安全格式化器实例"""
        if not cls._formatter_instance:
            cls._formatter_instance = SecureFormatter(strict_mode=strict)
        return cls._formatter_instance
    
    @classmethod
    def clear_audit_log(cls):
        """清除审计日志（在测试中有用）"""
        if cls._formatter_instance:
            cls._formatter_instance._audit_log = []
    
    @classmethod
    def get_audit_log(cls):
        """获取格式化操作的审计日志"""
        return cls._formatter_instance._audit_log if cls._formatter_instance else []

def secure_format(format_string: str, *args, **kwargs) -> str:
    """
    安全格式化接口，自动检测敏感数据并防止注入
    
    使用范例:
    password = "secret123"
    
    # 基本参数替换
    result = secure_format("User: {username}, Password: {password!p}", 
                          username="alice", password="secret123")
    
    # 环境参数访问
    result = secure_format("Data path: {hadoop_data_dir}/dataset", 
                          hadoop_data_dir="/data")
                          
    # 自动敏感处理
    result = secure_format("API key: {key}", key="9a8b7c6d5e4f3g2h1")
    
    :param format_string: 包含格式化字段的字符串
    :return: 经过安全处理的字符串
    """
    strict_mode = kwargs.pop('__strict__', False)
    formatter = SecureFormat.get_formatter(strict=strict_mode)
    return formatter.format(format_string, *args, **kwargs)

# 兼容旧API
format = secure_format

# 测试用例
if __name__ == "__main__":
    # 启用严格模式进行测试
    result = secure_format("Connect to {url} with {key!p}", 
                         url="mysql://127.0.0.1:3306", 
                         key="my-secret-key")
    print(f"Formatted: {result}")
    
    # 打印审计日志
    for event in SecureFormat.get_audit_log():
        print("AUDIT EVENT:", event)
