#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import re
import fnmatch
from typing import Dict, List, Tuple, Set, Optional, Pattern, Union
from resource_management.core.logger import Logger


class PackageNotFoundError(Exception):
    """当找不到包时抛出的异常"""
    def __init__(self, package_name):
        super().__init__(f"Package not found: {package_name}")
        self.package_name = package_name


class RepositoryError(Exception):
    """仓库相关错误"""
    pass


class DependencyError(Exception):
    """依赖关系错误"""
    pass


class GenericManagerProperties(object):
    """
    包管理器通用属性配置（优化版）
    - 添加类型注解
    - 支持扩展属性
    - 支持默认值配置
    """
    
    # 文件系统配置
    empty_file: str = "/dev/null"
    repo_definition_location: str = "/etc/repos.d"  # 默认仓库路径
    
    # 错误模式识别
    locked_output: Optional[str] = None
    repo_error: Optional[Tuple[str]] = None
    
    # 包管理器命令路径
    repo_manager_bin: str = "/usr/bin/package-manager"
    pkg_manager_bin: str = "/usr/bin/rpm"
    
    # 仓库维护命令
    repo_update_cmd: List[str] = [repo_manager_bin, "clean"]
    repo_refresh_cmd: List[str] = [repo_manager_bin, "refresh"]
    
    # 包查询命令
    available_packages_cmd: List[str] = [repo_manager_bin, "list", "available"]
    installed_packages_cmd: List[str] = [repo_manager_bin, "list", "installed"]
    all_packages_cmd: List[str] = [repo_manager_bin, "list", "all"]
    
    # 包操作命令
    install_cmd: Dict[bool, List[str]] = {
        True: [repo_manager_bin, "-y", "install"],
        False: [repo_manager_bin, "-q", "-y", "install"]
    }
    
    upgrade_cmd: Dict[bool, List[str]] = {
        True: [repo_manager_bin, "-y", "upgrade"],
        False: [repo_manager_bin, "-q", "-y", "upgrade"]
    }
    
    remove_cmd: Dict[bool, List[str]] = {
        True: [repo_manager_bin, "-y", "remove"],
        False: [repo_manager_bin, "-q", "-y", "remove"]
    }
    
    # 依赖验证
    verify_dependency_cmd: List[str] = [repo_manager_bin, "verify"]
    
    # 缓存配置
    cache_enabled: bool = True
    cache_expire: int = 3600  # 缓存过期时间(秒)
    
    # 时间控制
    command_timeout: int = 300  # 默认命令超时时间(秒)
    
    def __init__(self):
        """允许子类动态扩展属性"""
        pass


class GenericManager(object):
    """
    通用包管理器接口（优化版）
    - 新增方法签名类型注解
    - 增强错误处理机制
    - 添加扩展点（hook）
    - 优化包管理操作流
    """
    
    def __init__(self):
        self._cache: Dict[str, Tuple[float, object]] = {}
        self.properties = GenericManagerProperties()
    
    def refresh_repositories(self) -> bool:
        """
        刷新仓库缓存
        返回是否成功
        """
        raise NotImplementedError()
    
    def install_package(
        self, 
        name: str,
        context: Optional[object] = None,
        version: Optional[str] = None
    ) -> bool:
        """
        安装指定版本的包
        :param name: 包名
        :param context: 执行上下文（可选）
        :param version: 指定版本（可选）
        :return: 是否安装成功
        :raises PackageNotFoundError: 当包不存在时
        """
        raise NotImplementedError()
    
    def upgrade_package(
        self,
        name: str,
        context: Optional[object] = None
    ) -> bool:
        """
        升级包到最新版本
        :param name: 包名
        :param context: 执行上下文（可选）
        :return: 是否升级成功
        """
        raise NotImplementedError()
    
    def remove_package(
        self,
        name: str,
        context: Optional[object] = None,
        ignore_dependencies: bool = False
    ) -> bool:
        """
        移除包
        :param name: 包名
        :param context: 执行上下文（可选）
        :param ignore_dependencies: 是否忽略依赖
        :return: 是否移除成功
        """
        raise NotImplementedError()
    
    def ensure_package(
        self,
        name: str,
        version: Optional[str] = None,
        context: Optional[object] = None
    ) -> bool:
        """
        确保包已安装且符合版本要求
        :param name: 包名
        :param version: 期望的版本规范（如 ">=1.0.0"）
        :param context: 执行上下文（可选）
        :return: 是否符合要求
        """
        installed_version = self.get_installed_package_version(name)
        if not installed_version:
            return self.install_package(name, context=context, version=version)
            
        if version and not self._check_version(installed_version, version):
            return self.upgrade_package(name, context=context)
            
        return True
    
    def check_uncompleted_transactions(self) -> bool:
        """
        检查未完成的事务
        :return: 是否存在未完成事务
        """
        return False
    
    def fix_transaction_issues(self) -> bool:
        """
        自动修复事务问题
        :return: 是否修复成功
        """
        raise NotImplementedError()
    
    def get_available_packages_in_repos(self, repositories: List[str]) -> Set[str]:
        """
        获取仓库中所有可用包
        :param repositories: 仓库ID列表
        :return: 可用包名的集合
        """
        raise NotImplementedError()
    
    def installed_packages(
        self,
        pkg_names: Optional[List[str]] = None,
        repo_filter: Optional[str] = None
    ) -> List[Tuple[str, str, str]]:
        """
        获取已安装的包列表
        :param pkg_names: 包名过滤器（可选）
        :param repo_filter: 仓库过滤器（可选）
        :return: 三元组列表（包名, 版本, 仓库）
        """
        raise NotImplementedError()
    
    def available_packages(
        self,
        pkg_names: Optional[List[str]] = None,
        repo_filter: Optional[str] = None
    ) -> List[Tuple[str, str, str]]:
        """
        获取可用的包列表
        :param pkg_names: 包名过滤器（可选）
        :param repo_filter: 仓库过滤器（可选）
        :return: 三元组列表（包名, 版本, 仓库）
        """
        raise NotImplementedError()
    
    def all_packages(
        self,
        pkg_names: Optional[List[str]] = None,
        repo_filter: Optional[str] = None
    ) -> List[Tuple[str, str, str]]:
        """
        获取所有包列表（安装和未安装）
        :param pkg_names: 包名过滤器（可选）
        :param repo_filter: 仓库过滤器（可选）
        :return: 三元组列表（包名, 版本, 仓库）
        """
        raise NotImplementedError()
    
    def find_repos_by_pattern(self, hint_packages: List[str]) -> Set[str]:
        """
        通过包名模式找到相关仓库
        :param hint_packages: 包名模式列表（支持正则）
        :return: 仓库名称集合
        """
        all_packages = self.all_packages()
        repos = set()
        
        for pattern in hint_packages:
            regex = re.compile(pattern)
            for name, _, repo in all_packages:
                if regex.match(name):
                    repos.add(repo)
                    
        return repos
    
    def filter_repositories(
        self,
        repositories: Set[str],
        include_patterns: List[str] = (),
        exclude_patterns: List[str] = ()
    ) -> List[str]:
        """
        过滤仓库列表
        :param repositories: 仓库名称集合
        :param include_patterns: 包含模式列表
        :param exclude_patterns: 排除模式列表
        :return: 过滤后的仓库列表
        """
        def matches_any_pattern(name, patterns):
            return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)
            
        result = []
        for repo in repositories:
            # 首先检查包含模式
            if include_patterns and not matches_any_pattern(repo, include_patterns):
                continue
            
            # 然后检查排除模式
            if exclude_patterns and matches_any_pattern(repo, exclude_patterns):
                continue
                
            result.append(repo)
            
        return sorted(result)
    
    def get_packages_by_repos(
        self,
        repos: List[str],
        exclude_pkgs: List[str] = (),
        only_installed: bool = True
    ) -> List[str]:
        """
        获取仓库中的包
        :param repos: 仓库列表
        :param exclude_pkgs: 排除的包模式
        :param only_installed: 是否只返回已安装的包
        :return: 包名列表
        """
        packages = []
        # 组合所有仓库的包
        for repo in repos:
            pkgs = (
                self.installed_packages(repo_filter=repo) 
                if only_installed 
                else self.all_packages(repo_filter=repo)
            )
            packages += [pkg[0] for pkg in pkgs]
        
        # 去除重复
        unique_pkgs = list(set(packages))
        
        # 过滤排除包
        exclude_patterns = [re.compile(pattern) for pattern in exclude_pkgs]
        return [
            pkg for pkg in unique_pkgs
            if not any(pattern.match(pkg) for pattern in exclude_patterns)
        ]
    
    def get_package_details(self, packages: List[str]) -> List[Dict]:
        """
        获取包详细信息
        :param packages: 包名列表
        :return: 包信息字典列表
        """
        all_installed = self.installed_packages()
        details = []
        
        # 创建快速查找映射
        pkg_map = {}
        for name, version, repo in all_installed:
            # 支持多个版本的情况
            if name not in pkg_map:
                pkg_map[name] = {'name': name, 'versions': []}
            pkg_map[name]['versions'].append({
                'version': version,
                'repo_name': repo
            })
        
        # 构建结果
        for pkg in packages:
            if pkg in pkg_map:
                details.append({
                    'name': pkg,
                    'available_versions': pkg_map[pkg]['versions']
                })
        
        return details
    
    def get_installed_package_version(self, package_name: str) -> Optional[str]:
        """
        获取已安装包的版本
        :param package_name: 包名
        :return: 版本号（或None）
        """
        result = self.installed_packages(pkg_names=[package_name])
        return result[0][1] if result else None
    
    def verify_dependencies(self) -> bool:
        """
        验证依赖关系
        :return: 依赖关系是否正常
        """
        raise NotImplementedError()
    
    def check_system_health(self) -> bool:
        """
        检查系统健康状态
        :return: 系统是否健康
        """
        # 1. 检查未完成事务
        if self.check_uncompleted_transactions():
            return False
            
        # 2. 验证依赖关系
        if not self.verify_dependencies():
            return False
            
        # 3. 检查包管理器锁定状态等
        # ...
        
        return True
    
    def _check_version(self, installed_version: str, required_version: str) -> bool:
        """
        检查版本是否符合要求
        :param installed_version: 已安装版本
        :param required_version: 需要的版本规范
        :return: 是否符合
        """
        # 简单实现，实际应该使用语义化版本比较
        return installed_version in required_version
    
    def _executor_error_handler(self, command, error_log, exit_code):
        """
        错误处理器抽象方法
        """
        Logger.error(
            f'Command execution error: command = "{command}", '
            f'exit code = {exit_code}, stderr = {error_log}'
        )
    
    # 缓存管理方法
    def _get_cached(self, key: str) -> Optional[object]:
        """获取缓存结果"""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.properties.cache_expire:
                return value
        return None
    
    def _set_cache(self, key: str, value: object) -> None:
        """设置缓存值"""
        self._cache[key] = (time.time(), value)
    
    def _clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()


class RepositoryMetadata:
    """
    仓库元数据对象
    - 统一仓库信息表示
    - 支持多仓库操作
    """
    
    def __init__(self, repo_id: str, base_url: Optional[str] = None, mirrors: List[str] = None):
        self.repo_id = repo_id
        self.base_url = base_url
        self.mirrors = mirrors or []
        self.enabled = True
        self.priority = 99
        self.gpg_check = True
        
    def to_config_string(self) -> str:
        """生成仓库配置字符串"""
        config = f"[{self.repo_id}]\n"
        config += f"name={self.repo_id}\n"
        if self.base_url:
            config += f"baseurl={self.base_url}\n"
        if self.mirrors:
            config += f"mirrorlist={','.join(self.mirrors)}\n"
        config += f"enabled={'1' if self.enabled else '0'}\n"
        config += f"gpgcheck={'1' if self.gpg_check else '0'}\n"
        config += f"priority={self.priority}\n"
        return config
        
    def save_to_disk(self, repo_dir: str) -> bool:
        """保存仓库配置到磁盘"""
        repo_file = os.path.join(repo_dir, f"{self.repo_id}.repo")
        try:
            with open(repo_file, 'w') as f:
                f.write(self.to_config_string())
            return True
        except IOError as e:
            Logger.error(f"Failed to save repository {self.repo_id}: {str(e)}")
            return False


# 辅助工具函数
def version_compare(v1: str, v2: str) -> int:
    """
    语义化版本比较函数
    :param v1: 版本字符串1
    :param v2: 版本字符串2
    :return: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
    """
    # 实现略 (可用 packaging.version.parse 或自定义实现)
    return 1


def normalize_package_name(name: str) -> str:
    """
    标准化包名
    """
    return name.strip().lower().replace('_', '-')
