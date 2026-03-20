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

import logging
import os
import platform
import re
import socket
import time
import uuid
import json
import glob
import subprocess
import multiprocessing
import shutil
from typing import Dict, Any, Optional, Union, List, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("SystemFacter")

class SystemFacter:
    """智能系统信息收集与分析器
    
    统一收集跨平台系统信息，提供：
    - CPU、内存、存储等硬件资源分析
    - 网络拓扑和信息
    - 操作系统环境信息
    - 虚拟化和容器平台检测
    - 资源使用率分析
    - 安全配置审计
    - 自定义资源覆盖机制
    """
    
    # 预编译正则表达式模式
    MEMORY_PATTERNS = {
        "free": re.compile(r"MemFree:\s+(\d+)\s+.*"),
        "total": re.compile(r"MemTotal:\s+(\d+)\s+.*"),
        "swap_free": re.compile(r"SwapFree:\s+(\d+)\s+.*"),
        "swap_total": re.compile(r"SwapTotal:\s+(\d+)\s+.*")
    }
    
    # 单位转换常数
    KB_TO_GB = 1024 * 1024
    MB_TO_GB = 1024
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化系统信息收集器
        
        :param config_path: 可选的自定义配置文件路径
        """
        self.config = self._load_config(config_path)
        self._command_cache = {}
        self._resource_overrides = self._load_resource_overrides()
        
        logger.info("System facter initialized for %s platform", platform.system())
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置数据"""
        # 简化的配置加载 - 在实际项目中会使用配置管理库
        return {"system_resource_overrides": "/etc/system_resource_overrides"}
    
    def _load_resource_overrides(self) -> Dict[str, Any]:
        """加载资源覆盖配置"""
        overrides = {}
        
        try:
            if "system_resource_overrides" in self.config:
                override_dir = self.config["system_resource_overrides"]
                
                if os.path.isdir(override_dir):
                    logger.info("Loading system resource overrides from %s", override_dir)
                    
                    for file_path in glob.glob(f"{override_dir}/*.json"):
                        with open(file_path, 'r') as f:
                            try:
                                override_data = json.load(f)
                                for key, value in override_data.items():
                                    overrides[key] = value
                                logger.debug("Loaded %d overrides from %s", 
                                            len(override_data), file_path)
                            except json.JSONDecodeError:
                                logger.warning("Invalid JSON in override file %s", file_path)
                else:
                    logger.info("Override directory %s does not exist", override_dir)
            else:
                logger.debug("No system_resource_overrides configured")
        
        except Exception as e:
            logger.error("Error loading resource overrides: %s", str(e))
        
        return overrides

    def _get_resource(self, key: str, default: Any = None) -> Any:
        """获取覆盖资源或默认值"""
        return self._resource_overrides.get(key, default)
    
    def _exec_command(self, command: Union[str, List[str]]) -> Tuple[str, str]:
        """执行系统命令获取输出
        
        :param command: 要执行的命令（字符串或列表）
        :return: (标准输出, 标准错误)
        """
        if isinstance(command, str):
            command_str = command
        else:
            command_str = ' '.join(command)
            
        # 检查缓存
        if command_str in self._command_cache:
            return self._command_cache[command_str]
        
        logger.debug("Executing command: %s", command_str)
        
        try:
            process = subprocess.Popen(
                command,
                shell=isinstance(command, str),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            stdout, stderr = process.communicate()
            return_code = process.returncode
            
            if return_code != 0:
                logger.warning("Command failed (%d): %s\n%s", return_code, command_str, stderr.strip())
            
            # 缓存成功执行的命令
            if return_code == 0:
                self._command_cache[command_str] = (stdout.strip(), stderr.strip())
                return stdout.strip(), stderr.strip()
            else:
                return "", stderr.strip()
                
        except Exception as e:
            logger.error("Error executing command %s: %s", command_str, str(e))
            return "", str(e)
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """获取CPU信息"""
        return {
            "architecture": platform.machine(),
            "physical_cores": multiprocessing.cpu_count(),
            "logical_cores": os.cpu_count(),
            "model": platform.processor(),
        }
    
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        try:
            total_mem = self._get_resource("memorytotal", os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'))
            ram_used = shutil.disk_usage('/ram').used if os.path.exists('/ram') else total_mem * 0.3
            ram_free = total_mem - ram_used
            
            return {
                "total": self._convert_kb_to_gb(total_mem),
                "free": self._convert_kb_to_gb(ram_free),
                "used": self._convert_kb_to_gb(ram_used),
                "swap_total": self._convert_kb_to_gb(self._get_resource("swaptotal", 0)),
                "swap_free": self._convert_kb_to_gb(self._get_resource("swapfree", 0))
            }
        except:
            return {
                "total": "N/A",
                "free": "N/A",
                "used": "N/A",
                "swap_total": "N/A",
                "swap_free": "N/A"
            }
    
    def get_network_info(self) -> Dict[str, Any]:
        """获取网络信息"""
        try:
            fqdn = self._get_resource("fqdn", socket.getfqdn())
            primary_ip = socket.gethostbyname(fqdn.split('.')[0])
            
            # 获取活动接口
            interfaces = []
            if os.name == 'posix':  # Linux/Mac
                _, ip_output, _ = self._exec_command("ip -o addr show")
                for line in ip_output.splitlines():
                    if "inet " in line:
                        parts = line.split()
                        interfaces.append({
                            "name": parts[1],
                            "ip": parts[3].split('/')[0],
                            "mac": parts[parts.index('link/ether') + 1] if 'link/ether' in line else "N/A"
                        })
            
            elif os.name == 'nt':  # Windows
                _, ip_output, _ = self._exec_command("ipconfig /all")
                current_if = {}
                for line in ip_output.splitlines():
                    if "adapter" in line.lower() and current_if:
                        interfaces.append(current_if)
                        current_if = {}
                    elif "IPv4 Address" in line:
                        current_if["ip"] = line.split(':')[-1].strip()
                    elif "Physical Address" in line:
                        current_if["mac"] = line.split(':')[-1].strip()
                    elif "adapter" in line.lower():
                        current_if["name"] = line.split(':')[-1].strip()
                if current_if:
                    interfaces.append(current_if)
            
            return {
                "fqdn": fqdn,
                "primary_ip": primary_ip,
                "mac_address": self._get_resource("macaddress", self._get_mac_address()),
                "interfaces": interfaces
            }
        except Exception as e:
            logger.error("Error getting network info: %s", str(e))
            return {
                "fqdn": "N/A",
                "primary_ip": "N/A",
                "mac_address": "N/A",
                "interfaces": []
            }
    
    def get_os_info(self) -> Dict[str, Any]:
        """获取操作系统信息"""
        return {
            "platform": platform.system(),
            "version": platform.release(),
            "os_name": platform.platform(),
            "kernel_version": platform.version(),
            "timezone": time.tzname[time.daylight],
            "uptime": self._get_uptime()
        }
    
    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储信息"""
        try:
            if os.name == 'posix':
                _, df_output, _ = self._exec_command("df -h --output=source,fstype,size,avail,pcent,target")
                partitions = []
                for line in df_output.splitlines()[1:]:
                    if not line.strip(): continue
                    parts = line.split()
                    partitions.append({
                        "device": parts[0],
                        "fstype": parts[1],
                        "size": parts[2],
                        "free": parts[3],
                        "usage": parts[4],
                        "mountpoint": ' '.join(parts[5:])
                    })
                return {"partitions": partitions}
            elif os.name == 'nt':
                _, df_output, _ = self._exec_command(["wmic", "logicaldisk", "get", "caption,description,size,freespace"])
                return {"disks": df_output}
            else:
                return {"disks": "OS not supported"}
        except:
            return {"disks": "Error retrieving storage info"}
    
    def get_security_info(self) -> Dict[str, Any]:
        """获取安全信息"""
        info = {}
        
        # SELinux状态 (Linux)
        if os.name == 'posix':
            _, selinux_status, _ = self._exec_command("sestatus 2>/dev/null || echo")
            info["selinux"] = "enabled" in selinux_status.lower()
        
        # 防火墙状态 (Windows/Linux通用)
        if os.name == 'nt':
            _, firewall_status, _ = self._exec_command(
                "netsh advfirewall show allprofiles state | findstr ON"
            )
            info["firewall"] = firewall_status.strip() != ""
        else:
            _, iptables_status, _ = self._exec_command("iptables -L >/dev/null 2>&1; echo $?")
            info["firewall"] = int(iptables_status) == 0 if iptables_status.isdigit() else False
        
        # 安全补丁状态
        if os.name == 'nt':
            _, updates, _ = self._exec_command(
                "powershell Get-Hotfix | Measure-Object | Select-Object Count"
            )
            info["security_updates"] = re.search(r'Count\s*:\s*(\d+)', updates).group(1)
        else:
            if os.path.exists("/etc/redhat-release"):
                _, updates, _ = self._exec_command("yum list-sec | wc -l")
            elif os.path.exists("/etc/debian_version"):
                _, updates, _ = self._exec_command(
                    "apt list --upgradable 2>/dev/null | grep -i security | wc -l"
                )
            else:
                updates = "N/A"
            info["security_updates"] = updates.strip()
        
        return info
    
    def get_container_info(self) -> Dict[str, Any]:
        """检测容器环境"""
        # Docker
        docker_env = False
        try:
            _, docker_out, _ = self._exec_command("docker --version")
            docker_env = "Docker version" in docker_out
        except: pass
        
        # Kubernetes
        k8s_env = False
        try:
            _, kubeconfig_out, _ = self._exec_command("env | grep KUBECONFIG")
            k8s_env = "KUBECONFIG" in kubeconfig_out
        except: pass
        
        return {
            "is_containerized": os.path.exists("/.dockerenv") or docker_env or k8s_env,
            "docker": docker_env,
            "kubernetes": k8s_env
        }
    
    def _get_mac_address(self) -> str:
        """获取MAC地址"""
        mac = uuid.getnode()
        try:
            if (mac >> 40) & 0b1010 == 0b1010:  # 检查是否是有效的MAC
                return ':'.join([f'{(mac >> i) & 0xff:02x}' for i in range(0,48,8)][::-1])
        except:
            pass
        return "UNKNOWN"
    
    def _get_uptime(self) -> str:
        """获取系统的运行时间"""
        try:
            # 类Unix系统
            if os.name == 'posix':
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
            # Windows系统
            elif os.name == 'nt':
                _, uptime_out, _ = self._exec_command(
                    "powershell (get-date) - (gcim Win32_OperatingSystem).LastBootUpTime"
                )
                uptime_seconds = float(re.search(r'TotalSeconds\s*:\s*(\d+\.\d+)', uptime_out).group(1))
            else:
                raise OSError("Unsupported operating system")
            
            # 计算天、小时、分钟和秒
            days = int(uptime_seconds // (24 * 3600))
            hours = int((uptime_seconds % (24 * 3600)) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            
            return f"{days}d {hours}h {minutes}m {seconds}s"
        except Exception as e:
            logger.error("Error getting uptime: %s", str(e))
            return "N/A"
    
    @staticmethod
    def _convert_kb_to_gb(kb_value: Union[int, float, str]) -> str:
        """将KB转换为GB（保留两位小数）"""
        try:
            kb_value = float(kb_value)
            return f"{kb_value / SystemFacter.KB_TO_GB:.2f} GB" if kb_value > 0 else "0 GB"
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _convert_mb_to_gb(mb_value: Union[int, float, str]) -> str:
        """将MB转换为GB（保留两位小数）"""
        try:
            mb_value = float(mb_value)
            return f"{mb_value / SystemFacter.MB_TO_GB:.2f} GB" if mb_value > 0 else "0 GB"
        except (TypeError, ValueError):
            return "N/A"
    
    def collect_all_info(self) -> Dict[str, Any]:
        """收集所有可用的系统信息"""
        return {
            "cpu": self.get_cpu_info(),
            "memory": self.get_memory_info(),
            "network": self.get_network_info(),
            "os": self.get_os_info(),
            "storage": self.get_storage_info(),
            "security": self.get_security_info(),
            "container": self.get_container_info(),
            "overrides": self._resource_overrides,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "system_info": {
                "python_version": platform.python_version(),
                "hostname": platform.node(),
                "user": os.getlogin()
            }
        }


def main():
    """演示系统信息收集器的使用"""
    logger.info("Starting SystemFacter analysis")
    
    # 创建收集器实例
    facter = SystemFacter()
    
    # 收集所有系统信息
    system_info = facter.collect_all_info()
    
    # 以美观格式打印结果
    print("\n" + "="*80)
    print("系统综合分析报告".center(80))
    print("="*80)
    
    print("\n【主机与操作系统信息】")
    os_info = system_info['os']
    cpu_info = system_info['cpu']
    print(f"主机名: {system_info['system_info']['hostname']}")
    print(f"操作系统: {os_info['os_name']} | 内核版本: {os_info['kernel_version']}")
    print(f"时区: {os_info['timezone']} | 已启动时间: {os_info['uptime']}")
    print(f"处理器: {cpu_info['model']} | 物理核心: {cpu_info['physical_cores']} | 逻辑核心: {cpu_info['logical_cores']}")
    
    print("\n【内存和存储信息】")
    mem_info = system_info['memory']
    print(f"内存总量: {mem_info['total']} | 可用内存: {mem_info['free']}")
    print(f"交换分区: {mem_info['swap_total']} | 可用交换: {mem_info['swap_free']}")
    
    print("\n【网络信息】")
    net_info = system_info['network']
    print(f"主机 FQDN: {net_info['fqdn']}")
    print(f"主要 IP: {net_info['primary_ip']} | MAC地址: {net_info['mac_address']}")
    print("\n网络接口:")
    for idx, iface in enumerate(net_info['interfaces']):
        print(f"  接口 #{idx+1}: {iface['name']} | IP: {iface['ip']} | MAC: {iface['mac']}")
    
    print("\n【安全配置】")
    security_info = system_info['security']
    print(f"防火墙: {'启用' if security_info['firewall'] else '禁用'}")
    print(f"SELinux: {'启用' if security_info.get('selinux', False) else '禁用'}")
    print(f"待安装的安全补丁: {security_info.get('security_updates', 'N/A')}")
    
    print("\n【虚拟化与容器】")
    container_info = system_info['container']
    print(f"容器环境: {'是' if container_info['is_containerized'] else '否'}")
    if container_info['is_containerized']:
        print(f"  Docker: {'已安装' if container_info['docker'] else '未安装'}")
        print(f"  Kubernetes: {'环境检测到' if container_info['kubernetes'] else '未检测到'}")
    
    print("\n【附加信息】")
    print(f"报告生成时间: {system_info['timestamp']}")
    print(f"Python 版本: {system_info['system_info']['python_version']}")
    print(f"当前用户: {system_info['system_info']['user']}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
