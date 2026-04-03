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

Enhanced Configuration Management Toolkit
"""

__all__ = ["default", "default_string", "get_config", "as_bool", "as_list"]

from resource_management.libraries.script import Script
from resource_management.libraries.script.config_dictionary import UnknownConfiguration
from resource_management.core.logger import Logger
from typing import Any, Union, List, Tuple, Dict, Callable, Optional
import re

class ConfigManager:
    """高级配置管理器"""
    _config_cache = {}
    
    @classmethod
    def get_full_config(cls) -> Dict[str, Any]:
        """获取完整配置字典（带缓存）"""
        if "full_config" not in cls._config_cache:
            cls._config_cache["full_config"] = Script.get_config()
        return cls._config_cache["full_config"]
    
    @classmethod
    def get_nested_value(
        cls, 
        path: str, 
        default: Any = None, 
        *,
        transform: Callable = None,
        secure: bool = False
    ) -> Any:
        """
        从嵌套配置结构中获取值
        
        :param path: 配置路径（支持多级路径，如 "database/settings/timeout"）
        :param default: 找不到配置时的默认值
        :param transform: 值转换函数
        :param secure: 是否敏感配置项
        :return: 找到的配置值或默认值
        """
        config = cls.get_full_config()
        
        keys = [k for k in path.split("/") if k]
        if not keys:
            return default
            
        current = config
        for key in keys[:-1]:
            if key in current and isinstance(current[key], dict):
                current = current[key]
            else:
                # 尝试大小写不敏感匹配
                if isinstance(current, dict):
                    matched_key = next(
                        (k for k in current.keys() if k.lower() == key.lower()), 
                        None
                    )
                    if matched_key and isinstance(current[matched_key], dict):
                        current = current[matched_key]
                    else:
                        return default
                else:
                    return default
                    
        last_key = keys[-1]
        if last_key in current:
            value = current[last_key]
        else:
            # 大小写不敏感匹配最终键
            if isinstance(current, dict):
                matched_key = next(
                    (k for k in current.keys() if k.lower() == last_key.lower()), 
                    None
                )
                value = current[matched_key] if matched_key else default
            else:
                value = default
        
        # 执行值转换
        if transform:
            try:
                value = transform(value)
            except (TypeError, ValueError) as e:
                Logger.warning(
                    f"配置转换失败 [{path}]: {str(e)}，使用转换前值: {_safe_value(value, secure)}"
                )
        
        return value

def default(name: str, default_value: Any, *, 
            transform: Callable = None) -> Any:
    """
    从配置中获取指定路径的配置值（支持默认值）
    
    :param name: 配置路径（支持多级路径，如 "database/settings/timeout"）
    :param default_value: 找不到配置时的默认值
    :param transform: 值转换函数（如 int, str, as_bool 等）
    :return: 配置值或默认值
    """
    value = ConfigManager.get_nested_value(name, default_value, transform=transform)
    
    # 当获取到UnknownConfiguration时的特殊处理
    if isinstance(value, UnknownConfiguration):
        Logger.debug(f"配置 '{name}' 无法解析，使用默认值: {default_value}")
        return default_value
    
    # 如果值为空且默认值不为空，则使用默认值
    if value in (None, "", {}, []) and default_value not in (None, "", {}, []):
        return default_value
        
    return value

def default_string(
    name: str, 
    default_value: Union[str, List], 
    delimiter: str = ",", 
    *, 
    secure: bool = False
) -> str:
    """
    从配置中获取指定路径的配置值并转换为字符串
    
    :param name: 配置路径
    :param default_value: 默认值（字符串或列表）
    :param delimiter: 当配置值为列表时的连接符
    :param secure: 是否敏感配置项
    :return: 字符串表示的配置值
    """
    raw_value = ConfigManager.get_nested_value(name, default_value, secure=secure)
    
    # 处理UnknownConfiguration情况
    if isinstance(raw_value, UnknownConfiguration):
        Logger.debug(f"配置 '{name}' 无法解析，使用默认值")
        return _convert_to_string(default_value, delimiter, secure)
    
    # 如果配置值为列表，则连接为字符串
    if isinstance(raw_value, list):
        return delimiter.join(str(item) for item in raw_value)
        
    # 如果配置值为字典，则转换为键值对字符串
    if isinstance(raw_value, dict):
        return delimiter.join(f"{k}={v}" for k, v in raw_value.items())
        
    # 默认转换为字符串
    return str(raw_value)

def get_config(
    name: str, 
    expected_type: type = None, 
    default_value: Any = None, 
    *, 
    required: bool = False,
    transform: Callable = None,
    secure: bool = False,
    regex: Optional[str] = None
) -> Any:
    """
    获取配置值并进行类型验证和格式检查
    
    :param name: 配置路径
    :param expected_type: 期望的数据类型（bool, int, float, str, list, dict）
    :param default_value: 找不到配置时的默认值
    :param required: 是否为必须参数（缺失时报错）
    :param transform: 自定义转换函数
    :param secure: 是否敏感配置项
    :param regex: 对字符串值的正则验证模式
    :return: 经过验证的配置值
    :raises ValueError: 当配置验证失败时抛出
    """
    value = ConfigManager.get_nested_value(name, default_value, transform=transform, secure=secure)
    
    # 处理必须参数缺失情况
    if value is None and required:
        if isinstance(value, UnknownConfiguration):
            raise ValueError(f"必须的配置 '{name}' 无法解析")
        raise ValueError(f"必须的配置 '{name}' 不存在")
    
    # 类型检查
    if expected_type and not isinstance(value, expected_type):
        try:
            # 尝试类型转换
            converted = expected_type(value)
            Logger.info(
                f"配置自动类型转换: {name} ({type(value).__name__} -> {expected_type.__name__})"
            )
            value = converted
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"配置 '{name}' 类型错误: "
                f"期望 {expected_type.__name__}, "
                f"实际 {type(value).__name__} - {_safe_value(value, secure)}"
            )
    
    # 正则表达式检查
    if regex and isinstance(value, str) and not re.match(regex, value):
        raise ValueError(
            f"配置 '{name}' 不匹配模式 '{regex}': {_safe_value(value, secure)}"
        )
    
    return value

def as_bool(value: Any, default_value: bool = False) -> bool:
    """
    将值转换为布尔类型
    
    :param value: 要转换的值
    :param default_value: 转换失败时的默认值
    :return: 布尔值
    """
    if isinstance(value, bool):
        return value
        
    if isinstance(value, (int, float)):
        return bool(value)
        
    if isinstance(value, str):
        lower_val = value.lower().strip()
        # 匹配多种布尔形式
        if re.match(r'^(1|t(rue)?|yes|on|enabled?|y)$', lower_val):
            return True
        if re.match(r'^(0|f(alse)?|no|off|disabled?|n)$', lower_val):
            return False
            
    Logger.warning(f"无法转换的布尔值: {type(value).__name__} '{value}'，使用默认值: {default_value}")
    return default_value

def as_list(value: Any, delimiter: str = ",", *, remove_empty: bool = True) -> List[str]:
    """
    将值转换为列表
    
    :param value: 要转换的值
    :param delimiter: 分割字符串的分隔符
    :param remove_empty: 是否移除空元素
    :return: 字符串列表
    """
    if value is None:
        return []
        
    if isinstance(value, list):
        return value
        
    if isinstance(value, dict):
        return list(value.items())
        
    if not isinstance(value, str):
        return [str(value)]
        
    # 分割字符串
    parts = value.split(delimiter)
    
    # 清理元素
    processed = [part.strip() for part in parts] 
    
    # 移除空元素
    if remove_empty:
        processed = [part for part in processed if part]
        
    return processed

def _safe_value(value: Any, secure: bool = False, max_len: int = 100) -> str:
    """
    安全表示配置值（防止敏感信息泄露）
    
    :param value: 要处理的值
    :param secure: 是否为敏感值
    :param max_len: 最大显示长度
    :return: 安全字符串表示
    """
    if value is None:
        return "None"
        
    if secure:
        if isinstance(value, (list, dict)) and value:
            return f"[*** {len(value)} items ***]"
        return "******"
    
    string_val = str(value)
    if len(string_val) <= max_len:
        return string_val
    return f"{string_val[:max_len]}...[{len(string_val)} chars]"

def _convert_to_string(value: Any, delimiter: str, secure: bool) -> str:
    """将值转换为字符串表示"""
    if isinstance(value, list):
        return delimiter.join(str(item) for item in value)
    return _safe_value(value, secure)

class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_config_types(payload: dict, schema: dict) -> None:
        """
        批量验证配置数据结构
        
        :param payload: 要验证的配置字典
        :param schema: 验证模式字典 {配置路径: (类型, 其他参数)}
        :raises ValueError: 验证失败时抛出
        样例：
        schema = {
            "database/port": (int, {"min": 1024, "max": 65535}),
            "debug_mode": (bool, {"required": True})
        }
        """
        for path, (expected_type, options) in schema.items():
            try:
                required = options.get("required", False)
                default_val = options.get("default")
                
                value = get_config(
                    path,
                    expected_type=expected_type,
                    default_value=default_val,
                    required=required
                )
                
                # 最小值检查
                if "min" in options and value < options["min"]:
                    raise ValueError(
                        f"配置 '{path}' 值 {value} < 最小值 {options['min']}"
                    )
                
                # 最大值检查
                if "max" in options and value > options["max"]:
                    raise ValueError(
                        f"配置 '{path}' 值 {value} > 最大值 {options['max']}"
                    )
                    
                # 枚举值检查
                if "options" in options and value not in options["options"]:
                    raise ValueError(
                        f"配置 '{path}' 值 {value} 不在允许范围内: {options['options']}"
                    )
                    
                # 正则验证检查
                if "regex" in options and expected_type == str:
                    if not re.match(options["regex"], value):
                        raise ValueError(
                            f"配置 '{path}' 不匹配模式 '{options['regex']}'"
                        )
            except ValueError as e:
                Logger.error(f"配置验证失败: {str(e)}")
                raise
