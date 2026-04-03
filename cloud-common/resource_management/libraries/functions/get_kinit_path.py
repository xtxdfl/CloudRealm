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

Enhanced Kinit Executable Locator
"""

import os
import collections
import logging
from typing import Union, List, Optional, Tuple

__all__ = ["get_kinit_path"]

# 日志配置
logger = logging.getLogger('kinit_locator')
logger.setLevel(logging.INFO)

# 默认搜索路径
DEFAULT_SEARCH_PATHS = [
    '/usr/bin',
    '/bin',
    '/usr/sbin',
    '/sbin',
    '/usr/lib/mit/bin',
    '/usr/lib/mit/sbin',
    '/usr/kerberos/bin',
    '/usr/kerberos/sbin',
    '/opt/kerberos/bin'
]

# MIT krb5 bin 路径 (常见于源码编译)
MIT_KRB5_PATHS = [
    '/usr/local/bin'
]

# IBM AIX 特定路径
AIX_SPECIFIC_PATHS = [
    '/usr/krb5/bin'
]

def expand_search_directories(
    custom_dirs: Optional[Union[str, List[str]]] = None
) -> List[str]:
    """
    扩展和标准化搜索目录
    
    :param custom_dirs: 自定义目录字符串(逗号分隔)或列表
    :return: 唯一且有效的目录路径列表
    """
    # 初始化搜索路径集合
    search_paths = set()
    
    # 处理自定义路径
    if custom_dirs:
        if isinstance(custom_dirs, str):
            # 分割逗号分隔的字符串
            for path in custom_dirs.split(','):
                clean_path = path.strip()
                if clean_path:
                    search_paths.add(os.path.normpath(clean_path))
        elif isinstance(custom_dirs, list):
            for path in custom_dirs:
                if isinstance(path, str) and path.strip():
                    search_paths.add(os.path.normpath(path.strip()))
    
    # 添加默认路径
    for default_path in DEFAULT_SEARCH_PATHS:
        search_paths.add(os.path.normpath(default_path))
    
    # 添加平台特定路径
    for mit_path in MIT_KRB5_PATHS:
        search_paths.add(mit_path)
    
    # 添加AIX专用路径
    if os.uname().sysname == 'AIX':
        for aix_path in AIX_SPECIFIC_PATHS:
            search_paths.add(aix_path)
    
    # 添加PATH环境变量
    env_path = os.environ.get('PATH', '')
    for path in env_path.split(os.pathsep):
        clean_path = path.strip()
        if clean_path:
            search_paths.add(os.path.normpath(clean_path))
    
    # 返回有序且有效的路径
    valid_paths = []
    for path in search_paths:
        if os.path.isdir(path):
            valid_paths.append(path)
        else:
            logger.debug(f"排除无效搜索路径: {path}")
    
    # 基于优先级排序: 自定义路径 > 环境路径 > 默认路径
    ordered_paths = collections.OrderedDict()
    for path in valid_paths:
        ordered_paths[os.path.abspath(path)] = True
    
    return list(ordered_paths.keys())

def validate_kinit_executable(file_path: str) -> bool:
    """
    验证 kinit 可执行文件
    
    :param file_path: 候选文件路径
    :return: 是否是有效的可执行文件
    """
    return all([
        os.path.isfile(file_path),
        os.access(file_path, os.X_OK),
        # 附加安全验证(可选)
        file_path.endswith(('kinit', 'kinit.exe'))
    ])

def locate_kinit(
    search_directories: Optional[Union[str, List[str]]] = None
) -> Optional[str]:
    """
    在系统中定位 kinit 可执行文件
    
    :param search_directories: 自定义搜索路径(可选)
    :return: kinit 可执行文件的完整路径或 None
    """
    # 获取所有搜索路径
    search_paths = expand_search_directories(search_directories)
    
    logger.info(f"在以下路径中搜索 kinit 可执行文件: {search_paths}")
    
    # 搜索候选目录
    for directory in search_paths:
        candidate_path = os.path.join(directory, 'kinit')
        
        # Windows 支持
        if os.name == 'nt':
            candidate_path += '.exe'
            
        if os.path.exists(candidate_path) and validate_kinit_executable(candidate_path):
            logger.info(f"找到 kinit 可执行文件: {candidate_path}")
            return candidate_path
    
    # 尝试通过系统命令确定位置
    fallback_attempts = [
        ("which", "which kinit"),
        ("command", "command -v kinit"),
        ("where", "where kinit")  # Windows
    ]
    
    for util_cmd, find_cmd in fallback_attempts:
        try:
            logger.warning(f"尝试通过 {util_cmd} 定位 kinit")
            kinit_path = os.popen(find_cmd).read().strip()
            if kinit_path and os.path.exists(kinit_path):
                logger.info(f"通过 {util_cmd} 找到 kinit: {kinit_path}")
                return kinit_path
        except Exception:
            continue
    
    logger.error("无法在系统路径中找到 kinit 可执行文件")
    return None

def get_kinit_path(
    search_directories: Optional[Union[str, List[str]]] = None
) -> str:
    """
    获取系统 kinit 可执行文件路径
    
    :param search_directories: 自定义搜索路径(可选)
    :return: kinit 可执行文件的完整路径
    :raises EnvironmentError: 如果无法找到有效路径
    """
    # 首先尝试通过标准方法定位
    kinit_path = locate_kinit(search_directories)
    
    if kinit_path:
        return kinit_path
    
    # 错误报告和建议
    error_message = (
        "无法在系统中定位 kinit 可执行文件。\n"
        "可能原因: \n"
        "  1. Kerberos 客户端未正确安装\n"
        "  2. PATH 环境变量未包含 Kerberos bin 目录\n"
        "  3. 缺少执行权限\n\n"
        "解决建议: \n"
        "  - 安装 Kerberos 客户端软件包\n"
        "  - 确认 Kerberos bin 路径在系统 PATH 中\n"
        "  - 使用 search_directories 参数指定自定义路径"
    )
    
    logger.critical(error_message)
    raise EnvironmentError(error_message)

# ==================== 使用示例 ====================
if __name__ == "__main__":
    import logging
    
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 示例1: 使用默认路径搜索
    default_path = get_kinit_path()
    print(f"\n🎯 默认 kinit 路径: {default_path}")
    
    # 示例2: 使用自定义路径搜索
    custom_paths = "/custom/kerberos/bin,/alt/kerb/path"
    try:
        custom_kinit = get_kinit_path(custom_paths)
        print(f"🔍 在自定义路径中找到 kinit: {custom_kinit}")
    except EnvironmentError as e:
        print(f"❌ 自定义路径搜索失败: {str(e)}")
    
    # 示例3: 无有效路径情况
    try:
        get_kinit_path("/invalid/path")
    except EnvironmentError as e:
        print(f"⚠️ 预期中的错误: {str(e)}")

