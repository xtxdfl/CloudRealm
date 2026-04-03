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

import tempfile
from unittest import TestCase
import os
import logging
from mock.mock import patch, MagicMock, call
from cloud_commons import OSCheck  # 导入操作系统检测模?from only_for_platform import os_distro_value  # 导入平台相关?
# 使用mock设置distro模块返回?with patch("distro.linux_distribution", return_value=("Suse", "11", "Final")):
    from cloudConfig import cloudConfig  # 导入配置模块
    from ActualConfigHandler import ActualConfigHandler  # 导入实际配置处理?

class TestActualConfigHandler(TestCase):
    """单元测试类：验证实际配置处理功能"""
    
    def setUp(self):
        """准备测试环境：初始化服务组件元数?""
        # 导入服务组件常量定义
        from LiveStatus import LiveStatus
        
        # 定义服务列表
        LiveStatus.SERVICES = [
            "HDFS", "MAPREDUCE", "GANGLIA", "HBASE", "ZOOKEEPER", "OOZIE",
            "KERBEROS", "TEMPLETON", "HIVE", "YARN", "MAPREDUCE2", "FLUME",
            "TEZ", "FALCON", "STORM",
        ]
        
        # 定义客户端组件列?        LiveStatus.CLIENT_COMPONENTS = [
            {"serviceName": "HBASE", "componentName": "HBASE_CLIENT"},
            {"serviceName": "HDFS", "componentName": "HDFS_CLIENT"},
            # ... (其他客户端组?
        ]
        
        # 定义服务组件列表
        LiveStatus.COMPONENTS = [
            {"serviceName": "HDFS", "componentName": "DATANODE"},
            {"serviceName": "HDFS", "componentName": "NAMENODE"},
            # ... (其他服务组件)
        ]
    
    logger = logging.getLogger()

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    def test_read_write(self):
        """测试全局配置读写 - 验证基础配置数据的存储和检索功?""
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建模拟配置标签
        tags = {"global": "version1", "core-site": "version2"}
        
        # 创建配置处理器并写入配置
        handler = ActualConfigHandler(config, tags)
        handler.write_actual(tags)
        
        # 读取并验证配?        output = handler.read_actual()
        self.assertEqual(tags, output)
        
        # 清理测试文件
        os.remove(os.path.join(tmpdir, ActualConfigHandler.CONFIG_NAME))

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    def test_read_empty(self):
        """测试空配置读?- 验证缺失配置的安全处理机?""
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建配置处理?        handler = ActualConfigHandler(config, {})
        
        # 创建空配置文?        conf_file = os.path.join(tmpdir, ActualConfigHandler.CONFIG_NAME)
        open(conf_file, "w").close()  # 创建空文?        
        # 读取并验证空配置返回None
        output = handler.read_actual()
        self.assertEqual(None, output)
        
        # 清理测试文件
        os.remove(conf_file)

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    def test_read_write_component(self):
        """测试组件配置隔离 - 验证独立组件的配置存储能?""
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建模拟配置标签
        tags1 = {"global": "version1", "core-site": "version2"}
        
        # 创建配置处理?        handler = ActualConfigHandler(config, {})
        
        # 写入全局和组件配?        handler.write_actual(tags1)
        handler.write_actual_component("FOO", tags1)
        
        # 验证组件配置读取
        output1 = handler.read_actual_component("FOO")
        output2 = handler.read_actual_component("GOO")  # 不存在组?        
        self.assertEqual(tags1, output1)
        self.assertEqual(None, output2)
        
        # 创建新标签并覆盖全局配置
        tags2 = {"global": "version1", "core-site": "version2"}
        handler.write_actual(tags2)
        
        # 验证全局和组件配置隔?        output3 = handler.read_actual()
        output4 = handler.read_actual_component("FOO")
        self.assertEqual(tags2, output3)
        self.assertEqual(tags1, output4)  # 组件配置未改?        
        # 清理测试文件
        os.remove(os.path.join(tmpdir, "FOO_" + ActualConfigHandler.CONFIG_NAME))
        os.remove(os.path.join(tmpdir, ActualConfigHandler.CONFIG_NAME))

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    def test_write_actual_component_and_client_components(self):
        """测试客户端组件更?- 验证批量客户端配置更新机?""
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建不同版本的配置标?        tags1 = {"global": "version1", "core-site": "version2"}
        tags2 = {"global": "version33", "core-site": "version33"}
        
        # 创建配置处理?        clientsToUpdateConfigs1 = ["*"]  # 更新所有客户端
        handler = ActualConfigHandler(config, {})
        
        # 写入初始客户端配?        handler.write_actual_component("HDFS_CLIENT", tags1)
        handler.write_actual_component("HBASE_CLIENT", tags1)
        handler.write_actual_component("DATANODE", tags2)
        
        # 验证初始配置
        self.assertEqual(tags1, handler.read_actual_component("HDFS_CLIENT"))
        self.assertEqual(tags1, handler.read_actual_component("HBASE_CLIENT"))
        self.assertEqual(tags2, handler.read_actual_component("DATANODE"))
        
        # 更新HDFS服务下的所有客户端
        handler.write_client_components("HDFS", tags2, clientsToUpdateConfigs1)
        
        # 验证HDFS客户端更新，HBASE客户端不?        self.assertEqual(tags2, handler.read_actual_component("HDFS_CLIENT"))
        self.assertEqual(tags1, handler.read_actual_component("HBASE_CLIENT"))
        
        # 清理测试文件
        os.remove(os.path.join(tmpdir, "DATANODE_" + ActualConfigHandler.CONFIG_NAME))
        os.remove(os.path.join(tmpdir, "HBASE_CLIENT_" + ActualConfigHandler.CONFIG_NAME))
        os.remove(os.path.join(tmpdir, "HDFS_CLIENT_" + ActualConfigHandler.CONFIG_NAME))

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    @patch.object(ActualConfigHandler, "write_file")
    def test_write_client_components(self, write_file_mock):
        """测试客户端组件选择更新 - 验证特定组件的精确更新能?""
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建不同版本的配置标?        tags0 = {"global": "version0", "core-site": "version0"}
        tags1 = {"global": "version1", "core-site": "version2"}
        tags2 = {"global": "version33", "core-site": "version33"}
        
        # 创建配置处理器并初始化配?        clientsToUpdateConfigs1 = ["HDFS_CLIENT", "HBASE_CLIENT"]
        configTags = {"HDFS_CLIENT": tags0, "HBASE_CLIENT": tags1}
        handler = ActualConfigHandler(config, configTags)
        
        # 验证初始配置
        self.assertEqual(tags0, handler.read_actual_component("HDFS_CLIENT"))
        self.assertEqual(tags1, handler.read_actual_component("HBASE_CLIENT"))
        
        # 更新选定客户端配?        handler.write_client_components("HDFS", tags2, clientsToUpdateConfigs1)
        
        # 验证HDFS客户端更新，HBASE客户端不?        self.assertEqual(tags2, handler.read_actual_component("HDFS_CLIENT"))
        self.assertEqual(tags1, handler.read_actual_component("HBASE_CLIENT"))
        
        # 验证写文件方法被调用
        self.assertTrue(write_file_mock.called)
        self.assertEqual(1, write_file_mock.call_count)

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    @patch.object(ActualConfigHandler, "write_file")
    def test_write_empty_client_components(self, write_file_mock):
        """测试空更新列表处?- 验证零操作场景的处理能力"""
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建配置标签
        tags0 = {"global": "version0", "core-site": "version0"}
        tags1 = {"global": "version1", "core-site": "version2"}
        tags2 = {"global": "version33", "core-site": "version33"}
        
        # 创建配置处理器并初始化配?        clientsToUpdateConfigs1 = []  # 空更新列?        configTags = {"HDFS_CLIENT": tags0, "HBASE_CLIENT": tags1}
        handler = ActualConfigHandler(config, configTags)
        
        # 验证初始配置
        self.assertEqual(tags0, handler.read_actual_component("HDFS_CLIENT"))
        self.assertEqual(tags1, handler.read_actual_component("HBASE_CLIENT"))
        
        # 尝试空更?        handler.write_client_components("HDFS", tags2, clientsToUpdateConfigs1)
        
        # 验证配置保持不变
        self.assertEqual(tags0, handler.read_actual_component("HDFS_CLIENT"))
        self.assertEqual(tags1, handler.read_actual_component("HBASE_CLIENT"))
        
        # 验证写文件方法未被调?        self.assertFalse(write_file_mock.called)

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    @patch.object(ActualConfigHandler, "write_file")
    @patch.object(ActualConfigHandler, "read_file")
    def test_read_actual_component_inmemory(self, read_file_mock, write_file_mock):
        """测试内存缓存优化 - 验证配置访问的高效缓存机?""
        # 配置mock行为
        tags1 = {"global": "version1", "core-site": "version2"}
        read_file_mock.return_value = tags1
        
        # 创建配置对象并使用临时目?        config = cloudConfig().getConfig()
        tmpdir = tempfile.gettempdir()
        config.set("agent", "prefix", tmpdir)
        
        # 创建配置处理器并写入组件配置
        handler = ActualConfigHandler(config, {})
        handler.write_actual_component("NAMENODE", tags1)
        
        # 验证写文件方法被调用
        self.assertTrue(write_file_mock.called)
        
        # 读取已缓存的组件配置（直接从内存?        self.assertEqual(tags1, handler.read_actual_component("NAMENODE"))
        self.assertFalse(read_file_mock.called)
        
        # 读取未缓存组件配置（需要从文件读取?        self.assertEqual(tags1, handler.read_actual_component("DATANODE"))
        self.assertTrue(read_file_mock.called)
        self.assertEqual(1, read_file_mock.call_count)
        
        # 再次读取相同组件（使用缓存）
        self.assertEqual(tags1, handler.read_actual_component("DATANODE"))
        self.assertEqual(1, read_file_mock.call_count)  # 调用次数未增?
