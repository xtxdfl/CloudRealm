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

高效不可变配置管理系统

提供安全、不可变的配置字典实现，支持：
- 安全配置加密
- 动态参数化配置
- 自动类型转换
- 延迟错误处理
- 深拷贝递归转换
- 优雅的错误消息
"""

from resource_management.core.exceptions import Fail, ConfigurationError
from resource_management.core.encryption import ensure_decrypted
from collections.abc import Mapping, MutableMapping
import types
import re

IMMUTABLE_MESSAGE = """
配置字典不可更改!

如需在XML文件中添加动态属性，请使用{{parameter}}模板替换语法。
在XML文件中查找{{param}}模式的示例。
"""

CONFIGURATION_NOT_FOUND = """
无法在配置字典中找到参数 '{name}'!

可能原因:
1. 配置文件未定义该参数
2. 存在拼写错误或大小写不一致
3. 参数名称不符合XML命名规范

解决方案:
1. 检查配置文件是否定义了 '{name}'
2. 使用{{config_group/param_name}}格式访问嵌套参数
3. 如需获取未知参数的占位符，使用 UnknownConfiguration('{name}')
4. 使用标准XML配置模板，如 <name>{{param}}</name>
"""

class ConfigDictionary(Mapping):
    """
    不可变配置字典实现
    
    特性：
    • 配置不可变性: 防止运行时意外修改配置
    • 安全加密支持: 自动解密加密配置值
    • 智能类型转换: 自动转换"true"/"false"为布尔类型
    • 深拷贝递归转换: 支持多层嵌套配置结构
    • 模板参数化: 支持 {{param}} 参数替换语法
    
    使用场景：
      - 配置文件解析和处理
      - 安全敏感配置管理
      - 运行时配置参数化
      - XML配置文件预处理
    """
    
    __slots__ = ('_data', '_dynamic_pattern', '_encryption_enabled')
    
    def __init__(self, dictionary, encryption_enabled=True, dynamic_placeholder=r"\{\{(\w+)\}\}"):
        """
        初始化不可变配置字典
        
        :param dictionary: 原始配置字典
        :param encryption_enabled: 是否启用自动解密
        :param dynamic_placeholder: 动态参数匹配正则表达式
        """
        # 深拷贝并递归转换字典
        self._data = self._recursive_convert(dictionary)
        self._encryption_enabled = encryption_enabled
        self._dynamic_pattern = re.compile(dynamic_placeholder)
        
    def _recursive_convert(self, obj):
        """递归转换所有层级的字典为ConfigDictionary"""
        if isinstance(obj, MutableMapping):
            # 为字典项创建不可变副本
            immutable_dict = {k: self._recursive_convert(v) for k, v in obj.items()}
            return types.MappingProxyType(immutable_dict)
        elif isinstance(obj, list):
            # 列表项递归转换
            return [self._recursive_convert(item) for item in obj]
        elif isinstance(obj, tuple):
            # 元组项递归转换
            return tuple(self._recursive_convert(item) for item in obj)
        else:
            # 基本类型保持不变
            return obj
            
    def __getitem__(self, name):
        """
        获取配置参数值
        
        - 自动处理加密值
        - 执行类型转换("true"/"false"转布尔型)
        """
        try:
            # 定位配置值
            parts = name.split('/')
            value = self._data
            for part in parts:
                value = value[part]
            
            # 处理值
            return self._process_value(value, name)
        except (KeyError, TypeError) as e:
            # 未知配置参数处理
            if isinstance(e, TypeError) or name not in self:
                return UnknownConfiguration(name)
            raise ConfigurationError(f"访问配置错误: {str(e)}")
            
    def _process_value(self, value, name=None):
        """处理配置值：解密、类型转换、动态参数解析"""
        # 解密加密值
        if self._encryption_enabled:
            value = ensure_decrypted(value)
            
        # 自动类型转换
        if isinstance(value, str):
            lowered = value.lower()
            if lowered == "true":
                return True
            elif lowered == "false":
                return False
            elif lowered == "none" or lowered == "null":
                return None
            else:
                # 数值类型转换尝试
                try:
                    if '.' in value:
                        return float(value)
                    else:
                        return int(value)
                except (ValueError, TypeError):
                    # 解析动态参数模板
                    return self._resolve_dynamic_parameters(value, name)
        
        return value
        
    def _resolve_dynamic_parameters(self, value, context=None):
        """解析配置值中的动态参数模板"""
        if not isinstance(value, str):
            return value
            
        # 处理嵌套参数
        match = self._dynamic_pattern.search(value)
        if not match:
            return value
            
        # 递归解析所有动态参数
        def replace_func(m):
            param_name = m.group(1)
            try:
                # 解析嵌套参数
                param_value = self._process_value(self[param_name])
                return str(param_value)
            except Exception:
                return f"[ERROR: 参数 '{param_name}' 未定义]"
                
        return self._dynamic_pattern.sub(replace_func, value)
    
    def __iter__(self):
        """字典迭代支持"""
        return iter(self._data)
        
    def __len__(self):
        """字典长度支持"""
        return len(self._data)
        
    def __setitem__(self, name, value):
        """禁止修改配置值"""
        raise Fail(IMMUTABLE_MESSAGE)
        
    def __contains__(self, name):
        """检查参数是否存在"""
        try:
            parts = name.split('/')
            data = self._data
            for part in parts:
                if part not in data:
                    return False
                data = data[part]
            return True
        except TypeError:
            return False
            
    def __str__(self):
        """配置字典友好展示"""
        return self.pretty_format()
        
    def pretty_format(self, indent=0):
        """格式化展示配置字典"""
        lines = []
        indent_str = "  " * indent
        
        for key, value in self._data.items():
            if isinstance(value, ConfigDictionary) or (isinstance(value, Mapping) and not isinstance(value, str)):
                lines.append(f"{indent_str}{key}:")
                if isinstance(value, ConfigDictionary):
                    lines.append(value.pretty_format(indent+1))
                else:
                    # 处理普通字典
                    config_dict = ConfigDictionary(value)
                    lines.append(config_dict.pretty_format(indent+1))
            else:
                # 处理值显示
                display_value = value
                if isinstance(value, str) and len(value) > 50:
                    display_value = f"{value[:47]}..."
                
                lines.append(f"{indent_str}{key}: {display_value}")
                
        return "\n".join(lines)
            
    def to_dict(self):
        """将不可变字典转换为普通字典（用于JSON序列化）"""
        def convert(obj):
            if isinstance(obj, ConfigDictionary):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert(item) for item in obj)
            else:
                return obj
                
        return convert(self)


class UnknownConfiguration:
    """
    未知配置参数处理类
    
    特性：
    • 延迟错误处理：仅在访问属性时抛出异常
    • 详细错误信息：提供清晰问题诊断
    • 方法调用支持：支持调用语法访问
    • 动态参数模板支持：用于 {{param}} 语法
    """
    
    __slots__ = ('_name', '_accessed_attributes', '_called')
    
    def __init__(self, name):
        self._name = name
        self._accessed_attributes = []
        self._called = False
        
    def __getattr__(self, attr_name):
        """访问属性时记录访问路径"""
        # 构建访问路径
        full_path = f"{self._name}.{attr_name}"
        self._accessed_attributes.append(attr_name)
        return UnknownConfiguration(full_path)
        
    def __getitem__(self, key):
        """使用[]语法访问时记录访问路径"""
        # 构建访问路径
        full_path = f"{self._name}[{key}]"
        self._accessed_attributes.append(f"[{key}]")
        return UnknownConfiguration(full_path)
        
    def __call__(self, *args, **kwargs):
        """支持被作为函数调用"""
        self._called = True
        full_path = f"{self._name}(...)"
        self._accessed_attributes.append("(...)")
        return UnknownConfiguration(full_path)
        
    def __str__(self):
        """字符串表示时抛出异常"""
        self._report_error()
        return ""  # 实际不会执行到这里，因为上面已抛出异常
        
    def __repr__(self):
        """表示值访问时抛出异常"""
        self._report_error()
        return ""  # 实际不会执行到这里
        
    def __bool__(self):
        """布尔值访问时抛出异常"""
        self._report_error()
        return False  # 实际不会执行到这里
        
    def __int__(self):
        """整数值访问时抛出异常"""
        self._report_error()
        return 0  # 实际不会执行到这里
        
    def __float__(self):
        """浮点值访问时抛出异常"""
        self._report_error()
        return 0.0  # 实际不会执行到这里
        
    def _build_operation_path(self):
        """构建用户操作路径字符串"""
        if not self._accessed_attributes:
            return self._name
            
        path = self._name
        for attr in self._accessed_attributes:
            if attr.startswith('[') and attr.endswith(']'):
                # 用于集合访问
                path += attr
            elif attr == "(...)":
                # 用于函数调用
                path += "()"
            else:
                # 用于属性访问
                path += f".{attr}"
        return path
        
    def _report_error(self):
        """报告配置错误"""
        access_path = self._build_operation_path()
        msg = CONFIGURATION_NOT_FOUND.format(name=access_path)
        
        # 如果进行了调用，添加额外提示
        if "()" in access_path:
            msg += "\n提示: 配置值不能被当作函数调用，这是配置项不是函数!"
        
        # 如果使用了点操作符，提示用户检查层次结构
        if '.' in self._name or len(self._accessed_attributes) > 0:
            base_name = self._name.split('.')[0]
            if base_name != self._name:
                msg += f"\n提示: 检查配置组 '{base_name}' 是否存在"
        
        # 提示用户使用模板语法
        msg += f"\n提示: 如需在模板中使用该配置，请使用{{{{{access_path}}}}}语法"
        
        raise ConfigurationError(msg)
