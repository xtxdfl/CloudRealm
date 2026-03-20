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

from unittest import TestCase  # 单元测试基类
import tempfile  # 临时文件处理
import logging  # 日志记录
import json  # JSON处理
import pprint  # 美化打印
from mock.mock import patch, MagicMock  # 测试模拟工具
from cloud_agent.CommandStatusDict import CommandStatusDict  # 命令状态字典类


class TestCommandStatusDict(TestCase):
    """单元测试类：验证命令状态管理功能完整�?""
    
    logger = logging.getLogger()
    
    def test_put_command_status(self):
        """测试命令状态分类：验证EXECUTION/STATUS命令不同处理机制"""
        # 创建不同类型的命令对�?        execution_cmd = {
            "commandType": "EXECUTION_COMMAND",
            "commandId": "1-1",
            "clusterName": "cc",
            "exitCode": 777,
            "role": "DATANODE",
            "roleCommand": "INSTALL",
            "serviceName": "HDFS",
            "taskId": 5,
        }
        status_cmd = {
            "componentName": "DATANODE",
            "commandType": "STATUS_COMMAND",
        }
        
        # 创建模拟回调函数和状态字�?        callback_mock = MagicMock()
        cmd_statuses = CommandStatusDict(callback_action=callback_mock)
        
        # 添加状态命令（不应触发回调�?        cmd_statuses.put_command_status(status_cmd, None)
        self.assertEqual(callback_mock.call_count, 0,
                         "STATUS_COMMAND不应触发回调")
        
        # 添加执行命令（应触发回调�?        cmd_statuses.put_command_status(execution_cmd, None)
        self.assertEqual(callback_mock.call_count, 1,
                         "EXECUTION_COMMAND应触发回�?)
    
    def test_report_generation(self):
        """测试报告生成：验证多任务状态聚合正确�?""
        # 创建模拟回调函数和命令状态字�?        callback_mock = MagicMock()
        cmd_statuses = CommandStatusDict(callback_action=callback_mock)
        
        # 定义不同状态的命令和预期报�?        in_progress1 = self._build_cmd(
            status="IN_PROGRESS", task_id=5, exit_code=777,
            stdout="notice: /Stage[1]...", stderr=""
        )
        in_progress2 = self._build_cmd(
            status="IN_PROGRESS", task_id=6
        )
        completed_cmd = self._build_cmd(
            status="COMPLETE", task_id=4
        )
        failed_cmd = self._build_cmd(
            status="FAILED", task_id=3
        )
        status_cmd = {
            "componentName": "DATANODE",
            "commandType": "STATUS_COMMAND"
        }
        status_report = {"componentName": "DATANODE", "status": "HEALTHY"}
        
        # 添加所有命令状�?        cmd_statuses.put_command_status(in_progress1, in_progress1['report'])
        cmd_statuses.put_command_status(in_progress2, in_progress2['report'])
        cmd_statuses.put_command_status(completed_cmd, completed_cmd['report'])
        cmd_statuses.put_command_status(failed_cmd, failed_cmd['report'])
        cmd_statuses.put_command_status(status_cmd, status_report)
        
        # 生成最终报�?        report = cmd_statuses.generate_report()
        
        # 验证结果字段
        self.assertIn("componentStatus", report, "缺少组件状态信�?)
        self.assertIn("reports", report, "缺少任务报告信息")
        
        # 验证组件状�?        self.assertEqual(len(report["componentStatus"]), 1, "组件状态数量错�?)
        self.assertEqual(report["componentStatus"][0]["status"], "HEALTHY", "组件状态值错�?)
        
        # 验证任务报告排序和格�?        self.assertEqual(len(report["reports"]), 4, "任务报告数量错误")
        
        # 按任务ID降序排序（预期：ID高的任务在先�?        task_ids = [rep["taskId"] for rep in report["reports"]]
        self.assertEqual(task_ids, [6, 5, 4, 3], "任务报告排序错误")
        
        # 验证IN_PROGRESS任务的扩展信�?        progress_report = next(rep for rep in report["reports"] if rep["taskId"] == 5)
        expected_fields = ["stderr", "stdout", "structuredOut", "clusterName", 
                          "roleCommand", "serviceName", "role", "actionId", 
                          "exitCode"]
        for field in expected_fields:
            self.assertIn(field, progress_report, f"IN_PROGRESS报告中缺少字�?{field}")

    def _build_cmd(self, status, task_id, **kwargs):
        """辅助方法：构建标准化命令对象"""
        base_cmd = {
            "commandType": "EXECUTION_COMMAND",
            "commandId": "1-1",
            "clusterName": "cc",
            "role": "DATANODE",
            "roleCommand": "INSTALL",
            "serviceName": "HDFS",
            "taskId": task_id,
            "stdout": "",
            "stderr": ""
        }
        
        # 合并额外参数
        base_cmd.update(kwargs)
        
        # 创建匹配的报�?        base_cmd['report'] = {"status": status, "taskId": task_id}
        return base_cmd
    
    @patch("builtins.open")
    def test_structured_output_handling(self, open_mock):
        """测试结构化输出处理：验证文件读取机制"""
        # 设置模拟文件读取
        file_mock = MagicMock(name="structured_out.tmp")
        file_mock.__enter__.return_value = file_mock  # 支持上下文管理器
        file_mock.read.return_value = '{"config":"value", "status":"ready"}'
        open_mock.return_value = file_mock
        
        callback_mock = MagicMock()
        cmd_statuses = CommandStatusDict(callback_action=callback_mock)
        
        # 创建包含结构化输出文件的命令状�?        cmd = self._build_cmd(status="IN_PROGRESS", task_id=5)
        cmd_report = {
            "status": "IN_PROGRESS",
            "taskId": 5,
            "structuredOut": "structured_out.tmp"
        }
        cmd_statuses.put_command_status(cmd, cmd_report)
        
        # 生成报告并验证结�?        report = cmd_statuses.generate_report()
        
        self.assertEqual(len(report["reports"]), 1, "报告数量错误")
        rep = report["reports"][0]
        self.assertEqual(rep["status"], "IN_PROGRESS", "状态值错�?)
        self.assertEqual(rep["structuredOut"], 
                         '{"config":"value", "status":"ready"}',
                         "结构化输出内容错�?)
        
        # 验证文件打开路径
        open_mock.assert_called_with("structured_out.tmp", "r", encoding="utf-8")
    
    def test_report_size_validation(self):
        """测试报告尺寸校验：验证大小限制机�?""
        # 创建命令状态字�?        callback_mock = MagicMock()
        cmd_statuses = CommandStatusDict(callback_action=callback_mock)
        
        # 测试报告尺寸校验
        report_data = {
            "status": "IN_PROGRESS",
            "taskId": 5,
            "structuredOut": "structured_out.tmp"
        }
        json_size = len(json.dumps(report_data))
        
        # 验证不同尺寸阈值下的结�?        # 尺寸大于实际JSON - 通过
        self.assertTrue(
            cmd_statuses.size_approved(report_data, json_size + 1),
            "尺寸校验错误（宽松阈值）"
        )
        
        # 尺寸等于实际JSON - 通过
        self.assertTrue(
            cmd_statuses.size_approved(report_data, json_size),
            "尺寸校验错误（精确阈值）"
        )
        
        # 尺寸小于实际JSON - 不通过
        self.assertFalse(
            cmd_statuses.size_approved(report_data, json_size - 1),
            "尺寸校验错误（严格阈值）"
        )
    
    def test_report_splitting_logic(self):
        """测试报告分片逻辑：验证大数据集分页机�?""
        # 构建模拟报告数据�?        reports = {
            "cluster1": [
                {"taskId": "c1-t1", "status": "COMPLETED"},
                {"taskId": "c1-t2", "status": "FAILED"},
                {"taskId": "c1-t3", "status": "IN_PROGRESS"},
                {"taskId": "c1-t4", "status": "PENDING"}
            ],
            "cluster2": [
                {"taskId": "c2-t1", "status": "COMPLETED"},
                {"taskId": "c2-t2", "status": "FAILED"},
                {"taskId": "c2-t3", "status": "IN_PROGRESS"},
                {"taskId": "c2-t4", "status": "PENDING"}
            ]
        }
        
        # 创建命令状态字�?        callback_mock = MagicMock()
        cmd_statuses = CommandStatusDict(callback_action=callback_mock)
        
        # 计算全部数据的JSON尺寸
        total_size = len(json.dumps(reports))
        
        # 测试1：尺寸足�?- 单次返回全部数据
        result = list(cmd_statuses.split_reports(reports, total_size + 100))
        self.assertEqual(len(result), 1, "分片数量错误（大尺寸阈值）")
        self.assertEqual(len(result[0]["cluster1"]), 4, "cluster1数据不完�?)
        self.assertEqual(len(result[0]["cluster2"]), 4, "cluster2数据不完�?)
        
        # 测试2：尺寸刚�?- 单次返回全部数据
        result = list(cmd_statuses.split_reports(reports, total_size))
        self.assertEqual(len(result), 1, "分片数量错误（精确尺寸阈值）")
        
        # 测试3：尺寸不�?- 分成多个片段
        result = list(cmd_statuses.split_reports(reports, total_size // 2))
        self.assertGreater(len(result), 1, "未正确分片（小尺寸阈值）")
        
        # 测试4：极小尺�?- 每个任务单独分片
        result = list(cmd_statuses.split_reports(reports, 50))
        self.assertEqual(len(result), 8, "分片数量错误（极小尺寸阈值）")
        
        # 验证数据完整�?        combined_reports = {}
        for chunk in result:
            for cluster, tasks in chunk.items():
                combined_reports.setdefault(cluster, []).extend(tasks)
        
        self.assertEqual(len(combined_reports["cluster1"]), 4, "cluster1数据丢失")
        self.assertEqual(len(combined_reports["cluster2"]), 4, "cluster2数据丢失")

