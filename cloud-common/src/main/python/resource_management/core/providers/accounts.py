#!/usr/bin/env python3

import grp
import pwd
from typing import List, Optional, Dict, Any, Tuple, Callable
from resource_management.core import shell
from resource_management.core.providers import Provider
from resource_management.core.logger import Logger
from resource_management.core.utils import lazy_property
from resource_management.core.exceptions import ExecutionFailed, Fail


class UserProvider(Provider):
    """
    Linux用户管理Provider
    
    封装useradd/usermod/userdel命令，提供声明式用户管理接口。
    自动检测用户存在性，智能选择创建或修改模式。
    
    资源属性：
    - username (str): 用户名（必需）
    - comment (str): 用户描述（GECOS）
    - uid (int): 用户ID
    - gid (int/str): 主组ID或组名
    - groups (List[str]): 附加组列表
    - home (str): 主目录路径
    - shell (str): 登录Shell路径
    - password (str): 密码哈希值
    - system (bool): 是否为系统用户
    - fetch_nonlocal_groups (bool): 是否查询非本地组（LDAP等）
    - ignore_failures (bool): 是否忽略错误
    
    示例：
        UserProvider().action_create()  # 创建或更新用户
        UserProvider().action_remove()  # 删除用户
    """
    
    # useradd命令返回码：用户已存在
    USERADD_USER_ALREADY_EXISTS_EXITCODE = 9
    
    # 用户属性到命令行选项的映射
    # 格式: 属性名 -> (值获取函数, 命令行选项)
    _USER_OPTIONS: Dict[str, Tuple[Callable[['UserProvider'], Any], str]] = {
        "comment": (lambda self: self._existing_user.pw_gecos, "-c"),
        "gid": (lambda self: self._get_primary_group_name(), "-g"),
        "uid": (lambda self: self._existing_user.pw_uid, "-u"),
        "shell": (lambda self: self._existing_user.pw_shell, "-s"),
        "password": (lambda self: self._existing_user.pw_passwd, "-p"),
        "home": (lambda self: self._existing_user.pw_dir, "-d"),
        "groups": (lambda self: self._existing_additional_groups, "-G"),
    }
    
    @property
    def _existing_user(self) -> Optional[pwd.struct_passwd]:
        """
        获取已存在的用户对象
        
        返回: pwd.struct_passwd对象或None（用户不存在）
        
        异常: 不抛出异常，返回None表示用户不存在
        """
        try:
            return pwd.getpwnam(self.resource.username)
        except KeyError:
            return None
    
    @lazy_property
    def _existing_additional_groups(self) -> List[str]:
        """
        获取用户的附加组列表（不含主组）
        
        实现逻辑：
        1. 如果fetch_nonlocal_groups=True，使用grp.getgrall()查询所有组
        2. 否则仅解析/etc/group文件（性能更好）
        3. 过滤掉主组（pw_gid对应的组）
        
        返回: 附加组名称列表（去重且排序）
        
        注意：此属性为惰性加载，首次访问时计算并缓存
        """
        username = self.resource.username
        primary_gid = self._existing_user.pw_gid if self._existing_user else None
        
        if getattr(self.resource, 'fetch_nonlocal_groups', False):
            # 查询所有组（包括LDAP/NIS等非本地源）
            groups = [
                g.gr_name for g in grp.getgrall()
                if username in g.gr_mem and g.gr_gid != primary_gid
            ]
        else:
            # 仅解析/etc/group文件（性能更优）
            groups = []
            try:
                with open("/etc/group", "r") as fp:
                    for line in fp:
                        # 格式: groupname:password:gid:member1,member2
                        parts = line.strip().split(":")
                        if len(parts) >= 4 and parts[3]:
                            if username in parts[3].split(","):
                                try:
                                    gid = int(parts[2])
                                    if gid != primary_gid:
                                        groups.append(parts[0])
                                except ValueError:
                                    continue
            except IOError as e:
                Logger.warning(f"读取/etc/group失败: {e}")
        
        # 去重并排序
        unique_groups = sorted(set(groups))
        Logger.debug(f"用户 {username} 的附加组: {unique_groups}")
        return unique_groups
    
    def _get_primary_group_name(self) -> str:
        """
        获取用户主组名称
        
        返回: 主组名称字符串
        
        异常: 当无法解析主组时抛出ExecutionFailed
        """
        try:
            gid = self._existing_user.pw_gid
            return grp.getgrgid(gid).gr_name
        except KeyError:
            raise Fail(f"无法解析用户 {self.resource.username} 的主组GID: {gid}")
    
    def action_create(self) -> None:
        """
        创建或修改用户
        
        执行流程：
        1. 检查用户是否存在，决定使用useradd还是usermod
        2. 比对当前属性与目标属性，确定是否需要修改
        3. 构建命令行参数（过滤未变化属性）
        4. 执行命令（带sudo）
        5. 处理用户已存在的竞争条件
        
        特殊处理：
        - system=True时添加--system选项（仅创建时）
        - groups属性合并现有附加组（usermod场景）
        - 忽略uid未变化的场景（避免频繁修改）
        
        异常: 
            - 命令执行失败时抛出Fail
            - 用户不存在且创建失败时抛出Fail
        """
        existing_user = self._existing_user
        creating_user = (existing_user is None)
        
        if creating_user:
            # 创建新用户
            command = ["useradd", "-m"]  # -m: 创建主目录
            if getattr(self.resource, 'system', False):
                command.append("--system")
                Logger.debug(f"创建系统用户: {self.resource.username}")
            Logger.info(f"创建用户: {self.resource.username}")
        else:
            # 修改现有用户
            command = ["usermod"]
            Logger.info(f"修改用户: {self.resource.username}")
        
        # 检查是否有属性需要修改
        has_changes = False
        for attr_name, (getter, flag) in self._USER_OPTIONS.items():
            current_value = getter(self)
            desired_value = getattr(self.resource, attr_name, None)
            
            if desired_value is None:
                continue
            
            # 跳过uid未变化的场景（减少无意义的修改）
            if flag == "-u" and existing_user and current_value == desired_value:
                continue
            
            # 处理groups属性（需要合并现有附加组）
            if flag == "-G":
                # 构建完整组列表（新groups + 现有附加组）
                new_groups = set(desired_value)
                if existing_user and self._existing_additional_groups:
                    existing_additional = set(self._existing_additional_groups)
                    # 如果新组是现有附加组的子集，无需修改
                    if new_groups.issubset(existing_additional):
                        continue
                    # 保留现有附加组中未在新列表中的组
                    new_groups.update(existing_additional)
                
                option_value = ",".join(sorted(new_groups))
                if option_value:  # 非空才添加
                    command.extend([flag, option_value])
                    has_changes = True
                continue
            
            # 其他属性（非groups）
            if current_value != desired_value:
                option_value = str(desired_value)
                command.extend([flag, option_value])
                has_changes = True
        
        # 如果没有变化且是修改模式，直接返回
        if not creating_user and not has_changes:
            Logger.debug(f"用户 {self.resource.username} 属性无变化，跳过操作")
            return
        
        # 添加用户名参数
        command.append(self.resource.username)
        
        Logger.debug(f"执行命令: {' '.join(command)}")
        
        try:
            shell.checked_call(command, sudo=True)
            Logger.info(f"用户 {'创建' if creating_user else '修改'}成功: {self.resource.username}")
        except ExecutionFailed as ex:
            # 处理竞争条件：多进程同时创建用户
            if creating_user and ex.code == self.USERADD_USER_ALREADY_EXISTS_EXITCODE:
                Logger.warning(
                    f"检测到用户创建竞争条件，用户已存在: {self.resource.username}"
                )
                # 递归调用以修改现有用户
                self.action_create()
            else:
                raise Fail(
                    f"用户 {'创建' if creating_user else '修改'}失败 "
                    f"{self.resource.username}: {ex}"
                )
    
    def action_remove(self) -> None:
        """
        删除用户
        
        执行流程：
        1. 检查用户是否存在
        2. 执行userdel命令
        
        注意：不会删除用户主目录（userdel默认行为）
        如需删除，请在resource中配置remove_home=True
        
        异常: 当用户不存在或删除失败时抛出Fail
        """
        if not self._existing_user:
            Logger.debug(f"用户不存在，跳过删除: {self.resource.username}")
            return
        
        Logger.info(f"删除用户: {self.resource.username}")
        
        command = ["userdel", self.resource.username]
        
        # 是否删除主目录和邮箱
        if getattr(self.resource, 'remove_home', False):
            command.append("-r")  # -r: 删除主目录和邮箱
            Logger.debug(f"同时删除用户主目录: {self._existing_user.pw_dir}")
        
        try:
            shell.checked_call(command, sudo=True)
            Logger.info(f"用户删除成功: {self.resource.username}")
        except ExecutionFailed as ex:
            raise Fail(f"用户删除失败 {self.resource.username}: {ex}")


class GroupProvider(Provider):
    """
    Linux组管理Provider
    
    封装groupadd/groupmod/groupdel命令，提供声明式组管理接口。
    自动检测组存在性，智能选择创建或修改模式。
    
    资源属性：
    - group_name (str): 组名（必需）
    - gid (int): 组ID
    - password (str): 组密码（不推荐）
    
    示例：
        GroupProvider().action_create()  # 创建或更新组
        GroupProvider().action_remove()  # 删除组
    """
    
    # 组属性到命令行选项的映射
    _GROUP_OPTIONS: Dict[str, Tuple[Callable[['GroupProvider'], Any], str]] = {
        "gid": (lambda self: self._existing_group.gr_gid, "-g"),
        "password": (lambda self: self._existing_group.gr_passwd, "-p"),
    }
    
    @property
    def _existing_group(self) -> Optional[grp.struct_group]:
        """
        获取已存在的组对象
        
        返回: grp.struct_group对象或None（组不存在）
        
        异常: 不抛出异常，返回None表示组不存在
        """
        try:
            return grp.getgrnam(self.resource.group_name)
        except KeyError:
            return None
    
    def action_create(self) -> None:
        """
        创建或修改组
        
        执行流程：
        1. 检查组是否存在，决定使用groupadd还是groupmod
        2. 比对当前属性与目标属性，确定是否需要修改
        3. 构建命令行参数（过滤未变化属性）
        4. 执行命令（带sudo）
        
        注意：password属性极少使用（NIS/YP组密码）
        
        异常: 命令执行失败时抛出Fail
        """
        existing_group = self._existing_group
        creating_group = (existing_group is None)
        
        if creating_group:
            command = ["groupadd"]
            Logger.info(f"创建组: {self.resource.group_name}")
        else:
            command = ["groupmod"]
            Logger.info(f"修改组: {self.resource.group_name}")
        
        # 检查是否有属性需要修改
        has_changes = False
        for attr_name, (getter, flag) in self._GROUP_OPTIONS.items():
            current_value = getter(self)
            desired_value = getattr(self.resource, attr_name, None)
            
            if desired_value is not None and current_value != desired_value:
                command.extend([flag, str(desired_value)])
                has_changes = True
        
        # 如果没有变化且是修改模式，直接返回
        if not creating_group and not has_changes:
            Logger.debug(f"组 {self.resource.group_name} 属性无变化，跳过操作")
            return
        
        command.append(self.resource.group_name)
        
        Logger.debug(f"执行命令: {' '.join(command)}")
        
        try:
            shell.checked_call(command, sudo=True)
            Logger.info(f"组 {'创建' if creating_group else '修改'}成功: {self.resource.group_name}")
        except ExecutionFailed as ex:
            raise Fail(f"组 {'创建' if creating_group else '修改'}失败 {self.resource.group_name}: {ex}")
    
    def action_remove(self) -> None:
        """
        删除组
        
        执行流程：
        1. 检查组是否存在
        2. 执行groupdel命令
        
        注意：如果组是某个用户的主组，删除会失败
        
        异常: 当组不存在或删除失败时抛出Fail
        """
        if not self._existing_group:
            Logger.debug(f"组不存在，跳过删除: {self.resource.group_name}")
            return
        
        Logger.info(f"删除组: {self.resource.group_name}")
        
        command = ["groupdel", self.resource.group_name]
        
        try:
            shell.checked_call(command, sudo=True)
            Logger.info(f"组删除成功: {self.resource.group_name}")
        except ExecutionFailed as ex:
            if "is the primary group" in str(ex):
                raise Fail(
                    f"无法删除主组 {self.resource.group_name}，"
                    f"请先修改用户主组或删除相关用户"
                )
            else:
                raise Fail(f"组删除失败 {self.resource.group_name}: {ex}")


# 向后兼容别名
# 保持与旧配置文件的兼容性
User = UserProvider
Group = GroupProvider

