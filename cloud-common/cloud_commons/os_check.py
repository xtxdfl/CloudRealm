#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
import os
import sys
import platform
import json
import functools
import ctypes
from typing import Tuple, List, Dict, Optional, Any

# 使用缓存提高性能
from functools import lru_cache

class OSCheckException(Exception):
    """操作系统检测专用异常"""
    pass

class OSFamily:
    """操作系统家族定义"""
    WINSRV = "winsrv"
    REDHAT = "redhat"
    DEBIAN = "debian"
    SUSE = "suse"

class OSReleaseNames:
    """操作系统发行版名称"""
    WINDOWS = "Windows"
    MACOS = "macOS"
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    CENTOS = "centos"
    REDHAT = "redhat"
    ROCKY = "rocky"
    ORACLE = "oracle"
    AMAZON = "amazon"
    SUSE = "suse"
    ALPINE = "alpine"

class OSChecker:
    """
    操作系统检测器
    支持Windows、Linux、MacOS等主流操作系统
    """
    
    # 操作系统配置文件路径
    OS_RELEASE_FILE = "/etc/os-release"
    REDHAT_RELEASE_FILE = "/etc/redhat-release"
    ORACLE_RELEASE_FILE = "/etc/oracle-release"
    SYSTEM_RELEASE_FILE = "/etc/system-release"
    
    # Windows版本常量
    WINDOWS_VERSIONS = {
        (6, 0): "win2008server",
        (6, 1): "win2008serverr2",
        (6, 2): "win2012server",
        (6, 3): "win2012serverr2",
        (10, 0): "win2016server",
        (10, 0, 17763): "win2019server",
        (10, 0, 19041): "win2022server",
    }
    
    # Linux发行版别名映射
    OS_ALIASES = {
        "centos-redhat": "centos",
        "oracle-redhat": "oraclelinux",
        "rocky-redhat": "rocky",
        "amazon-redhat": "amazonlinux",
        "sles-suse": "sles",
        "sled-suse": "sled",
        "freebsd-bsd": "freebsd",
        "ubuntu-debian": "ubuntu"
    }
    
    # CPU架构映射
    CPU_ARCH = {
        "x86_64": "x64",
        "amd64": "x64",
        "i386": "x86",
        "i686": "x86",
        "arm64": "arm64",
        "aarch64": "arm64",
        "ppc": "powerpc",
        "ppc64": "powerpc",
        "ppc64le": "powerpc"
    }

    def __init__(self):
        # 操作系统映射配置
        self.os_data = self._load_os_mapping()
        
        # 缓存操作系统检测结果
        self._distribution = None
        self._os_type = None
        self._os_version = None
        self._os_family = None

    def _load_os_mapping(self) -> Dict:
        """加载操作系统映射配置"""
        try:
            with open(os.path.join(os.path.dirname(__file__), "resources", "os_family.json"), "r") as f:
                return json.load(f)
        except Exception as e:
            raise OSCheckException(f"Couldn't load OS mapping file: {str(e)}")

    @lru_cache(maxsize=None)
    def os_distribution(self) -> Tuple[str, str, str]:
        """
        获取操作系统发行版信息
        返回: (os_type, os_version, release_name)
        """
        system = platform.system()
        
        if system == "Windows":
            return self._get_windows_distribution()
        elif system == "Darwin":
            return ("macOS", platform.mac_ver()[0], "Darwin")
        else:
            return self._get_linux_distribution()

    def _get_windows_distribution(self) -> Tuple[str, str, str]:
        """获取Windows发行版信息"""
        try:
            major, minor, build, product_type = self._get_windows_version()
            
            # 查找Windows版本
            for keys, rel_name in self.WINDOWS_VERSIONS.items():
                if all(k == v for k, v in zip(keys, (major, minor, build)[:len(keys)])):
                    return (rel_name, f"{major}.{minor}", "WindowsServer")
            
            # 默认处理
            return ("win" + str(major) + str(minor), f"{major}.{minor}", "WindowsDesktop")
        except Exception as e:
            raise OSCheckException(f"Failed to detect Windows version: {str(e)}")

    @staticmethod
    def _get_windows_version() -> Tuple[int, int, int, int]:
        """获取Windows版本详情"""
        class OSVERSIONINFOEX(ctypes.Structure):
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

        version_info = OSVERSIONINFOEX()
        version_info.dwOSVersionInfoSize = ctypes.sizeof(version_info)
        retcode = ctypes.windll.Ntdll.RtlGetVersion(ctypes.byref(version_info))
        if retcode != 0:
            raise RuntimeError("Failed to get OS version")
            
        return (
            version_info.dwMajorVersion,
            version_info.dwMinorVersion,
            version_info.dwBuildNumber,
            version_info.wProductType
        )

    def _get_linux_distribution(self) -> Tuple[str, str, str]:
        """获取Linux发行版信息"""
        try:
            # 尝试使用distro模块
            try:
                import distro
                os_id = distro.id()
                os_version = distro.version()
                release_name = distro.name()
                
                # 特殊处理Amazon Linux
                if "amazon" in os_id.lower() and os_version == "":
                    if self._is_amazon_linux():
                        return ("amazonlinux", self._get_amazon_linux_version(), "Amazon Linux")
                        
                return (os_id, os_version, release_name)
            except ImportError:
                # 备用方案：手动解析
                pass
            
            # 手动解析发行版信息
            if os.path.exists(self.OS_RELEASE_FILE):
                return self._parse_os_release()
            elif os.path.exists(self.REDHAT_RELEASE_FILE):
                return self._parse_redhat_release()
            elif os.path.exists(self.SYSTEM_RELEASE_FILE):
                return self._parse_system_release()
            elif os.path.exists(self.ORACLE_RELEASE_FILE):
                return self._parse_oracle_release()
            else:
                # 最后尝试uname
                return (sys.platform, platform.release(), platform.system())
                
        except Exception as e:
            raise OSCheckException(f"Failed to detect Linux distribution: {str(e)}")

    def _parse_os_release(self) -> Tuple[str, str, str]:
        """解析/etc/os-release文件"""
        os_data = {}
        with open(self.OS_RELEASE_FILE, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os_data[key] = value.strip('"')
        
        os_id = os_data.get("ID", "linux")
        version = os_data.get("VERSION_ID", "")
        release_name = os_data.get("PRETTY_NAME", platform.system())
        
        # Amazon Linux 特殊处理
        if "amazon linux" in release_name.lower():
            os_id = "amazonlinux"
            version = os_data.get("VERSION_ID", self._get_amazon_linux_version())
        
        return (os_id, version, release_name)

    def _parse_redhat_release(self) -> Tuple[str, str, str]:
        """解析/etc/redhat-release文件"""
        with open(self.REDHAT_RELEASE_FILE, "r") as f:
            content = f.read().lower()
            
        if "centos" in content:
            match = re.search(r'release (\d+(\.\d+)?)', content)
            version = match.group(1) if match else "unknown"
            return ("centos", version, "CentOS")
        elif "red hat" in content:
            match = re.search(r'release (\d+(\.\d+)?)', content)
            version = match.group(1) if match else "unknown"
            return ("redhat", version, "Red Hat Enterprise Linux")
        return ("linux", "unknown", "Unknown Linux")

    def _parse_system_release(self) -> Tuple[str, str, str]:
        """解析/etc/system-release文件"""
        with open(self.SYSTEM_RELEASE_FILE, "r") as f:
            content = f.read().lower()
            
        if "amazon" in content:
            match = re.search(r'release (\d+)', content)
            version = match.group(1) if match else "unknown"
            return ("amazonlinux", version, "Amazon Linux")
        else:
            return self._parse_redhat_release()

    def _parse_oracle_release(self) -> Tuple[str, str, str]:
        """解析/etc/oracle-release文件"""
        with open(self.ORACLE_RELEASE_FILE, "r") as f:
            content = f.read().lower()
            
        match = re.search(r'release (\d+(\.\d+)?)', content)
        version = match.group(1) if match else "unknown"
        return ("oraclelinux", version, "Oracle Linux")

    @staticmethod
    def _is_amazon_linux() -> bool:
        """检查是否为Amazon Linux"""
        return os.path.exists("/etc/system-release") and "amazon" in open("/etc/system-release").read().lower()

    @staticmethod
    def _get_amazon_linux_version() -> str:
        """获取Amazon Linux版本"""
        try:
            with open("/etc/system-release", "r") as f:
                content = f.read()
                match = re.search(r'release (\d+)', content)
                return match.group(1) if match else "unknown"
        except:
            return "unknown"

    @lru_cache(maxsize=None)
    def get_os_type(self) -> str:
        """获取操作系统的标准类型标识"""
        os_id = self.os_distribution()[0].lower()
        
        # 特殊处理
        if "suse" in os_id:
            return OSReleaseNames.SUSE
        elif "debian" in os_id:
            return OSReleaseNames.DEBIAN
        elif "ubuntu" in os_id:
            return OSReleaseNames.UBUNTU
        
        # 识别处理器架构
        arch = self.get_cpu_arch()
        if arch:
            os_id += f"-{arch}"
            
        # 应用别名映射
        return self.OS_ALIASES.get(os_id, os_id)

    @lru_cache(maxsize=None)
    def get_os_family(self) -> str:
        """获取操作系统家族"""
        os_type = self.get_os_type()
        
        # 在映射数据中查找家族
        for family, family_data in self.os_data.get("mapping", {}).items():
            if os_type in family_data.get("distro", []):
                return family.lower()
        
        # 默认返回第一个类型名
        return os_type.split('-')[0].lower()

    def get_os_family_parent(self, family: str) -> Optional[str]:
        """获取操作系统家族的父家族"""
        family_data = self.os_data.get("mapping", {}).get(family, {})
        return family_data.get("extends")

    @lru_cache(maxsize=None)
    def get_os_version(self, with_patch: bool = False) -> str:
        """获取操作系统版本号"""
        _, version, _ = self.os_distribution()
        
        # 清理版本号中的非数字字符
        clean_version = re.sub(r"[^\d.]", "", version)
        parts = clean_version.split('.')
        
        if with_patch and len(parts) >= 3:
            return ".".join(parts[:3])
        elif len(parts) >= 2:
            return ".".join(parts[:2])
        else:
            return clean_version or "unknown"

    @lru_cache(maxsize=None)
    def get_os_major_version(self) -> str:
        """获取操作系统主版本号"""
        return self.get_os_version().split('.')[0]

    @lru_cache(maxsize=None)
    def get_os_release_name(self) -> str:
        """获取操作系统发行版名称"""
        return self.os_distribution()[2]

    @lru_cache(maxsize=None)
    def get_cpu_arch(self) -> str:
        """获取CPU架构信息"""
        machine = platform.machine().lower()
        return self.CPU_ARCH.get(machine, machine)

    @functools.lru_cache(maxsize=None)
    def is_family(self, family: str) -> bool:
        """检查操作系统是否属于特定家族"""
        current_family = self.get_os_family()
        
        # 直接匹配
        if current_family == family:
            return True
            
        # 检查父家族
        parent = self.get_os_family_parent(current_family)
        while parent:
            if parent == family:
                return True
            parent = self.get_os_family_parent(parent)
            
        return False

    # 常用家族检查方法
    def is_redhat_family(self) -> bool:
        return self.is_family(OSFamily.REDHAT)

    def is_debian_family(self) -> bool:
        return self.is_family(OSFamily.DEBIAN)

    def is_suse_family(self) -> bool:
        return self.is_family(OSFamily.SUSE)

    def is_windows_family(self) -> bool:
        """检查是否为Windows家族"""
        system = platform.system()
        return system == "Windows" or self.is_family(OSFamily.WINSRV)

    # 发行版特定检查方法
    def is_centos(self) -> bool:
        return self.get_os_type() == OSReleaseNames.CENTOS

    def is_ubuntu(self) -> bool:
        return self.get_os_type() == OSReleaseNames.UBUNTU

    def is_amazon_linux(self) -> bool:
        return self.get_os_type() == OSReleaseNames.AMAZON

    def is_amazon_linux_2023(self) -> bool:
        return self.is_amazon_linux() and self.get_os_major_version() == "2023"

    def is_windows_server(self) -> bool:
        """检查是否为Windows Server"""
        try:
            _, minor, _, product_type = self._get_windows_version()
            return product_type in (2, 3)  # 2=域控制器, 3=服务器
        except:
            return False

    def __str__(self) -> str:
        """返回操作系统的详细信息"""
        os_type = self.get_os_type()
        os_version = self.get_os_version()
        release_name = self.get_os_release_name()
        return f"{release_name} [{os_type} {os_version}] ({self.get_os_family()} family)"

# 全局实例，便于使用
os_check = OSChecker()

# 兼容旧API
class OSCheck:
    """兼容旧版的API包装器"""
    
    @staticmethod
    @lru_cache(maxsize=None)
    def os_distribution():
        return os_check.os_distribution()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def get_os_type():
        return os_check.get_os_type()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def get_os_family():
        return os_check.get_os_family()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def get_os_version():
        return os_check.get_os_version()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def get_os_major_version():
        return os_check.get_os_major_version()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def get_os_release_name():
        return os_check.get_os_release_name()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def is_redhat_family():
        return os_check.is_redhat_family()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def is_suse_family():
        return os_check.is_suse_family()
    
    @staticmethod
    @lru_cache(maxsize=None)
    def is_windows_family():
        return os_check.is_windows_family()
    
    @staticmethod
    def is_in_family(current_family, family):
        return os_check.is_family(family)

def get_os_info() -> Dict[str, str]:
    """获取操作系统信息的字典表示"""
    return {
        "type": os_check.get_os_type(),
        "version": os_check.get_os_version(),
        "major_version": os_check.get_os_major_version(),
        "platform": platform.system(),
        "architecture": os_check.get_cpu_arch(),
        "release": os_check.get_os_release_name(),
        "family": os_check.get_os_family(),
        "is_windows": os_check.is_windows_family(),
        "is_linux": platform.system() == "Linux",
        "is_mac": platform.system() == "Darwin",
        "is_server": os_check.is_windows_server() if os_check.is_windows_family() else True
    }

if __name__ == "__main__":
    # 测试输出
    print("=" * 50)
    print(f"Operating System: {os_check}")
    print("=" * 50)
    
    print("\nDetailed OS Info:")
    info = get_os_info()
    for key, value in info.items():
        print(f"{key.replace('_', ' ').title():>15}: {value}")
    
    print("\nFamily Checks:")
    print(f"Is RedHat Family? {os_check.is_redhat_family()}")
    print(f"Is Debian Family? {os_check.is_debian_family()}")
    print(f"Is SUSE Family? {os_check.is_suse_family()}")
    print(f"Is Windows Family? {os_check.is_windows_family()}")
    print(f"Is Windows Server? {os_check.is_windows_server()}")
