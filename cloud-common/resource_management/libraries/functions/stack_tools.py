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

Enhanced Stack Tools Manager
"""

import json
import os
import re
import sys
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any, Union
from resource_management.core.exceptions import StackToolError, ConfigurationError
from resource_management.core.logger import Logger
from resource_management.libraries.functions.default import default

__all__ = [
    "get_stack_tool", "get_stack_tool_name", "get_stack_tool_path",
    "get_stack_tool_package", "get_stack_name", "get_stack_root",
    "STACK_SELECTOR_NAME", "CONF_SELECTOR_NAME", "SYSTEM_STACK_ROOTS",
    "get_stack_tool_info", "validate_stack_tool", "resolve_stack_root"
]

# 定义常量
STACK_SELECTOR_NAME = "stack_selector"
CONF_SELECTOR_NAME = "conf_selector"

# 预定义的堆栈根目录映�?SYSTEM_STACK_ROOTS = {
    "HDP": ("/usr/hdp", "hdp-select"),
    "CDH": ("/opt/cloudera/parcels", "alternatives"),
    "cloud": ("/usr/lib/cloud-server", "cloud-server"), 
    "BIGTOP": ("/usr/lib/bigtop", "bigtop-select"),
    "MAPR": ("/opt/mapr", "mapr-selector"),
    "HDPC": ("/usr/hdpc", "hdpc-select")
}

# 堆栈工具类型定义
STACK_TOOL_TYPES = [
    STACK_SELECTOR_NAME,
    CONF_SELECTOR_NAME,
    "package_manager",
    "service_manager",
    "config_manager",
    "version_manager"
]

@lru_cache(maxsize=32)
def get_stack_tool(tool_selector: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    获取堆栈工具的完整信息（名称、路径、包名）
    
    核心特点�?    1. 自动缓存提升性能
    2. 多来源堆栈工具配置支持（集群环境、系统常量、环境变量）
    3. 丰富的错误处理和日志记录
    4. 灵活的回退机制
    
    :param tool_selector: 工具选择器名�?(e.g., 'stack_selector', 'conf_selector')
    :return: tuple (tool_name, tool_path, tool_package)
    """
    # 验证工具选择器名�?    if tool_selector not in STACK_TOOL_TYPES:
        Logger.error(f"Invalid stack tool selector: {tool_selector}. Valid types: {', '.join(STACK_TOOL_TYPES)}")
        raise ValueError(f"Invalid stack tool selector: {tool_selector}")

    try:
        # 1. 优先从集群级参数获取堆栈名称
        stack_name = get_stack_name()
        if not stack_name:
            Logger.warning("Cannot determine stack name. Stack tools cannot be loaded")
            return None, None, None

        # 2. 获取堆栈工具配置（优先使用缓存）
        stack_tools = _load_stack_tools_config()
        if not stack_tools:
            Logger.error("Stack tools configuration is missing or invalid")
            return None, None, None

        # 3. 根据堆栈名称查找工具
        if stack_name not in stack_tools:
            _warn_stack_mismatch(stack_name, list(stack_tools.keys()))
            return None, None, None

        # 4. 获取当前堆栈的工具配�?        stack_toolset = stack_tools[stack_name]
        tool_selector_key = tool_selector.lower()

        # 5. 在堆栈工具集中查找特定工�?        if not stack_toolset or tool_selector_key not in stack_toolset:
            Logger.warning(f"Cannot find config for {tool_selector} tool in stack {stack_name}")
            return None, None, None

        # 6. 解包工具配置 (名称, 路径, 包名)
        tool_config = stack_toolset[tool_selector_key]
        tool_info = tuple(pad(tool_config[:3], 3))
        
        # 7. 验证工具配置
        if validate_stack_tool(tool_selector, tool_info):
            Logger.info(f"Resolved {tool_selector} for {stack_name}: {tool_info}")
            return tool_info
        
        return None, None, None
    except json.JSONDecodeError as je:
        Logger.error(f"Invalid JSON format in stack tools config: {str(je)}")
        return None, None, None
    except Exception as e:
        Logger.exception(f"Unexpected error loading stack tool {tool_selector}: {str(e)}")
        return None, None, None

def get_stack_tool_name(tool_selector: str) -> Optional[str]:
    """获取堆栈工具的名�?""
    tool_info = get_stack_tool(tool_selector)
    return tool_info[0] if tool_info else None

def get_stack_tool_path(tool_selector: str) -> Optional[str]:
    """获取堆栈工具的路�?""
    tool_info = get_stack_tool(tool_selector)
    return tool_info[1] if tool_info else None

def get_stack_tool_package(tool_selector: str) -> Optional[str]:
    """获取堆栈工具的包�?""
    tool_info = get_stack_tool(tool_selector)
    return tool_info[2] if tool_info else None

def get_stack_tool_info(tool_selector: str) -> Dict[str, Optional[str]]:
    """获取堆栈工具的完整信息字�?""
    tool_info = get_stack_tool(tool_selector)
    if tool_info:
        return {
            "name": tool_info[0],
            "path": tool_info[1],
            "package": tool_info[2],
            "selector": tool_selector
        }
    return {
        "name": None,
        "path": None,
        "package": None,
        "selector": tool_selector
    }

@lru_cache(maxsize=8)
def get_stack_name() -> Optional[str]:
    """
    获取标准化堆栈名称，支持多种来源
    
    识别顺序�?    1. /clusterLevelParams/stack_name
    2. /commandParams/stack_name
    3. 环境变量 cloud_STACK_NAME
    4. 当前安装路径检�?    """
    try:
        # 1. 集群级参�?        stack_name = default("/clusterLevelParams/stack_name", None)
        if stack_name:
            return stack_name
        
        # 2. 命令参数
        stack_name = default("/commandParams/stack_name", None)
        if stack_name:
            return stack_name
        
        # 3. 环境变量
        stack_name = os.environ.get("cloud_STACK_NAME")
        if stack_name:
            return stack_name
        
        # 4. 自动检测（基于安装路径�?        for base_dir in ("/usr", "/opt"):
            if os.path.exists(base_dir):
                for name in os.listdir(base_dir):
                    if name.lower() in ("hdp", "hdp-select", "bigtop", "cdh"):
                        return name.upper()
        
        Logger.warning("Cannot determine stack name from configuration or environment")
        return None
        
    except Exception as e:
        Logger.error(f"Failed to determine stack name: {str(e)}")
        return None

def resolve_stack_root(stack_name: Optional[str] = None) -> str:
    """
    解析堆栈根目录，带智能回退机制
    
    :param stack_name: 堆栈名称 (可选，自动检�?
    :return: 堆栈安装根目�?    """
    if not stack_name:
        stack_name = get_stack_name()
    
    # 1. 从配置获取堆栈根目录
    stack_root_json = default("/configurations/cluster-env/stack_root", None)
    if stack_root_json:
        try:
            stack_roots = json.loads(stack_root_json) or {}
            if stack_name in stack_roots:
                return stack_roots[stack_name]
        except json.JSONDecodeError:
            Logger.error("Invalid JSON format in stack_root configuration")
    
    # 2. 检查系统默认位�?    if stack_name and stack_name in SYSTEM_STACK_ROOTS:
        return SYSTEM_STACK_ROOTS[stack_name][0]
    
    # 3. 基于堆栈名称的回退
    stack_prefix = stack_name.split("-")[0] if stack_name and "-" in stack_name else stack_name
    if stack_prefix and stack_prefix in SYSTEM_STACK_ROOTS:
        return SYSTEM_STACK_ROOTS[stack_prefix][0]
    
    # 4. 通用路径回退
    return "/usr/{0}".format(stack_name.lower() if stack_name else "unknown-stack")

def get_stack_root(stack_name: Optional[str] = None, stack_root_json: Optional[str] = None) -> str:
    """
    [兼容函数] 获取堆栈根目录，优先使用新的resolve_stack_root
    """
    return resolve_stack_root(stack_name)

def get_formatted_stack_name(raw_name: str) -> str:
    """
    从格式化的堆栈字符串中提取标准堆栈名�?    
    :param raw_name: 原始堆栈字符串（�?HDP-2.6.1.0-123'�?    :return: 标准堆栈名称（如'HDP'�?    """
    if not raw_name:
        return "UNKNOWN"
    
    # 处理版本化堆栈名�?    if "-" in raw_name:
        return raw_name.split("-")[0].upper()
    
    return raw_name.upper()

def validate_stack_tool(tool_selector: str, tool_info: Tuple) -> bool:
    """验证堆栈工具配置的完整�?""
    if not tool_info or len(tool_info) < 3:
        Logger.error(f"Incomplete configuration for {tool_selector}: {tool_info}")
        return False
    
    name, path, package = tool_info
    
    # 检查必要字�?    missing_fields = []
    if not name:
        missing_fields.append("name")
    if not path:
        missing_fields.append("path")
    if not package:
        missing_fields.append("package")
    
    if missing_fields:
        Logger.error(f"Missing required fields for {tool_selector}: {', '.join(missing_fields)}")
        return False
    
    return True

# --------------------------
# 内部工具函数
# --------------------------

def _load_stack_tools_config() -> Dict[str, Any]:
    """加载堆栈工具配置，带缓存和多来源支持"""
    try:
        # 1. 从集群环境配置获�?        stack_tools_config = default("/configurations/cluster-env/stack_tools", None)
        if stack_tools_config:
            return json.loads(stack_tools_config) or {}
        
        # 2. 从环境变量获取（开�?测试用）
        env_config = os.environ.get("cloud_STACK_TOOLS_CONFIG")
        if env_config:
            return json.loads(env_config)
        
        # 3. 生成默认配置
        return _generate_default_stack_tools()
    except json.JSONDecodeError as je:
        Logger.error(f"Invalid JSON format in stack tools config: {str(je)}")
        return {}
    except Exception as e:
        Logger.error(f"Error loading stack tools config: {str(e)}")
        return {}

def _generate_default_stack_tools() -> Dict[str, Dict]:
    """为常见堆栈生成默认工具配�?""
    default_tools = {}
    
    for stack, (root, selector_name) in SYSTEM_STACK_ROOTS.items():
        default_tools[stack] = {
            STACK_SELECTOR_NAME.lower(): [selector_name, f"{root}/bin/{selector_name}", f"{selector_name}-package"],
            CONF_SELECTOR_NAME.lower(): [f"conf_{selector_name}", f"{root}/bin/conf_{selector_name}", f"conf_{selector_name}-package"]
        }
    
    # Hadoop生态通用工具
    hadoop_tools = {
        "package_manager": ["yum", "/usr/bin/yum", "yum"],
        "service_manager": ["systemctl", "/usr/bin/systemctl", "systemd"]
    }
    
    for stack in default_tools:
        default_tools[stack].update(hadoop_tools)
    
    Logger.info(f"Generated default stack tools for stacks: {', '.join(default_tools.keys())}")
    return default_tools

def _warn_stack_mismatch(detected_stack: str, available_stacks: List[str]) -> None:
    """堆栈不匹配警告，带智能建�?""
    Logger.warning(f"Detected stack '{detected_stack}', but only {', '.join(available_stacks)} are available")
    
    # 尝试前缀匹配
    prefix = detected_stack.split("-")[0]
    if prefix != detected_stack and prefix in available_stacks:
        Logger.info(f"Using stack prefix '{prefix}' as fallback")
    
    # 相似度匹�?    best_match = None
    best_score = 0
    
    for stack in available_stacks:
        s = similarity(prefix, stack)
        if s > best_score and s > 0.6:  # 60%相似度阈�?            best_match = stack
            best_score = s
    
    if best_match:
        Logger.info(f"Did you mean '{best_match}'? (similarity: {best_score:.0%})")

def similarity(a: str, b: str) -> float:
    """计算两个字符串的相似�?0-1.0)"""
    a, b = a.lower(), b.lower()
    set_a, set_b = set(a), set(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0

# --------------------------
# 测试代码
# --------------------------

if __name__ == "__main__":
    def test_stack_tool(tool_name):
        print(f"\nTesting tool: {tool_name}")
        info = get_stack_tool_info(tool_name)
        print(f"  Name: {info['name']}")
        print(f"  Path: {info['path']}")
        print(f"  Package: {info['package']}")
    
    # 模拟测试环境
    os.environ["cloud_STACK_NAME"] = "HDP-3.1.4"
    
    print("Stack Root:", resolve_stack_root())
    
    test_stack_tool(STACK_SELECTOR_NAME)
    test_stack_tool(CONF_SELECTOR_NAME)
    test_stack_tool("package_manager")
    test_stack_tool("service_manager")
    
    print("\nStack Name Tests:")
    test_cases = ["HDP-2.6", "CDH-7.1", "cloud", "UNKNOWN"]
    for stack in test_cases:
        print(f"  Original: {stack} -> Formatted: {get_formatted_stack_name(stack)}")
