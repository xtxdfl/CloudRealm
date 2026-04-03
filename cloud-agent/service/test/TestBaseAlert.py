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
from unittest.mock import MagicMock, patch
from alerts.base_alert import BaseAlert
from cloudConfig import cloudConfig


class BaseAlertTestBase(unittest.TestCase):
    """BaseAlert基本功能测试基类"""
    
    def setUp(self):
        # 创建基础配置
        self.config = cloudConfig()
        
        # 默认警报元数?        self.default_alert_meta = {
            "name": "TestAlert",
            "uuid": "test-uuid-123",
            "enabled": "true",
            "interval": 5
        }
        
        # 默认警报源元数据
        self.default_source_meta = {
            "default_param": "value"
        }
    
    def create_alert_instance(self, alert_meta=None, source_meta=None):
        """创建BaseAlert实例"""
        alert_meta = alert_meta or self.default_alert_meta.copy()
        source_meta = source_meta or self.default_source_meta.copy()
        return BaseAlert(alert_meta, source_meta, self.config)


class AlertConfigurationTests(BaseAlertTestBase):
    """测试警报配置相关功能"""
    
    def test_interval_handling(self):
        """测试不同间隔配置处理"""
        test_cases = [
            # 测试缺省间隔
            ({}, None, 1, "缺省元数据应返回间隔1"),
            # 测试值为0的间?            ({"interval": 0}, None, 1, "间隔0应强制设置为1"),
            # 测试负值间?            ({"interval": -5}, None, 1, "负间隔应强制设置?"),
            # 测试有效间隔
            ({"interval": 10}, None, 10, "有效间隔应正确设?),
            # 测试非数字间?            ({"interval": "invalid"}, None, 1, "非数字间隔应返回1"),
            # 测试源数据中的间隔覆?            ({}, {"interval": 15}, 15, "源数据中的间隔应覆盖警报元数?),
        ]
        
        for meta, source, expected, message in test_cases:
            with self.subTest(msg=message):
                alert = self.create_alert_instance(meta, source)
                self.assertEqual(alert.interval(), expected, message)
    
    def test_enabled_status(self):
        """测试启用状态解?""
        test_cases = [
            # 测试缺省启用状?            ({}, "true", "缺省元数据应返回true"),
            # 测试显式启用
            ({"enabled": "true"}, None, "true", "显式启用应返回true"),
            # 测试显式禁用
            ({"enabled": "false"}, None, "false", "显式禁用应返回false"),
            # 测试无效?            ({"enabled": "invalid"}, None, "true", "无效值应视为true"),
            # 测试源数据覆?            ({}, {"enabled": "false"}, "false", "源数据应覆盖警报元数?),
        ]
        
        for meta, source, expected, message in test_cases:
            with self.subTest(msg=message):
                alert = self.create_alert_instance(meta, source)
                self.assertEqual(alert.is_enabled(), expected, message)
    
    def test_name_retrieval(self):
        """测试名称获取功能"""
        test_cases = [
            # 测试缺省名称
            ({}, "BaseAlert", "缺省名称应为BaseAlert"),
            # 测试显式名称
            ({"name": "CustomAlert"}, None, "CustomAlert", "应返回正确名?),
            # 测试源数据覆?            ({"name": "AlertMeta"}, {"name": "AlertSource"}, "AlertSource", "源数据名称应覆盖警报元数?),
        ]
        
        for meta, source, expected, message in test_cases:
            with self.subTest(msg=message):
                alert = self.create_alert_instance(meta, source)
                self.assertEqual(alert.get_name(), expected, message)
    
    def test_uuid_retrieval(self):
        """测试UUID获取功能"""
        test_cases = [
            # 测试缺省UUID
            ({}, None, "缺少UUID时应生成唯一标识"),
            # 测试显式UUID
            ({"uuid": "test-uuid-456"}, None, "test-uuid-456", "应返回正确UUID"),
            # 测试源数据覆?            ({"uuid": "meta-uuid"}, {"uuid": "source-uuid"}, "source-uuid", "源数据UUID应覆盖警报元数据"),
        ]
        
        for meta, source, expected, message in test_cases:
            with self.subTest(msg=message):
                alert = self.create_alert_instance(meta, source)
                result = alert.get_uuid()
                if message == "缺少UUID时应生成唯一标识":
                    self.assertTrue(len(result) > 10, "应生成有效的UUID")
                else:
                    self.assertEqual(result, expected, message)


class ClusterConfigurationTests(BaseAlertTestBase):
    """测试集群配置功能"""
    
    def test_cluster_configuration(self):
        """测试集群信息设置"""
        alert = self.create_alert_instance()
        
        # 设置集群信息
        cluster_name = "TestCluster"
        cluster_id = "cluster-001"
        host_name = "test-host.example.com"
        
        alert.set_cluster(cluster_name, cluster_id, host_name)
        
        # 验证设置
        self.assertEqual(alert.cluster_name, cluster_name)
        self.assertEqual(alert.cluster_id, cluster_id)
        self.assertEqual(alert.host_name, host_name)
        self.assertEqual(alert._BaseAlert__host_id, host_name)


class MethodPlaceholderTests(BaseAlertTestBase):
    """测试占位方法功能"""
    
    def test_collect_method(self):
        """测试collect方法的默认行?""
        alert = self.create_alert_instance()
        
        # 默认应抛出未实现错误
        with self.assertRaises(NotImplementedError):
            alert.collect()
    
    def test_operation_config_with_thresholds(self):
        """测试带阈值的操作配置"""
        alert_meta = {
            "warning_threshold": 75.0,
            "critical_threshold": 90.0
        }
        alert = self.create_alert_instance(alert_meta)
        
        # 验证阈值设?        self.assertEqual(alert.warning, 75.0)
        self.assertEqual(alert.critical, 90.0)
    
    def test_threshold_validation(self):
        """测试阈值验证逻辑"""
        alert_meta = {
            "critical_threshold": 70.0,
            "warning_threshold": 80.0  # 警告阈值大于严重阈?        }
        alert = self.create_alert_instance(alert_meta)
        
        # 验证阈值自动修正（警告阈值应不大于严重阈值）
        self.assertEqual(alert.warning, 70.0)
        self.assertEqual(alert.critical, 70.0)
        
        alert_meta = {
            "warning_threshold": "invalid",
            "critical_threshold": "invalid"
        }
        alert = self.create_alert_instance(alert_meta)
        
        # 验证无效阈值处?        self.assertEqual(alert.warning, 0)
        self.assertEqual(alert.critical, 0)


class AlertContextTests(BaseAlertTestBase):
    """测试警报上下文功?""
    
    @patch("alerts.base_alert.logger")
    def test_configuration_logging(self, logger_mock):
        """测试配置参数记录功能"""
        source_meta = {
            "param1": "value1",
            "param2": 42,
            "password": "secret",
            "_internal": "hidden"
        }
        
        alert = self.create_alert_instance(source_meta=source_meta)
        
        # 验证敏感信息过滤和日志记?        expected_log = {
            "default_param": "value",  # 来自默认源元数据
            "param1": "value1",
            "param2": 42,
            "password": "****",  # 敏感字段应屏?            "_internal": "hidden"  # 下划线开头字段应不记?        }
        
        alert.log_config_parameters()
        
        # 验证日志调用
        logger_mock.info.assert_called()
        call_args = logger_mock.info.call_args[0][0]
        
        # 验证参数是否存在
        self.assertIn("param1", call_args)
        self.assertIn("param2", call_args)
        self.assertNotIn("secret", call_args)  # 确保密码被屏?        self.assertNotIn("_internal", call_args)  # 确保内部字段未被记录


class ThresholdEvaluationTests(BaseAlertTestBase):
    """测试阈值评估功?""
    
    def test_percentage_threshold_evaluation(self):
        """测试百分比阈值评?""
        alert_meta = {
            "warning_threshold": 70.0,
            "critical_threshold": 90.0,
            "value_type": "PERCENTAGE"
        }
        alert = self.create_alert_instance(alert_meta)
        
        test_cases = [
            (65.0, "OK", "低于警告阈值应为OK状?),
            (75.0, "WARNING", "在警告阈值范围内应为WARNING"),
            (95.0, "CRITICAL", "超过严重阈值应为CRITICAL")
        ]
        
        for value, expected_state, msg in test_cases:
            with self.subTest(msg=msg):
                state = alert._evaluate_threshold(value)
                self.assertEqual(state, expected_state, msg)
    
    def test_byte_threshold_evaluation(self):
        """测试字节阈值评?""
        alert_meta = {
            "warning_threshold": "500MB",
            "critical_threshold": "1GB",
            "value_type": "BYTES"
        }
        alert = self.create_alert_instance(alert_meta)
        
        test_cases = [
            (400 * 1024 * 1024, "OK", "低于警告阈值应为OK状?),  # 400MB
            (700 * 1024 * 1024, "WARNING", "在警告阈值范围内应为WARNING"),  # 700MB
            (1.5 * 1024 * 1024 * 1024, "CRITICAL", "超过严重阈值应为CRITICAL")  # 1.5GB
        ]
        
        for value, expected_state, msg in test_cases:
            with self.subTest(msg=msg):
                state = alert._evaluate_threshold(value)
                self.assertEqual(state, expected_state, msg)
    
    def test_invalid_threshold_evaluation(self):
        """测试无效值阈值评?""
        alert = self.create_alert_instance()
        
        test_values = [None, "invalid", -10]
        for value in test_values:
            with self.subTest(value=value):
                state = alert._evaluate_threshold(value)
                self.assertEqual(state, "UNKNOWN", "无效值应返回UNKNOWN状?)


if __name__ == "__main__":
    unittest.main()

