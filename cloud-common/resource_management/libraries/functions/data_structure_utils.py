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

Advanced Dictionary Access Utilities for cloud Agent
"""

from typing import Any, Union, List, Tuple, Dict, Type, Callable, Optional
from types import TracebackType
import sys

__all__ = ["get_from_dict", "convert_to_list", "DictPathAccessor"]

class KeyNotFound:
    """哨兵类型，表示在字典路径查找中键不存�?""
    __instance = None
    
    def __new__(cls):
        """确保单例模式，禁止直接实例化"""
        if cls.__instance is None:
            cls.__instance = super(KeyNotFound, cls).__new__(cls)
        return cls.__instance
    
    def __reduce__(self) -> Tuple[Type, Tuple]:
        """支持序列�?""
        return (KeyNotFound, ())
    
    def __repr__(self) -> str:
        return "<KeyNotFound Sentinel>"
    
    def __bool__(self) -> bool:
        """布尔值始终为假，用于简洁的条件判断"""
        return False

class DictPathAccessor:
    """通过上下文管理器提供安全的字典路径访�?""
    
    def __init__(
        self, 
        data: Dict[Any, Any], 
        path: Union[str, List[Any], Tuple[Any]],
        default: Any = KeyNotFound
    ):
        """
        初始化数据路径访问器
        
        :param data: 目标字典
        :param path: 要访问的路径，可以是点分字符串或列表/元组
        :param default: 路径不存在时返回的默认�?        """
        self.data = data
        self.path = self._normalize_path(path)
        self.default = default
        self.value = KeyNotFound
    
    def __enter__(self) -> Any:
        """进入上下文时获取路径�?""
        try:
            self.value = get_from_dict(
                self.data, 
                self.path, 
                KeyNotFound  # 内部使用哨兵�?            )
            
            if self.value is KeyNotFound:
                self.value = self.default
        except (KeyError, IndexError, TypeError):
            self.value = self.default
        
        return self.value
    
    def __exit__(
        self, 
        exc_type: Optional[Type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> bool:
        """退出上下文时不处理异常"""
        return False
    
    @staticmethod
    def _normalize_path(path: Union[str, List[Any], Tuple[Any]]) -> List[Any]:
        """将路径统一转换为列表形�?""
        if isinstance(path, str):
            # 安全处理点分路径
            return path.split('.') if path.strip() else []
        return convert_to_list(path)

def convert_to_list(
    input_seq: Union[Any, List[Any], Tuple[Any]]
) -> List[Any]:
    """
    将输入转换为列表
    
    >>> convert_to_list('key')
    ['key']
    
    >>> convert_to_list(['a', 'b'])
    ['a', 'b']
    
    >>> convert_to_list(('c', 'd'))
    ['c', 'd']
    
    >>> convert_to_list(None)
    [None]
    
    :param input_seq: 输入值，可以是单个值或序列
    :return: 列表形式的�?    """
    if input_seq is None:
        return [None]
    if isinstance(input_seq, (list, tuple)):
        return list(input_seq)
    return [input_seq]

def get_from_dict(
    data_map: Dict[Any, Any], 
    key_path: Union[Any, List[Any], Tuple[Any]], 
    default_value: Any = KeyNotFound
) -> Any:
    """
    从深度嵌套字典中安全提取�?    
    >>> config = {'a': {'b': {'c': 42}}}
    >>> get_from_dict(config, ['a', 'b', 'c'])
    42
    
    >>> get_from_dict(config, 'a.b.c', default=0)
    42
    
    >>> get_from_dict(config, ['x'], default=None) is None
    True
    
    :param data_map: 目标嵌套字典
    :param key_path: 键路径，可以是单个值、列表或点分字符�?    :param default_value: 路径缺失时的默认返回�?    :return: 路径查找结果或默认�?    """
    normalized_path = convert_to_list(key_path)
    
    # 空路径检�?    if not normalized_path:
        return data_map if data_map is not None else default_value
    
    current_value = data_map
    
    # 遍历嵌套结构
    for key in normalized_path:
        if isinstance(current_value, dict) and key in current_value:
            current_value = current_value[key]
        elif isinstance(current_value, list) and isinstance(key, int) and 0 <= key < len(current_value):
            current_value = current_value[key]
        else:
            return default_value
    
    return current_value

# ------------------- 高级访问函数�?-------------------
def dict_get(
    data: Dict[Any, Any], 
    path: Union[str, List[Any]], 
    default: Any = None, 
    *,
    auto_create: bool = False,
    path_separator: str = '.'
) -> Any:
    """
    带自动创建能力的增强型路径获�?    
    >>> config = {}
    >>> dict_get(config, 'a.b.c', auto_create=True)
    {}
    >>> config
    {'a': {'b': {'c': {}}}}
    
    :param data: 根字�?    :param path: 点分路径或列�?    :param default: 默认返回�?    :param auto_create: 是否自动创建缺失路径
    :param path_separator: 路径分隔�?    :return: 路径末端的�?    """
    keys = path.split(path_separator) if isinstance(path, str) else path
    
    current = data
    for idx, key in enumerate(keys):
        is_last = idx == len(keys) - 1
        
        # 自动创建缺失路径
        if auto_create and key not in current:
            current[key] = {} if not is_last else default
        
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current

def dict_set(
    data: Dict[Any, Any], 
    path: Union[str, List[Any]], 
    value: Any,
    *,
    path_separator: str = '.'
) -> None:
    """
    安全设置字典路径�?    
    >>> config = {}
    >>> dict_set(config, 'a.b.c', 42)
    >>> config['a']['b']['c']
    42
    
    :param data: 根字�?    :param path: 点分路径或列�?    :param value: 要设置的�?    :param path_separator: 路径分隔�?    """
    keys = path.split(path_separator) if isinstance(path, str) else path
    
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value

def dict_delete(
    data: Dict[Any, Any], 
    path: Union[str, List[Any]],
    *,
    path_separator: str = '.'
) -> bool:
    """
    安全删除字典路径
    
    >>> config = {'a': {'b': {'c': 42}}}
    >>> dict_delete(config, 'a.b.c')
    True
    >>> config
    {'a': {'b': {}}}
    
    :param data: 根字�?    :param path: 点分路径或列�?    :param path_separator: 路径分隔�?    :return: 是否成功删除
    """
    keys = path.split(path_separator) if isinstance(path, str) else path
    
    if not keys:
        return False
    
    current = data
    # 遍历至末端键的父节点
    for key in keys[:-1]:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    
    last_key = keys[-1]
    if last_key in current:
        del current[last_key]
        return True
    
    return False

# ------------------- 使用示例 -------------------
if __name__ == "__main__":
    # 复杂配置示例
    app_config = {
        "database": {
            "postgres": {
                "host": "db-server.domain.com",
                "port": 5432,
                "credentials": {
                    "username": "admin",
                    "password": "secret"
                }
            },
            "redis": {
                "host": "redis-cache.domain.com"
            }
        },
        "logging": {
            "level": "DEBUG"
        }
    }
    
    # 示例1: 安全路径访问
    with DictPathAccessor(app_config, "database.postgres.credentials.password", "") as password:
        print(f"PostgreSQL Password: {password if password else '<N/A>'}")  # secret
    
    # 示例2: 带默认值访�?    access_key = get_from_dict(
        app_config, 
        ["database", "s3", "access_key"], 
        default_value="default-key"
    )
    print(f"S3 Access Key: {access_key}")  # default-key
    
    # 示例3: 使用dict_get自动创建缺失路径
    dict_get(app_config, "monitoring.enabled", False, auto_create=True)
    print("Monitoring path created:", 
          get_from_dict(app_config, "monitoring.enabled") == False)  # True
    
    # 示例4: 使用dict_set设置�?    dict_set(app_config, "logging.file_path", "/var/log/app.log")
    print("Log file path set:", get_from_dict(app_config, "logging.file_path"))  # /var/log/app.log
    
    # 示例5: 使用dict_delete删除敏感数据
    dict_delete(app_config, "database.postgres.credentials.password")
    print("Password removed:", 
          "password" not in app_config["database"]["postgres"]["credentials"])  # True
