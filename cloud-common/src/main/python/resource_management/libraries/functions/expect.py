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

cloud Agent

"""

__all__ = ["expect", "expect_v2", "ConfigValidator"]

from resource_management.libraries.script import Script
from resource_management.libraries.script.config_dictionary import UnknownConfiguration
from resource_management.core.exceptions import Fail, ComponentIsNotRunning
from typing import Any, Callable, Union, Dict, Optional, Tuple
import logging
import json
import os

def expect(name: str, expected_type: type, default_value: Any = None, 
           transform: Callable = None, secure: bool = False) -> Any:
    """
    从配置中获取指定路径的配置值，并进行类型验�?    
    :param name: 配置路径 (支持多级路径，如 "database/settings/timeout")
    :param expected_type: 期望的数据类�?(bool, int, float, str, list, dict)
    :param default_value: 找不到配置时的默认�?    :param transform: 对值进行额外处理的函数
    :param secure: 是否敏感配置项（日志时进行脱敏）
    :return: 经过验证和处理的配置�?    
    :raises Fail: 当配置类型不符合预期时抛�?    """
    config = Script.get_config()
    
    try:
        # 解析多级配置路径
        value = _fetch_nested_config(name, config, default_value)
        
        # 如果配置不可用（且无默认值），返回未知配置标�?        if value in [None, UnknownConfiguration] and default_value is None:
            return UnknownConfiguration(name)
        
        # 执行类型验证和数据转�?        value = _validate_and_transform(value, expected_type, name)
        
        # 执行额外转换（如果提供）
        if transform:
            value = transform(value)
            
        return value
    except Fail as e:
        raise e
    except Exception as e:
        logging.exception(f"配置处理失败: {name} - {str(e)}")
        return default_value if default_value is not None else UnknownConfiguration(name)

def expect_v2(name: str, expected_type: type, default_value: Any = None,
              transform: Callable = None, secure: bool = False) -> Any:
    """
    增强版配置获取函数，支持动态执行上下文和多种高级数据类�?    
    :param name: 配置路径
    :param expected_type: 期望的数据类�?    :param default_value: 默认�?    :param transform: 额外转换函数
    :param secure: 是否敏感配置
    :return: 经过验证的配置�?    """
    try:
        # 从执行上下文中获取配置�?        ctx = Script.get_execution_command()
        value = ctx.get_value(name, default_value)
        
        # 如果为缺省值，直接返回
        if value == default_value or value is None:
            return value
        
        # 处理配置�?        value = _validate_and_transform(value, expected_type, name)
        
        # 执行额外转换
        if transform:
            value = transform(value)
            
        return value
    except Exception as e:
        logging.exception(f"expect_v2处理失败: {name} - {str(e)}")
        if default_value is not None:
            return default_value
        return UnknownConfiguration(name)

def _fetch_nested_config(path: str, config: dict, default_value: Any) -> Any:
    """从嵌套结构中获取多级配置"""
    keys = path.split('/')
    current = config
    
    for key in keys:
        if not key:
            continue
            
        # 如果当前层级是字�?        if isinstance(current, dict):
            if key in current:
                current = current[key]
            else:
                # 尝试无大小写敏感匹配
                matched_key = next((k for k in current.keys() if k.lower() == key.lower()), None)
                if matched_key:
                    current = current[matched_key]
                else:
                    return default_value
        else:
            return default_value
    return current

def _validate_and_transform(value: Any, expected_type: type, config_name: str) -> Any:
    """验证和转换配置�?""
    # 布尔类型特殊处理
    if expected_type == bool:
        return _handle_bool_type(value, config_name)
    
    # 数字类型处理
    if expected_type in (int, float):
        return _handle_numeric_type(value, expected_type, config_name)
        
    # 字符串类型处�?    if expected_type == str and not isinstance(value, str):
        return str(value)
        
    # 列表类型处理
    if expected_type == list and isinstance(value, str):
        try:
            # 尝试解析JSON格式的列�?            return json.loads(value) if value.startswith('[') else value.split(',')
        except:
            return [value]
    
    # 字典类型处理
    if expected_type == dict and isinstance(value, str):
        try:
            # 尝试解析JSON格式的字�?            if value.startswith('{'):
                return json.loads(value)
            # 尝试解析key=value格式
            return dict(item.split('=') for item in value.split(','))
        except:
            return {'value': value}
    
    # 通用类型检�?    if not isinstance(value, expected_type):
        try:
            converted = expected_type(value)
            logging.warning(f"配置自动转换: {config_name} ({type(value).__name__} -> {expected_type.__name__})")
            return converted
        except (ValueError, TypeError) as e:
            raise Fail(f"配置 '{config_name}' 无法转换�?{expected_type.__name__}. 原始�? {_safe_value(value)}")
    
    return value

def _handle_bool_type(value: Any, config_name: str) -> bool:
    """处理布尔类型转换逻辑"""
    if isinstance(value, bool):
        return value
        
    if isinstance(value, str):
        lower_val = value.strip().lower()
        if lower_val in ("true", "yes", "on", "1", "enabled"):
            return True
        if lower_val in ("false", "no", "off", "0", "disabled"):
            return False
        # 检查类似布尔值的字符�?        if re.match(r'^(tru|enable?d?|y|1)$', lower_val):
            return True
        if re.match(r'^(fals|disab?le?d?|n|0)$', lower_val):
            return False
        raise Fail(f"布尔配置 '{config_name}' 值无�? {value}")
    
    if isinstance(value, (int, float)):
        return bool(value)
        
    raise Fail(f"无法转换的布尔配�?'{config_name}': {type(value).__name__} {_safe_value(value)}")

def _handle_numeric_type(value: Any, num_type: type, config_name: str) -> Any:
    """处理数值类型转�?""
    if isinstance(value, num_type):
        return value
        
    try:
        if num_type == int and isinstance(value, float):
            # 允许浮点到整数的转换（带警告�?            integer_value = int(value)
            logging.warning(f"配置转换: {config_name} (float -> int)：{value} -> {integer_value}")
            return integer_value
        
        if num_type == float and isinstance(value, int):
            return float(value)
            
        return num_type(value)
    except (ValueError, TypeError) as e:
        raise Fail(f"配置 '{config_name}' 无法转换�?{num_type.__name__}: {_safe_value(value)}")

def _safe_value(value: Any, max_len: int = 100) -> str:
    """安全表示值（避免敏感信息泄露�?""
    str_val = str(value)
    if len(str_val) > max_len:
        return str_val[:max_len] + f"...[{len(str_val)} chars]"
    return str_val

class ConfigValidator:
    """高级配置验证�?""
    
    @staticmethod
    def validate(config_name: str, value: Any, rules: Dict[str, Any]) -> None:
        """
        根据验证规则验证配置�?        
        :param config_name: 配置项名�?        :param value: 待验证的�?        :param rules: 验证规则字典
            - required: bool (是否必填)
            - type: type/List[type] (期望的类�?
            - min: numeric (最小�?
            - max: numeric (最大�?
            - options: List (允许的值列�?
            - regex: str (正则表达�?
            - validator: Callable (自定义验证函�?
        :raises Fail: 验证失败时抛�?        """
        # 必填项检�?        if rules.get('required', False) and value in [None, '', {}]:
            raise Fail(f"配置 '{config_name}' 是必填项但不能为�?)
        
        # 类型检�?        if 'type' in rules:
            expected_types = rules['type'] if isinstance(rules['type'], list) else [rules['type']]
            if not any(isinstance(value, t) for t in expected_types):
                type_names = [t.__name__ for t in expected_types]
                raise Fail(f"配置 '{config_name}' 期望类型 {', '.join(type_names)}, 实际类型: {type(value).__name__}")
        
        # 数字范围检�?        if isinstance(value, (int, float)):
            if 'min' in rules and value < rules['min']:
                raise Fail(f"配置 '{config_name}' 值不能小�?{rules['min']} (实际: {value})")
            if 'max' in rules and value > rules['max']:
                raise Fail(f"配置 '{config_name}' 值不能大�?{rules['max']} (实际: {value})")
        
        # 枚举值检�?        if 'options' in rules and value not in rules['options']:
            options_str = ', '.join(map(str, rules['options']))
            raise Fail(f"配置 '{config_name}' 值无�? 允许的选项: [{options_str}], 实际: {value}")
        
        # 正则表达式检�?        if 'regex' in rules and isinstance(value, str):
            if not re.match(rules['regex'], value):
                raise Fail(f"配置 '{config_name}' 不符合格式要�? {rules['regex']}")
        
        # 自定义验证器
        if 'validator' in rules:
            try:
                if not rules['validator'](value):
                    raise Fail(f"配置 '{config_name}' 自定义验证失�? {value}")
            except Exception as e:
                raise Fail(f"配置 '{config_name}' 自定义验证错�? {str(e)}")
    
    @staticmethod
    def validate_env(name: str, expected_type: type = str, default: Any = None) -> Any:
        """
        验证环境变量
        
        :param name: 环境变量名称
        :param expected_type: 期望类型
        :param default: 默认�?        :return: 验证后的�?        """
        value = os.environ.get(name, default)
        if value is None:
            return default
            
        try:
            # 布尔值特殊处�?            if expected_type == bool and isinstance(value, str):
                value = value.strip().lower()
                return value in ('1', 'true', 'yes')
            return expected_type(value)
        except Exception as e:
            logging.warning(f"环境变量 {name} 类型转换失败: {str(e)}")
            return default

def get_config_tree(path: str = "") -> Union[Dict, Any]:
    """
    获取配置树或指定路径的子�?    
    :param path: 配置路径 (例如: 'database/settings')
    :return: 配置字典或子�?    """
    config = Script.get_config()
    
    if not path:
        return config
        
    keys = [k for k in path.split('/') if k]
    current = config
    for key in keys:
        if key in current:
            current = current[key]
        else:
            raise ComponentIsNotRunning(f"配置路径 {path} 不存�?)
    return current

def inject_config(overrides: Dict[str, Any]) -> None:
    """
    向当前配置中注入自定义覆盖�?    
    :param overrides: 键值对字典 {config_path: new_value}
    """
    from resource_management.libraries.script import Script
    
    # 克隆原始配置
    if not hasattr(Script, '_original_config'):
        Script._original_config = Script.get_config().copy()
    
    # 创建配置副本并应用覆�?    updated_config = Script.get_config().copy()
    
    for key_path, value in overrides.items():
        keys = key_path.split('/')
        current = updated_config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    # 更新配置上下�?    Script.get_config_context().current = updated_config

def parse_bool(value: Any) -> bool:
    """通用布尔值解�?""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if not isinstance(value, str):
        raise ValueError("布尔值只能从字符串或数字转换")
    
    s = value.lower().strip()
    return s in ("true", "yes", "on", "1", "t", "y", "enable", "enabled")

class SecureConfigManager:
    """安全配置管理�?""
    
    def __init__(self, encryption_key: str = None):
        self._encryption_key = encryption_key or os.environ.get('SHDP_CONFIG_KEY')
        self._secure_cache = {}
    
    def get_secure(self, name: str, default: Any = None) -> Any:
        """获取配置并自动解密（如果启用加密�?""
        raw_value = expect_v2(name, str, default, secure=True)
        
        # 如果没有配置加密，或者值为默认值，直接返回
        if not self._encryption_key or raw_value in [None, default]:
            return raw_value
            
        # 检查是否加密�?(格式: ENC{...})
        if type(raw_value) is str and raw_value.startswith('ENC{') and raw_value.endswith('}'):
            return self.decrypt(raw_value[4:-1])
        return raw_value
    
    def decrypt(self, encrypted: str) -> str:
        """解密配置�?(简化实�?- 实际使用应替换为真实加密�?"""
        # 缓存解密结果
        if encrypted in self._secure_cache:
            return self._secure_cache[encrypted]
            
        # 这里使用简单的BASE64解码作为示例
        # 实际应用中应使用AES-GCM或类似算�?        try:
            from base64 import b64decode
            value = b64decode(encrypted.encode('utf-8')).decode('utf-8')
            self._secure_cache[encrypted] = value
            return value
        except Exception as e:
            logging.error(f"配置解密失败: {str(e)}")
            return ""
    
    def encrypt(self, plain: str) -> str:
        """加密配置�?(简化实�?"""
        if not plain:
            return ""
        from base64 import b64encode
        return f"ENC{{{b64encode(plain.encode('utf-8')).decode('utf-8')}}}"

def config_changed(monitored_keys: List[str]) -> bool:
    """
    检测监听的配置项是否发生变�?    :param monitored_keys: 需要监控的配置键列�?    :return: 配置是否有变�?    """
    if not hasattr(Script, '_prev_config'):
        Script._prev_config = {}
        return False
        
    current = Script.get_config()
    for key in monitored_keys:
        prev_value = _deep_get(Script._prev_config, key)
        curr_value = _deep_get(current, key)
        if prev_value != curr_value:
            return True
    return False

def _deep_get(config: Dict, path: str, default: Any = None) -> Any:
    keys = path.split('/')
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def snapshot_config() -> None:
    """保存当前配置快照"""
    import copy
    Script._prev_config = copy.deepcopy(Script.get_config())
