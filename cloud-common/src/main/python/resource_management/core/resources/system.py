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


__all__ = ["File", "Directory", "Link", "Execute", "ExecuteScript", "Mount"]

import subprocess
from typing import Optional, Dict, Any, List, Union, Callable, TYPE_CHECKING
from resource_management.core.signal_utils import TerminateStrategy
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
DEFAULT_TIMEOUT_KILL_STRATEGY = TerminateStrategy.TERMINATE_PARENT
DEFAULT_EXECUTE_TRIES = 1
DEFAULT_EXECUTE_TRY_SLEEP = 0  # �?DEFAULT_MOUNT_DUMP = 0
DEFAULT_MOUNT_PASSNO = 2
DEFAULT_MOUNT_OPTIONS = ["defaults"]

class File(Resource):
    """
    文件资源管理�?    
    管理文件的生命周期：创建、删除、内容写入、权限设置�?    支持文件备份、编码指定和访问权限控制�?    
    属性详解：
        path: 文件路径（默认使用资源名称）
        content: 文件内容（字符串或字节）
        mode: 权限模式（如 '0644'�?        owner: 所有者（用户名或 UID�?        group: 所属组（组名或 GID�?        backup: 备份数量（保留的历史版本�?        replace: 是否替换已存在但内容不同的文�?        encoding: 文件编码（如 'utf-8'�?        cd_access: 目录访问权限（u/g/o/a 组合�?    
    支持动作�?        create: 创建或更新文�?        delete: 删除文件
    """
    
    action = ForcedListArgument(default="create")
    path = ResourceArgument(default=lambda obj: obj.name)
    backup = ResourceArgument()
    mode = ResourceArgument()
    owner = ResourceArgument()
    group = ResourceArgument()
    content = ResourceArgument()
    replace = ResourceArgument(default=True)
    encoding = ResourceArgument()
    cd_access = ResourceArgument()
    
    actions = Resource.actions + ["create", "delete"]
    
    def __init__(self, name: str, **kwargs: Any) -> None:
        Logger.info(f"创建 File 资源: {name}")
        super().__init__(name, **kwargs)


class Directory(Resource):
    """
    目录资源管理�?    
    管理目录的生命周期，支持递归创建、权限传播和安全模式�?    提供强大的递归权限设置功能（但需谨慎使用）�?    
    核心功能�?        create_parents: 自动创建父目录（类似 mkdir -p�?        recursive_ownership: 递归设置所有权（危险操作）
        recursive_mode_flags: 递归模式标志（文�?目录区分�?        safemode_folders: 禁止递归操作的关键目录列�?        recursion_follow_links: 递归时是否跟随符号链�?    
    安全警告�?        recursive_ownership �?recursive_mode_flags 可能严重损坏系统�?        特别是在根目录或系统目录上使用时。仅在最后手段时使用�?    """
    
    action = ForcedListArgument(default="create")
    path = ResourceArgument(default=lambda obj: obj.name)
    mode = ResourceArgument()
    owner = ResourceArgument()
    group = ResourceArgument()
    follow = BooleanArgument(default=True)
    create_parents = BooleanArgument(default=False)
    cd_access = ResourceArgument()
    recursive_ownership = BooleanArgument(default=False)
    recursive_mode_flags = ResourceArgument(default=None)
    
    # 安全模式：禁止递归操作的关键系统目�?    safemode_folders = ForcedListArgument(
        default=[
            "/",
            "/bin",
            "/sbin",
            "/etc",
            "/dev",
            "/proc",
            "/var",
            "/usr",
            "/home",
            "/boot",
            "/lib",
            "/opt",
            "/mnt",
            "/media",
            "/srv",
            "/root",
            "/sys",
        ]
    )
    
    recursion_follow_links = BooleanArgument(default=False)
    
    actions = Resource.actions + ["create", "delete"]
    
    def __init__(self, name: str, **kwargs: Any) -> None:
        Logger.info(f"创建 Directory 资源: {name}")
        super().__init__(name, **kwargs)


class Link(Resource):
    """
    链接资源管理�?    
    管理符号链接和硬链接的创建与删除�?    
    属性：
        to: 链接目标路径（必需�?        hard: 是否为硬链接（默�?False，即符号链接�?    
    示例�?        Link("/usr/bin/python3", to="/usr/bin/python3.8")
        Link("/data/file", to="/mnt/storage/file", hard=True)
    """
    
    action = ForcedListArgument(default="create")
    path = ResourceArgument(default=lambda obj: obj.name)
    to = ResourceArgument(required=True)
    hard = BooleanArgument(default=False)
    
    actions = Resource.actions + ["create", "delete"]
    
    def __init__(self, name: str, **kwargs: Any) -> None:
        Logger.info(f"创建 Link 资源: {name} -> {kwargs.get('to', 'unknown')}")
        super().__init__(name, **kwargs)


class Execute(Resource):
    """
    命令执行资源�?    
    执行 shell 命令或程序，提供丰富的控制选项�?    
    核心功能�?        command: 命令（元组推荐，避免转义问题�?        sudo: 是否�?sudo 执行
        user: 指定执行用户
        environment: 环境变量字典
        cwd: 工作目录（注�?sudo 限制�?        timeout: 超时时间（秒�?        timeout_kill_strategy: 超时终止策略
        tries/try_sleep: 重试机制
        logoutput: 输出日志级别控制
        creates: 文件存在性检查（避免重复执行�?        returns: 期望的退出码列表
        wait_for_finish: 是否等待命令完成
        on_new_line: 实时输出处理回调
        on_timeout: 超时处理回调
    
    安全特性：
        支持 TerminateStrategy 控制进程终止方式
        安全处理 stdout/stderr 重定�?    """
    
    action = ForcedListArgument(default="run")
    command = ResourceArgument(default=lambda obj: obj.name)
    creates = ResourceArgument()
    cwd = ResourceArgument()
    environment = ResourceArgument(default={})
    user = ResourceArgument()
    returns = ForcedListArgument(default=0)
    tries = ResourceArgument(default=DEFAULT_EXECUTE_TRIES)
    try_sleep = ResourceArgument(default=DEFAULT_EXECUTE_TRY_SLEEP)
    path = ForcedListArgument(default=[])
    on_new_line = ResourceArgument()
    logoutput = ResourceArgument(default=None)
    timeout = ResourceArgument()
    on_timeout = ResourceArgument()
    wait_for_finish = BooleanArgument(default=True)
    sudo = BooleanArgument(default=False)
    stdout = ResourceArgument(default=subprocess.PIPE)
    stderr = ResourceArgument(default=subprocess.STDOUT)
    timeout_kill_strategy = ResourceArgument(default=DEFAULT_TIMEOUT_KILL_STRATEGY)
    
    actions = Resource.actions + ["run"]
    
    def __init__(self, name: Union[str, tuple], **kwargs: Any) -> None:
        # 安全处理命令显示（避免过长）
        cmd_display = name if isinstance(name, str) else ' '.join(map(str, name))[:50]
        Logger.info(f"创建 Execute 资源: {cmd_display}...")
        super().__init__(name, **kwargs)


class ExecuteScript(Resource):
    """
    脚本执行资源�?    
    直接执行内联脚本代码，无需独立脚本文件�?    
    属性：
        code: 脚本代码（必需�?        interpreter: 解释器路径（默认 /bin/bash�?        cwd: 工作目录
        environment: 环境变量
        user: 执行用户
        group: 执行�?    
    示例�?        ExecuteScript("install.sh",
            code="apt-get update && apt-get install -y nginx",
            interpreter="/bin/bash"
        )
    """
    
    action = ForcedListArgument(default="run")
    code = ResourceArgument(required=True)
    cwd = ResourceArgument()
    environment = ResourceArgument()
    interpreter = ResourceArgument(default="/bin/bash")
    user = ResourceArgument()
    group = ResourceArgument()
    
    actions = Resource.actions + ["run"]
    
    def __init__(self, name: str, **kwargs: Any) -> None:
        Logger.info(f"创建 ExecuteScript 资源: {name}")
        super().__init__(name, **kwargs)


class Mount(Resource):
    """
    文件系统挂载资源�?    
    管理文件系统的挂载、卸载、重新挂载和 fstab 配置�?    
    属性详解：
        mount_point: 挂载点（默认使用资源名称�?        device: 设备路径（如 /dev/sdb1�?        fstype: 文件系统类型（如 ext4, xfs, nfs�?        options: 挂载选项列表（默�?["defaults"]�?        dump: dump 备份标志（默�?0�?        passno: fsck 检查顺序（默认 2�?    
    支持动作�?        mount: 立即挂载
        umount: 立即卸载
        remount: 重新挂载
        enable: 添加�?fstab
        disable: �?fstab 移除
    """
    
    action = ForcedListArgument(default="mount")
    mount_point = ResourceArgument(default=lambda obj: obj.name)
    device = ResourceArgument()
    fstype = ResourceArgument()
    options = ResourceArgument(default=DEFAULT_MOUNT_OPTIONS)
    dump = ResourceArgument(default=DEFAULT_MOUNT_DUMP)
    passno = ResourceArgument(default=DEFAULT_MOUNT_PASSNO)
    
    actions = Resource.actions + ["mount", "umount", "remount", "enable", "disable"]
    
    def __init__(self, name: str, **kwargs: Any) -> None:
        Logger.info(f"创建 Mount 资源: {name}")
        super().__init__(name, **kwargs)


# ===== 资源创建辅助函数（可选） =====

def create_file(env: 'Environment', name: str, **kwargs: Any) -> File:
    """
    快速创建文件资源的辅助函数
    
    Args:
        env: 资源环境
        name: 文件路径
        **kwargs: File 的其他属�?        
    Returns:
        File 实例
        
    示例�?        create_file(env, "/etc/my.conf", content="config=1", mode="0644")
    """
    Logger.info(f"快速创建文�? {name}")
    file_res = File(name, **kwargs)
    env.add_resource(file_res)
    return file_res


def create_directory(env: 'Environment', name: str, **kwargs: Any) -> Directory:
    """
    快速创建目录资源的辅助函数
    
    Args:
        env: 资源环境
        name: 目录路径
        **kwargs: Directory 的其他属�?        
    Returns:
        Directory 实例
        
    示例�?        create_directory(env, "/var/log/myapp", create_parents=True)
    """
    Logger.info(f"快速创建目�? {name}")
    dir_res = Directory(name, **kwargs)
    env.add_resource(dir_res)
    return dir_res


def execute_command(env: 'Environment', name: Union[str, tuple], **kwargs: Any) -> Execute:
    """
    快速执行命令的辅助函数
    
    Args:
        env: 资源环境
        name: 命令（字符串或元组）
        **kwargs: Execute 的其他属�?        
    Returns:
        Execute 实例
        
    示例�?        execute_command(env, ("systemctl", "restart", "nginx"), sudo=True)
    """
    Logger.info(f"快速执行命�? {name}")
    exec_res = Execute(name, **kwargs)
    env.add_resource(exec_res)
    return exec_res
