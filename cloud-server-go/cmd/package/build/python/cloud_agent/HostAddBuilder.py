#!/usr/bin/env python3
"""
Cloud Agent - 主机添加构建脚本
用于在新主机上执行预检、硬件信息收集、安全配置和注册
"""

import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
import traceback
from typing import Dict, Any, Optional, Tuple, List

try:
    from cloud_agent.CloudConfig import CloudConfig
    from cloud_agent.NetUtil import NetUtil
    from cloud_agent.HostInfo import HostInfo
    from cloud_agent.Hardware import Hardware
    from cloud_agent.Utils import Utils
    from cloud_agent import Constants
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from cloud_agent.CloudConfig import CloudConfig
    from cloud_agent.NetUtil import NetUtil
    from cloud_agent.HostInfo import HostInfo
    from cloud_agent.Hardware import Hardware
    from cloud_agent.Utils import Utils
    from cloud_agent import Constants

logger = logging.getLogger(__name__)


class HostAddBuilder:
    """主机添加构建器 - 负责新主机的预处理和注册"""

    # 状态码定义
    STATUS_SUCCESS = 0
    STATUS_FAILED = 1
    STATUS_PENDING = 2
    STATUS_IN_PROGRESS = 3

    # 预检项
    PRECHECK_NETWORK = "network_connectivity"
    PRECHECK_SSH = "ssh_connectivity"
    PRECHECK_PORT = "port_available"
    PRECHECK_FIREWALL = "firewall_config"
    PRECHECK_DNS = "dns_resolution"

    def __init__(self, config: Optional[CloudConfig] = None):
        """初始化构建器"""
        self.config = config or CloudConfig()
        self.net_util = NetUtil(self.config)
        self.utils = Utils()
        self.hardware = Hardware(self.config)
        self.results: Dict[str, Any] = {}
        self.precheck_results: Dict[str, bool] = {}
        self.hardware_info: Dict[str, Any] = {}

    def execute(self, host_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行主机添加构建流程
        
        Args:
            host_params: 主机参数，包含 hostname, ip, ssh_port, ssh_user, ssh_password 等
            
        Returns:
            构建结果字典
        """
        self.results = {
            "status": self.STATUS_IN_PROGRESS,
            "hostname": host_params.get("hostname", ""),
            "ip": host_params.get("ip", ""),
            "timestamp": int(time.time() * 1000),
            "precheck": {},
            "hardware": {},
            "security": {},
            "errors": [],
            "warnings": []
        }

        try:
            logger.info(f"开始主机添加构建: {host_params.get('hostname')}({host_params.get('ip')})")
            
            # Step 1: 预检查 - 网络连通性、端口可用性等
            self._run_prechecks(host_params)
            
            # Step 2: 收集硬件信息
            self._collect_hardware_info(host_params)
            
            # Step 3: 安全检查
            self._run_security_checks(host_params)
            
            # Step 4: 生成注册信息
            registration_info = self._prepare_registration_info(host_params)
            
            self.results["registration"] = registration_info
            self.results["status"] = self.STATUS_SUCCESS
            logger.info(f"主机添加构建完成: {host_params.get('hostname')}")
            
        except Exception as e:
            self.results["status"] = self.STATUS_FAILED
            self.results["errors"].append({
                "phase": "main",
                "message": str(e),
                "trace": traceback.format_exc()
            })
            logger.error(f"主机添加构建失败: {str(e)}")
        
        return self.results

    def _run_prechecks(self, params: Dict[str, Any]) -> None:
        """执行预检查项"""
        logger.info("执行预检查...")
        
        hostname = params.get("hostname", "")
        ip = params.get("ip", "")
        ssh_port = params.get("ssh_port", 12308)
        
        # 1. DNS解析检查
        try:
            if hostname and hostname != ip:
                resolved_ip = socket.gethostbyname(hostname)
                self.precheck_results[self.PRECHECK_DNS] = True
                logger.info(f"DNS解析成功: {hostname} -> {resolved_ip}")
            else:
                self.precheck_results[self.PRECHECK_DNS] = True
        except Exception as e:
            self.precheck_results[self.PRECHECK_DNS] = False
            self.results["warnings"].append(f"DNS解析失败: {str(e)}")
            logger.warning(f"DNS解析检查跳过: {str(e)}")
        
        # 2. 网络连通性检查 (本地主机始终成功)
        is_local = self._is_localhost(ip)
        if is_local:
            self.precheck_results[self.PRECHECK_NETWORK] = True
            logger.info("本地主机网络连通性检查通过")
        else:
            self.precheck_results[self.PRECHECK_NETWORK] = self._check_network_connectivity(ip)
        
        # 3. 端口可用性检查
        self.precheck_results[self.PRECHECK_PORT] = self._check_port_available(ip, ssh_port)
        
        # 4. SSH连接检查 (本地跳过)
        if is_local:
            self.precheck_results[self.PRECHECK_SSH] = True
            logger.info("本地主机SSH检查跳过")
        else:
            self.precheck_results[self.PRECHECK_SSH] = self._check_ssh_connectivity(
                ip, params.get("ssh_user", "root"), 
                params.get("ssh_password", ""), ssh_port
            )
        
        # 5. 防火墙配置检查
        self.precheck_results[self.PRECHECK_FIREWALL] = self._check_firewall_config(ip)
        
        self.results["precheck"] = {
            "passed": all(self.precheck_results.values()),
            "details": self.precheck_results
        }
        
        # 如果关键预检失败，记录警告但继续
        if not all(self.precheck_results.values()):
            failed = [k for k, v in self.precheck_results.items() if not v]
            self.results["warnings"].append(f"部分预检失败: {', '.join(failed)}")
            logger.warning(f"预检失败项: {failed}")

    def _is_localhost(self, ip: str) -> bool:
        """判断是否为本地主机"""
        localhost_ips = ["127.0.0.1", "localhost", "0.0.0.0", "::1"]
        return ip.lower() in [i.lower() for i in localhost_ips] or ip == socket.gethostbyname(socket.gethostname())

    def _check_network_connectivity(self, ip: str) -> bool:
        """检查网络连通性"""
        try:
            # 使用ping命令检查连通性
            param = "-n" if os.name == "nt" else "-c"
            command = ["ping", param, "1", "-W", "2", ip]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"网络连通性检查失败: {str(e)}")
            return False

    def _check_port_available(self, ip: str, port: int) -> bool:
        """检查端口可用性"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            result = sock.connect_ex((ip, port))
            sock.close()
            # 端口可用（未占用）或连接被拒绝（服务可能不存在但网络通）
            return result in [0, 111, 10061, 10065]
        except Exception as e:
            logger.warning(f"端口检查失败 ({ip}:{port}): {str(e)}")
            return False

    def _check_ssh_connectivity(self, ip: str, user: str, password: str, port: int) -> bool:
        """检查SSH连接"""
        if not password:
            logger.info("未提供SSH密码，跳过SSH连接检查")
            return True
            
        try:
            # 尝试使用ssh命令测试连接
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(ip, port=port, username=user, password=password, timeout=5)
                client.close()
                return True
            except:
                pass
        except ImportError:
            pass
        
        # 备用方法：使用sshpass
        if password:
            try:
                cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p {port} {user}@{ip} echo 'connected'"
                result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                return result.returncode == 0
            except Exception as e:
                logger.warning(f"SSH连接检查失败: {str(e)}")
        
        return True  # 默认通过，让后续处理失败

    def _check_firewall_config(self, ip: str) -> bool:
        """检查防火墙配置"""
        if self._is_localhost(ip):
            return True
            
        # 检查常见端口是否被防火墙阻止
        ports_to_check = [22, 8080, 8443]
        blocked_ports = []
        
        for port in ports_to_check:
            if not self._check_port_available(ip, port):
                blocked_ports.append(port)
        
        if blocked_ports:
            self.results["warnings"].append(f"端口可能被防火墙阻止: {blocked_ports}")
        
        return True  # 防火墙检查不作为硬性失败条件

    def _collect_hardware_info(self, params: Dict[str, Any]) -> None:
        """收集硬件信息"""
        logger.info("收集硬件信息...")
        
        try:
            # 使用Hardware类获取硬件信息
            hardware_info = self.hardware.get_hardware_info()
            self.hardware_info = hardware_info
            
            # 补充CPU信息
            self.hardware_info["cpu"] = {
                "count": os.cpu_count() or 0,
                "info": self._get_cpu_info()
            }
            
            # 补充内存信息
            self.hardware_info["memory"] = self._get_memory_info()
            
            # 补充磁盘信息
            self.hardware_info["disk"] = self._get_disk_info()
            
            # 补充网络信息
            self.hardware_info["network"] = self._get_network_info()
            
            # 补充操作系统信息
            self.hardware_info["os"] = self._get_os_info()
            
            self.results["hardware"] = self.hardware_info
            logger.info("硬件信息收集完成")
            
        except Exception as e:
            self.results["warnings"].append(f"硬件信息收集部分失败: {str(e)}")
            logger.warning(f"硬件信息收集失败: {str(e)}")
            self.results["hardware"] = {"error": str(e)}

    def _get_cpu_info(self) -> Dict[str, Any]:
        """获取CPU信息"""
        cpu_info = {"cores": os.cpu_count() or 0, "model": ""}
        
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["wmic", "cpu", "get", "name"],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    cpu_info["model"] = lines[1].strip()
            except:
                pass
        else:
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_info["model"] = line.split(":")[1].strip()
                            break
            except:
                pass
        
        return cpu_info

    def _get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        memory_info = {"total": 0, "available": 0, "used": 0}
        
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory"],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    total = int(parts[0])
                    free = int(parts[1])
                    memory_info["total"] = total * 1024  # KB to bytes
                    memory_info["available"] = free * 1024
                    memory_info["used"] = (total - free) * 1024
            except:
                pass
        else:
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            memory_info["total"] = int(line.split()[1]) * 1024
                        elif line.startswith("MemAvailable:"):
                            memory_info["available"] = int(line.split()[1]) * 1024
                        elif line.startswith("MemFree:"):
                            memory_info["available"] = int(line.split()[1]) * 1024
            except:
                pass
        
        return memory_info

    def _get_disk_info(self) -> Dict[str, Any]:
        """获取磁盘信息"""
        disk_info = {"disks": [], "total": 0}
        
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["wmic", "logicaldisk", "get", "size,freespace,deviceid"],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        disk_info["disks"].append({
                            "device": parts[0],
                            "free": int(parts[1]) * 1024 * 1024,
                            "size": int(parts[2]) * 1024 * 1024
                        })
            except:
                pass
        else:
            try:
                result = subprocess.run(
                    ["df", "-B1", "-T"],
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 7:
                        try:
                            disk_info["disks"].append({
                                "device": parts[1],
                                "mount": parts[6],
                                "total": int(parts[2]),
                                "used": int(parts[3]),
                                "available": int(parts[4])
                            })
                            disk_info["total"] += int(parts[2])
                        except:
                            pass
            except:
                pass
        
        return disk_info

    def _get_network_info(self) -> Dict[str, Any]:
        """获取网络信息"""
        network_info = {"interfaces": [], "hostname": socket.gethostname()}
        
        try:
            hostname = socket.gethostname()
            network_info["hostname"] = hostname
            network_info["ip_addresses"] = socket.gethostbyname_ex(hostname)[2]
        except:
            pass
        
        if os.name != "nt":
            try:
                result = subprocess.run(
                    ["ip", "addr", "show"],
                    capture_output=True, text=True, timeout=5
                )
                network_info["raw_output"] = result.stdout
            except:
                pass
        
        return network_info

    def _get_os_info(self) -> Dict[str, Any]:
        """获取操作系统信息"""
        os_info = {
            "type": os.name,
            "platform": sys.platform,
            "release": "",
            "version": "",
            "arch": platform.machine()
        }
        
        try:
            os_info["release"] = platform.release()
            os_info["version"] = platform.version()
            os_info["arch"] = platform.machine()
        except:
            pass
        
        return os_info

    def _run_security_checks(self, params: Dict[str, Any]) -> None:
        """运行安全检查"""
        logger.info("执行安全检查...")
        
        security_checks = {
            "iptables": self._check_iptables(),
            "selinux": self._check_selinux(),
            "hosts_equiv": self._check_hosts_equiv(),
            "empty_passwords": self._check_empty_passwords()
        }
        
        self.results["security"] = security_checks
        logger.info("安全检查完成")

    def _check_iptables(self) -> Dict[str, Any]:
        """检查iptables状态"""
        result = {"enabled": False, "rules_count": 0}
        
        if os.name == "nt":
            return result
            
        try:
            output = subprocess.run(
                ["iptables", "-L", "-n"],
                capture_output=True, text=True, timeout=5
            )
            result["enabled"] = output.returncode == 0
            if output.stdout:
                result["rules_count"] = len(output.stdout.strip().split("\n"))
        except:
            pass
        
        return result

    def _check_selinux(self) -> Dict[str, Any]:
        """检查SELinux状态"""
        result = {"status": "unknown", "enforcing": False}
        
        if os.name == "nt":
            result["status"] = "not_applicable"
            return result
            
        try:
            with open("/sys/fs/selinux/enforce", "r") as f:
                result["enforcing"] = f.read().strip() == "1"
                result["status"] = "enforcing" if result["enforcing"] else "permissive"
        except:
            try:
                output = subprocess.run(
                    ["getenforce"],
                    capture_output=True, text=True, timeout=5
                )
                result["status"] = output.stdout.strip().lower()
                result["enforcing"] = result["status"] == "enforcing"
            except:
                result["status"] = "disabled"
        
        return result

    def _check_hosts_equiv(self) -> Dict[str, Any]:
        """检查hosts.equiv文件"""
        result = {"exists": False, "path": "/etc/hosts.equiv", "entries": []}
        
        if os.name == "nt":
            result["path"] = "C:\\Windows\\System32\\drivers\\etc\\hosts"
        
        try:
            result["exists"] = os.path.exists(result["path"])
            if result["exists"]:
                with open(result["path"], "r") as f:
                    result["entries"] = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except:
            pass
        
        return result

    def _check_empty_passwords(self) -> Dict[str, Any]:
        """检查空密码账户"""
        result = {"found": False, "accounts": []}
        
        if os.name == "nt":
            return result
            
        try:
            with open("/etc/shadow", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) > 1 and parts[1] in ["", "!!"]:
                        result["found"] = True
                        result["accounts"].append(parts[0])
        except:
            pass
        
        return result

    def _prepare_registration_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """准备注册信息"""
        return {
            "hostname": params.get("hostname", socket.gethostname()),
            "ip": params.get("ip", ""),
            "publicHostName": params.get("publicHostName", ""),
            "rackInfo": params.get("rackInfo", "/default-rack"),
            "sshPort": params.get("ssh_port", 12308),
            "sshUser": params.get("ssh_user", "root"),
            "osType": self.hardware_info.get("os", {}).get("type", "Linux"),
            "osArch": self.hardware_info.get("os", {}).get("arch", "x86_64"),
            "cpuCount": self.hardware_info.get("cpu", {}).get("count", 0),
            "cpuInfo": self.hardware_info.get("cpu", {}).get("model", ""),
            "totalMemory": self.hardware_info.get("memory", {}).get("total", 0),
            "totalDisk": self.hardware_info.get("disk", {}).get("total", 0),
            "components": params.get("components", []),
            "agentVersion": self._get_agent_version()
        }

    def _get_agent_version(self) -> str:
        """获取Agent版本"""
        return "1.0.0"


def execute_build(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行主机添加构建的入口函数
    
    Args:
        params: 主机参数字典
        
    Returns:
        构建结果
    """
    builder = HostAddBuilder()
    return builder.execute(params)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cloud Agent 主机添加构建工具")
    parser.add_argument("--hostname", required=True, help="主机名")
    parser.add_argument("--ip", required=True, help="IP地址")
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH端口")
    parser.add_argument("--ssh-user", default="root", help="SSH用户名")
    parser.add_argument("--ssh-password", default="", help="SSH密码")
    parser.add_argument("--rack", default="/default-rack", help="机架信息")
    parser.add_argument("--output", help="输出文件路径")
    
    args = parser.parse_args()
    
    params = {
        "hostname": args.hostname,
        "ip": args.ip,
        "ssh_port": args.ssh_port,
        "ssh_user": args.ssh_user,
        "ssh_password": args.ssh_password,
        "rackInfo": args.rack
    }
    
    result = execute_build(params)
    
    # 输出结果
    output = json.dumps(result, indent=2, ensure_ascii=False)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"结果已保存到: {args.output}")
    else:
        print(output)
    
    # 返回适当的退出码
    sys.exit(0 if result.get("status") == 0 else 1)


if __name__ == "__main__":
    main()