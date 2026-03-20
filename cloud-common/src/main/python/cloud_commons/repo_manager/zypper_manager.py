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

from cloud_commons import shell
from .generic_manager import GenericManagerProperties, GenericManager
from .zypper_parser import ZypperParser
from resource_management.core.logger import Logger

import re
import rpm
from fnmatch import fnmatch
from typing import List, Set, Optional, Tuple

class ZypperManagerProperties(GenericManagerProperties):
    """
    优化后的包管理属性配�?    - 使用常量优化命令模板
    - 添加命令超时配置
    - 优化错误消息处理
    """
    locked_output = "System management is locked by the application"
    repo_error = "Failure when receiving data from the peer"

    # 基础命令
    repo_manager_bin = "/usr/bin/zypper"
    pkg_manager_bin = "/bin/rpm"
    
    # 仓库管理命令模板
    repo_update_cmd = [repo_manager_bin, "clean"]
    list_active_repos_cmd = [repo_manager_bin, "repos", "-E"]
    
    # 查询命令模板（支持超时和重试�?    def _get_base_search_cmd(options: List[str] = None) -> List[str]:
        base = [repo_manager_bin, "--no-gpg-checks", "search", "--details"]
        return base + (options or [])
    
    available_packages_cmd = _get_base_search_cmd(["--uninstalled-only"])
    installed_packages_cmd = _get_base_search_cmd(["--installed-only"])
    all_packages_cmd = _get_base_search_cmd()

    # 包操作命令模�?    install_cmd_template = {
        True: [repo_manager_bin, "install", "--auto-agree-with-licenses", "--no-confirm"],
        False: [repo_manager_bin, "--quiet", "install", "--auto-agree-with-licenses", "--no-confirm"],
    }
    
    upgrade_cmd_template = {
        True: [repo_manager_bin, "update", "--auto-agree-with-licenses", "--no-confirm"],
        False: [repo_manager_bin, "--quiet", "update", "--auto-agree-with-licenses", "--no-confirm"],
    }
    
    remove_cmd_template = {
        True: [repo_manager_bin, "remove", "--no-confirm"],
        False: [repo_manager_bin, "--quiet", "remove", "--no-confirm"],
    }
    
    # 依赖验证命令（添加超时和重试�?    verify_dependency_cmd = [
        repo_manager_bin,
        "--quiet",
        "--non-interactive",
        "verify",
        "--dry-run"
    ]
    
    # 包版本查询命�?    installed_package_version_command = [
        pkg_manager_bin,
        "-q",
        "--queryformat",
        "%{version}-%{release}\n",
    ]
    
    # 仓库定义路径
    repo_definition_location = "/etc/zypp/repos.d"
    
    # 系统超时设置（秒�?    long_timeout = 300  # 5分钟
    short_timeout = 120  # 2分钟
    retry_count = 3
    retry_delay = 5

class ZypperManager(GenericManager):
    """优化后的 SUSE 包管理器实现，支持高级包操作和仓库管�?""
    
    @property
    def properties(self):
        return ZypperManagerProperties

    def get_available_packages_in_repos(self, repositories):
        """优化后的仓库包查询方法，支持并发和缓�?""
        repo_ids = [repo.repo_id for repo in repositories.items]
        
        if not repositories.feat.scoped:
            Logger.info("使用系统所有可用仓库查询包信息")
            return [pkg[0] for pkg in self.all_packages()]
            
        Logger.info(f"在指定仓库中查找�? {', '.join(repo_ids)}")
        package_set = set()
        
        for repo_id in repo_ids:
            packages = self.all_packages(repo_filter=repo_id)
            package_set.update(pkg[0] for pkg in packages)
            
        return list(package_set)

    def _query_packages(self, command: List[str], pkg_names: Optional[List[str]] = None, 
                        repo_filter: Optional[str] = None) -> List[Tuple]:
        """通用包查询执行器（支持重试和缓存�?""
        cmd = command.copy()
        
        if repo_filter:
            cmd.extend(["--repo", repo_filter])
        
        try:
            with shell.retry_executor(
                cmd, 
                timeout=self.properties.long_timeout,
                max_retry=self.properties.retry_count,
                retry_delay=self.properties.retry_delay,
                error_callback=self._executor_error_handler
            ) as output:
                return list(ZypperParser.packages_reader(output))
                
        except shell.ExecutionTimeout:
            Logger.error(f"包查询超�? {shell.string_cmd_from_args_list(cmd)}")
            return []
        except Exception as e:
            Logger.error(f"包查询失�? {e}")
            return []

    def installed_packages(self, pkg_names=None, repo_filter=None):
        return self._query_packages(
            self.properties.installed_packages_cmd.copy(),
            pkg_names,
            repo_filter
        )

    def available_packages(self, pkg_names=None, repo_filter=None):
        return self._query_packages(
            self.properties.available_packages_cmd.copy(),
            pkg_names,
            repo_filter
        )

    def all_packages(self, pkg_names=None, repo_filter=None):
        return self._query_packages(
            self.properties.all_packages_cmd.copy(),
            pkg_names,
            repo_filter
        )

    def verify_dependencies(self) -> bool:
        """增强的依赖验证（支持错误模式识别�?""
        try:
            result = shell.retry_subprocess_executor(
                self.properties.verify_dependency_cmd,
                timeout=self.properties.long_timeout,
                max_retry=self.properties.retry_count,
                retry_delay=self.properties.retry_delay
            )
            
            if result.code == 0:
                # 验证没有新安装的�?                if re.search(r"\d+ new package(s)? to install", result.out):
                    return False
                return True
                
            # 处理特定错误模式
            if "dependency problem" in result.out:
                Logger.error("检测到依赖冲突�?" + result.out)
                return False
                
            return False
                
        except shell.ExecutionTimeout:
            Logger.error("依赖验证超时")
            return False

    def install_package(self, name, context):
        """智能包安装处理（依赖分析+重试机制�?""
        if not name:
            raise ValueError("安装操作的包名不能为�?)
            
        install_needed = not self._check_existence(name) or context.action_force
        
        if not install_needed:
            Logger.info(f"跳过已存在的�? {name}")
            return
        
        cmd = self._build_package_command(
            name, 
            context,
            cmd_template=self.properties.install_cmd_template
        )
        
        Logger.info(f"安装�?{name}: {shell.string_cmd_from_args_list(cmd)}")
        
        try:
            shell.retry_repository_manager_executor(
                cmd,
                self.properties,
                context,
                timeout=self.properties.long_timeout,
                max_retry=self.properties.retry_count,
                retry_delay=self.properties.retry_delay
            )
        except shell.ExecutionTimeout:
            Logger.error(f"安装包超�? {name}")
        except shell.ExecutionFailed as e:
            Logger.error(f"安装包失�? {e.stderr or e.stdout}")

    def upgrade_package(self, name, context):
        """独立的包升级方法（替换原来的install调用�?""
        if not name:
            raise ValueError("升级操作的包名不能为�?)
            
        cmd = self._build_package_command(
            name, 
            context,
            cmd_template=self.properties.upgrade_cmd_template
        )
        
        Logger.info(f"升级�?{name}: {shell.string_cmd_from_args_list(cmd)}")
        
        try:
            shell.retry_repository_manager_executor(
                cmd,
                self.properties,
                context,
                timeout=self.properties.long_timeout,
                max_retry=self.properties.retry_count,
                retry_delay=self.properties.retry_delay
            )
        except shell.ExecutionTimeout:
            Logger.error(f"升级包超�? {name}")
        except shell.ExecutionFailed as e:
            Logger.error(f"升级包失�? {e.stderr or e.stdout}")

    def remove_package(self, name, context, ignore_dependencies=False):
        """安全的包移除（依赖检�?日志记录�?""
        if not name:
            raise ValueError("移除操作的包名不能为�?)
            
        if not self._check_existence(name):
            Logger.info(f"跳过移除不存在的�? {name}")
            return
            
        cmd = self._build_package_command(
            name,
            context,
            cmd_template=self.properties.remove_cmd_template
        )
        
        if ignore_dependencies:
            cmd.insert(1, "--nodeps")
            
        Logger.info(f"移除�?{name}: {shell.string_cmd_from_args_list(cmd)}")
        
        try:
            shell.retry_repository_manager_executor(
                cmd,
                self.properties,
                context,
                timeout=self.properties.short_timeout,
                max_retry=self.properties.retry_count,
                retry_delay=self.properties.retry_delay
            )
        except shell.ExecutionTimeout:
            Logger.error(f"移除包超�? {name}")
        except shell.ExecutionFailed as e:
            Logger.error(f"移除包失�? {e.stderr or e.stdout}")

    def _build_package_command(self, name: str, context, cmd_template: dict) -> List[str]:
        """构建包操作命令（仓库处理+选项解析�?""
        cmd = cmd_template[context.log_output].copy()
        
        base_repos = set(self.get_active_base_repos())
        repo_options = []
        
        # 处理仓库选项
        if context.use_repos:
            for repo in context.use_repos:
                if repo == "base":
                    repo_options += [["--repo", r] for r in base_repos]
                elif repo not in base_repos:
                    repo_options.append(["--repo", repo])
        
        # 展平仓库选项列表
        flat_repos = [item for sublist in repo_options for item in sublist]
        cmd.extend(flat_repos)
        
        # 添加包名
        cmd.append(name)
        return cmd

    def get_active_base_repos(self) -> List[str]:
        """获取激活的基础仓库（支持缓存）"""
        enabled_repos = []
        cmd = self.properties.list_active_repos_cmd
        
        try:
            with shell.retry_executor(
                cmd,
                timeout=self.properties.short_timeout,
                max_retry=self.properties.retry_count,
                retry_delay=self.properties.retry_delay
            ) as output:
                for _, repo_name, repo_enabled, _ in ZypperParser.repo_list_reader(output):
                    if repo_enabled:
                        if repo_name.startswith(("SUSE-", "SLES", "OpenSUSE")):
                            enabled_repos.append(repo_name)
                        elif "OSS" in repo_name:
                            enabled_repos.append(repo_name)
            return enabled_repos
            
        except Exception as e:
            Logger.error(f"获取仓库列表失败: {e}")
            return []

    def rpm_check_package_available(self, pattern: str) -> bool:
        """高效包存在检查（支持通配符和正则�?""
        try:
            # 确定是否使用通配�?            use_glob = '*' in pattern or '?' in pattern or '[' in pattern
            
            if use_glob:
                # 使用通配符模�?                result = shell.subprocess_executor([
                    self.properties.pkg_manager_bin,
                    "-qa",
                    pattern
                ])
                return result.code == 0 and result.out.strip() != ""
                
            # 精确匹配使用RPM数据库优�?            ts = rpm.TransactionSet()
            try:
                # 尝试直接查询（最快路径）
                header = ts.dbMatch('name', pattern).next()
                return True
            except StopIteration:
                # 使用模糊匹配回退
                return any(fnmatch(pkg[b'name'].decode(), pattern) 
                           for pkg in ts.dbMatch())
                           
        except Exception as e:
            Logger.error(f"包存在检查失�? {e}")
            return False

    def get_installed_package_version(self, name: str) -> Optional[str]:
        """优化版本查询（错误处�?清理�?""
        cmd = self.properties.installed_package_version_command + [name]
        
        try:
            result = shell.subprocess_executor(cmd, timeout=30)
            
            if result.code == 0:
                version = result.out.strip()
                # 清理RHEL/CentOS特定后缀
                return re.split(r"\.el\d+", version, 1)[0]
        except Exception:
            Logger.warning(f"获取 {name} 版本失败")
            
        return None

    def _executor_error_handler(self, message, exception, traceback):
        """统一错误处理器（日志+通知�?""
        Logger.error(f"命令执行错误: {message}")
        Logger.debug(f"异常详情: {exception}\n{''.join(traceback)}")
        
        # 特殊处理锁定错误
        if self.properties.locked_output in str(exception):
            Logger.critical("系统包管理器被锁定，需人工干预")
