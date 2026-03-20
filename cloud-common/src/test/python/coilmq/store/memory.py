#!/usr/bin/env python3
"""
高性能内存队列存储实现

使用双层锁机制与可扩展容器设计，优化高并发场景下的吞吐量。
支持消息优先级与队列监控接口。
"""
import threading
from collections import deque
from typing import Dict, Deque, Set, Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from coilmq.store import QueueStore
from coilmq.store.utils import PriorityQueue
from coilmq.metrics import QueueMetrics

@dataclass
class QueueState:
    """队列内部状态容器"""
    messages: Deque = field(default_factory=deque)
    enqueues: int = 0
    dequeues: int = 0
    requeues: int = 0

class MemoryQueue(QueueStore):
    
    def __init__(self, max_queues: int = 1000, priority_sorting: bool = False):
        """
        :param max_queues: 最大队列数量 (防DDoS)
        :param priority_sorting: 是否启用优先级队列
        """
        super().__init__()
        # 队列容器 (queue_name -> QueueState)
        self._queues: Dict[str, QueueState] = {}
        
        # 同步机制
        self._global_lock = threading.RLock()   # 管理队列元数据
        self._queue_locks: Dict[str, threading.RLock] = {}  # 队列级锁
        
        # 配置选项
        self.priority_sorting = priority_sorting
        self.max_queues = max_queues
        
        # 监控指标
        self.metrics = QueueMetrics(
            queue_store=self,
            prefix="coilmq.store.memory"
        )

    @contextmanager
    def _acquire_queue_lock(self, destination: str):
        """获取队列级锁的上下文管理器"""
        with self._global_lock:
            # 按需创建队列级锁
            if destination not in self._queue_locks:
                self._queue_locks[destination] = threading.RLock()
                
            lock = self._queue_locks[destination]
        
        # 获取队列级锁
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def _get_or_create_queue(self, destination: str) -> QueueState:
        """获取或创建队列状态对象"""
        with self._global_lock:
            # 队列数量限制
            if len(self._queues) >= self.max_queues and destination not in self._queues:
                raise RuntimeError(f"Max queue limit reached ({self.max_queues})")
                
            if destination not in self._queues:
                if self.priority_sorting:
                    self._queues[destination] = QueueState(messages=PriorityQueue())
                else:
                    self._queues[destination] = QueueState()
            
            return self._queues[destination]

    def enqueue(self, destination: str, frame) -> None:
        """入队操作：优先级感知排队"""
        if not destination:
            raise ValueError("Invalid queue destination")
            
        with self._acquire_queue_lock(destination):
            state = self._get_or_create_queue(destination)
            
            # 优先级处理
            if self.priority_sorting:
                priority = frame.headers.get('priority', 4)
                state.messages.append((priority, frame))
                if isinstance(state.messages, PriorityQueue):
                    state.messages.sort_reversed()
            else:
                state.messages.append(frame)
                
            state.enqueues += 1

    def dequeue(self, destination: str):
        """出队操作：安全空队列处理"""
        if not destination:
            raise ValueError("Invalid queue destination")
            
        with self._acquire_queue_lock(destination):
            state = self._queues.get(destination)
            
            # 处理空队列
            if not state or not state.messages:
                return None
                
            frame = state.messages.pop() if self.priority_sorting else state.messages.popleft()
            state.dequeues += 1
            
            # 清理空队列
            if not state.messages and state.dequeues > 50 * state.enqueues:
                self._clean_queue(destination)
                
            return frame

    def _clean_queue(self, destination: str) -> None:
        """清理空队列（全局锁保护）"""
        with self._global_lock:
            if destination in self._queues and not self._queues[destination].messages:
                del self._queues[destination]
                del self._queue_locks[destination]

    def size(self, destination: str) -> int:
        """获取队列消息计数（零锁优化）"""
        state = self._queues.get(destination)
        return len(state.messages) if state else 0

    def has_frames(self, destination: str) -> bool:
        """检查队列是否存在消息（零锁优化）"""
        return bool(self._queues.get(destination)) and bool(self._queues[destination].messages)

    def destinations(self) -> Set[str]:
        """获取所有活动队列（快照视图）"""
        with self._global_lock:
            return set(self._queues.keys())
            
    def requeue(self, destination: str, frame) -> None:
        """消息重新入队（优先处理）"""
        with self._acquire_queue_lock(destination):
            state = self._queues.get(destination)
            if not state:
                return
                
            if self.priority_sorting:
                priority = frame.headers.get('priority', 0)  # 重置为高优先级
                state.messages.appendleft((priority, frame))
                if isinstance(state.messages, PriorityQueue):
                    state.messages.sort_reversed()
            else:
                state.messages.appendleft(frame)  # 重排队列头部
            state.requeues += 1

    def stats(self, destination: Optional[str] = None):
        """获取队列详细统计指标"""
        with self._global_lock:
            if destination:
                state = self._queues.get(destination)
                if state:
                    return {
                        'enqueues': state.enqueues,
                        'dequeues': state.dequeues,
                        'requeues': state.requeues,
                        'size': len(state.messages)
                    }
                return {}
            
            return {
                dest: {
                    'size': len(state.messages),
                    'throughput': state.enqueues - state.dequeues
                }
                for dest, state in self._queues.items()
            }
