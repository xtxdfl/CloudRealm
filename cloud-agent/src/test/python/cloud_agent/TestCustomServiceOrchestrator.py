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
import tempfile
import unittest
import threading
from unittest.mock import MagicMock, patch, call
import configparser
from multiprocessing.pool import ThreadPool
import json

from cloud_agent.CustomServiceOrchestrator import CustomServiceOrchestrator
from cloud_agent.BackgroundCommandExecutionHandle import BackgroundCommandExecutionHandle
from cloud_agent.models.commands import CommandStatus
from cloud_agent.cloudConfig import cloudConfig
from cloud_agent.FileCache import FileCache
from cloud_agent.PythonExecutor import PythonExecutor
from cloud_agent.InitializerModule import InitializerModule
from cloud_agent.ConfigurationBuilder import ConfigurationBuilder
from cloud_commons import OSCheck, shell
from cloud_agent.ActionQueue import ActionQueue
from cloud_agent.AgentException import AgentException
from cloud_commons.shell import kill_process_with_children


class CustomServiceOrchestratorTestBase(unittest.TestCase):
    """自定义服务编排器测试基类，提供通用工具方法"""
    
    def setUp(self):
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 初始化基本配�?        self.config = cloudConfig()
        self.config.add_section("agent")
        self.config.set("agent", "prefix", self.temp_dir)
        self.config.set("agent", "cache_dir", os.path.join(self.temp_dir, "cache"))
        self.config.add_section("python")
        self.config.set("python", "custom_actions_dir", os.path.join(self.temp_dir, "custom_actions"))
        
        # 初始化初始器模块
        self.initializer_module = InitializerModule()
        self.initializer_module.config = self.config
        self.initializer_module.init()
        
        # 创建编排器实�?        self.orchestrator = CustomServiceOrchestrator(self.initializer_module)
        
        # 模拟文件缓存
        self.orchestrator.file_cache = MagicMock()
        
        # 设置OS模拟
        self.os_distribution_patcher = patch.object(
            OSCheck, "os_distribution", return_value={'os_type': 'linux', 'os_family': 'ubuntu'}
        )
        self.os_distribution_patcher.start()
    
    def tearDown(self):
        # 清理补丁
        self.os_distribution_patcher.stop()
    
    def create_execution_command(self, **overrides):
        """创建标准的执行命令模�?""
        command = {
            "commandType": "EXECUTION_COMMAND",
            "role": "DATANODE",
            "roleCommand": "INSTALL",
            "commandId": "1-1",
            "taskId": "3",
            "clusterName": "test_cluster",
            "serviceName": "HDFS",
            "configurations": {"global": {"param1": "value1"}},
            "configurationTags": {"global": {"tag": "v1"}},
            "clusterHostInfo": {
                "all_hosts": ["host1", "host2"],
                "cloud_server_host": "server.example.com",
                "cloud_server_port": "8080"
            },
            "hostLevelParams": {},
            "commandParams": {
                "script_type": "PYTHON",
                "script": "scripts/hbase_master.py",
                "command_timeout": "600",
                "service_package_folder": "HBASE",
            }
        }
        command.update(overrides)
        return command
    
    def create_status_command(self, **overrides):
        """创建状态检查命令模�?""
        command = self.create_execution_command(**overrides)
        command["commandType"] = "STATUS_COMMAND"
        command["componentName"] = "DATANODE"
        return command
    
    def create_custom_action_command(self, **overrides):
        """创建自定义动作命令模�?""
        command = self.create_execution_command(**overrides)
        command["roleCommand"] = "ACTIONEXECUTE"
        command["commandParams"]["script"] = "custom_action.py"
        return command
    
    def create_background_command(self, **overrides):
        """创建后台执行命令模板"""
        command = self.create_execution_command(**overrides)
        command["commandType"] = "BACKGROUND_EXECUTION_COMMAND"
        command["__handle"] = BackgroundCommandExecutionHandle(command, 123, MagicMock(), MagicMock())
        return command
    
    @staticmethod
    def mock_python_executor(result=None):
        """创建一个模拟的Python执行�?""
        executor = MagicMock(spec=PythonExecutor)
        
        if result is None:
            result = {
                "stdout": "Execution successful",
                "stderr": "",
                "exitcode": 0,
                "structuredOut": "{}"
            }
        
        executor.run_file.return_value = result
        return executor


class CommandDispatchTests(CustomServiceOrchestratorTestBase):
    """测试命令分发功能"""
    
    def test_dump_command_to_json(self):
        """测试命令转储到JSON文件"""
        command = self.create_execution_command()
        
        with patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("os.chmod") as chmod_mock:
            
            # 执行命令转储
            json_path = self.orchestrator.dump_command_to_json(command)
            
            # 验证文件创建
            self.assertTrue(os.path.exists(json_path), "JSON文件未创�?)
            self.assertTrue(json_path.endswith(f"command-{command['taskId']}.json"))
            
            # 验证文件权限
            chmod_mock.assert_called_with(json_path, 0o600)
            
            # 验证文件内容
            with open(json_path, 'r') as f:
                loaded = json.load(f)
                self.assertEqual(loaded["serviceName"], command["serviceName"])
    
    @patch("os.path.exists", return_value=True)
    def test_resolve_script_path(self, exists_mock):
        """测试脚本路径解析"""
        # 模拟服务基础目录
        service_base_dir = os.path.join(self.temp_dir, "HBASE")
        self.orchestrator.file_cache.get_service_base_dir.return_value = service_base_dir
        
        # 创建脚本文件
        script_path = os.path.join(service_base_dir, "scripts", "hbase_master.py")
        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        open(script_path, 'w').close()
        
        # 解析路径
        resolved = self.orchestrator.resolve_script_path(
            service_base_dir, "scripts/hbase_master.py"
        )
        
        self.assertEqual(resolved, script_path)
    
    @patch("os.path.exists", return_value=False)
    def test_resolve_script_path_not_found(self, exists_mock):
        """测试脚本路径解析失败"""
        with self.assertRaises(AgentException):
            self.orchestrator.resolve_script_path(
                self.temp_dir, "scripts/missing_script.py"
            )


class ExecutionFunctionalityTests(CustomServiceOrchestratorTestBase):
    """测试执行功能"""
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    @patch.object(CustomServiceOrchestrator, "resolve_script_path")
    @patch.object(CustomServiceOrchestrator, "resolve_hook_script_path")
    @patch.object(CustomServiceOrchestrator, "dump_command_to_json")
    def test_normal_execution(
        self, dump_mock, resolve_hook_mock, resolve_script_mock, 
        get_executor_mock, get_config_mock
    ):
        """测试正常执行流程"""
        # 准备模拟数据
        command = self.create_execution_command()
        get_config_mock.return_value = command
        resolve_script_mock.return_value = os.path.join(self.temp_dir, "script.py")
        resolve_hook_mock.return_value = (os.path.join(self.temp_dir, "hook.py"), os.path.join(self.temp_dir, "hook_dir"))
        
        # 准备模拟执行�?        executor_mock = self.mock_python_executor()
        get_executor_mock.return_value = executor_mock
        
        # 执行命令
        result = self.orchestrator.runCommand(
            command, 
            os.path.join(self.temp_dir, "out.txt"), 
            os.path.join(self.temp_dir, "err.txt")
        )
        
        # 验证执行结果
        self.assertEqual(result["exitcode"], 0)
        
        # 验证调用次数�?个主脚本 + 2个钩子）
        self.assertEqual(executor_mock.run_file.call_count, 3)
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    def test_status_command_execution(
        self, get_executor_mock, get_config_mock
    ):
        """测试状态命令执行流�?""
        # 准备模拟数据
        command = self.create_status_command()
        get_config_mock.return_value = command
        
        # 准备模拟执行�?        executor_mock = self.mock_python_executor()
        get_executor_mock.return_value = executor_mock
        
        # 执行命令
        result = self.orchestrator.runCommand(
            command, 
            os.path.join(self.temp_dir, "out.txt"), 
            os.path.join(self.temp_dir, "err.txt")
        )
        
        # 验证执行结果
        self.assertEqual(result["exitcode"], 0)
        
        # 状态命令只应调用一次（只执行主脚本�?        executor_mock.run_file.assert_called_once()
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    def test_custom_action_execution(
        self, get_executor_mock, get_config_mock
    ):
        """测试自定义动作执行流�?""
        # 准备模拟数据
        command = self.create_custom_action_command()
        get_config_mock.return_value = command
        
        # 准备模拟执行�?        executor_mock = self.mock_python_executor()
        get_executor_mock.return_value = executor_mock
        
        # 模拟自定义动作目�?        self.orchestrator.file_cache.get_custom_actions_base_dir.return_value = self.temp_dir
        
        # 执行命令
        result = self.orchestrator.runCommand(
            command, 
            os.path.join(self.temp_dir, "out.txt"), 
            os.path.join(self.temp_dir, "err.txt")
        )
        
        # 验证执行结果
        self.assertEqual(result["exitcode"], 0)
        
        # 自定义动作只应调用一�?        executor_mock.run_file.assert_called_once()
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    def test_unknown_script_type(
        self, get_executor_mock, get_config_mock
    ):
        """测试未知脚本类型处理"""
        # 准备模拟数据（无效的脚本类型�?        command = self.create_execution_command(
            commandParams={"script_type": "INVALID_TYPE"}
        )
        get_config_mock.return_value = command
        
        # 准备模拟执行�?        executor_mock = self.mock_python_executor()
        get_executor_mock.return_value = executor_mock
        
        # 执行命令
        result = self.orchestrator.runCommand(
            command, 
            os.path.join(self.temp_dir, "out.txt"), 
            os.path.join(self.temp_dir, "err.txt")
        )
        
        # 验证执行结果
        self.assertEqual(result["exitcode"], 1)
        self.assertIn("Unknown script type", result["stdout"])
        
        # 不应尝试执行
        executor_mock.run_file.assert_not_called()


class CancellationFunctionalityTests(CustomServiceOrchestratorTestBase):
    """测试命令取消功能"""
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    @patch("cloud_commons.shell.kill_process_with_children")
    def test_foreground_command_cancellation(
        self, kill_mock, get_executor_mock, get_config_mock
    ):
        """测试前台命令取消功能"""
        # 准备模拟数据
        command = self.create_execution_command()
        get_config_mock.return_value = command
        
        # 创建长时间运行的模拟执行�?        executor_mock = self.mock_python_executor()
        
        def delayed_executor(*args, **kwargs):
            time.sleep(2)  # 模拟长时间运�?            return {"exitcode": 0}
        
        executor_mock.run_file.side_effect = delayed_executor
        get_executor_mock.return_value = executor_mock
        
        # 注册命令
        self.orchestrator.commands_in_progress[command["taskId"]] = 1024
        
        # 在后台执行命�?        def execute_command():
            return self.orchestrator.runCommand(
                command, 
                os.path.join(self.temp_dir, "out.txt"), 
                os.path.join(self.temp_dir, "err.txt")
            )
        
        pool = ThreadPool(processes=1)
        async_result = pool.apply_async(execute_command)
        
        # 等待命令开�?        time.sleep(0.2)
        
        # 取消命令
        self.orchestrator.cancel_command(command["taskId"], "Test cancellation")
        
        # 获取结果
        result = async_result.get()
        
        # 验证取消结果
        self.assertEqual(result["exitcode"], 1)
        self.assertIn("Command aborted. Reason: 'Test cancellation'", result["stdout"])
        
        # 验证进程终止调用
        kill_mock.assert_called_with(1024)
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    @patch("cloud_commons.shell.kill_process_with_children")
    def test_background_command_cancellation(
        self, kill_mock, get_executor_mock, get_config_mock
    ):
        """测试后台命令取消功能"""
        # 准备模拟数据
        command = self.create_background_command()
        get_config_mock.return_value = command
        
        # 创建模拟执行�?        executor_mock = self.mock_python_executor()
        
        def background_executor(*args, **kwargs):
            # 模拟在后台运行的进程
            kwargs['background_execution'] = True
            return {"exitcode": 0}
        
        executor_mock.run_file.side_effect = background_executor
        get_executor_mock.return_value = executor_mock
        
        # 初始化动作队�?        action_queue = ActionQueue(self.initializer_module)
        action_queue.customServiceOrchestrator = self.orchestrator
        command["__handle"].action_queue = action_queue
        
        # 在后台执行命�?        self.orchestrator.runCommand(
            command, 
            os.path.join(self.temp_dir, "out.txt"), 
            os.path.join(self.temp_dir, "err.txt")
        )
        
        time.sleep(0.1)  # 确保命令开始执�?        
        # 取消命令
        self.orchestrator.cancel_command(command["taskId"], "Background cancellation")
        
        # 验证进程终止调用
        kill_mock.assert_called()


class HookScriptTests(CustomServiceOrchestratorTestBase):
    """测试钩子脚本功能"""
    
    @patch("os.path.exists")
    def test_resolve_hook_script_path_exists(self, exists_mock):
        """测试钩子脚本路径解析（存在）"""
        exists_mock.return_value = True
        
        hook_path, hook_dir = self.orchestrator.resolve_hook_script_path(
            "/hooks_dir", "BEFORE", "INSTALL", "PYTHON"
        )
        
        expected_path = os.path.join("/hooks_dir", "BEFORE-INSTALL", "scripts", "hook.py")
        expected_dir = os.path.join("/hooks_dir", "BEFORE-INSTALL")
        
        self.assertEqual(hook_path, expected_path)
        self.assertEqual(hook_dir, expected_dir)
    
    @patch("os.path.exists")
    def test_resolve_hook_script_path_not_exists(self, exists_mock):
        """测试钩子脚本路径解析（不存在�?""
        exists_mock.return_value = False
        
        result = self.orchestrator.resolve_hook_script_path(
            "/hooks_dir", "BEFORE", "INSTALL", "PYTHON"
        )
        
        self.assertIsNone(result)
    
    @patch.object(ConfigurationBuilder, "get_configuration")
    @patch.object(CustomServiceOrchestrator, "get_py_executor")
    @patch.object(CustomServiceOrchestrator, "resolve_hook_script_path")
    def test_hook_execution(
        self, resolve_hook_mock, get_executor_mock, get_config_mock
    ):
        """测试钩子脚本执行流程"""
        # 准备模拟数据
        command = self.create_execution_command()
        get_config_mock.return_value = command
        
        # 设置钩子脚本
        hook_mock_path = os.path.join(self.temp_dir, "hook.py")
        resolve_hook_mock.return_value = (hook_mock_path, os.path.dirname(hook_mock_path))
        
        # 准备模拟执行�?        executor_mock = self.mock_python_executor()
        get_executor_mock.return_value = executor_mock
        
        # 执行命令
        self.orchestrator.runCommand(
            command, 
            os.path.join(self.temp_dir, "out.txt"), 
            os.path.join(self.temp_dir, "err.txt")
        )
        
        # 验证钩子脚本调用
        self.assertEqual(executor_mock.run_file.call_count, 3)  # 主脚�?+ 两个钩子脚本


class ComponentStatusTests(CustomServiceOrchestratorTestBase):
    """测试组件状态功�?""
    
    @patch.object(CustomServiceOrchestrator, "runCommand")
    def test_request_component_status_alive(self, run_command_mock):
        """测试存活组件状态请�?""
        # 准备模拟数据
        status_command = self.create_status_command()
        
        # 设置状态为活着
        run_command_mock.return_value = {"exitcode": 0, "status": "LIVE"}
        
        # 请求状�?        result = self.orchestrator.requestComponentStatus(status_command)
        
        # 验证结果
        self.assertEqual(result["exitcode"], 0)
        self.assertTrue("LIVE" in result["status"])
    
    @patch.object(CustomServiceOrchestrator, "runCommand")
    def test_request_component_status_dead(self, run_command_mock):
        """测试死亡组件状态请�?""
        # 准备模拟数据
        status_command = self.create_status_command()
        
        # 设置状态为死亡
        run_command_mock.return_value = {"exitcode": 1, "status": "DEAD"}
        
        # 请求状�?        result = self.orchestrator.requestComponentStatus(status_command)
        
        # 验证结果
        self.assertEqual(result["exitcode"], 1)
        self.assertTrue("DEAD" in result["status"])


if __name__ == "__main__":
    unittest.main()

