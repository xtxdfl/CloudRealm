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
"""

import os
import re
import tempfile
import shutil
from contextlib import contextmanager
from typing import List, Dict, Optional, Generator, Tuple, Any

from cloud_commons.constants import cloud_SUDO_BINARY
from cloud_commons import shell
from resource_management.core import sudo
from resource_management.core.logger import Logger

from .generic_manager import GenericManager, GenericManagerProperties
from .apt_parser import AptParser, PackageInfo, transform_baseurl_to_repoid

APT_LOG_PREFIX = "[APT Manager]"


class AptManagerProperties(GenericManagerProperties):
    """
    APT包管理器属性配置（优化版）
    - 增强缓存配置
    - 添加超时控制
    - 分离环境变量配置
    """
    
    # 错误模式识别
    locked_output = "Unable to lock the administration directory"
    repo_error = "Failure when receiving data from the peer"

    # 核心二进制路�?    repo_manager_bin: str = "/usr/bin/apt-get"
    repo_cache_bin: str = "/usr/bin/apt-cache"
    pkg_manager_bin: str = "/usr/bin/dpkg"
    
    # 操作命令
    repo_update_cmd: List[str] = [repo_manager_bin, "update", "-qq"]
    repo_cleanup_cmd: List[str] = [repo_manager_bin, "clean", "--quiet"]
    
    # 包查询命令（优化性能�?    available_packages_cmd: List[str] = [
        repo_cache_bin, "dump", "--no-pre-depends", "--no-recommends"
    ]
    installed_packages_cmd: List[str] = [
        pkg_manager_bin, "-l", "--no-pager", "--status"
    ]
    
    # 仓库定义路径
    repo_definition_location: str = "/etc/apt/sources.list.d"
    
    # 包操作命令（优化参数�?    install_cmd: Dict[bool, List[str]] = {
        True: [
            repo_manager_bin,
            "-o", "Dpkg::Options::=--force-confdef",
            "--allow-unauthenticated",
            "--yes",  # 更直观的选项
            "install"
        ],
        False: [
            repo_manager_bin,
            "-qq",  # 更严格的静默模式
            "-o", "Dpkg::Options::=--force-confdef",
            "--allow-unauthenticated",
            "--yes",
            "install"
        ],
    }

    remove_cmd: Dict[bool, List[str]] = {
        True: [repo_manager_bin, "--yes", "remove"],
        False: [repo_manager_bin, "--yes", "-qq", "remove"],
    }
    
    upgrade_cmd: Dict[bool, List[str]] = {
        True: [repo_manager_bin, "--yes", "upgrade"],
        False: [repo_manager_bin, "--yes", "-qq", "upgrade"],
    }

    verify_dependency_cmd: List[str] = [
        repo_manager_bin, "-qq", "check"
    ]

    # 环境变量配置
    install_cmd_env: Dict[str, str] = {
        "DEBIAN_FRONTEND": "noninteractive",
        "APT_LISTCHANGES_FRONTEND": "none"
    }
    
    # 过滤规则
    repo_url_exclude: str = "ubuntu.com"
    
    # 配置操作命令
    configuration_dump_cmd: List[str] = [cloud_SUDO_BINARY, "apt-config", "dump"]
    
    # 性能与可靠性配�?    command_timeout: int = 300             # 命令执行超时（秒�?    auto_clean: bool = True                # 自动清理临时资源
    cache_ttl: int = 3600                  # 缓存有效期（秒）
    retry_count: int = 3                   # 重试次数
    retry_delay: int = 5                   # 重试间隔（秒�?

class AptRepositoryContext:
    """APT仓库上下文管理器，用于安全处理临时仓库配�?""
    
    def __init__(self, manager, repos: Optional[List[str]] = None):
        self.manager = manager
        self.repos = repos or []
        self.temp_dir = None
        self.copied_files = []
    
    def __enter__(self):
        if not self.repos:
            return self
            
        properties = self.manager.properties
        self.temp_dir = tempfile.mkdtemp(suffix="-cloud-apt-sources.d")
        Logger.info(f"{APT_LOG_PREFIX} 创建临时仓库目录: {self.temp_dir}")
        
        # 复制必要的仓库文�?        for repo in self.repos:
            source_file = os.path.join(properties.repo_definition_location, repo + ".list")
            dest_file = os.path.join(self.temp_dir, repo + ".list")
            
            if os.path.exists(source_file):
                sudo.copy(source_file, dest_file)
                self.copied_files.append(dest_file)
                Logger.info(f"{APT_LOG_PREFIX} 复制仓库配置: {source_file} -> {dest_file}")
            else:
                Logger.warning(f"{APT_LOG_PREFIX} 仓库文件不存�? {source_file}")
                
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.temp_dir:
            return
            
        # 清理临时文件
        if self.manager.properties.auto_clean:
            try:
                for file_path in self.copied_files:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        Logger.debug(f"{APT_LOG_PREFIX} 清理临时文件: {file_path}")
                
                if os.path.exists(self.temp_dir):
                    os.rmdir(self.temp_dir)
                    Logger.info(f"{APT_LOG_PREFIX} 清理临时目录: {self.temp_dir}")
            except Exception as e:
                Logger.error(f"{APT_LOG_PREFIX} 清理失败: {str(e)}")
        else:
            Logger.warning(f"{APT_LOG_PREFIX} 保留临时文件�? {self.temp_dir}")


class AptManager(GenericManager):
    """优化后的APT包管理器，支持高级包操作和仓库管�?""
    
    def __init__(self):
        super().__init__()
        self.pkg_cache: Dict[str, PackageInfo] = {}
        self.cache_timestamp: float = 0.0
    
    @property
    def properties(self) -> AptManagerProperties:
        return AptManagerProperties

    def get_installed_package_version(self, package_name: str) -> Optional[str]:
        """
        获取已安装包的版本（优化性能�?        :param package_name: 包名
        :return: 版本号（�?"1.0.0-1"）或 None
        """
        cmd = ["dpkg-query", "-W", "--showformat=${Version}", package_name]
        result = shell.subprocess_executor(
            cmd, 
            timeout=10,
            max_retries=self.properties.retry_count,
            retry_delay=self.properties.retry_delay
        )
        if result.success and result.out.strip():
            return result.out.strip()
        return None

    def _refresh_package_cache(self, force: bool = False) -> None:
        """
        刷新包缓存（只在需要时更新�?        :param force: 是否强制刷新
        """
        current_time = time.time()
        if force or (current_time - self.cache_timestamp) > self.properties.cache_ttl:
            Logger.debug(f"{APT_LOG_PREFIX} 刷新包缓�?)
            self.pkg_cache = {
                pkg.name: pkg for pkg in self._available_packages()
            }
            self.cache_timestamp = current_time

    def _available_packages(self, filter_func=None) -> Generator[PackageInfo, None, None]:
        """
        高效获取可用包列表（支持过滤�?        :param filter_func: 过滤函数（可选）
        """
        with shell.process_executor(
            self.properties.available_packages_cmd,
            error_callback=self._executor_error_handler,
            timeout=self.properties.command_timeout,
            strategy=shell.ReaderStrategy.BufferedChunks,
        ) as output:
            for pkg in AptParser.packages_reader(output):
                # 过滤特定URL
                if self.properties.repo_url_exclude in pkg.repo_url:
                    continue
                    
                # 应用自定义过�?                if filter_func and not filter_func(pkg):
                    continue
                    
                yield pkg

    def installed_packages(
        self, 
        pkg_names: Optional[List[str]] = None, 
        repo_filter: Optional[str] = None
    ) -> List[PackageInfo]:
        """
        获取已安装包列表（优化算法）
        :param pkg_names: 包名列表（可选过滤器�?        :param repo_filter: 仓库过滤器（可选）
        :return: 包信息对象列�?        """
        # 优先使用缓存
        self._refresh_package_cache()
        
        # 收集所有已安装�?        installed = []
        installed_names = set()
        
        with shell.process_executor(
            self.properties.installed_packages_cmd,
            error_callback=self._executor_error_handler,
            timeout=self.properties.command_timeout,
            strategy=shell.ReaderStrategy.BufferedChunks,
        ) as output:
            for pkg_info in AptParser.packages_installed_reader(output):
                # 应用包名过滤
                if pkg_names and pkg_info.name not in pkg_names:
                    continue
                    
                # 尝试从缓存获取仓库信�?                if pkg_info.name in self.pkg_cache:
                    full_info = self.pkg_cache[pkg_info.name]
                    pkg_info.repo_url = full_info.repo_url
                else:
                    pkg_info.repo_url = "unknown"
                
                # 应用仓库过滤
                if repo_filter and repo_filter not in pkg_info.repo_url:
                    continue
                    
                installed.append(pkg_info)
                installed_names.add(pkg_info.name)
        
        # 处理未缓存的�?        if pkg_names:
            missing_names = set(pkg_names) - installed_names
            for name in missing_names:
                installed.append(PackageInfo(
                    name=name,
                    version="unknown",
                    repo_url="unavailable",
                    repo_name="installed"
                ))
        
        return installed

    def get_available_packages_in_repos(self, repositories: Any) -> List[str]:
        """
        获取仓库中的包列表（使用高效转换�?        :param repositories: 仓库配置对象
        :return: 包名列表
        """
        self._refresh_package_cache()
        
        # 转换仓库URL为ID
        repo_ids = [transform_baseurl_to_repoid(r.base_url) for r in repositories.items]
        
        if repositories.feat.scoped:
            Logger.info(
                f"{APT_LOG_PREFIX} 在指定仓库中搜索�? {', '.join(repo_ids)}"
            )
        else:
            Logger.info(
                f"{APT_LOG_PREFIX} 在所有可用仓库中搜索�?
            )
        
        # 定义仓库过滤函数
        def repo_filter(pkg):
            if repositories.feat.scoped:
                return any(repo_id in pkg.repo_url for repo_id in repo_ids)
            return True
        
        # 收集匹配的包
        package_names = []
        for pkg in self._available_packages(filter_func=repo_filter):
            package_names.append(pkg.name)
            
        return list(set(package_names))

    def package_manager_configuration(self) -> Dict[str, str]:
        """
        获取APT配置信息（优化解析）
        :return: 配置键值字�?        """
        config = {}
        
        with shell.process_executor(
            self.properties.configuration_dump_cmd,
            error_callback=self._executor_error_handler,
            timeout=self.properties.command_timeout
        ) as output:
            for key, value in AptParser.config_reader(output):
                config[key] = value
                
        return config

    def verify_dependencies(self) -> bool:
        """
        更可靠的依赖关系验证（支持模式识别和重试�?        :return: 依赖关系是否正常
        """
        errors = []
        
        for attempt in range(self.properties.retry_count + 1):
            result = shell.subprocess_executor(
                self.properties.verify_dependency_cmd,
                timeout=self.properties.command_timeout
            )
            
            # 无任何输出表示成�?            if result.success and not result.out.strip():
                return True
                
            # 收集所有错�?            if "has missing dependency" in result.out or "E:" in result.out:
                error_lines = [
                    line for line in result.out.splitlines()
                    if "has missing dependency" in line or line.startswith("E:")
                ]
                errors.extend(error_lines)
                
            # 最后一次尝试后中断
            if attempt < self.properties.retry_count:
                Logger.warning(
                    f"{APT_LOG_PREFIX} 依赖验证失败，{self.properties.retry_delay}秒后重试 "
                    f"({attempt+1}/{self.properties.retry_count})"
                )
                time.sleep(self.properties.retry_delay)
            else:
                break
                
        # 记录并返回错�?        if errors:
            err_msg = f"{APT_LOG_PREFIX} 发现依赖问题:\n" + "\n".join(errors)
            Logger.error(Logger.filter_text(err_msg))
            return False
            
        return True

    def _install_package(
        self, 
        action: str, 
        name: str, 
        context: Any,
        version: Optional[str] = None,
        is_upgrade: bool = False
    ) -> bool:
        """
        内部包操作实现（安装/升级�?        :param action: 操作类型 ('install' �?'upgrade')
        :param name: 包名
        :param context: 执行上下�?        :param version: 期望的版本（可选）
        :param is_upgrade: 是否升级操作
        :return: 是否成功
        """
        normalized_name = self._normalize_package_name(name)
        
        # 检查包是否已存在（除非强制�?        if action == "install" and not context.action_force:
            if self._is_package_installed(normalized_name):
                Logger.info(f"{APT_LOG_PREFIX} 跳过已安装的�? {normalized_name}")
                return True
        
        # 准备仓库上下�?        use_repos = list(context.use_repos.keys()) if context.use_repos else []
        base_repos_used = "base" in use_repos
        
        # 准备命令
        cmd_option = self.properties.upgrade_cmd if is_upgrade else self.properties.install_cmd
        cmd = cmd_option[context.log_output].copy()
        
        # 处理仓库逻辑
        with AptRepositoryContext(self, use_repos) as repo_ctx:
            # 指定临时源目�?            if repo_ctx.temp_dir:
                cmd.extend(["-o", f"Dir::Etc::SourceParts={repo_ctx.temp_dir}"])
            
            # 基本仓库处理
            if base_repos_used:
                cmd.extend(["-o", f"Dir::Etc::SourceList={self.properties.empty_file}"])
            
            # 添加包标�?            pkg_spec = f"{normalized_name}={version}" if version else normalized_name
            cmd.extend([pkg_spec] if action == "install" else [])
            
            # 执行操作
            return shell.repository_manager_executor(
                cmd, 
                self.properties, 
                context, 
                env=self.properties.install_cmd_env,
                timeout=self.properties.command_timeout,
                max_retries=self.properties.retry_count,
                retry_delay=self.properties.retry_delay
            ).success

    def install_package(self, name: str, context: Any, version: Optional[str] = None) -> bool:
        """
        安装软件包（支持指定版本�?        :param name: 包名
        :param context: 执行上下�?        :param version: 版本号（可选）
        :return: 是否成功
        """
        Logger.info(f"{APT_LOG_PREFIX} 安装�? {name}{f' (版本: {version})' if version else ''}")
        return self._install_package("install", name, context, version)

    def upgrade_package(self, name: str, context: Any) -> bool:
        """
        升级软件包（专用方法�?        :param name: 包名
        :param context: 执行上下�?        :return: 是否成功
        """
        Logger.info(f"{APT_LOG_PREFIX} 升级�? {name}")
        context.is_upgrade = True
        return self._install_package("upgrade", name, context, is_upgrade=True)

    def remove_package(self, name: str, context: Any, ignore_dependencies: bool = False) -> bool:
        """
        移除软件包（支持依赖控制�?        :param name: 包名
        :param context: 执行上下�?        :param ignore_dependencies: 是否忽略依赖
        :return: 是否成功
        """
        normalized_name = self._normalize_package_name(name)
        
        if not self._is_package_installed(normalized_name):
            Logger.info(f"{APT_LOG_PREFIX} 跳过未安装的�? {normalized_name}")
            return True
            
        # 准备命令
        cmd_option = self.properties.remove_cmd[context.log_output].copy()
        cmd = cmd_option + [normalized_name]
        
        # 自动清除选项
        cmd.extend(["--autoremove"])
        
        Logger.info(f"{APT_LOG_PREFIX} 移除�? {normalized_name}")
        
        # 执行移除
        return shell.repository_manager_executor(
            cmd, 
            self.properties, 
            context,
            timeout=self.properties.command_timeout
        ).success

    def refresh_repositories(self) -> bool:
        """
        刷新APT仓库缓存（带清理机制�?        :return: 是否成功
        """
        # 清理旧数�?        clean_result = shell.repository_manager_executor(
            self.properties.repo_cleanup_cmd,
            self.properties,
            context=None
        )
        
        # 更新仓库列表
        update_result = shell.repository_manager_executor(
            self.properties.repo_update_cmd,
            self.properties,
            context=None,
            timeout=self.properties.command_timeout * 2
        )
        
        # 刷新缓存
        if clean_result.success and update_result.success:
            self._refresh_package_cache(force=True)
            
        return clean_result.success and update_result.success

    def _normalize_package_name(self, name: str) -> str:
        """
        标准化包名称（转换下划线�?        :param name: 原始包名
        :return: 标准化包�?        """
        return name.replace("_", "-")

    def _is_package_installed(self, normalized_name: str) -> bool:
        """
        高效检查包是否安装（避免完整解析）
        :param normalized_name: 标准化包�?        :return: 是否安装
        """
        # 使用dpkg --get-selections快速检�?        cmd = ["dpkg", "--get-selections", normalized_name]
        result = shell.subprocess_executor(cmd, timeout=5)
        return result.success and "install" in result.out

    def ensure_clean_state(self) -> bool:
        """
        确保系统处于清洁状态（修复常见问题�?        :return: 是否清洁
        """
        # 1. 修复中断的包
        result = shell.repository_manager_executor([
            self.properties.repo_manager_bin, 
            "--fix-interrupt", 
            "--quiet"
        ], self.properties, None)
        
        if not result.success:
            Logger.error(f"{APT_LOG_PREFIX} 修复中断包失�? {result.stderr}")
            return False
        
        # 2. 验证依赖
        if not self.verify_dependencies():
            Logger.warning(f"{APT_LOG_PREFIX} 依赖验证失败，尝试修�?..")
            
            # 尝试自动修复依赖
            fix_result = shell.repository_manager_executor([
                self.properties.repo_manager_bin, 
                "-f", 
                "install",
                "--allow-unauthenticated",
                "-y"
            ], self.properties, None)
            
            if not fix_result.success:
                Logger.error(f"{APT_LOG_PREFIX} 自动修复依赖失败")
                return False
        
        # 3. 清理缓存
        clean_result = shell.repository_manager_executor([
            self.properties.repo_manager_bin,
            "clean",
            "-q"
        ], self.properties, None)
        
        return clean_result.success
