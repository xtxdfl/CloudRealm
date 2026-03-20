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

Advanced Component Repository Version Management System
"""

import logging
from typing import Optional, Dict, Any
from resource_management.libraries.script.script import Script
from resource_management.core.logger import Logger

__all__ = [
    "get_component_repository_version",
    "ComponentVersionNotFoundError",
    "get_all_component_versions",
    "validate_component_versions",
    "set_component_repository_version"
]

class ComponentVersionNotFoundError(ValueError):
    """找不到组件版本时引发的专用异常"""
    def __init__(self, service_name, component_name=None):
        message = f"找不到服务 '{service_name}'"
        if component_name:
            message = f"服务 '{service_name}'中找不到组件 '{component_name}' 的版本"
        super().__init__(message)
        self.service_name = service_name
        self.component_name = component_name

def validate_component_versions(versions: Dict[str, Any]) -> bool:
    """验证组件版本映射的结构有效性
    
    参数:
        versions: 要验证的版本映射字典
        
    返回:
        bool: 映射结构是否有效
        
    抛出:
        ValueError: 如果结构无效则抛出异常
    """
    if not isinstance(versions, dict):
        raise ValueError("版本映射必须是字典类型")
    
    for service, components in versions.items():
        if not isinstance(components, dict):
            raise ValueError(f"服务 '{service}' 的组件映射应为字典类型")
        
        for comp, version in components.items():
            if not isinstance(version, str):
                raise ValueError(
                    f"服务 '{service}' 的组件 '{comp}' 版本必须是字符串")
                
            if not version.strip():
                raise ValueError(
                    f"服务 '{service}' 的组件 '{comp}' 版本不能为空")
    
    Logger.debug(f"验证成功: 版本映射包含 {len(versions)} 个服务")
    return True

def get_all_component_versions(config: Optional[Dict] = None) -> Dict[str, Dict[str, str]]:
    """获取完整的组件版本映射
    
    参数:
        config: 配置字典（可选），如未提供则从脚本配置中获取
        
    返回:
        dict: 结构为 {service: {component: version}} 的完整版本映射
        
    抛出:
        ValueError: 如果版本映射不存在或无效
    """
    if config is None:
        config = Script.get_config()
    
    if not config:
        raise ValueError("配置字典不可用")
    
    versions = config.get("componentVersionMap")
    if not versions:
        raise ValueError("配置中找不到 componentVersionMap")
    
    # 验证版本映射结构
    validate_component_versions(versions)
    
    Logger.debug(f"获取到包含 {len(versions)} 个服务的组件版本映射")
    return versions

def get_component_repository_version(
    service_name: Optional[str] = None,
    component_name: Optional[str] = None,
    default_value: Optional[str] = None,
    config: Optional[Dict] = None,
    use_default_on_error: bool = True
) -> str:
    """
    获取指定组件的仓库版本
    
    增强功能：
    - 支持通过 config 参数传入配置
    - 提供专用异常类 ComponentVersionNotFoundError
    - 支持自定义错误处理（返回默认值或抛出异常）
    - 自动验证版本映射结构

    参数:
        service_name: 服务名称
        component_name: 组件名称
        default_value: 找不到版本时的默认返回值
        config: 配置字典（可选）
        use_default_on_error: 是否在出错时返回默认值（False 则抛出异常）
        
    返回:
        str: 组件版本字符串
        
    抛出:
        ComponentVersionNotFoundError: 服务/组件未找到且 use_default_on_error=False
        ValueError: 版本映射无效
    """
    try:
        # 获取完整版本映射
        versions = get_all_component_versions(config)
        
        # 自动获取服务名称（如果未提供）
        if service_name is None:
            if config is None:
                config = Script.get_config()
            service_name = config.get("serviceName")
        
        # 检查服务是否存在
        if service_name not in versions or not versions[service_name]:
            if use_default_on_error:
                return default_value
            raise ComponentVersionNotFoundError(service_name)
        
        # 获取服务组件映射
        service_versions = versions[service_name]
        
        # 自动获取组件名称（如果未提供）
        if component_name is None:
            if config is not None:
                component_name = config.get("role")
            
            # 如果仍然未指定组件，尝试使用第一个组件
            if not component_name:
                return list(service_versions.values())[0]
        
        # 直接匹配组件
        if component_name in service_versions:
            return service_versions[component_name]
        
        # 通配符匹配（如 "client" 可匹配 "client_1", "client_2"）
        if service_name and component_name:
            for comp, version in service_versions.items():
                if component_name in comp:
                    Logger.warning(
                        f"使用部分匹配: '{component_name}' 匹配 '{comp}'")
                    return version
        
        # 匹配失败处理
        if use_default_on_error:
            return default_value
        raise ComponentVersionNotFoundError(service_name, component_name)
            
    except Exception as e:
        Logger.error(f"版本获取失败: {str(e)}")
        if use_default_on_error:
            return default_value
        raise

def set_component_repository_version(
    service_name: str,
    version: str,
    component_name: Optional[str] = None,
    config: Optional[Dict] = None
):
    """
    设置或更新组件版本信息（用于测试或动态配置场景）
    
    参数:
        service_name: 服务名称
        version: 要设置的版本号
        component_name: 组件名称（可选，如未指定则应用到服务所有组件）
        config: 配置字典（可选）
    """
    # 获取现有版本映射或创建新映射
    try:
        versions = get_all_component_versions(config)
    except ValueError:
        versions = {}
    
    # 确保服务条目存在
    if service_name not in versions:
        versions[service_name] = {}
    
    # 设置特定组件或所有组件
    if component_name:
        versions[service_name][component_name] = version
        Logger.info(
            f"设置版本: 服务 '{service_name}' 组件 '{component_name}' -> {version}")
    else:
        # 更新所有组件到相同版本
        for comp in versions[service_name]:
            versions[service_name][comp] = version
        Logger.info(
            f"设置全服务版本: 服务 '{service_name}' 所有组件 -> {version}")
    
    # 更新配置中的版本映射
    if config is None:
        config = Script.get_config()
    
    config["componentVersionMap"] = versions
