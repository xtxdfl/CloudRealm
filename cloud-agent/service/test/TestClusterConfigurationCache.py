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

import os
import sys
from ClusterConfigurationCache import ClusterConfigurationCache  # 导入集群配置缓存模块
from mock.mock import MagicMock, patch, ANY  # 导入测试模拟工具
from unittest import TestCase  # 导入测试基类


class TestClusterConfigurationCache(TestCase):
    """单元测试类：验证集群配置缓存功能完整?""
    
    # 文件操作常量
    o_flags = os.O_WRONLY | os.O_CREAT  # 文件打开标志
    perms = 0o600  # 文件权限设置

    def setUp(self):
        """准备测试环境：保存原始open函数"""
        self.original_open = open  # 保存原始open函数

    def tearDown(self):
        """清理测试环境：恢复标准输?""
        sys.stdout = sys.__stdout__

    @patch("json.load")
    @patch("os.path.exists", new=MagicMock(return_value=True))
    @patch("os.path.isfile", new=MagicMock(return_value=True))
    def test_cluster_configuration_cache_initialization(self, json_load_mock):
        """测试配置缓存初始?- 验证缓存文件到内存的加载机制"""
        # 创建模拟配置数据
        configuration_json = {"0": {"foo-site": {"foo": "bar", "foobar": "baz"}}}
        json_load_mock.return_value = configuration_json
        
        # 创建配置缓存实例
        cache_file_path = os.path.join(os.sep, "tmp", "bar", "baz")
        cluster_configuration = ClusterConfigurationCache(cache_file_path)
        
        # 更新并验证缓存内?        cluster_configuration.rewrite_cache(configuration_json, "abc")
        self.assertEqual("bar", cluster_configuration["0"]["foo-site"]["foo"])
        self.assertEqual("baz", cluster_configuration["0"]["foo-site"]["foobar"])

    @patch("cloud_simplejson.dump")
    def test_cluster_configuration_update(self, json_dump_mock):
        """测试配置缓存更新 - 验证内容更新和持久化功能"""
        # 获取配置缓存实例
        cluster_configuration = self._get_cluster_configuration()
        
        # 创建新配置数?        new_configuration = {"foo-site": {"bar": "rendered-bar", "baz": "rendered-baz"}}
        
        # 更新配置缓存
        osopen_mock, osfdopen_mock = self._update_cluster_configuration(
            cluster_configuration, new_configuration
        )
        
        # 验证JSON持久化调?        json_dump_mock.assert_called_with(
            {"0": {"foo-site": {"baz": "rendered-baz", "bar": "rendered-bar"}}}, 
            ANY,  # 验证任何文件对象
            indent=2  # 验证缩进格式
        )

    def _get_cluster_configuration(self):
        """辅助方法：创建带模拟文件操作的配置缓存实?""
        # 模拟open函数行为
        with patch("builtins.open") as open_mock:
            open_mock.side_effect = self._open_side_effect
            # 创建配置缓存实例
            return ClusterConfigurationCache(os.path.join(os.sep, "tmp", "bar", "baz"))

    @patch("os.open")
    @patch("os.fdopen")
    def _update_cluster_configuration(
        self, cluster_configuration, configuration, osfdopen_mock, osopen_mock
    ):
        """辅助方法：模拟更新配置缓存的操作过程"""
        # 设置文件描述符操作模?        osopen_mock.return_value = 11
        # 执行缓存更新
        cluster_configuration.rewrite_cache({"0": configuration}, "test-hash")
        
        return osopen_mock, osfdopen_mock

    def _open_side_effect(self, file, mode):
        """自定义open函数逻辑：模拟文件操作行?""
        if mode == "w":
            # 写模式返回模拟文件对?            return MagicMock()
        else:
            # 其他模式使用真实open函数
            return self.original_open(file, mode)
