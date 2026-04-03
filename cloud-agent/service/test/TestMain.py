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
import io
import signal
import configparser
import logging
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call, ANY
import resource
import shutil

# 测试工具
from testing_utils import PlatformSpec, WindowsOnly, UnixOnly

# 模块导入
with patch("cloud_commons.OSCheck.os_distribution", return_value="linux"):
    # 初始化配置和日志系统
    from cloud_agent import security
    from cloud_agent import main
    from cloudConfig import cloudConfig
    from PingPortListener import PingPortListener
    from DataCleaner import DataCleaner
    import HeartbeatHandlers as HeartbeatHandlers
    from cloud_commons.os_check import OSConst, OSCheck
    from ExitHelper import ExitHelper
    from cloud_commons import shell


class MainModuleTestSetup:
    """主模块测试的基础设置类，处理通用mock与工具方?""
    
    def setup_base_mocks(self):
        """创建核心模块的模拟对?""
        self.logger_mock = MagicMock()
        self.config_mock = MagicMock(spec=cloudConfig)
        self.shell_mock = MagicMock()
        self.exit_helper_mock = MagicMock()
        
        # 标准模拟补丁
        self.patches = [
            patch.object(main, "logger", self.logger_mock),
            patch.object(main, "cloudConfig", return_value=self.config_mock),
            patch("cloud_commons.shell.shellRunner", self.shell_mock),
            patch("cloud_agent.ExitHelper.ExitHelper", self.exit_helper_mock)
        ]
        
        # 启动所有模拟补?        for mock_patch in self.patches:
            mock_patch.start()
        
    def teardown_base_mocks(self):
        """停止所有模拟补?""
        for mock_patch in self.patches:
            mock_patch.stop()
    
    @classmethod
    def create_temp_config_file(cls, content_dict):
        """创建临时配置文件"""
        config = configparser.ConfigParser()
        for section, options in content_dict.items():
            config.add_section(section)
            for key, value in options.items():
                config.set(section, key, value)
        
        # 写入临时文件
        _, tmp_path = tempfile.mkstemp(prefix="cloud_test_", suffix=".ini")
        with open(tmp_path, "w") as f:
            config.write(f)
        return tmp_path


class TestSignalHandling(unittest.TestCase, MainModuleTestSetup):
    """测试信号处理逻辑（Unix平台专用?""
    
    @UnixOnly
    def setUp(self):
        self.setup_base_mocks()
        
    @UnixOnly
    def tearDown(self):
        self.teardown_base_mocks()
    
    @UnixOnly
    @patch("signal.signal")
    @patch.object(HeartbeatHandlers, "HeartbeatStopHandlersLinux")
    @patch("sys.exit")
    @patch("os.getpid")
    def test_signal_handling_process_hierarchy(
        self, getpid_mock, exit_mock, heartbeat_mock, signal_mock
    ):
        """测试不同进程层级下的信号处理方式"""
        # 设置为子进程ID（非主进程）
        main.agentPid = 1000
        getpid_mock.return_value = 2000
        
        # 触发信号处理?        HeartbeatHandlers.signal_handler(signal.SIGTERM, None)
        
        # 验证子进程行?        heartbeat_mock().set_stop.assert_called_once()
        exit_mock.assert_called_once_with(1)
        
        # 重置并设置为主进?        exit_mock.reset_mock()
        heartbeat_mock.reset_mock()
        getpid_mock.return_value = 1000
        
        # 再次触发信号
        HeartbeatHandlers.signal_handler(signal.SIGINT, None)
        
        # 验证主进程行?        self.assertEqual(heartbeat_mock().set_stop.call_count, 1)
    
    @UnixOnly
    def test_signal_registration(self):
        """验证SIGTERM和SIGINT信号的绑?""
        with patch("signal.signal") as signal_mock:
            main.bind_signal_handlers(1000)
            signal_mock.assert_any_call(signal.SIGTERM, HeartbeatHandlers.signal_handler)
            signal_mock.assert_any_call(signal.SIGINT, HeartbeatHandlers.signal_handler)


class TestLoggingConfiguration(unittest.TestCase, MainModuleTestSetup):
    """测试日志系统初始化与管理"""
    
    def setUp(self):
        self.setup_base_mocks()
        self.log_handler_mock = MagicMock()
        
        # 日志处理器的模拟补丁
        self.handler_patch = patch(
            "logging.handlers.RotatingFileHandler", return_value=self.log_handler_mock
        )
        self.handler_patch.start()
    
    def tearDown(self):
        self.teardown_base_mocks()
        self.handler_patch.stop()
    
    @patch("logging.basicConfig")
    def test_log_setup_default_level(self, basic_config_mock):
        """测试默认日志级别（INFO）配?""
        main.setup_logging(
            logging.getLogger(), "/var/log/cloud-agent/cloud-agent.log", 
            default_level=logging.INFO
        )
        
        # 验证日志级别
        self.logger_mock.setLevel.assert_called_with(logging.INFO)
        self.logger_mock.addHandler.assert_called_with(self.log_handler_mock)
        self.log_handler_mock.setLevel.assert_called_with(logging.INFO)
    
    @patch("logging.basicConfig")
    def test_log_setup_debug_level(self, basic_config_mock):
        """测试DEBUG日志级别配置"""
        main.setup_logging(
            logging.getLogger(), "/var/log/cloud-agent/cloud-agent.log", 
            default_level=logging.DEBUG
        )
        
        # 验证DEBUG级别
        self.logger_mock.setLevel.assert_called_with(logging.DEBUG)
        self.log_handler_mock.setLevel.assert_called_with(logging.DEBUG)
    
    def test_log_level_update(self):
        """测试运行时日志级别更?""
        # 创建包含日志级别的配?        temp_config_path = self.create_temp_config_file({
            "agent": {"loglevel": "DEBUG", "prefix": "/tmp"}
        })
        
        with patch("cloud_agent.cloudConfig.getConfig") as config_mock:
            # 模拟配置对象
            config_parser = configparser.ConfigParser()
            config_parser.read(temp_config_path)
            config_mock.return_value = config_parser
            
            # 执行日志级别更新
            main.update_log_level(config_parser)
            
            # 验证日志级别设置
            self.logger_mock.setLevel.assert_called_with(logging.DEBUG)
        
        # 清理临时文件
        os.unlink(temp_config_path)


class TestSystemConfiguration(unittest.TestCase):
    """测试系统资源配置与验?""
    
    @patch("resource.setrlimit")
    @patch("resource.getrlimit")
    def test_ulimit_configuration(self, getrlimit_mock, setrlimit_mock):
        """测试ulimit资源配置"""
        # 模拟初始资源限制
        test_limits = 10000
        getrlimit_mock.return_value = (8000, 20000)
        
        # 创建配置对象
        config = cloudConfig()
        config.set_ulimit_open_files(test_limits)
        main.update_open_files_ulimit(config)
        
        # 验证设置调用
        setrlimit_mock.assert_called_with(
            resource.RLIMIT_NOFILE, 
            (test_limits, test_limits)
        )
    
    @patch("resource.setrlimit")
    def test_ulimit_configuration_error(self, setrlimit_mock):
        """测试ulimit配置错误处理"""
        # 创建测试配置
        config = cloudConfig()
        config.set_ulimit_open_files(20000)
        
        # 模拟权限错误
        setrlimit_mock.side_effect = PermissionError("No permission")
        
        # 验证异常处理
        try:
            main.update_open_files_ulimit(config)
        except PermissionError:
            self.fail("未处理权限异?)
        
        # 验证日志记录
        self.assertIn("Ulimit update failed", main.logger.error.call_args[0][0])


class TestLifecycleOperations(unittest.TestCase, MainModuleTestSetup):
    """测试Agent生命周期管理操作"""
    
    def setUp(self):
        self.setup_base_mocks()
        
        # 创建临时工作目录
        self.test_dir = tempfile.mkdtemp(prefix="cloud_test_")
        self.original_prefix = main.AGENT_PREFIX
        
        # 设置临时工作前缀
        main.AGENT_PREFIX = self.test_dir
    
    def tearDown(self):
        self.teardown_base_mocks()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        main.AGENT_PREFIX = self.original_prefix
    
    @patch("os.path.isfile")
    @patch("os.path.isdir")
    @patch("cloud_agent.hostname.hostname")
    @patch("sys.exit")
    def test_prestart_checks_normal(self, exit_mock, hostname_mock, isdir_mock, isfile_mock):
        """测试正常环境的前置检?""
        # 配置模拟返回?        hostname_mock.return_value = "test-host"
        isdir_mock.return_value = True
        isfile_mock.return_value = False
        
        # 执行前置检?        main.perform_prestart_checks(None)
        
        # 验证无退出调?        exit_mock.assert_not_called()
    
    @patch("os.path.isfile")
    @patch("os.path.isdir")
    @patch("cloud_agent.hostname.hostname")
    @patch("sys.exit")
    def test_prestart_checks_hostname_mismatch(self, exit_mock, hostname_mock, isdir_mock, isfile_mock):
        """测试主机名不匹配的场?""
        hostname_mock.return_value = "local-host"
        isdir_mock.return_value = True
        isfile_mock.return_value = False
        
        # 执行带预期主机名的检?        main.perform_prestart_checks("expected-host")
        
        # 验证退出调?        exit_mock.assert_called_once_with(1)
        self.assertIn("Hostname mismatch", str(main.logger.error.call_args))
    
    @patch("os.path.isfile")
    @patch("os.path.isdir")
    @patch("sys.exit")
    def test_prestart_checks_missing_prefix(self, exit_mock, isdir_mock, isfile_mock):
        """测试缺失工作目录的场?""
        isdir_mock.return_value = False
        isfile_mock.return_value = False
        
        # 执行检?        main.perform_prestart_checks(None)
        
        # 验证退出调?        exit_mock.assert_called_once_with(1)
        self.assertIn("does not exist", str(main.logger.error.call_args))


class TestDaemonOperations(unittest.TestCase, MainModuleTestSetup):
    """测试守护进程管理操作（Unix平台专用?""
    
    @UnixOnly
    def setUp(self):
        self.setup_base_mocks()
        
        # 创建临时PID文件
        self.pid_file_path = tempfile.mkstemp(prefix="cloud_test_")[1]
        self.original_pid_file = main.agent_pidfile
        main.agent_pidfile = self.pid_file_path
    
    @UnixOnly
    def tearDown(self):
        self.teardown_base_mocks()
        
        # 清理PID文件
        if os.path.exists(self.pid_file_path):
            os.remove(self.pid_file_path)
        
        main.agent_pidfile = self.original_pid_file
    
    @UnixOnly
    @patch("sys.exit")
    @patch("time.sleep")
    @patch("os.path.exists")
    def test_daemon_creation(self, exists_mock, sleep_mock, exit_mock):
        """测试守护进程创建与PID文件生成"""
        pid_value = os.getpid()
        
        # 创建守护进程
        main.daemonize()
        
        # 验证PID文件内容
        with open(self.pid_file_path, "r") as f:
            self.assertEqual(str(pid_value), f.read().strip())
    
    @UnixOnly
    @patch("sys.exit")
    @patch("time.sleep")
    @patch("os.path.exists")
    def test_graceful_stop(self, exists_mock, sleep_mock, exit_mock):
        """测试优雅停止守护进程"""
        # 设置当前进程PID
        pid_value = os.getpid()
        
        # 模拟PID文件存在
        with open(self.pid_file_path, "w") as f:
            f.write(str(pid_value))
        
        # 模拟进程终止成功
        self.shell_mock.return_value.run.return_value = {"exitCode": 0}
        exists_mock.return_value = False
        
        # 执行停止操作
        main.main_stop()
        
        # 验证信号发送顺?        self.shell_mock.return_value.run.assert_has_calls([
            call(["cloud-sudo.sh", "kill", "-15", str(pid_value)]),
            call(["cloud-sudo.sh", "kill", "-0", str(pid_value)])
        ])
        
        # 验证成功退?        exit_mock.assert_called_with(0)
    
    @UnixOnly
    @patch("sys.exit")
    @patch("time.sleep")
    @patch("os.path.exists")
    def test_forced_stop(self, exists_mock, sleep_mock, exit_mock):
        """测试强制停止守护进程"""
        pid_value = os.getpid()
        
        # 模拟优雅停止失败
        self.shell_mock.return_value.run.side_effect = [
            {"exitCode": 0},  # SIGTERM发送成?            {"exitCode": 0},  # kill -0 返回进程仍在运行
            {"exitCode": 0}   # SIGKILL发送成?        ]
        exists_mock.side_effect = [True, False]  # PID文件在SIGKILL后被清除
        
        # 执行停止操作
        main.main_stop()
        
        # 验证信号发送顺?        self.shell_mock.return_value.run.assert_has_calls([
            call(["cloud-sudo.sh", "kill", "-15", str(pid_value)]),
            call(["cloud-sudo.sh", "kill", "-0", str(pid_value)]),
            call(["cloud-sudo.sh", "kill", "-9", str(pid_value)])
        ])
        
        # 验证成功退?        exit_mock.assert_called_with(0)


class TestMainProgramFlow(unittest.TestCase, MainModuleTestSetup):
    """测试主程序执行流?""
    
    def setUp(self):
        self.setup_base_mocks()
        
        # 创建临时配置目录
        self.test_dir = tempfile.mkdtemp(prefix="cloud_test_")
        
        # 创建临时配置文件
        self.config_path = os.path.join(self.test_dir, "cloud-agent.ini")
        with open(self.config_path, "w") as f:
            f.write("[agent]\nloglevel = INFO\n\n[security]\nserver_crt = server.crt")
    
    def tearDown(self):
        self.teardown_base_mocks()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch.object(main, "PingPortListener")
    @patch.object(main, "DataCleaner")
    @patch.object(main, "setup_logging")
    @patch.object(main, "bind_signal_handlers")
    @patch.object(main, "update_log_level")
    @patch.object(main, "daemonize")
    @patch.object(main, "perform_prestart_checks")
    @patch.object(NetUtil.NetUtil, "try_to_connect")
    @patch("sys.argv", ["cloud-agent"])
    @patch("optparse.OptionParser.parse_args")
    def test_normal_startup(
        self, parse_args_mock, try_connect_mock, precheck_mock,
        daemonize_mock, update_log_mock, signal_mock, logging_mock,
        data_clean_mock, ping_listener_mock
    ):
        """测试正常启动流程"""
        # 配置解析器返回?        options = MagicMock()
        options.expected_hostname = None
        options.verbose = False
        parse_args_mock.return_value = (options, [])
        
        # 配置网络连接状?        try_connect_mock.return_value = (0, True, False)  # 立即连接成功
        
        # 配置临时配置文件
        self.config_mock.getConfigFile.return_value = self.config_path
        
        # 执行主函?        main.main()
        
        # 验证关键流程
        logging_mock.assert_called_once_with(
            ANY, main.AGENT_LOG_PATH, logging.INFO
        )
        precheck_mock.assert_called_once_with(None)
        update_log_mock.assert_called_once()
        daemonize_mock.assert_called_once()
        
        # 验证核心组件启动
        data_clean_mock.return_value.start.assert_called_once()
        ping_listener_mock.return_value.start.assert_called_once()
        self.exit_helper_mock().register_app.assert_called_once()
        
        # 验证退出处?        self.exit_helper_mock().execute_cleanup.assert_called_once()
    
    @patch.object(main, "PingPortListener")
    @patch.object(NetUtil.NetUtil, "try_to_connect")
    @patch("sys.argv", ["cloud-agent"])
    @patch("optparse.OptionParser.parse_args")
    def test_multi_server_connection(
        self, parse_args_mock, try_connect_mock, ping_listener_mock
    ):
        """测试多服务器连接策略"""
        # 模拟多服务器列表
        hostname.cached_server_hostnames = ["server1", "server2", "server3"]
        
        # 配置解析器返回?        options = MagicMock()
        options.expected_hostname = None
        parse_args_mock.return_value = (options, [])
        
        # 定义连接状态顺?        try_connect_mock.side_effect = [
            (0, False, False),  # server1连接失败
            (1, False, False),  # server2连接失败
            (2, True, False)    # server3连接成功
        ]
        
        # 执行主函?        main.main()
        
        # 验证连接尝试次数
        self.assertEqual(try_connect_mock.call_count, 3)
        
        # 验证日志记录
        self.logger_mock.info.assert_any_call(
            "Successfully connected to the server: server3"
        )


class TestResetOperation(unittest.TestCase, MainModuleTestSetup):
    """测试Agent重置操作"""
    
    def setUp(self):
        self.setup_base_mocks()
        self.temp_dir = tempfile.mkdtemp(prefix="cloud_test_")
    
    def tearDown(self):
        self.teardown_base_mocks()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch("sys.exit")
    @patch("os.walk")
    @patch("os.remove")
    @patch("os.rmdir")
    def test_reset_operation_success(self, rmdir_mock, remove_mock, walk_mock, exit_mock):
        """测试重置操作成功流程"""
        # 模拟文件系统结构
        walk_mock.return_value = [
            (self.temp_dir, ["subdir"], ["file1.log", "file2.tmp"])
        ]
        
        # 模拟配置文件
        config_mock = MagicMock()
        self.config_mock.getConfig.return_value = config_mock
        config_mock.get.return_value = "old-host"
        
        # 执行重置操作
        main.reset_agent(["program", "reset", "new-host"])
        
        # 验证配置更新
        config_mock.set.assert_called_once_with("server", "hostname", "new-host")
        
        # 验证文件清理
        self.assertEqual(remove_mock.call_count, 2)
        self.assertEqual(rmdir_mock.call_count, 1)
        exit_mock.assert_called_once_with(0)
    
    @patch("sys.exit")
    def test_reset_operation_config_error(self, exit_mock):
        """测试配置访问错误处理"""
        # 模拟配置读取错误
        with patch("builtins.open", side_effect=PermissionError):
            main.reset_agent(["program", "reset", "new-host"])
            
            # 验证错误处理
            self.assertIn("Invalid Path", str(self.logger_mock.error.call_args))
            exit_mock.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
