#!/usr/bin/env python3
"""
高级 STOMP 传输层实�?提供可靠、高效的消息传输功能
支持连接池、多路复用、SSL/TLS 加密、断线重连等功能
"""

import logging
import socket
import ssl
import time
import random
import math
import threading
import errno
from io import BytesIO
import re
from collections import OrderedDict

import cloud_stomp.exception as exception
import cloud_stomp.listener
import cloud_stomp.utils as utils

log = logging.getLogger("stomp.py")

__all__ = ["BaseTransport", "Transport", "ConnectionPool"]

class BaseTransport(cloud_stomp.listener.Publisher):
    """
    STOMP 协议基础传输�?    提供监听器管理、心跳检测、消息处理等核心功能
    
    :param bool auto_decode: 自动解码消息内容 (默认�?True)
    """
    
    # 内容长度解析正则
    __content_length_re = re.compile(
        rb"^content-length[:]\s*(?P<value>[0-9]+)", re.MULTILINE | re.IGNORECASE
    )
    
    # 消息头结束标记正�?    __header_end_re = re.compile(rb"\n\n|\r\n\r\n", re.MULTILINE)

    def __init__(self, auto_decode=True):
        self.__recvbuf = bytearray()
        self.listeners = OrderedDict()
        self.running = False
        self.connected = False
        self.connection_error = False
        self.__receipts = {}
        self.__disconnect_receipt = None
        self.__auto_decode = auto_decode
        self.__connect_condition = threading.Condition()
        self.__send_condition = threading.Condition()
        self.__thread_exit_condition = threading.Condition()
        self.__thread_exited = False
        self.create_thread_fc = utils.default_create_thread
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'reconnect_attempts': 0
        }

    def start(self):
        """启动连接并开始消息接�?""
        if self.running:
            return
            
        self.running = True
        self.attempt_connection()
        self.notify("connecting")
        self.receiver_thread = self.create_thread_fc(self.__receiver_loop)
        self.receiver_thread.name = f"StompRecv-{threading.get_ident()}"

    def stop(self, timeout=5.0):
        """安全停止连接"""
        if not self.running:
            return
            
        self.running = False
        
        # 等待接收线程退�?        if self.receiver_thread and self.receiver_thread.is_alive():
            with self.__thread_exit_condition:
                self.receiver_thread.join(timeout)
                if self.receiver_thread.is_alive():
                    log.warning("Receiver thread did not exit in time")

    def is_connected(self):
        """检查连接状�?""
        return self.connected

    def set_connected(self, connected):
        """更新连接状态并通知等待线程"""
        with self.__connect_condition:
            prev_state = self.connected
            self.connected = connected
            
            # 连接状态变化时通知
            if connected != prev_state:
                self.__connect_condition.notify_all()

    # ====================== 消息处理 ======================
    def process_frame(self, frame_str):
        """
        处理接收到的完整�?        
        :param bytes frame_str: 原始帧数�?        """
        try:
            frame = utils.parse_frame(frame_str)
            if not frame:
                return
                
            frame_type = frame.cmd.lower()
            
            if log.isEnabledFor(logging.DEBUG):
                log.debug(
                    "Received %s frame: headers=%r, body_size=%d",
                    frame_type, 
                    frame.headers, 
                    len(frame.body)
                )
            
            # 预处理消息帧
            if frame_type == "message":
                (frame.headers, frame.body) = self.notify("before_message", frame.headers, frame.body)
            
            # 处理特定帧类�?            handler = getattr(self, f"_handle_{frame_type}_frame", None)
            if handler:
                handler(frame)
            else:
                self._handle_default_frame(frame_type, frame.headers, frame.body)
                
            self.stats['messages_received'] += 1
            
        except Exception as e:
            log.error("Error processing frame: %s", e, exc_info=True)

    def _handle_connected_frame(self, frame):
        """处理 CONNECTED �?""
        self.set_connected(True)
        self.notify("connected", frame.headers, frame.body)

    def _handle_message_frame(self, frame):
        """处理 MESSAGE �?""
        self.notify("message", frame.headers, frame.body)

    def _handle_receipt_frame(self, frame):
        """处理 RECEIPT �?""
        receipt_id = frame.headers.get("receipt-id")
        if not receipt_id:
            log.warning("Received RECEIPT frame without receipt-id")
            return
            
        receipt_value = self.__receipts.get(receipt_id)
        if receipt_value is not None:
            # 通知等待发送的线程
            with self.__send_condition:
                del self.__receipts[receipt_id]
                self.__send_condition.notify_all()
                
            # 如果是断开连接�?receipt
            if receipt_id == self.__disconnect_receipt:
                self.disconnect_socket()
                
        self.notify("receipt", frame.headers, frame.body)

    def _handle_error_frame(self, frame):
        """处理 ERROR �?""
        # 通知连接等待线程
        with self.__connect_condition:
            self.connection_error = True
            self.__connect_condition.notify_all()
            
        self.notify("error", frame.headers, frame.body)

    def _handle_heartbeat_frame(self, frame):
        """处理心跳�?""
        self.notify("heartbeat")
        self.stats['heartbeats_received'] = self.stats.get('heartbeats_received', 0) + 1

    def _handle_default_frame(self, frame_type, headers, body):
        """处理未定义处理器的帧类型"""
        self.notify(frame_type, headers, body)
        log.warning("Unhandled frame type: '%s'", frame_type)

    # ====================== 消息监听器管�?======================
    def set_listener(self, name, listener):
        """添加监听�?""
        self.listeners[name] = listener

    def remove_listener(self, name):
        """移除监听�?""
        if name in self.listeners:
            del self.listeners[name]

    def get_listener(self, name):
        """获取监听�?""
        return self.listeners.get(name)

    def notify(self, event, headers=None, body=None):
        """
        通知所有监听器事件
        
        :param str event: 事件类型
        :param dict headers: 消息�?        :param bytes body: 消息�?        :returns: 处理后的消息头和消息�?        """
        results = []
        for name, listener in self.listeners.items():
            if not listener:
                continue
                
            handler = getattr(listener, f"on_{event}", None)
            if not handler:
                continue
                
            try:
                if event in ("connecting", "disconnected"):
                    result = handler()
                elif event == "heartbeat":
                    result = handler()
                else:
                    result = handler(headers, body)
                results.append(result)
            except Exception as e:
                log.error("Listener %s error in on_%s: %s", name, event, e, exc_info=True)
        
        # 处理返回结果（仅�?message 事件�?        if event == "before_message" and results:
            last_result = results[-1]
            if last_result and isinstance(last_result, tuple) and len(last_result) == 2:
                headers, body = last_result
                
        return (headers, body)

    # ====================== 消息发�?======================
    def transmit(self, frame):
        """
        发�?STOMP �?        
        :param Frame frame: STOMP 帧对�?        """
        # 通知监听器即将发�?        for listener in self.listeners.values():
            if hasattr(listener, "on_sending"):
                frame = listener.on_sending(frame) or frame
        
        # 转换为字�?        frame_lines = utils.convert_frame_to_lines(frame)
        packed_frame = b"\n".join(frame_lines) + b"\x00"
        
        # 记录统计
        self.stats['messages_sent'] += 1
        self.stats['bytes_sent'] += len(packed_frame)
        
        # 发送日�?        log_data = {
            'command': frame.cmd,
            'headers': frame.headers,
            'body_size': len(frame.body)
        }
        if frame.cmd == "CONNECT":
            log_data['headers'] = {k: '***' if 'pass' in k.lower() else v for k, v in frame.headers.items()}
        log.info("Sending frame: %r", log_data)
        
        # 发送消�?        self._send_impl(packed_frame)
        
        # 如果帧需�?receipt，记录并等待
        receipt_id = frame.headers.get("receipt")
        if receipt_id:
            self.__receipts[receipt_id] = frame.cmd
            
            # 对于 DISCONNECT 命令，记�?receipt ID
            if frame.cmd == "DISCONNECT":
                self.__disconnect_receipt = receipt_id
            
            # 等待 receipt
            if frame.headers.get("wait-receipt") == "true":
                self.wait_for_receipt(receipt_id, timeout=10.0)
    
    def wait_for_receipt(self, receipt_id, timeout=5.0):
        """等待指定 receipt 的确�?""
        with self.__send_condition:
            while receipt_id in self.__receipts and self.running:
                remaining = self.__send_condition.wait(timeout=timeout)
                if not remaining and receipt_id in self.__receipts:
                    raise exception.ReceiptTimeoutException(f"Timeout waiting for receipt {receipt_id}")

    def _send_impl(self, packed_frame):
        """实际发送实现（由子类实现）"""
        raise NotImplementedError("Subclasses must implement _send_impl")

    # ====================== 接收核心 ======================
    def __receiver_loop(self):
        """接收消息的主循环"""
        log.info("Starting receiver thread")
        try:
            while self.running:
                try:
                    if not self.is_connected():
                        time.sleep(0.1)
                        self.attempt_connection()
                        continue
                        
                    frames = self._receive()
                    for frame in frames:
                        self.process_frame(frame)
                        
                except exception.ConnectionClosedException:
                    self._handle_connection_closed()
                    
                except Exception as e:
                    log.error("Receiver loop error: %s", e, exc_info=True)
                    time.sleep(1)  # 避免快速循环错�?                    
        finally:
            self._cleanup()
            with self.__thread_exit_condition:
                self.__thread_exited = True
                self.__thread_exit_condition.notify_all()
            log.info("Receiver thread exited")

    def _handle_connection_closed(self):
        """处理连接关闭事件"""
        if self.running:
            self.notify("disconnected")
            self.__recvbuf.clear()
            self.set_connected(False)
            self.stats['disconnects'] = self.stats.get('disconnects', 0) + 1

    def _receive(self):
        """接收消息返回消息帧列�?""
        try:
            # 接收数据
            data = self._recv_impl()
            if not data:
                raise exception.ConnectionClosedException()
                
            # 记录统计
            self.stats['bytes_received'] += len(data)
            
            # 添加到缓冲区
            self.__recvbuf.extend(data)
            
            # 处理完整�?            frames = []
            while self.running:
                # 查找帧结束位�?                end_pos = self.__find_frame_end()
                if end_pos < 0:
                    break
                    
                # 提取完整�?                frame = bytes(self.__recvbuf[:end_pos])
                del self.__recvbuf[:end_pos]
                
                # 移除帧结束符后的空白字符
                while self.__recvbuf and self.__recvbuf[0] in (0, 10, 13):
                    del self.__recvbuf[0]
                    
                frames.append(frame)
                
            return frames
            
        except socket.timeout:
            return []  # 超时无数据正�?        except Exception as e:
            log.error("Receive error: %s", e, exc_info=True)
            raise

    def __find_frame_end(self):
        """在缓冲区中查找完整帧结束位置"""
        # 优先使用明确的帧结束�?        nul_pos = self.__recvbuf.find(b'\x00')
        if nul_pos >= 0:
            return nul_pos
            
        # 对于可能缺失结束符的消息，尝试内容长�?        header_end_match = self.__header_end_re.search(self.__recvbuf)
        if header_end_match:
            header_end = header_end_match.end()
            
            # 检查内容长�?            content_match = self.__content_length_re.search(self.__recvbuf[:header_end])
            if content_match:
                try:
                    content_length = int(content_match.group("value"))
                    frame_end = header_end + content_length
                    if frame_end <= len(self.__recvbuf):
                        return frame_end
                except ValueError:
                    log.warning("Invalid content-length value")
                    
        return -1  # 未找到完整帧

    # ====================== 抽象方法 ======================
    def _send_impl(self, encoded_frame):
        """发送实现（子类重载�?""
        raise NotImplementedError("Subclasses must implement _send_impl")

    def _recv_impl(self):
        """接收实现（子类重载）"""
        raise NotImplementedError("Subclasses must implement _recv_impl")

    def attempt_connection(self):
        """尝试连接（子类重载）"""
        raise NotImplementedError("Subclasses must implement attempt_connection")

    def disconnect_socket(self):
        """断开连接（子类重载）"""
        self.set_connected(False)

    def _cleanup(self):
        """清理资源（子类重载）"""
        pass

    # ====================== 实用方法 ======================
    def wait_for_connection(self, timeout=10.0):
        """等待连接建立"""
        with self.__connect_condition:
            if self.is_connected():
                return True
                
            return self.__connect_condition.wait(timeout)

    def override_threading(self, create_thread_fc):
        """自定义线程创建函�?""
        self.create_thread_fc = create_thread_fc
        
    def get_stats(self):
        """获取连接统计信息"""
        return self.stats.copy()


class Transport(BaseTransport):
    """
    STOMP 传输实现 - 处理底层 socket 连接
    支持自动重连、SSL/TLS 加密、心跳保持等功能
    
    :param list host_and_ports: 主机端口列表 [(host, port), ...]
    :param float reconnect_initial: 初始重连延时 (�?
    :param float reconnect_backoff: 重连退避因�?    :param float reconnect_max: 最大重连延�?(�?
    :param int reconnect_attempts: 最大重连尝试次�?    :param float connect_timeout: 连接超时时间 (�?
    :param dict ssl_context: SSL 上下文配�?    :param dict keepalive: 心跳保持配置
    :param str vhost: 虚拟主机�?    """
    
    # 不同操作系统的心跳配�?    KEEPALIVE_OPTIONS = {
        'linux': {
            'enable_opt': (socket.SOL_SOCKET, socket.SO_KEEPALIVE),
            'idle_opt': (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE),
            'intvl_opt': (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL),
            'cnt_opt': (socket.IPPROTO_TCP, socket.TCP_KEEPCNT)
        },
        'darwin': {
            'enable_opt': (socket.SOL_SOCKET, socket.SO_KEEPALIVE),
            'idle_opt': (socket.IPPROTO_TCP, 0x10),  # TCP_KEEPALIVE
        },
        'windows': {
            'enable_opt': (socket.SOL_SOCKET, socket.SO_KEEPALIVE),
            'idle_opt': (socket.IPPROTO_TCP, 0x03)  # TCP_KEEPALIVE
        }
    }
    
    def __init__(
        self,
        host_and_ports=None,
        reconnect_initial=0.5,
        reconnect_backoff=1.5,
        reconnect_max=60.0,
        reconnect_attempts=5,
        connect_timeout=10.0,
        ssl_context=None,
        keepalive=None,
        vhost=None,
        auto_decode=True
    ):
        super().__init__(auto_decode)
        
        # 连接配置
        self.host_and_ports = host_and_ports or [("localhost", 61613)]
        self.current_host_port = None
        self.connect_timeout = connect_timeout
        self.vhost = vhost
        self.ssl_context = ssl_context or {}
        
        # 重连配置
        self.reconnect_initial = reconnect_initial
        self.reconnect_backoff = reconnect_backoff
        self.reconnect_max = reconnect_max
        self.reconnect_attempts = reconnect_attempts
        self.next_reconnect_delay = reconnect_initial
        
        # keepalive 配置
        self.keepalive = keepalive
        if keepalive and not self.KEEPALIVE_OPTIONS:
            log.warning("Keepalive not supported on this platform")
            self.keepalive = None
            
        # Socket 资源
        self.socket = None
        self.__socket_lock = threading.RLock()

    def _create_socket(self):
        """创建并配置新�?socket"""
        with self.__socket_lock:
            # 创建基本 socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout)
            
            # 应用 keepalive 配置
            if self.keepalive:
                self._apply_keepalive(sock)
                
            return sock

    def _apply_keepalive(self, sock):
        """�?socket 应用 keepalive 配置"""
        if not self.keepalive:
            return
            
        os_name = utils.get_os_name()
        ka_config = self.KEEPALIVE_OPTIONS.get(os_name)
        if not ka_config:
            log.warning("Keepalive not supported on OS: %s", os_name)
            return
            
        try:
            # 启用 keepalive
            if 'enable_opt' in ka_config:
                level, opt = ka_config['enable_opt']
                sock.setsockopt(level, opt, 1)
                
            # 设置参数
            params = {
                'idle_opt': self.keepalive.get('idle', 60),
                'intvl_opt': self.keepalive.get('interval', 10),
                'cnt_opt': self.keepalive.get('count', 5),
            }
            
            for key, default in params.items():
                if key in ka_config and key in self.keepalive:
                    level, opt = ka_config[key]
                    value = self.keepalive.get(key, default)
                    sock.setsockopt(level, opt, value)
                    log.debug("Set keepalive %s=%d", key, value)
                    
        except Exception as e:
            log.error("Error setting keepalive: %s", e)

    def _wrap_ssl(self, sock, host):
        """�?socket 包装�?SSL socket"""
        if not self.ssl_context:
            return sock
            
        try:
            context = self.ssl_context.get('context')
            if context:
                # 使用预创建的 SSL 上下�?                return context.wrap_socket(sock, server_hostname=host)
            else:
                # 创建并配�?SSL 上下�?                ssl_ctx = ssl.create_default_context(
                    cafile=self.ssl_context.get('ca_certs'),
                    capath=self.ssl_context.get('ca_path'),
                    cadata=self.ssl_context.get('ca_data')
                )
                
                # 客户端证�?                if self.ssl_context.get('certfile'):
                    ssl_ctx.load_cert_chain(
                        certfile=self.ssl_context['certfile'],
                        keyfile=self.ssl_context.get('keyfile'),
                        password=self.ssl_context.get('password')
                    )
                    
                # 验证模式
                ssl_ctx.verify_mode = self.ssl_context.get('cert_reqs', ssl.CERT_NONE)
                if ssl_ctx.verify_mode != ssl.CERT_NONE:
                    ssl_ctx.check_hostname = self.ssl_context.get('check_hostname', True)
                    
                return ssl_ctx.wrap_socket(sock, server_hostname=host)
                
        except Exception as e:
            log.error("SSL handshake error: %s", e)
            self.stats['ssl_errors'] = self.stats.get('ssl_errors', 0) + 1
            raise

    def attempt_connection(self):
        """尝试连接到服务器"""
        if self.is_connected():
            return
            
        self.stats['reconnect_attempts'] += 1
        self.stats['last_reconnect'] = time.time()
        
        for attempt in range(1, self.reconnect_attempts + 1):
            for host, port in self.host_and_ports:
                try:
                    if self.socket:
                        self._cleanup_socket()
                        
                    # 创建新连�?                    self._create_connection(host, port)
                    self.stats['successful_connects'] = self.stats.get('successful_connects', 0) + 1
                    self.next_reconnect_delay = self.reconnect_initial
                    return
                    
                except Exception as e:
                    log.warning(
                        "Connection failed to %s:%d (attempt %d): %s",
                        host, port, attempt, e
                    )
                    self.stats['failed_connects'] = self.stats.get('failed_connects', 0) + 1
                    time.sleep(0.1)  # 主机间短暂延�?            
            # 计算下次重连延迟
            self._adjust_reconnect_delay()
            
            # 等待重连
            log.info("Waiting %.2fs before next reconnect attempt", self.next_reconnect_delay)
            start_time = time.time()
            while time.time() - start_time < self.next_reconnect_delay and self.running:
                time.sleep(0.1)
        
        # 所有尝试失�?        self.stats['last_reconnect_fail'] = time.time()
        raise exception.ConnectFailedException(
            f"Failed to connect after {self.reconnect_attempts} attempts"
        )

    def _create_connection(self, host, port):
        """创建到指定主机的连接"""
        raw_sock = self._create_socket()
        
        # 连接服务�?        log.info("Connecting to %s:%d", host, port)
        raw_sock.connect((host, port))
        
        # 包装�?SSL socket (如果需�?
        if self.ssl_context:
            self.socket = self._wrap_ssl(raw_sock, host)
        else:
            self.socket = raw_sock
            
        self.current_host_port = (host, port)
        self.socket.settimeout(1.0)  # 设置接收超时
        self.set_connected(True)
        log.info("Connection established to %s:%d", host, port)

    def _adjust_reconnect_delay(self):
        """调整重连延迟时间"""
        self.next_reconnect_delay *= self.reconnect_backoff
        if self.next_reconnect_delay > self.reconnect_max:
            self.next_reconnect_delay = self.reconnect_max

    def disconnect_socket(self):
        """安全断开 socket 连接"""
        with self.__socket_lock:
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass  # 忽略关闭错误
                    
                try:
                    self.socket.close()
                except Exception:
                    pass
                    
                self.socket = None
                
            self.set_connected(False)
            super().disconnect_socket()

    def _cleanup_socket(self):
        """清理 socket 资源"""
        try:
            if self.socket:
                self.socket.close()
        except Exception:
            pass
            
        self.socket = None
        self.current_host_port = None

    def _cleanup(self):
        """连接停止时清理资�?""
        self.disconnect_socket()
        self.set_connected(False)
        super()._cleanup()

    # ====================== 核心传输方法 ======================
    def _send_impl(self, packed_frame):
        """发送帧实现"""
        if not self.socket:
            raise exception.NotConnectedException()
            
        with self.__socket_lock:
            try:
                total_sent = 0
                while total_sent < len(packed_frame):
                    sent = self.socket.send(packed_frame[total_sent:])
                    if sent == 0:
                        raise exception.ConnectionClosedException()
                    total_sent += sent
                    
            except (socket.error, OSError) as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR):
                    log.debug("Socket send temporarily blocked")
                else:
                    log.error("Send error: %s", e)
                    self.set_connected(False)
                    raise exception.ConnectionClosedException()
                    
            except Exception as e:
                log.error("Unexpected send error: %s", e)
                self.set_connected(False)
                raise

    def _recv_impl(self):
        """接收数据实现"""
        if not self.socket:
            raise exception.NotConnectedException()
            
        try:
            with self.__socket_lock:
                chunk = self.socket.recv(4096)
                if not chunk:
                    raise exception.ConnectionClosedException()
                return chunk
                
        except (socket.timeout, ssl.SSLWantReadError):
            return b''  # 无数据接收是正常�?            
        except (socket.error, OSError) as e:
            err = getattr(e, 'errno', None)
            if err in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR):
                return b''
                
            # 连接重置或关�?            if err in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
                log.warning("Connection reset: %s", e)
                self.set_connected(False)
                raise exception.ConnectionClosedException()
                
            # 其他错误
            log.error("Receive error: %s", e)
            self.set_connected(False)
            raise
            
        except Exception as e:
            log.error("Unexpected receive error: %s", e)
            self.set_connected(False)
            raise

    def set_ssl_context(self, context):
        """更新 SSL 配置"""
        if context and not hasattr(ssl, 'SSLContext'):
            raise Exception("SSL context requires Python 2.7.9+")
            
        self.ssl_context = context or {}


class ConnectionPool:
    """
    STOMP 连接�?    管理多个传输连接，实现负载均衡和故障转移
    """
    
    def __init__(self, transports):
        """
        :param list transports: 传输对象列表
        """
        self.transports = transports
        self.current_idx = 0
        self.lock = threading.Lock()
        
    def get_transport(self):
        """获取当前可用的传输连�?""
        with self.lock:
            # 循环选择
            self.current_idx = (self.current_idx + 1) % len(self.transports)
            return self.transports[self.current_idx]
            
    def broadcast(self, frame):
        """向所有连接广播帧"""
        results = []
        for transport in self.transports:
            try:
                transport.transmit(frame.copy())
                results.append(True)
            except Exception as e:
                log.error("Broadcast error: %s", e)
                results.append(False)
        return all(results)
        
    def start_all(self):
        """启动所有连�?""
        for transport in self.transports:
            if not transport.running:
                transport.start()
                
    def stop_all(self):
        """停止所有连�?""
        for transport in self.transports:
            if transport.running:
                transport.stop()
