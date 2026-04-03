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

from unittest import TestCase  # 单元测试基类
import tempfile  # 临时文件处理
from mock.mock import patch, MagicMock  # 测试模拟工具
from only_for_platform import not_for_platform, PLATFORM_WINDOWS  # 平台特定处理
from cloud_commons.os_check import OSCheck  # 操作系统检?from cloudConfig import cloudConfig  # 配置管理
from Hardware import Hardware  # 硬件信息
from Facter import FacterLinux  # Linux系统信息获取
from Register import Register  # 注册功能(优化后在此处导入)


@not_for_platform(PLATFORM_WINDOWS)  # 仅限非Windows平台执行
class TestRegistration(TestCase):
    """单元测试类：验证Agent注册数据的构建完整?""
    
    def setUp(self):
        """创建注册测试环境: 初始化配置和模拟对象"""
        # 创建临时配置
        self.config = cloudConfig()
        self.tmpdir = tempfile.gettempdir()
        self.config.set("agent", "prefix", self.tmpdir)
        self.config.set("agent", "current_ping_port", "33777")
        
        # 创建模拟对象字典
        self.mocks = self._create_mock_objects()
    
    def tearDown(self):
        """清理测试环境"""
        self.mocks.clear()
    
    def _create_mock_objects(self):
        """创建并返回一组模拟对象集?""
        return {
            "popen": MagicMock(),  # 子进程模?            "facter_info": MagicMock(return_value={
                "system_uptime": "10 days",
                "memorysize": "15.64 GiB",
                "processorcount": "8",
                "is_virtual": "false"
            }),  # 系统信息模拟
            "chk_writable": MagicMock(return_value=True),  # 文件系统可写检?            "run_os_cmd": MagicMock(return_value=(0, "", "")),  # 系统命令执行
            "os_family": MagicMock(return_value="suse"),  # 操作系统家族
            "os_type": MagicMock(return_value="suse"),  # 操作系统类型
            "os_version": MagicMock(return_value="15.3"),  # 操作系统版本
        }
    
    def _setup_registration_mocks(self):
        """配置注册构建所需的测试模?""
        # 设置硬件检测模块的依赖模拟
        with patch("subprocess.Popen", return_value=self.mocks["popen"]), \
             patch.object(Hardware, "_chk_writable_mount", self.mocks["chk_writable"]), \
             patch("builtins.open", MagicMock()), \
             patch("resource_management.core.shell.call", self.mocks["run_os_cmd"]):
            
            # 设置Facter模块的模?            with patch.object(FacterLinux, "facterInfo", self.mocks["facter_info"]), \
                 patch.object(FacterLinux, "__init__", return_value=None):
                
                # 设置操作系统检测模?                with patch.object(OSCheck, "get_os_family", self.mocks["os_family"]), \
                     patch.object(OSCheck, "get_os_type", self.mocks["os_type"]), \
                     patch.object(OSCheck, "get_os_version", self.mocks["os_version"]):
                    
                    # 创建并返回注册对?                    return Register(self.config)
    
    def test_registration_data_structure(self):
        """测试注册数据结构完整?- 验证顶层字段存在?""
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证所有必要字段存?        required_fields = {
            "hardwareProfile", "hostname", "publicHostname", 
            "id", "timestamp", "agentEnv", "prefix", "mounts", "capabilities"
        }
        self.assertSetEqual(set(data.keys()), required_fields, 
                          "注册数据结构缺少必要字段")
    
    def test_hardware_profile_content(self):
        """测试硬件信息采集 - 验证硬件配置文件完整?""
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证硬件信息
        self.assertIsInstance(data["hardwareProfile"], dict, 
                            "硬件配置信息应为字典类型")
        self.assertGreater(len(data["hardwareProfile"]), 0,
                         "硬件配置信息不应为空")
        self.assertIn("processors", data["hardwareProfile"],
                    "硬件配置缺少处理器信?)
        self.assertIn("disks", data["hardwareProfile"],
                    "硬件配置缺少磁盘信息")
    
    def test_hostname_resolution(self):
        """测试主机名解?- 验证主机名格式正确?""
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证主机名格?        self.assertIsInstance(data["hostname"], str, 
                           "主机名应为字符串类型")
        self.assertGreater(len(data["hostname"]), 0,
                        "主机名不应为?)
        self.assertNotIn(" ", data["hostname"],
                      "主机名不应包含空?)
        
        # 验证公共主机名格?        self.assertIsInstance(data["publicHostname"], str,
                           "公共主机名应为字符串类型")
        self.assertGreater(len(data["publicHostname"]), 0,
                        "公共主机名不应为?)
    
    def test_timestamp_generation(self):
        """测试时间戳生?- 验证时间戳取值范围有效?""
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证时间戳范?(1353678475465 = 2012-11-23 12:47:55 UTC)
        self.assertIsInstance(data["timestamp"], int,
                           "时间戳应为整型数?)
        self.assertGreater(data["timestamp"], 1353678475465,
                         "时间戳不应早?012?)
        
        # 验证时间精度
        current_time = 1680000000000  # 2023?月时间戳
        self.assertGreater(data["timestamp"], current_time - (10 * 365 * 24 * 3600 * 1000), 
                         "时间戳偏差过?)
    
    def test_agent_environment_data(self):
        """测试Agent环境信息 - 验证环境变量和工作状?""
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证环境信息
        self.assertIsInstance(data["agentEnv"], dict,
                           "Agent环境信息应为字典类型")
        self.assertGreater(len(data["agentEnv"]), 0,
                        "Agent环境信息不应为空")
        
        # 验证umask?        self.assertIn("umask", data["agentEnv"],
                   "Agent环境缺少umask?)
        self.assertNotEqual(data["agentEnv"]["umask"], "",
                         "umask值不应为?)
        self.assertRegex(data["agentEnv"]["umask"], r"^0[0-7]{3}$",
                      "umask格式应为四位八进制数")
    
    def test_configuration_integration(self):
        """测试配置集成 - 验证Agent配置正确注入"""
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证配置路径正确?        self.assertEqual(data["prefix"], self.tmpdir,
                      "临时路径配置不正?)
        
        # 验证端口配置
        self.assertEqual(data["agentEnv"]["current_ping_port"], "33777",
                      "心跳端口配置不正?)
    
    def test_virtual_machine_detection(self):
        """测试虚拟机检?- 验证虚拟化环境识别能?""
        # 模拟虚拟机环?        self.mocks["facter_info"].return_value["is_virtual"] = "true"
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证虚拟机标?        self.assertIn("is_virtual", data["hardwareProfile"],
                   "硬件配置缺少虚拟化标?)
        self.assertTrue(data["hardwareProfile"]["is_virtual"],
                     "虚拟化环境识别错?)
    
    def test_filesystem_writability_check(self):
        """测试文件系统可写性检?- 验证存储准备状?""
        # 模拟文件系统不可写场?        self.mocks["chk_writable"].return_value = False
        register = self._setup_registration_mocks()
        data = register.build()
        
        # 验证文件系统状?        self.assertIn("filesystem_status", data["agentEnv"],
                   "Agent环境缺少文件系统状?)
        self.assertEqual(data["agentEnv"]["filesystem_status"], "readonly",
                      "文件系统状态应标记为只?)
