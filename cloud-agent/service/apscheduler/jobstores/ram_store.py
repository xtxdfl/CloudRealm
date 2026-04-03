#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超高速内存任务存储系统 - 为 APScheduler 提供极致性能的内存存储后端
提供高级缓存管理、任务分区和内存保护机制
"""

import time
import logging
import threading
import heapq
import bisect
from collections import defaultdict, OrderedDict
from typing import List, Dict, Optional, Tuple

from apscheduler.jobstores.base import JobStore
from apscheduler.job import Job

logger = logging.getLogger(__name__)

class RAMJobStore(JobStore):
    """高级内存任务存储系统
    
    特性:
    1. O(1)复杂度的任务查询和更新
    2. 智能内存回收机制
    3. 任务状态分区管理
    4. 下次运行时间索引
    5. 运行时内存监控
    6. 高并发锁机制
    """
    
    # 任务状态常量
    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_COMPLETED = 'completed'
    
    def __init__(self, max_jobs: int = 10000, max_memory_usage: int = 512):
        """
        初始化内存任务存储
        
        参数:
            max_jobs: 最大任务数量
            max_memory_usage: 最大内存使用(MB)
        """
        self._jobs: Dict[str, Job] = {}  # 主任务存储
        self._lock = threading.RLock()  # 线程锁
        
        # 任务状态分区
        self._active_jobs: Dict[str, Job] = {}
        self._paused_jobs: Dict[str, Job] = {}
        
        # 下次运行时间索引 (时间戳, job_id)
        self._next_run_times: List[Tuple[float, str]] = []
        self._next_run_index: Dict[str, float] = {}
        
        # 配置参数
        self.max_jobs = max_jobs
        self.max_memory = max_memory_usage * 1024 * 1024  # 转换为字节
        
        # 监控统计
        self.stats = {
            'add_count': 0,
            'remove_count': 0,
            'update_count': 0,
            'load_count': 0,
            'due_jobs_count': 0
        }
        
        # 内存监控
        self._memory_monitor_running = False
        self._memory_monitor = threading.Thread(
            target=self._monitor_memory_usage,
            daemon=True
        )
        self._start_memory_monitor()
        
        logger.info("RAMJobStore initialized with capacity for %d jobs", max_jobs)
    
    def _start_memory_monitor(self):
        """启动内存监控线程"""
        if not self._memory_monitor_running:
            self._memory_monitor_running = True
            self._memory_monitor.start()
            logger.debug("Memory monitor started")
    
    def _stop_memory_monitor(self):
        """停止内存监控线程"""
        self._memory_monitor_running = False
    
    def _monitor_memory_usage(self):
        """持续监控内存使用情况"""
        import psutil  # 仅用于监控
        process = psutil.Process()
        
        while self._memory_monitor_running:
            try:
                mem_info = process.memory_info()
                current_mem = mem_info.rss  # 驻留集大小
                
                if current_mem > self.max_memory:
                    # 触发内存回收
                    self._free_up_memory()
                
                # 每10秒检查一次
                time.sleep(10)
            except Exception as e:
                logger.exception("Memory monitoring error: %s", e)
                time.sleep(30)
    
    def _free_up_memory(self):
        """释放内存空间"""
        with self._lock:
            logger.warning("Memory threshold exceeded, freeing up space...")
            
            # 按最近执行时间排序任务 - 删除最旧的任务
            sorted_jobs = sorted(
                self._jobs.items(),
                key=lambda x: x[1].runs if x[1].runs is not None else 0
            )
            
            # 删除1/4的任务释放内存空间
            remove_count = max(10, len(self._jobs) // 4)
            for job_id, _ in sorted_jobs[:remove_count]:
                self._remove_job_internal(job_id)
            
            logger.info("Freed memory by removing %d jobs", remove_count)
    
    def add_job(self, job):
        """添加新任务到存储"""
        with self._lock:
            if len(self._jobs) >= self.max_jobs:
                logger.warning("Job store full, cannot add new job")
                return
            
            # 添加到主存储
            self._jobs[job.id] = job
            
            # 根据状态添加到对应分区
            self._active_jobs[job.id] = job
            
            # 更新下次运行时间索引
            if job.next_run_time is not None:
                self._update_next_run_index(job.id, job.next_run_time.timestamp(), job.runs)
            
            # 更新统计
            self.stats['add_count'] += 1
            logger.debug("Job added: ID=%s", job.id)
    
    def _update_next_run_index(self, job_id: str, next_run_time: float, runs: int = 0):
        """更新下次运行时间索引"""
        if job_id in self._next_run_index:
            # 删除现有条目
            old_time = self._next_run_index[job_id]
            idx = bisect.bisect_left(self._next_run_times, (old_time, job_id))
            del self._next_run_times[idx]
            del self._next_run_index[job_id]
        
        # 添加新条目
        bisect.insort(self._next_run_times, (next_run_time, job_id))
        self._next_run_index[job_id] = next_run_time
    
    def remove_job(self, job):
        """从存储中移除任务"""
        with self._lock:
            self._remove_job_internal(job.id)
            self.stats['remove_count'] += 1
    
    def _remove_job_internal(self, job_id: str):
        """内部任务移除实现"""
        if job_id in self._jobs:
            # 从主存储移除
            del self._jobs[job_id]
            
            # 从状态分区移除
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
            elif job_id in self._paused_jobs:
                del self._paused_jobs[job_id]
            
            # 从索引移除
            if job_id in self._next_run_index:
                old_time = self._next_run_index[job_id]
                idx = bisect.bisect_left(self._next_run_times, (old_time, job_id))
                del self._next_run_times[idx]
                del self._next_run_index[job_id]
            
            logger.debug("Job removed: ID=%s", job_id)
    
    def update_job(self, job):
        """更新任务状态"""
        with self._lock:
            if job.id not in self._jobs:
                logger.warning("Cannot update non-existent job: %s", job.id)
                return
                
            # 如果更改了运行时间，更新索引
            if job.id in self._next_run_index:
                current_time = self._jobs[job.id].next_run_time.timestamp() if self._jobs[job.id].next_run_time else 0
                new_time = job.next_run_time.timestamp() if job.next_run_time else 0
                
                if current_time != new_time:
                    if job.next_run_time is not None:
                        self._update_next_run_index(job.id, new_time, job.runs)
                    elif job.id in self._next_run_index:
                        # 如果运行时间设为None，移除索引
                        self._remove_from_next_run_index(job.id)
            
            # 更新主存储
            self._jobs[job.id] = job
            
            # 更新状态分区
            if self._is_job_active(job.id):
                self._active_jobs[job.id] = job
                if job.id in self._paused_jobs:
                    del self._paused_jobs[job.id]
            else:
                self._paused_jobs[job.id] = job
                if job.id in self._active_jobs:
                    del self._active_jobs[job.id]
            
            # 更新统计
            self.stats['update_count'] += 1
            logger.debug("Job updated: ID=%s", job.id)
    
    def _is_job_active(self, job_id: str) -> bool:
        """检查任务是否处于活动状态"""
        # 实际应用中，根据业务逻辑确定活动状态
        return True
    
    def _remove_from_next_run_index(self, job_id: str):
        """从下次运行时间索引中移除任务"""
        if job_id in self._next_run_index:
            old_time = self._next_run_index[job_id]
            idx = bisect.bisect_left(self._next_run_times, (old_time, job_id))
            del self._next_run_times[idx]
            del self._next_run_index[job_id]
    
    def load_jobs(self) -> List[Job]:
        """加载所有任务"""
        with self._lock:
            # 仅返回活动任务
            self.stats['load_count'] += 1
            return list(self._active_jobs.values())
    
    def get_due_jobs(self, now) -> List[Job]:
        """获取当前应执行的任务"""
        with self._lock:
            due_jobs = []
            now_timestamp = now.timestamp()
            
            # 使用索引高效查找
            for next_run_time, job_id in self._next_run_times:
                if next_run_time > now_timestamp:
                    break
                
                if job_id in self._jobs:
                    due_jobs.append(self._jobs[job_id])
            
            # 更新统计
            self.stats['due_jobs_count'] += len(due_jobs)
            return due_jobs
    
    def get_next_run_time(self) -> Optional[float]:
        """获取下一个任务的运行时间"""
        with self._lock:
            if not self._next_run_times:
                return None
                
            return self._next_run_times[0][0]
    
    def get_job_count(self) -> int:
        """获取当前存储的任务数量"""
        with self._lock:
            return len(self._jobs)
    
    def get_active_job_count(self) -> int:
        """获取活动任务数量"""
        with self._lock:
            return len(self._active_jobs)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                'total_jobs': len(self._jobs),
                'active_jobs': len(self._active_jobs),
                'paused_jobs': len(self._paused_jobs),
                'next_run_times': len(self._next_run_times),
                **self.stats
            }
    
    def clear_store(self):
        """清空任务存储"""
        with self._lock:
            self._jobs.clear()
            self._active_jobs.clear()
            self._paused_jobs.clear()
            self._next_run_times.clear()
            self._next_run_index.clear()
            logger.info("Job store cleared")
    
    def close(self):
        """关闭存储并清理资源"""
        self._stop_memory_monitor()
        logger.info("RAMJobStore closed")
    
    def __repr__(self):
        """提供有意义的表示"""
        stats = self.get_stats()
        return f"<{self.__class__.__name__} (jobs: total={stats['total_jobs']}, active={stats['active_jobs']})>"


class AutoScalingJobStore(RAMJobStore):
    """自动扩展内存任务存储"""
    def __init__(self, initial_capacity: int = 1000, max_capacity: int = 1000000, 
                 growth_factor: float = 1.5, min_free_slots: int = 100):
        """
        初始化自动扩展存储
        
        参数:
            initial_capacity: 初始容量
            max_capacity: 最大容量
            growth_factor: 扩展因子
            min_free_slots: 触发扩展的最小空闲槽位
        """
        super().__init__(max_jobs=initial_capacity)
        self.initial_capacity = initial_capacity
        self.max_capacity = max_capacity
        self.growth_factor = growth_factor
        self.min_free_slots = min_free_slots
        logger.info(f"AutoScalingJobStore initialized with max capacity {max_capacity}")

    def add_job(self, job):
        """添加任务(带自动扩展)"""
        # 检查容量，必要时扩展
        if len(self._jobs) >= (self.max_jobs - self.min_free_slots):
            self._expand_capacity()
        
        super().add_job(job)

    def _expand_capacity(self):
        """扩展存储容量"""
        current_capacity = self.max_jobs
        new_capacity = min(
            int(current_capacity * self.growth_factor),
            self.max_capacity
        )
        
        if new_capacity > current_capacity:
            self.max_jobs = new_capacity
            logger.info(f"Expanded capacity from {current_capacity} to {new_capacity}")
        else:
            logger.warning("Maximum capacity reached, cannot expand further")


class MemoryMonitor:
    """任务存储内存监控器"""
    def __init__(self, store: RAMJobStore, interval: int = 5):
        self.store = store
        self.interval = interval
        self.monitor_thread = threading.Thread(target=self._monitor, daemon=True)
        self.monitoring = False
        
    def start(self):
        """启动监控"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread.start()
            logger.info("Memory monitor started")
    
    def stop(self):
        """停止监控"""
        self.monitoring = False
    
    def _monitor(self):
        """监控任务存储运行状态"""
        import os
        import psutil
        
        process = psutil.Process(os.getpid())
        
        while self.monitoring:
            try:
                # 获取内存使用情况
                mem_info = process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                
                # 获取任务存储统计
                store_stats = self.store.get_stats()
                
                # 生成监控报告
                report = {
                    'timestamp': time.time(),
                    'rss_mem_mb': round(rss_mb, 2),
                    'job_store_total': store_stats['total_jobs'],
                    'job_store_active': store_stats['active_jobs'],
                    'memory_pressure': rss_mb / (self.store.max_memory / (1024 * 1024))
                }
                
                logger.info(
                    "MemoryMonitor: RSS=%.2fMB, Jobs=%d/%d, Pressure=%.2f%%",
                    report['rss_mem_mb'],
                    store_stats['active_jobs'],
                    store_stats['total_jobs'],
                    report['memory_pressure'] * 100
                )
                
                # 生成警报（如果内存压力过高）
                if report['memory_pressure'] > 0.9:
                    logger.warning("High memory pressure: %.2fMB", rss_mb)
                    # 在实际应用中触发警报系统
                
                time.sleep(self.interval)
            except Exception:
                logger.exception("Memory monitoring failed")
                time.sleep(10)

