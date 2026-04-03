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
import io
import sys
import re
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call, create_autospec
import logging
from configparser import ConfigParser
from cloud_agent import HostCleanup
from cloud_commons import OSCheck

# 常量定义
PACKAGE_SECTION = "packages"
REPO_SECTION = "repositories"
USER_SECTION = "users"
DIR_SECTION = "directories"
PROCESS_SECTION = "processes"
ALT_SECTION = "alternatives"
METADATA_SECTION = "metadata"
USER_HOMEDIR_SECTION = "usr_homedir"

# 配置文件内容模板
HOSTCLEANUP_CONFIG = f"""
[{PROCESS_SECTION}]
proc_list = 323,434
proc_owner_list = abc,efg

[{USER_SECTION}]
usr_list = rrdcached,cloud-qa,hive,oozie,hbase,hcat,mysql,mapred,hdfs,zookeeper,sqoop

[{REPO_SECTION}]
repo_list = HDP-1.3.0,HDP-epel

[{DIR_SECTION}]
dir_list = /etc/hadoop,/etc/hbase,/etc/hcatalog,/tmp/hive

[{ALT_SECTION}]
symlink_list = hcatalog-conf,hadoop-default,hadoop-log,oozie-conf
target_list = /etc/hcatalog/conf.dist,/usr/share/man/man1/hadoop.1.gz,/etc/oozie/conf.dist,/usr/lib/hadoop

[{PACKAGE_SECTION}]
pkg_list = sqoop.noarch,hadoop-libhdfs.x86_64,rrdtool.x86_64,ganglia-gmond.x86_64

[{METADATA_SECTION}]
created = 2023-07-02 20:39:22.162757"""


class HostCleanupTestBase(unittest.TestCase):
    """主机清理测试基类，提供通用工具方法"""
    
    def setUp(self):
        # 准备临时目录
        self.test_dir = tempfile.mkdtemp(prefix="cloud_hostcleanup_")
        
        # 设置基本配置
        self.config_file = os.path.join(self.test_dir, "test_hostcheck.result")
        with open(self.config_file, "w") as f:
            f.write(HOSTCLEANUP_CONFIG)
        
        # 初始化HostCleanup实例
        self.hc = HostCleanup.HostCleanup()
        
        # 禁用实际日志记录
        HostCleanup.logger = MagicMock()
        
        # 捕获标准输出
        self.stdout_capture = io.StringIO()
        sys.stdout = self.stdout_capture
    
    def tearDown(self):
        # 恢复标准输出
        sys.stdout = sys.__stdout__
        # 清理临时目录
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def create_mock_options(self, input_files="", output_file="", skip="", 
                            silent=False, verbose=False, java_home=""):
        """创建模拟的命令行选项对象"""
        options = MagicMock()
        options.inputfiles = input_files
        options.outputfile = output_file
        options.skip = skip
        options.silent = silent
        options.verbose = verbose
        options.java_home = java_home
        return options, []
    
    def assert_cleanup_section_called(self, mock_object, section_name, expected_calls):
        """验证清理模块调用了特定部分的清理"""
        self.assertIn(section_name, str(mock_object.call_args))
        self.assertTrue(
            any(section_name in str(call_args) for call_args in mock_object.call_args_list),
            f"Expected cleanup for {section_name} not performed"
        )
        if expected_calls:
            mock_object.assert_has_calls(expected_calls)

    def generate_cleanup_map(self, **kwargs):
        """生成清理配置映射"""
        return {
            PACKAGE_SECTION: kwargs.get(PACKAGE_SECTION, []),
            REPO_SECTION: kwargs.get(REPO_SECTION, []),
            USER_SECTION: kwargs.get(USER_SECTION, []),
            DIR_SECTION: kwargs.get(DIR_SECTION, []),
            PROCESS_SECTION: {
                "proc_list": kwargs.get("proc_list", []),
                "proc_owner_list": kwargs.get("proc_owner_list", [])
            },
            ALT_SECTION: kwargs.get(ALT_SECTION, {}),
            USER_HOMEDIR_SECTION: kwargs.get(USER_HOMEDIR_SECTION, [])
        }


class ConfigParsingTests(HostCleanupTestBase):
    """测试配置文件解析功能"""
    
    def test_valid_config_parsing(self):
        """测试解析有效配置文件"""
        # 处理配置文件
        config_map = self.hc.read_host_check_file(self.config_file)
        
        # 验证关键配置
        self.assertIn(PROCESS_SECTION, config_map)
        self.assertEqual(config_map[PROCESS_SECTION]["proc_list"], ["323", "434"])
        
        self.assertIn(USER_SECTION, config_map)
        self.assertIn("mysql", config_map[USER_SECTION])
        
        self.assertIn(REPO_SECTION, config_map)
        self.assertIn("HDP-epel", config_map[REPO_SECTION])
        
        self.assertIn(DIR_SECTION, config_map)
        self.assertIn("/etc/hadoop", config_map[DIR_SECTION])
        
        self.assertIn(ALT_SECTION, config_map)
        self.assertIn("symlink_list", config_map[ALT_SECTION])
        self.assertIn("oozie-conf", config_map[ALT_SECTION]["symlink_list"])
        
        self.assertIn(PACKAGE_SECTION, config_map)
        self.assertIn("hadoop-libhdfs.x86_64", config_map[PACKAGE_SECTION])
    
    def test_missing_config_file(self):
        """测试处理缺失配置文件"""
        with self.assertRaises(IOError):
            self.hc.read_host_check_file("/non/existent/file")
    
    def test_invalid_config_format(self):
        """测试无效配置格式处理"""
        # 创建无效配置文件
        invalid_file = os.path.join(self.test_dir, "invalid_config")
        with open(invalid_file, "w") as f:
            f.write("[section]\ninvalid_line")
        
        config_map = self.hc.read_host_check_file(invalid_file)
        self.assertEqual(len(config_map), 0)
        self.assertIn("Failed to parse", self.stdout_capture.getvalue())


class ArgumentParsingTests(HostCleanupTestBase):
    """测试命令行参数解析功�?""
    
    @patch("optparse.OptionParser.parse_args")
    @patch("logging.FileHandler")
    @patch("logging.basicConfig")
    def test_option_parsing(self, log_config_mock, file_handler_mock, parse_args_mock):
        """测试参数完整解析"""
        # 创建输入文件
        input_file = os.path.join(self.test_dir, "input_file1")
        with open(input_file, "w") as f:
            f.write(HOSTCLEANUP_CONFIG)
        
        # 设置模拟返回�?        parse_args_mock.return_value = self.create_mock_options(
            input_files=input_file,
            output_file="output.log",
            skip="users,directories",
            verbose=True,
            java_home="/usr/java"
        )
        
        # 模拟文件处理
        file_handler_mock.return_value = MagicMock()
        
        # 测试执行主函�?        HostCleanup.main()
        
        # 验证参数处理
        self.assertEqual(HostCleanup.SKIP_LIST, ["users", "directories"])
        log_config_mock.assert_called_once_with(level=logging.INFO)
        file_handler_mock.assert_called_once_with("output.log")
    
    @patch("optparse.OptionParser.parse_args")
    @patch("logging.FileHandler")
    def test_silent_mode(self, file_handler_mock, parse_args_mock):
        """测试静默模式解析"""
        parse_args_mock.return_value = self.create_mock_options(
            input_files="input_file",
            output_file="output.log",
            silent=True
        )
        
        # 测试执行
        HostCleanup.main()
        
        # 验证不会请求用户确认
        self.assertNotIn("Do you want to continue", self.stdout_capture.getvalue())


class CleanupExecutionTests(HostCleanupTestBase):
    """测试清理执行功能"""
    
    @patch.object(HostCleanup.HostCleanup, "do_delete_users")
    @patch.object(HostCleanup.HostCleanup, "do_erase_packages")
    @patch.object(HostCleanup.HostCleanup, "do_erase_dir_silent")
    @patch.object(HostCleanup.HostCleanup, "do_erase_files_silent")
    @patch.object(HostCleanup.HostCleanup, "do_kill_processes")
    @patch.object(HostCleanup.HostCleanup, "do_erase_alternatives")
    @patch.object(HostCleanup.HostCleanup, "do_clear_cache")
    def test_full_cleanup_execution(self, clear_mock, alt_mock, kill_mock, 
                                  files_mock, dir_mock, pkg_mock, user_mock):
        """测试完整清理流程"""
        # 准备清理配置
        cleanup_map = self.generate_cleanup_map(
            packages=["package1", "package2"],
            repositories=["repo1", "repo2"],
            usr_list=["user1", "user2"],
            directories=["/dir1", "/dir2"],
            proc_list=["1234", "5678"],
            alternatives={
                "symlink_list": ["link1", "link2"],
                "target_list": ["/target1", "/target2"]
            },
            usr_homedir=["/home/user1"]
        )
        
        # 执行清理
        self.hc.do_cleanup(cleanup_map)
        
        # 验证调用
        pkg_mock.assert_called_once_with(["package1", "package2"])
        files_mock.assert_called_once_with(["repo1", "repo2"])
        user_mock.assert_called_once_with(["user1", "user2"])
        dir_mock.assert_has_calls([
            call(["/dir1", "/dir2"]),
            call(["/home/user1"])
        ])
        kill_mock.assert_called_once_with(["1234", "5678"])
        alt_mock.assert_called_once_with({
            "symlink_list": ["link1", "link2"],
            "target_list": ["/target1", "/target2"]
        })
        clear_mock.assert_called_once()
    
    @patch.object(HostCleanup.HostCleanup, "do_erase_packages")
    def test_cleanup_skip_packages(self, pkg_mock):
        """测试跳过软件包清�?""
        # 设置跳过列表
        HostCleanup.SKIP_LIST = ["packages"]
        
        # 准备清理配置
        cleanup_map = self.generate_cleanup_map(
            packages=["should_be_skipped"]
        )
        
        # 执行清理
        self.hc.do_cleanup(cleanup_map)
        
        # 验证软件包清理未执行
        pkg_mock.assert_not_called()
        
    @patch.object(HostCleanup.HostCleanup, "do_delete_users")
    def test_cleanup_skip_users(self, user_mock):
        """测试跳过用户清理"""
        # 设置跳过列表
        HostCleanup.SKIP_LIST = [USER_SECTION]
        
        # 准备清理配置
        cleanup_map = self.generate_cleanup_map(
            usr_list=["user1", "user2"]
        )
        
        # 执行清理
        self.hc.do_cleanup(cleanup_map)
        
        # 验证用户清理未执�?        user_mock.assert_not_called()


class PackageCleanupTests(HostCleanupTestBase):
    """测试软件包清理功�?""
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_redhat_package_cleanup(self, os_command_mock):
        """测试RedHat系统软件包清�?""
        # 模拟RedHat系统
        with patch.object(OSCheck, "get_os_type", return_value="redhat"):
            # 执行软件包清�?            self.hc.do_erase_packages(["pkg1", "pkg2"])
            
            # 验证命令调用
            os_command_mock.assert_called_once_with("yum erase -y pkg1 pkg2")
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_suse_package_cleanup(self, os_command_mock):
        """测试SUSE系统软件包清�?""
        # 模拟SUSE系统
        with patch.object(OSCheck, "get_os_type", return_value="suse"):
            # 执行软件包清�?            self.hc.do_erase_packages(["pkg1", "pkg2"])
            
            # 验证命令调用
            os_command_mock.assert_called_once_with("zypper -n -q remove pkg1 pkg2")
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_failed_package_cleanup(self, os_command_mock):
        """测试软件包清理失败处�?""
        # 模拟命令失败
        os_command_mock.return_value = (1, "", "Package not found")
        
        # 执行软件包清�?        result = self.hc.do_erase_packages(["unknown-package"])
        
        # 验证返回代码
        self.assertEqual(result, 1)
        self.assertIn("Failed to remove", self.stdout_capture.getvalue())


class UserManagementTests(HostCleanupTestBase):
    """测试用户管理功能"""
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_user_deletion(self, os_command_mock):
        """测试用户删除功能"""
        # 设置成功响应
        os_command_mock.return_value = (0, "Success", "")
        
        # 执行用户删除
        self.hc.do_delete_users(["user1", "user2"])
        
        # 验证命令调用
        expected_calls = [
            call("userdel -rf user1"),
            call("userdel -rf user2"),
            call("groupdel hadoop")
        ]
        os_command_mock.assert_has_calls(expected_calls)
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_user_deletion_failure(self, os_command_mock):
        """测试用户删除失败处理"""
        # 设置失败响应
        os_command_mock.return_value = (1, "", "User unknown")
        
        # 执行用户删除
        self.hc.do_delete_users(["nonexistent"])
        
        # 验证错误处理
        self.assertIn("Failed to delete user", self.stdout_capture.getvalue())


class FileSystemCleanupTests(HostCleanupTestBase):
    """测试文件系统清理功能"""
    
    @patch("shutil.rmtree")
    @patch("os.path.exists", return_value=True)
    def test_directory_cleanup(self, exists_mock, rmtree_mock):
        """测试目录清理功能"""
        # 执行目录清理
        self.hc.do_erase_dir_silent(["/dir/to/remove"])
        
        # 验证调用
        rmtree_mock.assert_called_once_with("/dir/to/remove", ignore_errors=True)
    
    @patch("os.remove")
    @patch("os.path.exists", return_value=True)
    def test_file_cleanup(self, exists_mock, remove_mock):
        """测试文件清理功能"""
        # 执行文件清理
        self.hc.do_erase_files_silent(["/file/to/remove"])
        
        # 验证调用
        remove_mock.assert_called_once_with("/file/to/remove")
    
    @patch("shutil.rmtree")
    def test_nonexistent_directory(self, rmtree_mock):
        """测试清理不存在目�?""
        # 执行目录清理
        self.hc.do_erase_dir_silent(["/non/existent/dir"])
        
        # 验证未尝试清�?        rmtree_mock.assert_not_called()
    
    @patch("os.remove")
    def test_nonexistent_file(self, remove_mock):
        """测试清理不存在文�?""
        # 执行文件清理
        self.hc.do_erase_files_silent(["/non/existent/file"])
        
        # 验证未尝试清�?        remove_mock.assert_not_called()


class ProcessManagementTests(HostCleanupTestBase):
    """测试进程管理功能"""
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_process_killing(self, os_command_mock):
        """测试进程终止功能"""
        # 执行进程终止
        self.hc.do_kill_processes(["1234", "5678"])
        
        # 验证命令调用
        expected_calls = [
            call("kill -9 1234"),
            call("kill -9 5678")
        ]
        os_command_mock.assert_has_calls(expected_calls)
    
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_process_kill_failure(self, os_command_mock):
        """测试终止进程失败处理"""
        # 设置失败响应
        os_command_mock.return_value = (1, "", "No such process")
        
        # 执行进程终止
        self.hc.do_kill_processes(["9999"])
        
        # 验证错误处理
        self.assertIn("Failed to kill process", self.stdout_capture.getvalue())


class AlternativeManagementTests(HostCleanupTestBase):
    """测试替代方案管理功能"""
    
    @patch("cloud_agent.HostCleanup.HostCleanup.get_alternatives_desc")
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_alternative_removal(self, os_command_mock, alt_desc_mock):
        """测试替代方案删除功能"""
        # 设置替代描述
        alt_desc_mock.return_value = "/path/to/alternative\n"
        
        # 执行替代删除
        alt_map = {"symlink_list": ["alt_link"], "target_list": ["/target/dir"]}
        self.hc.do_erase_alternatives(alt_map)
        
        # 验证命令调用
        os_command_mock.assert_called_once_with(
            "alternatives --remove alt_link /path/to/alternative"
        )
    
    @patch("cloud_agent.HostCleanup.HostCleanup.get_alternatives_desc")
    @patch("cloud_agent.HostCleanup.HostCleanup.run_os_command")
    def test_alternative_removal_failure(self, os_command_mock, alt_desc_mock):
        """测试替代方案删除失败处理"""
        # 设置失败响应
        os_command_mock.return_value = (1, "", "Alternative not found")
        alt_desc_mock.return_value = "/path/to/alternative\n"
        
        # 执行替代删除
        alt_map = {"symlink_list": ["missing_alt"]}
        self.hc.do_erase_alternatives(alt_map)
        
        # 验证错误处理
        self.assertIn("Failed to remove alternative", self.stdout_capture.getvalue())


if __name__ == "__main__":
    unittest.main()
