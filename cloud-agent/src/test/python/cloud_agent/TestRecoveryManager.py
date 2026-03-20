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
from unittest.mock import MagicMock, patch
import copy
from cloud_agent.RecoveryManager import RecoveryManager


class RecoveryBaseTestCase(unittest.TestCase):
    """恢复管理测试基类"""
    
    NODE_MANAGER_COMMAND = {
        "commandType": "STATUS_COMMAND",
        "payloadLevel": "EXECUTION_COMMAND",
        "componentName": "NODEMANAGER",
        "desiredState": "STARTED",
        "hasStaleConfigs": False,
        "executionCommandDetails": {
            "commandType": "EXECUTION_COMMAND",
            "roleCommand": "INSTALL",
            "role": "NODEMANAGER",
            "hostLevelParams": {"custom_command": ""},
            "configurations": {
                "capacity-scheduler": {
                    "yarn.scheduler.capacity.default.minimum-user-limit-percent": "100"
                },
                "commandParams": {
                    "service_package_folder": "common-services/YARN/2.1.0.2.0/package"
                },
            },
        },
    }
    
    def create_recovery_manager(self, enabled=False, *args, **kwargs):
        """创建恢复管理器实�?""
        return RecoveryManager(
            command_callback=MagicMock(), 
            enabled=enabled, 
            *args, **kwargs
        )


class RecoveryDefaultsTests(RecoveryBaseTestCase):
    """测试恢复管理器默认行�?""
    
    def test_default_behavior(self):
        """测试禁用状态下的默认行�?""
        rm = self.create_recovery_manager(enabled=False)
        
        # 验证恢复功能默认禁用
        self.assertFalse(rm.enabled(), "恢复功能应默认禁�?)
        
        # 验证初始状�?        self.assertIsNone(rm.get_install_command("NODEMANAGER"), "安装命令初始应为�?)
        self.assertIsNone(rm.get_start_command("NODEMANAGER"), "启动命令初始应为�?)
        
        # 更新状态并验证
        rm.update_current_status("NODEMANAGER", "INSTALLED")
        rm.update_desired_status("NODEMANAGER", "STARTED")
        self.assertFalse(rm.requires_recovery("NODEMANAGER"), "禁用状态下不应需要恢�?)


class WindowManagementTests(RecoveryBaseTestCase):
    """测试恢复窗口管理逻辑"""
    
    @patch.object(RecoveryManager, "_now_")
    def test_window_parameters_validation(self, time_mock):
        """测试配置参数验证"""
        time_mock.side_effect = [1000, 1001, 1002, 1003, 1004]
        
        rm = self.create_recovery_manager(enabled=True)
        
        # 验证无效配置
        self.assertFalse(
            rm.update_config(max_per_window=0, window_in_sec=60, min_wait=5, lifetime_max=10),
            "最大恢复次数为0时应禁用恢复"
        )
        self.assertFalse(
            rm.update_config(max_per_window=5, window_in_sec=0, min_wait=5, lifetime_max=10),
            "窗口时间�?时应禁用恢复"
        )
        self.assertTrue(
            rm.update_config(max_per_window=5, window_in_sec=60, min_wait=1, lifetime_max=10),
            "有效配置应启用恢�?
        )
    
    @patch.object(RecoveryManager, "_now_")
    def test_sliding_window_behavior(self, time_mock):
        """测试滑动窗口行为"""
        # 设置时间序列
        time_mock.side_effect = [
            1000, 1001, 1002, 1003, 1004,
            1070, 1071, 1072, 1150, 1151,
            1800, 1900, 2000, 2010, 2020
        ]
        
        # 配置恢复管理器：�?分钟窗口最�?次恢复，至少等待60�?        rm = self.create_recovery_manager(enabled=True)
        rm.update_config(
            max_per_window=2,
            window_in_sec=300,  # 5分钟
            min_wait=60,  # 1分钟
            lifetime_max=5
        )
        
        # �?秒：可以执行3次恢复（但窗口限制为2次）
        self.assertTrue(rm.execute("NODEMANAGER"), "�?次恢复应成功")
        self.assertTrue(rm.execute("DATANODE"), "不同的组件应独立计数")
        self.assertTrue(rm.execute("NODEMANAGER"), "同一组件�?次恢复应成功")
        self.assertFalse(rm.execute("NODEMANAGER"), "同一组件�?次应受窗口限�?)
        
        # 70秒后
        self.assertTrue(rm.execute("NODEMANAGER"), "超过等待时间后应允许恢复")
        
        # 115秒后
        self.assertFalse(rm.execute("NODEMANAGER"), "超过窗口最大限制后应拒绝恢�?)
        
        # 30分钟后（窗口重置�?        self.assertTrue(rm.execute("NODEMANAGER"), "窗口重置后应允许恢复")


class RecoveryConditionTests(RecoveryBaseTestCase):
    """测试恢复条件判断逻辑"""
    
    def setUp(self):
        super().setUp()
        self.rm = self.create_recovery_manager(enabled=True)
        recovery_config = {
            "components": [{
                "component_name": "NODEMANAGER",
                "service_name": "YARN",
                "desired_state": "INSTALLED"
            }]
        }
        self.rm.update_recovery_config({"recoveryConfig": recovery_config})
        self.rm.update_config(max_per_window=5, window_in_sec=60, min_wait=1, lifetime_max=10)
    
    def test_component_recovery_conditions(self):
        """测试不同状态组合下的恢复条�?""
        tests = [
            # 当前状�? 期望状�? 应恢�?            ("INSTALLED", "INSTALLED", False),
            ("INSTALLED", "STARTED",   True),
            ("STARTED",   "INSTALLED", True),
            ("STARTED",   "STARTED",   False),
            ("INIT",      "INSTALLED", True),
            ("INIT",      "STARTED",   True),
            ("UNKNOWN",   "INSTALLED", False),
            ("STARTED",   None,        False),
            (None,        "STARTED",   False)
        ]
        
        for current, desired, should_recover in tests:
            with self.subTest(current=current, desired=desired, should_recover=should_recover):
                self.rm.update_current_status("NODEMANAGER", current)
                self.rm.update_desired_status("NODEMANAGER", desired)
                self.assertEqual(
                    self.rm.requires_recovery("NODEMANAGER"), 
                    should_recover,
                    f"状�?{current}=>{desired})下恢复预期应为{should_recover}"
                )
    
    def test_unconfigured_component_handling(self):
        """测试未配置恢复的组件处理"""
        self.rm.update_desired_status("DATANODE", "STARTED")
        self.rm.update_current_status("DATANODE", "STOPPED")
        self.assertFalse(
            self.rm.requires_recovery("DATANODE"),
            "未配置恢复的组件不应需要恢�?
        )


class RecoveryReportTests(RecoveryBaseTestCase):
    """测试恢复状态报告生�?""
    
    @patch.object(RecoveryManager, "_now_")
    def test_report_generation(self, time_mock):
        """测试详细的恢复状态报�?""
        time_mock.side_effect = [
            1000, 1001, 1002, 1003, 1004, 
            1100, 1200, 1300, 1400, 1500
        ]
        
        rm = self.create_recovery_manager(enabled=True)
        rm.update_config(max_per_window=3, window_in_sec=300, min_wait=30, lifetime_max=5)
        
        # 初始报告
        report = rm.get_recovery_status()
        self.assertEqual(report["summary"], "RECOVERABLE", "初始报告应为可恢�?)
        
        # 执行恢复操作
        rm.execute("NODEMANAGER")
        rm.execute("DATANODE")
        
        # 验证详细报告
        report = rm.get_recovery_status()
        self.assertEqual(report["summary"], "RECOVERABLE")
        self.assertEqual(len(report["componentReports"]), 2)
        self.assertEqual(report["componentReports"][0]["name"], "NODEMANAGER")
        self.assertEqual(report["componentReports"][0]["numAttempts"], 1)
        self.assertFalse(report["componentReports"][0]["limitReached"])
        
        # 超出窗口限制
        rm.execute("NODEMANAGER")
        rm.execute("NODEMANAGER")
        rm.execute("NODEMANAGER")  # �?次（超出限制�?        
        # 验证限量报告
        report = rm.get_recovery_status()
        self.assertEqual(report["summary"], "PARTIALLY_RECOVERABLE", "部分组件超过限制")
        for comp_report in report["componentReports"]:
            if comp_report["name"] == "NODEMANAGER":
                self.assertTrue(comp_report["limitReached"], "NODEMANAGER应达到限�?)
        
        # 超出生命周期限制
        rm.execute("NODEMANAGER")  # �?�?        report = rm.get_recovery_status()
        self.assertEqual(report["summary"], "UNRECOVERABLE", "超过生命周期限制应为不可恢复")


class RecoveryCommandTests(RecoveryBaseTestCase):
    """测试恢复命令生成逻辑"""
    
    @patch.object(RecoveryManager, "_now_")
    def test_command_generation(self, time_mock):
        """测试恢复命令生成"""
        time_mock.side_effect = [1000, 1010, 1080, 1100]
        
        rm = self.create_recovery_manager(enabled=True)
        recovery_config = {
            "components": [{
                "component_name": "NODEMANAGER",
                "service_name": "YARN",
                "desired_state": "INSTALLED"
            }]
        }
        rm.update_recovery_config({"recoveryConfig": recovery_config})
        rm.update_config(max_per_window=5, window_in_sec=60, min_wait=10, lifetime_max=10)
        rm.retry_gap_in_sec = 60
        
        # 设置组件状�?        rm.update_current_status("NODEMANAGER", "STOPPED")
        rm.update_desired_status("NODEMANAGER", "STARTED")
        
        # 首次获取恢复命令
        commands = rm.get_recovery_commands()
        self.assertEqual(len(commands), 1, "应生成一个恢复命�?)
        self.assertEqual(commands[0]["roleCommand"], "START", "命令应为启动操作")
        
        # 再次快速获取（应在重试间隔内）
        commands = rm.get_recovery_commands()
        self.assertEqual(len(commands), 0, "应在重试间隔内返回空")
        
        # 超时后获�?        commands = rm.get_recovery_commands()
        self.assertEqual(len(commands), 1, "超时后应可再次生成命�?)


class ConfigurationTests(RecoveryBaseTestCase):
    """测试恢复配置管理"""
    
    def test_dynamic_configuration(self):
        """测试动态配置更�?""
        rm = self.create_recovery_manager(enabled=True)
        
        # 初始无配�?        self.assertFalse(rm.configured_for_recovery("NODEMANAGER"))
        
        # 更新恢复配置
        recovery_config = {
            "components": [
                {"component_name": "NODEMANAGER", "service_name": "YARN", "desired_state": "INSTALLED"},
                {"component_name": "DATANODE", "service_name": "HDFS", "desired_state": "STARTED"}
            ]
        }
        rm.update_recovery_config({"recoveryConfig": recovery_config})
        
        # 验证配置
        self.assertTrue(rm.configured_for_recovery("NODEMANAGER"))
        self.assertTrue(rm.configured_for_recovery("DATANODE"))
        self.assertFalse(rm.configured_for_recovery("NAMENODE"), "未配置的组件应返回False")
        
        # 更新为部分配�?        recovery_config["components"] = [{"component_name": "NODEMANAGER", "service_name": "YARN", "desired_state": "INSTALLED"}]
        rm.update_recovery_config({"recoveryConfig": recovery_config})
        
        # 验证更新
        self.assertTrue(rm.configured_for_recovery("NODEMANAGER"))
        self.assertFalse(rm.configured_for_recovery("DATANODE"), "配置更新后应移除该组�?)


class WindowResetTests(RecoveryBaseTestCase):
    """测试时间窗口重置逻辑"""
    
    @patch.object(RecoveryManager, "_now_")
    def test_action_window_reset(self, time_mock):
        """测试超过时间窗口后行为计数重�?""
        time_mock.side_effect = [1000, 1005, 2000]
        
        rm = self.create_recovery_manager(enabled=True)
        rm.update_config(
            max_per_window=2,
            window_in_sec=900,  # 15分钟
            min_wait=60,
            lifetime_max=10
        )
        
        # 创建初始行为
        rm.execute("NODEMANAGER")
        initial_action = rm.get_actions_copy()["NODEMANAGER"]
        
        # 在窗口内再次执行
        rm.execute("NODEMANAGER")
        same_window_action = rm.get_actions_copy()["NODEMANAGER"]
        self.assertEqual(initial_action["lastReset"], same_window_action["lastReset"], "窗口内不应重�?)
        
        # 超过窗口时间后执�?        rm.execute("NODEMANAGER")
        reset_action = rm.get_actions_copy()["NODEMANAGER"]
        self.assertNotEqual(initial_action["lastReset"], reset_action["lastReset"], "窗口过期后应重置")
        self.assertEqual(reset_action["count"], 1, "重置后计数应�?")


class StalenessCheckTests(RecoveryBaseTestCase):
    """测试恢复信息过时检�?""
    
    @patch.object(RecoveryManager, "_now_")
    def test_action_staleness_detection(self, time_mock):
        """测试行为信息过时检�?""
        time_mock.side_effect = [0, 3600, 7200]
        
        rm = self.create_recovery_manager(enabled=True)
        rm.update_config(
            max_per_window=5,
            window_in_sec=3600,  # 1小时
            min_wait=300,  # 5分钟
            lifetime_max=20,
            max_staleness=3601  # 1小时+1�?        )
        
        # 初始化行为记�?        rm.actions = {
            "COMPONENT_A": {
                "lastAttempt": 0,
                "count": 1,
                "lastReset": 0,
                "lifetimeCount": 1
            },
            "COMPONENT_B": {
                "lastAttempt": 3600,
                "count": 1,
                "lastReset": 3600,
                "lifetimeCount": 1
            }
        }
        
        # 验证过时检�?        self.assertTrue(rm.is_action_info_stale("COMPONENT_A"), "超过最大时效应标记为过�?)
        self.assertFalse(rm.is_action_info_stale("COMPONENT_B"), "在时效范围内的不应标记为过时")


if __name__ == '__main__':
    unittest.main(verbosity=2)
