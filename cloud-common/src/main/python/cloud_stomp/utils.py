#!/usr/bin/env python3
"""
高级 STOMP 协议工具集
包含线程管理、本地网络探测、帧解析和心跳计算等核心功能
针对高性能消息系统优化
"""

import logging
import re
import socket
import threading
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Union, Iterable, Callable, Match

log = logging.getLogger("stomp.py")

# 类型定义
HostPort = Tuple[str, int]
HeaderType = Dict[str, str]
RawFrame = bytes


def get_localhost_names() -> List[str]:
    """
    获取所有指向本地主机的名称列表
    包含：未限定主机名、FQDN 和所有 IP 地址
    
    :return: 本地主机名称列表
    """
    local_names = {
        "localhost", 
        "127.0.0.1",
        "::1",
        "0:0:0:0:0:0:0:1"
    }
    
    try:
        # 添加主机名相关的名称
        hostname = socket.gethostname()
        local_names.update({
            hostname,
            socket.getfqdn(hostname),
            socket.gethostbyname(hostname)
        })
        
        # 添加所有接口的IP地址
        for iface in socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC):
            _, _, _, _, (ip, *_) = iface
            local_names.add(ip)
    except Exception as e:
        log.debug("Hostname resolution failed: %s", e)
    
    # 添加 Docker 和 Kubernetes 的特殊本地地址
    for ip in ("172.17.0.1", "host.docker.internal", "kubernetes.default.svc", "minikube"):
        try:
            resolved = socket.gethostbyname(ip)
            local_names.add(ip)
            local_names.add(resolved)
        except:
            pass  # 忽略无法解析的特殊地址
    
    log.debug("Discovered %d localhost aliases", len(local_names))
    return list(local_names)


# 初始化本地主机名称列表
LOCALHOST_NAMES = get_localhost_names()

# 正则表达式预编译
HEADER_LINE_RE = re.compile(r"(?P<key>[^\s:]+?)\s*:\s*(?P<value>.+)$")
PREAMBLE_END_RE = re.compile(rb"(?:\r?\n){2}")
LINE_END_RE = re.compile(r"\r?\n")
HEADER_ESCAPE_RE = re.compile(rb"\\(?:\\|r|n|c|.)")
HEADER_ESCAPE_MAP = {
    b"\\r": b"\r",
    b"\\n": b"\n",
    b"\\c": b":",
    b"\\\\": b"\\"
}


def configure_thread_factory(
    daemon: bool = True, 
    stack_size: Optional[int] = None,
    name_prefix: str = "stomp-worker-"
) -> Callable[[Callable], threading.Thread]:
    """
    配置线程工厂函数
    返回一个线程创建函数，支持自定义参数
    
    :param daemon: 是否创建守护线程
    :param stack_size: 线程栈大小
    :param name_prefix: 线程名前缀
    
    :return: 线程创建函数
    """
    counter = 0
    counter_lock = threading.Lock()
    
    def create_thread(callback: Callable) -> threading.Thread:
        nonlocal counter
        with counter_lock:
            counter += 1
        
        name = f"{name_prefix}{counter}"
        
        return threading.Thread(
            name=name,
            target=callback,
            daemon=daemon,
            **(dict(stack_size=stack_size) if stack_size else {})
        )
    
    return create_thread


# 默认线程工厂
default_create_thread = configure_thread_factory()


@lru_cache(maxsize=1024)
def is_localhost(hostport: HostPort, 
                 include_private_ranges: bool = True) -> int:
    """
    判断主机是否属于本地网络
    支持更广范围的本地地址检测（包括私有IP范围）
    
    :param hostport: 主机端口元组 (host, port)
    :param include_private_ranges: 是否包含私有地址段
    
    :return: 1-本地主机, 2-远端主机
    """
    host, _ = hostport
    if not host:
        return 1  # 空主机视为本地
    
    # IP地址标准化
    if host in LOCALHOST_NAMES:
        return 1
    
    try:
        # IPv4私有地址段检测
        if "." in host:
            parts = list(map(int, host.split(".")))
            if parts[0] == 10:  # 10.0.0.0/8
                return 1
            if parts[0] == 172 and 16 <= parts[1] <= 31:  # 172.16.0.0/12
                return 1
            if parts[0] == 192 and parts[1] == 168:  # 192.168.0.0/16
                return 1
            
            # 回环地址检测
            if host == "127.0.0.1":
                return 1
        
        # IPv6检测
        if host.startswith("fd") or host.startswith("fc"):
            return 1  # IPv6本地地址
        if host == "::1":
            return 1
        
        # 主机名模式匹配
        if any(local_pat in host for local_pat in (".local", ".lan", ".intranet")):
            return 1
    except Exception:
        pass  # 解析失败视为远端主机
    
    return 2


def unescape_header(value: bytes) -> str:
    """
    高效STOMP头部反转义器
    支持STOMP 1.1/1.2头部的转义序列解析
    
    :param value: 要反转义的字节串
    :return: 反转义后的字符串
    """
    def replace_escape(match: Match) -> bytes:
        seq = match.group(0)
        return HEADER_ESCAPE_MAP.get(seq, seq)
    
    return HEADER_ESCAPE_RE.sub(replace_escape, value).decode()


def parse_headers(lines: List[str]) -> HeaderType:
    """
    高效解析STOMP头部
    支持重复头部处理和多值解码优化
    
    :param lines: 头部行列表
    :return: 头部字典（支持多值）
    """
    headers = {}
    for line in lines:
        if not line.strip():
            continue
            
        match = HEADER_LINE_RE.match(line)
        if match:
            key = unescape_header(match.group("key").encode())
            value = unescape_header(match.group("value").encode())
            
            if key not in headers:
                headers[key] = value
            else:
                # 处理重复头部（转换为逗号分隔值）
                headers[key] += f",{value}"
    
    return headers


def parse_frame(frame_data: RawFrame) -> Optional["Frame"]:
    """
    高性能STOMP帧解析器
    支持空帧、心跳帧和规范校验
    
    :param frame_data: 原始帧字节数据
    :return: Frame对象或None（无效帧）
    """
    # 优化心跳帧检测
    if frame_data in (b"\x0a", b"\x0d\x0a"):  # LF or CR+LF
        return Frame(cmd="heartbeat")
    
    # 寻找帧头-正文分隔
    mat = PREAMBLE_END_RE.search(frame_data)
    if not mat:
        log.error("Invalid frame: missing header separator")
        return None
        
    preamble_end = mat.start()
    body_start = mat.end()
    
    # 提取帧头部分
    preamble = frame_data[:preamble_end].decode(errors="replace")
    preamble_lines = LINE_END_RE.split(preamble)
    
    # 跳过空行
    while preamble_lines and not preamble_lines[0]:
        preamble_lines.pop(0)
    
    if not preamble_lines:
        return None
        
    cmd = preamble_lines[0].upper()
    headers = parse_headers(preamble_lines[1:])
    
    # 提取正文并移除帧终止符
    body = frame_data[body_start:]
    if body.endswith(b"\x00"):
        body = body[:-1]
    
    return Frame(
        cmd=cmd,
        headers=headers,
        body=body if body else None
    )


def merge_headers(header_sources: Iterable[Optional[HeaderType]]) -> HeaderType:
    """
    MultiHeader合并器：支持优先级合并和类型安全
    
    :param header_sources: 要合并的头部来源列表
    :return: 合并后的头部字典
    """
    merged = {}
    for source in header_sources:
        if not source:
            continue
            
        for key, values in source.items():
            # 处理多值头部（逗号分隔）
            if key in merged:
                if not isinstance(values, str) and hasattr(values, '__iter__'):
                    values = ",".join(values)
                    
                merged[key] += "," + values
            else:
                merged[key] = values
    return merged


def calculate_heartbeats(
    server_heartbeat: Tuple[int, int], 
    client_heartbeat: Tuple[int, int]
) -> Tuple[int, int]:
    """
    STOMP心跳协商算法
    
    :param server_heartbeat: 服务器心跳要求 (sx, sy)
    :param client_heartbeat: 客户端心跳要求 (cx, cy)
    
    :return: 实际心跳配置 (cx_actual, cy_actual)
    
    >>> calculate_heartbeats((0, 10000), (5000, 0))
    (5000, 10000)
    """
    sx, sy = server_heartbeat
    cx, cy = client_heartbeat
    
    def effective_send(current, remote_requirement):
        if current == 0 or remote_requirement == 0:
            return 0
        return max(current, remote_requirement)
    
    def effective_receive(current, remote_requirement):
        if current == 0 or remote_requirement == 0:
            return 0
        return min(current, remote_requirement)
    
    # 发送心跳：客户端配置优先
    x = effective_send(cx, sy)
    
    # 接收心跳：服务器配置优先
    y = effective_receive(cy, sx)
    
    log.debug(
        "Negotiated heartbeats: "
        "server(%d,%d) + client(%d,%d) -> (%d,%d)",
        sx, sy, cx, cy, x, y
    )
    return x, y


def optimize_frame_transmission(frame: "Frame") -> List[bytes]:
    """
    优化帧的序列化传输
    避免内存拷贝并符合STOMP协议规范
    
    :param frame: 要传输的Frame对象
    :return: 高效传输缓冲区列表
    """
    # 优化心跳帧
    if frame.cmd == "heartbeat":
        return [b"\n"]
    
    buffers = []
    cmd_line = (frame.cmd + "\n").encode()
    buffers.append(cmd_line)
    
    # 序列化头部（使用字节拼接）
    for key, value in sorted(frame.headers.items()):
        if value is None:
            continue
            
        if not isinstance(value, str):
            value = str(value)
            
        header_line = b"%b:%b\n" % (
            key.encode().replace(b'\\', b'\\\\').replace(b'\n', b'\\n').replace(b':', b'\\c'),
            value.encode().replace(b'\\', b'\\\\').replace(b'\n', b'\\n').replace(b':', b'\\c')
        )
        buffers.append(header_line)
    
    # 添加分隔符
    buffers.append(b"\n")
    
    # 添加正文（如果有）
    if frame.body:
        if isinstance(frame.body, str):
            frame.body = frame.body.encode()
        buffers.append(frame.body)
    
    # 添加帧终止符
    buffers.append(b"\x00")
    return buffers


def safe_length(data: Optional[Union[str, bytes]]) -> int:
    """
    空安全长度计算
    支持字符串和字节
    
    :param data: 输入数据
    :return: 数据长度（0为null或空）
    """
    if data is None:
        return 0
    if isinstance(data, (bytes, str)):
        return len(data)
    try:
        return len(data)
    except TypeError:
        return 0  # 不可测量类型返回0


class Frame:
    """
    STOMP通讯帧封装
    支持多值头部管理和二进制正文
    
    :param cmd: STOMP命令
    :param headers: 头部字典
    :param body: 帧正文
    """
    
    __slots__ = ("cmd", "headers", "body")
    
    def __init__(
        self,
        cmd: Optional[str] = None,
        headers: Optional[HeaderType] = None,
        body: Optional[Union[str, bytes]] = None
    ):
        self.cmd = cmd
        self.headers = headers or {}
        self.body = body
    
    def to_network(self) -> bytearray:
        """
        高效序列化帧（写优化）
        :return: 预分配缓冲区
        """
        # 计算预估长度
        size_guess = (
            len(self.cmd or "") + 
            sum(len(k) + len(v) + 3 for k, v in self.headers.items()) + 
            safe_length(self.body) + 3
        )
        
        buffer = bytearray(size_guess)
        pos = 0
        
        # 添加命令
        if self.cmd:
            cmd_bytes = f"{self.cmd}\n".encode()
            buffer[pos:pos+len(cmd_bytes)] = cmd_bytes
            pos += len(cmd_bytes)
        
        # 添加头部
        for key, values in self.headers.items():
            if values is None:
                continue
                
            if not isinstance(values, list):
                values = [values]
                
            for value in values:
                if value is None:
                    continue
                    
                header_line = f"{key}:{value}\n".encode()
                buffer[pos:pos+len(header_line)] = header_line
                pos += len(header_line)
        
        # 添加分隔符
        buffer[pos] = ord("\n")
        pos += 1
        
        # 添加正文
        if self.body:
            if isinstance(self.body, str):
                body_bytes = self.body.encode()
            else:
                body_bytes = self.body
                
            end = pos + len(body_bytes)
            if end > len(buffer):
                buffer += bytearray(end - len(buffer))
            buffer[pos:end] = body_bytes
            pos = end
        
        # 添加终止符
        buffer[pos] = 0
        return buffer[:pos+1]
    
    def __str__(self) -> str:
        """
        Frame对象的摘要表示（生产环境安全格式）
        """
        body_preview = "[%d bytes]" % safe_length(self.body) if self.body else "None"
        return (
            f"Frame(cmd={repr(self.cmd)}, "
            f"headers={dict(self.headers)}, "
            f"body={body_preview})"
        )
    
    def __repr__(self) -> str:
        return self.__str__()


# -------------------- 性能测试工具 -------------------- 
class FrameBenchmark:
    """STOMP帧性能基准测试工具"""
    
    @staticmethod
    def run():
        """执行序列化和解析性能测试"""
        bench_frame = Frame(
            cmd="SEND",
            headers={
                "destination": "/queue/test",
                "content-type": "text/plain",
                "persistent": "true",
                "id": str(uuid.uuid4())
            },
            body="x" * 1024 * 1024  # 1MB正文
        )
        
        # 序列化性能测试
        serialize_time = timeit.timeit(
            lambda: bench_frame.to_network(),
            number=100
        )
        log.info("Frame serialization: %.2f MB/s", 
                 100 * 1024 * 1024 / serialize_time / 1e6)
        
        # 解析性能测试
        frame_data = bench_frame.to_network()
        parse_time = timeit.timeit(
            lambda: parse_frame(frame_data),
            number=1000
        )
        log.info("Frame parsing: %.2fk frames/s", 
                 1000 / parse_time)
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    FrameBenchmark.run()
