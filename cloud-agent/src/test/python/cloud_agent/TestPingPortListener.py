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
from unittest.mock import patch, MagicMock, call, Mock
import subprocess
import socket
import sys
sys.modules['cloud_agent'] = MagicMock()
from cloud_agent import PingPortListener


class PingPortListenerTestBase(unittest.TestCase):
    """PingPortListener 测试基类"""
    
    def setUp(self):
        # 创建配置模拟
        self.config_mock = MagicMock()
        self.config_mock.get.return_value = 55000
        
        # 初始化类变量
        PingPortListener.logger = MagicMock()
        
        # 创建模拟的进程对�?        self.proc_mock = MagicMock()
        self.proc_mock.communicate.return_value = ("", 0)
        
        # 创建模拟的套接字对象
        self.socket_mock = MagicMock()
        self.socket_mock.accept.return_value = (MagicMock(), ("127.0.0.1", 12345))


class ListenerInitializationTests(PingPortListenerTestBase):
    """测试监听器初始化功能"""
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_successful_initialization(self, popen_mock, socket_mock):
        """测试成功初始化监听器"""
        # 配置模拟返回�?        popen_mock.return_value = self.proc_mock
        socket_instance = MagicMock()
        socket_mock.return_value = socket_instance
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 验证套接字配�?        socket_mock.assert_called_with(socket.AF_INET, socket.SOCK_STREAM)
        socket_instance.bind.assert_called_with(("0.0.0.0", 55000))
        socket_instance.listen.assert_called_with(1)
        
        # 验证配置设置
        self.config_mock.set.assert_called_with(
            "agent", "current_ping_port", listener.port
        )
        
        # 验证日志记录
        PingPortListener.logger.info.assert_called()
        PingPortListener.logger.warn.assert_not_called()
        PingPortListener.logger.error.assert_not_called()
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_port_in_use_handling(self, popen_mock, socket_mock):
        """测试端口已被占用时的处理"""
        # 配置模拟�?        socket_mock.return_value.bind.side_effect = OSError("Address already in use")
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 验证日志记录
        PingPortListener.logger.warn.assert_called()
        PingPortListener.logger.info.assert_called_with("Start PingPortListener on port %s", listener.port)
        
        # 验证配置设置
        self.config_mock.set.assert_called_with(
            "agent", "current_ping_port", listener.port
        )
    
    @patch("socket.socket")
    def test_no_root_privileges(self, socket_mock):
        """测试无root权限时的处理"""
        # 配置模拟�?        socket_mock.return_value.bind.side_effect = PermissionError("Permission denied")
        
        with self.assertRaises(SystemExit):
            PingPortListener.PingPortListener(self.config_mock)
        
        # 验证日志记录
        PingPortListener.logger.error.assert_called()


class PortAllocationTests(PingPortListenerTestBase):
    """测试端口分配功能"""
    
    @patch("socket.socket")
    def test_default_port_assignment(self, socket_mock):
        """测试默认端口分配"""
        # 设置配置�?        self.config_mock.get.return_value = 55000
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 验证端口分配
        self.assertEqual(listener.port, 55000)
        
        # 验证绑定调用
        socket_mock.return_value.bind.assert_called_with(
            ("0.0.0.0", 55000)
        )
    
    @patch("socket.socket")
    def test_automatic_port_allocation(self, socket_mock):
        """测试自动端口分配"""
        # 配置第一次绑定失�?        socket_instance = socket_mock.return_value
        socket_instance.bind.side_effect = [
            OSError("Port in use"),  # 第一次尝试失�?            MagicMock()  # 第二次尝试成�?        ]
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 验证端口分配范围
        self.assertTrue(55000 < listener.port <= 56000)
        
        # 验证日志记录
        PingPortListener.logger.warn.assert_called()
    
    @patch("socket.socket")
    def test_port_exhaustion_handling(self, socket_mock):
        """测试端口耗尽时的处理"""
        # 配置所有端口都失败
        socket_instance = socket_mock.return_value
        socket_instance.bind.side_effect = OSError("Port in use")
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 验证分配端口在范围内的最后一�?        self.assertEqual(listener.port, 56000)
        
        # 验证日志记录
        PingPortListener.logger.warn.assert_called()
        PingPortListener.logger.error.assert_not_called()


class ConnectionHandlingTests(PingPortListenerTestBase):
    """测试连接处理功能"""
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_invalid_ping_connection(self, popen_mock, socket_mock):
        """测试拒绝来自非信任源的ping连接"""
        # 配置模拟�?        socket_instance = socket_mock.return_value
        client_sock = MagicMock()
        socket_instance.accept.return_value = (client_sock, ("192.168.1.100", 54321))
        
        # 设置信任IP列表
        self.config_mock.get.return_value = "127.0.0.1,192.168.0.0/24"
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 启动ping处理线程
        listener.start()
        
        # 模拟连接处理
        listener.handle_ping_request()
        
        # 验证日志记录
        PingPortListener.logger.info.assert_called_with(
            "Reject ping request from untrusted source %s", "192.168.1.100"
        )
        
        # 验证套接字关�?        client_sock.shutdown.assert_called_with(socket.SHUT_RDWR)
        client_sock.close.assert_called()
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_valid_ping_connection(self, popen_mock, socket_mock):
        """测试接受来自信任源的ping连接"""
        # 配置模拟�?        socket_instance = socket_mock.return_value
        client_sock = MagicMock()
        client_sock.recv.return_value = b"PING"
        client_sock.getpeername.return_value = ("127.0.0.1", 12345)
        
        # 设置信任IP列表
        self.config_mock.get.return_value = "127.0.0.1"
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        listener._PingPortListener__trusted_networks = ["127.0.0.1"]
        
        # 启动ping处理线程
        listener.start()
        
        # 模拟连接处理
        listener.handle_ping_request()
        
        # 验证日志记录
        PingPortListener.logger.info.assert_called_with(
            "Accept ping request from %s", "127.0.0.1"
        )
        
        # 验证响应发�?        client_sock.send.assert_called_with(b"OK")
        
        # 验证套接字关�?        client_sock.shutdown.assert_called_with(socket.SHUT_RDWR)
        client_sock.close.assert_called()
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_ping_response_processing(self, popen_mock, socket_mock):
        """测试ping请求的响应处�?""
        # 配置模拟�?        socket_instance = socket_mock.return_value
        client_sock = MagicMock()
        client_sock.recv.return_value = b"PING"
        client_sock.getpeername.return_value = ("127.0.0.1", 12345)
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        listener._PingPortListener__trusted_networks = ["127.0.0.1"]
        
        # 模拟处理请求
        listener.handle_ping_request()
        
        # 验证数据接收
        client_sock.recv.assert_called_with(1024)
        
        # 验证响应发�?        client_sock.send.assert_called_with(b"OK")
        
        # 验证日志记录
        PingPortListener.logger.info.assert_any_call(
            "Accept ping request from %s", "127.0.0.1"
        )
        PingPortListener.logger.info.assert_any_call(
            "Close ping connection from %s", "127.0.0.1"
        )


class NetworkResolutionTests(PingPortListenerTestBase):
    """测试网络解析功能"""
    
    @patch("subprocess.Popen")
    def test_trusted_networks_resolution(self, popen_mock):
        """测试可信网络解析"""
        # 设置不同格式的网络配�?        network_config = "10.0.0.1,192.168.0.0/24,localhost,example.com"
        
        # 设置配置返回�?        self.config_mock.get.return_value = network_config
        
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 验证可信网络解析
        self.assertEqual(len(listener._PingPortListener__trusted_networks), 3)
        self.assertIn("10.0.0.1", listener._PingPortListener__trusted_networks)
        self.assertIn("192.168.0.0/24", listener._PingPortListener__trusted_networks)
        self.assertNotIn("localhost", listener._PingPortListener__trusted_networks)
        self.assertNotIn("example.com", listener._PingPortListener__trusted_networks)
    
    @patch("subprocess.Popen")
    def test_trusted_networks_formats(self, popen_mock):
        """测试不同可信网络格式解析"""
        test_cases = [
            # 测试单个IP
            ("192.168.1.1", ["192.168.1.1"]),
            # 测试CIDR表示�?            ("10.0.0.0/8", ["10.0.0.0/8"]),
            # 测试多个IP
            ("10.0.0.1,192.168.1.2", ["10.0.0.1", "192.168.1.2"]),
            # 测试IP范围
            ("10.0.0.1-10.0.0.10", ["10.0.0.1-10.0.0.10"]),
            # 测试无效格式
            ("invalid_ip", []),
            # 测试域名（应被忽略）
            ("example.com", []),
        ]
        
        for config, expected in test_cases:
            with self.subTest(config=config, expected=expected):
                # 设置配置返回�?                self.config_mock.get.return_value = config
                
                # 创建监听器实�?                listener = PingPortListener.PingPortListener(self.config_mock)
                
                # 验证可信网络
                self.assertEqual(
                    listener._PingPortListener__trusted_networks, expected
                )


class TerminationTests(PingPortListenerTestBase):
    """测试监听器终止功�?""
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_normal_termination(self, popen_mock, socket_mock):
        """测试正常终止过程"""
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 启动监听�?        listener.start()
        
        # 终止监听�?        listener.stop()
        listener.join()
        
        # 验证套接字关�?        socket_mock.return_value.close.assert_called()
        
        # 验证日志记录
        PingPortListener.logger.info.assert_called_with(
            "Shutting down PingPortListener"
        )
    
    @patch("socket.socket")
    @patch("subprocess.Popen")
    def test_forceful_termination(self, popen_mock, socket_mock):
        """测试强制终止过程"""
        # 创建监听器实�?        listener = PingPortListener.PingPortListener(self.config_mock)
        
        # 模拟阻塞接受
        socket_instance = socket_mock.return_value
        socket_instance.accept.side_effect = socket.timeout
        
        # 启动监听�?        listener.start()
        
        # 终止监听�?        listener.stop()
        listener.join()
        
        # 验证套接字关�?        socket_instance.close.assert_called()
        
        # 验证日志记录
        PingPortListener.logger.info.assert_called_with(
            "Shutting down PingPortListener"
        )
        PingPortListener.logger.error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
