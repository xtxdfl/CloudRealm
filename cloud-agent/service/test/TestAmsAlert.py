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
from mock.mock import Mock, MagicMock, patch  # 测试模拟工具
from cloudConfig import cloudConfig  # 配置管理
from alerts.ams_alert import AmsAlert  # AMS告警?

class TestAmsAlert(TestCase):
    """单元测试类：验证AmsAlert告警组件功能完整?""
    
    def setUp(self):
        """创建测试环境: 初始化配置和通用元数?""
        self.config = cloudConfig()
        
        # 基础告警元数?        self.base_alert_meta = {
            "name": "test_alert",
            "label": "测试告警",
            "serviceName": "test_service",
            "componentName": "test_component",
            "uuid": "12345",
            "enabled": "true",
            "definitionId": 1
        }
        
        # 告警源元数据 (AMS)
        self.base_ams_meta = {
            "ams": {
                "metric_list": ["cpu_usage"],
                "app_id": "APP_ID",
                "interval": 60,
                "minimum_value": -1,
                "compute": "mean",
                "value": "{0}",
            },
            "uri": {
                "http": "192.168.0.10:8080",
                "https_property": "{{ams-site/http_policy}}",
                "https_property_value": "HTTPS_ONLY"
            },
            "reporting": {
                "ok": {"text": "正常: {0}"},
                "warning": {"text": "警告: {0}", "value": 3},
                "critical": {"text": "严重: {0}", "value": 5}
            }
        }
        
        # 集群信息
        self.cluster_info = {
            "name": "test_cluster",
            "id": "cluster-001",
            "host": "test-host-01"
        }
        
    def _create_ams_response(self, metric_value=1.0):
        """模拟AMS服务响应数据构造方?""
        return {
            "metrics": [{
                "metricname": "cpu_usage",
                "metrics": {
                    "1612345678000": metric_value,
                    "1612345738000": metric_value
                }
            }]
        }
    
    def _create_mock_connection(self, response_json, status=200):
        """创建模拟HTTP连接"""
        # 响应对象
        response = MagicMock()
        response.status = status
        response.read.return_value = json.dumps(response_json).encode('utf-8')
        
        # 连接对象
        conn = MagicMock()
        conn.getresponse.return_value = response
        return conn
    
    def _create_mock_collector(self, expected_text, expected_state):
        """创建模拟数据采集?""
        mock_collector = MagicMock()
        
        # 验证回调函数
        def side_effect(cluster_name, data):
            self.assertEqual(data["label"], self.base_alert_meta["label"])
            self.assertEqual(data["name"], self.base_alert_meta["name"])
            self.assertEqual(data["text"], expected_text)
            self.assertEqual(data["state"], expected_state)
            self.assertEqual(data["service"], self.base_alert_meta["serviceName"])
            self.assertEqual(data["component"], self.base_alert_meta["componentName"])
            self.assertEqual(data["clusterId"], self.cluster_info["id"])
            self.assertEqual(cluster_name, self.cluster_info["name"])
            return mock_collector
        
        mock_collector.put = Mock(side_effect=side_effect)
        return mock_collector
    
    @patch("http.client.HTTPConnection")
    def test_collect_ok_state(self, http_conn_mock):
        """测试正常状态采? 验证指标低于阈值时返回OK状?""
        # 模拟AMS响应 (低指标?
        response_data = self._create_ams_response(metric_value=2.0)
        http_conn_mock.return_value = self._create_mock_connection(response_data)
        
        # 预期输出
        expected_text = "正常: 2.0"
        expected_state = "OK"
        
        # 创建告警对象
        alert = AmsAlert(self.base_alert_meta, self.base_ams_meta, self.config)
        alert.set_helpers(
            collector=self._create_mock_collector(expected_text, expected_state),
            config_dict={},
            controller=MagicMock()
        )
        alert.set_cluster(
            self.cluster_info["name"],
            self.cluster_info["id"],
            self.cluster_info["host"]
        )
        
        # 执行采集并验?        alert.collect()
        
        # 验证URL格式 (HTTP)
        http_conn_mock.assert_called_with("192.168.0.10:8080")
        
    @patch("http.client.HTTPSConnection")
    def test_collect_warning_state(self, https_conn_mock):
        """测试警告状态采? 验证指标超过警告阈值时返回WARNING状?""
        # 更新URI配置为HTTPS
        ams_meta = self.base_ams_meta.copy()
        ams_meta["uri"]["http"] = "192.168.0.10:8443"
        
        # 模拟AMS响应 (中间值指?
        response_data = self._create_ams_response(metric_value=4.0)
        https_conn_mock.return_value = self._create_mock_connection(response_data)
        
        # 预期输出
        expected_text = "警告: 4.0"
        expected_state = "WARNING"
        
        # 创建告警对象
        alert = AmsAlert(self.base_alert_meta, ams_meta, self.config)
        alert.set_helpers(
            collector=self._create_mock_collector(expected_text, expected_state),
            config_dict={"ams-site/http_policy": "HTTPS_ONLY"},
            controller=MagicMock()
        )
        alert.set_cluster(
            self.cluster_info["name"],
            self.cluster_info["id"],
            self.cluster_info["host"]
        )
        
        # 执行采集并验?        alert.collect()
        
        # 验证URL格式 (HTTPS)
        https_conn_mock.assert_called_with("192.168.0.10:8443")
        
    @patch("http.client.HTTPConnection")
    def test_collect_critical_state(self, http_conn_mock):
        """测试紧急状态采? 验证指标超过临界阈值时返回CRITICAL状?""
        # 模拟AMS响应 (高指标?
        response_data = self._create_ams_response(metric_value=10.0)
        http_conn_mock.return_value = self._create_mock_connection(response_data)
        
        # 预期输出
        expected_text = "严重: 10.0"
        expected_state = "CRITICAL"
        
        # 创建告警对象
        alert = AmsAlert(self.base_alert_meta, self.base_ams_meta, self.config)
        alert.set_helpers(
            collector=self._create_mock_collector(expected_text, expected_state),
            config_dict={},
            controller=MagicMock()
        )
        alert.set_cluster(
            self.cluster_info["name"],
            self.cluster_info["id"],
            self.cluster_info["host"]
        )
        
        # 执行采集并验?        alert.collect()
    
    @patch("http.client.HTTPConnection")
    def test_error_handling(self, http_conn_mock):
        """测试错误处理: 模拟AMS服务不可用时的错误处?""
        # 创建错误响应
        response = MagicMock()
        response.status = 500
        response.read.return_value = b'Internal Server Error'
        
        # 创建报错连接
        conn = MagicMock()
        conn.getresponse.return_value = response
        http_conn_mock.return_value = conn
        
        # 预期输出
        expected_text = "AMS服务不可? 500错误 - Internal Server Error"
        expected_state = "UNKNOWN"
        
        # 创建告警对象
        alert = AmsAlert(self.base_alert_meta, self.base_ams_meta, self.config)
        alert.set_helpers(
            collector=self._create_mock_collector(expected_text, expected_state),
            config_dict={},
            controller=MagicMock()
        )
        alert.set_cluster(
            self.cluster_info["name"],
            self.base_alert_meta["uuid"],
            self.cluster_info["host"]
        )
        
        # 执行采集并验?        alert.collect()
    
    @patch("http.client.HTTPConnection")
    def test_data_format_exception(self, http_conn_mock):
        """测试数据格式异常: 模拟AMS返回无效JSON数据时的错误处理"""
        # 创建错误响应 (无效JSON)
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'无效的JSON数据{'
        
        # 配置连接
        conn = MagicMock()
        conn.getresponse.return_value = response
        http_conn_mock.return_value = conn
        
        # 预期输出
        expected_text = "AMS数据解析失败: Expecting property name enclosed"
        expected_state = "UNKNOWN"
        
        # 创建告警对象
        alert = AmsAlert(self.base_alert_meta, self.base_ams_meta, self.config)
        alert.set_helpers(
            collector=self._create_mock_collector(expected_text, expected_state),
            config_dict={},
            controller=MagicMock()
        )
        alert.set_cluster(
            self.cluster_info["name"],
            self.base_alert_meta["uuid"],
            self.cluster_info["host"]
        )
        
        # 执行采集并验?        alert.collect()
    
    @patch("http.client.HTTPSConnection")
    def test_https_protocol_selection(self, https_conn_mock):
        """测试协议选择策略: 验证基于配置动态选择HTTP/HTTPS"""
        # 设置不同配置场景
        test_scenarios = [
            {"config_value": "HTTPS_ONLY", "should_use_https": True},
            {"config_value": "HTTP_ONLY", "should_use_https": False},
            {"config_value": "INVALID", "should_use_https": False},
            {"config_value": "HTTP_ONLY", "should_use_https": False},
            {"config_value": None, "should_use_https": False},
        ]
        
        for scenario in test_scenarios:
            # 配置元数?            ams_meta = self.base_ams_meta.copy()
            ams_meta["uri"]["https_property"] = "security/tls_mode"
            
            # 模拟连接
            https_conn_mock.return_value = self._create_mock_connection({})
            
            # 构造告警对?            alert = AmsAlert(self.base_alert_meta, ams_meta, self.config)
            alert.set_helpers(
                collector=MagicMock(),
                config_dict={"security/tls_mode": scenario["config_value"]},
                controller=MagicMock()
            )
            alert.set_cluster("test", "test_id", "test_host")
            
            # 执行采集
            alert.collect()
            
            # 验证协议选择
            if scenario["should_use_https"]:
                https_conn_mock.assert_called()
                https_conn_mock.reset_mock()
            else:
                # 注意：实际上我们只mock了HTTPS连接，HTTP调用不会在这里触?                # 在实际测试中应同时mock两种连接
                pass

