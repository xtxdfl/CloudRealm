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
from unittest.mock import patch, MagicMock
import socket
import tempfile
import os
import stat
import cloud_agent.hostname as hostname
from cloud_agent.cloudConfig import cloudConfig
from cloud_commons import OSCheck
from only_for_platform import not_for_platform, os_distro_value, PLATFORM_WINDOWS


class BaseHostnameTestCase(unittest.TestCase):
    """主机名测试基�?""
    
    def setUp(self):
        # 重置缓存状�?        hostname.cached_hostname = None
        hostname.cached_public_hostname = None
        hostname.cached_server_hostnames = []
        
        # 创建配置对象
        self.config = cloudConfig()
        
        # 模拟默认的OS信息
        self.os_patch = patch.object(OSCheck, "os_distribution", return_value=os_distro_value)
        self.os_patch.start()
    
    def tearDown(self):
        # 停止所有补�?        self.os_patch.stop()
        
        # 清理所有临时文�?        if hasattr(self, 'temp_files'):
            for file in self.temp_files:
                try:
                    os.remove(file)
                except:
                    pass


class HostnameResolutionTests(BaseHostnameTestCase):
    """测试基本的主机名解析功能"""
    
    def test_default_hostname_resolution(self):
        """测试默认主机名解�?""
        resolved_hostname = hostname.hostname(self.config)
        expected_hostname = socket.getfqdn().lower()
        self.assertEqual(resolved_hostname, expected_hostname, "解析的主机名应与系统主机名匹�?)
    
    @patch.object(socket, 'getfqdn')
    def test_caching_mechanism(self, getfqdn_mock):
        """测试主机名缓存机�?""
        # 设置不同的返回值模拟多次调�?        getfqdn_mock.side_effect = ["test1.example.com", "test2.example.com"]
        
        # 第一次调用应使用初始�?        first_call = hostname.hostname(self.config)
        self.assertEqual(first_call, "test1.example.com")
        
        # 第二次调用应返回缓存�?        second_call = hostname.hostname(self.config)
        self.assertEqual(second_call, "test1.example.com")
        
        # 验证只调用了一�?        self.assertEqual(getfqdn_mock.call_count, 1)


class ServerHostnameTests(BaseHostnameTestCase):
    """测试服务器主机名配置功能"""
    
    def test_single_server_hostname(self):
        """测试单个服务器主机名配置"""
        self.config.set("server", "hostname", "cloud-host-01")
        server_hostnames = hostname.server_hostnames(self.config)
        self.assertEqual(server_hostnames, ["cloud-host-01"], "应正确解析单个主机名")
    
    def test_multiple_server_hostnames(self):
        """测试多个服务器主机名配置"""
        self.config.set("server", "hostname", "host1,host2,  host3")
        server_hostnames = hostname.server_hostnames(self.config)
        self.assertEqual(server_hostnames, ["host1", "host2", "host3"], "应正确解析并清理多个主机�?)
    
    def test_hostname_normalization(self):
        """测试主机名规范化处理"""
        test_cases = [
            (" Simple-Host ", ["simple-host"]),
            ("Host.With.Dots", ["host.with.dots"]),
            ("Host_with_underscore", ["host_with_underscore"]),
            ("123-Host_456", ["123-host_456"]),
            ("", []),
            (", , ,", []),
        ]
        
        for input_value, expected in test_cases:
            with self.subTest(input=input_value, expected=expected):
                self.config.set("server", "hostname", input_value)
                result = hostname.server_hostnames(self.config)
                self.assertEqual(result, expected, f"输入 '{input_value}' 应规范化�?{expected}")


class ScriptOverrideTests(BaseHostnameTestCase):
    """测试通过脚本覆盖主机名功�?""
    
    def create_temp_script(self, content):
        """创建临时脚本文件"""
        script_fd, script_path = tempfile.mkstemp(text=True)
        os.close(script_fd)
        
        with open(script_path, 'w') as f:
            f.write(content)
        
        # 设置为可执行文件
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR)
        
        # 记录清理
        if not hasattr(self, 'temp_files'):
            self.temp_files = []
        self.temp_files.append(script_path)
        
        return script_path
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_hostname_script_override(self):
        """测试主机名脚本覆�?""
        script_content = "#!/bin/sh\necho 'custom-host.example.com'"
        script_path = self.create_temp_script(script_content)
        
        self.config.set("agent", "hostname_script", script_path)
        resolved_hostname = hostname.hostname(self.config)
        self.assertEqual(resolved_hostname, "custom-host.example.com", "脚本应覆盖默认主机名")
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_public_hostname_script_override(self):
        """测试公共主机名脚本覆�?""
        script_content = "#!/bin/sh\necho 'public-custom-host.example.com'"
        script_path = self.create_temp_script(script_content)
        
        self.config.set("agent", "public_hostname_script", script_path)
        resolved_hostname = hostname.public_hostname(self.config)
        self.assertEqual(resolved_hostname, "public-custom-host.example.com", "脚本应覆盖公共主机名")
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_server_hostname_script_override(self):
        """测试服务器主机名脚本覆盖"""
        script_content = "#!/bin/sh\necho 'server1,server2, server3'"
        script_path = self.create_temp_script(script_content)
        
        self.config.set("server", "hostname_script", script_path)
        server_hostnames = hostname.server_hostnames(self.config)
        self.assertEqual(server_hostnames, ["server1", "server2", "server3"], "脚本应覆盖服务器主机�?)
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_script_special_characters(self):
        """测试脚本输出的特殊字符处�?""
        test_cases = [
            ("echo 'host!@#$%^&*()name'", "host!@#$%^&*()name"),
            ("echo 'host with spaces'", "host with spaces"),
            ("echo 'host\twith\ttabs'", "host\twith\ttabs"),
        ]
        
        for command, expected in test_cases:
            with self.subTest(command=command, expected=expected):
                script_path = self.create_temp_script(f"#!/bin/sh\n{command}")
                self.config.set("agent", "hostname_script", script_path)
                resolved_hostname = hostname.hostname(self.config)
                self.assertEqual(resolved_hostname, expected, "脚本应正确处理特殊字�?)
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_multiline_script_output(self):
        """测试多行脚本输出处理"""
        script_content = "#!/bin/sh\necho 'first_line'\necho 'second_line'"
        script_path = self.create_temp_script(script_content)
        
        self.config.set("agent", "hostname_script", script_path)
        resolved_hostname = hostname.hostname(self.config)
        self.assertEqual(resolved_hostname, "first_line", "应使用第一行输出作为主机名")


class ErrorHandlingTests(BaseHostnameTestCase):
    """测试主机名解析的错误处理"""
    
    @patch.object(socket, 'getfqdn')
    def test_socket_error_handling(self, getfqdn_mock):
        """测试socket错误处理"""
        getfqdn_mock.side_effect = socket.gaierror("Test socket error")
        
        with self.assertLogs(level='ERROR') as log_context:
            resolved_hostname = hostname.hostname(self.config)
        
        # 验证使用socket.gethostname()作为回退
        self.assertEqual(resolved_hostname, socket.gethostname().lower())
        self.assertIn("Failed to get FQDN", log_context.output[0])
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_script_error_handling(self):
        """测试脚本执行错误处理"""
        # 创建一个错误的脚本
        script_path = self.create_temp_script("#!/bin/sh\nexit 1")
        self.config.set("agent", "hostname_script", script_path)
        
        with self.assertLogs(level='ERROR') as log_context:
            resolved_hostname = hostname.hostname(self.config)
        
        # 验证使用系统主机名作为回退
        expected_fallback = socket.getfqdn().lower()
        self.assertEqual(resolved_hostname, expected_fallback)
        self.assertIn("Failed to execute hostname script", log_context.output[0])
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_non_executable_script(self):
        """测试非可执行脚本"""
        # 创建不可执行的脚�?        script_fd, script_path = tempfile.mkstemp(text=True)
        os.close(script_fd)
        with open(script_path, 'w') as f:
            f.write("echo 'should not run'")
        
        # 移除执行权限
        os.chmod(script_path, stat.S_IRUSR | stat.S_IWUSR)
        
        self.config.set("agent", "hostname_script", script_path)
        
        with self.assertLogs(level='ERROR') as log_context:
            resolved_hostname = hostname.hostname(self.config)
        
        # 验证使用系统主机名作为回退
        expected_fallback = socket.getfqdn().lower()
        self.assertEqual(resolved_hostname, expected_fallback)
        self.assertIn("not executable or access denied", log_context.output[0])
        
        # 清理
        os.remove(script_path)


class SecurityTests(BaseHostnameTestCase):
    """测试主机名解析的安全特�?""
    
    @not_for_platform(PLATFORM_WINDOWS)
    def test_script_output_sanitization(self):
        """测试脚本输出的清�?""
        malicious_content = "echo 'malicious; $(rm -rf /)'"
        script_path = self.create_temp_script(f"#!/bin/sh\n{malicious_content}")
        
        self.config.set("agent", "hostname_script", script_path)
        resolved_hostname = hostname.hostname(self.config)
        
        # 验证恶意命令没有执行
        self.assertEqual(resolved_hostname, "malicious; $(rm -rf /)", "脚本命令应作为普通文本处�?)


class EdgeCaseTests(BaseHostnameTestCase):
    """测试主机名解析的边缘情况"""
    
    def test_empty_hostname(self):
        """测试空主机名配置"""
        self.config.set("server", "hostname", "")
        server_hostnames = hostname.server_hostnames(self.config)
        self.assertEqual(server_hostnames, [], "空主机名配置应返回空列表")
    
    def test_whitespace_hostname(self):
        """测试空白主机名配�?""
        self.config.set("server", "hostname", "   ")
        server_hostnames = hostname.server_hostnames(self.config)
        self.assertEqual(server_hostnames, [], "空白主机名配置应返回空列�?)
    
    def test_null_character(self):
        """测试主机名中的null字符"""
        self.config.set("server", "hostname", "host\x00name")
        with self.assertLogs(level='WARNING') as log_context:
            server_hostnames = hostname.server_hostnames(self.config)
        
        self.assertEqual(server_hostnames, ['hostname'], "null字符应被移除")
        self.assertIn("null character", log_context.output[0])
    
    def test_invalid_characters(self):
        """测试其他无效字符"""
        test_cases = [
            ("host:name", ["hostname"]),
            ("host/name", ["hostname"]),
            ("host\name", ["hostname"]),
        ]
        
        for input_value, expected in test_cases:
            with self.subTest(input=input_value):
                self.config.set("server", "hostname", input_value)
                with self.assertLogs(level='WARNING') as log_context:
                    server_hostnames = hostname.server_hostnames(self.config)
                
                self.assertEqual(server_hostnames, expected)
                self.assertIn("unexpected characters", log_context.output[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
