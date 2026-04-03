#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import struct
import logging
from typing import Union, Optional, Tuple, Any, List
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from collections import namedtuple
import secrets

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | WebSocket | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('websocket-messages')

# 协议常量定义
class Opcode(Enum):
    """WebSocket 操作码枚举"""
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA

# 有效关闭代码集合
VALID_CLOSING_CODES = {1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011}

# 帧元数据结构
FrameMeta = namedtuple('FrameMeta', ['opcode', 'fin', 'mask'])

class WebSocketException(Exception):
    """WebSocket 异常基类"""
    pass

class FrameConstructionError(WebSocketException):
    """帧构建错误异常"""
    pass

class ProtocolViolation(WebSocketException):
    """协议违反异常"""
    pass

@dataclass
class Message:
    """WebSocket 消息基类
    
    功能:
    - 封装不同类型的 WebSocket 消息
    - 支持消息分片
    - 提供帧构建和消息扩展
    - 处理 UTF-8 自动编码和错误处理
    
    属性:
        opcode: 消息类型操作码
        data: 消息数据 (二进制格式)
        encoding: 文本消息的字符编码 (仅对文本有效)
        completed: 消息是否已完成
        fragments: 分片编号
    """
    __slots__ = ('opcode', 'data', 'encoding', 'completed', 'fragments')
    
    opcode: Opcode
    data: Union[bytearray, bytes, str] = bytearray()
    encoding: str = "utf-8"
    completed: bool = False
    fragments: List['Message'] = None
    
    def __post_init__(self):
        """初始化后处理数据转换"""
        self._ensure_binary()
        
    def _ensure_binary(self) -> None:
        """确保数据为二进制格式"""
        if isinstance(self.data, str):
            self.data = self.data.encode(self.encoding)
        elif isinstance(self.data, bytearray):
            self.data = bytes(self.data)
        
    @property
    def is_control(self) -> bool:
        """是否为控制消息"""
        return self.opcode.value >= Opcode.CLOSE.value

    def __len__(self) -> int:
        """消息长度"""
        return len(self.data)
    
    def build_frame(self, 
                   fin: bool = True, 
                   mask: bool = False, 
                   first_fragment: bool = False, 
                   last_fragment: bool = False) -> bytes:
        """
        构建 WebSocket 帧字节
        
        参数:
            fin: 是否为最后一个分片 (FIN 位)
            mask: 是否使用掩码
            first_fragment: 是否是该消息的第一个分片
            last_fragment: 是否为该消息的最后一个分片
            
        返回:
            构建好的帧字节
        """
        return FrameBuilder.build(
            body=self.data,
            opcode=self.opcode.value,
            mask=mask,
            fin=fin,
            is_first=first_fragment,
            is_last=last_fragment
        )
    
    def extend(self, data: Union[bytes, bytearray, str]) -> None:
        """扩展消息数据
        
        参数:
            data: 要添加的数据
        """
        if isinstance(data, str):
            try:
                data_bytes = data.encode(self.encoding)
            except UnicodeEncodeError as e:
                raise ProtocolViolation(f"UTF-8 encoding error: {str(e)}")
            else:
                # 扩展二进制数据
                self._extend_bytes(data_bytes)
        elif isinstance(data, (bytes, bytearray)):
            self._extend_bytes(data)
        else:
            raise TypeError(f"Unsupported data type: {type(data)}")
    
    def _extend_bytes(self, data: bytes) -> None:
        """将二进制数据扩展至消息中"""
        if not self.data:
            self.data = data
        elif isinstance(self.data, bytes):
            self.data = b''
            self.data += data
        else:
            self.data += data
    
    def as_text(self) -> str:
        """将消息内容转为文本 (仅对文本消息有效)"""
        if self.opcode != Opcode.TEXT:
            raise TypeError(f"Cannot convert {self.opcode.name} message to text")
        
        try:
            return self.data.decode(self.encoding)
        except UnicodeDecodeError:
            # 宽松模式下处理无效UTF-8序列
            return self.data.decode(self.encoding, errors='replace')
    
    def as_bytes(self) -> bytes:
        """以二进制格式返回消息内容"""
        if isinstance(self.data, bytearray):
            return bytes(self.data)
        return self.data
    
    def __str__(self) -> str:
        """字符串表示 (针对控制帧)"""
        return f"{self.opcode.name} message"

@dataclass
class TextMessage(Message):
    """文本消息 (UTF-8 编码)"""
    opcode: Opcode = Opcode.TEXT
    
    def __str__(self) -> str:
        """字符串表示"""
        if self.data:
            try:
                # 安全地显示前100个字符
                text = self.as_text()
                return f"Text({len(text)}): '{text[:100]}{'...' if len(text)>100 else ''}'"
            except:
                return f"Text message (invalid UTF-8, {len(self.data)} bytes)"
        return "Empty text message"

@dataclass
class BinaryMessage(Message):
    """二进制消息"""
    opcode: Opcode = Opcode.BINARY
    
    def __str__(self) -> str:
        """字符串表示"""
        if self.data:
            return f"Binary data ({len(self)} bytes)"
        return "Empty binary message"

@dataclass
class CloseControlMessage(Message):
    """关闭控制消息"""
    opcode: Opcode = Opcode.CLOSE
    code: int = 1000
    reason: str = ""
    
    def __post_init__(self):
        """关闭消息的特殊初始化处理"""
        # 将代码和原因编码为规范格式
        if self.code:
            self.data = struct.pack("!H", self.code)
        
        if self.reason:
            try:
                reason_bytes = self.reason.encode("utf-8")
            except UnicodeEncodeError:
                raise ProtocolViolation("Invalid UTF-8 in close reason")
            else:
                self.data += reason_bytes
                
        # 验证关闭代码
        if self.code not in VALID_CLOSING_CODES and not (2999 <= self.code <= 4999):
            logger.warning(f"Invalid close code: {self.code}")
            self.code = 1003  # 设置为无效关闭码
    
    def __str__(self) -> str:
        """关闭消息的字符串表示"""
        return f"Close (code={self.code}, reason='{self.reason}')"

@dataclass
class PingControlMessage(Message):
    """Ping 控制消息"""
    opcode: Opcode = Opcode.PING
    
    def __str__(self) -> str:
        """Ping 消息的字符串表示"""
        return f"Ping ({len(self)} bytes)"

@dataclass
class PongControlMessage(Message):
    """Pong 控制消息 (对 Ping 的响应)"""
    opcode: Opcode = Opcode.PONG
    
    def __str__(self) -> str:
        """Pong 消息的字符串表示"""
        return f"Pong ({len(self)} bytes)"

class FrameBuilder:
    """高级 WebSocket 帧构建器
    
    功能:
    - 构建符合 RFC6455 标准的 WebSocket 帧
    - 支持掩码和分片功能
    - 优化内存使用，避免大消息的多次拷贝
    - 提供灵活的接口控制帧参数
    """
    
    MAX_FRAME_LENGTH = 2**24 - 1  # 16MB 最大载荷
    
    @staticmethod
    def build(
        body: Union[bytes, bytearray, str] = b"",
        opcode: int = Opcode.TEXT.value,
        mask: bool = False,
        fin: bool = True,
        rsv: int = 0,
        is_first: bool = False,
        is_last: bool = False
    ) -> bytes:
        """
        构建 WebSocket 帧
        
        参数:
            body: 帧载荷 (可以是文本或二进制)
            opcode: 操作码 (参见 Opcode 枚举)
            mask: 是否应用掩码
            fin: FIN 位 (设为 True 表示最后一帧)
            rsv: RSV 保留位 (范围为0-7)
            is_first: 是否为消息的第一帧
            is_last: 是否为消息的最后一帧
            
        返回:
            构建好的帧字节
        """
        # 确定最终 FIN 值
        final_fin = fin or is_last
        
        # 确定操作码 (第一分片使用实际操作码，后续分片使用延续帧)
        actual_opcode = opcode if is_first else Opcode.CONTINUATION.value
        
        # 验证载荷长度
        body_bytes = FrameBuilder._convert_body(body)
        payload_length = len(body_bytes)
        if payload_length > FrameBuilder.MAX_FRAME_LENGTH:
            raise FrameConstructionError(f"Payload too large: {payload_length} > {FrameBuilder.MAX_FRAME_LENGTH}")
        
        # 构建帧头
        frame_bytes = FrameBuilder._build_header(
            opcode=actual_opcode,
            fin=final_fin,
            rsv=rsv,
            mask=mask,
            payload_length=payload_length
        )
        
        # 应用掩码并添加载荷
        if mask:
            masking_key = secrets.token_bytes(4)
            masked_payload = FrameBuilder._mask_data(body_bytes, masking_key)
            frame_bytes += masking_key
            frame_bytes += masked_payload
        else:
            frame_bytes += body_bytes
            
        return frame_bytes
    
    @staticmethod
    def _convert_body(body: Union[bytes, bytearray, str]) -> bytes:
        """转换载荷为二进制格式"""
        if isinstance(body, str):
            return body.encode()
        elif isinstance(body, bytearray):
            return bytes(body)
        return body
    
    @staticmethod
    def _build_header(
        opcode: int,
        fin: bool,
        rsv: int,
        mask: bool,
        payload_length: int
    ) -> bytes:
        """构建帧头字节"""
        # 第一个字节
        first_byte = (0x80 if fin else 0x00) | (rsv << 4) | opcode
        
        # 第二个字节 (含载荷长度)
        second_byte = 0x80 if mask else 0x00
        
        # 处理载荷长度部分
        payload_length_data = bytearray()
        if payload_length <= 125:
            second_byte |= payload_length
        elif payload_length <= 65535:
            second_byte |= 126
            payload_length_data += struct.pack(">H", payload_length)
        else:
            second_byte |= 127
            payload_length_data += struct.pack(">Q", payload_length)
        
        # 组合头数据
        header_bytes = bytes([first_byte, second_byte]) + payload_length_data
        return header_bytes
    
    @staticmethod
    def _mask_data(data: bytes, masking_key: bytes) -> bytes:
        """应用XOR掩码到数据"""
        # 使用 bytearray 高效处理
        masked = bytearray(data)
        mask_arr = bytearray(masking_key)
        
        # 逐字节应用掩码
        for i in range(len(masked)):
            masked[i] ^= mask_arr[i % 4]
            
        return masked

class WebSocketMessageFactory:
    """WebSocket 消息工厂
    
    提供基于操作码创建不同类型的消息对象
    """
    
    @staticmethod
    def create(opcode: Union[Opcode, int], data: Any = b"", **kwargs) -> Message:
        """基于操作码创建对应的消息对象"""
        opcode_int = opcode.value if isinstance(opcode, Opcode) else opcode
        
        # 处理控制消息
        if opcode_int == Opcode.CLOSE.value:
            # 分离关闭代码和原因
            code, reason = WebSocketMessageFactory._decode_close_data(data)
            return CloseControlMessage(code=code, reason=reason)
        
        # 根据操作码选择消息类
        message_class = {
            Opcode.TEXT.value: TextMessage,
            Opcode.BINARY.value: BinaryMessage,
            Opcode.PING.value: PingControlMessage,
            Opcode.PONG.value: PongControlMessage,
            Opcode.CONTINUATION.value: partial(
                Message, 
                opcode=Opcode.CONTINUATION
            )
        }.get(opcode_int)
        
        if not message_class:
            raise ValueError(f"Unsupported opcode: {opcode_int}")
        
        return message_class(data=data, **kwargs)
    
    @staticmethod
    def _decode_close_data(data: bytes) -> Tuple[int, str]:
        """解析关闭帧数据为代码和原因"""
        code = 1000  # 默认正常关闭
        reason = ""
        
        if len(data) == 0:
            return code, reason
            
        # 解析状态码 (前2字节)
        if len(data) >= 2:
            code = struct.unpack(">H", data[:2])[0]
            
            # 检查状态码有效性
            if code not in VALID_CLOSING_CODES and not (2999 <= code <= 4999):
                code = 1003  # 无效关闭码
        
        # 解析原因 (剩余字节)
        if len(data) > 2:
            try:
                reason_bytes = data[2:]
                reason = reason_bytes.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                # 宽松处理无效UTF-8序列
                reason = reason_bytes.decode("latin-1", errors="replace")
        
        return code, reason

class MessageBuilder:
    """高级消息构建器
    
    功能:
    - 辅助构建各种类型的消息
    - 支持超大消息的分片处理
    - 自动处理编码和掩码
    """
    
    MAX_FRAGMENT_SIZE = 2**14 - 500  # ~16KB 分片大小
    
    @staticmethod
    def create_close(code: int = 1000, reason: str = "") -> CloseControlMessage:
        """创建关闭消息"""
        return CloseControlMessage(code=code, reason=reason)
    
    @staticmethod
    def create_ping(data: Union[str, bytes] = b"") -> PingControlMessage:
        """创建 Ping 消息"""
        return PingControlMessage(data=data)
    
    @staticmethod
    def create_pong(data: Union[str, bytes] = b"") -> PongControlMessage:
        """创建 Pong 消息"""
        return PongControlMessage(data=data)
    
    @staticmethod
    def create_text(text: str, encoding: str = "utf-8") -> TextMessage:
        """创建文本消息"""
        return TextMessage(data=text, encoding=encoding)
    
    @staticmethod
    def create_binary(data: Union[bytes, bytearray]) -> BinaryMessage:
        """创建二进制消息"""
        return BinaryMessage(data=data)
    
    @staticmethod
    def fragment_message(
        message: Message, 
        fragment_size: int = MAX_FRAGMENT_SIZE,
        mask: bool = False
    ) -> Generator[bytes, None, None]:
        """将大消息分片为多个帧
        
        参数:
            message: 要分片的消息对象
            fragment_size: 每个分片的最大大小
            mask: 是否应用掩码
            
        返回:
            帧生成器
        """
        data_bytes = message.as_bytes()
        total_length = len(data_bytes)
        num_fragments = max(1, (total_length + fragment_size - 1) // fragment_size)
        
        # 构建分片
        for i in range(num_fragments):
            # 确定分片范围
            start = i * fragment_size
            stop = min((i + 1) * fragment_size, total_length)
            fragment = data_bytes[start:stop]
            
            # 判断是否为第一个分片
            is_first = (i == 0)
            # 判断是否为最后一个分片
            is_last = (i == num_fragments - 1)
            
            # 构建帧
            yield FrameBuilder.build(
                body=fragment,
                opcode=message.opcode.value,
                mask=mask,
                is_first=is_first,
                is_last=is_last
            )

# 使用示例
if __name__ == "__main__":
    def demo_message_factory():
        """演示消息工厂使用"""
        print("\n=== WebSocket Message Factory ===")
        
        # 创建文本消息
        text_msg = WebSocketMessageFactory.create(Opcode.TEXT, "Hello, World!")
        print(f"Text message: {text_msg}")
        print(f"Frame: {text_msg.build_frame()[:20]}...")
        
        # 创建关闭消息
        close_msg = WebSocketMessageFactory.create(
            Opcode.CLOSE, 
            struct.pack(">H", 1001) + b"Service restart"
        )
        print(f"\nClose message: {close_msg}")
        
        # 从二进制数据创建关闭消息
        close_msg2 = WebSocketMessageFactory.create(
            Opcode.CLOSE.value,
            b"\x03\xe8Connection closed"  # 代码1000 + 原因
        )
        print(f"Close message2: {close_msg2}")
    
    def demo_frame_fragmentation():
        """演示消息分片功能"""
        print("\n=== Message Fragmentation ===")
        
        # 创建一个大文本消息 (50KB)
        big_text = "A" * 50 * 1024
        text_msg = TextMessage(data=big_text)
        
        # 分片成多个帧
        fragments = list(MessageBuilder.fragment_message(
            text_msg, 
            fragment_size=MessageBuilder.MAX_FRAGMENT_SIZE
        ))
        
        print(f"Original message size: {len(text_msg) / 1024:.2f}KB")
        print(f"Number of fragments: {len(fragments)}")
        print(f"First fragment size: {len(fragments[0])/1024:.2f}KB")
        print(f"Last fragment size: {len(fragments[-1])} bytes")
        
        # 显示第一个帧的头信息
        frame_header = fragments[0][:20]
        print(f"First frame header: {frame_header}")
    
    def demo_message_builder():
        """演示消息构建器使用"""
        print("\n=== Message Builder ===")
        
        # 构建基本消息
        ping_msg = MessageBuilder.create_ping(b"Ping payload")
        print(f"Ping message: {ping_msg}")
        print(f"Frame: {ping_msg.build_frame()[:20]}...")
        
        # 构建带掩码的消息
        text_msg = MessageBuilder.create_text("Hello, with mask!")
        text_frame = text_msg.build_frame(mask=True)
        print(f"\nMasked text frame: {text_frame[:20]}...")
        
        # 构建二进制消息
        binary_data = os.urandom(100)  # 100字节随机数据
        binary_msg = MessageBuilder.create_binary(binary_data)
        print(f"\nBinary message: {binary_msg}")
    
    # 运行演示
    demo_message_factory()
    demo_frame_fragmentation()
    demo_message_builder()
