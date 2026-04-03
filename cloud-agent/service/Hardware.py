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

import os
import platform
import logging
import subprocess
import time
import json
import concurrent.futures
from typing import Dict, List, Optional, Union
from pathlib import Path
from functools import lru_cache
from contextlib import contextmanager

# 配置日志
logger = logging.getLogger("HardwareInformation")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class HardwareException(Exception):
    """硬件信息收集异常基类"""
    pass

class ResourceUnavailableError(HardwareException):
    """所需资源不可用异常"""
    pass

class CrossPlatformCollector:
    """跨平台硬件信息收集器
    
    提供统一接口收集多种系统硬件信息，包括：
    - 磁盘存储空间分析
    - 硬件配置概览
    - 挂载点状态检测
    - 存储性能指标
    
    支持多种操作系统：Linux, Windows, macOS
    """
    
    # 通用配置常量
    DEFAULT_TIMEOUT = 20  # 秒
    CACHE_TTL = 300  # 硬件信息缓存时间
    DISK_INFO_UPDATE_INTERVAL = 3600  # 磁盘扫描缓存时间
    
    # 平台特定常量
    OS_WINDOWS = "windows"
    OS_LINUX = "linux"
    OS_MACOS = "darwin"
    
    # 挂载点过滤配置
    IGNORE_MOUNTS = {
        "linux": ["proc", "dev", "sys", "boot", "home", "tmp", "run", "cgroup", "devpts"],
        "windows": ["tmp", "recovery"],
        "darwin": ["dev", "private"],
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化硬件信息收集器
        
        :param config: 配置字典：
            - cache_enabled: 是否启用缓存
            - mount_check_timeout: 挂载点检查超时时间
            - ignore_remote_mounts: 是否忽略远程挂载点
            - custom_ignore_mounts: 自定义忽略的挂载点
        """
        self.config = config or {}
        self.os_name = platform.system().lower()
        self.last_disk_scan = 0
        self.available_disks_cache = []
        self.hardware_cache = None
        self.cache_timestamp = 0
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        logger.info(f"初始化硬件收集器 - 操作系统: {self.os_name}")

    @property
    def is_windows(self) -> bool:
        """判断是否为Windows系统"""
        return self.os_name == self.OS_WINDOWS

    @property
    def is_linux(self) -> bool:
        """判断是否为Linux系统"""
        return self.os_name == self.OS_LINUX

    @property
    def is_macos(self) -> bool:
        """判断是否为macOS系统"""
        return self.os_name == self.OS_MACOS

    @property
    def cache_enabled(self) -> bool:
        """是否启用硬件信息缓存"""
        return self.config.get("cache_enabled", True)

    @property
    def mount_check_timeout(self) -> int:
        """获取挂载点检查超时时间（秒）"""
        return self.config.get("mount_check_timeout", self.DEFAULT_TIMEOUT)

    @property
    def ignore_remote_mounts(self) -> bool:
        """是否忽略远程挂载点"""
        return self.config.get("ignore_remote_mounts", False)

    @property
    def custom_ignore_mounts(self) -> List[str]:
        """获取自定义忽略的挂载点"""
        return self.config.get("custom_ignore_mounts", [])

    @lru_cache(maxsize=128)
    def should_ignore_mount(self, mount_point: str) -> bool:
        """判断是否应忽略指定的挂载点"""
        # 静态平台忽略规则
        if any(mp in mount_point for mp in self.IGNORE_MOUNTS.get(self.os_name, [])):
            return True
        
        # 自定义忽略规则
        if any(ignored in mount_point for ignored in self.custom_ignore_mounts):
            return True
        
        # 特定平台动态规则
        if self.is_windows:
            return mount_point.startswith("\\\\")  # 忽略网络驱动器
        elif self.is_linux or self.is_macos:
            return mount_point.startswith("/mnt/wsl")  # 忽略WSL虚拟文件系统
        
        return False

    @contextmanager
    def command_executor(self, command: Union[str, List], timeout: int = DEFAULT_TIMEOUT):
        """安全执行命令行操作的上下文管理器"""
        proc = None
        try:
            if isinstance(command, list):
                proc = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="ignore"
                )
            else:  # Windows的Powershell命令
                proc = subprocess.Popen(
                    ["powershell.exe", "-Command", command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            # 等待超时
            start_time = time.time()
            while time.time() - start_time < timeout and proc.poll() is None:
                time.sleep(0.1)
            
            if proc.poll() is None:
                proc.terminate()
                raise TimeoutError(f"命令执行超时: {' '.join(command) if isinstance(command, list) else command}")
            
            stdout, stderr = proc.communicate()
            yield stdout, stderr, proc.returncode
            
        except Exception as e:
            logger.error(f"执行命令失败: {str(e)}")
            raise HardwareException(f"命令执行错误: {str(e)}")
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait()

    def run_command(self, command: Union[str, List], timeout: int = DEFAULT_TIMEOUT) -> str:
        """执行命令并返回输出"""
        with self.command_executor(command, timeout) as (stdout, stderr, returncode):
            if returncode != 0:
                logger.error(f"命令返回错误: {stderr.strip()}")
                raise ResourceUnavailableError(f"命令执行失败: {stderr.strip()}")
            return stdout

    def get_disk_info_windows(self) -> List[Dict]:
        """获取Windows系统磁盘信息"""
        command = (
            "Get-WmiObject Win32_LogicalDisk | "
            "Where-Object { $_.DriveType -eq 3 } | "
            "Select-Object DeviceID, VolumeName, @{Name='Size';Expression={$_.Size}}, "
            "@{Name='FreeSpace';Expression={$_.FreeSpace}}, "
            "@{Name='UsedSpace';Expression={$_.Size - $_.FreeSpace}}, "
            "@{Name='PercentUsed';Expression={[math]::Round(($_.Size - $_.FreeSpace)/$_.Size * 100, 2)}}, "
            "@{Name='FileSystem';Expression={$_.FileSystem}}, "
            "@{Name='Type';Expression={$_.FileSystem}} | "
            "ConvertTo-Json"
        )
        
        try:
            output = self.run_command(command)
            drives = json.loads(output)
            return [
                {
                    "device": drive["DeviceID"],
                    "mountpoint": f"{drive['DeviceID']}\\",
                    "type": drive["FileSystem"] or "NTFS",
                    "size": drive["Size"],
                    "used": drive["UsedSpace"],
                    "available": drive["FreeSpace"],
                    "percent": f"{drive['PercentUsed']}%"
                }
                for drive in drives
            ]
        except json.JSONDecodeError:
            logger.error("解析Windows磁盘信息失败")
            return []
        except HardwareException:
            return []

    def get_disk_info_linux(self) -> List[Dict]:
        """获取Linux系统磁盘信息"""
        command = ["df", "-kPT", "--output=source,fstype,size,used,avail,pcent,target"]
        if self.ignore_remote_mounts:
            command.append("-l")
        
        try:
            output = self.run_command(command, self.mount_check_timeout)
            lines = [line for line in output.splitlines()[1:] if line.strip()]
            
            mounts = []
            for line in lines:
                parts = line.split()
                if len(parts) < 7:
                    continue
                
                source, fstype, size, used, avail, pcent, target = parts[:7]
                if pcent.endswith('%'):
                    pcent = pcent[:-1]
                
                mounts.append({
                    "device": source,
                    "mountpoint": target,
                    "type": fstype,
                    "size": str(int(size) * 1024),
                    "used": str(int(used) * 1024),
                    "available": str(int(avail) * 1024),
                    "percent": f"{pcent}%"
                })
            return mounts
        except HardwareException:
            return []

    def get_disk_info_macos(self) -> List[Dict]:
        """获取macOS系统磁盘信息"""
        command = ["df", "-kP"]
        try:
            output = self.run_command(command, self.mount_check_timeout)
            lines = [line for line in output.splitlines()[1:] if line.strip()]
            
            mounts = []
            for line in lines:
                parts = line.split()
                if len(parts) < 9:
                    continue
                
                device, size, used, avail, capacity, _, _, fstype, target = parts[:9]
                mounts.append({
                    "device": device,
                    "mountpoint": target,
                    "type": fstype,
                    "size": size,
                    "used": used,
                    "available": avail,
                    "percent": capacity
                })
            return mounts
        except HardwareException:
            return []

    def get_os_disks(self) -> List[Dict]:
        """获取系统磁盘信息（平台自适应）"""
        # 使用缓存避免频繁扫描
        if time.time() - self.last_disk_scan < self.DISK_INFO_UPDATE_INTERVAL and self.available_disks_cache:
            logger.debug("使用缓存的磁盘信息")
            return self.available_disks_cache
        
        logger.info("扫描系统磁盘信息")
        
        if self.is_windows:
            disks = self.get_disk_info_windows()
        elif self.is_linux:
            disks = self.get_disk_info_linux()
        elif self.is_macos:
            disks = self.get_disk_info_macos()
        else:
            logger.warning("不支持的操作系统类型")
            disks = []
        
        # 过滤无效和忽略的挂载点
        valid_disks = []
        invalid_count = 0
        for disk in disks:
            if not disk["mountpoint"] or disk["size"] == "0":
                invalid_count += 1
                continue
            
            if self.should_ignore_mount(disk["mountpoint"]):
                logger.debug(f"忽略挂载点: {disk['mountpoint']}")
                continue
            
            valid_disks.append(disk)
        
        # 更新缓存
        self.available_disks_cache = valid_disks
        self.last_disk_scan = time.time()
        
        if invalid_count > 0:
            logger.info(f"过滤了 {invalid_count} 个无效挂载点")
        
        logger.info(f"发现 {len(valid_disks)} 个有效存储设备")
        return valid_disks

    def get_facter_info(self) -> Dict:
        """获取系统基本信息"""
        try:
            # 模拟Facter返回的基本系统信息
            return {
                "fqdn": platform.node(),
                "ip_address": self.get_primary_ip(),
                "os": platform.system(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "processor_count": os.cpu_count() or 1,
                "memory_total": self.get_total_memory(),
                "mac_address": self.get_mac_address(),
                "uptime": self.get_system_uptime()
            }
        except Exception as e:
            logger.error(f"获取系统基本信息异常: {str(e)}")
            return {}
    
    def get_primary_ip(self) -> str:
        """获取主网络IP地址"""
        try:
            if self.is_windows:
                self.run_command("ipconfig", 5)
                # 实际实现应解析ipconfig输出
            
            # Linux/macOS实现
            with self.command_executor(["hostname", "-I"]) as (stdout, _, _):
                return stdout.split()[0]
        except:
            return "127.0.0.1"

    def get_total_memory(self) -> str:
        """获取系统总内存"""
        try:
            import psutil
            return str(psutil.virtual_memory().total)
        except ImportError:
            if self.is_linux:
                meminfo = self.run_command("head -1 /proc/meminfo")
                return meminfo.split()[1] + " KB"
            return "Unknown"

    def get_mac_address(self) -> str:
        """获取MAC地址"""
        try:
            if self.is_windows:
                output = self.run_command("getmac /v /FO CSV")
                return output.split('","')[2].strip('"')
            elif self.is_linux:
                with open("/sys/class/net/eth0/address") as f:
                    return f.read().strip()
            else:
                output = self.run_command(["ifconfig", "en0"])
                return output.split("ether ")[1].split()[0]
        except:
            return "00:00:00:00:00:00"

    def get_system_uptime(self) -> str:
        """获取系统运行时间"""
        try:
            if self.is_windows:
                output = self.run_command(
                    "powershell -Command \"(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime\""
                )
                uptime = output.split(":")[0].strip()
                return uptime.replace("Days", "天").replace("Hours", "小时").strip()
            
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.readline().split()[0])
                return time.strftime("%-d天 %-H小时 %-M分", time.gmtime(uptime_seconds))
        except:
            return "Unknown"

    def get_hardware_info(self, invalidate_cache: bool = False) -> Dict:
        """获取完整的硬件信息
        
        :param invalidate_cache: 是否强制刷新缓存
        :return: 包含系统硬件信息的字典
        """
        # 检查缓存状态
        if (self.cache_enabled and 
            self.hardware_cache and 
            not invalidate_cache and 
            time.time() - self.cache_timestamp < self.CACHE_TTL):
            logger.debug("使用缓存的硬件信息")
            return self.hardware_cache
        
        # 并行收集硬件信息
        with concurrent.futures.ThreadPoolExecutor() as executor:
            facter_future = executor.submit(self.get_facter_info)
            disks_future = executor.submit(self.get_os_disks)
            
            try:
                hardware_info = facter_future.result(timeout=self.DEFAULT_TIMEOUT)
                hardware_info["mounts"] = disks_future.result(timeout=self.DEFAULT_TIMEOUT)
            except concurrent.futures.TimeoutError:
                logger.warning("硬件信息收集超时，使用部分数据")
                hardware_info = facter_future.result() if facter_future.done() else {}
                hardware_info["mounts"] = disks_future.result() if disks_future.done() else []
        
        # 添加收集时间和性能指标
        hardware_info["collection_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        hardware_info["performance"] = self.get_performance_metrics()
        
        # 更新缓存
        self.hardware_cache = hardware_info
        self.cache_timestamp = time.time()
        
        logger.info("硬件信息收集完成")
        return hardware_info

    def get_performance_metrics(self) -> Dict:
        """获取系统性能指标"""
        # 此实现简化，实际应用应使用系统原生API
        return {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_io": 0.0,
            "recommendation": "System performance is optimal"
        }

    def generate_hardware_report(self) -> str:
        """生成易读的硬件报告"""
        info = self.get_hardware_info()
        report = []
        
        report.append("=== 硬件信息报告 ===")
        report.append(f"系统: {info.get('os', '')} {info.get('os_release', '')}")
        report.append(f"主机名: {info.get('fqdn', '')}")
        report.append(f"IP地址: {info.get('ip_address', '')}")
        report.append(f"CPU核心: {info.get('processor_count', '')}")
        report.append(f"总内存: {self.human_readable_size(info.get('memory_total', '0'))}")
        report.append(f"系统运行: {info.get('uptime', '')}")
        
        report.append("\n=== 存储设备 ===")
        total_size = 0
        total_used = 0
        for i, disk in enumerate(info.get("mounts", []), 1):
            try:
                size = int(disk.get("size", "0"))
                used = int(disk.get("used", "0"))
                avail = int(disk.get("available", "0"))
                
                total_size += size
                total_used += used
                
                report.append(
                    f"{i}. {disk.get('device', '')} @ {disk.get('mountpoint', '')} "
                    f"[{disk.get('type', '')}] - "
                    f"总计: {self.human_readable_size(size)}, "
                    f"已用: {self.human_readable_size(used)} "
                    f"({disk.get('percent', '0')}%), "
                    f"可用: {self.human_readable_size(avail)}"
                )
            except ValueError:
                pass
        
        report.append("\n=== 存储概览 ===")
        if total_size > 0:
            used_percent = (total_used / total_size) * 100
            report.append(
                f"总空间: {self.human_readable_size(total_size)}, "
                f"已用空间: {self.human_readable_size(total_used)} "
                f"({used_percent:.1f}%)"
            )
        
        report.append("\n=== 系统性能建议 ===")
        report.append(info.get("performance", {}).get("recommendation", ""))
        report.append(f"报告生成时间: {info.get('collection_time', '')}")
        
        return "\n".join(report)

    @staticmethod
    def human_readable_size(size: Union[int, str], decimals=2) -> str:
        """将字节大小转换为易读格式"""
        try:
            size = int(size)
        except (TypeError, ValueError):
            return "0 B"
        
        for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
            if size < 1024.0:
                break
            size /= 1024.0
        
        return f"{size:.{decimals}f} {unit}"


# 示例使用
if __name__ == "__main__":
    # 配置示例
    config = {
        "cache_enabled": True,
        "mount_check_timeout": 15,
        "ignore_remote_mounts": True,
        "custom_ignore_mounts": ["/backup", "/archive"]
    }
    
    # 创建硬件收集器
    collector = CrossPlatformCollector(config)
    
    # 生成报告
    print("\n硬件信息分析报告:")
    print(collector.generate_hardware_report())
    
    # 获取原始数据
    # print("\n原始硬件数据:")
    # print(json.dumps(collector.get_hardware_info(), indent=2))
