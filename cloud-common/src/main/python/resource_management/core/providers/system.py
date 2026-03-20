#!/usr/bin/env python3

import re
import os
import time
import pwd
import grp
from typing import List, Optional, Dict, Union, Callable, Any, Pattern
from enum import IntEnum

from resource_management.core import shell, sudo
from resource_management.core.base import Fail
from resource_management.core.exceptions import ExecutionFailed, ExecuteTimeoutException
from resource_management.core.providers import Provider
from resource_management.core.logger import Logger


class FileType(IntEnum):
    """文件类型枚举"""
    REGULAR = 0o100000  # S_IFREG
    DIRECTORY = 0o40000  # S_IFDIR
    LINK = 0o120000  # S_IFLNK


class SafemodeProtector:
    """
    递归操作安全保护器
    
    防止在系统关键目录执行递归权限/属主修改，
    避免造成系统不可用。
    
    默认保护目录：/bin, /boot, /dev, /etc, /lib, /proc, /sys, /usr, /var
    """
    
    DEFAULT_SAFEMODE_FOLDERS = {
        "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/sys",
        "/usr", "/var", "/sbin", "/opt", "/root", "/home"
    }
    
    @staticmethod
    def validate_path(path: str, safemode_folders: List[str]) -> None:
        """
        验证路径是否允许递归操作
        
        实现逻辑：
        1. 将路径转换为绝对路径并标准化
        2. 检查是否在safemode列表中
        3. 匹配时抛出Fail异常
        
        参数:
            path: 目标路径
            safemode_folders: 禁止递归操作的目录列表
        
        异常: 当路径在safemode列表中时抛出Fail
        """
        abs_path = os.path.abspath(os.path.realpath(path))
        forbidden_paths = set(safemode_folders) if safemode_folders else SafemodeProtector.DEFAULT_SAFEMODE_FOLDERS
        
        if abs_path in forbidden_paths:
            raise Fail(
                f"拒绝在safemode目录执行递归操作: '{path}'\n"
                f"此操作可能损坏系统。如需继续，请显式修改safemode_folders参数。"
            )
        
        Logger.debug(f"路径递归操作验证通过: {path}")


class MetadataManager:
    """
    文件元数据管理器
    
    集中处理文件/目录的属主、属组、权限、扩展属性设置，
    支持递归操作和差异检测（仅修改变化的部分）。
    """
    
    # 权限标志位正则表达式（验证格式）
    _MODE_FLAGS_REGEX: Pattern = re.compile(
        r"^([ugoa]+[+=-][rwx]+,)*([ugoa]+[+=-][rwx]+)$"
    )
    
    @staticmethod
    def set_metadata(
        path: str,
        user: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[int] = None,
        cd_access: Optional[str] = None,
        recursive_ownership: bool = False,
        recursive_mode_flags: Optional[Dict[str, str]] = None,
        recursion_follow_links: bool = False,
        safemode_folders: Optional[List[str]] = None,
    ) -> None:
        """
        设置文件/目录元数据
        
        执行顺序：
        1. 属主/属组修改（可选递归）
        2. 权限修改（可选递归，文件/目录区分）
        3. 扩展权限（cd_access，为所有父目录添加+rx）
        
        参数说明：
        - path: 目标路径
        - user: 用户名或None（不修改）
        - group: 组名或None（不修改）
        - mode: 八进制权限（如0o755）或None
        - cd_access: 扩展访问控制（如"u"表示用户）
        - recursive_ownership: 是否递归修改属主/属组
        - recursive_mode_flags: 递归权限标志（如{"f":"u+rw", "d":"u+rwx"}）
        - recursion_follow_links: 递归时是否跟随符号链接
        - safemode_folders: safemode目录列表
        
        异常:
            - 用户/组不存在时抛出Fail
            - 递归路径在safemode中时抛出Fail
            - 权限格式无效时抛出Fail
        """
        # 获取用户/组实体信息
        user_entity = group_entity = None
        if user or group:
            stat = sudo.stat(path)
            
            if user:
                try:
                    user_entity = pwd.getpwnam(user)
                    if stat.st_uid != user_entity.pw_uid:
                        Logger.info(f"修改属主: {path} {stat.st_uid} -> {user}")
                    else:
                        user_entity = None  # 无需修改
                except KeyError:
                    raise Fail(f"用户不存在: '{user}'")
            
            if group:
                try:
                    group_entity = grp.getgrnam(group)
                    if stat.st_gid != group_entity.gr_gid:
                        Logger.info(f"修改属组: {path} {stat.st_gid} -> {group}")
                    else:
                        group_entity = None  # 无需修改
                except KeyError:
                    raise Fail(f"组不存在: '{group}'")
        
        # 递归修改属主/属组
        if recursive_ownership and (user_entity or group_entity):
            SafemodeProtector.validate_path(path, safemode_folders or [])
            sudo.chown_recursive(
                path,
                user_entity,
                group_entity,
                follow_links=recursion_follow_links
            )
        
        # 递归修改权限
        if recursive_mode_flags:
            MetadataManager._validate_recursive_mode_flags(recursive_mode_flags)
            SafemodeProtector.validate_path(path, safemode_folders or [])
            sudo.chmod_recursive(
                path,
                recursive_mode_flags,
                follow_links=recursion_follow_links
            )
        
        # 非递归修改属主/属组（顶层）
        if user_entity or group_entity:
            sudo.chown(path, user_entity, group_entity)
        
        # 修改权限（顶层）
        if mode is not None:
            stat = sudo.stat(path)
            if stat.st_mode != mode:
                Logger.info(f"修改权限: {path} {stat.st_mode:o} -> {mode:o}")
                sudo.chmod(path, mode)
        
        # 设置cd访问权限（为所有父目录添加+rx）
        if cd_access:
            MetadataManager._set_cd_access(path, cd_access)
    
    @staticmethod
    def _validate_recursive_mode_flags(flags: Dict[str, str]) -> None:
        """
        验证递归权限标志格式
        
        格式要求：
        - 必须是字典，键只能是"f"（文件）或"d"（目录）
        - 值必须是权限字符串格式：[ugoa...][[+-=][perms...]...
        
        异常: 格式无效时抛出Fail
        """
        if not isinstance(flags, dict):
            raise Fail(
                "recursive_mode_flags必须是字典，格式: {'f': 'u+rw', 'd': 'u+rwx'}"
            )
        
        for key, value in flags.items():
            if key not in ("f", "d"):
                raise Fail(
                    f"recursive_mode_flags包含无效键 '{key}'，只允许 'f' (文件) 或 'd' (目录)"
                )
            
            if not MetadataManager._MODE_FLAGS_REGEX.match(value):
                raise Fail(
                    f"权限标志格式无效 '{value}'，应为: [ugoa...][[+-=][rwx...]...]\n"
                    f"示例: u+rw,g+r,o+r"
                )
        
        Logger.debug(f"递归权限标志验证通过: {flags}")
    
    @staticmethod
    def _set_cd_access(path: str, cd_access: str) -> None:
        """
        设置目录cd访问权限
        
        实现逻辑：
        1. 验证cd_access格式（仅包含ugoa字符）
        2. 从给定路径向上遍历到根目录
        3. 对每个目录添加+rx权限
        
        参数:
            path: 起始路径
            cd_access: 访问控制字符串（如"u"表示用户）
        
        异常: 格式无效时抛出Fail
        """
        # 验证格式
        if not re.match(r"^[ugoa]+$", cd_access):
            raise Fail(f"cd_access格式无效 '{cd_access}'，只能包含ugoa字符")
        
        dir_path = os.path.normpath(path)
        Logger.debug(f"设置cd访问权限: {cd_access}+rx for path {path}")
        
        # 向上遍历所有父目录
        while dir_path and dir_path != os.sep:
            if sudo.path_isdir(dir_path):
                sudo.chmod_extended(dir_path, f"{cd_access}+rx")
                Logger.debug(f"  已设置: {dir_path}")
            
            dir_path = os.path.dirname(dir_path)


class FileProvider(Provider):
    """
    文件资源管理Provider
    
    提供文件的创建、内容更新和删除功能。
    核心特性：
    - 原子性写入（临时文件+rename）
    - 内容差异比对（避免无意义更新）
    - 文件存在性检查（与目录冲突检测）
    - 备份机制（replace=True时自动备份旧文件）
    """
    
    def action_create(self) -> None:
        """
        创建或更新文件
        
        执行流程：
        1. 路径有效性检查（不能是目录）
        2. 父目录存在性检查
        3. 内容差异比对（如果replace=True）
        4. 原子性写入（通过临时文件）
        5. 元数据同步（属主/属组/权限）
        
        特殊处理：
        - 如果content是可调用对象（函数），会动态执行获取内容
        - encoding参数控制文件编码（默认utf-8）
        - backup=True时，旧文件会备份到backup_file
        
        异常:
            - 路径是目录时抛出Fail
            - 父目录不存在时抛出Fail
            - 内容获取失败时抛出Fail
        """
        path = self.resource.path
        
        # 1. 路径不能是目录
        if sudo.path_isdir(path):
            raise Fail(f"无法创建文件，路径已存在且为目录: {path}")
        
        # 2. 父目录必须存在
        dirname = os.path.dirname(path)
        if not sudo.path_isdir(dirname):
            raise Fail(f"父目录不存在: {dirname}")
        
        # 3. 判断是否需要写入
        content = self._get_content()
        should_write = False
        reason = ""
        
        if not sudo.path_exists(path):
            should_write = True
            reason = "文件不存在"
        elif self.resource.replace:
            if content is not None:
                old_content = sudo.read_file(path, encoding=self.resource.encoding)
                if content != old_content:
                    should_write = True
                    reason = "内容不匹配"
                    # 备份旧文件
                    if getattr(self.resource, 'backup', False):
                        backup_path = self.resource.env.backup_file(path)
                        Logger.info(f"已备份旧文件到: {backup_path}")
        
        # 默认属主/属组
        owner = self.resource.owner or "root"
        group = self.resource.group or "root"
        
        if should_write:
            Logger.info(f"写入文件: {path} ({reason})")
            
            def on_file_created(filename: str) -> None:
                """临时文件创建后的回调，用于设置元数据"""
                MetadataManager.set_metadata(
                    filename,
                    user=owner,
                    group=group,
                    mode=self.resource.mode,
                    cd_access=self.resource.cd_access
                )
                Logger.debug(f"移动临时文件: {filename} -> {path}")
            
            # 原子性写入（先写临时文件再rename）
            sudo.create_file(
                path,
                content,
                encoding=self.resource.encoding,
                on_file_created=on_file_created
            )
        else:
            # 仅更新元数据
            Logger.debug(f"文件内容无变化，仅更新元数据: {path}")
            MetadataManager.set_metadata(
                path,
                user=owner,
                group=group,
                mode=self.resource.mode,
                cd_access=self.resource.cd_access
            )
    
    def action_delete(self) -> None:
        """
        删除文件
        
        执行流程：
        1. 检查路径是否为目录（不允许删除目录）
        2. 如果文件存在，执行删除
        
        异常: 路径是目录时抛出Fail
        """
        path = self.resource.path
        
        if sudo.path_isdir(path):
            raise Fail(f"无法删除，路径是目录而非文件: {path}")
        
        if sudo.path_exists(path):
            Logger.info(f"删除文件: {path}")
            sudo.unlink(path)
        else:
            Logger.debug(f"文件不存在，跳过删除: {path}")
    
    def _get_content(self) -> Union[str, bytes, None]:
        """
        获取文件内容
        
        支持类型：
        - str: 字符串内容
        - bytes: 二进制内容
        - Callable: 可调用对象（动态生成内容）
        - None: 无内容
        
        返回: 文件内容或None
        
        异常: 未知内容类型时抛出Fail
        """
        content = self.resource.content
        
        if content is None:
            return None
        elif isinstance(content, (str, bytes)):
            return content
        elif callable(content):
            # 动态生成内容（函数调用）
            result = content()
            Logger.debug(f"动态生成内容: {len(result)} bytes")
            return result
        
        raise Fail(f"未知的内容类型 {type(content)}: {content!r}")


class DirectoryProvider(Provider):
    """
    目录资源管理Provider
    
    提供目录的创建、递归元数据设置和删除功能。
    核心特性：
    - 自动创建父目录（create_parents=True）
    - 递归元数据设置（recursive_ownership/mode）
    - 符号链接循环检测
    - Safemode保护（防止操作系统目录被修改）
    """
    
    def action_create(self) -> None:
        """
        创建目录
        
        执行流程：
        1. 路径准备（处理符号链接）
        2. 目录创建（支持create_parents）
        3. 处理并发竞争（FileExists异常重试）
        4. 递归设置元数据（可选）
        
        特殊处理：
        - follow=True时，会解析符号链接链（循环检测）
        - create_parents=True时，自动创建所有父目录
        - 处理并发创建的竞争条件
        
        异常:
            - 路径存在但不是目录时抛出Fail
            - safemode路径递归操作时抛出Fail
            - 符号链接循环时抛出Fail
        """
        path = self.resource.path
        
        # 路径不存在时才创建
        if not sudo.path_exists(path):
            Logger.info(f"创建目录: {path}")
            
            # 处理符号链接链
            original_path = path
            if getattr(self.resource, 'follow', False):
                path = self._resolve_symlink_chain(path)
                if path != original_path:
                    Logger.info(f"解析符号链: {original_path} -> {path}")
            
            # 创建目录
            if getattr(self.resource, 'create_parents', False):
                sudo.makedirs(path, self.resource.mode or 0o755)
            else:
                self._create_single_directory(path)
        
        # 确保是目录
        if not sudo.path_isdir(path):
            raise Fail(f"路径存在但不是目录: {path}")
        
        # 设置元数据（可能递归）
        MetadataManager.set_metadata(
            path,
            user=self.resource.owner,
            group=self.resource.group,
            mode=self.resource.mode,
            cd_access=self.resource.cd_access,
            recursive_ownership=getattr(self.resource, 'recursive_ownership', False),
            recursive_mode_flags=getattr(self.resource, 'recursive_mode_flags', None),
            recursion_follow_links=getattr(self.resource, 'recursion_follow_links', False),
            safemode_folders=getattr(self.resource, 'safemode_folders', None)
        )
    
    def _resolve_symlink_chain(self, path: str) -> str:
        """
        解析符号链接链
        
        实现逻辑：
        1. 循环解析符号链接
        2. 检测循环链接（记录已访问路径）
        3. 相对路径转换为绝对路径
        
        参数:
            path: 起始路径（可能是符号链接）
        
        返回: 最终目标路径
        
        异常: 检测到循环链接时抛出Fail
        """
        visited = set()
        current_path = path
        
        while sudo.path_islink(current_path):
            if current_path in visited:
                raise Fail(f"符号链接循环检测: {path}")
            
            visited.add(current_path)
            prev_path = current_path
            current_path = sudo.readlink(current_path)
            
            # 相对路径处理
            if not os.path.isabs(current_path):
                current_path = os.path.join(os.path.dirname(prev_path), current_path)
        
        return current_path
    
    def _create_single_directory(self, path: str) -> None:
        """
        创建单层目录（不自动创建父目录）
        
        异常:
            - 父目录不存在时抛出Fail
            - 并发竞争时重试为makedirs
        """
        dirname = os.path.dirname(path)
        if not sudo.path_isdir(dirname):
            raise Fail(f"父目录不存在: {dirname}")
        
        try:
            sudo.makedir(path, self.resource.mode or 0o755)
        except Exception as ex:
            # 处理并发竞争：其他进程已创建
            if "File exists" in str(ex):
                Logger.warning(f"检测到并发创建，使用makedirs: {path}")
                sudo.makedirs(path, self.resource.mode or 0o755)
            else:
                raise
    
    def action_delete(self) -> None:
        """
        删除目录
        
        实现逻辑：
        1. 检查路径是否存在
        2. 确保是目录
        3. 递归删除（rmtree）
        
        注意：此操作会删除目录下所有内容！
        
        异常: 路径不是目录时抛出Fail
        """
        path = self.resource.path
        
        if not sudo.path_exists(path):
            Logger.debug(f"目录不存在，跳过删除: {path}")
            return
        
        if not sudo.path_isdir(path):
            raise Fail(f"无法删除，路径不是目录: {path}")
        
        Logger.info(f"删除目录及所有内容: {path}")
        sudo.rmtree(path)


class LinkProvider(Provider):
    """
    链接资源管理Provider
    
    提供符号链接和硬链接的创建与删除功能。
    核心特性：
    - 自动检测链接冲突
    - 支持硬链接（验证目标存在且非目录）
    - 原子性替换（先删除再创建）
    """
    
    def action_create(self) -> None:
        """
        创建链接
        
        执行流程：
        1. 检查链接是否已存在且正确
        2. 如果是符号链接，验证目标一致性
        3. 删除冲突链接（如果存在）
        4. 创建新链接（符号链接或硬链接）
        
        特殊处理：
        - 硬链接要求目标必须存在且不能是目录
        - 符号链接目标不存在时记录警告（允许悬空链接）
        
        异常:
            - 硬链接目标不存在或为目录时抛出Fail
            - 符号链接循环检测（通过os.path.realpath）
        """
        path = self.resource.path
        target = self.resource.to
        is_hard = getattr(self.resource, 'hard', False)
        
        # 链接已存在
        if sudo.path_lexists(path):
            if is_hard:
                # 硬链接：验证inode是否相同
                if os.path.samefile(path, target):
                    Logger.debug(f"硬链接已存在且正确: {path} -> {target}")
                    return
                raise Fail(f"硬链接冲突，路径已存在文件: {path}")
            else:
                # 符号链接：读取当前目标
                current_target = sudo.readlink(path)
                if current_target == target:
                    Logger.debug(f"符号链接已存在且正确: {path} -> {target}")
                    return
                
                # 目标不一致，删除旧链接
                Logger.info(f"替换符号链接: {path} ({current_target} -> {target})")
                sudo.unlink(path)
        
        # 创建硬链接
        if is_hard:
            if not sudo.path_exists(target):
                raise Fail(f"硬链接目标不存在: {target}")
            if sudo.path_isdir(target):
                raise Fail(f"无法为目录创建硬链接: {target}")
            
            Logger.info(f"创建硬链接: {path} -> {target}")
            sudo.link(target, path)
        else:
            # 创建符号链接（允许目标不存在）
            if not sudo.path_exists(target):
                Logger.warning(f"符号链接目标不存在（悬空链接）: {target}")
            
            Logger.info(f"创建符号链接: {path} -> {target}")
            sudo.symlink(target, path)
    
    def action_delete(self) -> None:
        """
        删除链接
        
        实现逻辑：
        1. 检查路径是否存在（包含符号链接）
        2. 执行删除
        
        注意：使用path_lexists检查符号链接（即使目标不存在）
        """
        path = self.resource.path
        
        if sudo.path_lexists(path):
            Logger.info(f"删除链接: {path}")
            sudo.unlink(path)
        else:
            Logger.debug(f"链接不存在，跳过删除: {path}")


class ExecuteProvider(Provider):
    """
    命令执行Provider
    
    提供强大的Shell命令执行功能，支持：
    - 环境变量注入
    - 用户身份切换
    - 超时控制
    - 重试机制
    - 实时输出捕获
    - 创建文件检测（creates参数）
    """
    
    def action_run(self) -> None:
        """
        执行命令
        
        执行流程：
        1. 检查creates文件是否存在（跳过执行）
        2. 构建执行上下文（环境变量、用户、超时等）
        3. 调用shell.checked_call执行
        4. 处理超时、重试等异常
        
        参数说明（通过resource）：
        - command: 命令字符串或列表
        - creates: 如果此文件存在则跳过执行
        - logoutput: 是否记录命令输出
        - cwd: 工作目录
        - environment: 环境变量字典
        - user: 执行用户
        - timeout: 超时时间（秒）
        - tries: 重试次数
        - try_sleep: 重试间隔（秒）
        - returns: 期望的返回码列表（默认[0]）
        
        异常:
            - 命令执行失败且返回码不在期望列表中时抛出Fail
            - 超时且未设置on_timeout时抛出ExecuteTimeoutException
        """
        # creates文件存在则跳过
        creates_path = getattr(self.resource, 'creates', None)
        if creates_path and sudo.path_exists(creates_path):
            Logger.info(f"跳过执行（creates文件已存在）: {creates_path}")
            return
        
        command = self.resource.command
        Logger.info(f"执行命令: {command}")
        
        # 构建执行参数
        exec_params = {
            'logoutput': getattr(self.resource, 'logoutput', True),
            'cwd': getattr(self.resource, 'cwd', None),
            'env': getattr(self.resource, 'environment', None),
            'user': getattr(self.resource, 'user', None),
            'wait_for_finish': getattr(self.resource, 'wait_for_finish', True),
            'timeout': getattr(self.resource, 'timeout', None),
            'on_timeout': getattr(self.resource, 'on_timeout', None),
            'path': getattr(self.resource, 'path', None),
            'sudo': getattr(self.resource, 'sudo', True),
            'timeout_kill_strategy': getattr(self.resource, 'timeout_kill_strategy', None),
            'on_new_line': getattr(self.resource, 'on_new_line', None),
            'stdout': getattr(self.resource, 'stdout', None),
            'stderr': getattr(self.resource, 'stderr', None),
            'tries': getattr(self.resource, 'tries', 1),
            'try_sleep': getattr(self.resource, 'try_sleep', 0),
            'returns': getattr(self.resource, 'returns', [0]),
        }
        
        try:
            result = shell.checked_call(command, **exec_params)
            Logger.info(f"命令执行成功: {command}")
            return result
        except ExecutionFailed as ex:
            raise Fail(f"命令执行失败: {command}\n返回码: {ex.code}\n输出: {ex.output}")
        except ExecuteTimeoutException:
            if exec_params['on_timeout']:
                Logger.warning(f"命令超时，执行回调: {command}")
                exec_params['on_timeout']()
            else:
                raise Fail(f"命令执行超时: {command}")


class ExecuteScriptProvider(Provider):
    """
    脚本执行Provider
    
    动态创建临时脚本文件并执行，执行后自动清理。
    适用于需要在远程节点执行复杂脚本的场景。
    """
    
    def action_run(self) -> None:
        """
        执行脚本代码
        
        执行流程：
        1. 创建临时脚本文件（带resource_management-script前缀）
        2. 写入脚本代码（code属性）
        3. 设置脚本文件元数据（属主/属组）
        4. 使用解释器执行脚本
        5. 临时文件自动清理
        
        必需资源属性：
        - code: 脚本代码字符串
        - interpreter: 解释器路径（如/bin/bash）
        
        可选属性：
        - user/group: 脚本文件属主/属组
        - cwd: 执行工作目录
        - environment: 环境变量
        
        异常: 脚本执行失败时抛出Fail
        """
        from tempfile import NamedTemporaryFile
        
        code = self.resource.code
        interpreter = self.resource.interpreter
        
        if not code or not interpreter:
            raise Fail("资源缺少必需属性: code 和 interpreter")
        
        Logger.info(f"执行脚本（{len(code)} bytes）: {self.resource}")
        
        # 创建临时脚本文件
        with NamedTemporaryFile(
            mode='w',
            prefix='resource_management-script-',
            suffix='.sh',
            delete=False
        ) as tf:
            tf.write(code)
            temp_script = tf.name
        
        try:
            # 设置脚本文件元数据
            MetadataManager.set_metadata(
                temp_script,
                user=getattr(self.resource, 'user', None),
                group=getattr(self.resource, 'group', None),
                mode=0o755  # 确保可执行
            )
            
            # 执行脚本
            shell.call(
                [interpreter, temp_script],
                cwd=getattr(self.resource, 'cwd', None),
                env=getattr(self.resource, 'environment', None),
                preexec_fn=self._preexec_fn()
            )
            
            Logger.info(f"脚本执行成功: {self.resource}")
        
        finally:
            # 清理临时文件
            if sudo.path_exists(temp_script):
                sudo.unlink(temp_script)
                Logger.debug(f"已清理临时脚本: {temp_script}")
    
    def _preexec_fn(self) -> Optional[Callable]:
        """
        获取预执行函数（用于设置进程属性）
        
        返回: 可调用对象或None
        """
        preexec = getattr(self.resource, 'preexec_fn', None)
        return preexec if callable(preexec) else None


# 向后兼容别名
# 保持与旧配置文件的兼容性
File = FileProvider
Directory = DirectoryProvider
Link = LinkProvider
Execute = ExecuteProvider
ExecuteScript = ExecuteScriptProvider

