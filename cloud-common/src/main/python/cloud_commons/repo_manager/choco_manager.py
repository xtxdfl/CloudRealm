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

import re
from typing import Dict, List, Optional

from cloud_commons.repo_manager.generic_manager import GenericManagerProperties, GenericManager
from cloud_commons.shell import shellRunner
from resource_management.core.logger import Logger

# Chocolatey 命令模板
CHOCO_INSTALL_CMD = ["cmd", "/c", "choco", "install"]
CHOCO_UPGRADE_CMD = ["cmd", "/c", "choco", "upgrade"]
CHOCO_UNINSTALL_CMD = ["cmd", "/c", "choco", "uninstall"]
CHOCO_LIST_CMD = ["cmd", "/c", "choco", "list"]
CHOCO_INFO_CMD = ["cmd", "/c", "choco", "info"]

# 预编译正则表达式用于输出解析
PACKAGE_LIST_REGEX = re.compile(r"^(?P<name>\S+)\s+(?P<version>\S+)(?:\s+(?P<source>\S+))?$")
PACKAGE_VERSION_REGEX = re.compile(r"^(?:\d+\.)?\d+(?:\.\d+)+([-+]\S+)?$")

class ChocoManagerProperties(GenericManagerProperties):
    """
    Chocolatey包管理器特性配�?    - 优化默认参数
    - 添加超时控制
    - 分离环境变量
    """
    command_timeout = 300         # 命令执行超时（秒�?    retry_count = 3              # 操作重试次数
    retry_delay = 15             # 重试延迟（秒�?    use_pre_releases = True      # 是否允许预发布版�?    install_cmd_env = {"CHOCOLATEY_IGNORE_DEPENDENCIES": "false"}
    max_output_size = 10 * 1024 * 1024  # 10MB最大输出限�?

class ChocoManager(GenericManager):
    """优化后的Chocolatey包管理器实现"""
    
    def __init__(self):
        self._local_cache = {}
        self._cache_timestamp = 0
    
    @property
    def properties(self) -> GenericManagerProperties:
        return ChocoManagerProperties

    def _choco_command(self, action: str, name: str, context, ignore_dependencies: bool = False) -> List[str]:
        """构建Chocolatey命令"""
        # 选择基础命令
        if action == "install":
            cmd = CHOCO_INSTALL_CMD[2:]
        elif action == "upgrade":
            cmd = CHOCO_UPGRADE_CMD[2:]
        elif action == "uninstall":
            cmd = CHOCO_UNINSTALL_CMD[2:]
        else:
            return []
        
        # 详细模式配置
        cmd.append("--no-progress")
        if context.log_output:
            cmd.append("-v")
            cmd.append("-d")
        
        # 预发布版本设�?        if self.properties.use_pre_releases:
            cmd.append("--pre")
        
        # 添加源参�?        if context.use_repos and action != "uninstall":
            sources = self._build_sources_param(context)
            if sources:
                cmd.extend(["-s", sources])
        
        # 添加忽略依赖选项
        if ignore_dependencies and action == "uninstall":
            cmd.append("--remove-dependencies")
        elif ignore_dependencies and action == "install":
            Logger.warning("Chocolatey does not support ignoring dependencies during install")
        
        # 其他配置
        cmd.append("--yes")
        
        # 添加包名
        if action != "list":  # list命令不需要包�?            cmd.append(name)
        
        return ["cmd", "/c"] + cmd
    
    def _build_sources_param(self, context) -> str:
        """构建源参数字符串"""
        if not context.use_repos:
            return ""
        
        sources = []
        priority_map = []
        
        # 区分优先级和非优先级�?        for repo, spec in context.use_repos.items():
            if spec.get("priority") is not None:
                priority_map.append((spec.get("priority"), repo))
            else:
                sources.append(repo)
        
        # 按优先级排序
        priority_map.sort(key=lambda x: x[0], reverse=True)
        for _, repo in priority_map:
            sources.insert(0, repo)
        
        return ",".join(sources)
    
    def _execute_choco_command(self, 
                              action: str,
                              name: str,
                              context,
                              ignore_dependencies: bool = False) -> Dict:
        """执行Chocolatey命令"""
        cmd = self._choco_command(action, name, context, ignore_dependencies)
        Logger.info(f"Executing Chocolatey {action} for {name}: {' '.join(cmd[2:])}")
        
        runner = shellRunner(
            timeout=self.properties.command_timeout,
            max_retry=self.properties.retry_count,
            retry_delay=self.properties.retry_delay
        )
        try:
            return runner.run(cmd)
        except Exception as e:
            Logger.error(f"Failed to execute Chocolatey command: {str(e)}")
            raise

    def install_package(self, name: str, context) -> None:
        """
        安装Chocolatey软件�?        :param name: 包名
        :param context: 执行上下�?        """
        # 检查包是否已安�?        if self._check_existence(name, context):
            Logger.info(f"Skipping installation of existing package: {name}")
            return
            
        # 执行安装
        res = self._execute_choco_command("install", name, context)
        
        if res["exitCode"] not in (0, 1641, 3010):
            # 0=成功, 1641=需要重�? 3010=需要重�?            error_msg = (
                f"Failed to install Chocolatey package {name}. "
                f"Exit code: {res['exitCode']}\n"
                f"Error: {res.get('error', '')}\n"
                f"Output: {res.get('output', '')[:2000]}")
            Logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新本地缓存
        self._refresh_cache(name, context)
        Logger.info(f"Successfully installed Chocolatey package: {name}")

    def upgrade_package(self, name: str, context) -> None:
        """
        升级Chocolatey软件�?        :param name: 包名
        :param context: 执行上下�?        """
        # 检查包是否安装
        if not self._check_existence(name, context):
            Logger.info(f"Package not installed, performing fresh install: {name}")
            return self.install_package(name, context)
            
        # 执行升级
        res = self._execute_choco_command("upgrade", name, context)
        
        if res["exitCode"] not in (0, 1641, 3010):
            error_msg = (
                f"Failed to upgrade Chocolatey package {name}. "
                f"Exit code: {res['exitCode']}\n"
                f"Error: {res.get('error', '')}\n"
                f"Output: {res.get('output', '')[:2000]}")
            Logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新本地缓存
        self._refresh_cache(name, context)
        Logger.info(f"Successfully upgraded Chocolatey package: {name}")

    def remove_package(self, 
                      name: str, 
                      context, 
                      ignore_dependencies: bool = False) -> None:
        """
        移除Chocolatey软件�?        :param name: 包名
        :param context: 执行上下�?        :param ignore_dependencies: 是否保留依赖
        """
        # 检查包是否安装
        if not self._check_existence(name, context):
            Logger.info(f"Skipping removal of non-existing package: {name}")
            return
            
        # 执行卸载
        res = self._execute_choco_command("uninstall", name, context, ignore_dependencies)
        
        if res["exitCode"] not in (0, 1641, 3010):
            error_msg = (
                f"Failed to uninstall Chocolatey package {name}. "
                f"Exit code: {res['exitCode']}\n"
                f"Error: {res.get('error', '')}\n"
                f"Output: {res.get('output', '')[:2000]}")
            Logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新本地缓存
        if name in self._local_cache:
            del self._local_cache[name]
        Logger.info(f"Successfully removed Chocolatey package: {name}")

    def _check_existence(self, name: str, context) -> bool:
        """
        检查包是否安装
        :param name: 包名
        :param context: 执行上下�?        :return: 是否存在
        """
        # 首先检查本地缓�?        self._refresh_cache(name, context)
        return name in self._local_cache

    def get_installed_package_version(self, package_name: str) -> Optional[str]:
        """获取已安装包的版�?""
        # 忽略context使用默认参数
        self._refresh_cache(package_name)
        return self._local_cache.get(package_name)
    
    def _refresh_cache(self, package_name: str = None, context = None) -> None:
        """刷新本地包缓�?""
        # 构建列表命令
        cmd = ["cmd", "/c", "choco", "list", "--local-only", "--limit-output"]
        if self.properties.use_pre_releases:
            cmd.append("--pre")
        if context and context.log_output:
            cmd.append("-v")
            cmd.append("-d")
        
        # 执行命令
        runner = shellRunner(
            timeout=30,
            max_output_size=self.properties.max_output_size
        )
        res = runner.run(cmd)
        
        # 处理失败
        if res["exitCode"] != 0:
            Logger.warning(
                f"Failed to list Chocolatey packages. "
                f"Exit code: {res['exitCode']}, "
                f"Error: {res.get('error', '')[:500]}")
            return
        
        # 解析输出
        self._local_cache = {}
        lines = res["output"].splitlines()
        
        for line in lines:
            match = re.match(r"^(?P<name>\S+)\|(?P<version>[\w\.\-]+)\|", line)
            if match:
                pkg_name = match.group("name")
                version = match.group("version")
                self._local_cache[pkg_name] = version
            elif package_name and package_name.lower() in line.lower():
                Logger.debug(f"Failed to parse Chocolatey package line: {line}")

    def list_installed_packages(self, context = None) -> Dict[str, str]:
        """获取所有已安装包的列表"""
        self._refresh_cache(context=context)
        return self._local_cache.copy()

    def package_info(self, name: str, include_dependencies: bool = False) -> Dict:
        """获取包的详细信息，包含依赖关�?""
        # 构建info命令
        cmd = CHOCO_INFO_CMD[2:] + [name, "--detail"]
        cmd.append("--no-progress")
        
        # 是否包含依赖
        if include_dependencies:
            cmd.append("--include-dependencies")
        
        # 执行命令
        runner = shellRunner(
            timeout=60,
            max_output_size=self.properties.max_output_size
        )
        res = runner.run(["cmd", "/c"] + cmd)
        
        # 解析结果
        if res["exitCode"] != 0:
            Logger.warning(
                f"Failed to get Chocolatey package info for {name}. "
                f"Exit code: {res['exitCode']}, "
                f"Error: {res.get('error', '')[:500]}")
            return {}
        
        return self._parse_package_info(res["output"])

    def _parse_package_info(self, output: str) -> Dict:
        """解析详细包信�?""
        info = {}
        current_category = ""
        
        for line in output.splitlines():
            if not line.strip():
                continue
                
            # 类别标签
            if '[' in line and ']' in line:
                current_category = re.search(r"\[(\w+)\]", line).group(1).lower()
                info[current_category] = {}
                continue
                
            # 分隔�?            if line.startswith('----'):
                continue
                
            # 键值对
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                if current_category:
                    info[current_category][key] = value
                else:
                    info[key] = value
        
        return info

    def upgrade_all_packages(self, context) -> bool:
        """升级所有可更新的包"""
        # 构建升级命令
        cmd = CHOCO_UPGRADE_CMD[2:] + ["all"]
        cmd.append("--no-progress")
        cmd.append("--yes")
        if self.properties.use_pre_releases:
            cmd.append("--pre")
        if context.log_output:
            cmd.append("-v")
            cmd.append("-d")
        
        # 执行升级
        runner = shellRunner(
            timeout=600,  # 较长超时
            max_retry=self.properties.retry_count,
            retry_delay=self.properties.retry_delay
        )
        res = runner.run(["cmd", "/c"] + cmd)
        
        if res["exitCode"] not in (0, 1641, 3010):
            Logger.error(
                f"Failed to upgrade all Chocolatey packages. "
                f"Exit code: {res['exitCode']}, "
                f"Error: {res.get('error', '')[:500]}")
            return False
        
        # 更新整个缓存
        self._refresh_cache(context=context)
        Logger.info("All Chocolatey packages upgraded successfully")
        return True

    def search_package(self, pattern: str, include_pre: bool = True) -> Dict[str, str]:
        """在配置的源中搜索�?""
        # 构建搜索命令
        cmd = CHOCO_LIST_CMD[2:] + ["--all-versions", "--limit-output"]
        cmd.append("--by-id-only")
        if include_pre:
            cmd.append("--pre")
        
        # 执行搜索
        runner = shellRunner(
            timeout=180,
            max_output_size=self.properties.max_output_size
        )
        res = runner.run(["cmd", "/c"] + cmd)
        
        # 解析结果
        package_versions = {}
        if res["exitCode"] == 0:
            for line in res["output"].splitlines():
                match = re.match(r"^(?P<name>\S+)\|(?P<version>[\w\.\-]+)(?:\||$)", line)
                if match and pattern.lower() in match.group("name").lower():
                    package_versions[match.group("name")] = match.group("version")
        
        return package_versions

    def list_available_updates(self, context = None) -> Dict[str, str]:
        """列出所有可用的更新"""
        # 构建命令
        cmd = CHOCO_UPGRADE_CMD[2:] + ["all", "--noop", "--limit-output"]
        cmd.append("--no-progress")
        if self.properties.use_pre_releases:
            cmd.append("--pre")
        if context and context.log_output:
            cmd.append("-v")
            cmd.append("-d")
        
        # 执行命令
        runner = shellRunner(
            timeout=120,
            max_output_size=self.properties.max_output_size
        )
        res = runner.run(["cmd", "/c"] + cmd)
        
        # 解析输出
        available_updates = {}
        if res["exitCode"] == 0:
            for line in res["output"].splitlines():
                match = re.match(r"^(?P<name>\S+)\|(?P<version>[\w\.\-]+)(?:\||$)", line)
                if match:
                    package_name = match.group("name")
                    new_version = match.group("version")
                    old_version = self.get_installed_package_version(package_name)
                    
                    if old_version and old_version != new_version:
                        available_updates[package_name] = {
                            "current": old_version,
                            "available": new_version
                        }
        
        return available_updates
