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
See the License for specific language governing permissions and
limitations under the License.
"""

import os
import sys
import socket
import logging
import unittest
import tempfile
import pwd
import glob
from unittest.mock import MagicMock, patch, call, mock_open
from HostInfo import HostInfoLinux
from cloud_commons import OSCheck, OSConst, Firewall
from cloud_commons.os_check import OSConst, OSCheck

# 测试配置
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data", "host_info")
if not os.path.exists(TEST_DATA_DIR):
    os.makedirs(TEST_DATA_DIR)

# 测试基础?class HostInfoTestBase(unittest.TestCase):
    """主机信息测试基类，提供通用工具方法"""
    
    def setUp(self):
        """创建测试环境"""
        self.logger = MagicMock(spec=logging.Logger)
        self.host_info = HostInfoLinux()
        
        # 创建临时目录结构
        self.temp_dir = tempfile.mkdtemp(prefix="hostinfo_test_")
        self.test_users = [
            {"name": "user1", "homeDir": os.path.join(self.temp_dir, "home", "user1")},
            {"name": "user2", "homeDir": os.path.join(self.temp_dir, "home", "user2")}
        ]
        self.create_test_directories()
    
    def tearDown(self):
        """清理测试环境"""
        # 移除临时目录
        if os.path.exists(self.temp_dir):
            os.system(f"rm -rf {self.temp_dir}")
    
    def create_test_directories(self):
        """创建测试目录结构"""
        # 基础目录创建
        os.makedirs(os.path.join(self.temp_dir, "etc", "conf"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, "var", "lib"), exist_ok=True)
        
        # 用户主目?        for user in self.test_users:
            if "homeDir" in user:
                os.makedirs(user["homeDir"], exist_ok=True)


class DirectoryStructureTests(HostInfoTestBase):
    """测试目录结构和类型检测功?""
    
    @patch("os.path.exists")
    def test_directory_type_detection(self, exists_mock):
        """测试不同类型目录的准确识?""
        # 为不同类型目录配置模拟响?        test_cases = [
            ("existent_file", "file", [False, True, True, False, True]),
            ("symlink_to_dir", "sym_link", [True, False, False, True]),
            ("standard_dir", "directory", [True, False, True]),
            ("nonexistent", "not_exist", [False, False]),
            ("unknown_type", "unknown", [True, False, False])
        ]
        
        for path_name, expected_type, exists_values in test_cases:
            path = os.path.join(self.temp_dir, path_name)
            with self.subTest(path=path, expected=expected_type):
                # 设置模拟返回值序?                exists_mock.side_effect = exists_values
                result = self.host_info.dirType(path)
                self.assertEqual(result, expected_type)

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_hadoop_directory_counters(self, exists_mock, glob_mock):
        """测试Hadoop相关目录的计数功?""
        base_path = os.path.join(self.temp_dir, "test_dir")
        
        # 测试用例：目录存在且有内?        exists_mock.return_value = True
        glob_mock.return_value = ["file1", "file2", "file3"]
        count = self.host_info.hadoopVarRunCount(base_path)
        self.assertEqual(count, 3)
        
        # 测试用例：目录存在但为空
        glob_mock.return_value = []
        count = self.host_info.hadoopVarRunCount(base_path)
        self.assertEqual(count, 0)
        
        # 测试用例：目录不存在
        exists_mock.return_value = False
        count = self.host_info.hadoopVarRunCount(base_path)
        self.assertEqual(count, 0)
    
    @patch("os.path.realpath")
    @patch("os.path.islink")
    @patch("os.listdir")
    @patch("os.path.exists")
    def test_etc_alternatives_analysis(self, exists_mock, listdir_mock, islink_mock, realpath_mock):
        """测试 /etc/alternatives 配置解析"""
        # 准备测试环境
        etc_dir = os.path.join(self.temp_dir, "etc", "alternatives")
        config_name = "sample_config"
        
        # 设置模拟响应
        exists_mock.return_value = True
        listdir_mock.return_value = [config_name]
        islink_mock.return_value = True
        realpath_mock.return_value = os.path.join(etc_dir, "real_config")
        
        # 执行被测试方?        results = []
        self.host_info.etcAlternativesConf("test_project", results)
        
        # 验证解析结果
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], config_name)
        self.assertEqual(results[0]["target"], realpath_mock.return_value)


class UserManagementTests(HostInfoTestBase):
    """测试用户账户管理功能"""
    
    @patch.object(pwd, "getpwall")
    def test_user_account_validation(self, getpwall_mock):
        """测试有效的用户账户检?""
        # 创建3个测试用户账?        test_users = [
            pwd.struct_passwd(("testuser", "*", 1000, 1000, "Test User", 
                              os.path.join(self.temp_dir, "home/testuser"), "/bin/bash")),
            pwd.struct_passwd(("testuser2", "*", 1001, 1001, "Test User 2", 
                              os.path.join(self.temp_dir, "home/testuser2"), "/bin/bash")),
            pwd.struct_passwd(("nonexistent_dir_user", "*", 1002, 1002, 
                              "Non-existent Home", "/invalid/home", "/bin/bash"))
        ]
        getpwall_mock.return_value = test_users
        
        # 获取用户列表
        user_list = []
        self.host_info.checkUsers(["testuser", "testuser2", "nonexistent_dir_user"], user_list)
        
        # 验证检测结?        self.assertEqual(len(user_list), 3)
        
        # 验证有效用户账户
        valid_user = next(u for u in user_list if u["name"] == "testuser")
        self.assertEqual(valid_user["status"], "Available")
        self.assertEqual(valid_user["homeDir"], test_users[0].pw_dir)
        
        # 验证无效主目录用?        invalid_home_user = next(u for u in user_list if u["name"] == "nonexistent_dir_user")
        self.assertEqual(invalid_home_user["status"], "Home Directory Missing")


class SystemServiceTests(HostInfoTestBase):
    """测试系统服务状态监测功?""
    
    @patch.object(OSCheck, "get_os_type", return_value="redhat")
    @patch("resource_management.core.shell.call")
    def test_service_health_evaluation(self, call_mock, _):
        """测试服务健康状态评估逻辑"""
        # 服务测试用例配置
        service_test_cases = [
            {
                "services": ("httpd",),
                "status": "Healthy",
                "output": "service is active",
                "code": 0
            },
            {
                "services": ("nginx",),
                "status": "Unhealthy",
                "output": "service not found",
                "code": 127
            },
            {
                "services": ("mysql", "mariadb"),
                "status": "Unhealthy",
                "output": "all services inactive",
                "code": 1
            },
            {
                "services": ("invalid-service",),
                "status": "Unhealthy",
                "output": "command execution error",
                "side_effect": Exception("command not found")
            }
        ]
        
        for test_case in service_test_cases:
            with self.subTest(services=test_case["services"]):
                # 配置模拟响应
                if "side_effect" in test_case:
                    call_mock.side_effect = test_case["side_effect"]
                else:
                    call_mock.return_value = (test_case["code"], test_case["output"], "")
                
                # 检测服务状?                results = []
                self.host_info.checkLiveServices([test_case["services"]], results)
                
                # 验证检测结?                self.assertEqual(len(results), 1)
                found_service = False
                for item in results:
                    if all(service in item["name"] for service in test_case["services"]):
                        self.assertEqual(item["status"], test_case["status"])
                        if test_case["status"] == "Unhealthy":
                            self.assertIn(test_case["output"], item["desc"])
                        found_service = True
                self.assertTrue(found_service)
                
                call_mock.reset_mock()


class FirewallStatusTests(HostInfoTestBase):
    """测试防火墙状态检测功?""
    
    @patch.object(Firewall, "getFirewallObject")
    @patch.object(OSCheck, "get_os_type", return_value="redhat")
    @patch.object(OSCheck, "get_os_family", return_value=OSConst.REDHAT_FAMILY)
    def test_firewall_state_detection(self, family_mock, type_mock, firewall_mock):
        """测试防火墙运行状态检测逻辑"""
        firewall_impl = MagicMock()
        
        # 活跃状态测?        firewall_impl.check_firewall.return_value = True
        firewall_mock.return_value = firewall_impl
        self.assertTrue(self.host_info.checkFirewall())
        
        # 非活跃状态测?        firewall_impl.check_firewall.return_value = False
        self.assertFalse(self.host_info.checkFirewall())


class NetworkConfigurationTests(HostInfoTestBase):
    """测试网络配置检测功?""
    
    @patch.object(socket, "gethostname")
    @patch.object(socket, "gethostbyname")
    @patch.object(socket, "getfqdn")
    def test_network_resolution_checks(self, getfqdn_mock, host_by_name_mock, hostname_mock):
        """测试主机名解析检测逻辑"""
        hostname_mock.return_value = "test-host"
        getfqdn_mock.return_value = "test-host.example.com"
        
        # 成功解析测试
        host_by_name_mock.side_effect = ["192.168.1.1", "192.168.1.1"]
        self.assertTrue(self.host_info.checkReverseLookup())
        
        # 解析失败测试
        host_by_name_mock.side_effect = [
            "192.168.1.1", 
            socket.gaierror("Resolution failed")
        ]
        self.assertFalse(self.host_info.checkReverseLookup())
        
        # 不匹配地址测试
        host_by_name_mock.side_effect = ["192.168.1.1", "10.0.0.1"]
        self.assertFalse(self.host_info.checkReverseLookup())


class JavaProcessTests(HostInfoTestBase):
    """测试Java进程检测功?""
    
    @patch.object(pwd, "getpwuid")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.listdir")
    def test_java_process_identification(self, listdir_mock, open_mock, pwuid_mock):
        """测试Java进程信息采集逻辑"""
        test_pid = "1234"
        
        # 设置测试环境
        os.makedirs(os.path.join(self.temp_dir, "proc"), exist_ok=True)
        
        # 配置模拟响应
        listdir_mock.return_value = [test_pid]
        open_mock.side_effect = [
            mock_open(read_data=f"/usr/lib/jvm/java-11-openjdk/bin/java").return_value,
            mock_open(read_data="Uid:1001\n").return_value
        ]
        pwuid_mock.return_value = pwd.struct_passwd(("java-user", "*", 1001, 1001, 
                                                   "Java User", "/home/java-user", 
                                                   "/bin/bash"))
        
        # 执行进程检?        results = []
        self.host_info.javaProcs(results)
        
        # 验证输出结果
        self.assertEqual(len(results), 1)
        proc_info = results[0]
        self.assertEqual(proc_info["pid"], int(test_pid))
        self.assertEqual(proc_info["user"], "java-user")
        self.assertEqual(proc_info["command"], "/usr/lib/jvm/java-11-openjdk/bin/java")
        self.assertTrue(proc_info["hadoop"])


class PerformanceSettingsTests(HostInfoTestBase):
    """测试性能设置检测功?""
    
    @patch("os.path.isfile")
    @patch("builtins.open", new_callable=mock_open)
    @patch.object(OSCheck, "get_os_family", return_value=OSConst.REDHAT_FAMILY)
    def test_advanced_performance_settings(self, family_mock, open_mock, isfile_mock):
        """测试透明大页(THP)配置检测逻辑"""
        test_values = [
            {"file_content": "[always] madvise never", "expected": "always", "os_family": OSConst.REDHAT_FAMILY},
            {"file_content": "always madvise [never]", "expected": "never", "os_family": OSConst.UBUNTU_FAMILY},
            {"file_content": "invalid content", "expected": "unknown", "os_family": OSConst.SUSE_FAMILY}
        ]
        
        for config in test_values:
            with self.subTest(expected=config["expected"], family=config["os_family"]):
                # 设置模拟环境
                family_mock.return_value = config["os_family"]
                isfile_mock.return_value = True
                open_mock.return_value.read.return_value = config["file_content"]
                
                # 执行检?                result = self.host_info.getTransparentHugePage()
                self.assertEqual(result, config["expected"])
                
                # 重置模拟对象
                open_mock.reset_mock()
        
        # 测试文件不存在的情况
        isfile_mock.return_value = False
        result = self.host_info.getTransparentHugePage()
        self.assertEqual(result, "file_not_found")


class HostInfoIntegrationTests(HostInfoTestBase):
    """测试主机信息收集集成功能"""
    
    @patch.object(OSCheck, "get_os_type", return_value="redhat")
    @patch.object(HostInfoLinux, "getTransparentHugePage")
    @patch.object(HostInfoLinux, "checkFirewall")
    @patch.object(HostInfoLinux, "etcAlternativesConf")
    @patch.object(HostInfoLinux, "hadoopVarRunCount")
    @patch.object(HostInfoLinux, "hadoopVarLogCount")
    @patch.object(HostInfoLinux, "checkFolders")
    @patch.object(HostInfoLinux, "javaProcs")
    @patch.object(HostInfoLinux, "checkLiveServices")
    @patch.object(HostInfoLinux, "checkUsers")
    @patch("os.umask")
    @patch("resource_management.core.providers.get_provider")
    def test_full_host_health_report(
        self, provider_mock, umask_mock, users_mock, services_mock, java_mock,
        folders_mock, hadoop_log_mock, hadoop_run_mock, alternatives_mock,
        firewall_mock, thp_mock, os_type_mock
    ):
        """测试完整主机健康报告的生成逻辑"""
        # 配置模拟依赖
        provider_mock.return_value.get_package_details.return_value = [
            "java-11-openjdk", "hadoop-3.3.1"
        ]
        users_mock.return_value = []
        services_mock.return_value = []
        java_mock.return_value = []
        folders_mock.return_value = []
        hadoop_log_mock.return_value = 3
        hadoop_run_mock.return_value = 2
        alternatives_mock.return_value = []
        firewall_mock.return_value = True
        thp_mock.return_value = "never"
        
        # 执行主机信息收集
        result_data = {}
        self.host_info.register(result_data, detailed=True, live_report=True)
        
        # 验证输出数据结构
        self.assertIn("hostHealth", result_data)
        self.assertIn("platform", result_data)
        
        # 验证特定?        host_health = result_data["hostHealth"]
        self.assertIn("hostname", host_health)
        self.assertEqual(host_health["firewallRunning"], True)
        self.assertEqual(host_health["transparentHugePage"], "never")
        self.assertGreater(len(result_data["packages"]), 0)
        
        # 验证日志记录
        self.logger.info.assert_any_call("Completed host information collection")


if __name__ == "__main__":
    unittest.main()
