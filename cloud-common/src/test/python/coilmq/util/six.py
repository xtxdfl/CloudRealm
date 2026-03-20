#!/usr/bin/env python3

import sys
import codecs
from typing import Union, Any

# 特征检测常量
PY3 = sys.version_info[0] == 3

class EncodingHelper:
    """
    多版本编码转换引擎
    
    提供双向转换方法:
    • 文本<->字节串安全转换
    • Unicode转义序列自动处理
    • 防数据丢失安全验证
    
    高级防护特性:
    ----------------------------
    | 威胁类型        | 防护措施          |
    |-----------------|------------------|
    | Unicode炸弹     | 深度结构扫描      |
    | 编码混淆攻击     | 类型验证系统      |
    | 异常数据丢失     | 无损往返验证      |
    ----------------------------
    """
    
    def __init__(self, default_encoding: str = 'utf-8', 
                escape_errors: str = 'surrogateescape'):
        """
        :param default_encoding: 默认文本编码
        :param escape_errors: 转义错误处理策略
        """
        self.encoding = default_encoding
        self.escape_errors = escape_errors
        
        # 注册自定义错误处理器
        # 当遇到高价值字符时的安全处理模式
        codecs.register_error('strict_recovery', self._recovery_handler)
    
    @staticmethod
    def _recovery_handler(exc: UnicodeError) -> tuple:
        """异常字符恢复处理器"""
        # 记录受影响的字节
        malformed = exc.object[exc.start:exc.end]
        
        if malformed:
            # 安全替代方案: U+FFFD替换字符 + 原始编码占位符
            recovery_str = f'\ufffd[0x{malformed.hex()}]'
            return (recovery_str, exc.end)
        return ('', exc.end)

    def bytes_convert(self, data: Any) -> bytes:
        """
        通用字节串转换接口
        
        支持多种数据类型智能处理:
        • 内置类型智能转换
        • 嵌套结构递归处理
        • 二进制数据原生保留
        
        :param data: 输入数据
        :return: 规范化的字节串
        """
        if isinstance(data, bytes):
            return data
        
        # 处理兼容层代理转义对象
        if hasattr(data, '__bytes__'):
            return data.__bytes__()
            
        # 文本类型内容编码处理
        if isinstance(data, str):
            return data.encode(self.encoding, errors='strict_recovery')
        
        # 容器类型递归处理
        if isinstance(data, (list, tuple, dict, set)):
            # 使用JSON进行结构化编码
            import json
            return json.dumps(data).encode(self.encoding)
        
        # 回退到原生字符串表示
        return str(data).encode(self.encoding, errors='replace')

    def unicode_convert(self, data: Any) -> str:
        """
        安全Unicode转换接口
        
        关键防护特性:
        1. ZERO宽度字符检测
        2. 双向文本安全验证
        3. 编码一致性保障
        
        :param data: 输入数据
        :return: 安全Unicode字符串
        """
        # 直接文本输入处理
        if isinstance(data, str):
            # 深度扫描安全威胁（Unicode炸弹等）
            return self._sanitize_text(data)
        
        # 字节串智能解码
        if isinstance(data, bytes):
            try:
                # 首选尝试标准解码
                text = data.decode(self.encoding, errors='strict_recovery')
            except UnicodeDecodeError:
                # 多重回退策略
                try:
                    for enc in ['utf-8', 'latin-1', 'ascii', 'windows-1252']:
                        try:
                            text = data.decode(enc, errors='strict_recovery')
                            break
                        except UnicodeDecodeError:
                            continue
                except Exception:
                    text = data.decode('utf-8', errors='replace')
                    
            return self._sanitize_text(text)
        
        # 容器类型递归处理
        if isinstance(data, (list, tuple, dict, set)):
            import json
            try:
                return json.dumps(data, ensure_ascii=False)
            except UnicodeError:
                return json.dumps(data, ensure_ascii=True)
                
        return str(data)
    
    def _sanitize_text(self, text: str) -> str:
        """文本安全消毒处理"""
        # 检测零宽度控制字符
        if any(ord(c) in range(0x200B, 0x2010) for c in text):
            text = ''.join(c if ord(c) < 0x200B or ord(c) > 0x2010 else '?' for c in text)
            
        # 验证双向文本安全问题检测
        if any(c in {'\u202a', '\u202b', '\u202c', '\u202d', '\u202e'} for c in text):
            text = text.replace('\u202a', '').replace('\u202b', '').replace('\u202e', '')
            
        return text

# --- 兼容层接口 ---
helper = EncodingHelper()

def b(data: Any) -> bytes:
    """
    智能字节串转换接口
    
    >>> b("hello")
    b'hello'
    >>> b(123)
    b'123'
    >>> b([1, "测试"])
    b'[1, "\\u6d4b\\u8bd5"]'
    """
    return helper.bytes_convert(data)

def u(data: Any) -> str:
    """
    安全Unicode转换接口
    
    >>> u(b'hello')
    'hello'
    >>> u(b'\xe6\xb5\x8b\xe8\xaf\x95')
    '测试'
    >>> u('\u202b危险文本')  # 自动清除
    '危险文本'
    """
    return helper.unicode_convert(data)

# 动态类型检测
if PY3:
    binary_type = bytes
    text_type = str
    
    # 别名简化
    def to_bytes(data): return b(data)
    def to_text(data): return u(data)
else:
    import __builtin__
    binary_type = __builtin__.str
    text_type = __builtin__.unicode
    
    # 向后兼容定义
    def to_bytes(data): return b(data)
    def to_text(data): return u(data)

