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

from unittest import TestCase
from alerts.script_alert import ScriptAlert  # 导入被测试的脚本告警?from mock.mock import Mock, MagicMock, patch  # 导入mock库用于模拟对?import os  # 导入操作系统功能模块

# 导入cloud配置模块
from cloudConfig import cloudConfig

# 定义dummy文件路径 - 用于测试的模拟文件目?DUMMY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dummy_files")


class TestScriptAlert(TestCase):
    """单元测试类：验证ScriptAlert的收集功?""
    
    def setUp(self):
        """在每个测试方法前执行：创建基础环境"""
        # 创建cloud配置实例 - 用于告警初始?        self.config = cloudConfig()

    def test_collect(self):
        """测试脚本告警收集功能"""
        # 准备告警元数据（模拟实际告警配置?        alert_meta = {
            "definitionId": 1,  # 告警定义ID
            "name": "alert1",  # 告警名称
            "label": "label1",  # 告警标签
            "serviceName": "service1",  # 服务名称
            "componentName": "component1",  # 组件名称
            "uuid": "123",  # 唯一ID
            "enabled": "true",  # 启用状?        }
        
        # 准备告警源数据（包含脚本路径等重要信息）
        alert_source_meta = {
            "stacks_directory": DUMMY_PATH,  # 栈目录路?            "path": os.path.join(DUMMY_PATH, "test_script.py"),  # 脚本文件路径
            "common_services_directory": DUMMY_PATH,  # 公共服务目录
            "host_scripts_directory": DUMMY_PATH,  # 主机脚本目录
        }
        
        # 定义集群和主机信?        cluster = "c1"  # 集群名称
        cluster_id = "0"  # 集群ID
        host = "host1"  # 主机名称
        
        # 定义预期输出文本（根据脚本内容设定）
        expected_text = "bar is 12, baz is asd"

        def collector_side_effect(clus, data):
            """模拟收集器的副作用函数，用于验证调用参数"""
            # 验证传递的数据是否正确
            self.assertEqual(data["name"], alert_meta["name"])  # 检查告警名
            self.assertEqual(data["clusterId"], cluster_id)  # 检查集群ID
            self.assertEqual(clus, cluster)  # 检查集群名?            # TODO: 这里可以添加更多断言来验证data的内?            
        # 创建模拟收集器（用于捕获脚本执行结果?        mock_collector = MagicMock()
        mock_collector.put = Mock(side_effect=collector_side_effect)

        # 初始化脚本告警对?        alert = ScriptAlert(alert_meta, alert_source_meta, self.config)
        
        # 设置辅助对象（包含收集器和其他依赖）
        alert.set_helpers(
            mock_collector,  # 传入模拟的收集器
            MagicMock(),     # 模拟配置管理对象
            MagicMock()      # 模拟其它辅助对象（如参数处理器）
        )
        
        # 设置告警关联的集群信?        alert.set_cluster(cluster, cluster_id, host)

        # 执行收集操作（核心测试点?        alert.collect()
        
        # 验证收集器是否被调用?        self.assertTrue(mock_collector.put.called, "收集器未被调?)
        
        # TODO: 验证收集器调用次数和具体参数
        # 可以检查mock_collector.put.call_args_list的具体参?        
        # TODO: 验证脚本执行结果处理逻辑
        # 可以检查收集到的文本是否匹配expected_text
        # 可以验证脚本的stdout和stderr处理逻辑
        # 可以验证脚本返回码的处理逻辑
