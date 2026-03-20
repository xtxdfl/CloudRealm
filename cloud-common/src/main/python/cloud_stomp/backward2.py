#!/usr/bin/env python
"""
企业级 Python 2 兼容性工具包
提供安全文本编码、协议帧处理、输入验证和错误恢复功能
专为 Python 2.7 及以下版本设计，支持 STOMP 协议
"""

import sys
import codecs
import struct
import re
from functools import wraps

# Python 2 特定导入
if sys.version_info[0] == 2:
    import cStringIO as StringIO
else:
    # 确保在 Python 3 环境中也能导入
    from io import StringIO

# 编码格式常量
STOMP_ENCODING = "utf-8"
FALLBACK_ENCODING = "latin-1"

# STOMP 协议常量
NULL_CHAR = "\x00"
LINE_SEPARATOR = "\n"
HEADER_SEPARATOR = ":"

# 错误处理策略
ERROR_HANDLERS = {
    "strict": codecs.lookup_error("strict"),
    "ignore": codecs.lookup_error("ignore"),
    "replace": codecs.lookup_error("replace"),
}

# 内存优化 - 预编译正则表达式
CONTENT_LENGTH_PATTERN = re.compile(r"\bcontent-length\s*:\s*(\d+)", re.IGNORECASE)
CONTENT_TYPE_PATTERN = re.compile(r"\bcontent-type\s*:\s*charset\s*=\s*([\w-]+)", re.IGNORECASE)

class StompEncodingError(UnicodeError):
    """STOMP 协议编码异常"""
    
    def __init__(self, message, problematic_bytes, encoding=STOMP_ENCODING):
        super(StompEncodingError, self).__init__(message)
        self.reason = message
        self.encoding = encoding
        self.object = problematic_bytes
        
        # 错误诊断信息
        self.byte_position = -1
        if problematic_bytes:
            sample = problematic_bytes[:20] + (b'...' if len(problematic_bytes) > 20 else b'')
            self.diagnostic = f"编码问题: {self.reason} (输入样例: {_bytes_to_hex(sample)})"
        else:
            self.diagnostic = message

    def __str__(self):
        return self.diagnostic


def _bytes_to_hex(byte_data, max_length=50):
    """将字节显示为十六进制格式用于诊断"""
    if not byte_data:
        return "<empty>"
    
    hex_str = " ".join(f"{b:02X}" for b in byte_data[:max_length])
    if len(byte_data) > max_length:
        hex_str += " ..."
    return hex_str


def encode_with_context(func):
    """编码上下文装饰器，捕获位置信息"""
    @wraps(func)
    def wrapper(char_data, *args, **kwargs):
        try:
            return func(char_data, *args, **kwargs)
        except UnicodeEncodeError as e:
            # 捕获具体错误位置
            problematic_bytes = char_data.encode(STOMP_ENCODING, errors='replace')
            raise StompEncodingError(
                f"编码失败: {e.reason}",
                problematic_bytes=problematic_bytes,
                encoding=e.encoding
            ) from e
    return wrapper


def decode_with_context(func):
    """解码上下文装饰器，捕获位置信息"""
    @wraps(func)
    def wrapper(byte_data, *args, **kwargs):
        try:
            return func(byte_data, *args, **kwargs)
        except UnicodeDecodeError as e:
            # 捕获具体错误位置
            problematic_range = byte_data[max(0, e.start-10):e.end+10]
            raise StompEncodingError(
                f"解码失败: {e.reason} 在位置 {e.start}-{e.end}",
                problematic_bytes=problematic_range,
                encoding=e.encoding
            ) from e
    return wrapper


@encode_with_context
def encode(char_data, preferred_encoding=None, errors="replace"):
    """
    安全字符编码函数
    
    :param char_data: 输入字符数据 (unicode 或 str)
    :param preferred_encoding: 首选编码 (默认为 STOMP_ENCODING)
    :param errors: 错误处理策略 ("strict", "ignore", "replace")
    :return: 编码后的字节数据
    
    >>> encode('hello')
    b'hello'
    >>> encode(u'こんにちは')
    b'\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf'
    """
    if not char_data:
        return b''
    
    chosen_encoding = preferred_encoding or STOMP_ENCODING
    
    # 错误处理策略
    selected_handler = ERROR_HANDLERS.get(errors, ERROR_HANDLERS["replace"])
    
    # 处理不同类型输入
    if isinstance(char_data, basestring):
        if not isinstance(char_data, unicode):
            # Python 2 中 str -> unicode 转换
            try:
                char_data = unicode(char_data, chosen_encoding, errors=errors)
            except UnicodeDecodeError as e:
                # 回退处理
                char_data = unicode(char_data, FALLBACK_ENCODING, errors="replace")
        
        return char_data.encode(chosen_encoding, errors=selected_handler)
    
    # 处理非字符串类型
    try:
        string_repr = unicode(char_data)
        return string_repr.encode(chosen_encoding, errors=selected_handler)
    except Exception:
        # 最终回退
        return b''


@decode_with_context
def decode(byte_data, headers=None, errors="replace"):
    """
    智能字节解码函数
    
    :param byte_data: 输入字节数据
    :param headers: STOMP 协议头部 (用于检测编码)
    :param errors: 错误处理策略
    :return: 解码后的字符数据 (unicode)
    
    >>> decode(b'hello')
    u'hello'
    """
    if not byte_data:
        return u''
    
    # 从协议头检测编码
    detected_encoding = STOMP_ENCODING
    if headers:
        # 检测 Content-Length
        content_length_match = CONTENT_LENGTH_PATTERN.search(headers)
        if content_length_match and content_length_match.group(1).isdigit():
            content_length = int(content_length_match.group(1))
            byte_data = byte_data[:content_length]
        
        # 检测 Charset
        content_type_match = CONTENT_TYPE_PATTERN.search(headers)
        if content_type_match:
            charset = content_type_match.group(1).lower()
            try:
                codecs.lookup(charset)
                detected_encoding = charset
            except LookupError:
                pass  # 使用默认编码
    
    # 错误处理策略
    selected_handler = ERROR_HANDLERS.get(errors, ERROR_HANDLERS["replace"])
    
    try:
        return byte_data.decode(detected_encoding, errors=selected_handler)
    except UnicodeDecodeError:
        # 回退解码策略
        try:
            return byte_data.decode(STOMP_ENCODING, errors=errors)
        except UnicodeDecodeError:
            return u"".join(unichr(b) if b < 128 else u'�' for b in bytearray(byte_data))


def pack(pieces=(), encoding=STOMP_ENCODING):
    """
    高性能数据包组装
    
    :param pieces: 数据片段序列
    :param encoding: 文本编码方式
    :return: 组装后的完整字节数据
    
    >>> pack([b'hello', b' world'])
    b'hello world'
    """
    if not pieces:
        return b''
    
    # 优化处理单一元素
    if len(pieces) == 1:
        item = pieces[0]
        if isinstance(item, unicode):
            return item.encode(encoding)
        return item
    
    buffer = StringIO()
    for piece in pieces:
        if isinstance(piece, unicode):
            buffer.write(piece.encode(encoding))
        else:
            buffer.write(piece)
    
    return buffer.getvalue()


def join(charlist=(), encoding=STOMP_ENCODING):
    """
    高效字符连接
    
    :param charlist: 字符序列
    :param encoding: 文本编码方式
    :return: 连接后的 unicode 字符串
    
    >>> join([u'h', u'e', u'l', u'l', u'o'])
    u'hello'
    """
    if not charlist:
        return u''
    
    return u''.join(
        char.decode(encoding) if isinstance(char, bytes) else char
        for char in charlist
    )


def input_prompt(prompt):
    """
    安全的用户输入处理函数
    
    :param prompt: 提示信息
    :return: 用户输入的 unicode 字符串
    
    >>> name = input_prompt("请输入您的姓名: ")
    """
    if not isinstance(prompt, basestring):
        prompt = str(prompt)
    
    if isinstance(prompt, unicode):
        prompt = prompt.encode(sys.stdout.encoding or STOMP_ENCODING, "replace")
    
    try:
        raw_result = raw_input(prompt)
    except NameError:  # Python 3 兼容
        raw_result = input(prompt)
    
    # 安全解码输入
    if isinstance(raw_result, unicode):
        return raw_result
    
    try:
        return unicode(raw_result, sys.stdin.encoding or STOMP_ENCODING)
    except UnicodeDecodeError:
        return unicode(raw_result, FALLBACK_ENCODING, "replace")


def secure_buffer(data, max_size=1024 * 1024):  # 1MB
    """
    创建安全内存缓冲区，防止大内存攻击
    
    :param data: 输入数据
    :param max_size: 最大允许大小
    :return: 安全的缓冲区对象
    """
    size = len(data) if data else 0
    if size > max_size:
        raise MemoryError(f"输入数据过大 ({size} bytes > {max_size} bytes)")
    
    return StringIO.StringIO(data)


def to_unicode(obj, encoding=STOMP_ENCODING, errors='replace'):
    """安全转换为 unicode 字符串"""
    if isinstance(obj, unicode):
        return obj
    if isinstance(obj, bytes):
        return obj.decode(encoding, errors)
    if not hasattr(obj, '__str__'):
        return unicode(obj)
    
    try:
        return unicode(str(obj), encoding, errors)
    except UnicodeDecodeError:
        return u""


def extract_charset(headers):
    """从 STOMP 协议头提取字符集声明"""
    if not headers:
        return STOMP_ENCODING
    
    # 查找 'content-type' 声明
    for header, value in headers.items():
        if header.lower() == 'content-type':
            charset_match = CONTENT_TYPE_PATTERN.search(value)
            if charset_match:
                charset = charset_match.group(1).lower()
                try:
                    # 验证字符集有效性
                    codecs.lookup(charset)
                    return charset
                except LookupError:
                    pass
    
    return STOMP_ENCODING


def null_terminated(data):
    """安全移除 NULL 终止符"""
    if not data:
        return data
    
    if isinstance(data, unicode):
        return data.rstrip(NULL_CHAR)
    
    # 处理字节数据
    if isinstance(data, bytes):
        return data.rstrip(NULL_CHAR.encode(STOMP_ENCODING))
    
    # 其他类型
    return data.rstrip(bytes(NULL_CHAR, STOMP_ENCODING))


# STOMP 协议相关常量
NULL = NULL_CHAR
LINE_SEP = LINE_SEPARATOR
HEADER_SEP = HEADER_SEPARATOR

# 兼容性导出
__all__ = [
    'encode',
    'decode',
    'pack',
    'join',
    'input_prompt',
    'secure_buffer',
    'to_unicode',
    'extract_charset',
    'null_terminated',
    'NULL',
    'LINE_SEP',
    'HEADER_SEP',
    'StompEncodingError'
]


# 单元测试兼容层
if __name__ == "__main__":
    import unittest
    
    class TestStompCompatibility(unittest.TestCase):
        """测试兼容性函数集"""
        
        def test_encode_simple(self):
            self.assertEqual(encode("hello"), b"hello")
            self.assertEqual(encode(u"hello"), b"hello")
            
        def test_encode_unicode(self):
            text = u"日本語"
            encoded = encode(text)
            self.assertEqual(encoded, b'\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e')
            
        def test_decode_simple(self):
            self.assertEqual(decode(b"hello"), u"hello")
            
        def test_decode_with_content_type(self):
            headers = {"Content-Type": "text/plain; charset=windows-1251"}
            text = b'\xcf\xf0\xe8\xe2\xe5\xf2'
            decoded = decode(text, headers=headers)
            self.assertEqual(decoded, u'\u041f\u0440\u0438\u0432\u0435\u0442')  # 俄语 "привет"
            
        def test_pack_mixed(self):
            result = pack([b"hello ", u"world!"])
            self.assertEqual(result, b"hello world!")
            
        def test_input_prompt(self):
            # 模拟输入
            global input_override
            input_override = "test input"
            result = input_prompt("Enter text: ")
            self.assertEqual(result, u"test input")
            del input_override
            
        def test_secure_buffer_valid(self):
            buf = secure_buffer(b"x" * 100)
            self.assertEqual(buf.getvalue(), b"x" * 100)
            
        def test_secure_buffer_invalid(self):
            with self.assertRaises(MemoryError):
                secure_buffer(b"x" * (2 * 1024 * 1024))  # 2MB > 1MB limit
        
        # ... 更多测试用例
        
    # Windows 兼容的测试运行器
    if sys.version_info[0] == 2:
        runner = unittest.TextTestRunner(encoding='utf-8')
        unittest.main(testRunner=runner)
    else:
        unittest.main()

