#!/usr/bin/env python3

import os
import sys
import time
import random
import shutil
import tempfile
from typing import Optional, Union, List, Dict, Any, Callable, Tuple
from enum import IntEnum

from resource_management.core import shell
from resource_management.core.logger import Logger
from resource_management.core.exceptions import Fail
from cloud_commons.unicode_tolerant_fs import unicode_walk
from resource_management.core.utils import attr_to_bitmask


# 运行模式枚举
class RunMode(IntEnum):
    """运行模式"""
    ROOT = 0
    SUDO = 1


# 获取当前运行模式
RUN_MODE = RunMode.ROOT if os.geteuid() == 0 else RunMode.SUDO


# 文件类型位掩�?class FileType(IntEnum):
    """文件类型位掩�?""
    REGULAR = 0o100000  # S_IFREG
    DIRECTORY = 0o040000  # S_IFDIR
    LINK = 0o120000  # S_IFLNK


# 错误码常�?class ErrorCode(IntEnum):
    """系统错误�?""
    ENOENT = 2  # No such file or directory
    ENOTDIR = 20  # Not a directory
    ELOOP = 40  # Too many symbolic links


# Safemode 保护�?class SafemodeProtector:
    """
    递归操作安全保护�?    
    防止在系统关键目录执行递归操作，避免造成系统损害�?    """
    
    DEFAULT_SAFEMODE_FOLDERS = {
        "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/sys",
        "/usr", "/var", "/sbin", "/opt", "/root", "/home", "/run", "/tmp", "/media", "/mnt"
    }
    
    @staticmethod
    def validate_path(path: str, safemode_folders: Optional[List[str]] = None) -> None:
        """
        验证路径是否允许递归操作
        
        Args:
            path: 目标路径
            safemode_folders: 自定�?safemode 目录列表
            
        Raises:
            Fail: 当路径在 safemode 列表中时
        """
        abs_path = os.path.abspath(os.path.realpath(path))
        forbidden = set(safemode_folders) if safemode_folders else SafemodeProtector.DEFAULT_SAFEMODE_FOLDERS
        
        if abs_path in forbidden:
            raise Fail(
                f"拒绝�?safemode 目录执行递归操作: '{path}'\n"
                f"此操作可能造成系统损坏。如需继续，请显式修改 safemode_folders 参数�?
            )
        
        Logger.debug(f"路径递归操作验证通过: {path}")


# 元数据管理器
class MetadataManager:
    """
    文件元数据管理器
    
    集中管理属主、属组、权限设置，支持递归和非递归操作�?    """
    
    @staticmethod
    def chown(path: str, owner: Optional[pwd.struct_passwd], group: Optional[grp.struct_group]) -> None:
        """
        修改文件属主和属�?        
        Args:
            path: 目标路径
            owner: 用户对象（None 表示不修改）
            group: 组对象（None 表示不修改）
        """
        if RUN_MODE == RunMode.ROOT:
            uid = owner.pw_uid if owner else -1
            gid = group.gr_gid if group else -1
            if uid != -1 or gid != -1:
                os.chown(path, uid, gid)
        else:
            owner_str = owner.pw_name if owner else ""
            group_str = group.gr_name if group else ""
            if owner_str or group_str:
                shell.checked_call(["chown", f"{owner_str}:{group_str}", path], sudo=True)
    
    @staticmethod
    def chown_recursive(
        path: str,
        owner: Optional[pwd.struct_passwd],
        group: Optional[grp.struct_group],
        follow_links: bool = False
    ) -> None:
        """
        递归修改目录下所有文件的属主和属�?        
        Args:
            path: 目标目录
            owner: 用户对象
            group: 组对�?            follow_links: 是否跟随符号链接
        """
        if RUN_MODE == RunMode.ROOT:
            uid = owner.pw_uid if owner else -1
            gid = group.gr_gid if group else -1
            
            if uid == -1 and gid == -1:
                return
            
            for root, dirs, files in unicode_walk(path, followlinks=True):
                for name in files + dirs:
                    try:
                        full_path = os.path.join(root, name)
                        if follow_links:
                            os.chown(full_path, uid, gid)
                        else:
                            os.lchown(full_path, uid, gid)
                    except OSError as ex:
                        # 处理竞争条件：文件在遍历过程中被删除
                        if ex.errno != ErrorCode.ENOENT:
                            raise
        else:
            owner_str = owner.pw_name if owner else ""
            group_str = group.gr_name if group else ""
            if owner_str or group_str:
                flags = ["-R"]
                if follow_links:
                    flags.append("-L")
                shell.checked_call(["chown"] + flags + [f"{owner_str}:{group_str}", path], sudo=True)
    
    @staticmethod
    def chmod(path: str, mode: int) -> None:
        """
        设置文件权限
        
        Args:
            path: 目标路径
            mode: 八进制权限（�?0o755�?        """
        if RUN_MODE == RunMode.ROOT:
            os.chmod(path, mode)
        else:
            mode_str = str(oct(mode))[2:]  # 移除 '0o' 前缀
            shell.checked_call(["chmod", mode_str, path], sudo=True)
    
    @staticmethod
    def chmod_extended(path: str, mode_str: str) -> None:
        """
        使用符号模式设置权限
        
        Args:
            path: 目标路径
            mode_str: 符号模式（如 'u+rwx,g+rx'�?        """
        if RUN_MODE == RunMode.ROOT:
            st = os.stat(path)
            new_mode = attr_to_bitmask(mode_str, initial_bitmask=st.st_mode)
            os.chmod(path, new_mode)
        else:
            shell.checked_call(["chmod", mode_str, path], sudo=True)
    
    @staticmethod
    def chmod_recursive(
        path: str,
        recursive_mode_flags: Dict[str, str],
        follow_links: bool = False
    ) -> None:
        """
        递归设置目录下文件和目录的权�?        
        Args:
            path: 目标目录
            recursive_mode_flags: 权限标志字典，格�?{'d': '...', 'f': '...'}
            follow_links: 是否跟随符号链接
        """
        # 验证参数
        for key, value in recursive_mode_flags.items():
            if key not in ('d', 'f'):
                raise Fail(f"recursive_mode_flags 键必须为 'd' �?'f'，找�? '{key}'")
        
        if RUN_MODE == RunMode.ROOT:
            dir_flag = recursive_mode_flags.get("d")
            file_flag = recursive_mode_flags.get("f")
            
            for root, dirs, files in unicode_walk(path, followlinks=follow_links):
                if dir_flag:
                    for dir_name in dirs:
                        full_path = os.path.join(root, dir_name)
                        new_mode = attr_to_bitmask(dir_flag, initial_bitmask=os.stat(full_path).st_mode)
                        os.chmod(full_path, new_mode)
                
                if file_flag:
                    for file_name in files:
                        full_path = os.path.join(root, file_name)
                        new_mode = attr_to_bitmask(file_flag, initial_bitmask=os.stat(full_path).st_mode)
                        os.chmod(full_path, new_mode)
        else:
            # 使用 find 命令递归设置
            find_flags = ["-L"] if follow_links else []
            for key, flags in recursive_mode_flags.items():
                shell.checked_call(
                    ["find"] + find_flags + [path, "-type", key, "-exec", "chmod", flags, "{}", "+"]
                )
    
    @staticmethod
    def set_cd_access(path: str, cd_access: str) -> None:
        """
        为路径的所有父目录设置执行权限
        
        Args:
            path: 目标路径
            cd_access: 访问控制字符串（�?'u' 表示用户�?        """
        if not re.match(r"^[ugoa]+$", cd_access):
            raise Fail(f"cd_access 格式无效: '{cd_access}'，只能包�?ugoa")
        
        dir_path = os.path.normpath(path)
        Logger.debug(f"设置 cd 访问权限: {cd_access}+rx for {path}")
        
        while dir_path and dir_path != os.sep:
            if PathChecker.is_dir(dir_path):
                MetadataManager.chmod_extended(dir_path, f"{cd_access}+rx")
                Logger.debug(f"  已设�? {dir_path}")
            dir_path = os.path.dirname(dir_path)


# 临时文件管理�?class TempFileManager:
    """
    临时文件管理�?    
    负责创建临时文件并执行原子性移动�?    """
    
    @staticmethod
    def create_temp_path(prefix: str = "resource_management-") -> str:
        """
        生成唯一的临时文件路�?        
        Returns:
            临时文件路径字符�?        """
        temp_dir = tempfile.gettempdir()
        timestamp = int(time.time() * 1000)  # 毫秒级时间戳
        random_part = random.randint(0, 999999)
        return f"{temp_dir}{os.sep}{prefix}{timestamp}_{random_part}.tmp"
    
    @staticmethod
    def atomic_write(
        final_path: str,
        content: Union[str, bytes],
        encoding: Optional[str] = None,
        on_created: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        原子性写入文�?        
        流程�?        1. 创建临时文件
        2. 写入内容
        3. 执行 on_created 回调（如设置权限�?        4. 移动到最终路�?        
        Args:
            final_path: 最终文件路�?            content: 文件内容
            encoding: 编码（字符串内容�?            on_created: 临时文件创建后的回调函数
        """
        temp_path = TempFileManager.create_temp_path()
        mode = "wb" if isinstance(content, bytes) else "w"
        
        try:
            # 写入临时文件
            with open(temp_path, mode, encoding=encoding) as fp:
                fp.write(content)
            
            Logger.debug(f"临时文件创建: {temp_path}")
            
            # 执行回调（如设置元数据）
            if on_created:
                on_created(temp_path)
                Logger.debug(f"临时文件回调执行完成: {temp_path}")
            
            # 原子性移动到最终位�?            TempFileManager.move(temp_path, final_path)
            Logger.debug(f"原子性移�? {temp_path} -> {final_path}")
        
        except Exception as ex:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise Fail(f"原子性写入失�? {final_path}: {ex}")
    
    @staticmethod
    def move(src: str, dst: str) -> None:
        """
        移动文件
        
        Args:
            src: 源路�?            dst: 目标路径
        """
        if RUN_MODE == RunMode.ROOT:
            shutil.move(src, dst)
        else:
            shell.checked_call(["mv", "-f", src, dst], sudo=True)


# 路径检查器
class PathChecker:
    """
    路径检查器
    
    提供各种路径类型检查�?    """
    
    @staticmethod
    def exists(path: str) -> bool:
        """检查路径是否存�?""
        if RUN_MODE == RunMode.ROOT:
            return os.path.exists(path)
        else:
            return shell.call(["test", "-e", path], sudo=True)[0] == 0
    
    @staticmethod
    def is_dir(path: str) -> bool:
        """检查路径是否为目录"""
        if RUN_MODE == RunMode.ROOT:
            return os.path.isdir(path)
        else:
            return shell.call(["test", "-d", path], sudo=True)[0] == 0
    
    @staticmethod
    def is_link(path: str) -> bool:
        """检查路径是否为符号链接"""
        if RUN_MODE == RunMode.ROOT:
            return os.path.islink(path)
        else:
            return shell.call(["test", "-L", path], sudo=True)[0] == 0
    
    @staticmethod
    def lexists(path: str) -> bool:
        """检查路径是否存在（包含符号链接�?""
        if RUN_MODE == RunMode.ROOT:
            return os.path.lexists(path)
        else:
            return shell.call(["test", "-e", path], sudo=True)[0] == 0
    
    @staticmethod
    def is_file(path: str) -> bool:
        """检查路径是否为普通文�?""
        if RUN_MODE == RunMode.ROOT:
            return os.path.isfile(path)
        else:
            return shell.call(["test", "-f", path], sudo=True)[0] == 0
    
    @staticmethod
    def readlink(path: str) -> str:
        """读取符号链接目标"""
        if RUN_MODE == RunMode.ROOT:
            return os.readlink(path)
        else:
            return shell.checked_call(["readlink", path], sudo=True)[1].strip()
    
    @staticmethod
    def stat(path: str) -> os.stat_result:
        """获取文件状�?""
        if RUN_MODE == RunMode.ROOT:
            return os.stat(path)
        else:
            cmd = ["stat", "-c", "%u %g %a", path]
            _, out, _ = shell.checked_call(cmd, sudo=True)
            uid_str, gid_str, mode_str = out.strip().split()
            # 模拟 os.stat_result
            stat_result = os.stat_result((
                int(mode_str, 8),  # st_mode
                0,  # st_ino
                0,  # st_dev
                0,  # st_nlink
                int(uid_str),  # st_uid
                int(gid_str),  # st_gid
                0,  # st_size
                0,  # st_atime
                0,  # st_mtime
                0,  # st_ctime
            ))
            return stat_result


# 其他工具函数
def listdir(path: str) -> List[str]:
    """列出目录内容"""
    if RUN_MODE == RunMode.ROOT:
        return os.listdir(path)
    else:
        if not PathChecker.is_dir(path):
            raise Fail(f"{path} 不是目录，无法列出内�?)
        
        _, out, _ = shell.checked_call(["ls", path], sudo=True)
        return out.splitlines()


def copy(src: str, dst: str) -> None:
    """复制文件或目�?""
    if RUN_MODE == RunMode.ROOT:
        shutil.copy(src, dst)
    else:
        shell.checked_call(["cp", "-r", src, dst], sudo=True)


def rmtree(path: str) -> None:
    """递归删除目录�?""
    if RUN_MODE == RunMode.ROOT:
        shutil.rmtree(path)
    else:
        shell.checked_call(["rm", "-rf", path], sudo=True)


def symlink(source: str, link_name: str) -> None:
    """创建符号链接"""
    if RUN_MODE == RunMode.ROOT:
        os.symlink(source, link_name)
    else:
        shell.checked_call(["ln", "-sf", source, link_name], sudo=True)


def link(source: str, link_name: str) -> None:
    """创建硬链�?""
    if RUN_MODE == RunMode.ROOT:
        os.link(source, link_name)
    else:
        shell.checked_call(["ln", "-f", source, link_name], sudo=True)


def unlink(path: str) -> None:
    """删除文件或链�?""
    if RUN_MODE == RunMode.ROOT:
        os.unlink(path)
    else:
        shell.checked_call(["rm", "-f", path], sudo=True)


def makedir(path: str, mode: int = 0o755) -> None:
    """创建目录"""
    if RUN_MODE == RunMode.ROOT:
        os.mkdir(path)
        os.chmod(path, mode)
    else:
        shell.checked_call(["mkdir", path], sudo=True)
        chmod(path, mode)


def makedirs(path: str, mode: int = 0o755) -> None:
    """
    递归创建目录
    
    Args:
        path: 目录路径
        mode: 权限模式
    """
    if RUN_MODE == RunMode.ROOT:
        try:
            os.makedirs(path, mode)
        except OSError as ex:
            if ex.errno == ErrorCode.ENOENT:
                dirname = os.path.dirname(ex.filename)
                if os.path.islink(dirname) and not os.path.exists(dirname):
                    raise Fail(f"无法创建目录 '{path}'，父目录 '{dirname}' 是损坏的符号链接")
            elif ex.errno == ErrorCode.ENOTDIR:
                dirname = os.path.dirname(ex.filename)
                if os.path.isfile(dirname):
                    raise Fail(f"无法创建目录 '{path}'，父路径 '{dirname}' 是文�?)
            elif ex.errno == ErrorCode.ELOOP:
                dirname = os.path.dirname(ex.filename)
                if os.path.islink(dirname) and not os.path.exists(dirname):
                    raise Fail(f"无法创建目录 '{path}'，父目录 '{dirname}' 是循环符号链�?)
            raise
    else:
        shell.checked_call(["mkdir", "-p", path], sudo=True)
        chmod(path, mode)


def kill(pid: int, signal: int) -> None:
    """发送信号给进程"""
    if RUN_MODE == RunMode.ROOT:
        os.kill(pid, signal)
    else:
        try:
            shell.checked_call(["kill", f"-{signal}", str(pid)], sudo=True)
        except Fail as ex:
            raise OSError(str(ex))


# ===== 绑定�?sudo 模块（保持向后兼容） =====
from resource_management.core import sudo

# 将函数绑定到 sudo 模块
sudo.chown = MetadataManager.chown
sudo.chown_recursive = MetadataManager.chown_recursive
sudo.chmod = MetadataManager.chmod
sudo.chmod_extended = MetadataManager.chmod_extended
sudo.chmod_recursive = MetadataManager.chmod_recursive
sudo.move = TempFileManager.move
sudo.copy = copy
sudo.makedirs = makedirs
sudo.makedir = makedir
sudo.symlink = symlink
sudo.link = link
sudo.unlink = unlink
sudo.rmtree = rmtree
sudo.create_file = TempFileManager.atomic_write
sudo.read_file = lambda path, encoding=None: open(path, 'rb').read() if RUN_MODE == RunMode.ROOT else read_file(path)
sudo.path_exists = PathChecker.exists
sudo.path_isdir = PathChecker.is_dir
sudo.path_islink = PathChecker.is_link
sudo.path_lexists = PathChecker.lexists
sudo.path_isfile = PathChecker.is_file
sudo.readlink = PathChecker.readlink
sudo.stat = PathChecker.stat
sudo.listdir = listdir
sudo.kill = kill
