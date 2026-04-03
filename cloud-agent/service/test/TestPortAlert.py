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
from unittest.mock import MagicMock, patch, call
from alerts.port_alert import PortAlert
from cloudConfig import cloudConfig


class PortAlertTestBase(unittest.TestCase):
    """端口警报测试基类"""
    
    def setUp(self):
        # 创建基础配置
        self.config = cloudConfig()
        
        # 定义通用警报元数?        self.base_alert_meta = {
            "definitionId": 1001,
            "name": "PortAlerts",
            "label": "Port Alert Test",
            "serviceName": "NetworkService",
            "componentName": "PortMonitor",
            "uuid": "port-alert-123",
            "enabled": "true"
        }
        
        # 定义通用警报源数?        self.base_alert_source_meta = {
            "uri": "http://example.com:8080",
            "default_port": 8080
        }
        
        # 创建集群配置
        self.cluster_name = "TestCluster"
        self.cluster_id = "cluster-001"
        self.host_name = "test-host.example.com"
    
    def create_port_alert(self, alert_meta=None, source_meta=None):
        """创建 PortAlert 实例"""
        alert_meta = alert_meta or self.base_alert_meta.copy()
        source_meta = source_meta or self.base_alert_source_meta.copy()
        
        alert = PortAlert(alert_meta, source_meta, self.config)
        alert.set_cluster(self.cluster_name, self.cluster_id, self.host_name)
        
        # 模拟配置构建?        alert.configuration_builder = MagicMock()
        
        return alert
    
    def create_collector_mock(self, alert, expected_state, expected_text):
        """创建收集器模拟对象并验证预期结果"""
        collector_mock = MagicMock()
        
        def collector_side_effect(cluster, alert_data):
            self.assertEqual(cluster, self.cluster_name)
            self.assertEqual(alert_data["name"], alert.alert_meta["name"])
            self.assertEqual(alert_data["state"], expected_state)
            self.assertIn(expected_text, alert_data["text"])
            self.assertEqual(alert_data["clusterId"], self.cluster_id)
        
        collector_mock.put.side_effect = collector_side_effect
        alert.collector = collector_mock
        
        return alert


class PortCheckSuccessTests(PortAlertTestBase):
    """测试端口检查成功场?""
    
    @patch("socket.socket")
    @patch("time.time")
    def test_default_port_connection(self, mock_time, mock_socket):
        """测试默认端口连接成功"""
        # 准备模拟数据
        mock_time.side_effect = [1000, 1000.201, 2000]
        mock_socket.return_value.connect.return_value = None
        
        # 创建警报实例
        alert = self.create_port_alert()
        alert = self.create_collector_mock(
            alert, 
            "OK", 
            "TCP OK - 0.2010 response on port 8080"
        )
        
        # 执行收集
        alert.collect()
        
        # 验证模拟调用
        mock_socket.return_value.connect.assert_called_with(('example.com', 8080))
        alert.collector.put.assert_called()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_custom_port_connection(self, mock_time, mock_socket):
        """测试自定义端口连接成?""
        # 准备模拟数据
        mock_time.side_effect = [1000, 1000.502, 2000]
        mock_socket.return_value.connect.return_value = None
        
        # 创建带自定义端口的警?        source_meta = self.base_alert_source_meta.copy()
        source_meta["uri"] = "http://custom.example.com:9000"
        alert = self.create_port_alert(source_meta=source_meta)
        alert = self.create_collector_mock(
            alert, 
            "OK", 
            "TCP OK - 0.5020 response on port 9000"
        )
        
        # 执行收集
        alert.collect()
        
        # 验证连接参数
        mock_socket.return_value.connect.assert_called_with(('custom.example.com', 9000))
    
    @patch("socket.socket")
    @patch("time.time")
    def test_hostname_as_uri(self, mock_time, mock_socket):
        """测试使用主机名作为URI"""
        # 准备模拟数据
        mock_time.side_effect = [1000, 1001.5, 2000]
        mock_socket.return_value.connect.return_value = None
        
        # 创建使用主机名的警报
        source_meta = {"default_port": 3306}  # 没有URI
        alert = self.create_port_alert(source_meta=source_meta)
        alert = self.create_collector_mock(
            alert, 
            "OK", 
            f"TCP OK - 1.5000 response on port 3306"
        )
        
        # 执行收集
        alert.collect()
        
        # 验证使用主机名连?        mock_socket.return_value.connect.assert_called_with(
            (self.host_name, 3306)
        )


class ResponseTimeThresholdTests(PortAlertTestBase):
    """测试响应时间阈值场?""
    
    @patch("socket.socket")
    @patch("time.time")
    def test_warning_threshold_exceeded(self, mock_time, mock_socket):
        """测试超过警告阈?""
        # 准备长时间响应模?        mock_time.side_effect = [1000, 1003.117, 2000]
        mock_socket.return_value.connect.return_value = None
        
        # 创建警报实例
        alert = self.create_port_alert()
        alert = self.create_collector_mock(
            alert, 
            "WARNING", 
            "TCP OK - 3.1170 response on port 8080"
        )
        
        # 执行收集
        alert.collect()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_critical_threshold_exceeded(self, mock_time, mock_socket):
        """测试超过严重阈?""
        # 准备更长时间响应模拟
        mock_time.side_effect = [1000, 1005.324, 2000]
        mock_socket.return_value.connect.return_value = None
        
        # 创建警报实例
        alert = self.create_port_alert()
        alert = self.create_collector_mock(
            alert, 
            "CRITICAL", 
            "TCP OK - 5.3240 response on port 8080"
        )
        
        # 执行收集
        alert.collect()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_custom_threshold_configuration(self, mock_time, mock_socket):
        """测试自定义阈值配?""
        # 准备长时间响应模?        mock_time.side_effect = [1000, 1003.5, 2000]
        
        # 创建自定义阈值的警报
        source_meta = self.base_alert_source_meta.copy()
        source_meta["reporting"] = {
            "warning": {"value": 4.0},
            "critical": {"value": 5.0}
        }
        
        alert = self.create_port_alert(source_meta=source_meta)
        alert = self.create_collector_mock(
            alert, 
            "OK",  # 应在警告阈值内
            "TCP OK - 3.5000 response on port 8080"
        )
        
        # 执行收集
        alert.collect()


class ConnectionFailureTests(PortAlertTestBase):
    """测试连接失败场景"""
    
    @patch("socket.socket")
    @patch("time.time")
    def test_socket_timeout(self, mock_time, mock_socket):
        """测试连接超时"""
        # 模拟超时异常
        mock_socket.return_value.connect.side_effect = TimeoutError("Connection timed out")
        mock_time.side_effect = [1000, 1500, 2000]
        
        # 创建警报实例
        alert = self.create_port_alert()
        alert = self.create_collector_mock(
            alert, 
            "CRITICAL", 
            "Socket Timeout to example.com:8080"
        )
        
        # 执行收集
        alert.collect()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_connection_refused(self, mock_time, mock_socket):
        """测试连接被拒?""
        # 模拟连接拒绝异常
        mock_socket.return_value.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_time.side_effect = [1000, 1000.3, 2000]
        
        # 创建警报实例
        alert = self.create_port_alert()
        alert = self.create_collector_mock(
            alert, 
            "CRITICAL", 
            "Connection refused to example.com:8080"
        )
        
        # 执行收集
        alert.collect()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_generic_exception(self, mock_time, mock_socket):
        """测试通用异常"""
        # 模拟一般异?        mock_socket.return_value.connect.side_effect = Exception("Unknown error")
        mock_time.side_effect = [1000, 1000.2, 2000]
        
        # 创建警报实例
        alert = self.create_port_alert()
        alert = self.create_collector_mock(
            alert, 
            "CRITICAL", 
            "Unknown error to example.com:8080"
        )
        
        # 执行收集
        alert.collect()


class SpecialProtocolTests(PortAlertTestBase):
    """测试特殊协议处理（如ZooKeeper?""
    
    @patch("socket.socket")
    @patch("time.time")
    def test_zookeeper_command_check(self, mock_time, mock_socket):
        """测试ZooKeeper命令检?""
        # 准备ZooKeeper配置
        source_meta = {
            "uri": "http://zk.example.com:2181",
            "default_port": 2181,
            "parameters": [
                {"name": "socket.command", "value": "ruok"},
                {"name": "socket.command.response", "value": "imok"}
            ]
        }
        
        # 创建ZooKeeper警报
        alert_meta = self.base_alert_meta.copy()
        alert_meta["name"] = "zookeeper_server_process"
        
        # 配置模拟数据
        mock_time.side_effect = [1000, 1000.201, 2000]
        sock_mock = mock_socket.return_value
        sock_mock.recv.return_value = "imok".encode()
        
        # 创建警报实例
        alert = self.create_port_alert(alert_meta, source_meta)
        alert = self.create_collector_mock(
            alert, 
            "OK", 
            "TCP OK - 0.2010 response on port 2181"
        )
        
        # 执行收集
        alert.collect()
        
        # 验证已发送ZooKeeper命令
        sock_mock.send.assert_called_with("ruok".encode())
        sock_mock.recv.assert_called_once()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_zookeeper_invalid_response(self, mock_time, mock_socket):
        """测试ZooKeeper无效响应"""
        # 准备ZooKeeper配置
        source_meta = {
            "uri": "http://zk.example.com:2181",
            "default_port": 2181,
            "parameters": [
                {"name": "socket.command", "value": "ruok"},
                {"name": "socket.command.response", "value": "imok"}
            ]
        }
        
        # 创建ZooKeeper警报
        alert_meta = self.base_alert_meta.copy()
        alert_meta["name"] = "zookeeper_server_process"
        
        # 配置模拟数据（错误响应）
        mock_time.side_effect = [1000, 1000.201, 2000]
        sock_mock = mock_socket.return_value
        sock_mock.recv.return_value = "notok".encode()
        
        # 创建警报实例
        alert = self.create_port_alert(alert_meta, source_meta)
        alert = self.create_collector_mock(
            alert, 
            "CRITICAL", 
            "Invalid response to 'ruok' command: 'notok' (expected 'imok')"
        )
        
        # 执行收集
        alert.collect()
    
    @patch("socket.socket")
    @patch("time.time")
    def test_zookeeper_response_time_warning(self, mock_time, mock_socket):
        """测试ZooKeeper响应时间过长"""
        # 准备ZooKeeper配置
        source_meta = {
            "uri": "http://zk.example.com:2181",
            "default_port": 2181,
            "parameters": [
                {"name": "socket.command", "value": "ruok"},
                {"name": "socket.command.response", "value": "imok"}
            ]
        }
        
        # 创建ZooKeeper警报
        alert_meta = self.base_alert_meta.copy()
        alert_meta["name"] = "zookeeper_server_process"
        
        # 配置长响应时间模?        mock_time.side_effect = [1000, 1003.501, 2000]
        sock_mock = mock_socket.return_value
        sock_mock.recv.return_value = "imok".encode()
        
        # 创建警报实例
        alert = self.create_port_alert(alert_meta, source_meta)
        alert = self.create_collector_mock(
            alert, 
            "WARNING", 
            "TCP OK - 3.5010 response on port 2181"
        )
        
        # 执行收集
        alert.collect()


class ThresholdConfigurationTests(PortAlertTestBase):
    """测试阈值配置处?""
    
    def test_threshold_parsing(self):
        """测试阈值解?""
        # 创建带警告和严重阈值的警报
        source_meta = self.base_alert_source_meta.copy()
        source_meta["reporting"] = {
            "warning": {"value": "2.5"},
            "critical": {"value": "4.0"}
        }
        
        alert = self.create_port_alert(source_meta=source_meta)
        
        self.assertEqual(alert.warning, 2.5)
        self.assertEqual(alert.critical, 4.0)
    
    def test_invalid_threshold_handling(self):
        """测试无效阈值处?""
        # 创建含无效值的警报
        source_meta = self.base_alert_source_meta.copy()
        source_meta["reporting"] = {
            "warning": {"value": "invalid"},
            "critical": {"value": "not a number"}
        }
        
        alert = self.create_port_alert(source_meta=source_meta)
        
        # 应使用默认?        self.assertEqual(alert.warning, 2.0)
        self.assertEqual(alert.critical, 5.0)
    
    def test_threshold_validation(self):
        """测试阈值逻辑验证"""
        # 创建警告阈值大于严重阈值的无效配置
        source_meta = self.base_alert_source_meta.copy()
        source_meta["reporting"] = {
            "warning": {"value": "4.0"},
            "critical": {"value": "2.0"}
        }
        
        alert = self.create_port_alert(source_meta=source_meta)
        
        # 警告阈值应不大于严重阈?        self.assertEqual(alert.warning, 2.0)
        self.assertEqual(alert.critical, 2.0)
    
    def test_missing_threshold_handling(self):
        """测试缺失阈值配?""
        # 没有阈值配?        alert = self.create_port_alert()
        
        # 应使用默认?        self.assertEqual(alert.warning, 2.0)
        self.assertEqual(alert.critical, 5.0)


class HostResolutionTests(PortAlertTestBase):
    """测试主机名解析功?""
    
    @patch("socket.socket")
    @patch("socket.getaddrinfo")
    def test_hostname_resolution(self, mock_getaddrinfo, mock_socket):
        """测试主机名解析过?""
        # 模拟DNS解析
        mock_getaddrinfo.return_value = [(None, None, None, None, ('192.168.1.100',))]
        
        # 创建使用主机名的警报
        source_meta = {"uri": "http://my-server.local:8080"}
        alert = self.create_port_alert(source_meta=source_meta)
        alert = self.create_collector_mock(alert, "OK", "TCP OK")
        
        # 执行收集
        alert.collect()
        
        # 验证解析和连?        mock_getaddrinfo.assert_called_with('my-server.local', 8080)
        mock_socket.return_value.connect.assert_called_with(('192.168.1.100', 8080))
    
    @patch("socket.socket")
    @patch("socket.getaddrinfo")
    def test_hostname_resolution_failure(self, mock_getaddrinfo, mock_socket):
        """测试主机名解析失?""
        # 模拟DNS解析失败
        mock_getaddrinfo.side_effect = Exception("DNS resolution failed")
        
        # 创建使用主机名的警报
        source_meta = {"uri": "http://invalid-host.local:8080"}
        alert = self.create_port_alert(source_meta=source_meta)
        alert = self.create_collector_mock(
            alert, 
            "CRITICAL", 
            "DNS resolution failed for invalid-host.local:8080"
        )
        
        # 执行收集
        alert.collect()


if __name__ == "__main__":
    unittest.main()

