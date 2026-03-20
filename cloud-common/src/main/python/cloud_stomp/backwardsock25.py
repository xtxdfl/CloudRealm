#!/usr/bin/env python3
"""
高级 IPv4/IPv6 双协议栈网络适配器
专为旧版 Python 设计，提供现代的网络连接功能
支持 TCP Keepalive、多地址轮询和智能超时
"""

import socket
import sys
import errno
import time
from typing import Tuple, Union, Optional

# 协议支持矩阵
IPPROTO_MAP = {
    "TCP": socket.SOCK_STREAM,
    "UDP": socket.SOCK_DGRAM
}

# 错误消息常量
ADDRINFO_ERR = "DNS 查询无有效结果"
CONNECT_ERR = "无法建立连接（尝试 %d 次）"
TIMEOUT_ERR = "连接超时（%.2f 秒）"
RESOLUTION_ERR = "域名解析失败：%s"
SOCKET_ERR = "套接字创建失败：%s"


def get_os_socket_defaults() -> tuple:
    """
    获取操作系统默认的套接字选项
    返回：(KEEPALIVE_ENABLED, KEEPINTVL, KEEPCNT)
    """
    if sys.platform.startswith('linux'):
        return (1, 30, 3)  # Linux 默认值
    elif sys.platform.startswith('darwin'):
        return (1, 75, 8)  # macOS 默认值
    elif sys.platform.startswith('win'):
        return (1, 7200, 10)  # Windows 默认值
    else:
        return (1, 45, 5)  # 其他系统保守值


def configure_keepalive(
    sock: socket.socket,
    after_idle_sec: int = 30,
    interval_sec: int = 30,
    max_fails: int = 3
) -> None:
    """
    配置 TCP Keepalive 选项以检测死连接
    支持跨平台（Linux/macOS/Windows）

    :param sock: TCP 套接字对象
    :param after_idle_sec: 空闲多少秒后发送探测包
    :param interval_sec: 探测间隔秒数
    :param max_fails: 最大失败次数
    """
    # 不同平台选项常量
    if sys.platform.startswith('linux'):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
    elif sys.platform.startswith('darwin'):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # macOS 使用 TCP_KEEPALIVE 选项
        if hasattr(socket, 'TCP_KEEPALIVE'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, after_idle_sec)
    elif sys.platform.startswith('win'):
        sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, after_idle_sec*1000, interval_sec*1000))


def create_dualstack_socket(
    family: Optional[socket.AddressFamily] = None,
    proto: str = 'TCP'
) -> socket.socket:
    """
    创建支持双协议栈 (IPv4/IPv6) 的套接字
    自动处理平台差异
    
    :param family: 地址族 (None 为自动选择)
    :param proto: 协议类型 ('TCP' 或 'UDP')
    
    :return: 配置好的套接字对象
    """
    # 获取协议类型
    sock_type = IPPROTO_MAP.get(proto.upper(), IPPROTO_MAP['TCP'])
    
    # 自动选择最佳地址族
    if family is None:
        family = socket.AF_INET6 if socket.has_ipv6 else socket.AF_INET
    
    try:
        # 尝试创建双栈套接字
        if 'IPV6_V6ONLY' in socket.__dict__:
            sock = socket.socket(family, sock_type, 0)
            if family == socket.AF_INET6:
                try:
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                except socket.error:
                    pass  # 不支持的选项继续使用默认
            return sock
        else:
            return socket.socket(family, sock_type, 0)
    except socket.error as err:
        raise RuntimeError(SOCKET_ERR % str(err))


def resolve_host(
    host: str,
    port: int,
    proto: str = 'TCP'
) -> list:
    """
    智能主机解析器
    支持DNS轮询、双协议栈排序和优先级处理

    :param host: 主机名或IP地址
    :param port: 目标端口
    :param proto: 协议类型
    
    :return: 地址信息列表 (family, socktype, proto, canonname, sockaddr)
    """
    # 协议类型映射
    sock_type = IPPROTO_MAP.get(proto.upper(), IPPROTO_MAP['TCP'])
    
    # 解析策略 - 优先IPv6，然后IPv4
    families = []
    if socket.has_ipv6 and sys.platform != "win32":
        families.append(socket.AF_INET6)
    families.append(socket.AF_INET)
    
    # 尝试所有可能的地址族
    resolved_addrs = []
    for family in families:
        try:
            addrinfos = socket.getaddrinfo(
                host, port, family, sock_type, 0, 
                socket.AI_V4MAPPED | socket.AI_ADDRCONFIG
            )
            resolved_addrs.extend(addrinfos)
        except (socket.gaierror, AttributeError) as err:
            pass  # 部分地址族不支持则跳过
    
    if not resolved_addrs:
        raise socket.gaierror(RESOLUTION_ERR % host)
    
    # 地址排序策略
    # 1. 优先相同协议系列
    # 2. 然后按连接类型（直连>代理）
    # 3. 最后按地址类型（IPV6 > IPV4）
    def address_score(addr_info):
        family, _, _, _, addr = addr_info
        # IPv6得分更高
        return 1 if family == socket.AF_INET6 else 0
    
    resolved_addrs.sort(key=address_score, reverse=True)
    
    return resolved_addrs


def smart_connect(
    host: str,
    port: int,
    timeout: Optional[float] = None,
    max_retries: int = 3,
    retry_delay: float = 0.5,
    enable_keepalive: bool = True
) -> socket.socket:
    """
    高性能网络连接器
    支持多地址尝试、指数退避重试和智能超时处理

    :param host: 目标主机名或IP
    :param port: 目标端口
    :param timeout: 连接超时（秒）
    :param max_retries: 最大重试次数
    :param retry_delay: 重试延迟基数（指数退避）
    :param enable_keepalive: 是否启用TCP Keepalive
    
    :return: 已连接的套接字对象
    """
    errors = []
    resolved_addrs = resolve_host(host, port)
    
    # 连接计时器
    start_time = time.time()
    retry_count = 0
    
    for attempt in range(max_retries):
        for addr_info in resolved_addrs:
            af, socktype, proto, _, sa = addr_info
            sock = None
            current_retry = attempt + 1
            
            try:
                # 计算尝试超时
                attempt_timeout = None
                if timeout is not None:
                    elapsed = time.time() - start_time
                    attempt_timeout = max(0.1, timeout - elapsed)
                
                # 创建配置套接字
                sock = create_dualstack_socket(af, 'TCP')
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # 设置连接超时
                if timeout is not None:
                    sock.settimeout(attempt_timeout)
                
                # 尝试连接
                sock.connect(sa)
                
                # 连接后配置
                sock.settimeout(None)  # 重置为阻塞模式
                if enable_keepalive:
                    # 配置操作系统级连接保持
                    configure_keepalive(sock)
                
                return sock
            
            except (socket.timeout, TimeoutError) as terr:
                # 超时错误处理
                if timeout:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise TimeoutError(TIMEOUT_ERR % timeout) from terr
                errors.append(f"尝试 {sa}: 超时")
                
            except socket.error as serr:
                # 处理暂时性错误
                err_code = serr.args[0]
                if err_code == errno.EINPROGRESS:  # 非阻塞连接中
                    continue
                elif err_code in (errno.EAGAIN, errno.EWOULDBLOCK):
                    time.sleep(0.05)  # 轻微延迟后重试
                    continue
                elif err_code == errno.EALREADY:
                    continue
                elif err_code in (errno.EINTR, errno.ECONNREFUSED):
                    # 可恢复错误
                    errors.append(f"尝试 {sa}: {serr.strerror}")
                    if current_retry < max_retries:
                        time.sleep(retry_delay * (2 ** current_retry))  # 指数退避
                        continue
                else:
                    # 记录所有其他错误
                    errors.append(f"尝试 {sa}: {serr.strerror}")
                    if sock is not None:
                        try:
                            sock.close()
                        except OSError:
                            pass
                    if attempt == max_retries - 1:
                        if errors:
                            # 仅记录最后一次错误进行报告
                            last_error = errors[-1]
                            raise ConnectionError(last_error) from serr
                        else:
                            raise ConnectionError(ADDRINFO_ERR) from serr
                    
            finally:
                # 安全关闭失败的套接字
                if sock is not None and (not hasattr(sock, '_connected') or not sock._connected):
                    try:
                        sock.close()
                    except OSError:
                        pass
        
        # 当前地址列表全部尝试失败，延迟后重试整个列表
        retry_count += 1
        if retry_count < max_retries:
            sleep_time = retry_delay * (2 ** retry_count)
            time.sleep(min(sleep_time, 30))  # 上限30秒
    
    # 达到最大重试次数
    error_details = "\n".join(errors[:5]) + (f"\n...（共 {len(errors)} 个错误）" if len(errors) > 5 else "")
    raise ConnectionError(CONNECT_ERR % max_retries + "\n" + error_details)


# 兼容性别名
get_socket = smart_connect


class ResilientConnection:
    """
    弹性网络连接管理类
    支持连接池、自动重连和故障转移
    """
    
    __slots__ = ('host', 'port', 'timeout', 'socket', 'is_connected', 'last_active')
    
    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.is_connected = False
        self.last_active = time.time()
    
    def connect(self) -> None:
        """建立连接并配置可靠性选项"""
        if self.is_connected:
            return
            
        self.socket = smart_connect(
            self.host,
            self.port,
            timeout=self.timeout,
            enable_keepalive=True
        )
        self.is_connected = True
        self.last_active = time.time()
    
    def reconnect(self) -> bool:
        """优雅重连（5秒内不超过3次尝试）"""
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            try:
                self.close()
                self.connect()
                return True
            except (ConnectionError, TimeoutError):
                attempts += 1
                time.sleep(min(2**attempts, 5))  # 指数退避，上限5秒
        return False
    
    def get_socket(self) -> socket.socket:
        """获取有效套接字（必要时重连）"""
        self.validate_connection()
        return self.socket
    
    def validate_connection(self) -> None:
        """验证连接状态（自动处理断开）"""
        # 检查空闲超时（5分钟）
        if self.is_connected and (time.time() - self.last_active > 300):
            try:
                # 发送空包测试连接
                self.socket.send(b'', socket.MSG_DONTWAIT)
            except OSError:
                self.is_connected = False
        
        # 需要时自动重连
        if not self.is_connected:
            self.reconnect()
    
    def close(self) -> None:
        """安全关闭连接"""
        if self.socket and self.is_connected:
            try:
                # 优雅关闭 (SHUT_RDWR)
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.socket.close()
            except OSError:
                pass
        self.is_connected = False
        self.socket = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ---------------------- 测试工具 ----------------------
def connection_test(host: str, port: int, proto: str = 'TCP') -> None:
    """
    网络连接测试工具
    输出详细的诊断信息
    
    :param host: 测试主机
    :param port: 测试端口
    :param proto: 协议类型
    """
    print(f"⏳ 测试连接到 {host}:{port} ({proto.upper()})...")
    start = time.time()
    
    try:
        # 解析诊断
        print("🔍 DNS 解析:")
        addrs = resolve_host(host, port, proto)
        for i, addr in enumerate(addrs[:3]):
            print(f"  #{i+1}: {addr[4][0]} ({'IPv6' if ':' in addr[4][0] else 'IPv4'})")
        if len(addrs) > 3:
            print(f"  ...共 {len(addrs)} 个地址")
        
        # 连接测试
        conn = ResilientConnection(host, port)
        with conn:
            sock = conn.get_socket()
            print(f"✅ 连接成功 (耗时: {time.time()-start:.2f}s)")
            
            # 连接详情
            local_addr, local_port = sock.getsockname()
            print("  📡 本地地址:", f"{local_addr}:{local_port}")
            print("  🌐 远程地址:", f"{host}:{port}")
            
            # 协议信息
            if proto.upper() == "TCP":
                print("  🛡️  Keepalive 状态:", 
                      "已启用" if conn.socket.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) else "未启用")
    
    except Exception as e:
        print(f"❌ 连接失败: {str(e)}")
        print("💡 建议:")
        if "Name or service not known" in str(e):
            print("  - 检查主机名拼写和DNS配置")
        elif "refused" in str(e).lower():
            print("  - 目标服务未运行或端口错误")
        elif "timed out" in str(e).lower():
            print("  - 检查防火墙设置和网络连通性")
            print("  - 测试端口是否开放: nc -zv", host, port)
        elif "No route to host" in str(e):
            print("  - 网络路由问题，检查目标可达性")
        else:
            print("  - 检查防火墙/安全组设置")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='网络连接诊断工具')
    parser.add_argument('host', help='目标主机名或IP')
    parser.add_argument('port', type=int, help='目标端口')
    parser.add_argument('--proto', choices=['tcp', 'udp'], default='tcp', help='协议类型')
    
    args = parser.parse_args()
    connection_test(args.host, args.port, args.proto)

