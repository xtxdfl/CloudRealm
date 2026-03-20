#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import struct
import logging
import enum
import dataclasses
from struct import unpack
from typing import (
    Generator, Optional, List, Tuple, Any, 
    Union, ByteString, Callable, cast
)

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | WebSocket | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('websocket-stream')

# 定义全局常量
VALID_CLOSING_CODES = {1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011}
MAX_FRAME_SIZE = 2**24  # 16 MB
UTF8_VALIDATION_CHUNK_SIZE = 4096  # 4KB 块验证

class Opcode(enum.IntEnum):
    """WebSocket 操作码定义"""
    CONTINUATION = 0x0
    TEXT         = 0x1
    BINARY       = 0x2
    CLOSE        = 0x8
    PING         = 0x9
    PONG         = 0xA

class FrameStatus(enum.Enum):
    """帧处理状态"""
    COMPLETE     = enum.auto()
    INCOMPLETE   = enum.auto()
    ERROR        = enum.auto()
    CONTROL      = enum.auto()

class FrameError(Exception):
    """帧处理异常基类"""
    def __init__(self, code: int, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason

class FrameTooLargeError(FrameError):
    """帧过大异常"""
    def __init__(self):
        super().__init__(1002, "Frame size exceeds maximum limit")

class ProtocolViolationError(FrameError):
    """协议违反异常"""
    def __init__(self, reason: str):
        super().__init__(1002, f"Protocol violation: {reason}")

class UTF8ValidationError(FrameError):
    """UTF-8 验证失败异常"""
    def __init__(self):
        super().__init__(1007, "Invalid UTF-8 sequence")

class UnsupportedFrameError(FrameError):
    """不支持的帧类型异常"""
    def __init__(self, opcode: int):
        super().__init__(1003, f"Unsupported frame opcode: {opcode}")

class StreamClosedError(Exception):
    """流已关闭异常"""
    pass

@dataclasses.dataclass
class Frame:
    """WebSocket 帧元数据结构"""
    opcode: Opcode
    payload: bytes = b''
    fin: bool = True
    rsv1: bool = False
    rsv2: bool = False
    rsv3: bool = False
    masking_key: Optional[bytes] = None
    length: int = 0
    
    def __post_init__(self):
        # 自动设置载荷长度
        if not self.length:
            self.length = len(self.payload)

@dataclasses.dataclass
class ControlMessage:
    """控制消息基类"""
    opcode: Opcode
    payload: bytes
    
    def single(self, mask: bool = False) -> Frame:
        """构建单帧控制消息"""
        return Frame(
            opcode=self.opcode,
            payload=self.payload,
            masking_key=struct.pack("!I", 0) if mask else None
        )

@dataclasses.dataclass
class CloseControlMessage(ControlMessage):
    """关闭连接控制消息"""
    code: int = 1000
    reason: str = ""
    
    def __post_init__(self):
        if self.reason:
            reason_bytes = self.reason.encode('utf-8')
            self.payload = struct.pack('>H', self.code) + reason_bytes
        else:
            self.payload = struct.pack('>H', self.code)
        
        super().__init__(Opcode.CLOSE, self.payload)

@dataclasses.dataclass
class PingControlMessage(ControlMessage):
    """Ping 控制消息"""
    def __init__(self, data: Union[str, bytes] = ""):
        if isinstance(data, str):
            payload = data.encode('utf-8')
        else:
            payload = data
        super().__init__(Opcode.PING, payload)

@dataclasses.dataclass
class PongControlMessage(ControlMessage):
    """Pong 控制消息"""
    def __init__(self, data: Union[str, bytes] = ""):
        if isinstance(data, str):
            payload = data.encode('utf-8')
        else:
            payload = data
        super().__init__(Opcode.PONG, payload)

@dataclasses.dataclass
class DataMessage:
    """数据消息基类 (文本/二进制)"""
    payload: bytes
    completed: bool = False
    frames: List[Frame] = dataclasses.field(default_factory=list)
    
    def extend(self, data: bytes) -> None:
        """添加分段数据"""
        self.payload += data
    
    @property
    def is_text(self) -> bool:
        """是否为文本消息"""
        return False

@dataclasses.dataclass
class TextMessage(DataMessage):
    """文本数据消息 (UTF-8 编码)"""
    @property
    def is_text(self) -> bool:
        return True
    
    @property
    def text(self) -> str:
        """获取解码后的文本内容"""
        return self.payload.decode('utf-8', errors='replace')

@dataclasses.dataclass
class BinaryMessage(DataMessage):
    """二进制数据消息"""
    pass

def validate_utf8(data: bytes) -> bool:
    """
    高效验证 UTF-8 字节序列
    
    参数:
        data: 需要验证的字节序列
        
    返回:
        如果数据是有效的 UTF-8 则返回 True
    """
    try:
        # 分块验证大块数据
        if len(data) > UTF8_VALIDATION_CHUNK_SIZE:
            for i in range(0, len(data), UTF8_VALIDATION_CHUNK_SIZE):
                chunk = data[i:i+UTF8_VALIDATION_CHUNK_SIZE]
                chunk.decode('utf-8', errors='strict')
        else:
            data.decode('utf-8', errors='strict')
        return True
    except UnicodeDecodeError:
        return False

class WebSocketStream:
    """高级 WebSocket 消息流处理器
    
    功能:
    - 解析传入的 WebSocket 字节流
    - 处理分帧消息 (文本/二进制)
    - 验证 UTF-8 文本数据
    - 处理控制帧 (Ping/Pong/Close)
    - 管理流状态和错误处理
    
    使用示例:
    >>> stream = WebSocketStream()
    >>> stream.receive(chunk1)
    >>> stream.receive(chunk2)
    >>> for msg in stream.processed_messages():
    ...     print(f"Received: {msg}")
    """
    
    def __init__(self, 
                 always_mask: bool = False, 
                 expect_masking: bool = True,
                 max_frame_size: int = MAX_FRAME_SIZE):
        """
        初始化 WebSocket 流处理器
        
        参数:
            always_mask: 是否总是掩码发送的帧
            expect_masking: 是否期望接收的帧被掩码
            max_frame_size: 单个帧的最大允许大小
        """
        self.always_mask = always_mask
        self.expect_masking = expect_masking
        self.max_frame_size = max_frame_size
        
        # 消息状态
        self.current_frame: Optional[Frame] = None
        self.current_message: Optional[DataMessage] = None
        self.pending_data = bytearray()
        
        # 消息队列
        self.data_messages: List[DataMessage] = []
        self.ping_messages: List[PingControlMessage] = []
        self.pong_messages: List[PongControlMessage] = []
        self.close_message: Optional[CloseControlMessage] = None
        self.errors: List[FrameError] = []
    
    def reset(self) -> None:
        """重置流状态"""
        self.current_frame = None
        self.current_message = None
        self.pending_data.clear()
        self.data_messages.clear()
        self.ping_messages.clear()
        self.pong_messages.clear()
        self.close_message = None
        self.errors.clear()
    
    def receive(self, data: ByteString) -> None:
        """接收字节数据并添加到处理队列"""
        self.pending_data.extend(data)
        
    def process_data(self) -> FrameStatus:
        """
        处理接收到的字节数据
        
        返回:
            FrameStatus 指示当前处理状态
        """
        if not self.pending_data:
            return FrameStatus.INCOMPLETE
            
        try:
            # 如果没有当前帧，尝试读取帧头
            if self.current_frame is None:
                status = self._read_frame_header()
                if status != FrameStatus.COMPLETE:
                    return status
                
            # 处理帧载荷
            return self._process_frame_payload()
            
        except FrameError as e:
            self.errors.append(e)
            self._handle_frame_error(e)
            return FrameStatus.ERROR
            
        except Exception as e:
            logger.exception("Unexpected error processing frame")
            error = ProtocolViolationError(str(e))
            self.errors.append(error)
            return FrameStatus.ERROR
        
        return FrameStatus.COMPLETE
    
    def _read_frame_header(self) -> FrameStatus:
        """读取并解析帧头"""
        # 检查是否有足够数据读取基本帧头 (至少 2 字节)
        if len(self.pending_data) < 2:
            logger.debug("Frame header incomplete (basic)")
            return FrameStatus.INCOMPLETE
            
        # 读取第一个字节
        first_byte = self.pending_data[0]
        fin = bool(first_byte & 0x80)
        rsv1 = bool(first_byte & 0x40)
        rsv2 = bool(first_byte & 0x20)
        rsv3 = bool(first_byte & 0x10)
        opcode = first_byte & 0x0F
        
        # 读取第二个字节
        second_byte = self.pending_data[1]
        mask_bit = bool(second_byte & 0x80)
        payload_len = second_byte & 0x7F
        
        # 处理扩展载荷长度
        extra_bytes = 0
        if payload_len == 126:
            extra_bytes = 2
        elif payload_len == 127:
            extra_bytes = 8
            
        # 检查是否有足够的字节用于扩展长度
        if len(self.pending_data) < 2 + extra_bytes:
            logger.debug("Frame header incomplete (extended)")
            return FrameStatus.INCOMPLETE
            
        # 读取实际载荷长度
        if extra_bytes == 2:
            payload_len = unpack('>H', self.pending_data[2:4])[0]
        elif extra_bytes == 8:
            payload_len = unpack('>Q', self.pending_data[2:10])[0]
            if payload_len > self.max_frame_size:
                raise FrameTooLargeError()
        
        # 检查帧长度是否超过最大限制
        if payload_len > self.max_frame_size:
            raise FrameTooLargeError()
            
        # 处理掩码密钥
        mask_key = None
        mask_bytes = 0
        if mask_bit:
            mask_bytes = 4
            if len(self.pending_data) < 2 + extra_bytes + mask_bytes:
                return FrameStatus.INCOMPLETE
            mask_start = 2 + extra_bytes
            mask_key = bytes(self.pending_data[mask_start:mask_start+4])
            
            # 验证掩码
            if self.expect_masking and not mask_key:
                raise ProtocolViolationError("Expected masking but not provided")
            elif not self.expect_masking and mask_key:
                raise ProtocolViolationError("Unexpected masking")
        
        # 创建新帧
        header_end = 2 + extra_bytes + mask_bytes
        self.current_frame = Frame(
            opcode=Opcode(opcode),
            fin=fin,
            rsv1=rsv1,
            rsv2=rsv2,
            rsv3=rsv3,
            masking_key=mask_key,
            length=payload_len
        )
        
        # 移除已处理的头字节
        del self.pending_data[:header_end]
        return FrameStatus.COMPLETE
    
    def _process_frame_payload(self) -> FrameStatus:
        """处理帧载荷数据"""
        frame = cast(Frame, self.current_frame)
        
        # 检查是否有足够的载荷数据
        bytes_need = frame.length - len(frame.payload)
        if bytes_need > 0:
            # 获取可用数据 (最多需要的字节数)
            bytes_avail = min(bytes_need, len(self.pending_data))
            if bytes_avail == 0:
                return FrameStatus.INCOMPLETE
            
            # 添加数据到帧载荷
            chunk = self.pending_data[:bytes_avail]
            frame.payload += bytes(chunk)
            del self.pending_data[:bytes_avail]
            
            # 如果载荷还不完整，继续等待
            if len(frame.payload) < frame.length:
                logger.debug("Frame payload incomplete")
                return FrameStatus.INCOMPLETE
        
        # 应用去掩码（如果存在）
        if frame.masking_key and frame.payload:
            frame.payload = self._unmask_data(
                frame.payload, 
                frame.masking_key
            )
        
        # 处理完整帧
        self._handle_complete_frame(frame)
        self.current_frame = None
        return FrameStatus.COMPLETE
    
    def _unmask_data(self, data: bytes, mask_key: bytes) -> bytes:
        """应用去掩码操作"""
        result = bytearray(data)
        mask = bytearray(mask_key)
        
        # 手动优化循环操作
        for i in range(len(result)):
            result[i] ^= mask[i % 4]
        
        return bytes(result)
    
    def _handle_complete_frame(self, frame: Frame) -> None:
        """处理一个完整的帧"""
        opcode = frame.opcode
        
        # 处理控制帧
        if opcode >= Opcode.CLOSE:
            return self._handle_control_frame(frame)
        
        # 处理数据帧
        if opcode in {Opcode.TEXT, Opcode.BINARY, Opcode.CONTINUATION}:
            return self._handle_data_frame(frame)
        
        # 未知操作码
        raise UnsupportedFrameError(opcode)
    
    def _handle_control_frame(self, frame: Frame) -> None:
        """处理控制帧 (Ping/Pong/Close)"""
        if frame.opcode == Opcode.CLOSE:
            self._handle_close_frame(frame)
        elif frame.opcode == Opcode.PING:
            self._handle_ping_frame(frame)
        elif frame.opcode == Opcode.PONG:
            self._handle_pong_frame(frame)
        else:
            raise UnsupportedFrameError(frame.opcode)
    
    def _handle_close_frame(self, frame: Frame) -> None:
        """处理关闭帧"""
        payload = frame.payload
        
        # 解析关闭代码和原因
        code = 1000  # 默认正常关闭
        reason = ""
        
        if len(payload) >= 2:
            try:
                code = unpack('>H', payload[:2])[0]
            except struct.error:
                code = 1002
                reason = "Invalid close code format"
            
            # 验证关闭代码
            if code not in VALID_CLOSING_CODES and not (2999 <= code <= 4999):
                code = 1002
                reason = "Invalid close code"
                
            # 解析原因
            if len(payload) > 2:
                reason_bytes = payload[2:]
                if not validate_utf8(reason_bytes):
                    raise UTF8ValidationError()
                reason = reason_bytes.decode('utf-8', errors='replace')
        
        self.close_message = CloseControlMessage(code, reason)
    
    def _handle_ping_frame(self, frame: Frame) -> None:
        """处理 Ping 帧"""
        self.ping_messages.append(PingControlMessage(frame.payload))
    
    def _handle_pong_frame(self, frame: Frame) -> None:
        """处理 Pong 帧"""
        self.pong_messages.append(PongControlMessage(frame.payload))
    
    def _handle_data_frame(self, frame: Frame) -> None:
        """处理数据帧 (文本/二进制/分块)"""
        # 检查分片连续性
        if frame.opcode == Opcode.CONTINUATION:
            if self.current_message is None:
                raise ProtocolViolationError("Unexpected continuation frame")
        else:
            # 新消息开始
            if self.current_message and not self.current_message.completed:
                raise ProtocolViolationError("New message started before completion")
                
            # 根据操作码创建新消息
            if frame.opcode == Opcode.TEXT:
                self.current_message = TextMessage(b'')
                # 初始文本帧必须验证 UTF-8
                if frame.payload and not validate_utf8(frame.payload):
                    raise UTF8ValidationError()
            else:  # Opcode.BINARY
                self.current_message = BinaryMessage(b'')
        
        # 添加数据到当前消息
        cast(DataMessage, self.current_message).extend(frame.payload)
        
        # 如果这是消息的最后一帧，标记完成并添加到消息队列
        if frame.fin:
            cast(DataMessage, self.current_message).completed = True
            self.data_messages.append(self.current_message)
            self.current_message = None
    
    def _handle_frame_error(self, error: FrameError) -> None:
        """处理帧错误"""
        logger.error(f"Frame error {error.code}: {error.reason}")
        
        # 如果是严重的协议错误，设置关闭消息
        if not self.close_message and error.code in VALID_CLOSING_CODES:
            self.close_message = CloseControlMessage(error.code, error.reason)
        
        # 清除当前帧
        self.current_frame = None
        self.current_message = None
        self.pending_data.clear()
    
    def processed_messages(self) -> Generator[Union[DataMessage, ControlMessage], None, None]:
        """生成器：返回所有处理完成的消息"""
        # 返回所有数据消息
        while self.data_messages:
            yield self.data_messages.pop(0)
        
        # 返回所有 Ping 消息
        while self.ping_messages:
            yield self.ping_messages.pop(0)
        
        # 返回所有 Pong 消息
        while self.pong_messages:
            yield self.pong_messages.pop(0)
        
        # 返回关闭消息 (如果有)
        if self.close_message:
            yield self.close_message
            self.close_message = None
        
        # 清除所有错误
        self.errors.clear()
    
    def create_message(self, 
                     opcode: Opcode, 
                     payload: Union[str, bytearray, bytes],
                     mask: bool = False) -> Frame:
        """创建要发送的消息帧"""
        # 处理不同载荷类型
        if isinstance(payload, str):
            payload_bytes = payload.encode('utf-8')
        else:
            payload_bytes = bytes(payload)
        
        # 创建帧
        return Frame(
            opcode=opcode,
            payload=payload_bytes,
            fin=True,
            masking_key=struct.pack("!I", 0) if (mask or self.always_mask) else None,
            length=len(payload_bytes)
        )
    
    def text_message(self, text: str, mask: bool = False) -> Frame:
        """创建文本消息"""
        return self.create_message(Opcode.TEXT, text, mask)
    
    def binary_message(self, data: ByteString, mask: bool = False) -> Frame:
        """创建二进制消息"""
        return self.create_message(Opcode.BINARY, data, mask)
    
    def ping(self, data: ByteString = b'', mask: bool = False) -> Frame:
        """创建 Ping 控制帧"""
        return self.create_message(Opcode.PING, data, mask)
    
    def pong(self, data: ByteString = b'', mask: bool = False) -> Frame:
        """创建 Pong 控制帧"""
        return self.create_message(Opcode.PONG, data, mask)
    
    def close(self, code: int = 1000, reason: str = "", mask: bool = False) -> Frame:
        """创建 Close 控制帧"""
        if reason:
            payload = struct.pack('>H', code) + reason.encode('utf-8')
        else:
            payload = struct.pack('>H', code)
        return self.create_message(Opcode.CLOSE, payload, mask)

# 示例使用
if __name__ == "__main__":
    # 初始化 WebSocket 流
    stream = WebSocketStream()
    
    # 模拟接收数据 (真实场景中会从网络读取)
    def simulate_receive(stream: WebSocketStream, data: bytes):
        logger.info(f"Receiving {len(data)} bytes")
        stream.receive(data)
        
        # 处理所有可用数据
        while True:
            status = stream.process_data()
            if status in {FrameStatus.INCOMPLETE, FrameStatus.ERROR}:
                break
                
        # 显示所有处理完成的消息
        for msg in stream.processed_messages():
            if isinstance(msg, TextMessage):
                logger.info(f"Text message: {msg.text}")
            elif isinstance(msg, BinaryMessage):
                logger.info(f"Binary message ({len(msg.payload)} bytes)")
            elif isinstance(msg, PingControlMessage):
                logger.info("Ping received")
            elif isinstance(msg, PongControlMessage):
                logger.info("Pong received")
            elif isinstance(msg, CloseControlMessage):
                logger.info(f"Close received: {msg.code} - {msg.reason}")
    
    # 模拟简单的文本消息
    text_frame = b'\x81\x05' + 'Hello'.encode()
    simulate_receive(stream, text_frame)
    
    # 模拟分块的文本消息
    chunk1 = b'\x01\x05' + 'Hel'.encode()            # FIN=0, 非完整消息
    chunk2 = b'\x80\x02' + 'lo'.encode()             # FIN=1, 完成消息
    simulate_receive(stream, chunk1)
    simulate_receive(stream, chunk2)
    
    # 模拟 Ping 消息
    ping_frame = b'\x89\x05' + 'ping!'.encode()
    simulate_receive(stream, ping_frame)
    
    # 模拟带掩码的文本消息
    masked_frame = b'\x81\x85\x11\x22\x33\x44' + b'\x60\x4f\x43\x51\x51'
    simulate_receive(stream, masked_frame)  # 应解码为 "Hello"
    
    # 模拟关闭消息
    close_frame = b'\x88\x06' + struct.pack('>H', 1000) + b'Bye'
    simulate_receive(stream, close_frame)
