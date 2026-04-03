#!/usr/bin/env python3
"""
高级字节处理工具集
针对 Python3 优化的高效字节/字符串转换处理
支持高效拼接、智能编解码和内存优化操作
"""

import sys
from typing import Optional, Union, Iterable, ByteString

# 常量定义
NULL = b"\x00"
"""STOMP协议中的空字符分隔符"""

UTF8_ENCODING = "utf-8"
"""默认UTF-8编码配置"""


def input_prompt(prompt: str) -> str:
    """
    获取用户输入（支持输入验证和安全处理）
    
    :param prompt: 提示信息
    :return: 用户输入的安全字符串（去除非必需的控制字符）
    
    >>> input_prompt("Enter your name: ")
    """
    # 输入过滤（安全处理）
    safe_prompt = prompt.strip().replace("\n", "").replace("\r", "").replace("\x00", "")
    if safe_prompt != prompt:
        raise ValueError("输入提示包含危险控制字符")
        
    response = input(safe_prompt)
    
    # 移除潜在危险字符
    return "".join(
        c for c in response 
        if c.isprintable() or c in '\t\n\r'
    ).strip()


def decode(
    byte_data: Optional[ByteString], 
    encoding: str = UTF8_ENCODING, 
    errors: str = "strict"
) -> Optional[str]:
    """
    智能字节解码器（带错误处理）
    
    :param byte_data: 要解码的字节数据（None则返回None）
    :param encoding: 字符编码（默认UTF-8）
    :param errors: 错误处理策略 ("ignore", "replace", "backslashreplace")
    :return: 解码后的字符串或原始None
    
    >>> decode(b'hello\xc3\x9f')
    'helloß'
    >>> decode(b'invalid\xff', errors='replace')
    'invalid�'
    """
    if byte_data is None:
        return None
        
    try:
        return byte_data.decode(encoding, errors=errors)
    except LookupError:
        # 无效编码策略时的后备方案
        return byte_data.decode(encoding, errors="replace")


def encode(
    char_data: Union[str, bytes, bytearray],
    encoding: str = UTF8_ENCODING,
    errors: str = "strict"
) -> bytes:
    """
    通用数据编码器（智能类型处理）
    
    :param char_data: 可编码对象（字符串/字节/其他）
    :param encoding: 字符编码（默认UTF-8）
    :param errors: 错误处理策略
    :return: 字节表示
    
    >>> encode("hello")
    b'hello'
    >>> encode(123.45)
    b'123.45'
    >>> encode(b'already bytes')
    b'already bytes'
    """
    if isinstance(char_data, bytes):
        return char_data  # 已经是字节则无需处理
    elif isinstance(char_data, bytearray):
        return bytes(char_data)
    elif isinstance(char_data, str):
        return char_data.encode(encoding, errors=errors)
    else:
        # 其他类型的安全字符串转换
        return str(char_data).encode(encoding, errors=errors)


def pack(pieces: Iterable[Union[str, bytes]]) -> bytes:
    """
    高效拼接字节序列（零拷贝优化）
    
    :param pieces: 可迭代的字符串/字节序列
    :return: 拼接后的字节
    
    >>> pack(['hello', b' ', 'world'])
    b'hello world'
    
    >>> pack([])  # 空输入
    b''
    """
    # 快速路径：纯字节序列
    if all(isinstance(p, bytes) for p in pieces):
        return b"".join(tuple(pieces))
    
    # 混合输入路径
    buffer = bytearray()
    for piece in pieces:
        if isinstance(piece, bytes):
            buffer += piece
        else:
            buffer += encode(piece)
    return bytes(buffer)


def join(
    chunks: Iterable[Union[bytes, int]], 
    encoding: str = UTF8_ENCODING,
    errors: str = "strict"
) -> str:
    """
    字节序列连接器（增量式解码优化内存）
    
    :param chunks: 字节/整数序列（单字节整数[0-255]）
    :param encoding: 字符编码（默认UTF-8）
    :param errors: 错误处理策略
    :return: 连接并解码后的字符串
    
    >>> join([b'he', b'llo'])
    'hello'
    
    >>> join([104, 101, 108, 108, 111])  # ASCII码点
    'hello'
    """
    # 高效内存处理
    if all(isinstance(c, bytes) for c in chunks):
        # 纯字节路径
        return decode(b"".join(chunks), encoding, errors)
    
    # 处理混合字节和整数
    decoded_parts = []
    buffer = bytearray()
    for chunk in chunks:
        if isinstance(chunk, int):
            buffer.append(chunk)
        elif chunk:  # 忽略空字节
            if buffer:
                decoded_parts.append(buffer.decode(encoding, errors))
                buffer.clear()
            decoded_parts.append(decode(chunk, encoding, errors))
    
    if buffer:
        decoded_parts.append(buffer.decode(encoding, errors))
    
    return "".join(decoded_parts)


def is_binary_data(data: bytes) -> bool:
    """
    检测字节数据是否为二进制
    
    :param data: 待检测字节
    :return: 是否是二进制数据
    
    >>> is_binary_data(b'text data')  # False
    >>> is_binary_data(b'PNG\x89...')  # True
    """
    # 空数据认为是文本
    if not data:
        return False
    
    # 检测非文本字符比例
    non_text_count = sum(
        1 for byte in data
        if byte < 0x20 and byte not in (0x09, 0x0A, 0x0D)  # 排除空白符
        or byte >= 0x7F  # 高位字节
    )
    return bool(non_text_count / len(data) > 0.25)  # >25%非文本即判为二进制


def safe_decode(
    data: bytes, 
    fallback_encoding: str = "latin-1",
    detect_binary: bool = True
) -> str:
    """
    安全解码器（自动处理编码问题）
    
    :param data: 待解码字节
    :param fallback_encoding: 备选编码方案
    :param detect_binary: 是否自动检测二进制内容
    :return: 最可能正确的解码字符串
    
    >>> safe_decode(b'invalid\xff')
    'invalidÿ'
    """
    if detect_binary and is_binary_data(data):
        return f"<Binary data: {len(data)} bytes>"
    
    try:
        # 优先尝试UTF-8解码
        return data.decode(UTF8_ENCODING)
    except UnicodeDecodeError:
        # 尝试替代编码方案
        try:
            return data.decode(fallback_encoding, errors="replace")
        except LookupError:
            # 终极后备方案：直接显示十六进制
            return f"Hex: {data.hex()}"
