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

高级堆栈设置管理器
"""

__all__ = ["StackSettings"]

import json
from typing import Any, Dict, List, Optional, Union


class StackSettings:
    # 堆栈相关配置键名常量
    STACK_NAME_KEY = "stack_name"
    STACK_VERSION_KEY = "stack_version"
    STACK_TOOLS_KEY = "stack_tools"
    STACK_FEATURES_KEY = "stack_features"
    STACK_PACKAGES_KEY = "stack_packages"
    STACK_ROOT_KEY = "stack_root"
    STACK_SELECT_KEY = "stack_select"
    USER_GROUPS_KEY = "user_groups"
    USER_LIST_KEY = "user_list"
    GROUP_LIST_KEY = "group_list"
    
    # 默认空值
    EMPTY_DICT = {}
    EMPTY_LIST = []

    def __init__(self, stack_settings: Dict[str, Any]):
        """
        初始化堆栈设置管理器
        
        :param stack_settings: 原始堆栈设置字典 (通常来自 command.json 的 cluster-env)
        """
        self._stack_settings = stack_settings or {}
        self._cached_values = {}
        self._validate_settings()

    def _validate_settings(self) -> None:
        """验证基础配置键是否存在"""
        required_keys = {
            self.STACK_NAME_KEY, 
            self.STACK_FEATURES_KEY,
            self.STACK_PACKAGES_KEY
        }
        
        missing = required_keys - set(self._stack_settings.keys())
        if missing:
            raise ValueError(f"缺少必需的堆栈配置键: {', '.join(missing)}")

    def _get_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值并使用缓存优化
        
        :param key: 配置键名
        :param default: 默认值（未找到键时返回）
        :return: 配置值或默认值
        """
        if key in self._cached_values:
            return self._cached_values[key]
            
        value = self._stack_settings.get(key, default)
        self._cached_values[key] = value
        return value

    @property
    def mpack_name(self) -> str:
        """获取管理包名称 (如 'HDPCORE')"""
        return self._get_value(self.STACK_NAME_KEY, "")

    @property
    def mpack_version(self) -> str:
        """获取管理包版本 (如 '3.1.0-b224')"""
        return self._get_value(self.STACK_VERSION_KEY, "")

    @property
    def group_list(self) -> List[str]:
        """获取用户组列表"""
        raw_groups = self._get_value(self.GROUP_LIST_KEY, "[]")
        try:
            return json.loads(raw_groups)
        except (TypeError, json.JSONDecodeError):
            return []

    @property
    def user_list(self) -> List[str]:
        """获取用户列表"""
        raw_users = self._get_value(self.USER_LIST_KEY, "[]")
        try:
            return json.loads(raw_users)
        except (TypeError, json.JSONDecodeError):
            return []

    @property
    def stack_features(self) -> Dict[str, Any]:
        """获取堆栈特性配置 (字典形式)"""
        return self._get_parsed_setting(self.STACK_FEATURES_KEY, "{}", dict)

    @property
    def stack_packages(self) -> Dict[str, Any]:
        """获取堆栈包配置 (字典形式)"""
        return self._get_parsed_setting(self.STACK_PACKAGES_KEY, "{}", dict)

    @property
    def stack_tools(self) -> Dict[str, Any]:
        """获取堆栈工具配置 (字典形式)"""
        return self._get_parsed_setting(self.STACK_TOOLS_KEY, "{}", dict)
    
    @property
    def user_groups_map(self) -> Dict[str, List[str]]:
        """获取用户组映射 (用户->组列表)"""
        return self._get_parsed_setting(self.USER_GROUPS_KEY, "{}", dict)

    def _get_parsed_setting(
        self, 
        key: str, 
        default: Union[str, dict, list], 
        result_type: type
    ) -> Union[Dict, List]:
        """
        获取并解析JSON格式的配置
        
        :param key: 配置键名
        :param default: 默认值 (字符串或对象)
        :param result_type: 期望的结果类型 (dict或list)
        :return: 解析后的配置对象
        """
        raw_value = self._get_value(key, default)
        
        # 已经是期望类型则直接返回
        if isinstance(raw_value, result_type):
            return raw_value
            
        # 解析JSON字符串
        if isinstance(raw_value, str):
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, result_type):
                    return parsed
            except json.JSONDecodeError:
                pass
                
        # 返回类型安全的默认值
        if result_type == dict:
            return self.EMPTY_DICT
        return self.EMPTY_LIST

    def has_feature(self, feature_name: str) -> bool:
        """
        检查堆栈是否支持指定特性
        
        :param feature_name: 特性名称
        :return: 是否支持该特性
        """
        return feature_name in self.stack_features.get("features", {})

    def get_service_users(self, service_name: str) -> List[str]:
        """
        获取指定服务的用户列表
        
        :param service_name: 服务名称（e.g. "ZOOKEEPER"）
        :return: 服务用户列表
        """
        service_key = f"{service_name.upper()}_USERS"
        return self.stack_features.get("users", {}).get(service_key, [])

    def get_tool(self, tool_name: str) -> Optional[Dict]:
        """
        获取指定工具配置
        
        :param tool_name: 工具名称
        :return: 工具配置字典 (name, path, etc)
        """
        return self.stack_tools.get(tool_name)

    def validate_dependencies(self, component: str) -> List[str]:
        """
        验证组件的依赖关系
        
        :param component: 组件名称
        :return: 缺失依赖列表
        """
        component_name = component.upper()
        dependency_key = f"{component_name}_DEPENDENCIES"
        dependencies = self.stack_packages["packages"].get(dependency_key, [])
        
        missing = []
        for dep in dependencies:
            if not self.is_package_available(dep):
                missing.append(dep)
                
        return missing

    def is_package_available(self, package_name: str) -> bool:
        """
        检查包是否可用
        
        :param package_name: 包名称
        :return: 包是否可用
        """
        return package_name in self.stack_packages

    @classmethod
    def from_cluster_env(cls, cluster_env_config: Dict) -> 'StackSettings':
        """
        从cluster_env配置创建StackSettings实例
        
        :param cluster_env_config: cluster-env配置字典
        :return: StackSettings实例
        """
        return cls(cluster_env_config)
