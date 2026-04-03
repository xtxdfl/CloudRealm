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

import unittest
import socket
import json
from unittest.mock import patch, MagicMock, Mock, call
from only_for_platform import not_for_platform, PLATFORM_WINDOWS
from Hardware import Hardware
from cloudConfig import cloudConfig
from Facter import Facter, FacterLinux
from cloud_commons import OSCheck
import distro
import subprocess


class HardwareTestBase(unittest.TestCase):
    """硬件信息测试基类"""
    
    def setUp(self):
        # 准备基础mock
        self.config = MagicMock()
        self.df_output = """
Filesystem      Type  1024-blocks  Used Available Capacity Mounted on
/dev/main_ext4  ext4    10485760  2048   10483712     20% /
/dev/data_ext4  ext4   104857600 10240  104753360     10% /data
/tmpfs          tmpfs    1024000     4   10239996      1% /dev
"""
        self.os_type = "suse"
        self.os_version = "11"
        
        # 公共patch设置
        self.patch_distro = patch.object(
            distro, "linux_distribution", return_value=(self.os_type, self.os_version, "Final")
        )
        self.patch_fqdn = patch.object(socket, "getfqdn", return_value="cloud.apache.org")
        self.patch_hostbyname = patch.object(socket, "gethostbyname", return_value="192.168.1.1")
        
        # 启动公共patch
        self.patch_distro.start()
        self.patch_fqdn.start()
        self.patch_hostbyname.start()
        
        # Facter特定mock
        self.patch_hostname = patch.object(
            FacterLinux, "setDataIfConfigShortOutput", 
            return_value="""Iface   Status
eth0    active
eth1    inactive""")
        self.patch_iplink = patch.object(
            FacterLinux, "setDataIpLinkOutput", 
            return_value="""1: lo: <LOOPBACK> mtu 65536 state DOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00""")
        
        self.patch_hostname.start()
        self.patch_iplink.start()
        
        # Hardware特定mock
        self.patch_osdisks = patch.object(Hardware, "osdisks", return_value=[])
        self.patch_osdisks.start()
        self.patch_writable = patch.object(Hardware, "_chk_writable_mount", return_value=True)
        self.patch_writable.start()
        
        # 默认配置
        self.config = cloudConfig()
    
    def tearDown(self):
        # 停止所有patch
        self.patch_distro.stop()
        self.patch_fqdn.stop()
        self.patch_hostbyname.stop()
        self.patch_hostname.stop()
        self.patch_iplink.stop()
        self.patch_osdisks.stop()
        self.patch_writable.stop()


@not_for_platform(PLATFORM_WINDOWS)
class MountPointsTests(HardwareTestBase):
    """测试挂载点信息收集功?""
    
    @patch("resource_management.core.shell.call")
    def test_writable_mount_points(self, shell_call_mock):
        """测试收集可写挂载?""
        shell_call_mock.return_value = (0, self.df_output, "")
        
        hardware = Hardware(config=self.config)
        result = hardware.get()
        
        self.assertEqual(len(result["mounts"]), 2)
        self.assertEqual(len(hardware.osdisks()), 2)
        
        for mount in result["mounts"]:
            self.assertIsInstance(mount["available"], int)
            self.assertIsInstance(mount["size"], int)
            self.assertIsInstance(mount["used"], int)
            self.assertIsInstance(mount["percent"], (int, float))
            self.assertTrue(mount["size"] > 0)
            self.assertTrue(mount["mountpoint"].startswith("/"))
            self.assertTrue(mount["device"].startswith("/dev/"))
            self.assertTrue(mount["type"] in ["ext4", "tmpfs"])
    
    @patch("cloud_agent.Hardware.path_isfile")
    @patch("resource_management.core.shell.call")
    def test_ignore_special_filesystems(self, shell_call_mock, isfile_mock):
        """测试忽略特殊文件系统"""
        # 添加特殊文件系统到df输出
        df_output = self.df_output + """
tmpfs          tmpfs    1024000     4   10239996  1% /etc/hosts
tmpfs          tmpfs    1024000     4   10239996  1% /run/secrets
tmpfs          tmpfs    1024000     4   10239996  1% /sys/fs/cgroup
tmpfs          tmpfs    1024000     4   10239996  1% /dev/shm
""".strip()
        shell_call_mock.return_value = (0, df_output, "")
        
        # 标记某些文件为特殊文?        isfile_mock.side_effect = lambda path: path in [
            "/etc/hosts", "/etc/resolv.conf", "/etc/hostname"]
        
        # 标记某些挂载点为只读
        with patch.object(Hardware, "_chk_writable_mount") as writable_mock:
            writable_mock.side_effect = lambda path: path not in ["/run/secrets"]
            
            hardware = Hardware(config=self.config)
            mounts = hardware.osdisks()
            
            # 验证只保留可写挂载点
            self.assertEqual(len(mounts), 2)
            mount_points = {m["mountpoint"] for m in mounts}
            self.assertNotIn("/run/secrets", mount_points)
            self.assertNotIn("/sys/fs/cgroup", mount_points)
            self.assertNotIn("/dev/shm", mount_points)
    
    def test_mount_point_blacklist(self):
        """测试挂载点黑名单功能"""
        # 准备测试数据
        test_config = {
            "agent": {
                "ignore_mount_points": "/blacklisted,/another/blacklist"
            }
        }
        df_output = self.df_output + """
/dev/blackdisk  ext4   10485760  5120    10480640  50% /blacklisted
/dev/whitedisk  ext4   10485760  2048    10483712  20% /whitelisted
/dev/subdisk    ext4   10485760  2048    10483712  20% /blacklisted/subdir
""".strip()
        
        # 配置mock
        config_mock = Mock()
        config_mock.get.side_effect = (
            lambda section, key, default="": test_config.get(section, {}).get(key, default))
        config_mock.has_option.side_effect = (
            lambda section, key: key in test_config.get(section, {}))
        
        # 执行收集
        with patch("resource_management.core.shell.call") as shell_call_mock:
            shell_call_mock.return_value = (0, df_output, "")
            hardware = Hardware(config=config_mock)
            mounts = hardware.osdisks()
            
            # 验证黑名单生?            mount_points = {m["mountpoint"] for m in mounts}
            self.assertNotIn("/blacklisted", mount_points)
            self.assertNotIn("/blacklisted/subdir", mount_points)
            self.assertIn("/whitelisted", mount_points)
    
    @patch("resource_management.core.shell.call")
    def test_remote_mount_configuration(self, shell_call_mock):
        """测试远程挂载点配置选项"""
        # 默认配置 - 不收集远程挂?        timeout = 10
        hardware = Hardware(config=self.config)
        hardware.osdisks()
        shell_call_mock.assert_called_with(
            ["timeout", str(timeout), "df", "-kPT", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            quiet=True,
        )
        
        # 配置收集远程挂载
        self.config.set(cloudConfig.cloud_PROPERTIES_CATEGORY, Hardware.CHECK_REMOTE_MOUNTS_KEY, "true")
        hardware = Hardware(config=self.config)
        hardware.osdisks()
        shell_call_mock.assert_called_with(
            ["timeout", str(timeout), "df", "-kPT"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            quiet=True,
        )
        
        # 自定义超时时?        custom_timeout = 5
        self.config.set(cloudConfig.cloud_PROPERTIES_CATEGORY, Hardware.CHECK_REMOTE_MOUNTS_TIMEOUT_KEY, str(custom_timeout))
        hardware = Hardware(config=self.config)
        hardware.osdisks()
        shell_call_mock.assert_called_with(
            ["timeout", str(custom_timeout), "df", "-kPT"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=custom_timeout,
            quiet=True,
        )
    
    def test_df_parser(self):
        """测试df输出解析"""
        test_cases = [
            # 标准有效?            {
                "input": "/dev/disk1 ext4 10485760 2048 10483712 2% /",
                "expected": {
                    "device": "/dev/disk1",
                    "type": "ext4",
                    "size": 10485760 * 1024,
                    "used": 2048 * 1024,
                    "available": 10483712 * 1024,
                    "percent": 2,
                    "mountpoint": "/"
                }
            },
            # 带空格的文件系统?            {
                "input": "/dev/mapper/disk 1 ext4 10485760 2048 10483712 2% /mnt/disk 1",
                "expected": {
                    "device": "/dev/mapper/disk 1",
                    "type": "ext4",
                    "size": 10485760 * 1024,
                    "used": 2048 * 1024,
                    "available": 10483712 * 1024,
                    "percent": 2,
                    "mountpoint": "/mnt/disk 1"
                }
            },
            # 字段数量错误（太少）
            {
                "input": "/dev/disk1 ext4 10485760 2048 10483712",
                "expected": None
            },
            # 字段数量错误（太多）
            {
                "input": "/dev/disk1 ext4 10485760 2048 10483712 2% / extra",
                "expected": None
            },
            # 无效的数字?            {
                "input": "/dev/disk1 ext4 invalid 2048 10483712 2% /",
                "expected": None
            },
        ]
        
        for case in test_cases:
            with self.subTest(case=case["input"]):
                try:
                    result = next(Hardware._parse_df([case["input"]]))
                except StopIteration:
                    result = None
                
                self.assertEqual(result, case["expected"])


@not_for_platform(PLATFORM_WINDOWS)
class FacterInfoTests(HardwareTestBase):
    """测试Facter信息收集功能"""
    
    def test_hostname_parsing(self):
        """测试主机名解?""
        with patch.object(OSCheck, "get_os_type", return_value=self.os_type):
            with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
                with patch.object(socket, "getfqdn", return_value="host01.example.com"):
                    with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                        facter = Facter(config=self.config)
                        info = facter.facterInfo()
                        
                        self.assertEqual(info["hostname"], "host01")
                        self.assertEqual(info["domain"], "example.com")
                        self.assertEqual(info["fqdn"], "host01.example.com")
    
    def test_uptime_calculation(self):
        """测试正常运行时间计算"""
        test_cases = [
            (86400, {"uptime_seconds": "86400", "uptime_hours": "24", "uptime_days": "1"}),
            (3600, {"uptime_seconds": "3600", "uptime_hours": "1", "uptime_days": "0"}),
            (172800, {"uptime_seconds": "172800", "uptime_hours": "48", "uptime_days": "2"}),
        ]
        
        with patch.object(OSCheck, "get_os_type", return_value=self.os_type):
            with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
                for seconds, expected in test_cases:
                    with self.subTest(seconds=seconds):
                        with patch.object(FacterLinux, "setDataUpTimeOutput", return_value=f"{seconds} 0.0"):
                            with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                                facter = Facter(config=self.config)
                                info = facter.facterInfo()
                                
                                self.assertEqual(info["uptime_seconds"], expected["uptime_seconds"])
                                self.assertEqual(info["uptime_hours"], expected["uptime_hours"])
                                self.assertEqual(info["uptime_days"], expected["uptime_days"])
    
    def test_memory_info(self):
        """测试内存信息收集"""
        meminfo_output = """
MemTotal:        2097152 kB
MemFree:          1048576 kB
SwapTotal:        4194304 kB
SwapFree:         3145728 kB
        """.strip()
        
        with patch.object(OSCheck, "get_os_type", return_value=self.os_type):
            with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
                with patch.object(FacterLinux, "setMemInfoOutput", return_value=meminfo_output):
                    with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                        facter = Facter(config=self.config)
                        info = facter.facterInfo()
                        
                        self.assertEqual(info["memorysize"], 2097152)
                        self.assertEqual(info["memorytotal"], 2097152)
                        self.assertEqual(info["memoryfree"], 1048576)
                        self.assertEqual(info["swapsize"], "4.00 GB")
                        self.assertEqual(info["swapfree"], "3.00 GB")
    
    def test_network_info(self):
        """测试网络接口信息"""
        with patch.object(OSCheck, "get_os_type", return_value=self.os_type):
            with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
                with patch.object(Facter, "getIpAddress", return_value="192.168.1.100"):
                    with patch.object(FacterLinux, "get_ip_address_by_ifname", return_value="255.255.255.0"):
                        with patch.object(socket, "inet_ntoa", return_value="255.255.255.0"):
                            with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                                facter = Facter(config=self.config)
                                info = facter.facterInfo()
                                
                                self.assertEqual(info["ipaddress"], "192.168.1.100")
                                self.assertEqual(info["netmask"], "255.255.255.0")
                                self.assertIn("interfaces", info)
    
    def test_os_family_info(self):
        """测试操作系统家族信息"""
        test_cases = [
            ("suse", "linux", "suse", "suse"),
            ("redhat", "rhel", "redhat", "redhat"),
            ("ubuntu", "debian", "ubuntu", "ubuntu"),
            ("windows", "win", "windows", "None"),
        ]
        
        with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
            for os_type, os_family, expected_os, expected_family in test_cases:
                with self.subTest(os_type=os_type):
                    with patch.object(OSCheck, "get_os_type", return_value=os_type):
                        with patch.object(OSCheck, "get_os_family", return_value=os_family):
                            with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                                facter = Facter(config=self.config)
                                info = facter.facterInfo()
                                
                                self.assertEqual(info["operatingsystem"], os_type)
                                self.assertEqual(info["osfamily"], os_family)
    
    @patch("glob.glob")
    @patch("builtins.open")
    @patch("json.loads")
    def test_system_resource_overrides(self, json_loads, open_mock, glob_mock):
        """测试系统资源覆盖功能"""
        # 准备mock数据
        glob_mock.return_value = ["/etc/cloud/resource1.json", "/etc/cloud/resource2.json"]
        file_mock1 = MagicMock()
        file_mock1.read.return_value = '{"cpu": "8", "memory": "16GB"}'
        file_mock2 = MagicMock()
        file_mock2.read.return_value = '{"disk_size": "1024GB"}'
        
        open_mock.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=file_mock1)),
            MagicMock(__enter__=MagicMock(return_value=file_mock2))
        ]
        json_loads.side_effect = [
            {"cpu": "8", "memory": "16GB"},
            {"disk_size": "1024GB"}
        ]
        
        # 配置资源覆盖路径
        self.config.set(cloudConfig.cloud_PROPERTIES_CATEGORY, "resource_overrides_path", "/etc/cloud")
        
        # 获取覆盖数据
        with patch.object(os.path, "exists", return_value=True):
            with patch.object(os.path, "isdir", return_value=True):
                with patch("os.path.join", side_effect=lambda a, b: f"{a}/{b}"):
                    with patch.object(Facter, "getSystemResourceOverrides") as overrides_mock:
                        facter = Facter(config=self.config)
                        _ = facter.facterInfo()  # 触发覆盖加载
                        
                        # 验证覆盖逻辑
                        overrides_mock.return_value = {"cpu": "8", "memory": "16GB", "disk_size": "1024GB"}
                        self.assertEqual(len(overrides_mock.call_args[0]), 0)
                        
                        # 验证文件操作
                        self.assertEqual(open_mock.call_count, 2)
                        self.assertEqual(json_loads.call_count, 2)


class HardwareInterfaceTests(HardwareTestBase):
    """测试网络接口信息收集功能"""
    
    @patch("fcntl.ioctl")
    @patch("socket.socket")
    @patch("struct.pack")
    @patch("socket.inet_ntoa")
    def test_interface_info_with_ifconfig(self, inet_ntoa_mock, struct_pack_mock, sock_mock, _):
        """测试使用ifconfig收集接口信息"""
        # 配置mock返回?        inet_ntoa_mock.return_value = "255.255.255.0"
        sock_mock.return_value.if_nameindex.return_value = [
            (1, "eth0"),
            (2, "lo")
        ]
        
        # 获取网络信息
        with patch.object(OSCheck, "get_os_type", return_value=self.os_type):
            with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
                with patch.object(Facter, "getIpAddress", return_value="10.0.1.100"):
                    with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                        facter = Facter(config=self.config)
                        info = facter.facterInfo()
                        
                        # 验证接口信息
                        self.assertEqual(info["netmask"], "255.255.255.0")
                        self.assertTrue("interfaces" in info)
                        self.assertTrue("eth0" in info["interfaces"])
                        self.assertTrue("lo" in info["interfaces"])
    
    @patch("fcntl.ioctl")
    @patch("socket.socket")
    @patch("struct.pack")
    @patch("socket.inet_ntoa")
    def test_interface_info_without_ifconfig(self, inet_ntoa_mock, struct_pack_mock, sock_mock, _):
        """测试使用ip link收集接口信息"""
        # 配置无ifconfig数据
        with patch.object(FacterLinux, "setDataIfConfigShortOutput", return_value=""):
            # 配置mock返回?            inet_ntoa_mock.return_value = "255.255.255.0"
            sock_mock.return_value.if_nameindex.return_value = [
                (1, "eth0"),
                (2, "lo")
            ]
            
            # 获取网络信息
            with patch.object(OSCheck, "get_os_type", return_value=self.os_type):
                with patch.object(OSCheck, "get_os_version", return_value=self.os_version):
                    with patch.object(Facter, "getIpAddress", return_value="10.0.1.100"):
                        with patch.object(Facter, "getSystemResourceOverrides", return_value={}):
                            facter = Facter(config=self.config)
                            info = facter.facterInfo()
                            
                            # 验证接口信息
                            self.assertEqual(info["netmask"], "255.255.255.0")
                            self.assertTrue("interfaces" in info)
                            self.assertTrue("eth0" in info["interfaces"])
                            self.assertTrue("lo" in info["interfaces"])


if __name__ == "__main__":
    unittest.main()

