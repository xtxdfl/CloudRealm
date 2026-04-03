#!/usr/bin/env python3
"""
高级 PKCS#7 填充工具
~~~~~~~~~~~~~~~~~~~~

提供符合 RFC 5652 标准的 PKCS#7 填充实现，支持：
- 自适应的块大小填充
- 严格的填充验证
- 多种数据格式支持
- 全面的错误处理
- 可配置的安全策略

核心功能:
--------
• PKCS#7 填充生成
• PKCS#7 填充去除
• 多数据格式支持
• 块大小自适应
• 安全策略配置
• 性能优化

改进点:
--------
1. 放弃 Python 2 兼容，专注 Python 3 实现
2. 增强类型提示和文档注释
3. 添加自适应块大小支持
4. 强化安全验证机制
5. 优化数据转换接口
6. 增加单元测试友好接口
"""

from typing import Union, ByteString

# 默认块大小（AES标准）
DEFAULT_BLOCK_SIZE = 16

def ensure_bytes(data: Union[ByteString, str, int]) -> bytes:
    """
    将不同类型的数据转换为字节格式
    
    :param data: 输入数据（字节、字符串、整数等）
    :return: 字节表示
    :raises TypeError: 当输入类型不支持时
    """
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, str):
        return data.encode('utf-8')
    if isinstance(data, int):
        return data.to_bytes((data.bit_length() + 7) // 8, 'big')
    
    raise TypeError(f"不支持的输入类型: {type(data)}")

def validate_block_size(block_size: int) -> None:
    """
    验证块大小是否有效
    
    :param block_size: 块大小
    :raises ValueError: 当块大小无效时
    """
    if not (1 <= block_size <= 255):
        raise ValueError(f"无效的块大小: {block_size} (1-255)")
    if block_size % 8 != 0:
        raise ValueError("块大小必须是8的倍数")
    return block_size

def pad_pkcs7(
    data: Union[ByteString, str, int], 
    block_size: int = DEFAULT_BLOCK_SIZE
) -> bytes:
    """
    应用符合 RFC 5652 标准的 PKCS#7 填充
    
    :param data: 要填充的数据（字节、字符串或整数）
    :param block_size: 块大小（默认16字节）
    :return: 填充后的字节数据
    """
    # 验证并处理块大小
    block_size = validate_block_size(block_size) if block_size else DEFAULT_BLOCK_SIZE
    
    # 转换为字节
    binary_data = ensure_bytes(data)
    
    # 计算填充长度
    padding_length = block_size - (len(binary_data) % block_size)
    if padding_length == 0:
        padding_length = block_size
    
    # 应用填充
    if not (1 <= padding_length <= block_size):
        raise RuntimeError(f"无效的填充长度: {padding_length}")
    
    padding = bytes([padding_length] * padding_length)
    return binary_data + padding

def unpad_pkcs7(
    padded_data: Union[ByteString, str], 
    block_size: int = DEFAULT_BLOCK_SIZE,
    strict_mode: bool = True
) -> bytes:
    """
    去除 PKCS#7 填充并验证其有效性
    
    :param padded_data: 填充后的数据
    :param block_size: 块大小（默认16字节）
    :param strict_mode: 启用严格的填充验证（默认True）
    :return: 去除填充的原始数据
    :raises ValueError: 当填充无效时
    """
    # 验证并处理块大小
    block_size = validate_block_size(block_size) if block_size else DEFAULT_BLOCK_SIZE
    
    # 转换为字节
    if isinstance(padded_data, str):
        padded_bytes = padded_data.encode('utf-8')
    else:
        padded_bytes = bytes(padded_data)
    
    # 检查最小数据长度
    if len(padded_bytes) < block_size:
        raise ValueError("数据长度小于块大小")
    
    # 检查数据块对齐
    if len(padded_bytes) % block_size != 0:
        if strict_mode:
            raise ValueError("数据长度不是块大小的倍数")
        # 非严格模式下自动添加额外填充
        padded_bytes = pad_pkcs7(padded_bytes, block_size)[:len(padded_bytes)]
    
    try:
        # 获取填充值（最后一个字节）
        padding_value = padded_bytes[-1]
    except IndexError:
        raise ValueError("空数据无法去除填充")
    
    # 验证填充值范围
    if not (1 <= padding_value <= block_size):
        raise ValueError(f"无效的填充值: {padding_value} (1-{block_size})")
    
    # 计算原始数据结束位置
    unpadded_length = len(padded_bytes) - padding_value
    
    # 验证负长度情况
    if unpadded_length < 0:
        raise ValueError("填充值大于数据长度")
    
    # 在严格模式下验证每个填充字节
    if strict_mode:
        expected_padding = bytes([padding_value] * padding_value)
        actual_padding = padded_bytes[unpadded_length:]
        
        if actual_padding != expected_padding:
            raise ValueError("填充字节不一致")
    
    # 返回原始数据
    return padded_bytes[:unpadded_length]

# 简化的兼容别名（向后兼容）
to_bufferable = ensure_bytes
append_PKCS7_padding = pad_pkcs7
strip_PKCS7_padding = unpad_pkcs7

if __name__ == '__main__':
    # 演示示例
    original_str = "Hello, PKCS#7! 😊"
    
    try:
        print("\nPKCS#7 填充演示")
        print("=" * 60)
        
        # 默认块大小（16）填充示例
        print(f"原始数据: '{original_str}'")
        
        padded_data = pad_pkcs7(original_str)
        print(f"\n填充后 (16字节块): {padded_data!r}")
        
        # 验证填充操作是否正确
        unpadded_data = unpad_pkcs7(padded_data)
        print(f"\n去除填充: '{unpadded_data.decode('utf-8')}'")
        
        # 尝试去除无效填充（应该失败）
        try:
            print("\n测试无效填充:")
            corrupt_data = padded_data[:-1] + b'\x00'
            unpadded_data = unpad_pkcs7(corrupt_data)
        except ValueError as e:
            print(f"  检测到无效填充: {e}")
        
        # 使用不同块大小测试
        print("\n8字节块测试:")
        padded_data = pad_pkcs7("Short", 8)
        print(f"  填充后: {padded_data!r}")
        
        unpadded_data = unpad_pkcs7(padded_data, 8)
        print(f"  去除填充: '{unpadded_data.decode('utf-8')}'")
        
        # 测试整数输入
        print("\n整数输入测试:")
        padded_data = pad_pkcs7(123456789, 12)
        print(f"  填充后: {padded_data!r}")
        
        # 测试空输入
        print("\n空输入测试:")
        padded_data = pad_pkcs7("", 10)
        print(f"  填充空数据: {padded_data!r}")
        
        unpadded_data = unpad_pkcs7(padded_data, 10)
        print(f"  去除空数据填充: {unpadded_data!r}")
    
    except Exception as e:
        print(f"\n错误: {str(e)}")
        print("=" * 60)
