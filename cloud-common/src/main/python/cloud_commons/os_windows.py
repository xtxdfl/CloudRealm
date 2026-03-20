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

import ctypes
import getpass
import os
import random
import re
import shlex
import string
import subprocess
import sys
import tempfile
import time
import logging
import traceback

import win32api
import win32con
import win32event
import win32file
import win32net
import win32netcon
import win32process
import win32security
import win32service
import win32serviceutil
import winerror
import winioctlcon
import wmi

from typing import Tuple, Optional, Dict, Any, List, Union
from contextlib import contextmanager
from cloud_commons.exceptions import FatalException
from cloud_commons.logging_utils import logging_utils

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()],
    force=True
)
logger = logging.getLogger("WindowsUtils")

# --------------------- 常量定义 ---------------------
SERVICE_STATUS_UNKNOWN = "unknown"
SERVICE_STATUS_STARTING = "starting"
SERVICE_STATUS_RUNNING = "running"
SERVICE_STATUS_STOPPING = "stopping"
SERVICE_STATUS_STOPPED = "stopped"
SERVICE_STATUS_NOT_INSTALLED = "not installed"

ADMINISTRATORS_GROUP = "BUILTIN\\Administrators"
SYSTEM_USER = "NT AUTHORITY\\SYSTEM"
WHOAMI_GROUPS = "whoami /groups"

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
REPARSE_FOLDER = win32file.FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
REPARSE_TAGS = {
    winioctlcon.IO_REPARSE_TAG_SYMLINK: "symbolic",
    winioctlcon.IO_REPARSE_TAG_MOUNT_POINT: "mountpoint"
}

# --------------------- 系统信息获取 ---------------------
class OSVERSIONINFOEXW(ctypes.Structure):
    _fields_ = [
        ("dwOSVersionInfoSize", ctypes.c_ulong),
        ("dwMajorVersion", ctypes.c_ulong),
        ("dwMinorVersion", ctypes.c_ulong),
        ("dwBuildNumber", ctypes.c_ulong),
        ("dwPlatformId", ctypes.c_ulong),
        ("szCSDVersion", ctypes.c_wchar * 128),
        ("wServicePackMajor", ctypes.c_ushort),
        ("wServicePackMinor", ctypes.c_ushort),
        ("wSuiteMask", ctypes.c_ushort),
        ("wProductType", ctypes.c_byte),
        ("wReserved", ctypes.c_byte),
    ]

def get_windows_version() -> Tuple[int, int, int]:
    """获取Windows的主版本号、次版本号和内部版本�?""
    os_version = OSVERSIONINFOEXW()
    os_version.dwOSVersionInfoSize = ctypes.sizeof(os_version)
    if ctypes.windll.Ntdll.RtlGetVersion(ctypes.byref(os_version)) != 0:
        raise FatalException(
            winerror.ERROR_BAD_ENVIRONMENT,
            "Failed to retrieve Windows version"
        )
    return (os_version.dwMajorVersion, 
            os_version.dwMinorVersion, 
            os_version.dwBuildNumber)

def get_system_info() -> Dict[str, Any]:
    """获取详细的系统信�?""
    sys_info = wmi.WMI().Win32_ComputerSystem()[0]
    os_info = wmi.WMI().Win32_OperatingSystem()[0]
    
    return {
        "hostname": sys_info.Name,
        "manufacturer": sys_info.Manufacturer,
        "model": sys_info.Model,
        "os_name": os_info.Caption,
        "os_version": os_info.Version,
        "build_number": os_info.BuildNumber,
        "total_physical_memory": int(sys_info.TotalPhysicalMemory) if sys_info.TotalPhysicalMemory else 0,
        "number_of_processors": int(os_info.NumberOfProcessors),
        "system_type": sys_info.SystemType
    }

def get_windows_edition() -> str:
    """获取Windows版本名称"""
    major, minor, build = get_windows_version()
    
    versions = {
        (10, 0): "Windows 10" if build < 22000 else "Windows 11",
        (6, 3): "Windows 8.1",
        (6, 2): "Windows 8",
        (6, 1): "Windows 7",
        (6, 0): "Windows Vista",
        (5, 2): "Windows Server 2003",
        (5, 1): "Windows XP",
        (5, 0): "Windows 2000"
    }
    
    return versions.get((major, minor), f"Unknown Windows version ({major}.{minor})")

# --------------------- 文件系统操作 ---------------------
def win_symlink(source: str, link_name: str) -> None:
    """创建Windows符号链接"""
    if not source or not link_name:
        raise ValueError("Source and link name must be provided")
    
    flags = 0
    is_dir = os.path.isdir(source)
    if is_dir:
        flags = 1  # SYMBOLIC_LINK_FLAG_DIRECTORY
    
    # 获取CreateSymbolicLinkW函数的正确签�?    csl = ctypes.windll.kernel32.CreateSymbolicLinkW
    csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    csl.restype = ctypes.c_ubyte
    
    # 转换为绝对路�?    abs_source = os.path.abspath(source)
    abs_link = os.path.abspath(link_name)
    
    # 删除已存在的链接
    if os.path.lexists(abs_link):
        if os.path.isdir(abs_link):
            os.rmdir(abs_link)
        else:
            os.remove(abs_link)
    
    # 创建符号链接
    if not csl(abs_link, abs_source, flags):
        error_code = ctypes.windll.kernel32.GetLastError()
        raise ctypes.WinError(error_code)

os.symlink = win_symlink

def win_islink(path: str) -> bool:
    """判断路径是否为符号链�?""
    try:
        attrs = win32file.GetFileAttributes(path)
        return attrs & REPARSE_FOLDER == REPARSE_FOLDER
    except pywintypes.error as e:
        if e.winerror == winerror.ERROR_FILE_NOT_FOUND:
            return False
        raise

os.path.islink = win_islink

def win_readlink(path: str) -> Optional[str]:
    """读取符号链接的目标路�?""
    if not win_islink(path):
        return None
    
    try:
        # 打开文件并获取重解析点数�?        handle = win32file.CreateFile(
            path,
            win32file.GENERIC_READ,
            0,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_FLAG_OPEN_REPARSE_POINT | win32file.FILE_FLAG_BACKUP_SEMANTICS,
            None
        )
        
        # 获取重解析点数据
        MAX_BUFFER = 16 * 1024
        buffer = win32file.DeviceIoControl(
            handle, 
            winioctlcon.FSCTL_GET_REPARSE_POINT, 
            None, 
            MAX_BUFFER
        )
        
        # 关闭句柄
        win32file.CloseHandle(handle)
        
        # 解析重解析点数据
        tag = int.from_bytes(buffer[:4], byteorder='little')
        reparse_type = REPARSE_TAGS.get(tag, "unknown")
        
        if reparse_type != "symbolic":
            logger.warning(f"Unsupported reparse point type: {reparse_type}")
            return None
        
        # 解析符号链接数据
        # 偏移量：4字节标记 + 2字节数据长度 + 2字节保留
        data_buffer = buffer[8:]
        subst_offset = int.from_bytes(data_buffer[0:2], 'little')
        subst_length = int.from_bytes(data_buffer[2:4], 'little')
        print_offset = int.from_bytes(data_buffer[4:6], 'little')
        print_length = int.from_bytes(data_buffer[6:8], 'little')
        
        # 提取目标路径
        subst_str = data_buffer[subst_offset:subst_offset+subst_length].decode('utf-16le')
        if subst_str.startswith("\\??\\"):
            subst_str = subst_str[4:]
        return subst_str
    
    except Exception as e:
        logger.error(f"Error reading symlink {path}: {str(e)}")
        return None

os.readlink = win_readlink

def normalize_win_path(path: str) -> str:
    """标准化Windows路径"""
    path = os.path.abspath(path)
    path = os.path.normpath(path)
    path = path.replace("/", "\\")
    if not path.endswith("\\") and os.path.isdir(path):
        path += "\\"
    return path

def set_file_security(
        file_path: str, 
        user: str = None, 
        permissions: str = None, 
        inheritance: bool = False
    ) -> int:
    """设置Windows文件权限"""
    try:
        # 获取文件安全描述�?        sd = win32security.GetFileSecurity(file_path, win32security.DACL_SECURITY_INFORMATION)
        
        # 创建新的DACL
        dacl = win32security.ACL()
        
        # 添加用户权限
        if user and permissions:
            user_sid = win32security.LookupAccountName(None, user)[0]
            access_flags = {
                'F': win32file.FILE_ALL_ACCESS,
                'M': win32file.FILE_GENERIC_READ | win32file.FILE_GENERIC_WRITE | win32file.FILE_GENERIC_EXECUTE,
                'RX': win32file.FILE_GENERIC_READ | win32file.FILE_GENERIC_EXECUTE,
                'R': win32file.FILE_GENERIC_READ,
                'W': win32file.FILE_GENERIC_WRITE,
                'X': win32file.FILE_GENERIC_EXECUTE
            }.get(permissions, win32file.FILE_GENERIC_READ | win32file.FILE_GENERIC_EXECUTE)
            
            inheritance_flags = win32security.CONTAINER_INHERIT_ACE
            inheritance_flags |= win32security.OBJECT_INHERIT_ACE if inheritance else 0
            inheritance_flags |= win32security.INHERIT_ONLY_ACE if inheritance else 0
            
            dacl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION,
                inheritance_flags,
                access_flags,
                user_sid
            )
        
        # 设置DACL
        sd.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetFileSecurity(file_path, win32security.DACL_SECURITY_INFORMATION, sd)
        return 0
    except Exception as e:
        logger.error(f"Failed to set security for {file_path}: {str(e)}")
        return 1

# --------------------- 命令行操�?---------------------
def run_command(
        cmd: Union[str, List[str]], 
        environment: Dict = None, 
        as_shell: bool = False, 
        working_dir: str = None,
        timeout: int = 300
    ) -> Tuple[int, str, str]:
    """
    运行系统命令（安全版本）
    
    参数:
        cmd: 命令字符串或列表
        environment: 环境变量字典
        as_shell: 是否通过shell执行
        working_dir: 工作目录
        timeout: 超时时间（秒�?    
    返回:
        (returncode, stdout, stderr)
    """
    # 安全地处理命令输�?    if isinstance(cmd, str):
        if as_shell:
            cmd_str = cmd
            cmd_list = ["cmd.exe", "/C", cmd]
        else:
            cmd_list = shlex.split(cmd)
            cmd_str = " ".join(cmd_list)
    else:
        cmd_list = cmd
        cmd_str = " ".join(cmd)
    
    logger.info(f"正在执行命令: {cmd_str}")
    
    creation_flags = 0
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = subprocess.SW_HIDE
    
    # 避免显示命令行窗�?    startup_info.dwFlags = win32con.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = win32con.SW_HIDE
    
    try:
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            env=environment,
            cwd=working_dir,
            shell=as_shell,
            text=True,
            encoding='utf-8',
            errors='replace',
            startupinfo=startup_info
        )
        
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode, stdout.strip(), stderr.strip()
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            logger.warning(f"命令超时: {cmd_str}")
            return -1, stdout.strip(), stderr.strip()
    
    except Exception as e:
        logger.error(f"执行命令失败: {cmd_str} - {str(e)}")
        return -1, "", str(e)

def run_as_admin(
        cmd: Union[str, List[str]], 
        wait: bool = True, 
        hidden: bool = True
    ) -> bool:
    """以管理员身份运行命令"""
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = cmd
    
    args = []
    if hidden:
        args = ["-WindowStyle", "Hidden"]
    
    ps_command = (
        f"Start-Process -FilePath 'cmd.exe' -ArgumentList '/c {cmd_str}' "
        f"{' '.join(args)} "
        "-Verb RunAs -Wait:$true"
    )
    
    result, _, _ = run_command(
        ["powershell.exe", "-Command", ps_command],
        as_shell=False
    )
    
    return result == 0

def execute_powershell(script_content: str, timeout: int = 60) -> Tuple[int, str, str]:
    """执行PowerShell脚本"""
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.ps1', 
                delete=False,
                encoding='utf-8'
            ) as script_file:
            
            script_file.write(script_content)
            script_path = script_file.name
        
        cmd = [
            "powershell.exe",
            "-ExecutionPolicy", "Unrestricted",
            "-File", script_path
        ]
        
        result, stdout, stderr = run_command(
            cmd, 
            timeout=timeout
        )
        
        os.remove(script_path)
        return result, stdout, stderr
    
    except Exception as e:
        logger.error(f"执行Powershell失败: {str(e)}")
        return -1, "", str(e)

# --------------------- 用户和权限管�?---------------------
def is_current_user_admin() -> bool:
    """检查当前用户是否具有管理员权限"""
    try:
        # 方法1：检查管理员组成员身�?        if ctypes.windll.shell32.IsUserAnAdmin():
            return True
        
        # 方法2：尝试打开需要管理员权限的资�?        try:
            hKey = win32api.RegOpenKeyEx(
                win32con.HKEY_LOCAL_MACHINE,
                "Software",
                0,
                win32con.KEY_ALL_ACCESS
            )
            win32api.RegCloseKey(hKey)
            return True
        except:
            pass
        
        # 方法3：使用whoami命令
        result, stdout, _ = run_command(WHOAMI_GROUPS)
        if result == 0 and ADMINISTRATORS_GROUP in stdout:
            return True
        
        return False
    except Exception as e:
        logger.error(f"检查管理员权限失败: {str(e)}")
        return False

def get_current_user() -> str:
    """获取当前用户名（域\\用户�?""
    username = win32api.GetUserNameEx(win32con.NameSamCompatible)
    if not username:
        username = win32api.GetUserName()
    return username

def set_file_owner(file_path: str, user: str, recursive: bool = False) -> None:
    """设置文件所有�?""
    try:
        if recursive and os.path.isdir(file_path):
            for root, dirs, files in os.walk(file_path):
                for item in dirs + files:
                    set_file_owner(os.path.join(root, item), user, False)
            return
        
        # 获取用户的SID
        user_sid = win32security.LookupAccountName(None, user)[0]
        
        # 获取文件安全描述�?        sd = win32security.GetNamedSecurityInfo(
            file_path,
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION
        )
        
        # 设置新所有�?        win32security.SetNamedSecurityInfo(
            file_path,
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION,
            user_sid,
            None,
            None,
            None
        )
    except Exception as e:
        logger.error(f"设置文件所有者失�? {file_path} -> {user}: {str(e)}")
        raise

def grant_privilege(user: str, privilege: str) -> bool:
    """为用户授予特�?""
    try:
        # 获取用户SID
        _, user_sid, _ = win32security.LookupAccountName(None, user)
        
        # 打开策略
        policy = win32security.LsaOpenPolicy(
            None,
            win32security.POLICY_CREATE_ACCOUNT | win32security.POLICY_LOOKUP_NAMES
        )
        
        # 授予特权
        win32security.LsaAddAccountRights(
            policy,
            user_sid,
            (privilege,)
        )
        logger.info(f"授予用户 {user} 特权: {privilege}")
        return True
    except Exception as e:
        logger.error(f"授予特权失败: {privilege} -> {user}: {str(e)}")
        return False

def revoke_privilege(user: str, privilege: str) -> bool:
    """撤销用户的特�?""
    try:
        # 获取用户SID
        _, user_sid, _ = win32security.LookupAccountName(None, user)
        
        # 打开策略
        policy = win32security.LsaOpenPolicy(
            None,
            win32security.POLICY_CREATE_ACCOUNT | win32security.POLICY_LOOKUP_NAMES
        )
        
        # 撤销特权
        win32security.LsaRemoveAccountRights(
            policy,
            user_sid,
            False,  # 仅删除指定权�?            (privilege,)
        )
        logger.info(f"撤销用户 {user} 特权: {privilege}")
        return True
    except Exception as e:
        logger.error(f"撤销特权失败: {privilege} -> {user}: {str(e)}")
        return False

def create_windows_user(username: str, password: str, description: str = "Service Account") -> bool:
    """创建Windows用户账户"""
    try:
        # 解析域和用户�?        if '\\' in username:
            domain, username = username.split('\\', 1)
        else:
            domain = None
        
        # 准备用户信息
        user_info = {
            'name': username,
            'password': password,
            'priv': win32netcon.USER_PRIV_USER,
            'home_dir': "",
            'comment': description,
            'flags': win32netcon.UF_SCRIPT | win32netcon.UF_DONT_EXPIRE_PASSWD | win32netcon.UF_PASSWD_CANT_CHANGE,
            'script_path': None
        }
        
        # 创建用户
        win32net.NetUserAdd(domain, 1, user_info)
        logger.info(f"成功创建用户: {username}")
        
        # 添加到管理员�?        add_user_to_group(username, ADMINISTRATORS_GROUP)
        return True
    
    except Exception as e:
        logger.error(f"创建用户失败: {username}: {str(e)}")
        return False

def add_user_to_group(username: str, groupname: str) -> bool:
    """将用户添加到用户�?""
    try:
        # 解析域和组名
        if '\\' in groupname:
            domain, groupname = groupname.split('\\', 1)
        else:
            domain = None
        
        # 将用户添加到�?        win32net.NetLocalGroupAddMembers(
            domain,
            groupname,
            3,  # 级别3指定SID
            [{'domainandname': username}]
        )
        logger.info(f"用户 {username} 已添加到�? {groupname}")
        return True
    except Exception as e:
        logger.error(f"添加用户到组失败: {username} -> {groupname}: {str(e)}")
        return False

# --------------------- 服务管理 ---------------------
class ServiceManager:
    """Windows服务管理工具"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.scm_handle = win32service.OpenSCManager(
            None, 
            None, 
            win32service.SC_MANAGER_ALL_ACCESS
        )
    
    def __del__(self):
        if self.scm_handle:
            win32service.CloseServiceHandle(self.scm_handle)
    
    def _get_service_handle(self, access=win32service.SERVICE_ALL_ACCESS):
        try:
            return win32service.OpenService(
                self.scm_handle, 
                self.service_name, 
                access
            )
        except pywintypes.error as e:
            if e.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
                return None
            raise
    
    def service_exists(self) -> bool:
        """检查服务是否存�?""
        return self._get_service_handle() is not None
    
    def get_service_status(self) -> str:
        """获取服务状�?""
        try:
            handle = self._get_service_handle(win32service.SERVICE_QUERY_STATUS)
            if not handle:
                return SERVICE_STATUS_NOT_INSTALLED
            
            status = win32service.QueryServiceStatus(handle)
            states = {
                win32service.SERVICE_STOPPED: SERVICE_STATUS_STOPPED,
                win32service.SERVICE_START_PENDING: SERVICE_STATUS_STARTING,
                win32service.SERVICE_STOP_PENDING: SERVICE_STATUS_STOPPING,
                win32service.SERVICE_RUNNING: SERVICE_STATUS_RUNNING
            }
            return states.get(status[1], SERVICE_STATUS_UNKNOWN)
        except Exception as e:
            logger.error(f"获取服务状态失�? {self.service_name}: {str(e)}")
            return SERVICE_STATUS_UNKNOWN
    
    def start_service(self, timeout: int = 30) -> Tuple[int, str]:
        """启动服务"""
        handle = self._get_service_handle()
        if not handle:
            return winerror.ERROR_SERVICE_DOES_NOT_EXIST, "服务不存�?
        
        try:
            win32service.StartService(handle, None)
            
            # 等待服务启动
            win32service.WaitForServiceStatus(
                handle,
                win32service.SERVICE_RUNNING,
                timeout
            )
            return 0, "成功启动服务"
        except pywintypes.error as e:
            return e.winerror, e.strerror
        finally:
            win32service.CloseServiceHandle(handle)
    
    def stop_service(self, timeout: int = 30) -> Tuple[int, str]:
        """停止服务"""
        handle = self._get_service_handle()
        if not handle:
            return winerror.ERROR_SERVICE_DOES_NOT_EXIST, "服务不存�?
        
        try:
            status = win32service.ControlService(
                handle, 
                win32service.SERVICE_CONTROL_STOP
            )
            
            # 等待服务停止
            win32service.WaitForServiceStatus(
                handle,
                win32service.SERVICE_STOPPED,
                timeout
            )
            return 0, "成功停止服务"
        except pywintypes.error as e:
            return e.winerror, e.strerror
        finally:
            win32service.CloseServiceHandle(handle)
    
    def install_service(
            self,
            display_name: str,
            bin_path: str,
            service_type: int = win32service.SERVICE_WIN32_OWN_PROCESS,
            start_type: int = win32service.SERVICE_AUTO_START,
            error_control: int = win32service.SERVICE_ERROR_NORMAL,
            dependencies: List[str] = None,
            service_user: str = None,
            password: str = None
        ) -> bool:
        """安装服务"""
        if not bin_path or not os.path.exists(bin_path):
            raise ValueError("无效的可执行文件路径")
        
        try:
            win32serviceutil.InstallService(
                pythonClassString = None,
                serviceName = self.service_name,
                displayName = display_name,
                description = display_name,
                exeName = bin_path,
                startType = start_type,
                errorControl = error_control,
                bRunInteractive = False,
                serviceType = service_type,
                dependencies = dependencies or [],
                userName = service_user,
                password = password
            )
            logger.info(f"服务安装成功: {self.service_name}")
            return True
        except Exception as e:
            logger.error(f"服务安装失败: {self.service_name}: {str(e)}")
            return False
    
    def uninstall_service(self) -> bool:
        """卸载服务"""
        if not self.service_exists():
            logger.warning(f"服务不存�? {self.service_name}")
            return False
        
        try:
            win32serviceutil.RemoveService(self.service_name)
            logger.info(f"服务已卸�? {self.service_name}")
            return True
        except Exception as e:
            logger.error(f"服务卸载失败: {self.service_name}: {str(e)}")
            return False
    
    def configure_service(
            self,
            description: str = None,
            start_type: int = None,
            recovery_config: Dict = None
        ) -> bool:
        """配置服务参数"""
        handle = self._get_service_handle(win32service.SERVICE_CHANGE_CONFIG)
        if not handle:
            return False
        
        try:
            # 更新描述
            if description:
                win32service.ChangeServiceConfig(
                    handle, 
                    win32service.SERVICE_NO_CHANGE,
                    win32service.SERVICE_NO_CHANGE,
                    win32service.SERVICE_NO_CHANGE,
                    None, None, None, None, None, None, description
                )
            
            # 更新启动类型
            if start_type is not None:
                win32service.ChangeServiceConfig(
                    handle, 
                    win32service.SERVICE_NO_CHANGE,
                    start_type,
                    win32service.SERVICE_NO_CHANGE,
                    None, None, None, None, None, None, None
                )
            
            # 配置失败恢复策略
            if recovery_config:
                recovery_info = {
                    'ResetPeriod': recovery_config.get('reset_period', 86400),
                    'Command': recovery_config.get('command', ''),
                    'FailureActionsOnNonCrashFailures': recovery_config.get('all_failures', True),
                    'FailureActions': []
                }
                
                actions = recovery_config.get('actions', [])
                for action in actions:
                    failure_action = (
                        action['type'],
                        action['delay'] * 1000  # 转换为毫�?                    )
                    recovery_info['FailureActions'].append(failure_action)
                
                win32service.SetServiceFailureActions(handle, recovery_info)
            
            return True
        except Exception as e:
            logger.error(f"服务配置失败: {self.service_name}: {str(e)}")
            return False
        finally:
            win32service.CloseServiceHandle(handle)

# --------------------- 系统工具 ---------------------
def run_command_impersonated(
        cmd: Union[str, List[str]],
        username: str,
        password: str,
        domain: str = ".",
        timeout: int = 300
    ) -> Tuple[int, str, str]:
    """模拟指定用户运行命令"""
    # 获取用户令牌
    try:
        token = win32security.LogonUser(
            username,
            domain,
            password,
            win32con.LOGON32_LOGON_INTERACTIVE,
            win32con.LOGON32_PROVIDER_DEFAULT
        )
    except pywintypes.error as e:
        return e.winerror, "", f"登录失败: {e.strerror}"
    
    # 转换为主令牌
    primary_token = win32security.DuplicateTokenEx(
        token,
        win32security.SecurityImpersonation,
        win32con.TOKEN_ALL_ACCESS,
        win32security.TokenPrimary
    )
    
    # 设置进程启动信息
    startup_info = win32process.STARTUPINFO()
    startup_info.dwFlags = win32con.STARTF_USESTDHANDLES
    
    # 创建标准输出和标准错误管�?    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = True
    
    h_stdout = win32file.CreateFile(
        "NUL",
        win32file.GENERIC_WRITE,
        0,
        sa,
        win32file.OPEN_EXISTING,
        0,
        None
    )
    h_stderr = win32file.CreateFile(
        "NUL",
        win32file.GENERIC_WRITE,
        0,
        sa,
        win32file.OPEN_EXISTING,
        0,
        None
    )
    
    startup_info.hStdInput = win32file.CreateFile(
        "NUL",
        win32file.GENERIC_READ,
        0,
        sa,
        win32file.OPEN_EXISTING,
        0,
        None
    )
    startup_info.hStdOutput = h_stdout
    startup_info.hStdError = h_stderr
    
    # 创建进程
    try:
        cmd_line = subprocess.list2cmdline(cmd) if isinstance(cmd, list) else cmd
        process_info = win32process.CreateProcessAsUser(
            primary_token,
            None,  # 应用程序名称
            cmd_line,
            None,  # 进程属�?            None,  # 线程属�?            True,  # 继承句柄
            0,     # 创建标志
            None,  # 环境
            None,  # 当前目录
            startup_info
        )
    except pywintypes.error as e:
        return e.winerror, "", f"创建进程失败: {e.strerror}"
    
    # 等待进程结束
    h_process, h_thread, dw_process_id, dw_thread_id = process_info
    wait_result = win32event.WaitForSingleObject(
        h_process, 
        timeout * 1000  # 转换为毫�?    )
    
    # 获取退出码
    exit_code = win32process.GetExitCodeProcess(h_process)
    
    # 读取输出
    win32file.SetFilePointer(h_stdout, 0, win32file.FILE_BEGIN)
    stdout_data = win32file.ReadFile(
        h_stdout, 
        4096, 
        None
    )[1].decode('utf-8', 'ignore')
    
    win32file.SetFilePointer(h_stderr, 0, win32file.FILE_BEGIN)
    stderr_data = win32file.ReadFile(
        h_stderr, 
        4096, 
        None
    )[1].decode('utf-8', 'ignore')
    
    # 清理资源
    for handle in (h_stdout, h_stderr, startup_info.hStdInput):
        try:
            win32file.CloseHandle(handle)
        except:
            pass
    
    win32file.CloseHandle(h_thread)
    win32file.CloseHandle(h_process)
    
    return exit_code, stdout_data, stderr_data

def secure_password_input(prompt: str = "Password: ") -> str:
    """安全获取密码输入"""
    for c in prompt:
        try:
            print(c, end='', flush=True)
        except:
            pass
    
    password = []
    while True:
        ch = msvcrt.getch()
        if ch in (b'\r', b'\n'):  # Enter
            print()
            break
        elif ch == b'\x08':  # Backspace
            if password:
                password.pop()
                print('\b \b', end='', flush=True)
        elif ch == b'\x03':  # Ctrl+C
            print("\n操作取消")
            raise KeyboardInterrupt
        else:
            password.append(ch.decode(sys.stdin.encoding, 'ignore'))
            print('*', end='', flush=True)
    
    return ''.join(password)

# --------------------- 高级诊断工具 ---------------------
def check_windows_firewall() -> List[bool]:
    """检查Windows防火墙状态（�?专用/公用�?""
    try:
        # 创建临时Powershell脚本
        script = """
        $domain = (Get-NetFirewallProfile -Profile Domain).Enabled
        $private = (Get-NetFirewallProfile -Profile Private).Enabled
        $public = (Get-NetFirewallProfile -Profile Public).Enabled
        Write-Output "Domain:$domain"
        Write-Output "Private:$private"
        Write-Output "Public:$public"
        """
        
        # 执行Powershell脚本
        code, output, error = execute_powershell(script)
        if code != 0:
            raise FatalException(code, f"防火墙检查失�? {error}")
        
        # 解析输出
        profiles = {'Domain': False, 'Private': False, 'Public': False}
        for line in output.splitlines():
            if ':' in line:
                name, status = line.split(':', 1)
                profiles[name.strip()] = status.strip() == 'True'
        
        return [profiles['Domain'], profiles['Private'], profiles['Public']]
    
    except Exception as e:
        logger.error(f"防火墙检查错�? {str(e)}")
        return [False, False, False]

def check_windows_updates() -> Tuple[bool, List[Dict]]:
    """检查可用的Windows更新"""
    try:
        script = """
        $updates = @()
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $result = $searcher.Search("IsInstalled=0")
        if ($result.Updates.Count -gt 0) {
            $result.Updates | ForEach-Object {
                $update = @{
                    Title = $_.Title
                    Description = $_.Description
                    KB = ($_.KBArticleIDs | Select-Object -First 1)
                    SizeMB = [Math]::Round($_.MaxDownloadSize / 1MB, 2)
                }
                $updates += $update
            }
            $updates | ConvertTo-Json
        }
        """
        
        code, output, error = execute_powershell(script)
        if code != 0:
            logger.error(f"更新检查失�? {error}")
            return False, []
        
        # 没有更新则返回空
        if not output.strip():
            return False, []
        
        import json
        updates = json.loads(output)
        return True, updates
    except Exception as e:
        logger.error(f"更新检查错�? {str(e)}")
        return False, []

# --------------------- 锁机�?---------------------
@contextmanager
def system_wide_lock(lock_name: str, timeout: int = 10):
    """系统级互斥锁上下文管理器"""
    lock = win32event.CreateMutex(None, True, lock_name)
    acquired = False
    try:
        result = win32event.WaitForSingleObject(lock, timeout * 1000)
        if result == win32event.WAIT_OBJECT_0 or result == win32event.WAIT_ABANDONED:
            acquired = True
            yield
        elif result == win32event.WAIT_TIMEOUT:
            raise TimeoutError(f"无法�?{timeout} 秒内获取�? {lock_name}")
        else:
            raise OSError(f"未知错误: {result}")
    finally:
        if acquired:
            win32event.ReleaseMutex(lock)
        win32api.CloseHandle(lock)

# --------------------- 主函数示�?---------------------
if __name__ == "__main__":
    logging_utils.set_log_level(logging.DEBUG)
    
    try:
        # 1. 系统信息展示
        print("=== 系统信息 ===")
        version_info = get_windows_version()
        print(f"Windows版本: {version_info[0]}.{version_info[1]}.{version_info[2]}")
        print(f"Windows版本名称: {get_windows_edition()}")
        
        # 2. 服务管理示例
        print("\n=== 服务管理示例 ===")
        service_name = "WinRM"
        service_manager = ServiceManager(service_name)
        
        status = service_manager.get_service_status()
        print(f"服务 '{service_name}' 状�? {status}")
        
        if status == SERVICE_STATUS_STOPPED:
            print("尝试启动服务...")
            err_code, msg = service_manager.start_service()
            print(f"结果: {msg} (错误�? {err_code})")
        
        # 3. 文件操作示例
        print("\n=== 文件操作示例 ===")
        test_file = "C:\\Windows\\Temp\\cloud_test.txt"
        with open(test_file, "w") as f:
            f.write("Windows工具集测�?)
        
        try:
            # 设置文件权限
            set_file_security(test_file, get_current_user(), "F")
            print(f"文件权限设置成功: {test_file}")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
        
        # 4. 用户权限检�?        print("\n=== 用户权限检�?===")
        print("当前用户:", get_current_user())
        print("是否为管理员:", is_current_user_admin())
        
        # 5. 防火墙检�?        print("\n=== 防火墙状�?===")
        domain_status, private_status, public_status = check_windows_firewall()
        print(f"域配置文�? {'启用' if domain_status else '禁用'}")
        print(f"专用配置文件: {'启用' if private_status else '禁用'}")
        print(f"公用配置文件: {'启用' if public_status else '禁用'}")
        
        # 6. 模拟用户执行命令
        print("\n=== 模拟用户执行命令 ===")
        if is_current_user_admin():
            try:
                retcode, stdout, stderr = run_command_impersonated(
                    "whoami /all",
                    username="Guest",
                    password="",
                    domain="NT AUTHORITY"
                )
                print(f"命令执行结果 ({retcode}):\n{stdout}")
            except Exception as e:
                print(f"模拟执行失败: {str(e)}")
        
        # 7. 系统更新检�?        print("\n=== Windows更新检�?===")
        has_updates, updates = check_windows_updates()
        if has_updates:
            print(f"找到 {len(updates)} 个可用更�?")
            for update in updates:
                print(f"- {update.get('KB', 'æe.get('Title', '无标�?)}")
        else:
            print("没有可用更新")
    
    except Exception as e:
        logger.exception("主程序出�? %s", str(e))

