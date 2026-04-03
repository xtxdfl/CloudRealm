#!/usr/bin/env python3
"""
高级网络 Socket 工厂
提供跨平台的 IPv4/IPv6 双栈支持、智能地址解析和连接优化
支持 TCP/TLS/UDP 协议，具备完善的错误处理和连接调优功能
"""

import socket
import logging
import ipaddress
from typing import Tuple, Optional, Union

# 配置日志
log = logging.getLogger("stomp.socket_factory")

# 连接超时默认值（秒）
DEFAULT_CONNECT_TIMEOUT = 10.0
# 接收缓冲区大小（字节）
DEFAULT_RECV_BUFFER_SIZE = 64 * 1024  # 64KB
# 发送缓冲区大小（字节）
DEFAULT_SEND_BUFFER_SIZE = 64 * 1024  # 64KB

class ManagedSocket:
    """
    封装 socket 对象的高级包装器
    提供连接管理、错误处理和资源自动清理功能
    
    :param socket_type: socket 类型 (默认 socket.SOCK_STREAM)
    :param socket_proto: socket 协议 (默认 0)
    """
    AF_FAMILIES = (socket.AF_INET, socket.AF_INET6)
    
    def __init__(
        self, 
        socket_type: int = socket.SOCK_STREAM,
        socket_proto: int = 0
    ):
        self._sock = None
        self._conn_timeout = DEFAULT_CONNECT_TIMEOUT
        self._socket_type = socket_type
        self._socket_proto = socket_proto
        self._keepalive_params = {}
        self._is_connected = False
        self._last_host = None
        self._last_port = None
        self._stats = {
            'connections': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }
    
    @property
    def raw_socket(self) -> socket.socket:
        """返回底层 socket 对象"""
        return self._sock
    
    @property
    def is_connected(self) -> bool:
        """检查 socket 是否有效连接"""
        if not self._sock:
            return False
        try:
            # 通过非阻塞检查获取当前状态
            self._sock.setblocking(False)
            data = self._sock.recv(1, socket.MSG_PEEK)
            return len(data) != 0 or data is not None
        except (socket.error, BlockingIOError) as e:
            # EAGAIN 或 EWOULDBLOCK 表示连接正常但没有数据
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return True
            # 其他错误表示连接可能已中断
            return False
        finally:
            # 恢复阻塞模式
            if self._sock:
                self._sock.setblocking(True)
    
    def configure_keepalive(
        self, 
        idle: int = 60, 
        interval: int = 10, 
        count: int = 3
    ) -> None:
        """
        配置 TCP keepalive 参数
        :param idle: 首次探测前的空闲时间（秒）
        :param interval: 探测间隔（秒）
        :param count: 最大探测次数
        """
        self._keepalive_params = {
            'idle': idle,
            'interval': interval,
            'count': count
        }
        
    def _apply_socket_options(self):
        """应用 socket 配置选项"""
        if not self._sock:
            return
            
        # 设置 keepalive
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # 平台特定 keepalive 参数
        platform = sys.platform
        try:
            if platform.startswith('linux'):
                self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self._keepalive_params.get('idle', 60))
                self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self._keepalive_params.get('interval', 10))
                self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self._keepalive_params.get('count', 3))
            elif platform == 'darwin' or platform == 'freebsd':
                self._sock.setsockopt(socket.IPPROTO_TCP, 0x10, self._keepalive_params.get('idle', 60))  # TCP_KEEPALIVE
            elif platform == 'win32':
                # Windows 使用不同常量
                self._sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, self._keepalive_params.get('idle', 60)*1000, self._keepalive_params.get('interval', 10)*1000))
        except AttributeError:
            log.warning("Keepalive parameters not supported on this platform")
        
        # 优化缓冲区大小
        try:
            current_recv_buf = self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            if current_recv_buf < DEFAULT_RECV_BUFFER_SIZE:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, DEFAULT_RECV_BUFFER_SIZE)
            
            current_send_buf = self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
            if current_send_buf < DEFAULT_SEND_BUFFER_SIZE:
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, DEFAULT_SEND_BUFFER_SIZE)
        except OSError:
            log.warning("Unable to optimize socket buffers")
    
    def connect(
        self, 
        host: str, 
        port: int, 
        timeout: Optional[float] = None,
        force_ipv6: bool = False,
        force_ipv4: bool = False
    ) -> None:
        """
        连接到指定主机的端口
        :param host: 主机名或IP地址
        :param port: 端口号
        :param timeout: 连接超时时间（秒）
        :param force_ipv6: 强制使用IPv6连接
        :param force_ipv4: 强制使用IPv4连接
        """
        # 清理上一个连接
        if self._sock and self.is_connected:
            self.disconnect()
        
        # 解析主机地址
        resolved_addrs = self._resolve_host(host, force_ipv6, force_ipv4)
        if not resolved_addrs:
            raise socket.error(f"Could not resolve host: {host}")
        
        # 创建新 socket
        address_family = resolved_addrs[0][0]  # 使用第一个地址的协议族
        self._create_socket(address_family)
        
        # 应用配置
        self._apply_socket_options()
        
        # 设置连接超时
        if timeout is not None:
            self._conn_timeout = timeout
        self._sock.settimeout(self._conn_timeout)
        
        # 尝试所有可用地址
        last_exception = None
        for family, addr in resolved_addrs:
            if family != address_family:
                continue  # 只尝试初始选择的协议族
                
            try:
                log.info("Connecting to [%s]:%d via %s", addr[0], port, family)
                self._sock.connect((addr[0], port))
                self._last_host = host
                self._last_port = port
                self._is_connected = True
                self._stats['connections'] += 1
                log.info("Connected to [%s]:%d", addr[0], port)
                return
            except (socket.timeout, socket.error) as e:
                last_exception = e
                log.warning("Failed to connect to [%s]:%d: %s", addr[0], port, e)
                continue
        
        # 所有地址连接失败
        self.close()
        raise last_exception or socket.error(f"Failed to connect to {host}:{port}")
    
    def _resolve_host(
        self, 
        host: str, 
        force_ipv6: bool, 
        force_ipv4: bool
    ) -> list:
        """
        解析主机名，返回可用地址列表
        :param host: 主机名或IP地址
        :return: 排序后的地址列表 [(family, address), ...]
        """
        # 优先尝试作为IP地址解析
        try:
            ip_addr = ipaddress.ip_address(host)
            if ip_addr.version == 6:
                return [(socket.AF_INET6, (host,))]
            else:
                return [(socket.AF_INET, (host,))]
        except ValueError:
            pass  # 不是有效IP地址，继续DNS解析
        
        # DNS 解析
        families = []
        if force_ipv6:
            families.append(socket.AF_INET6)
        elif force_ipv4:
            families.append(socket.AF_INET)
        else:
            families.extend([socket.AF_INET6, socket.AF_INET])
        
        resolved = []
        for family in families:
            try:
                info_list = socket.getaddrinfo(
                    host,
                    None,  # Port not needed for resolution
                    family,
                    self._socket_type,
                    self._socket_proto,
                    socket.AI_ADDRCONFIG | socket.AI_V4MAPPED
                )
                for info in info_list:
                    if len(info) >= 4:
                        resolved.append((info[0], info[4]))
            except socket.gaierror as e:
                log.warning("Address resolution error for family %s: %s", family, e)
        
        # 排序地址 (IPv6 优先)
        def address_sort_key(item):
            family, addr = item
            return 0 if family == socket.AF_INET6 else 1
                    
        return sorted(resolved, key=address_sort_key)
    
    def _create_socket(self, family: int) -> None:
        """创建特定协议族的 socket"""
        # 关闭现有 socket
        self.close()
        
        # 创建新 socket
        self._sock = socket.socket(family, self._socket_type, self._socket_proto)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 尝试开启 IPv6 Only 选项
        if family == socket.AF_INET6:
            try:
                self._sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            except AttributeError:
                log.debug("IPv6 only option not available")
    
    def reconnect(self, timeout: Optional[float] = None) -> bool:
        """
        重新连接到上次成功的主机/端口
        :param timeout: 连接超时时间（秒）
        :return: 是否重新连接成功
        """
        if not self._last_host or not self._last_port:
            log.error("No previous connection to reconnect")
            return False
            
        try:
            self.connect(self._last_host, self._last_port, timeout=timeout)
            return True
        except socket.error as e:
            log.error("Reconnect failed: %s", e)
            return False
    
    def disconnect(self) -> None:
        """优雅断开连接"""
        if not self._sock:
            return
            
        try:
            # 尝试优雅关闭
            self._sock.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass  # 可能已经关闭
            
        log.info("Disconnected from [%s]:%d", self._last_host, self._last_port)
        self._is_connected = False
        self.close()
    
    def close(self) -> None:
        """关闭 socket 并清理资源"""
        if self._sock:
            try:
                self._sock.close()
            except socket.error:
                pass
            finally:
                self._sock = None
                self._is_connected = False

    def send(
        self, 
        data: Union[bytes, bytearray], 
        flags: int = 0
    ) -> int:
        """
        发送数据
        :param data: 要发送的数据
        :param flags: socket 发送标志
        :return: 实际发送的字节数
        """
        if not self.is_connected:
            raise ConnectionError("Socket not connected")
            
        try:
            sent = self._sock.send(data, flags)
            self._stats['bytes_sent'] += sent
            return sent
        except (socket.error, OSError) as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return 0  # 非阻塞模式下暂时无法发送
            log.error("Send error: %s", e)
            self.disconnect()
            raise
    
    def recv(
        self, 
        buffersize: int, 
        flags: int = 0
    ) -> bytes:
        """
        接收数据
        :param buffersize: 最大接收字节数
        :param flags: socket 接收标志
        :return: 接收到的数据
        """
        if not self.is_connected:
            raise ConnectionError("Socket not connected")
            
        try:
            data = self._sock.recv(buffersize, flags)
            if not data:
                self.disconnect()
            else:
                self._stats['bytes_received'] += len(data)
            return data
        except (socket.error, OSError) as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return b''  # 非阻塞模式下无数据可读
            log.error("Receive error: %s", e)
            self.disconnect()
            raise
    
    def get_stats(self) -> dict:
        """获取 socket 使用统计信息"""
        return self._stats.copy()


def create_tcp_socket() -> ManagedSocket:
    """
    创建优化的 TCP Socket
    :return: 配置好的 ManagedSocket 对象
    """
    sock = ManagedSocket(socket.SOCK_STREAM)
    sock.configure_keepalive(idle=30, interval=15, count=5)
    return sock


def create_udp_socket() -> ManagedSocket:
    """
    创建优化的 UDP Socket
    :return: 配置好的 ManagedSocket 对象
    """
    return ManagedSocket(socket.SOCK_DGRAM)


# 兼容旧版函数的封装
def get_socket(
    host: str, 
    port: int, 
    timeout: float = DEFAULT_CONNECT_TIMEOUT,
    socket_type: int = socket.SOCK_STREAM,
    **kwargs
) -> ManagedSocket:
    """
    [兼容函数] 创建并连接 socket
    
    :param host: 主机名或 IP 地址
    :param port: 端口号
    :param timeout: 连接超时时间（秒）
    :param socket_type: socket 类型 (默认 TCP)
    :return: 已连接的 ManagedSocket 对象
    """
    sock = ManagedSocket(socket_type)
    
    # 设置超时
    real_timeout = timeout or DEFAULT_CONNECT_TIMEOUT
    
    # 尝试连接
    try:
        sock.connect(host, port, timeout=real_timeout, **kwargs)
        return sock
    except Exception as e:
        sock.close()
        raise ConnectionError(f"Failed to connect to {host}:{port}") from e
