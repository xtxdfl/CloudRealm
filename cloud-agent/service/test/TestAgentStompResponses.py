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
import json
import time
import logging
import shutil
import tempfile
import unittest
from coilmq.util.frames import Frame
from mock.mock import MagicMock, patch, call, create_autospec

# 测试基类和工具类
from BaseStompServerTestCase import BaseStompServerTestCase
from Utils import Utils

# Agent核心组件
from InitializerModule import InitializerModule
from HeartbeatThread import HeartbeatThread
from ComponentStatusExecutor import ComponentStatusExecutor
from CommandStatusReporter import CommandStatusReporter
from HostStatusReporter import HostStatusReporter
from CustomServiceOrchestrator import CustomServiceOrchestrator


@patch("socket.gethostbyname", return_value="192.168.64.101")
@patch(
    "cloud_agent.hostname.hostname", 
    return_value="c6401.cloud.apache.org"
)
class TestAgentStompResponses(BaseStompServerTestCase):
    """综合测试类：验证Agent通过STOMP协议与服务器的完整交互流?""
    
    TEST_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        "test_data", 
        "stomp_responses"
    )

    def setUp(self):
        """创建隔离的测试环境：构建临时目录、缓存和配置文件"""
        super().setUp()
        
        # 创建临时工作目录
        self.temp_dir = tempfile.mkdtemp(prefix="cloud_agent_test_")
        
        # 配置缓存路径
        self.cluster_cache_dir = os.path.join(self.temp_dir, "cluster_cache")
        os.makedirs(self.cluster_cache_dir, exist_ok=True)
        
        # 构建Agent工作目录
        self.agent_work_dir = os.path.join(self.temp_dir, "cloud-agent")
        os.makedirs(self.agent_work_dir, exist_ok=True)
        
        # 写入Agent版本文件
        with open(os.path.join(self.agent_work_dir, "version"), "w") as f:
            f.write("2.5.0.0")
        
        # 初始化Agent核心模块
        self.initializer = InitializerModule(
            config_overrides={"agent": {"prefix": self.temp_dir}}
        )
        
        # 创建服务器交互助?        self.server_helper = StompServerHelper(self.server)
        
    def tearDown(self):
        """清理测试环境：停止线程并删除临时文件"""
        if self.initializer:
            self.initializer.stop_event.set()
            time.sleep(0.5)  # 等待线程退?        
        # 移除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()
    
    def _load_test_json(self, filename):
        """加载指定JSON测试数据文件"""
        filepath = os.path.join(self.TEST_DATA_DIR, filename)
        with open(filepath, "r") as f:
            return json.load(f)
    
    def _start_agent_threads(self):
        """启动Agent所有工作线程：心跳、命令、状态等"""
        # 启动Agent核心模块
        self.initializer.init()
        
        # 启动心跳线程
        heartbeat = HeartbeatThread(self.initializer)
        heartbeat.name = "Test-Heartbeat"
        heartbeat.daemon = True
        heartbeat.start()
        
        # 启动动作队列
        self.initializer.action_queue.start()
        
        # 启动告警调度?        self.initializer.alert_scheduler_handler.start()
        
        # 启动组件状态检?        component_status = ComponentStatusExecutor(self.initializer)
        component_status.name = "Test-ComponentStatus"
        component_status.daemon = True
        component_status.start()
        
        # 启动命令状态报?        cmd_reporter = CommandStatusReporter(self.initializer)
        cmd_reporter.name = "Test-CommandReporter"
        cmd_reporter.daemon = True
        cmd_reporter.start()
        
        # 启动主机状态报?        host_reporter = HostStatusReporter(self.initializer)
        host_reporter.name = "Test-HostReporter"
        host_reporter.daemon = True
        host_reporter.start()
        
        return {
            "heartbeat": heartbeat,
            "component_status": component_status,
            "cmd_reporter": cmd_reporter,
            "host_reporter": host_reporter
        }
    
    def _wait_for_registration(self, timeout=10):
        """等待Agent完成注册过程"""
        start_time = time.time()
        while not self.initializer.is_registered:
            if time.time() - start_time > timeout:
                raise TimeoutError("Agent注册超时")
            time.sleep(0.1)
    
    @patch.object(CustomServiceOrchestrator, "runCommand")
    def test_full_lifecycle(self, run_cmd_mock):
        """测试Agent完整生命周期：注册、执行命令、报告状?""
        # 配置命令执行模拟
        run_cmd_mock.return_value = {
            "stdout": "Command output",
            "stderr": "Command errors",
            "structuredOut": "{}",
            "exitcode": 1,
        }
        
        # 启动Agent线程
        threads = self._start_agent_threads()
        
        # 验证初始连接序列
        connect_frame = self.server.frames_queue.get(timeout=5)
        self.server_helper.validate_connect_frame(connect_frame)
        
        users_frame = self.server.frames_queue.get(timeout=5)
        self.server_helper.validate_user_subscribe_frame(users_frame)
        
        reg_frame = self.server.frames_queue.get(timeout=5)
        self.server_helper.validate_registration_frame(reg_frame)
        
        # 注册响应
        self.server_helper.send_registration_response()
        
        # 发送初始拓扑数?        self.server_helper.send_frame(
            "1", "topology_create.json", 
            description="初始集群拓扑"
        )
        
        # 发送元数据
        self.server_helper.send_frame(
            "2", "metadata_after_registration.json",
            description="服务元数?
        )
        
        # 发送配置更?        self.server_helper.send_frame(
            "3", "configurations_update.json",
            description="集群配置更新"
        )
        
        # 发送主机级参数
        self.server_helper.send_frame(
            "4", "host_level_params.json",
            description="主机级参?
        )
        
        # 发送告警定?        self.server_helper.send_frame(
            "5", "alert_definitions.json",
            description="告警规则定义"
        )
        
        # 验证初始数据请求
        _ = self.server.frames_queue.get(timeout=5)  # 拓扑请求
        _ = self.server.frames_queue.get(timeout=5)  # 元数据请?        _ = self.server.frames_queue.get(timeout=5)  # 配置请求
        _ = self.server.frames_queue.get(timeout=5)  # 主机参数请求
        _ = self.server.frames_queue.get(timeout=5)  # 告警定义请求
        
        # 等待Agent完成注册
        self._wait_for_registration()
        
        # 验证集群状?        cluster = self.initializer.topology_cache["0"]
        self.assertEqual(
            cluster["hosts"][0]["hostName"],
            "c6401.cloud.apache.org",
            "集群主机名不正确"
        )
        
        # 验证元数?        metadata = self.initializer.metadata_cache["0"]
        self.assertEqual(
            metadata["status_commands_to_run"], 
            ("STATUS",),
            "状态命令配置错?
        )
        
        # 验证集群配置
        configs = self.initializer.configurations_cache["0"]
        self.assertEqual(
            configs["configurations"]["zoo.cfg"]["clientPort"],
            "2181",
            "ZooKeeper端口配置错误"
        )
        
        # 发送执行命?        self.server_helper.send_frame(
            destination="/user/commands",
            json_file="execution_commands.json",
            description="命令执行请求"
        )
        
        # 验证命令订阅?        cmd_sub_frame = self.server.frames_queue.get(timeout=5)
        self.server_helper.validate_command_subscribe_frame(cmd_sub_frame)
        
        # 验证心跳?        heartbeat_frame = self.server.frames_queue.get(timeout=5)
        self.server_helper.validate_heartbeat_frame(heartbeat_frame)
        
        # 验证Datanode安装报告 (进行?
        dn_install_progress = self.server.frames_queue.get(timeout=5)
        report = json.loads(dn_install_progress.body)
        self.assertEqual(
            report["clusters"]["0"][0]["roleCommand"], 
            "INSTALL",
            "DATANODE命令类型错误"
        )
        self.assertEqual(
            report["clusters"]["0"][0]["status"], 
            "IN_PROGRESS",
            "DATANODE状态应为进行中"
        )
        
        # 验证Datanode安装报告 (失败)
        dn_install_fail = self.server.frames_queue.get(timeout=5)
        report = json.loads(dn_install_fail.body)
        self.assertEqual(
            report["clusters"]["0"][0]["status"], 
            "FAILED",
            "DATANODE状态应为失?
        )
        
        # 验证主机状态报?        host_status = self.server.frames_queue.get(timeout=5)
        report = json.loads(host_status.body)
        self.assertIn("mounts", report, "主机状态缺少挂载信?)
        
        # 停止Agent
        self.initializer.stop_event.set()
        
        # 发送停止确?        self.server_helper.send_stop_confirmation()
        
        # 等待线程结束
        time.sleep(1)
        
        # 断言最终状?        self.assertFalse(self.initializer.action_queue.is_alive(), "动作队列未停?)
        self.assertFalse(threads["heartbeat"].is_alive(), "心跳线程未停?)
    
    def test_topology_operations(self):
        """测试集群拓扑的动态管理：组件与节点的增删"""
        # 启动Agent
        threads = self._start_agent_threads()
        
        # 完成初始注册序列
        self.server_helper.perform_initial_registration(self.server)
        
        # 发送基础拓扑
        self.server_helper.send_frame(
            "1", "topology_create.json",
            description="基础集群拓扑"
        )
        
        # 等待Agent处理完初始数?        self._wait_for_registration()
        
        # 执行拓扑操作序列
        operations = [
            ("添加组件", "topology_add_component.json"),
            ("添加组件主机", "topology_add_component_host.json"),
            ("添加主机", "topology_add_host.json"),
            ("删除主机", "topology_delete_host.json"),
            ("删除组件", "topology_delete_component.json"),
            ("删除组件主机", "topology_delete_component_host.json"),
            ("删除集群", "topology_delete_cluster.json")
        ]
        
        for desc, file in operations:
            self.server_helper.send_frame(
                destination="/events/topologies",
                json_file=file,
                description=desc
            )
            time.sleep(0.1)  # 保证顺序处理
        
        # 验证最终拓扑状?        expected = self._load_test_json("topology_cache_expected.json")
        
        def validate_topology():
            actual = Utils.get_mutable_copy(self.initializer.topology_cache)
            self.assertDictEqual(actual, expected, "拓扑状态与预期不符")
        
        # 带重试验证，避免时间同步问题
        self.retry_assertion(validate_topology, 5, 0.2)
        
        # 清理
        self.initializer.stop_event.set()
    
    def test_alert_definition_management(self):
        """测试告警定义的动态管理：规则的新增、更新和删除"""
        # 启动Agent
        threads = self._start_agent_threads()
        
        # 完成初始注册序列
        self.server_helper.perform_initial_registration(self.server)
        
        # 发送初始告警定?        self.server_helper.send_frame(
            "5", "alert_definitions_small.json",
            description="初始告警定义"
        )
        
        # 等待Agent处理完初始数?        self._wait_for_registration()
        
        # 执行告警定义操作序列
        operations = [
            ("新增告警定义", "alert_definitions_add.json"),
            ("更新告警定义", "alert_definitions_edit.json"),
            ("删除告警定义", "alert_definitions_delete.json")
        ]
        
        for desc, file in operations:
            self.server_helper.send_frame(
                destination="/user/alert_definitions",
                json_file=file,
                description=desc
            )
            time.sleep(0.1)  # 保证顺序处理
        
        # 验证最终告警定?        expected = self._load_test_json("alert_definition_expected.json")
        
        def validate_alerts():
            actual = Utils.get_mutable_copy(self.initializer.alert_definitions_cache)
            self.assertDictEqual(actual, expected, "告警定义与预期不?)
        
        # 带重试验?        self.retry_assertion(validate_alerts, 5, 0.2)
        
        # 清理
        self.initializer.stop_event.set()
    
    def retry_assertion(self, assertion_func, max_retries=5, delay=0.1):
        """带重试的断言机制，处理异步操作的同步问题"""
        last_exception = None
        for _ in range(max_retries):
            try:
                assertion_func()
                return
            except AssertionError as e:
                last_exception = e
                time.sleep(delay)
        if last_exception:
            raise last_exception


class StompServerHelper:
    """STOMP服务器交互辅助工具，简化测试代?""
    
    def __init__(self, stomp_server):
        self.server = stomp_server
        self.test_data_dir = os.path.join(
            os.path.dirname(__file__), 
            "test_data", 
            "stomp_responses"
        )
    
    def load_test_json(self, filename):
        """加载指定JSON测试数据文件"""
        filepath = os.path.join(self.test_data_dir, filename)
        with open(filepath, "r") as f:
            return json.load(f)
    
    def send_frame(self, correlation_id="", json_file="", 
                 destination="/user/", description=""):
        """发送STOMP帧到Agent"""
        if not json_file:
            body = ""
        else:
            body = json.dumps(self.load_test_json(json_file))
        
        frame = Frame(
            "MESSAGE",
            headers={
                "destination": destination,
                "correlationId": correlation_id 
            },
            body=body
        )
        self.server.topic_manager.send(frame)
    
    def validate_connect_frame(self, frame):
        """验证STOMP连接?""
        self.assertEqual(frame.cmd, "CONNECT", 
                      "初始帧应为CONNECT命令")
        self.assertIn("host", frame.headers, 
                   "CONNECT帧缺少host?)
    
    def validate_user_subscribe_frame(self, frame):
        """验证用户订阅?""
        self.assertEqual(frame.cmd, "SUBSCRIBE", 
                      "第二帧应为SUBSCRIBE命令")
        self.assertEqual(frame.headers["destination"], "/user/", 
                      "订阅目标应为/user/")
    
    def validate_registration_frame(self, frame):
        """验证注册?""
        self.assertEqual(frame.cmd, "SEND", 
                      "第三帧应为SEND命令")
        self.assertEqual(frame.headers["destination"], "/register", 
                      "注册目标应为/register")
        
        # 验证注册内容
        payload = json.loads(frame.body)
        self.assertIn("responseId", payload, "注册缺少responseId")
        self.assertIn("hostname", payload, "注册缺少hostname")
    
    def send_registration_response(self):
        """发送注册成功响?""
        frame = Frame(
            "MESSAGE",
            headers={"destination": "/user/", "correlationId": "0"},
            body=json.dumps({
                "registrationResponse": {
                    "status": "COMPLETE",
                    "hostId": "host-001",
                    "agentId": "agent-001"
                }
            })
        )
        self.server.topic_manager.send(frame)
    
    def validate_command_subscribe_frame(self, frame):
        """验证命令订阅?""
        self.assertEqual(frame.cmd, "SUBSCRIBE", 
                      "命令帧应为SUBSCRIBE命令")
        self.assertEqual(frame.headers["destination"], "/commands", 
                      "订阅目标应为/commands")

    def validate_heartbeat_frame(self, frame):
        """验证心跳?""
        self.assertEqual(frame.cmd, "SEND", 
                      "心跳帧应为SEND命令")
        self.assertEqual(frame.headers["destination"], "/heartbeat", 
                      "心跳目标应为/heartbeat")
    
    def validate_host_status_frame(self, frame):
        """验证主机状态帧"""
        self.assertEqual(frame.cmd, "SEND", 
                      "主机状态帧应为SEND命令")
        self.assertEqual(frame.headers["destination"], "/host_status", 
                      "状态目标应?host_status")
        
        payload = json.loads(frame.body)
        self.assertIn("hostHealth", payload, "状态缺少hostHealth字段")
    
    def send_stop_confirmation(self):
        """发送停止确?""
        frame = Frame(
            "MESSAGE",
            headers={"destination": "/user/", "correlationId": "stop-ack"},
            body=json.dumps({"status": "STOPPED"})
        )
        self.server.topic_manager.send(frame)
    
    def perform_initial_registration(self, server):
        """执行初始化注册序?""
        connect_frame = server.frames_queue.get(timeout=5)
        self.validate_connect_frame(connect_frame)
        
        users_frame = server.frames_queue.get(timeout=5)
        self.validate_user_subscribe_frame(users_frame)
        
        reg_frame = server.frames_queue.get(timeout=5)
        self.validate_registration_frame(reg_frame)
        
        self.send_registration_response()
