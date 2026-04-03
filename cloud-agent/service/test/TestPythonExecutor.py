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
import re
import time
import unittest
import tempfile
import threading
import collections
from unittest.mock import MagicMock, patch, call
from PythonExecutor import PythonExecutor
from cloudConfig import cloudConfig
from cloud_commons import OSCheck
from cloud_commons.shell import kill_process_with_children

# 模拟子进程类
class MockSubprocess:
    """模拟Python子进程行为，用于测试"""
    
    def __init__(self, execution_time=0.1, exit_code=0, output="Test output"):
        self.returncode = None
        self.finished_event = threading.Event()
        self.should_terminate = threading.Event()
        self.output_emitted = False
        self.execution_time = execution_time
        self.expected_exit_code = exit_code
        self.output = output
        self.pid = 12345
        self.tmpout = None
        self.tmperr = None
        self.was_terminated = False
        self.started = False
        
    def communicate(self):
        """模拟子进程执行过?""
        self.started = True
        start_time = time.time()
        
        # 写入输出到临时文?        self._write_output(self.tmpout, f"{self.output}\n")
        self._write_output(self.tmperr, "Error stream\n")
        
        # 模拟执行时间
        while time.time() - start_time < self.execution_time:
            if self.should_terminate.is_set():
                self.was_terminated = True
                self.returncode = 137  # 模拟SIGKILL
                self.finished_event.set()
                return (b"", b"Process terminated")
            time.sleep(0.01)
        
        # 正常完成
        self.returncode = self.expected_exit_code
        self.finished_event.set()
        return (b"", b"")
    
    def terminate(self):
        """模拟终止子进?""
        if not self.finished_event.is_set():
            self.should_terminate.set()
    
    def _write_output(self, filepath, content):
        """将内容写入输出文?""
        if filepath and not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content)
    
    def wait(self):
        """等待进程完成"""
        if not self.finished_event.is_set():
            self.finished_event.wait()


class PythonExecutorTestBase(unittest.TestCase):
    """Python执行器测试基类，提供通用工具方法"""
    
    TEST_TIMEOUT = 5.0  # 整体测试超时
    
    @classmethod
    def setUpClass(cls):
        # 初始化测试目?        cls.test_dir = tempfile.mkdtemp(prefix="cloud_python_executor_")
        cls.config = cloudConfig()
        
    @classmethod
    def tearDownClass(cls):
        # 清理测试目录
        import shutil
        shutil.rmtree(cls.test_dir, ignore_errors=True)
    
    def setUp(self):
        # 创建测试Python脚本
        self.python_script = tempfile.mktemp(dir=self.test_dir, suffix=".py")
        with open(self.python_script, 'w') as f:
            f.write("#!/usr/bin/env python3\nprint('Script executed')")
        
        # 初始化执行器实例
        self.executor = PythonExecutor(self.test_dir, self.config)
        
        # 补丁OS依赖
        self.os_patch = patch.object(OSCheck, "os_distribution", return_value={'os_type': 'linux', 'os_family': 'debian'})
        self.os_patch.start()
        
    def tearDown(self):
        # 清理补丁
        self.os_patch.stop()
        # 重置模拟
        PythonExecutor.open_subprocess_files = MagicMock(return_value=("", ""))
    
    def _quick_run(self, executor, *args, **kwargs):
        """快速执行方法，封装多线程调用的复杂?""
        result_container = []
        
        def run_and_collect():
            try:
                result_container.append(executor.run_file(*args, **kwargs))
            except Exception as e:
                result_container.append(e)
        
        thread = threading.Thread(target=run_and_collect)
        thread.start()
        thread.join(timeout=self.TEST_TIMEOUT)
        
        if thread.is_alive():
            raise TimeoutError("Test execution timed out")
        
        return result_container[0]
    
    def _validate_output_files(self, out_file, err_file, structured_out_file):
        """验证输出文件的存在性和基本格式"""
        self.assertTrue(os.path.exists(out_file), "Stdout file not created")
        self.assertTrue(os.path.exists(err_file), "Stderr file not created")
        self.assertTrue(os.path.exists(structured_out_file), "Structured out file not created")
        
        # 验证输出文件内容
        with open(out_file, 'r') as f:
            self.assertNotEqual(len(f.read()), 0, "Stdout file is empty")
        
        with open(structured_out_file, 'r') as f:
            content = f.read()
            self.assertIn("{", content, "Structured out should contain JSON")
            self.assertIn("}", content, "Structured out should contain JSON")
        
        return True


class ExecutionTimeoutTests(PythonExecutorTestBase):
    """测试执行超时功能"""
    
    @patch("cloud_commons.shell.kill_process_with_children")
    def test_execution_timeout(self, kill_mock):
        """测试脚本超时被终止的流程"""
        # 准备脚本（耗时2秒，但设定超时为0.1秒）
        with open(self.python_script, 'w') as f:
            f.write("import time\ntime.sleep(2)\nprint('Done')")
        
        # 创建临时输出文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 设置kill模拟
        kill_mock.side_effect = lambda pid: True
        
        # 执行测试
        result = self._quick_run(
            self.executor,
            self.python_script,
            [self.python_script],
            tmpout,
            tmperr,
            0.1,  # 超时0.1?            tmpstruct,
            lambda: True,  # 回调函数
            "test-1"
        )
        
        # 验证执行结果
        self.assertEqual(result['exitcode'], 137)
        self.assertTrue(self.executor.python_process_has_been_killed)
        self.assertIn("killed due to timeout", result['stderr'])
        self.assertTrue(kill_mock.called)
    
    def test_no_timeout(self):
        """测试脚本在超时前正常完成"""
        # 创建临时输出文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行测试
        result = self._quick_run(
            self.executor,
            self.python_script,
            [self.python_script],
            tmpout,
            tmperr,
            10.0,  # 超时10?            tmpstruct,
            lambda: True,
            "test-2"
        )
        
        # 验证执行结果
        self.assertEqual(result['exitcode'], 0)
        self.assertFalse(self.executor.python_process_has_been_killed)
        self.assertIn("Script executed", result['stdout'])
        
        # 验证输出文件
        self._validate_output_files(tmpout, tmperr, tmpstruct)


class ExecutionControlTests(PythonExecutorTestBase):
    """测试执行控制功能"""
    
    def test_successful_execution(self):
        """测试脚本正常执行成功的流?""
        # 创建临时文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行并验?        result = self.executor.run_file(
            self.python_script,
            [self.python_script, "--test-arg"],
            tmpout,
            tmperr,
            10.0,
            tmpstruct,
            lambda: True,
            "test-3"
        )
        
        self.assertEqual(result['exitcode'], 0)
        self.assertEqual(result['stderr'], "")
        self.assertIn("Script executed", result['stdout'])
        self.assertEqual(result['structuredOut'], {})
        
        # 验证成功检测是否准?        self.assertTrue(self.executor.is_successful(result['exitcode']))
    
    def test_failed_execution(self):
        """测试脚本执行失败的流?""
        # 创建失败脚本
        with open(self.python_script, 'w') as f:
            f.write("#!/usr/bin/env python3\nimport sys\nprint('Error'); sys.exit(1)")
        
        # 临时文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行并验?        result = self.executor.run_file(
            self.python_script,
            [self.python_script],
            tmpout,
            tmperr,
            10.0,
            tmpstruct,
            lambda: True,
            "test-4"
        )
        
        self.assertEqual(result['exitcode'], 1)
        self.assertIn("Error", result['stdout'])
        self.assertFalse(self.executor.is_successful(result['exitcode']))
    
    def test_callback_execution(self):
        """测试回调函数被正确调?""
        # 创建一个可追踪对象
        traceable = collections.namedtuple('Trace', 'called')(False)
        
        def callback():
            traceable.called = True
        
        # 临时文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行
        self.executor.run_file(
            self.python_script,
            [self.python_script],
            tmpout,
            tmperr,
            10.0,
            tmpstruct,
            callback,
            "test-5"
        )
        
        # 验证回调被调?        self.assertTrue(traceable.called)


class FileManagementTests(PythonExecutorTestBase):
    """测试文件管理功能"""
    
    def test_output_file_rotation(self):
        """测试输出文件轮转功能"""
        # 创建一系列测试文件
        log_dir = os.path.join(self.test_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        base_name = "output-123.txt"
        backup_files = []
        
        # 创建原始文件?个备?        for i in range(1, 5):
            file_path = os.path.join(log_dir, f"{base_name}.{i}" if i > 1 else base_name)
            with open(file_path, 'w') as f:
                f.write(f"Log content #{i}")
            backup_files.append(file_path)
        
        # 配置执行器日志目?        self.config.set('agent', 'log_dir', log_dir)
        executor = PythonExecutor(self.test_dir, self.config)
        
        # 执行备份操作
        main_file = os.path.join(log_dir, base_name)
        executor.back_up_log_file_if_exists(main_file)
        
        # 验证备份结果
        self.assertFalse(os.path.exists(main_file), "Original file should be renamed")
        
        # 检查备份文?        backups_exist = [
            os.path.exists(os.path.join(log_dir, f"{base_name}.{i}")) for i in range(1, 5)
        ]
        self.assertTrue(backups_exist[1], "First backup file should exist as .1")
        self.assertTrue(backups_exist[2], "Second backup file should exist as .2")
        self.assertTrue(backups_exist[3], "Third backup file should exist as .3")
        self.assertFalse(backups_exist[0], ".4 backup should have been removed")
    
    def test_output_file_creation(self):
        """测试输出文件被正确创?""
        out_file = os.path.join(self.test_dir, "test.out")
        err_file = os.path.join(self.test_dir, "test.err")
        struct_file = os.path.join(self.test_dir, "test.json")
        
        # 确保文件不存?        if os.path.exists(out_file):
            os.remove(out_file)
        if os.path.exists(err_file):
            os.remove(err_file)
        if os.path.exists(struct_file):
            os.remove(struct_file)
        
        # 执行脚本
        self.executor.run_file(
            self.python_script,
            [self.python_script],
            out_file,
            err_file,
            10.0,
            struct_file,
            lambda: True,
            "test-6"
        )
        
        # 验证文件创建和内?        self._validate_output_files(out_file, err_file, struct_file)


class CommandConstructionTests(PythonExecutorTestBase):
    """测试命令构建功能"""
    
    def test_python_command_construction(self):
        """测试Python命令的正确构?""
        # Windows系统
        with patch.object(OSCheck, "get_os_type", return_value="windows"):
            executor = PythonExecutor(self.test_dir, self.config)
            command = executor.python_command("script.py", ["arg1", "arg2"])
            self.assertIn("python", command[0].lower())
            self.assertEqual(command[1:], ["script.py", "arg1", "arg2"])
        
        # Linux系统
        with patch.object(OSCheck, "get_os_type", return_value="linux"):
            executor = PythonExecutor(self.test_dir, self.config)
            command = executor.python_command("/opt/scripts/main.py", ["--debug"])
            self.assertRegex(command[0], r'python\d*')
            self.assertEqual(command[1:], ["/opt/scripts/main.py", "--debug"])
    
    def test_command_logging(self):
        """测试命令日志记录功能"""
        # 创建补丁记录日志
        with patch("logging.info") as log_mock:
            # 执行脚本
            tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
            tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
            tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
            
            self.executor.run_file(
                "/path/to/custom.py",
                ["/path/to/custom.py", "--option", "value"],
                tmpout,
                tmperr,
                10.0,
                tmpstruct,
                None,
                "test-log"
            )
            
            # 验证日志调用
            self.assertTrue(log_mock.called)
            log_args = log_mock.call_args[0][0]
            self.assertIn("/path/to/custom.py", log_args)
            self.assertIn("--option", log_args)


class ErrorHandlingTests(PythonExecutorTestBase):
    """测试错误处理功能"""
    
    def test_missing_script(self):
        """测试脚本文件不存在的情况"""
        # 临时文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行不存在的脚本
        result = self.executor.run_file(
            "/non/existent/script.py",
            ["/non/existent/script.py"],
            tmpout,
            tmperr,
            10.0,
            tmpstruct,
            lambda: True,
            "test-7"
        )
        
        # 验证结果
        self.assertEqual(result['exitcode'], 1)
        self.assertIn("FileNotFoundError", result['stderr'])
        self.assertFalse(self.executor.is_successful(result['exitcode']))
    
    @patch("subprocess.Popen")
    def test_execution_failure(self, popen_mock):
        """测试子进程启动失败的情况"""
        # 模拟Popen异常
        popen_mock.side_effect = OSError("Failed to execute")
        
        # 临时文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行
        result = self.executor.run_file(
            self.python_script,
            [self.python_script],
            tmpout,
            tmperr,
            10.0,
            tmpstruct,
            lambda: True,
            "test-8"
        )
        
        # 验证结果
        self.assertEqual(result['exitcode'], 1)
        self.assertIn("Failed to execute", result['stderr'])
    
    def test_invalid_params(self):
        """测试无效参数处理"""
        # 临时文件
        tmpout = tempfile.mktemp(dir=self.test_dir, suffix=".out")
        tmperr = tempfile.mktemp(dir=self.test_dir, suffix=".err")
        tmpstruct = tempfile.mktemp(dir=self.test_dir, suffix=".json")
        
        # 执行带空脚本路径
        with self.assertRaises(ValueError):
            self.executor.run_file(
                "",
                [],
                tmpout,
                tmperr,
                10.0,
                tmpstruct,
                None,
                "test-invalid"
            )
        
        # 执行带空任务ID
        with self.assertRaises(ValueError):
            self.executor.run_file(
                self.python_script,
                [self.python_script],
                tmpout,
                tmperr,
                10.0,
                tmpstruct,
                None,
                ""
            )


if __name__ == "__main__":
    unittest.main()
