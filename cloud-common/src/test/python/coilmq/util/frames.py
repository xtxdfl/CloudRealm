#!/usr/bin/env python3

import re
import logging
import io
import sys
from collections import OrderedDict
from functools import partial

# STOMP协议指令枚举
SEND = "SEND"
CONNECT = "CONNECT"
MESSAGE = "MESSAGE"
ERROR = "ERROR"
CONNECTED = "CONNECTED"
SUBSCRIBE = "SUBSCRIBE"
UNSUBSCRIBE = "UNSUBSCRIBE"
BEGIN = "BEGIN"
COMMIT = "COMMIT"
ABORT = "ABORT"
ACK = "ACK"
NACK = "NACK"
DISCONNECT = "DISCONNECT"

# 协议版本2.0新增指令
STOMP_V2_COMMANDS = [
    "connect",
    "connected",
    "send",
    "subscribe",
    "unsubscribe",
    "ack",
    "nack",
    "begin",
    "commit",
    "abort",
    "disconnect",
]

# 内容类型常量
TEXT_PLAIN = "text/plain"
APPLICATION_JSON = "application/json"

class FrameError(Exception):
    """基础帧异常类"""
    pass

class IncompleteFrame(FrameError):
    """帧体不完整异常"""
    def __init__(self, expected, actual):
        super().__init__(f"所需长度: {expected}, 实际长度: {actual}")
        self.expected = expected
        self.actual = actual

class BodyNotTerminated(FrameError):
    """帧体未正常终止异常"""
    pass

class InvalidHeader(FrameError):
    """无效头部格式异常"""
    def __init__(self, header):
        super().__init__(f"无效头部: {header}")
        self.header = header

class Frame:
    """
    STOMP协议帧核心容器
    
    特征:
    • 自动头部校验
    • 智能体部编码
    • 协议版本协商
    • 多版本兼容
    
    使用示例:
    >>> frame = Frame("SEND", {
    ...     "destination": "/queue/test",
    ...     "content-type": "text/plain"
    ... }, "测试消息")
    >>> raw_frame = frame.pack()
    """
    # STOMP协议版本 (默认为1.2)
    PROTOCOL_VERSION = "1.2"
    
    def __init__(self, cmd, headers=None, body=None):
        """
        :param cmd: 帧指令 (必须为VALID_COMMANDS中的指令)
        :param headers: 头部键值对
        :param body: 帧体内容 (字符串或字节串)
        """
        self.cmd = self._validate_command(cmd)
        self.headers = headers or {}
        self._body = None
        self.body = body  # 通过属性设置器处理
        
        # 添加基础头部
        self.headers.setdefault("content-length", HeaderValue(self._calculate_body_length))
        self.headers.setdefault("protocol-version", self.PROTOCOL_VERSION)
    
    @property
    def body(self):
        """获取帧体内容"""
        return self._body
    
    @body.setter
    def body(self, value):
        """设置帧体内容并自动检测编码"""
        if value is None:
            self._body = b''
        elif isinstance(value, str):
            self._body = value.encode('utf-8')
            self.headers['content-type'] = f"{TEXT_PLAIN};charset=utf-8"
        else:
            self._body = value
    
    def _validate_command(self, cmd):
        """验证指令有效性"""
        cmd_lower = cmd.lower()
        if cmd_lower not in STOMP_V2_COMMANDS:
            raise ValueError(f"无效STOMP指令: {cmd}")
        return cmd.upper()
    
    def _calculate_body_length(self):
        """计算体部长度"""
        return len(self.body)
    
    def __str__(self):
        """可读性表示"""
        body_preview = (self.body[:20] + b'...') if len(self.body) > 20 else self.body
        return (
            f"Frame(cmd={self.cmd}, "
            f"headers={self.headers}, "
            f"body={body_preview!r})"
        )
    
    def __repr__(self):
        return f"<{self.__class__.__name__} cmd={self.cmd}>"
    
    def __eq__(self, other):
        """深度比较帧对象"""
        return (
            isinstance(other, Frame) and
            self.cmd == other.cmd and
            self.headers == other.headers and
            self.body == other.body
        )
    
    @property
    def transaction(self):
        """获取事务ID（如果存在）"""
        return self.headers.get("transaction")
    
    @classmethod
    def from_buffer(cls, buff):
        """
        从字节缓冲区解析帧
        
        :param buff: 可读缓冲区 (io.BytesIO)
        :return: 解析后的帧对象
        :raises IncompleteFrame: 当帧不完整时
        :raises BodyNotTerminated: 当缺少终止符时
        """
        try:
            # 解析命令行和头部
            cmd, headers = _parse_headers(buff)
            
            # 解析帧体
            body = _parse_body(buff, headers)
            
            return cls(cmd, headers=headers, body=body)
        except EOFError:
            raise IncompleteFrame(0, 0)
    
    def pack(self):
        """
        帧对象序列化为字节串
        
        :return: 完整的帧字节串
        """
        # 构建头部部分
        header_lines = []
        for key, value in self.headers.items():
            # 动态计算头部值
            resolved_value = value() if callable(value) else value
            header_lines.append(f"{key}:{resolved_value}")
        
        headers_bytes = "\n".join(header_lines).encode('utf-8')
        
        # 构建帧结构
        parts = [
            self.cmd.encode('utf-8') + b"\n",
            headers_bytes,
            b"\n\n",         # 头部与体部的分隔符
            self.body
        ]
        
        # 添加终止符
        parts.append(b"\x00")
        
        return b"".join(parts)

class ConnectedFrame(Frame):
    """连接成功响应帧"""
    
    def __init__(self, session, heartbeat=None, extra_headers=None):
        """
        :param session: 会话标识符
        :param heartbeat: 心跳配置 (可选)
        :param extra_headers: 额外头部 (可选)
        """
        headers = extra_headers or {}
        headers["session"] = session
        
        # STOMP 1.2+ 支持心跳
        if heartbeat:
            headers["heart-beat"] = heartbeat
        
        super().__init__(cmd=CONNECTED, headers=headers)
        
        # 设置标准属性
        self.headers["server"] = "CoilMQ/3.0"
        self.headers["version"] = Frame.PROTOCOL_VERSION

class ErrorFrame(Frame):
    """错误通知帧"""
    
    def __init__(self, message, body=None, extra_headers=None):
        """
        :param message: 错误描述
        :param body: 详细错误体 (可选)
        :param extra_headers: 额外头部 (可选)
        """
        headers = extra_headers or {}
        headers["message"] = message
        headers["content-type"] = TEXT_PLAIN
        
        super().__init__(cmd=ERROR, headers=headers, body=body)
        
        # 错误标识符 (用于日志追踪)
        self.headers["error-id"] = f"ERR-{id(self):08x}"

class ReceiptFrame(Frame):
    """操作回执帧"""
    
    def __init__(self, receipt_id, extra_headers=None):
        """
        :param receipt_id: 回执标识符
        """
        headers = extra_headers or {}
        headers["receipt-id"] = receipt_id
        
        super().__init__(cmd="RECEIPT", headers=headers)

class HeaderValue:
    """
    头部值动态描述器
    
    示例:
    >>> frame = Frame("SEND")
    >>> frame.headers["timestamp"] = HeaderValue(time.time)
    >>> str(frame.headers["timestamp"])
    '1625157809.12345'
    """
    
    def __init__(self, calculator):
        """
        :param calculator: 动态计算函数
        """
        if not callable(calculator):
            raise TypeError("必须提供可调用对象")
        self.calculator = calculator
        
    def __call__(self):
        return str(self.calculator())
    
    def __str__(self):
        return str(self.calculator())
    
    def __repr__(self):
        return f"<DynamicHeader {self.calculator}>"

class FrameBuffer:
    """
    高效帧缓冲区处理器
    
    特性:
    • 零拷贝数据流处理
    • 多帧同时解析
    • 自动错误恢复
    • 资源使用监测
    
    使用示例:
    >>> buffer = FrameBuffer()
    >>> buffer.append(data_chunk1)
    >>> buffer.append(data_chunk2)
    >>> 
    >>> for frame in buffer:
    ...     process_frame(frame)
    """
    
    # 帧头部终止符
    HEADER_TERMINATOR = b"\n\n"
    
    # 帧终止符 (NULL字节)
    FRAME_TERMINATOR = b"\x00"
    
    # 头部行格式正则
    HEADER_REGEX = re.compile(rb"^([^:\s]+)\s*:\s*(.*?)\s*$")
    
    def __init__(self):
        self._buffer = io.BytesIO()
        self._position = 0
        self.logger = logging.getLogger('stomp.buffer')
        self._stats = {
            'frames_processed': 0,
            'bytes_processed': 0,
            'errors': 0
        }
    
    @property
    def size(self):
        """当前缓冲字节数"""
        return self._buffer.getbuffer().nbytes - self._position
    
    def clear(self):
        """清空缓冲区"""
        self._buffer.close()
        self._buffer = io.BytesIO()
        self._position = 0
    
    def append(self, data):
        """
        添加数据到缓冲区
        
        :param data: 二进制数据块
        :raises TypeError: 当数据类型错误时
        """
        if not isinstance(data, bytes):
            raise TypeError("仅支持字节类型数据")
        
        # 记录当前位置
        current = self._position
        self._buffer.seek(0, io.SEEK_END)
        self._buffer.write(data)
        self._position = current
        self._stats['bytes_processed'] += len(data)
    
    def __iter__(self):
        """实现迭代器接口"""
        return self
    
    def __next__(self):
        """提取下一个完整帧"""
        frame = self.extract_frame()
        if frame:
            self._stats['frames_processed'] += 1
            return frame
        raise StopIteration
    
    def extract_frame(self):
        """从缓冲区提取帧"""
        buffer_size = self.size
        if buffer_size < 1:
            return None
        
        # 重置到上次位置
        self._buffer.seek(self._position)
        
        try:
            # 定位帧头结束位置
            header_end = self._find_header_end()
            
            # 解析命令和头部
            cmd = self._buffer.readline().strip().decode('utf-8')
            if not cmd:
                return None
                
            headers = self._parse_headers(header_end)
            
            # 解析体部
            body = self._parse_body(headers)
            
            # 成功解析，更新位置
            self._position = self._buffer.tell()
            
            return Frame(cmd, headers, body)
        except EOFError:
            return None
        except BodyNotTerminated as e:
            self.logger.error("帧终止错误: %s", e)
            self._stats['errors'] += 1
            self.recover()  # 恢复解析状态
            return None
        except FrameError as e:
            self.logger.warning("帧解析错误: %s", e)
            self._stats['errors'] += 1
            self.recover()
            return None
    
    def _find_header_end(self):
        """定位头部终止位置"""
        start_pos = self._position
        buffer = self._buffer.getbuffer()
        
        # 在内存视图中搜索终止符
        while True:
            term_pos = buffer.find(self.HEADER_TERMINATOR, start_pos)
            if term_pos != -1:
                return term_pos
            if start_pos + 2 >= len(buffer):
                raise EOFError("未找到头部终止符")
            start_pos += 1
    
    def _parse_headers(self, header_end):
        """解析头部内容"""
        headers = OrderedDict()
        self._buffer.seek(self._position)
        
        # 读取到头部结束
        header_data = self._buffer.read(header_end - self._position)
        
        # 逐行解析
        for line in header_data.split(b'\n'):
            line = line.strip()
            if not line:
                continue
                
            match = self.HEADER_REGEX.match(line)
            if not match:
                raise InvalidHeader(line)
                
            key, value = match.groups()
            headers[key.decode('utf-8')] = value.decode('utf-8')
        
        return headers
    
    def _parse_body(self, headers):
        """解析帧体内容"""
        content_length = int(headers.get("content-length", -1))
        
        # 基于内容长度处理
        if content_length > 0:
            body = self._buffer.read(content_length)
            if len(body) < content_length:
                raise IncompleteFrame(content_length, len(body))
            
            # 检查并跳过终止符
            terminator = self._buffer.read(1)
            if terminator != self.FRAME_TERMINATOR:
                raise BodyNotTerminated()
            return body
        
        # 处理无内容长度的帧
        chunks = []
        while True:
            chunk = self._buffer.readline()
            term_pos = chunk.find(self.FRAME_TERMINATOR)
            
            if term_pos != -1:
                chunks.append(chunk[:term_pos])
                # 回退未使用数据
                unused = chunk[term_pos+1:]
                pos = self._buffer.tell()
                self._buffer.seek(pos - len(unused))
                return b"".join(chunks)
            
            chunks.append(chunk)
    
    def recover(self):
        """尝试恢复解析状态"""
        # 搜索下一个完整帧的起始位置
        buffer_data = self._buffer.getbuffer()
        start_pos = buffer_data.find(b'\n', self._position)
        
        if start_pos != -1:
            # 丢弃无效数据
            discarded = start_pos - self._position
            self.logger.warning("丢弃 %d 字节无效数据", discarded)
            self._position = start_pos
        else:
            # 无有效数据起始点，清空缓冲区
            self.clear()

# === 辅助函数 ===
def _parse_headers(buff):
    """解析头部辅助函数"""
    lines = []
    while True:
        line = buff.readline().rstrip(b"\r\n")
        if not line:
            break
        lines.append(line.decode('utf-8'))
    
    if not lines:
        return None, {}
    
    cmd = lines[0]
    headers = OrderedDict()
    
    for line in lines[1:]:
        parts = line.split(':', 1)
        if len(parts) < 2:
            continue
        key, value = parts
        headers[key.strip()] = value.strip()
    
    return cmd, headers

def _parse_body(buff, headers):
    """解析帧体辅助函数"""
    content_length = int(headers.get("content-length", -1))
    
    if content_length >= 0:
        body = buff.read(content_length)
        if len(body) < content_length:
            raise IncompleteFrame(content_length, len(body))
        
        terminator = buff.read(1)
        if terminator != b"\x00":
            raise BodyNotTerminated()
        return body
    
    # 流式处理体部
    parts = []
    while True:
        chunk = buff.read(1024)
        if not chunk:
            break
        
        pos = chunk.find(b"\x00")
        if pos >= 0:
            parts.append(chunk[:pos])
            # 回退未读数据
            buff.seek(-(len(chunk) - pos - 1), 1)
            break
        
        parts.append(chunk)
    
    return b"".join(parts)

