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

from .generic_manager import GenericManagerProperties, GenericManager
from .yum_parser import YumParser, PackageInfo
from cloud_commons import shell
from resource_management.core.logger import Logger
from resource_management.core import sudo

import configparser
import glob
import os
import re
import fnmatch
import time
import concurrent.futures
from io import StringIO
from typing import List, Set, Dict, Generator, Optional, Tuple, Union

# YUM 事务状态常�?class RPMTransactions:
    ALL = "all"
    DONE = "done"
    ABORTED = "aborted"

# YUM 事务项对�?class YumTransactionItem:
    __slots__ = ('transaction_id', 'pkgs_done', 'pkgs_all')
    
    def __init__(self, transaction_id: str, pkgs_done: List[str] = None, pkgs_all: List[str] = None):
        self.transaction_id = transaction_id
        self.pkgs_done = pkgs_done or []
        self.pkgs_all = pkgs_all or []

    @property
    def pkgs_aborted(self) -> List[str]:
        """返回中断事务中未完成的包列表"""
        all_set = set(self.pkgs_all)
        done_set = set(self.pkgs_done)
        return list(all_set - done_set)
        
    @property
    def is_completed(self) -> bool:
        """检查事务是否完�?""
        return set(self.pkgs_done) == set(self.pkgs_all)
        
    def __repr__(self) -> str:
        return f"<YumTransactionItem id={self.transaction_id}, done={len(self.pkgs_done)}/{len(self.pkgs_all)}>"


class YumManagerProperties(GenericManagerProperties):
    """
    YUM包管理器属性配置（优化版）
    - 新增超时控制和并发选项
    - 优化命令参数逻辑
    - 增强错误处理能力
    """
    
    locked_output = None
    repo_error = ("Failure when receiving data from the peer", "Nothing to do")
    
    # 核心命令配置
    repo_manager_bin = "/usr/bin/yum"
    pkg_manager_bin = "/usr/bin/rpm"
    
    # 仓库管理命令
    repo_update_cmd = [repo_manager_bin, "clean", "all"]
    repo_refresh_cmd = [repo_manager_bin, "makecache", "fast"]
    
    # 包查询命令模板（统一基础�?    BASE_LIST_CMD = [repo_manager_bin, "list", "--showduplicates", "-q"]
    available_packages_cmd = BASE_LIST_CMD + ["available"]
    installed_packages_cmd = BASE_LIST_CMD + ["installed"]
    all_packages_cmd = BASE_LIST_CMD + []
    
    # 文件系统路径配置
    yum_lib_dir = "/var/lib/yum"
    yum_tr_prefix = "transaction-"
    repo_definition_location = "/etc/yum.repos.d"
    cache_expire_time = 3600  # 缓存过期时间�?小时�?    
    # 包操作命令模�?    install_cmd = {
        True: [repo_manager_bin, "-y", "install"],
        False: [repo_manager_bin, "-d", "0", "-e", "0", "-y", "install"],
    }

    upgrade_cmd = {
        True: [repo_manager_bin, "-y", "update"],
        False: [repo_manager_bin, "-d", "0", "-e", "0", "-y", "update"],
    }

    remove_cmd = {
        True: [repo_manager_bin, "-y", "erase"],
        False: [repo_manager_bin, "-d", "0", "-e", "0", "-y", "erase"],
    }
    
    # 依赖与验证命�?    verify_dependency_cmd = [
        repo_manager_bin, "check", "dependencies"
    ]
    installed_package_version_command = [
        pkg_manager_bin,
        "--queryformat",
        "%{NAME} %{VERSION}-%{RELEASE}\\n"
    ]
    remove_without_dependencies_cmd = ["rpm", "-e", "--nodeps", "--allmatches"]
    
    # 性能优化配置
    max_workers = 4                 # 最大并行工作数
    command_timeout = 300           # 命令超时时间（秒�?    repo_scan_timeout = 120         # 仓库扫描超时（秒�?    cache_refresh_interval = 1800   # 缓存刷新间隔（秒�?
    # 事务恢复命令
    CLEANUP_CMD = [
        repo_manager_bin, 
        "cleanup", 
        "--cleandupes", 
        "--verbose"
    ]
    COMPLETE_TX_CMD = [
        repo_manager_bin,
        "complete-transaction",
        "--cleanup-only"
    ]


class YumManager(GenericManager):
    """高性能YUM包管理器（优化版�?""
    
    # 包查询缓存机�?    _query_cache: Dict[str, Tuple[float, List[PackageInfo]]] = {}
    
    @property
    def properties(self) -> YumManagerProperties:
        return YumManagerProperties

    def refresh_repositories(self, context) -> bool:
        """刷新YUM仓库缓存"""
        Logger.info("Refreshing YUM repositories")
        commands = [
            self.properties.repo_update_cmd,
            self.properties.repo_refresh_cmd
        ]
        
        for cmd in commands:
            result = shell.repository_manager_executor(
                cmd, 
                self.properties, 
                context,
                timeout=self.properties.repo_scan_timeout
            )
            if not result.success:
                Logger.error(f"Repository refresh failed: {result.stderr}")
                return False
                
        # 清除包查询缓�?        self._query_cache.clear()
        return True

    def get_available_packages_in_repos(self, repositories) -> List[str]:
        """
        Gets all available packages in specified repositories (optimized)
        
        :param repositories: Command repository configuration
        :return: List of package names
        """
        Logger.info("Fetching available packages from repositories")
        
        # 1. 准备仓库ID列表
        repo_ids = {repo.repo_id for repo in repositories.items}
        
        # 2. 获取系统匹配的仓库ID（包含fallback�?        all_repos = self._build_repos_ids(repositories)
        effective_repos = repo_ids | all_repos if repositories.feat.scoped else all_repos
        
        Logger.debug(f"Effective repositories: {', '.join(effective_repos)}")
        
        # 3. 并行查询所有仓�?        pkg_names = set()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.properties.max_workers
        ) as executor:
            # 查询已安装包
            installed_future = executor.submit(
                self._query_packages,
                self.installed_packages,
                repo_filter=None
            )
            
            # 查询可用包（每个仓库独立查询�?            futures = [
                executor.submit(
                    self._query_packages,
                    self.available_packages,
                    pkg_names=None,
                    repo_filter=repo
                )
                for repo in effective_repos
            ]
            
            # 处理已安装包结果
            pkg_names.update(pkg[0] for pkg in installed_future.result())
            
            # 处理可用包结�?            for future in concurrent.futures.as_completed(futures):
                results = future.result()
                pkg_names.update(pkg[0] for pkg in results)

        Logger.info(f"Found {len(pkg_names)} unique packages")
        return list(pkg_names)

    def _query_packages(
        self, 
        query_func,
        pkg_names: Optional[List[str]] = None, 
        repo_filter: Optional[str] = None
    ) -> List[PackageInfo]:
        """查询包信息（带缓存机制）"""
        cache_key = f"{query_func.__name__}:{repo_filter}:{'_'.join(sorted(pkg_names) if pkg_names else 'all')}"
        
        # 检查有效缓�?        current_time = time.time()
        if cache_key in self._query_cache:
            timestamp, packages = self._query_cache[cache_key]
            if current_time - timestamp < self.properties.cache_expire_time:
                Logger.debug(f"Using cached package data for {cache_key}")
                return packages
        
        # 执行实际查询
        packages = query_func(pkg_names, repo_filter)
        
        # 更新缓存
        self._query_cache[cache_key] = (current_time, packages)
        return packages

    def available_packages(
        self, 
        pkg_names: Optional[List[str]] = None, 
        repo_filter: Optional[str] = None
    ) -> List[PackageInfo]:
        """获取可用软件包列表（带仓库过滤）"""
        query_cmd = self._build_query_command(
            self.properties.available_packages_cmd,
            repo_filter
        )
        return self._execute_package_query(
            query_cmd, 
            pkg_names
        )

    def installed_packages(
        self, 
        pkg_names: Optional[List[str]] = None, 
        repo_filter: Optional[str] = None
    ) -> List[PackageInfo]:
        """获取已安装软件包列表（带仓库过滤�?""
        query_cmd = self._build_query_command(
            self.properties.installed_packages_cmd,
            repo_filter
        )
        return self._execute_package_query(
            query_cmd, 
            pkg_names
        )

    def all_packages(
        self, 
        pkg_names: Optional[List[str]] = None, 
        repo_filter: Optional[str] = None
    ) -> List[PackageInfo]:
        """获取所有软件包列表（带仓库过滤�?""
        query_cmd = self._build_query_command(
            self.properties.all_packages_cmd,
            repo_filter
        )
        return self._execute_package_query(
            query_cmd, 
            pkg_names
        )

    def _build_query_command(
        self, 
        base_cmd: List[str], 
        repo_filter: Optional[str] = None
    ) -> List[str]:
        """构建包查询命令（添加仓库过滤�?""
        cmd = list(base_cmd)
        if repo_filter:
            cmd.extend(["--disablerepo=*", "--enablerepo=" + repo_filter])
        return cmd

    def _execute_package_query(
        self, 
        command: List[str], 
        pkg_names: Optional[List[str]] = None
    ) -> List[PackageInfo]:
        """
        执行包查询操�?        返回标准化PackageInfo对象
        """
        packages = []
        try:
            with shell.process_executor(
                command, 
                timeout=self.properties.repo_scan_timeout,
                error_callback=self._executor_error_handler
            ) as output:
                for pkg in YumParser.packages_reader(output):
                    # 包名过滤（如果指定）
                    if pkg_names and pkg.name not in pkg_names:
                        continue
                    packages.append(pkg)
                    
        except shell.ExecutionTimeout as e:
            Logger.error(f"Package query timed out: {' '.join(command)}")
        except Exception as e:
            Logger.error(f"Package query failed: {str(e)}")
            
        return packages

    def verify_dependencies(self) -> bool:
        """增强的依赖检查机制（支持错误模式识别�?""
        Logger.info("Verifying package dependencies")
        try:
            result = shell.subprocess_executor(
                self.properties.verify_dependency_cmd,
                timeout=self.properties.command_timeout
            )
            
            # 分析输出中的错误模式
            error_patterns = ["has missing requires of", "Error:", "dependencies failed"]
            has_errors = result.code != 0 or any(
                pattern in result.out for pattern in error_patterns
            )
            
            if has_errors:
                err_msg = Logger.filter_text(
                    f"Dependency issues detected (exit code: {result.code}):"
                    f"{result.out[:500]}..."
                )
                Logger.error(err_msg)
                return False
                
            return True
            
        except shell.ExecutionTimeout:
            Logger.error("Dependency verification timed out")
            return False

    def install_package(self, name: str, context) -> bool:
        """
        安装软件包（智能重试机制�?        返回操作是否成功
        """
        if not name:
            raise ValueError("Package name cannot be empty")
            
        # 检查包是否已存�?        if self.is_package_installed(name) and not context.action_force:
            Logger.info(f"Skipping installation of existing package: {name}")
            return True
            
        # 构建安装命令
        cmd = self._build_base_command(
            self.properties.install_cmd[context.log_output],
            name,
            context
        )
        
        # 执行安装（带重试�?        return self._execute_package_operation(
            "install",
            name,
            cmd,
            context
        )

    def upgrade_package(self, name: str, context) -> bool:
        """升级软件包（使用专用upgrade命令�?""
        if not name:
            raise ValueError("Package name cannot be empty")
            
        # 构建升级命令
        cmd = self._build_base_command(
            self.properties.upgrade_cmd[context.log_output],
            name,
            context
        )
        
        # 标记为升级操�?        context.is_upgrade = True
        
        # 执行升级
        return self._execute_package_operation(
            "upgrade",
            name,
            cmd,
            context
        )

    def remove_package(
        self, 
        name: str, 
        context,
        ignore_dependencies: bool = False
    ) -> bool:
        """移除软件包（支持依赖忽略�?""
        if not name:
            raise ValueError("Package name cannot be empty")
            
        # 检查包是否存在
        if not self.is_package_installed(name):
            Logger.info(f"Skipping removal of non-existing package: {name}")
            return True
            
        # 构建移除命令
        if ignore_dependencies:
            cmd = self.properties.remove_without_dependencies_cmd + [name]
        else:
            cmd = self._build_base_command(
                self.properties.remove_cmd[context.log_output],
                name,
                context
            )
        
        # 执行移除
        return self._execute_package_operation(
            "remove",
            name,
            cmd,
            context
        )

    def _build_base_command(
        self,
        base_cmd: List[str],
        name: str,
        context
    ) -> List[str]:
        """构建基础包操作命令（添加仓库配置�?""
        cmd = base_cmd.copy()
        if context.use_repos:
            enable_opt = "--enablerepo=" + ",".join(
                repo for repo in context.use_repos
                if repo != 'base'  # 跳过特殊标记
            )
            
            # 添加基础仓库
            if 'base' in context.use_repos:
                base_repos = self.get_active_base_repos()
                enable_opt = ",".join([enable_opt] + base_repos) if enable_opt else ",".join(base_repos)
            
            disable_opt = "--disablerepo=*"
            cmd.extend([disable_opt, enable_opt])
            
        cmd.append(name)
        return cmd

    def _execute_package_operation(
        self,
        operation: str,
        name: str,
        cmd: List[str],
        context,
        max_retries: int = 2,
        retry_delay: int = 5
    ) -> bool:
        """执行包操作（带重试和错误处理机制�?""
        Logger.info(f"{operation.capitalize()}ing package {name}: {' '.join(cmd)}")
        
        # 操作重试循环
        for attempt in range(max_retries + 1):
            try:
                result = shell.repository_manager_executor(
                    cmd,
                    self.properties,
                    context,
                    timeout=self.properties.command_timeout
                )
                
                # 操作成功立即返回
                if result.success:
                    return True
                    
                # 检查是否可恢复错误
                if self._is_recoverable_error(result.stderr):
                    self._handle_recoverable_error(operation, result.stderr)
                    
            except shell.ExecutionTimeout:
                Logger.error(f"{operation.capitalize()} operation for {name} timed out")
                
            # 重试逻辑
            if attempt < max_retries:
                Logger.warning(f"Retrying {operation} in {retry_delay} seconds... (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                Logger.error(f"{operation.capitalize()} package {name} failed after {max_retries} attempts")
                return False
                
        return False

    def _is_recoverable_error(self, error: str) -> bool:
        """检查错误是否可恢复"""
        recoverable_errors = [
            "Locked by another process",
            "does not update",
            "Package not found"
        ]
        return any(msg in error for msg in recoverable_errors)

    def _handle_recoverable_error(self, operation: str, error: str):
        """处理可恢复错�?""
        if "Locked by another process" in error:
            Logger.warning("YUM is locked by another process. Waiting...")
            time.sleep(10)
            
        elif "Package not found" in error:
            Logger.warning("Package not found in enabled repositories. Refreshing repos...")
            self.refresh_repositories(None)  # 传入合适的context
            
        # 其他错误处理逻辑...

    def is_package_installed(self, name: Union[str, re.Pattern]) -> bool:
        """检查包是否已安装（优化模式匹配�?""
        if isinstance(name, re.Pattern):
            # 正则表达式匹�?            pattern = name
            return any(
                pattern.match(pkg.name) 
                for pkg in self.installed_packages()
            )
        else:
            # 普通字符串匹配（使用快速查询）
            return self.rpm_check_package_available(name)

    def rpm_check_package_available(self, pattern: str) -> bool:
        """优化包存在检查（支持通配符）"""
        # 如果是精确匹配，则使用高效查�?        if '*' not in pattern and '?' not in pattern:
            return bool(
                shell.subprocess_executor([
                    self.properties.pkg_manager_bin,
                    "-q",
                    pattern
                ]).code == 0
            )
            
        # 使用YUM数据库查询通配符模�?        results = self._query_packages(
            self.installed_packages,
            pkg_names=None,
            repo_filter=None
        )
        
        # 生成匹配模式
        glob_pattern = fnmatch.translate(pattern)
        regex = re.compile(glob_pattern)
        
        # 检查是否有匹配�?        return any(
            regex.match(pkg.name) 
            for pkg in results
        )

    def get_installed_package_version(self, package_name: str) -> Optional[str]:
        """获取包版本（带缓存）"""
        cache_key = f"version:{package_name}"
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]
            
        # 构建查询命令
        cmd = self.properties.installed_package_version_command + [package_name]
        
        try:
            result = shell.subprocess_executor(
                cmd, 
                timeout=30
            )
            
            if result.success and result.out:
                # 解析输出: <package-name> <version>
                parts = result.out.strip().split()
                if len(parts) >= 2:
                    version = parts[1].split(".el")[0]  # 清理版本字符�?                    self._query_cache[cache_key] = version
                    return version
                    
        except Exception:
            Logger.warning(f"Failed to query version for {package_name}")
            
        return None

    @staticmethod
    def _build_repos_ids(repositories) -> Set[str]:
        """
        高效构建仓库ID集合（带缓存机制�?        包含动态匹配的仓库
        """
        # 提取仓库URL模式
        base_urls = set()
        mirrors = set()
        if repositories:
            for repo in repositories.items:
                if repo.base_url:
                    base_urls.add(repo.base_url)
                if repo.mirrors_list:
                    mirrors.add(repo.mirrors_list)

        # 收集匹配仓库
        repo_ids = set()
        
        # 扫描仓库配置文件
        for repo_file in glob.glob(
            os.path.join(YumManagerProperties.repo_definition_location, "*.repo")
        ):
            try:
                config = configparser.ConfigParser()
                config.read(repo_file)
                
                for section in config.sections():
                    # 检查baseurl匹配
                    if 'baseurl' in config[section]:
                        url = config[section]['baseurl']
                        if url in base_urls:
                            repo_ids.add(section)
                    # 检查mirrorlist匹配
                    if 'mirrorlist' in config[section]:
                        mirror = config[section]['mirrorlist']
                        if mirror in mirrors:
                            repo_ids.add(section)
            except Exception as e:
                Logger.warning(f"Error parsing repo file {repo_file}: {str(e)}")

        return repo_ids

    def get_active_base_repos(self) -> List[str]:
        """获取激活的基础仓库（带缓存�?""
        repo_cmd = [self.properties.repo_manager_bin, "repolist", "-v", "--enabled"]
        cached_key = "active_base_repos"
        
        # 检查缓�?        if cached_key in self._query_cache:
            return self._query_cache[cached_key]
            
        active_repos = []
        try:
            with shell.process_executor(
                repo_cmd, 
                timeout=self.properties.repo_scan_timeout
            ) as output:
                repo_id = None
                for line in output:
                    line = line.strip()
                    if line.startswith("Repo-id"):
                        # 示例: "Repo-id      : base"
                        repo_id = line.split(":", 1)[1].strip()
                    elif repo_id and ("SUSE-" in line or "OSS" in line or "OpenSuse" in line):
                        active_repos.append(repo_id)
                        
            self._query_cache[cached_key] = active_repos
            return active_repos
            
        except Exception as e:
            Logger.error(f"Failed to list active repositories: {str(e)}")
            return []
            
        return []

    def check_uncompleted_transactions(self, auto_clean: bool = False) -> bool:
        """
        检查未完成事务（支持自动清理）
        返回系统是否处于清理状�?        """
        transactions = list(self.uncomplete_transactions())
        if not transactions:
            Logger.info("No incomplete YUM transactions found")
            return True
            
        # 日志报告问题事务
        Logger.warning(f"Found {len(transactions)} incomplete YUM transactions:")
        for i, tr in enumerate(transactions, 1):
            aborted_pkgs = tr.pkgs_aborted
            Logger.warning(
                f"  [{i}] Transaction {tr.transaction_id}: "
                f"Completed: {len(tr.pkgs_done)}, Aborted: {len(aborted_pkgs)}"
            )
            
        # 自动清理选项
        if auto_clean:
            return self._cleanup_transactions(transactions)
            
        return False

    def _cleanup_transactions(self, transactions: List[YumTransactionItem]) -> bool:
        """尝试自动清理未完成事�?""
        Logger.info("Attempting automatic cleanup of incomplete transactions")
        
        # 1. 尝试完成事务
        result = shell.subprocess_executor(
            self.properties.COMPLETE_TX_CMD,
            timeout=self.properties.command_timeout
        )
        if not result.success:
            Logger.error(f"Failed to complete transactions: {result.stderr}")
            
        # 2. 清理包重�?        result = shell.subprocess_executor(
            self.properties.CLEANUP_CMD,
            timeout=self.properties.command_timeout
        )
        if not result.success:
            Logger.error(f"Failed to cleanup duplicates: {result.stderr}")
            
        # 3. 清理旧事务文�?        cleanup_ok = True
        for tr in transactions:
            try:
                tx_file = os.path.join(
                    self.properties.yum_lib_dir,
                    f"{self.properties.yum_tr_prefix}{tr.transaction_id}"
                )
                if os.path.exists(tx_file):
                    sudo.unlink(tx_file)
                    Logger.info(f"Removed transaction file: {tx_file}")
            except Exception as e:
                Logger.error(f"Failed to remove transaction file: {str(e)}")
                cleanup_ok = False
                
        # 4. 验证清理结果
        if cleanup_ok and not self.uncomplete_transactions():
            Logger.info("Successfully cleaned up incomplete transactions")
            return True
            
        Logger.error("Failed to fully clean up incomplete transactions")
        return False

    def uncomplete_transactions(self) -> Generator[YumTransactionItem, None, None]:
        """高效收集未完成事务（使用索引�?""
        try:
            # 1. 快速检查事务目�?            tx_files = sudo.listdir(self.properties.yum_lib_dir)
            if not any(f.startswith(self.properties.yum_tr_prefix) for f in tx_files):
                return
                
            # 2. 扫描事务文件
            transactions = {}
            for filename in tx_files:
                if not filename.startswith(self.properties.yum_tr_prefix):
                    continue
                    
                # 解析文件�? transaction-<id>.<type>
                base_name = filename[len(self.properties.yum_tr_prefix):]
                try:
                    tx_id, tx_type = base_name.split(".", 1)
                except ValueError:
                    continue
                    
                if tx_type not in (RPMTransactions.ALL, RPMTransactions.DONE):
                    continue
                    
                # 读取事务内容
                file_path = os.path.join(self.properties.yum_lib_dir, filename)
                content = sudo.read_file(file_path)
                if not content:
                    continue
                    
                # 解析包列�?                pkg_list = [line.split(":", 1)[1].strip() for line in content.splitlines() if ":" in line]
                
                # 更新事务对象
                if tx_id not in transactions:
                    transactions[tx_id] = {RPMTransactions.ALL: [], RPMTransactions.DONE: []}
                
                transactions[tx_id][tx_type] = pkg_list
                
            # 生成未完成事�?            for tx_id, data in transactions.items():
                if not (data[RPMTransactions.ALL] and data[RPMTransactions.DONE]):
                    continue
                    
                if set(data[RPMTransactions.ALL]) != set(data[RPMTransactions.DONE]):
                    yield YumTransactionItem(
                        transaction_id=tx_id,
                        pkgs_all=data[RPMTransactions.ALL],
                        pkgs_done=data[RPMTransactions.DONE]
                    )
                    
        except Exception as e:
            Logger.error(f"Error reading YUM transactions: {str(e)}")

    def print_uncompleted_transaction_hint(self):
        """提供事务恢复操作指南"""
        help_msg = """
*** Incomplete YUM Transactions Detected ***

cloud has detected incomplete YUM transactions on this host. 
This can interfere with package management operations. 

To resolve:

1. View incomplete transactions:
   sudo yum history list
   
2. Recover specific transaction:
   sudo yum history undo <transaction_id>
   
3. Attempt auto-recovery:
   sudo yum-complete-transaction
   
4. Clean up package duplicates:
   sudo package-cleanup --cleandupes

5. If all else fails, remove transaction files:
   sudo rm -f /var/lib/yum/transaction-*
   sudo rm -f /var/lib/dnf/transaction-*

WARNING: Manual transaction recovery should be performed with caution.
Backup important data before proceeding.
"""
        for line in help_msg.split('\n'):
            if line.strip():
                Logger.error(line.strip())
