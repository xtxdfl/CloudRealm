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

from mock.mock import MagicMock, patch
from unittest import TestCase

from ConfigurationBuilder import ConfigurationBuilder
from InitializerModule import InitializerModule


class TestConfigurationBuilder(TestCase):
    """单元测试：验证ConfigurationBuilder的公共FQDN获取功能"""
    
    # 通过patch装饰器模拟public_hostname函数
    @patch(
        "cloud_agent.hostname.public_hostname",
        new=MagicMock(return_value="c6401.cloud.apache.org"),
    )
    def test_public_fqdn(self):
        """
        测试ConfigurationBuilder的public_fqdn属?        - 验证是否正确获取公共FQDN
        - 测试与主机名解析模块的集?        """
        # 创建InitializerModule实例（配置初始化依赖?        initializer_module = InitializerModule()
        
        # 实例化被测试对象
        config_builder = ConfigurationBuilder(initializer_module)
        
        # 验证public_fqdn属性的返回?        self.assertEqual(
            "c6401.cloud.apache.org",  # 预期的FQDN?            config_builder.public_fqdn    # 实际从ConfigurationBuilder获取的?        )
