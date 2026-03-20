#!/usr/bin/env python3
"""
高性能 Redis 队列存储实现

使用 Redis Streams、Lua 脚本和连接池技术提供原子化消息操作
支持自动重连和消息压缩
"""
import pickle
from typing import Optional, Iterable, Set
from contextlib import contextmanager
from redis import Redis, ConnectionPool, RedisError
from redis.client import Pipeline

from coilmq.store import QueueStore
from coilmq.config import config
from coilmq.exception import QueueError
from coilmq.util import compression

# --- 序列化优化 ---
# 使用最高效的 pickle 协议
PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL

# --- Lua 脚本 ---
# 原子化获取并删除消息
DEQUEUE_SCRIPT = """
local dest = KEYS[1]
local items = redis.call('XREAD', 'COUNT', '1', 'STREAMS', dest, '0')
if not items then return nil end

local msg_id = items[1][2][1][1]
local payload = items[1][2][1][2][2]
redis.call('XDEL', dest, msg_id)
return payload
"""

# --- 连接工厂 ---
def make_redis_store(cfg=None) -> 'RedisQueueStore':
    """创建 Redis 队列存储实例"""
    conf = cfg or config
    redis_params = dict(conf.items("redis"))
    
    # 创建连接池 (线程安全)
    pool = ConnectionPool(
        max_connections=int(redis_params.get('max_connections', 10)),
        health_check_interval=int(redis_params.get('health_check_interval', 30)),
        **redis_params
    )
    return RedisQueueStore(redis_pool=pool)

# --- 核心存储类 ---
class RedisQueueStore(QueueStore):
    """基于 Redis Streams 的队列存储实现"""
    
    def __init__(self, redis_pool: ConnectionPool = None):
        """
        :param redis_pool: Redis 连接池实例
        """
        self.pool = redis_pool or ConnectionPool()
        self.dequeue_script = None  # Lua 脚本缓存
        
        # 性能计数器
        self._ops_counter = {'enqueue': 0, 'dequeue': 0, 'requeue': 0}
        
        super().__init__()

    @contextmanager
    def _connection(self) -> Redis:
        """获取 Redis 连接 (自动回收)"""
        conn = Redis(connection_pool=self.pool)
        try:
            yield conn
        except RedisError as e:
            raise QueueError(f"Redis operation failed: {str(e)}") from e
        finally:
            conn.close()

    @contextmanager
    def _pipeline(self) -> Pipeline:
        """获取 Redis 管道 (原子批量操作)"""
        with self._connection() as conn:
            pipeline = conn.pipeline(transaction=True)
            try:
                yield pipeline
                pipeline.execute()
            except Exception:
                pipeline.reset()
                raise

    def _serialize(self, frame) -> bytes:
        """序列化消息帧 (可选压缩)"""
        data = pickle.dumps(frame, protocol=PICKLE_PROTOCOL)
        if len(data) > 1024:  # > 1KB 启动压缩
            return compression.gzip_compress(data)
        return data

    def _deserialize(self, data: bytes):
        """反序列化消息帧"""
        try:
            if data.startswith(b'\x1f\x8b'):  # Gzip 魔术头
                data = compression.gzip_decompress(data)
            return pickle.loads(data)
        except pickle.UnpicklingError as e:
            raise QueueError("Failed to deserialize message") from e

    def enqueue(self, destination: str, frame) -> None:
        """入队消息 (原子操作)"""
        with self._connection() as conn:
            serialized = self._serialize(frame)
            conn.xadd(
                name=destination,
                fields={'payload': serialized},
                maxlen=config.getint('redis', 'max_stream_length', fallback=10000)
            )
        self._ops_counter['enqueue'] += 1

    def dequeue(self, destination: str):
        """出队消息 (原子化操作, 使用Lua脚本)"""
        # 缓存脚本
        if not self.dequeue_script:
            with self._connection() as conn:
                self.dequeue_script = conn.register_script(DEQUEUE_SCRIPT)
        
        # 执行原子化操作
        try:
            with self._connection() as conn:
                result = self.dequeue_script(keys=[destination])
                if not result:
                    return None
                self._ops_counter['dequeue'] += 1
                return self._deserialize(result)
        except RedisError as e:
            # 脚本可能过期 (例如Redis重启)，重新注册
            if "NOSCRIPT" in str(e):
                self.dequeue_script = None
                return self.dequeue(destination)
            raise

    def requeue(self, destination: str, frame) -> None:
        """消息重新入队 (优先处理)"""
        with self._connection() as conn:
            serialized = self._serialize(frame)
            # 使用 LPUSH 重新添加到队列头部
            conn.lpush(destination, serialized)
        self._ops_counter['requeue'] += 1

    def size(self, destination: str) -> int:
        """获取队列长度"""
        with self._connection() as conn:
            return conn.xlen(destination)

    def has_frames(self, destination: str) -> bool:
        """检查队列是否非空"""
        return self.size(destination) > 0

    def destinations(self) -> Set[str]:
        """获取所有有效队列名称"""
        with self._connection() as conn:
            return {key.decode('utf-8') for key in conn.keys('*') 
                    if conn.type(key) == b'stream'}

    def backpressure_size(self, destination: str) -> Optional[int]:
        """获取队列积压消息大小 (bytes)"""
        with self._connection() as conn:
            stream_info = conn.xinfo_stream(destination)
            return stream_info.get('length', 0) * 1024  # 平均估算值

    def close(self):
        """清理资源"""
        self.pool.disconnect()

    @property
    def metrics(self):
        """获取队列性能指标"""
        return {
            'ops': self._ops_counter,
            'pool': {
                'connections': self.pool._created_connections,
                'in_use': self.pool._in_use_connections
            }
        }
