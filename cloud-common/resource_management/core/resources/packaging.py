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

__all__ = ["Package"]

from typing import Optional, Dict, List, Any, Union, TYPE_CHECKING
from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
from resource_management.core.logger import Logger

# 类型检�?if TYPE_CHECKING:
    from resource_management.core.environment import Environment

# 常量定义
DEFAULT_PACKAGE_ACTION = "install"
DEFAULT_RETRY_COUNT = 4
DEFAULT_RETRY_SLEEP = 30  # �?DEFAULT_BUILD_VARS: List[str] = []

# 日志级别常量
LOGOUTPUT_INFO = True
LOGOUTPUT_DISABLED = False
LOGOUTPUT_DEBUG = None


class Package(Resource):
    """
    软件包管理资源类
    
    支持跨平台软件包管理，自动适配底层包管理器（APT/YUM/Zypper）�?    
    核心属性：
        package_name: 软件包名称（默认使用资源名称�?        location: 安装源位置（URL、路径或包名�?        version: 要安装的特定版本（如 "1.2.3-1"�?        use_repos: 仓库白名单（字典：repo_id => repo_file�?        skip_repos: 仓库黑名单（�?YUM 支持�?        logoutput: 日志输出级别控制
        
    重试机制�?        retry_count: 重试总次数（默认 4 次）
        retry_sleep: 重试间隔（默�?30 秒）
        retry_on_repo_unavailability: 仓库不可用时是否重试
        retry_on_locked: 包管理器锁定时是否重�?        
    高级功能�?        build_vars: 源码编译时的编译变量（如 ["--prefix=/usr/local"]�?    
    支持动作�?        install: 安装软件包（默认�?        upgrade: 升级软件包（保留配置�?        remove: 卸载软件包（保留配置�?        
    平台差异�?        APT: 需要仓库文件名，支持锁重试
        YUM: 支持 repo_id 过滤，内置锁重试
        Zypper: 支持锁重试，仓库不可用重�?    
    安全特性：
        重试机制防止因瞬时网�?锁定问题失败
        skip_repos 避免使用不可信仓�?        version 锁定确保环境一致�?    """
    
    action = ForcedListArgument(default=DEFAULT_PACKAGE_ACTION)
    package_name = ResourceArgument(default=lambda obj: obj.name)
    location = ResourceArgument(default=lambda obj: obj.package_name)
    
    # 仓库管理
    use_repos = ResourceArgument(default={})  # repo_id => repo_file
    skip_repos = ResourceArgument(default=[])  # YUM 专用
    
    # 日志控制
    logoutput = ResourceArgument(default=LOGOUTPUT_DEBUG)
    
    # 重试策略
    retry_count = ResourceArgument(default=DEFAULT_RETRY_COUNT)
    retry_sleep = ResourceArgument(default=DEFAULT_RETRY_SLEEP)
    retry_on_repo_unavailability = BooleanArgument(default=False)
    retry_on_locked = BooleanArgument(default=True)
    
    # 版本与源�?    version = ResourceArgument()
    build_vars = ForcedListArgument(default=DEFAULT_BUILD_VARS)
    
    actions = ["install", "upgrade", "remove"]
    
    def __init__(self, name: str, **kwargs: Any) -> None:
        Logger.info(f"创建 Package 资源: {name}")
        
        # 解析包名和版�?        package_name = kwargs.get('package_name', name)
        version = kwargs.get('version')
        
        if version:
            Logger.info(f"安装�? {package_name}-{version}")
        else:
            Logger.info(f"安装�? {package_name}（最新版本）")
        
        # 记录仓库策略
        use_repos = kwargs.get('use_repos', {})
        if use_repos:
            Logger.debug(f"使用仓库: {list(use_repos.keys())}")
        
        skip_repos = kwargs.get('skip_repos', [])
        if skip_repos:
            Logger.debug(f"跳过仓库: {skip_repos}")
        
        # 记录重试策略
        retry_count = kwargs.get('retry_count', DEFAULT_RETRY_COUNT)
        retry_on_locked = kwargs.get('retry_on_locked', True)
        if retry_on_locked:
            Logger.debug(f"启用锁定重试: {retry_count} �?)
        
        super().__init__(name, **kwargs)


# ===== 软件包管理辅助函�?=====

def install_package(
    env: 'Environment',
    package_name: str,
    version: Optional[str] = None,
    **kwargs: Any
) -> Package:
    """
    快速安装软件包的辅助函�?    
    Args:
        env: 资源环境
        package_name: 软件包名�?        version: 版本号（可选）
        **kwargs: Package 的其他属�?        
    Returns:
        Package 实例
        
    示例�?        install_package(env, "nginx")
        install_package(env, "python3", version="3.9.5-1")
        install_package(env, "git", use_repos={"epel": "epel.repo"})
    """
    Logger.info(f"快速安装软件包: {package_name}")
    
    pkg = Package(
        package_name,
        version=version,
        action="install",
        **kwargs
    )
    env.add_resource(pkg)
    return pkg


def upgrade_package(
    env: 'Environment',
    package_name: str,
    **kwargs: Any
) -> Package:
    """
    快速升级软件包的辅助函�?    
    Args:
        env: 资源环境
        package_name: 软件包名�?        **kwargs: Package 的其他属�?        
    Returns:
        Package 实例
    """
    Logger.info(f"快速升级软件包: {package_name}")
    
    pkg = Package(
        package_name,
        action="upgrade",
        **kwargs
    )
    env.add_resource(pkg)
    return pkg


def remove_package(
    env: 'Environment',
    package_name: str,
    **kwargs: Any
) -> Package:
    """
    快速卸载软件包的辅助函�?    
    Args:
        env: 资源环境
        package_name: 软件包名�?        **kwargs: Package 的其他属�?        
    Returns:
        Package 实例
    """
    Logger.info(f"快速卸载软件包: {package_name}")
    
    pkg = Package(
        package_name,
        action="remove",
        **kwargs
    )
    env.add_resource(pkg)
    return pkg


def install_packages(
    env: 'Environment',
    packages: List[str],
    **kwargs: Any
) -> List[Package]:
    """
    批量安装多个软件�?    
    Args:
        env: 资源环境
        packages: 软件包名称列�?        **kwargs: 公共�?Package 属�?        
    Returns:
        Package 实例列表
        
    示例�?        install_packages(env, ["nginx", "mysql", "php"], use_repos={"epel": "epel.repo"})
    """
    Logger.info(f"批量安装 {len(packages)} 个软件包")
    
    installed = []
    for pkg_name in packages:
        pkg = install_package(env, pkg_name, **kwargs)
        installed.append(pkg)
    
    return installed

