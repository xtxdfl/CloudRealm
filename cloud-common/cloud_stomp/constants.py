#!/usr/bin/env python3
"""
STOMP 1.2 协议完整常量定义
包含命令、头部、内容类型及规范定义的所有属性

参考规范: 
  STOMP 1.0: https://stomp.github.io/stomp-specification-1.0.html
  STOMP 1.1: https://stomp.github.io/stomp-specification-1.1.html
  STOMP 1.2: https://stomp.github.io/stomp-specification-1.2.html
"""

from enum import Enum, unique

__all__ = [
    'Command',
    'Header',
    'ContentType',
    'AckMode',
    'SpecVersion',
    'SPEC_VERSIONS',
    'STOMP_ENCODING',
]

# 协议标准编码
STOMP_ENCODING = 'utf-8'

# 支持协议版本列表
SPEC_VERSIONS = ['1.0', '1.1', '1.2']


@unique
class SpecVersion(str, Enum):
    """
    STOMP 规范版本定义
    完全兼容 STOMP 1.0, 1.1 和 1.2 协议
    """
    V10 = '1.0'
    V11 = '1.1'
    V12 = '1.2'
    
    def __str__(self):
        return self.value


@unique
class Command(str, Enum):
    """
    STOMP 协议命令集 - 所有标准及扩展命令
    根据 STOMP 1.2 规范定义
    """
    # ---------- 客户端命令 ----------
    CONNECT    = 'CONNECT'     # 建立连接
    STOMP      = 'STOMP'       # 1.1+ 连接命令
    DISCONNECT = 'DISCONNECT'  # 断开连接
    SEND       = 'SEND'       # 发送消息
    SUBSCRIBE  = 'SUBSCRIBE'   # 订阅目标
    UNSUBSCRIBE = 'UNSUBSCRIBE' # 取消订阅
    ACK        = 'ACK'         # 消息确认
    NACK       = 'NACK'        # 消息否定确认
    BEGIN      = 'BEGIN'       # 开始事务
    COMMIT     = 'COMMIT'      # 提交事务
    ABORT      = 'ABORT'       # 中止事务
    
    # ---------- 服务端命令 ----------
    CONNECTED  = 'CONNECTED'   # 连接响应
    MESSAGE    = 'MESSAGE'     # 消息传递
    RECEIPT    = 'RECEIPT'     # 收据通知
    ERROR      = 'ERROR'       # 错误通知
    
    # ---------- 心跳命令 ----------
    HEARTBEAT  = '\n'          # 心跳帧
    
    def __str__(self):
        return self.value


@unique
class Header(str, Enum):
    """
    STOMP 协议头部键名 - 所有标准及可选头部
    
    每个头部包含文档说明和适用协议版本
    """
    # ========== 连接相关 ==========
    ACCEPT_VERSION = 'accept-version'  # [客户端] 支持的协议版本
    HOST = 'host'                      # [客户端] 连接的虚拟主机名
    LOGIN = 'login'                    # [客户端] 认证用户名
    PASSCODE = 'passcode'              # [客户端] 认证密码
    HEARTBEAT = 'heart-beat'           # [客户端/服务端] 心跳配置 (cx, cy)
    
    # ========== 会话相关 ==========
    SESSION = 'session'                # [服务端] 会话标识符
    SERVER = 'server'                  # [服务端] 服务器标识
    VERSION = 'version'                # [服务端] 实际使用协议版本
    
    # ========== 消息传输 ==========
    DESTINATION = 'destination'        # [客户端/服务端] 消息目标地址
    CONTENT_TYPE = 'content-type'      # [客户端/服务端] 消息内容类型
    CONTENT_LENGTH = 'content-length'  # [客户端/服务端] 消息内容长度(字节)
    MESSAGE_ID = 'message-id'          # [服务端] 消息唯一标识
    SUBSCRIPTION = 'subscription'      # [服务端] 订阅标识
    ACK = 'ack'                        # [客户端] 订阅确认模式
    
    # ========== 事务管理 ==========
    TRANSACTION = 'transaction'        # [客户端] 事务标识符
    
    # ========== 回执通知 ==========
    RECEIPT = 'receipt'                # [客户端] 请求操作回执ID
    RECEIPT_ID = 'receipt-id'          # [服务端] 回执ID
    
    # ========== 消息处理 ==========
    EXPIRES = 'expires'                # [客户端] 消息过期时间(毫秒)
    PERSISTENT = 'persistent'          # [客户端] 消息持久化标志(true/false)
    PRIORITY = 'priority'              # [客户端] 消息优先级(0-9)
    TIMESTAMP = 'timestamp'            # [客户端] 消息创建时间(纪元毫秒)
    MESSAGE = 'message'                # [服务端] 错误信息描述
    TYPE = 'type'                      # [服务端] 错误类型标识
    
    # ========== 消息确认 ==========
    ACK_ID = 'ack-id'                  # [客户端] 要确认的消息ID
    ID = 'id'                          # [客户端] 订阅ID/确认ID
    
    # ========== 1.1+ 新增 ==========
    ACCEPT_ENCODING = 'accept-encoding' # [客户端] 支持的压缩编码
    CONTENT_ENCODING = 'content-encoding' # [服务端] 内容实际压缩编码
    RETRY_DELAY = 'retry-delay'          # [服务端] 重试延迟时间(毫秒)
    EXPIRATION = 'expiration'          # [客户端] 消息过期时间(ISO8601)
    
    # ========== 自定义头部 ==========
    CUSTOM_PREFIX = 'x-'               # 自定义头部前缀
    
    def __str__(self):
        return self.value
    
    @property
    def is_custom(self):
        """检查是否为自定义头部"""
        return self.name.startswith('x-')

    @classmethod
    def create_custom(cls, name):
        """创建自定义头部"""
        if not name.startswith(cls.CUSTOM_PREFIX):
            name = f"{cls.CUSTOM_PREFIX}{name}"
        return name


@unique
class ContentType(str, Enum):
    """
    STOMP 消息常用内容类型
    完整 MIME 类型参考: https://www.iana.org/assignments/media-types
    """
    TEXT_PLAIN = 'text/plain'             # 纯文本
    TEXT_HTML = 'text/html'               # HTML格式文本
    TEXT_XML = 'text/xml'                 # XML格式文本
    TEXT_JSON = 'text/json'               # JSON格式文本
    TEXT_MARKDOWN = 'text/markdown'       # Markdown格式文本
    APPLICATION_JSON = 'application/json' # JSON应用数据
    APPLICATION_XML = 'application/xml'   # XML应用数据
    APPLICATION_OCTET_STREAM = 'application/octet-stream'  # 二进制数据
    APPLICATION_ZIP = 'application/zip'   # ZIP压缩数据
    APPLICATION_PDF = 'application/pdf'   # PDF文档
    
    # 企业消息系统常用类型
    ACTIVEMQ_MAP='jms/map-message'        # ActiveMQ Map消息
    ACTIVEMQ_OBJECT='jms/object-message'  # ActiveMQ 对象消息
    
    def __str__(self):
        return self.value
    
    @classmethod
    def for_data(cls, data):
        """
        根据数据类型推断合适的内容类型
        :param data: 消息数据
        :return: 推荐的内容类型
        """
        if isinstance(data, bytes):
            return cls.APPLICATION_OCTET_STREAM
        if isinstance(data, str):
            return cls.TEXT_PLAIN
        if data is None:
            return ''
        return cls.APPLICATION_JSON


@unique
class AckMode(str, Enum):
    """
    消息确认模式 - 用于订阅头部的 ack 属性
    """
    AUTO = 'auto'         # 自动确认 (默认)
    CLIENT = 'client'     # 客户端手动确认
    CLIENT_INDIVIDUAL = 'client-individual'  # 客户端单独确认 (1.2+)
    
    def __str__(self):
        return self.value


class StompConstantsMeta(type):
    """
    常量类的元类 - 提供额外的验证和工具方法
    """
    def __iter__(cls):
        """迭代所有命令或头部"""
        return iter(cls.__members__.values())
    
    def __getitem__(cls, key):
        """通过名称获取常量"""
        return cls.__members__[key]
    
    def get(cls, value, default=None):
        """通过值获取枚举成员"""
        return next((m for m in cls if m.value == value), default)


if __name__ == '__main__':
    # 示例用法
    print("STOMP协议版本:", SpecVersion.V12)
    print("消息命令:", Command.MESSAGE)
    print("目标头部:", Header.DESTINATION)
    print("文本内容类型:", ContentType.TEXT_PLAIN)
    print("客户端确认模式:", AckMode.CLIENT)
    
    # 自定义头部使用
    custom_header = Header.create_custom('my-custom-header')
    print(f"自定义头部: {custom_header}")
    
    # 内容类型推断
    print(f"二进制数据推荐类型: {ContentType.for_data(b'data')}")
    print(f"文本数据推荐类型: {ContentType.for_data('text')}")
    print(f"对象数据推荐类型: {ContentType.for_data({'key':'value'})}")
