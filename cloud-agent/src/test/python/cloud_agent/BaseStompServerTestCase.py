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

import json
import os
import sys
import time
import unittest
import logging
import socket
import select
import threading
from unittest.mock import patch, MagicMock
from queue import Queue, Empty
from coilmq.util.frames import Frame, FrameBuffer
from coilmq.queue import QueueManager
from coilmq.topic import TopicManager
from coilmq.util import frames
from coilmq.server.socket_server import ThreadedStompServer, StompRequestHandler
from coilmq.store.memory import MemoryQueue
from coilmq.scheduler import FavorReliableSubscriberScheduler, RandomQueueScheduler
from coilmq.protocol import STOMP10

# 设置日志记录
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    stream=sys.stdout
)
logging.getLogger("coilmq").setLevel(logging.WARNING)
logging.getLogger("stomp.py").setLevel(logging.WARNING)


class StompServerTestBase(unittest.TestCase):
    """STOMP服务器测试基�?""
    
    STOMP_PORT = 21613
    SERVER_WAIT_TIME = 0.2  # 服务器启动等待时�?�?
    
    def setUp(self):
        # 初始化客户端列表和服务端
        self.clients = []
        self.server = None
        self.server_address = ("127.0.0.1", self.STOMP_PORT)
        
        # 启动服务器线�?        self.server_ready = threading.Event()
        self.server_thread = threading.Thread(
            target=self._start_stomp_server, 
            name="STOMP-Server-Thread"
        )
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # 等待服务器启�?        self.server_ready.wait()
        logger.info("STOMP server started on %s", self.server_address)

    def _start_stomp_server(self):
        """启动STOMP服务器线�?""
        try:
            self.server = ThreadedStompServer(
                self.server_address,
                StompRequestHandler,
                authenticator=None,
                queue_manager=QueueManager(
                    store=MemoryQueue(),
                    subscriber_scheduler=FavorReliableSubscriberScheduler(),
                    queue_scheduler=RandomQueueScheduler(),
                ),
                topic_manager=TopicManager(),
                protocol=STOMP10
            )
            self.server.allow_reuse_address = True
            self.server_ready.set()
            self.server.serve_forever()
        except Exception as e:
            logger.error("Server startup failed: %s", e)
            self.server_ready.set()
            raise

    def tearDown(self):
        """清理测试资源"""
        # 关闭所有客户端连接
        for client in self.clients:
            try:
                client.disconnect()
                client.close()
            except Exception:
                pass
        
        # 关闭服务�?        if self.server:
            try:
                self.server.server_close()
            except Exception:
                pass
        
        # 确保服务器线程已停止
        if self.server_thread.is_alive():
            self.server.server_socket.close()
            self.server_thread.join(1)
        
        logger.info("STOMP server stopped")

    def create_stomp_client(self):
        """创建并返回一个新的STOMP测试客户�?""
        client = StompTestClient(self.server_address)
        self.clients.append(client)
        return client

    def load_test_resource(self, filename):
        """加载测试资源文件"""
        file_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 
            "resources", 
            "stomp", 
            filename
        )
        
        with open(file_path) as f:
            if file_path.endswith('.json'):
                return json.load(f)
            return f.read()
    
    def assert_with_retries(self, assertion_func, max_retries=5, delay=0.2):
        """带重试的断言"""
        for _ in range(max_retries):
            try:
                assertion_func()
                return
            except AssertionError:
                time.sleep(delay)
        assertion_func()


class StompConnectionTests(StompServerTestBase):
    """测试STOMP连接功能"""
    
    def test_basic_client_connection(self):
        """测试基本客户端连�?""
        client = self.create_stomp_client()
        
        # 客户端连接服务器
        client.connect()
        
        # 验证收到CONNECTED�?        frame = client.receive_frame(timeout=1)
        self.assertIsNotNone(frame, "No response received from server")
        self.assertEqual(frame.cmd, frames.CONNECTED, "Did not receive expected CONNECTED frame")
    
    def test_multiple_client_connections(self):
        """测试多个客户端连�?""
        clients = [self.create_stomp_client() for _ in range(3)]
        
        for client in clients:
            client.connect()
            frame = client.receive_frame(timeout=1)
            self.assertEqual(frame.cmd, frames.CONNECTED)

    def test_invalid_connect_frame(self):
        """测试无效的CONNECT�?""
        client = self.create_stomp_client()
        
        # 发送无效帧（缺少必要头部）
        client.send_frame(Frame(frames.CONNECT))
        
        # 验证被断开连接
        with self.assertRaises(Empty):
            client.receive_frame(timeout=1)
    
    def test_goodbye_message_disconnect(self):
        """测试断开连接消息"""
        client = self.create_stomp_client()
        client.connect()
        
        # 客户端断开连接
        client.disconnect()
        
        # 验证连接关闭（接收线程停止）
        client.receive_thread.join(0.5)
        self.assertFalse(client.receive_thread.is_alive())


class MessageDeliveryTests(StompServerTestBase):
    """测试消息交付功能"""
    
    def test_point_to_point_messaging(self):
        """测试点对点消息交�?""
        # 创建客户�?        sender = self.create_stomp_client()
        receiver = self.create_stomp_client()
        queue_name = "/queue/test-queue"
        
        # 连接服务�?        sender.connect()
        receiver.connect()
        receiver.receive_frame()  # Skip CONNECTED frame
        
        # 订阅队列
        receiver.subscribe(queue_name)
        
        # 发送消�?        test_message = "Test point-to-point message"
        sender.send(queue_name, test_message)
        
        # 接收消息
        frame = receiver.receive_frame(timeout=2)
        self.assertIsNotNone(frame, "No message received")
        self.assertEqual(frame.cmd, frames.MESSAGE, "Expected MESSAGE frame")
        self.assertEqual(frame.body, test_message, "Received message does not match sent")
    
    def test_publish_subscribe_messaging(self):
        """测试发布-订阅消息交付"""
        topic_name = "/topic/test-topic"
        clients = [self.create_stomp_client() for _ in range(3)]
        test_message = "Hello pub/sub world!"
        
        # 所有客户端连接并订阅主�?        for client in clients:
            client.connect()
            client.receive_frame()  # 跳过CONNECTED�?            client.subscribe(topic_name)
        
        # 发送消息（从额外客户端�?        sender = self.create_stomp_client()
        sender.connect()
        sender.send(topic_name, test_message)
        
        # 所有订阅者应收到消息
        for client in clients:
            frame = client.receive_frame(timeout=2)
            self.assertEqual(frame.cmd, frames.MESSAGE)
            self.assertEqual(frame.body, test_message)
    
    def test_message_persistence(self):
        """测试消息持久�?""
        queue_name = "/queue/persistent-queue"
        
        # 发送消息（接收者尚未连接）
        sender = self.create_stomp_client()
        sender.connect()
        sender.send(queue_name, "Persistent message")
        
        # 稍后接收消息
        receiver = self.create_stomp_client()
        receiver.connect()
        receiver.subscribe(queue_name)
        
        frame = receiver.receive_frame(timeout=2)
        self.assertEqual(frame.body, "Persistent message")


class StompTestClient:
    """STOMP测试客户�?""

    def __init__(self, server_addr):
        self.server_addr = server_addr
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(self.server_addr)
        self.connected = True
        self.received_frames = Queue()
        self.frame_buffer = FrameBuffer()
        self.receive_thread = threading.Thread(
            target=self._receive_loop, 
            name=f"Client-Receiver-{id(self)}"
        )
        self.receive_thread.daemon = True
        self.receive_thread.start()
        logger.debug("Created client connected to %s", self.server_addr)
    
    def connect(self, headers=None):
        """连接到STOMP服务�?""
        self.send_frame(Frame(frames.CONNECT, headers=headers))
    
    def send(self, destination, message, headers=None):
        """发送消息到指定目标"""
        headers = headers or {}
        headers["destination"] = destination
        headers["content-length"] = len(message)
        self.send_frame(Frame("SEND", headers=headers, body=message))
    
    def subscribe(self, destination):
        """订阅消息目标"""
        self.send_frame(Frame("SUBSCRIBE", headers={"destination": destination}))
    
    def unsubscribe(self, destination):
        """取消订阅"""
        self.send_frame(Frame("UNSUBSCRIBE", headers={"destination": destination}))
    
    def disconnect(self):
        """断开连接"""
        if self.connected:
            self.send_frame(Frame("DISCONNECT"))
            self.close()
    
    def send_frame(self, frame):
        """发送STOMP�?""
        logger.debug("Sending frame: %s", frame)
        self.socket.send(frame.pack())
    
    def _receive_loop(self):
        """接收消息线程"""
        while self.connected:
            try:
                ready, _, _ = select.select([self.socket], [], [], 0.5)
                if not ready:
                    continue
                
                data = self.socket.recv(4096)
                if not data:
                    break
                
                self.frame_buffer.append(data)
                for frame in self.frame_buffer:
                    logger.debug("Received frame: %s", frame)
                    self.received_frames.put(frame)
            except (socket.error, OSError):
                break
        
        self.connected = False
        self.receive_thread = None
    
    def receive_frame(self, timeout=1):
        """接收一帧消�?""
        try:
            return self.received_frames.get(timeout=timeout)
        except Empty:
            return None
    
    def close(self):
        """关闭客户�?""
        if self.connected:
            self.connected = False
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.socket.close()
        
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(0.5)


class StompProtocolTests(StompServerTestBase):
    """测试STOMP协议实现"""
    
    def test_frame_parsing(self):
        """测试帧解析正确�?""
        client = self.create_stomp_client()
        client.connect()
        
        # 获取初始的CONNECTED�?        connected_frame = client.receive_frame(1)
        self.assertTrue(connected_frame)
        
        # 发送多帧消�?        client.send("/queue/frame-test", "First message")
        client.send("/queue/frame-test", "Second message")
        client.send("/queue/frame-test", "Third message")
        
        # 验证接收
        received_messages = []
        for _ in range(3):
            frame = client.receive_frame(1)
            if frame and frame.cmd == "MESSAGE":
                received_messages.append(frame.body)
        
        self.assertEqual(
            received_messages, 
            ["First message", "Second message", "Third message"]
        )
    
    def test_unhandled_command(self):
        """测试未知命令处理"""
        client = self.create_stomp_client()
        client.connect()
        
        # 发送未知命令帧
        client.send_frame(Frame("UNKNOWN_CMD", headers={"test": "true"}))
        
        # 验证连接被关�?        with self.assertRaises(Empty):
            client.receive_frame(timeout=1)
    
    def test_malformed_frame(self):
        """测试格式错误的帧处理"""
        client = self.create_stomp_client()
        client.connect()
        
        # 发送无效帧（缺少冒号）
        client.socket.send(b"CONNECT\ninvalid-header\n\n\x00")
        
        # 验证连接被关�?        with self.assertRaises(Empty):
            client.receive_frame(timeout=1)


@patch("cloud_agent.security.cloudStompConnection")
class IntegrationTests(StompServerTestBase):
    """测试与上层组件的集成"""
    
    def test_message_acknowledgment(self, mock_conn):
        """测试消息确认机制"""
        # 创建生产�?        producer = self.create_stomp_client()
        producer.connect()
        queue_name = "/queue/ack-test"
        
        # 创建消费者（开启ACK机制�?        consumer = self.create_stomp_client()
        consumer.connect()
        consumer.subscribe(queue_name, ack="client-individual")
        
        # 发送消�?        producer.send(queue_name, "Test ACK message")
        
        # 接收消息
        msg_frame = consumer.receive_frame(timeout=2)
        self.assertIsNotNone(msg_frame)
        self.assertIn("message-id", msg_frame.headers)
        
        # 确认消息
        consumer.send_frame(Frame(
            frames.ACK,
            headers={"message-id": msg_frame.headers["message-id"]}
        ))
        
        # TODO: 后续可以扩展验证消息确实被标记为已消�?
    def test_error_frame_handling(self, mock_conn):
        """测试错误帧处�?""
        client = self.create_stomp_client()
        client.connect()
        
        # 执行无效操作（未订阅发送）
        client.send_frame(Frame("MESSAGE", headers={}, body="Invalid message"))
        
        # 验证收到ERROR�?        error_frame = client.receive_frame(timeout=1)
        self.assertEqual(error_frame.cmd, frames.ERROR)


if __name__ == "__main__":
    unittest.main(failfast=True)

