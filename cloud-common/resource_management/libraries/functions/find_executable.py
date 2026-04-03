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

Advanced Executable Locator Utility
"""

import os
import logging
import platform
from typing import Union, List, Optional, Tuple
from resource_management.libraries.functions.find_path import find_path
from resource_management.core.exceptions import ExecutionFailed, ConfigurationError
from resource_management.core.logger import StructuredLogger

# 初始化结构化日志记录器
logger = StructuredLogger(__name__)

# 默认搜索路径（根据不同操作系统）
DEFAULT_UNIX_SEARCH_PATHS = (
    "/usr/bin",
    "/usr/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
    "/bin",
    "/sbin",
    "/opt/bin",
    "/opt/homebrew/bin"  # macOS Homebrew 路径
)

DEFAULT_KERBEROS_PATHS = (
    "/usr/kerberos/bin",
    "/usr/lib/mit/bin",
    "/usr/lib/mit/sbin",
    "/opt/sasl/bin",      # SASL 路径
    "/opt/krb5/bin"       # Kerberos 自定义安装路径
)

DEFAULT_WINDOWS_SEARCH_PATHS = (
    "C:\\Windows\\System32",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\Tools",
    "C:\\Apps"
)

def locate_executable(
    filename: str, 
    search_directories: Optional[Union[str, List[str]]] = None,
    *,
    use_defaults: bool = True,
    system_path: bool = False,
    file_extension_hint: Optional[str] = None,
    validate_executable: bool = True,
    symlink_follow: bool = True
) -> str:
    """
    在指定目录或默认路径中查找可执行文件
    
    此功能提供强大的可执行文件定位能力：
    1. 自动适应操作系统环境
    2. 支持自定义搜索路径
    3. 提供文件验证和拓展名检测
    4. 可选择扩展到系统PATH
    
    :param filename: 要查找的文件名 (如 'kinit', 'python3')
    :param search_directories: 自定义搜索目录 (字符串或列表)
    :param use_defaults: 是否包含默认搜索路径 (默认: 是)
    :param system_path: 是否扩展到系统PATH环境变量 (默认: 否)
    :param file_extension_hint: 文件拓展名提示 (例如: Windows下的'.exe')
    :param validate_executable: 是否验证文件可执行 (默认: 是)
    :param symlink_follow: 是否遵循符号链接 (默认: 是)
    :return: 找到的完整路径 或 原始文件名
    
    示例:
        locate_executable('kinit')
        locate_executable('ping', use_defaults=True, system_path=True)
    """
    # 记录操作上下文
    logger.info(f"定位可执行文件 '{filename}'", 
               custom_path=bool(search_directories),
               use_defaults=use_defaults,
               system_path=system_path)
    
    # 步骤1: 准备搜索路径列表
    normalized_dirs = prepare_search_paths(
        search_directories, 
        use_defaults, 
        system_path
    )
    
    # 步骤2: 处理文件拓展名
    candidate_names = generate_candidate_names(
        filename, 
        file_extension_hint
    )
    
    # 步骤3: 执行路径搜索
    actual_path = iterative_path_search(
        normalized_dirs, 
        candidate_names, 
        validate_executable,
        symlink_follow
    )
    
    # 步骤4: 处理结果
    return process_search_result(
        filename,
        actual_path,
        normalized_dirs
    )

def prepare_search_paths(
    custom_paths: Optional[Union[str, List[str]]], 
    use_defaults: bool, 
    include_system_path: bool
) -> List[str]:
    """
    准备规范化的搜索路径集合
    """
    search_paths = []
    
    # 自定义路径处理
    if custom_paths:
        if isinstance(custom_paths, str):
            search_paths.extend(sanitize_path_list(custom_paths))
        else:
            search_paths.extend(normalize_paths(custom_paths))
    
    # 默认路径处理
    if use_defaults:
        default_paths = get_os_specific_default_paths()
        search_paths.extend(default_paths)
    
    # 系统PATH处理
    if include_system_path:
        system_path = os.environ.get('PATH', '')
        search_paths.extend(sanitize_path_list(system_path))
    
    # 路径去重和过滤
    return normalize_and_deduplicate(search_paths)

def sanitize_path_list(path_str: str) -> List[str]:
    """
    清理并分割路径字符串
    """
    return [
        os.path.normpath(p.strip()) 
        for p in path_str.split(os.pathsep) 
        if p.strip()
    ]

def normalize_paths(path_list: List[str]) -> List[str]:
    """
    标准化路径列表
    """
    return [os.path.normpath(p) for p in path_list]

def get_os_specific_default_paths() -> Tuple[str]:
    """
    获取操作系统特定的默认搜索路径
    """
    current_os = platform.system().lower()
    
    if current_os == 'windows':
        return DEFAULT_WINDOWS_SEARCH_PATHS
    
    # Unix-like 系统 (Linux, macOS 等)
    unix_paths = list(DEFAULT_UNIX_SEARCH_PATHS)
    
    # 添加Kerberos路径 (仅Unix)
    if os.path.exists('/usr/kerberos') or any(os.path.exists(p) for p in DEFAULT_KERBEROS_PATHS):
        unix_paths.extend(DEFAULT_KERBEROS_PATHS)
    
    return tuple(unix_paths)

def normalize_and_deduplicate(path_list: List[str]) -> List[str]:
    """
    对路径列表进行规范化并去重
    """
    seen = set()
    normalized = []
    for path in path_list:
        abs_path = os.path.abspath(os.path.expanduser(path))
        # 仅保留真实存在的目录
        if os.path.isdir(abs_path) and abs_path not in seen:
            seen.add(abs_path)
            normalized.append(abs_path)
    return normalized

def generate_candidate_names(
    base_name: str, 
    extension_hint: Optional[str] = None
) -> List[str]:
    """
    生成可能的目标文件名列表
    """
    candidates = [base_name]
    
    # 添加拓展名变体 (针对Windows)
    if extension_hint and extension_hint not in base_name:
        candidates.append(f"{base_name}{extension_hint}")
    
    # 操作系统特定处理
    if os.name == 'nt':
        # 确保所有基础名称都有.exe变体
        if not base_name.endswith('.exe'):
            exe_candidate = f"{base_name}.exe"
            if exe_candidate not in candidates:
                candidates.append(exe_candidate)
    return candidates

def iterative_path_search(
    directories: List[str], 
    filenames: List[str],
    validate_exec: bool,
    follow_symlinks: bool
) -> Optional[str]:
    """
    在目录列表中搜索候选文件名
    """
    logger.debug("扫描可执行文件", directories=directories, candidates=filenames)
    
    for dir_path in directories:
        for candidate in filenames:
            candidate_path = os.path.join(dir_path, candidate)
            
            # 检查文件是否存在
            if not os.path.lexists(candidate_path):
                continue
                
            # 处理符号链接
            if follow_symlinks and os.path.islink(candidate_path):
                resolved_path = os.path.realpath(candidate_path)
                if os.path.isfile(resolved_path):
                    candidate_path = resolved_path
                else:
                    continue
            
            # 验证可执行性
            if validate_exec and not is_executable(candidate_path):
                continue
                
            return candidate_path
    
    return None

def is_executable(file_path: str) -> bool:
    """
    验证文件是否具有可执行权限
    """
    try:
        # 检查文件类型和权限
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)
    except OSError:
        return False

def process_search_result(
    original_name: str, 
    found_path: Optional[str], 
    search_paths: List[str]
) -> str:
    """
    处理并记录查找结果
    """
    if found_path:
        logger.info(f"找到可执行文件: '{original_name}' -> '{found_path}'", 
                   search_paths=search_paths[:5])
        return found_path
    
    logger.warning(f"未找到可执行文件: '{original_name}'", 
                 search_scopes=len(search_paths))
    return original_name

def discover_executable_paths(
    filename: str, 
    search_directories: Optional[Union[str, List[str]]] = None,
    include_versions: bool = True
) -> List[str]:
    """
    查找文件的所有可用版本
    
    :param filename: 目标文件名
    :param search_directories: 搜索目录集合
    :param include_versions: 是否包含不同版本
    :return: 发现的所有有效路径列表
    """
    # 准备搜索路径
    search_paths = prepare_search_paths(
        search_directories, 
        use_defaults=True, 
        include_system_path=True
    )
    
    # 生成文件名变体
    base_name = os.path.splitext(filename)[0]
    all_candidates = []
    
    if include_versions:
        # 模式匹配版本变体 (例如: python3.9, python3.10)
        all_candidates.extend([
            base_name + "*",
            base_name + "[0-9]*",
            base_name + ".[0-9]*"
        ])
    else:
        all_candidates = [filename]
    
    # 收集所有匹配的可执行文件
    found_paths = []
    for dir_path in search_paths:
        for pattern in all_candidates:
            try:
                files = os.path.join(dir_path, pattern)
                # 使用glob进行模式匹配
                import glob
                matches = glob.glob(files)
                
                for file_path in matches:
                    if is_executable(file_path):
                        found_paths.append(file_path)
            except:
                pass
    
    # 按版本排序 (如果适用)
    if include_versions:
        from distutils.version import LooseVersion
        found_paths.sort(key=lambda x: LooseVersion(os.path.basename(x)), reverse=True)
    
    return found_paths

def confirm_executable_version(
    executable_path: str,
    version_expression: Optional[str] = None,
    timeout: int = 15
) -> Tuple[bool, str]:
    """
    确认可执行文件的版本
    
    :param executable_path: 完整可执行文件路径
    :param version_expression: 期望版本 (正则表达式)
    :param timeout: 执行超时时间 (秒)
    :return: (是否匹配, 实际版本输出)
    """
    if not is_executable(executable_path):
        return False, "文件不可执行"
    
    # 基本的版本查询命令
    version_commands = [
        [executable_path, "--version"],
        [executable_path, "-version"],
        [executable_path, "-v"],
        [executable_path, "version"]
    ]
    
    for cmd in version_commands:
        try:
            import shlex
            import subprocess
            full_cmd = shlex.join(cmd)
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout.strip() or result.stderr.strip()
            if output and not "not found" in output.lower():
                # 如果没有指定版本表达式，直接返回成功
                if not version_expression:
                    return True, output
                
                # 检查版本匹配
                import re
                if re.search(version_expression, output, re.IGNORECASE):
                    return True, output
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return False, "无法验证版本"

def find_versioned_executable(
    base_name: str, 
    version_spec: Optional[str] = None,
    use_max: bool = True
) -> str:
    """
    查找符合版本要求的可执行文件
    
    :param base_name: 执行名称 (如: python, node)
    :param version_spec: 版本要求 (如: '>=3.8', '==16.0.x')
    :param use_max: 未指定版本时是否使用最新版本
    :return: 符合要求的可执行文件路径
    """
    # 查找所有可用版本
    all_versions = discover_executable_paths(
        base_name,
        None,
        include_versions=True
    )
    
    # 没有找到任何版本
    if not all_versions:
        return base_name
    
    # 没有版本要求 - 返回最新或最旧版本
    if not version_spec:
        return all_versions[0] if use_max else all_versions[-1]
    
    # 提取路径中的版本信息
    versioned_paths = []
    for path in all_versions:
        # 从路径中提取版本: /usr/bin/python3.9 -> ('python', '3.9')
        base, version = extract_version_from_path(path, base_name)
        if version:
            try:
                from packaging.version import parse as parse_ver
                versioned_paths.append((parse_ver(version), path))
            except:
                continue
    
    # 排序版本
    versioned_paths.sort(key=lambda x: x[0], reverse=True)
    
    # 应用版本要求
    try:
        from packaging.specifiers import SpecifierSet
        spec = SpecifierSet(version_spec)
        for ver, path in versioned_paths:
            if ver in spec:
                return path
    except:
        pass
    
    # 没有找到匹配版本 - 返回最接近的
    return all_versions[0]

def extract_version_from_path(path: str, base_name: str) -> Tuple[str, Optional[str]]:
    """
    从文件路径中提取版本号
    """
    filename = os.path.basename(path)
    base_prefix = base_name
    suffix = None
    
    # 检查简单版本模式 (如：python3.9)
    if filename.startswith(base_prefix):
        version_str = filename[len(base_prefix):].lstrip()
        return base_prefix, version_str
    
    # 检查带分隔符的版本 (如：python-3.9)
    dash_prefix = f"{base_prefix}-"
    if filename.startswith(dash_prefix):
        version_str = filename[len(dash_prefix):]
        return dash_prefix.rstrip('-'), version_str
    
    # 无法提取
    return path, None

# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 示例1: 基本查找
    print("'kinit' 的路径: ", locate_executable('kinit'))
    
    # 示例2: 带自定义路径的查找
    custom_paths = "/usr/local/sbin, /opt/bin"
    print("'nginx' 的路径: ", 
          locate_executable('nginx', search_directories=custom_paths))
    
    # 示例3: Windows系统查找
    if platform.system() == 'Windows':
        print("PowerShell的路径: ", 
              locate_executable('powershell', file_extension_hint='.exe'))
    
    # 示例4: 版本查找
    print("最新的Python版本: ", 
          find_versioned_executable('python3'))
    
    # 示例5: 发现所有python版本
    print("所有可用的Python版本:")
    for path in discover_executable_paths('python'):
        result, ver_info = confirm_executable_version(path)
        print(f"- {path}: {ver_info[:100]}...")

