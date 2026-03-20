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
import unittest
import tempfile
from unittest.mock import MagicMock, patch, create_autospec

# 模块导入
from cloud_agent.models.hooks import HookPrefix
from cloud_agent.CommandHooksOrchestrator import (
    HookSequenceBuilder,
    ResolvedHooks,
    HooksOrchestrator,
    HOOK_FILE_EXTENSION
)

class CommandHooksTestBase(unittest.TestCase):
    """命令钩子系统测试基类，提供通用工具方法"""
    
    def setUp(self):
        """创建测试环境"""
        # 创建临时钩子目录
        self.hooks_dir = tempfile.mkdtemp(prefix="cloud_hooks_test_")
        self._create_hook_files()
        
        # 创建文件缓存模拟�?        self.file_cache = MagicMock()
        self.file_cache.get_hook_base_dir.return_value = self.hooks_dir
        self.injector = create_autospec(object)
        self.injector.file_cache = self.file_cache
        
        # 初始化钩子编排器
        self.orchestrator = HooksOrchestrator(self.injector)
    
    def tearDown(self):
        """清理测试环境"""
        # 移除临时目录
        if os.path.exists(self.hooks_dir):
            os.system(f"rm -rf {self.hooks_dir}")
    
    def _create_hook_files(self):
        """创建测试钩子文件"""
        # 创建预启动钩�?        self._create_hook_file("pre-start-script1", HookPrefix.PRE, "START", scope="any")
        self._create_hook_file("pre-start-script2", HookPrefix.PRE, "START", service="ZOOKEEPER")
        self._create_hook_file("pre-start-script3", HookPrefix.PRE, "START", service="ZOOKEEPER", role="SERVER")
        
        # 创建后启动钩�?        self._create_hook_file("post-start-script1", HookPrefix.POST, "START", scope="any")
        self._create_hook_file("post-start-script2", HookPrefix.POST, "START", service="ZOOKEEPER")
        self._create_hook_file("post-start-script3", HookPrefix.POST, "START", service="ZOOKEEPER", role="SERVER")
        
        # 创建服务特定钩子
        self._create_hook_file("pre-hdfs-install", HookPrefix.PRE, "INSTALL", service="HDFS")
        self._create_hook_file("post-kafka-configure", HookPrefix.POST, "CONFIGURE", service="KAFKA")
        
        # 创建角色特定钩子
        self._create_hook_file("pre-yarn-resourcemanager-command", HookPrefix.PRE, "COMMAND", service="YARN", role="RESOURCEMANAGER")
    
    def _create_hook_file(self, script_name, prefix, command, service="GENERAL", role=None, scope=None):
        """创建单个钩子文件"""
        # 构建文件�?        filename_parts = [prefix.value]
        if scope:
            filename_parts.append(scope)
        elif service and role:
            filename_parts.extend([command, service, role])
        elif service:
            filename_parts.extend([command, service])
        else:
            filename_parts.append(command)
        
        filename = "-".join(filename_parts) + HOOK_FILE_EXTENSION
        filepath = os.path.join(self.hooks_dir, filename)
        
        # 创建文件
        with open(filepath, 'w') as f:
            f.write(f"#!/bin/sh\necho 'Running {script_name}'")


class HookSequenceBuilderTests(CommandHooksTestBase):
    """测试钩子序列构建器功�?""
    
    def test_sequence_generation(self):
        """测试钩子序列生成逻辑"""
        # 测试前置钩子序列
        pre_sequence = list(
            HookSequenceBuilder().build(
                HookPrefix.PRE, 
                command="START", 
                service="ZOOKEEPER", 
                role="SERVER"
            )
        )
        expected_pre_sequence = [
            "pre-start-GENERAL",  # 全局钩子
            "pre-start-ZOOKEEPER",  # 服务级别钩子
            "pre-start-ZOOKEEPER-SERVER"  # 具体角色钩子
        ]
        self.assertEqual(pre_sequence, expected_pre_sequence)
        
        # 测试后置钩子序列
        post_sequence = list(
            HookSequenceBuilder().build(
                HookPrefix.POST, 
                command="INSTALL", 
                service="HDFS", 
                role="NAMENODE"
            )
        )
        expected_post_sequence = [
            "post-install-HDFS-NAMENODE",  # 具体角色钩子 (倒序)
            "post-install-HDFS",  # 服务级别钩子 (倒序)
            "post-install-GENERAL"  # 全局钩子 (倒序)
        ]
        self.assertEqual(post_sequence, expected_post_sequence)
    
    def test_sequence_boundary_cases(self):
        """测试边界条件下的序列生成"""
        # 缺少服务名称
        sequence = list(
            HookSequenceBuilder().build(
                HookPrefix.PRE, 
                command="START", 
                service=None, 
                role="SERVER"
            )
        )
        expected = ["pre-start"]
        self.assertEqual(sequence, expected)
        
        # 缺少角色名称
        sequence = list(
            HookSequenceBuilder().build(
                HookPrefix.PRE, 
                command="STOP", 
                service="HDFS"
            )
        )
        expected = ["pre-stop-HDFS"]
        self.assertEqual(sequence, expected)
        
        # 缺少所有参�?        sequence = list(
            HookSequenceBuilder().build(
                HookPrefix.POST, 
                command=None
            )
        )
        expected = ["post"]
        self.assertEqual(sequence, expected)


class HooksResolutionTests(CommandHooksTestBase):
    """测试钩子解析功能"""
    
    def test_single_component_hooks(self):
        """测试组件特定钩子解析"""
        # 解析HDFS组件的INSTALL命令钩子
        resolved = self.orchestrator.resolve_hooks(
            {
                "commandType": "INSTALL",
                "serviceName": "HDFS",
                "role": "DATANODE"
            },
            "INSTALL"
        )
        
        # 验证钩子文件
        self.assertEqual(len(resolved.pre_hooks), 1)
        self.assertIn("pre-install-HDFS", resolved.pre_hooks[0])
        self.assertEqual(len(resolved.post_hooks), 0)
    
    def test_multi_component_hooks(self):
        """测试多组件钩子解�?""
        # 解析ZOOKEEPER服务的START命令钩子
        resolved = self.orchestrator.resolve_hooks(
            {
                "commandType": "START",
                "serviceName": "ZOOKEEPER",
                "role": "SERVER"
            },
            "START"
        )
        
        # 验证前钩�?        self.assertSequenceEqual(
            [os.path.basename(p) for p in resolved.pre_hooks],
            ["pre-start-GENERAL.sh", "pre-start-ZOOKEEPER.sh", "pre-start-ZOOKEEPER-SERVER.sh"]
        )
        
        # 验证后钩�?        self.assertSequenceEqual(
            [os.path.basename(p) for p in resolved.post_hooks],
            ["post-start-ZOOKEEPER-SERVER.sh", "post-start-ZOOKEEPER.sh", "post-start-GENERAL.sh"]
        )
    
    def test_nonexistent_hooks(self):
        """测试不存在的钩子处理"""
        # 尝试解析不存在的服务钩子
        resolved = self.orchestrator.resolve_hooks(
            {
                "commandType": "CONFIGURE",
                "serviceName": "cloud",
                "role": "METRICS"
            },
            "CONFIGURE"
        )
        
        self.assertEqual(len(resolved.pre_hooks), 0)
        self.assertEqual(len(resolved.post_hooks), 0)
    
    def test_command_specialization(self):
        """测试特定命令的钩子解�?""
        # 解析YARN服务RESOURCEMANAGER角色的COMMAND命令
        resolved = self.orchestrator.resolve_hooks(
            {
                "commandType": "COMMAND",
                "serviceName": "YARN",
                "role": "RESOURCEMANAGER"
            },
            "COMMAND"
        )
        
        self.assertEqual(len(resolved.pre_hooks), 1)
        self.assertIn("pre-command-YARN-RESOURCEMANAGER.sh", resolved.pre_hooks[0])


class ResolvedHooksTests(unittest.TestCase):
    """测试解析后的钩子对象功能"""
    
    def test_hook_collection(self):
        """测试钩子收集功能"""
        # 创建虚拟钩子列表
        pre_hooks = [f"pre-hook-{i}" for i in range(1, 4)]
        post_hooks = [f"post-hook-{i}" for i in range(1, 3)]
        
        # 创建解析对象
        resolved = ResolvedHooks(pre_hooks, post_hooks)
        
        # 验证属�?        self.assertEqual(resolved.pre_hooks, pre_hooks)
        self.assertEqual(resolved.post_hooks, post_hooks)
        self.assertEqual(len(resolved), len(pre_hooks) + len(post_hooks))
    
    def test_empty_hooks(self):
        """测试空钩子集�?""
        resolved = ResolvedHooks([], [])
        self.assertEqual(len(resolved.pre_hooks), 0)
        self.assertEqual(len(resolved.post_hooks), 0)
        self.assertEqual(len(resolved), 0)


class HookExecutionTests(CommandHooksTestBase):
    """测试钩子执行功能"""
    
    @patch("subprocess.Popen")
    @patch("cloud_agent.security.FileHelper")
    @patch("os.path.exists", return_value=True)
    @patch("os.access", return_value=True)
    def test_hook_execution(self, access_mock, exists_mock, file_helper_mock, popen_mock):
        """测试钩子执行流程"""
        # 准备钩子列表
        hook1 = os.path.join(self.hooks_dir, "pre-start-GENERAL.sh")
        hook2 = os.path.join(self.hooks_dir, "pre-start-ZOOKEEPER.sh")
        
        # 模拟钩子执行过程
        process_mock = MagicMock()
        process_mock.poll.return_value = None
        process_mock.wait.return_value = 0
        popen_mock.return_value = process_mock
        
        # 执行钩子
        self.orchestrator.execute_hooks([hook1, hook2])
        
        # 验证执行顺序
        self.assertEqual(popen_mock.call_count, 2)
        self.assertEqual(
            popen_mock.call_args_list[0][0][0],
            [hook1]
        )
        self.assertEqual(
            popen_mock.call_args_list[1][0][0],
            [hook2]
        )
    
    @patch("subprocess.Popen")
    @patch("cloud_agent.security.FileHelper")
    @patch("os.path.exists", return_value=False)
    def test_invalid_hook_execution(self, exists_mock, file_helper_mock, popen_mock):
        """测试无效钩子处理"""
        # 尝试执行不存在的钩子
        self.orchestrator.execute_hooks(["/invalid/path.sh"])
        
        # 验证未尝试执�?        self.assertEqual(popen_mock.call_count, 0)
    
    @patch("subprocess.Popen")
    @patch("cloud_agent.security.FileHelper")
    @patch("os.path.exists", return_value=True)
    @patch("os.access", return_value=False)  # 无执行权�?    def test_non_executable_hooks(self, access_mock, exists_mock, file_helper_mock, popen_mock):
        """测试无执行权限的钩子处理"""
        # 尝试执行钩子
        hook = os.path.join(self.hooks_dir, "pre-start-GENERAL.sh")
        self.orchestrator.execute_hooks([hook])
        
        # 验证未尝试执�?        self.assertEqual(popen_mock.call_count, 0)


if __name__ == "__main__":
    unittest.main()
