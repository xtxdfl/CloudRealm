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
from cloud_agent.cloudConfig import cloudConfig
import os
import tempfile
import configparser


class cloudConfigTests(unittest.TestCase):
    """cloud配置类测试套�?""
    
    def setUp(self):
        # 创建临时配置文件
        self.config_file = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
        self.config_file.write("""# 
[security]
keysdir = /var/lib/security/keys
authentication = pam

[agent]
command_file_retention_policy = remove_on_success
ulimit_open_files = 4096
        """)
        self.config_file.flush()
    
    def tearDown(self):
        # 关闭并删除临时文�?        self.config_file.close()
        os.unlink(self.config_file.name)
    
    def test_config_file_parsing(self):
        """测试配置文件解析功能"""
        config = cloudConfig()
        config.read(self.config_file.name)
        
        # 验证解析的配置项
        self.assertEqual(config.get('security', 'keysdir'), '/var/lib/security/keys')
        self.assertEqual(config.get('security', 'authentication'), 'pam')
    
    def test_default_values(self):
        """测试默认配置�?""
        config = cloudConfig()
        
        # 默认值检�?        self.assertEqual(config.get('security', 'keysdir'), '/tmp/cloud-agent')
        self.assertEqual(config.get('logging', 'log_dir', fallback='not_defined'), 'not_defined')
    
    def test_set_and_get(self):
        """测试配置项设置与获取"""
        config = cloudConfig()
        
        # 测试基本设置
        config.set('network', 'port', '9000')
        self.assertEqual(config.get('network', 'port'), '9000')
        
        # 测试值覆�?        config.set('network', 'port', '9001')
        self.assertEqual(config.get('network', 'port'), '9001')
        
        # 测试默认�?        self.assertEqual(config.get('network', 'ssl_enabled', fallback=False), False)
    
    def test_whitespace_handling(self):
        """测试空格处理"""
        config = cloudConfig()
        
        # 测试前导/尾随空格
        config.set('security', 'key_path', ' /path/with/spaces/ ')
        self.assertEqual(config.get('security', 'key_path'), '/path/with/spaces/')
        
        # 测试字符串中间空�?        config.set('security', 'algorithm', ' RSA 4096 ')
        self.assertEqual(config.get('security', 'algorithm'), 'RSA 4096')
    
    def test_ulimit_handling(self):
        """测试打开文件限制处理"""
        config = cloudConfig()
        
        # 默认值测�?        self.assertEqual(config.get_ulimit_open_files(), 0)
        
        # 有效值设�?        config.set_ulimit_open_files(8192)
        self.assertEqual(config.get_ulimit_open_files(), 8192)
        
        # 无效值处�?        config.set('agent', 'ulimit_open_files', 'invalid')
        self.assertEqual(config.get_ulimit_open_files(), 0)
    
    def test_command_file_retention_policies(self):
        """测试命令文件保留策略"""
        config = cloudConfig()
        
        # 默认策略
        self.assertEqual(
            config.command_file_retention_policy,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_KEEP
        )
        
        # keep策略测试
        config.set(
            'agent',
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_PROPERTY,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_KEEP
        )
        self.assertEqual(
            config.command_file_retention_policy,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_KEEP
        )
        
        # remove策略测试
        config.set(
            'agent',
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_PROPERTY,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_REMOVE
        )
        self.assertEqual(
            config.command_file_retention_policy,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_REMOVE
        )
        
        # remove_on_success策略测试
        config.set(
            'agent',
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_PROPERTY,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_REMOVE_ON_SUCCESS
        )
        self.assertEqual(
            config.command_file_retention_policy,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_REMOVE_ON_SUCCESS
        )
        
        # 无效策略处理
        config.set(
            'agent',
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_PROPERTY,
            'invalid_policy'
        )
        self.assertEqual(
            config.command_file_retention_policy,
            cloudConfig.COMMAND_FILE_RETENTION_POLICY_KEEP
        )
    
    def test_special_characters(self):
        """测试特殊字符处理"""
        config = cloudConfig()
        
        # URL测试
        url = "https://example.com/path?query=param&value=test"
        config.set('api', 'endpoint', url)
        self.assertEqual(config.get('api', 'endpoint'), url)
        
        # 特殊路径测试
        path = "/var/lib/$app/#data/!important/"
        config.set('storage', 'path', path)
        self.assertEqual(config.get('storage', 'path'), path)
    
    def test_file_saving(self):
        """测试配置保存功能"""
        config = cloudConfig()
        
        # 添加配置�?        config.set('security', 'encryption', 'AES-256')
        config.set('network', 'timeout', '30')
        
        # 保存到临时文�?        temp_file = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
        with open(temp_file.name, 'w') as f:
            config.write(f)
        
        # 重新读取验证
        config_check = cloudConfig()
        config_check.read(temp_file.name)
        self.assertEqual(config_check.get('security', 'encryption'), 'AES-256')
        self.assertEqual(config_check.get('network', 'timeout'), '30')
        
        # 清理
        temp_file.close()
        os.unlink(temp_file.name)


class AdvancedConfigTests(unittest.TestCase):
    """高级配置功能测试"""
    
    def test_environment_variables(self):
        """测试环境变量配置"""
        # 配置对象
        config = cloudConfig()
        
        # 设置环境变量
        os.environ['SHRPD_AGENT_PORT'] = '9000'
        os.environ['SHRPD_AGENT_LOGGING_LEVEL'] = 'debug'
        
        # 环境变量解析测试
        self.assertEqual(config.get('agent', 'port', fallback=''), '9000')
        self.assertEqual(config.get('logging', 'level', fallback=''), 'debug')
        
        # 环境变量优先级测�?        config.set('agent', 'port', '8000')
        self.assertEqual(config.get('agent', 'port'), '8000')  # 配置文件值应覆盖环境变量
    
    def test_multiple_config_files(self):
        """测试多配置文件加�?""
        # 创建主配置文�?        main_file = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
        main_file.write("""
[security]
keysdir = /etc/main/keys
timeout = 30
        """)
        main_file.close()
        
        # 创建覆盖配置文件
        override_file = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
        override_file.write("""
[security]
keysdir = /etc/override/keys
authentication = ldap
        """)
        override_file.close()
        
        # 加载配置文件
        config = cloudConfig()
        config.read([main_file.name, override_file.name])
        
        # 验证覆盖行为
        self.assertEqual(config.get('security', 'keysdir'), '/etc/override/keys')
        self.assertEqual(config.get('security', 'authentication'), 'ldap')
        self.assertEqual(config.get('security', 'timeout'), '30')
        
        # 清理
        os.unlink(main_file.name)
        os.unlink(override_file.name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
