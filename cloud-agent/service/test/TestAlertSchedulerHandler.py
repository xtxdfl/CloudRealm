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

import copy
import os

from AlertSchedulerHandler import AlertSchedulerHandler  # 导入告警调度?from alerts.metric_alert import MetricAlert  # 导入指标告警
from alerts.ams_alert import AmsAlert  # 导入AMS告警
from alerts.port_alert import PortAlert  # 导入端口告警
from alerts.web_alert import WebAlert  # 导入Web告警

from InitializerModule import InitializerModule  # 导入初始化模?
from cloudConfig import cloudConfig  # 导入配置模块

from mock.mock import Mock, MagicMock, patch  # 导入测试模拟工具
from unittest import TestCase  # 导入测试基类

# 定义测试文件路径
TEST_PATH = os.path.join("cloud_agent", "dummy_files")


class TestAlertSchedulerHandler(TestCase):
    """单元测试类：验证告警调度处理器功?""
    
    def setUp(self):
        """准备测试环境：基础配置初始?""
        self.config = cloudConfig()  # 创建配置实例

    @patch("cloud_commons.network.reconfigure_urllib2_opener")
    def test_job_context_injector(self, reconfigure_urllib2_opener_mock):
        """测试代理设置注入 - 验证网络连接配置是否根据设置调整"""
        # 禁用系统代理的配置测?        self.config.use_system_proxy_setting = lambda: False  # 模拟禁用系统代理
        
        # 初始化模块并创建调度?        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 执行代理注入
        scheduler._job_context_injector(self.config)
        self.assertTrue(reconfigure_urllib2_opener_mock.called)  # 验证代理配置调整
        
        # 启用系统代理的配置测?        reconfigure_urllib2_opener_mock.reset_mock()
        self.config.use_system_proxy_setting = lambda: True  # 模拟启用系统代理
        
        # 重新初始化并测试
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        scheduler._job_context_injector(self.config)
        self.assertFalse(reconfigure_urllib2_opener_mock.called)  # 验证无调整操?
    def test_json_to_callable_metric(self):
        """测试JSON转MetricAlert - 验证指标告警对象转换正确?""
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 创建指标告警JSON定义
        json_definition = {"source": {"type": "METRIC"}}
        
        # 执行转换
        callable_result = scheduler._AlertSchedulerHandler__json_to_callable(
            "cluster", "host", "host", copy.deepcopy(json_definition)
        )
        
        # 验证转换结果
        self.assertIsNotNone(callable_result)
        self.assertIsInstance(callable_result, MetricAlert)
        self.assertEqual(callable_result.alert_meta, json_definition)
        self.assertEqual(callable_result.alert_source_meta, json_definition["source"])

    def test_json_to_callable_ams(self):
        """测试JSON转AmsAlert - 验证AMS告警对象转换正确?""
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 创建AMS告警JSON定义
        json_definition = {"source": {"type": "AMS"}}
        
        # 执行转换
        callable_result = scheduler._AlertSchedulerHandler__json_to_callable(
            "cluster", "host", "host", copy.deepcopy(json_definition)
        )
        
        # 验证转换结果
        self.assertIsNotNone(callable_result)
        self.assertIsInstance(callable_result, AmsAlert)
        self.assertEqual(callable_result.alert_meta, json_definition)
        self.assertEqual(callable_result.alert_source_meta, json_definition["source"])

    def test_json_to_callable_port(self):
        """测试JSON转PortAlert - 验证端口告警对象转换正确?""
        # 创建端口告警JSON定义
        json_definition = {"source": {"type": "PORT"}}
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 执行转换
        callable_result = scheduler._AlertSchedulerHandler__json_to_callable(
            "cluster", "host", "host", copy.deepcopy(json_definition)
        )
        
        # 验证转换结果
        self.assertIsNotNone(callable_result)
        self.assertIsInstance(callable_result, PortAlert)
        self.assertEqual(callable_result.alert_meta, json_definition)
        self.assertEqual(callable_result.alert_source_meta, json_definition["source"])

    def test_json_to_callable_web(self):
        """测试JSON转WebAlert - 验证Web告警对象转换正确?""
        # 创建Web告警JSON定义
        json_definition = {"source": {"type": "WEB"}}
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 执行转换
        callable_result = scheduler._AlertSchedulerHandler__json_to_callable(
            "cluster", "host", "host", copy.deepcopy(json_definition)
        )
        
        # 验证转换结果
        self.assertIsNotNone(callable_result)
        self.assertIsInstance(callable_result, WebAlert)
        self.assertEqual(callable_result.alert_meta, json_definition)
        self.assertEqual(callable_result.alert_source_meta, json_definition["source"])

    def test_json_to_callable_none(self):
        """测试无效类型转换 - 验证未知告警类型的正确处?""
        # 创建未知告警类型JSON定义
        json_definition = {"source": {"type": "SOMETHING"}}
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 执行转换
        callable_result = scheduler._AlertSchedulerHandler__json_to_callable(
            "cluster", "host", "host", copy.deepcopy(json_definition)
        )
        
        # 验证转换结果为None（表示无法处理）
        self.assertIsNone(callable_result)

    def test_execute_alert_noneScheduler(self):
        """测试空调度器执行 - 验证调度器未启动时的安全处理"""
        execution_commands = []  # 空命令列?        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 设置调度器为?        scheduler._AlertSchedulerHandler__scheduler = None
        alert_mock = Mock()  # 创建模拟告警对象
        # 设置JSON转换直接返回模拟对象
        scheduler._AlertSchedulerHandler__json_to_callable = Mock(return_value=alert_mock)
        
        # 执行告警指令
        scheduler.execute_alert(execution_commands)
        
        # 验证告警收集未被调用（空命令但有调度器为空的特殊情况?        self.assertFalse(alert_mock.collect.called)

    def test_execute_alert_noneCommands(self):
        """测试空命令执?- 验证空输入处理能?""
        execution_commands = None  # None输入
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        alert_mock = Mock()
        scheduler._AlertSchedulerHandler__json_to_callable = Mock(return_value=alert_mock)
        
        # 执行告警指令
        scheduler.execute_alert(execution_commands)
        
        # 验证告警收集未被调用
        self.assertFalse(alert_mock.collect.called)

    def test_execute_alert_emptyCommands(self):
        """测试空命令列表执?- 验证空列表处理能?""
        execution_commands = []  # 空命令列?        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        alert_mock = Mock()
        scheduler._AlertSchedulerHandler__json_to_callable = Mock(return_value=alert_mock)
        
        # 执行告警指令
        scheduler.execute_alert(execution_commands)
        
        # 验证告警收集未被调用
        self.assertFalse(alert_mock.collect.called)

    def test_execute_alert(self):
        """测试常规告警执行 - 验证正常告警处理流程"""
        # 创建告警执行命令
        execution_commands = [
            {
                "clusterName": "cluster",
                "hostName": "host",
                "publicHostName": "host",
                "alertDefinition": {"name": "alert1"},
            }
        ]
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 创建模拟告警对象
        alert_mock = MagicMock()
        alert_mock.collect = Mock()
        alert_mock.set_helpers = Mock()
        # 设置JSON转换直接返回模拟对象
        scheduler._AlertSchedulerHandler__json_to_callable = Mock(return_value=alert_mock)
        # 模拟配置映射数据
        scheduler._AlertSchedulerHandler__config_maps = {"cluster": {}}
        
        # 执行告警指令
        scheduler.execute_alert(execution_commands)
        
        # 验证转换调用参数
        scheduler._AlertSchedulerHandler__json_to_callable.assert_called_with(
            "cluster", "host", "host", {"name": "alert1"}
        )
        # 验证告警收集被调?        self.assertTrue(alert_mock.collect.called)

    @patch("os.path.exists", new=MagicMock(return_value=True))
    def test_execute_alert_from_extension(self):
        """测试扩展告警执行 - 验证扩展功能支持?""
        execution_commands = [
            {
                "clusterName": "cluster",
                "hostName": "host",
                "publicHostName": "host",
                "alertDefinition": {"name": "alert1"},
            }
        ]
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 创建模拟告警对象
        alert_mock = MagicMock()
        alert_mock.collect = Mock()
        alert_mock.set_helpers = Mock()
        # 设置JSON转换直接返回模拟对象
        scheduler._AlertSchedulerHandler__json_to_callable = Mock(return_value=alert_mock)
        # 模拟配置映射数据
        scheduler._AlertSchedulerHandler__config_maps = {"cluster": {}}
        
        # 执行告警指令
        scheduler.execute_alert(execution_commands)
        
        # 验证转换调用参数
        scheduler._AlertSchedulerHandler__json_to_callable.assert_called_with(
            "cluster", "host", "host", {"name": "alert1"}
        )
        # 验证告警收集被调?        self.assertTrue(alert_mock.collect.called)

    def test_load_definitions(self):
        """测试定义加载 - 验证告警定义载入能力"""
        # 创建端口告警定义数据
        definitions = {"alertDefinitions": [{"source": {"type": "PORT"}}]}
        
        initializer_module = InitializerModule()
        initializer_module.init()
        # 将定义写入缓?        initializer_module.alert_definitions_cache.rewrite_cluster_cache("0", definitions)
        
        scheduler = AlertSchedulerHandler(initializer_module)
        # 模拟配置映射数据
        scheduler._AlertSchedulerHandler__config_maps = {"cluster": {}}
        
        # 加载定义
        definitions = scheduler._AlertSchedulerHandler__load_definitions()
        
        # 验证加载的告警对象类?        alert_def = definitions[0]
        self.assertIsInstance(alert_def, PortAlert)

    def test_load_definitions_noFile(self):
        """测试空定义加?- 验证空定义安全处理能?""
        initializer_module = InitializerModule()
        initializer_module.init()
        # 写入空定?        initializer_module.alert_definitions_cache.rewrite_cluster_cache(
            "0", {"alertDefinitions": []}
        )
        
        scheduler = AlertSchedulerHandler(initializer_module)
        # 模拟配置映射数据
        scheduler._AlertSchedulerHandler__config_maps = {"cluster": {}}
        
        # 加载定义
        definitions = scheduler._AlertSchedulerHandler__load_definitions()
        
        # 验证结果为空列表
        self.assertEqual(definitions, [])

    def __test_start(self):
        """测试调度器启动（内部保留?""
        execution_commands = [
            {
                "clusterName": "cluster",
                "hostName": "host",
                "publicHostName": "host",
                "alertDefinition": {"name": "alert1"},
            }
        ]
        
        initializer_module = InitializerModule()
        initializer_module.init()
        scheduler = AlertSchedulerHandler(initializer_module)
        
        # 创建模拟告警对象
        alert_mock = MagicMock()
        alert_mock.interval = Mock(return_value=5)
        alert_mock.collect = Mock()
        alert_mock.set_helpers = Mock()
        
        # 模拟调度方法
        scheduler.schedule_definition = MagicMock()
        # 创建模拟调度?        scheduler._AlertSchedulerHandler__scheduler = MagicMock()
        scheduler._AlertSchedulerHandler__scheduler.running = False
        scheduler._AlertSchedulerHandler__scheduler.start = Mock()
        # 设置JSON转换直接返回模拟对象
        scheduler._AlertSchedulerHandler__json_to_callable = Mock(return_value=alert_mock)
        # 模拟配置映射数据
        scheduler._AlertSchedulerHandler__config_maps = {"cluster": {}}
        
        # 启动调度?        scheduler.start()
        
        # 验证调度器启动方法被调用
        self.assertTrue(scheduler._AlertSchedulerHandler__scheduler.start.called)
        # 验证调度方法被调?        scheduler.schedule_definition.assert_called_with(alert_mock)
