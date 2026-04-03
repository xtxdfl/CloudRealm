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

Kerberos 安全工具管理
"""

import os
import sys
import glob
import subprocess
from typing import Union, List, Optional
from distutils.spawn import find_executable as distutils_find

__all__ = ["get_kdestroy_path", "find_executable"]


def get_kdestroy_path(search_directories: Union[str, List[str], None] = None) -> Optional[str]:
    """
    在指定目录或默认路径中查找 kdestroy 可执行文件
    
    :param search_directories: 可选，指定搜索路径（逗号分隔的字符串或路径列表）
    :return: 找到的 kdestroy 可执行文件完整路径，未找到则返回 None
    
    示例:
    >>> get_kdestroy_path()
    '/usr/bin/kdestroy'
    >>> get_kdestroy_path('/custom/bin:/other/path')
    '/custom/bin/kdestroy'
    >>> get_kdestroy_path(['/custom/bin', '/other/path'])
    '/custom/bin/kdestroy'
    """
    return find_executable("kdestroy", search_directories)


def find_executable(
    executable_name: str,
    search_directories: Union[str, List[str], None] = None,
    validate: bool = True
) -> Optional[str]:
    """
    高级可执行文件查找工具
    
    :param executable_name: 要查找的可执行文件名称 (如 'kdestroy')
    :param search_directories: 可选，指定搜索路径（逗号分隔的字符串或路径列表）
    :param validate: 是否验证找到的可执行文件有效性（默认为 True）
    :return: 可执行文件的完整路径，未找到则返回 None
    """
    # 标准化输入参数
    directories = _normalize_search_directories(search_directories)
    candidates = []
    
    # 收集所有可能的候选路径
    if directories:
        # 检查给定目录
        candidates.extend(_find_in_directories(executable_name, directories))
    
    # 检查标准系统路径
    candidates.extend(_find_in_system_path(executable_name))
    
    # 检查特定平台常见路径
    candidates.extend(_find_in_common_locations(executable_name))
    
    # 过滤并验证候选路径
    for path in candidates:
        if path and (not validate or _validate_executable(path)):
            return path
    
    return None


def _normalize_search_directories(
    search_directories: Union[str, List[str], None]
) -> List[str]:
    """
    规范化搜索目录参数
    
    :param search_directories: 目录的字符串、列表或 None
    :return: 标准化目录列表
    """
    if search_directories is None:
        return []
    
    if isinstance(search_directories, str):
        # 处理逗号分隔和冒号分隔的路径字符串
        directories = []
        for sep in [":", ","]:
            if sep in search_directories:
                directories = search_directories.split(sep)
                break
        
        if not directories:
            directories = [search_directories]
    elif isinstance(search_directories, list):
        directories = search_directories
    else:
        raise TypeError("search_directories 必须是字符串、列表或 None")
    
    # 过滤并清理路径
    return list(filter(None, [os.path.abspath(p.strip()) for p in directories if p.strip()]))


def _find_in_directories(executable_name: str, directories: List[str]) -> List[str]:
    """
    在指定目录列表中查找可执行文件
    
    :param executable_name: 可执行文件名称
    :param directories: 要搜索的目录列表
    :return: 可能的路径列表
    """
    candidates = []
    for directory in directories:
        if not os.path.isdir(directory):
            continue
            
        # 检查基础路径
        exe_path = os.path.join(directory, executable_name)
        if os.path.isfile(exe_path):
            candidates.append(exe_path)
        
        # 检查常见扩展名 (尤其Windows)
        if sys.platform == "win32":
            for ext in [".exe", ".bat", ".cmd"]:
                ext_path = os.path.join(directory, executable_name + ext)
                if os.path.isfile(ext_path):
                    candidates.append(ext_path)
    
    return candidates


def _find_in_system_path(executable_name: str) -> List[str]:
    """
    在系统 PATH 环境变量中查找可执行文件
    
    :param executable_name: 可执行文件名称
    :return: 可能的路径列表
    """
    path = distutils_find(executable_name)
    return [path] if path else []


def _find_in_common_locations(executable_name: str) -> List[str]:
    """
    在特定平台的常用位置查找可执行文件
    
    :param executable_name: 可执行文件名称
    :return: 可能的路径列表
    """
    common_paths = []
    
    # Linux/Unix 常见路径
    if sys.platform.startswith("linux") or sys.platform in ["darwin", "freebsd"]:
        common_paths = [
            "/usr/bin",
            "/usr/sbin",
            "/bin",
            "/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
            "/opt/bin",
            "/opt/sbin"
        ]
    
    # Windows 常见路径
    elif sys.platform == "win32":
        program_dirs = os.getenv("ProgramFiles", "C:\\Program Files")
        common_paths = [
            os.path.join(program_dirs, "MIT", "Kerberos", "bin"),
            os.path.join(os.getenv("SystemRoot", "C:\\Windows"), "System32"),
            os.path.join(program_dirs, "Kerberos", "bin"),
            os.path.join(program_dirs, "SSSD", "bin"),
            os.path.join(program_dirs, "Cygwin", "bin")
        ]
    
    # 处理通配符模式
    expanded_paths = []
    for path in common_paths:
        # 处理通配符
        if "*" in path or "?" in path:
            expanded_paths.extend(glob.glob(path))
        else:
            expanded_paths.append(path)
    
    return _find_in_directories(executable_name, expanded_paths)


def _validate_executable(file_path: str) -> bool:
    """
    验证找到的可执行文件是否真实有效
    
    :param file_path: 待验证的文件路径
    :return: 是否有效可执行文件
    """
    try:
        # 基本文件存在且可执行检查
        if not os.access(file_path, os.X_OK) or not os.path.isfile(file_path):
            return False
            
        # Unix/Linux 系统特殊检查
        if sys.platform != "win32":
            import magic
            # 检查文件类型是否为可执行文件
            file_type = magic.from_file(file_path)
            return "executable" in file_type or "script" in file_type
    except:
        pass
    
    # 最后手段 - 尝试实际执行
    try:
        proc = subprocess.Popen(
            [file_path, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        _, _ = proc.communicate(timeout=5)
        return proc.returncode == 0
    except:
        return False


class KerberosToolManager:
    """Kerberos 工具管理类"""
    _cache = {}
    
    @classmethod
    def get_tool_path(cls, tool_name: str) -> Optional[str]:
        """获取Kerberos工具路径（带缓存）"""
        if tool_name not in cls._cache:
            valid_path = find_executable(tool_name)
            cls._cache[tool_name] = valid_path
        return cls._cache[tool_name]
    
    @classmethod
    def execute_kdestroy(cls, cache_file: Optional[str] = None) -> bool:
        """执行kdestroy命令清理Kerberos凭据缓存"""
        kdestroy_path = cls.get_tool_path("kdestroy")
        if not kdestroy_path:
            return False
            
        cmd = [kdestroy_path]
        if cache_file:
            cmd.extend(["-c", cache_file])
            
        try:
            subprocess.run(cmd, check=True, timeout=10)
            return True
        except subprocess.CalledProcessError:
            return False
        except subprocess.TimeoutExpired:
            return False

