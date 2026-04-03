#!/usr/bin/env python3
"""
高级任务存储抽象基类 - 为分布式任务调度系统提供标准接口
支持企业级扩展功能包括：事务处理、多版本并发控制、监控指标和负载均衡
"""

import abc
import datetime
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

class JobStore(metaclass=abc.ABCMeta):
    """任务存储系统抽象基类
    
    这是所有任务存储实现的通用接口，提供任务持久化和检索功能。
    
    特性:
    1. 支持事务性操作
    2. 提供并发控制机制
    3. 内置监控指标接口
    4. 集成健康检查协议
    5. 支持分布式锁
    """
    
    @abc.abstractmethod
    def add_job(self, job: 'Job') -> str:
        """添加任务到存储
        
        参数:
            job: 要添加的任务对象
            
        返回:
            生成的任务ID
            
        异常:
            JobStoreError: 添加失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def update_job(self, job: 'Job') -> bool:
        """更新任务状态
        
        参数:
            job: 要更新的任务对象
            
        返回:
            bool: 更新是否成功
            
        异常:
            JobStoreError: 更新失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def remove_job(self, job_id: str) -> bool:
        """从存储中移除任务
        
        参数:
            job_id: 要移除的任务ID
            
        返回:
            bool: 移除是否成功
            
        异常:
            JobStoreError: 移除失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def load_jobs(self) -> List['Job']:
        """从存储加载所有任务
        
        返回:
            任务对象列表
            
        异常:
            JobStoreError: 加载失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def get_due_jobs(self, now: datetime.datetime) -> List['Job']:
        """获取指定时间前应执行的任务
        
        参数:
            now: 截止时间
            
        返回:
            应执行的任务列表
            
        异常:
            JobStoreError: 查询失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def get_next_run_time(self) -> Optional[datetime.datetime]:
        """获取下一次任务执行时间
        
        返回:
            最早的下次运行时间，如果没有任务返回 None
            
        异常:
            JobStoreError: 查询失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def close(self) -> None:
        """关闭存储连接并释放资源
        
        异常:
            JobStoreError: 关闭过程中出错时抛出
        """
        pass
    
    @abc.abstractmethod
    def get_job(self, job_id: str) -> Optional['Job']:
        """通过ID获取任务
        
        参数:
            job_id: 任务ID
            
        返回:
            任务对象，如果不存在返回 None
            
        异常:
            JobStoreError: 查询失败时抛出
        """
        pass
    
    def pause_job(self, job_id: str) -> bool:
        """暂停任务(默认实现)
        
        参数:
            job_id: 任务ID
            
        返回:
            bool: 操作是否成功
            
        异常:
            JobStoreError: 操作失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("pause_job not implemented")
    
    def resume_job(self, job_id: str) -> bool:
        """恢复任务(默认实现)
        
        参数:
            job_id: 任务ID
            
        返回:
            bool: 操作是否成功
            
        异常:
            JobStoreError: 操作失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("resume_job not implemented")
    
    def get_job_count(self) -> int:
        """获取任务总数(默认实现)
        
        返回:
            任务总数
            
        异常:
            JobStoreError: 查询失败时抛出
        """
        return len(self.load_jobs())
    
    def get_active_job_count(self) -> int:
        """获取活动任务总数(默认实现)
        
        返回:
            活动任务数量
            
        异常:
            JobStoreError: 查询失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("get_active_job_count not implemented")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标(默认实现)
        
        返回:
            存储性能指标的字典
            
        异常:
            JobStoreError: 查询失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("get_performance_metrics not implemented")
    
    def start_transaction(self):
        """开始事务(可选操作)
        
        异常:
            JobStoreError: 事务启动失败时抛出
            NotImplementedError: 如果不支持事务
        """
        raise NotImplementedError("Transaction not supported")
    
    def commit_transaction(self):
        """提交事务(可选操作)
        
        异常:
            JobStoreError: 事务提交失败时抛出
            NotImplementedError: 如果不支持事务
        """
        raise NotImplementedError("Transaction not supported")
    
    def rollback_transaction(self):
        """回滚事务(可选操作)
        
        异常:
            JobStoreError: 事务回滚失败时抛出
            NotImplementedError: 如果不支持事务
        """
        raise NotImplementedError("Transaction not supported")
    
    @contextmanager
    def transaction_context(self):
        """事务上下文管理器(可选操作)
        
        用法:
            with store.transaction_context():
                store.add_job(job1)
                store.update_job(job2)
        """
        try:
            self.start_transaction()
            yield
            self.commit_transaction()
        except Exception:
            self.rollback_transaction()
            raise
        finally:
            pass
    
    def optimize_storage(self) -> bool:
        """优化存储(可选操作)
        
        返回:
            bool: 优化是否成功
            
        异常:
            JobStoreError: 优化失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("optimize_storage not implemented")
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查(可选操作)
        
        返回:
            存储健康状态字典
            
        异常:
            JobStoreError: 检查失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("health_check not implemented")
    
    def archive_completed_jobs(self) -> int:
        """归档已完成任务(可选操作)
        
        返回:
            归档的任务数量
            
        异常:
            JobStoreError: 归档失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("archive_completed_jobs not implemented")
    
    def acquire_lock(self, job_id: str, timeout: int = 10) -> bool:
        """获取任务锁(可选操作)
        
        参数:
            job_id: 任务ID
            timeout: 获取锁的超时时间(秒)
            
        返回:
            bool: 是否成功获取锁
            
        异常:
            JobStoreError: 操作失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("acquire_lock not implemented")
    
    def release_lock(self, job_id: str) -> None:
        """释放任务锁(可选操作)
        
        参数:
            job_id: 任务ID
            
        异常:
            JobStoreError: 操作失败时抛出
            NotImplementedError: 如果不支持此操作
        """
        raise NotImplementedError("release_lock not implemented")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
    
    def __repr__(self) -> str:
        """提供有意义的表示"""
        return f"<{self.__class__.__name__}>"


class AdvancedJobStore(JobStore):
    """增强版JobStore接口，添加额外企业级功能"""
    
    @abc.abstractmethod
    def bulk_add_jobs(self, jobs: List['Job']) -> Tuple[int, int]:
        """批量添加任务
        
        参数:
            jobs: 要添加的任务列表
            
        返回:
            成功添加数量和失败数量
            
        异常:
            JobStoreError: 添加失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def bulk_update_jobs(self, jobs: List['Job']) -> Tuple[int, int]:
        """批量更新任务
        
        参数:
            jobs: 要更新的任务列表
            
        返回:
            成功更新数量和失败数量
            
        异常:
            JobStoreError: 更新失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def bulk_remove_jobs(self, job_ids: List[str]) -> Tuple[int, int]:
        """批量移除任务
        
        参数:
            job_ids: 要移除的任务ID列表
            
        返回:
            成功移除数量和失败数量
            
        异常:
            JobStoreError: 移除失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def get_jobs_by_status(self, status: str) -> List['Job']:
        """按状态获取任务
        
        参数:
            status: 任务状态(如'scheduled', 'running', 'paused')
            
        返回:
            匹配的任务列表
            
        异常:
            JobStoreError: 查询失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def reset_store(self) -> bool:
        """重置存储(清空所有任务)
        
        返回:
            bool: 操作是否成功
            
        异常:
            JobStoreError: 操作失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def backup_store(self, backup_location: str) -> bool:
        """备份存储内容
        
        参数:
            backup_location: 备份位置(路径或URI)
            
        返回:
            bool: 操作是否成功
            
        异常:
            JobStoreError: 操作失败时抛出
        """
        pass
    
    @abc.abstractmethod
    def get_cluster_info(self) -> Dict[str, Any]:
        """获取集群信息(分布式存储)
        
        返回:
            集群状态字典
            
        异常:
            JobStoreError: 查询失败时抛出
            NotImplementedError: 不是集群存储
        """
        pass


class JobStoreError(Exception):
    """任务存储异常基类"""
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception


class JobConflictError(JobStoreError):
    """任务冲突异常(如乐观锁版本冲突)"""
    pass


class JobNotFoundError(JobStoreError):
    """任务不存在异常"""
    pass


class StoreConnectError(JobStoreError):
    """存储连接异常"""
    pass


class TransactionError(JobStoreError):
    """事务操作异常"""
    pass


class JobStoreFactory:
    """任务存储工厂，提供统一创建接口"""
    STORE_TYPES = {}
    
    @classmethod
    def register_store(cls, store_type: str, store_class):
        """注册任务存储类型"""
        cls.STORE_TYPES[store_type] = store_class
    
    @classmethod
    def create_store(cls, store_type: str, **kwargs) -> JobStore:
        """创建指定类型的任务存储"""
        store_class = cls.STORE_TYPES.get(store_type)
        if not store_class:
            raise ValueError(f"Unsupported store type: {store_type}")
        
        try:
            return store_class(**kwargs)
        except Exception as e:
            raise StoreConnectError(f"Failed to create {store_type} store") from e


# 示例任务存储实现接口
class ExampleJobStore(JobStore):
    """示例任务存储实现(简化版)"""
    
    def __init__(self):
        self.jobs = {}
        self.lock_counter = 0
    
    def add_job(self, job):
        job_id = f"job_{len(self.jobs) + 1}"
        self.jobs[job_id] = job
        return job_id
    
    def update_job(self, job):
        if job.id not in self.jobs:
            return False
        self.jobs[job.id] = job
        return True
    
    def remove_job(self, job_id):
        if job_id not in self.jobs:
            return False
        del self.jobs[job_id]
        return True
    
    def load_jobs(self):
        return list(self.jobs.values())
    
    def get_due_jobs(self, now):
        return [job for job in self.jobs.values() 
                if job.next_run_time and job.next_run_time <= now]
    
    def get_next_run_time(self):
        due_times = [job.next_run_time for job in self.jobs.values() 
                     if job.next_run_time]
        return min(due_times) if due_times else None
    
    def close(self):
        self.jobs.clear()
    
    def get_job(self, job_id):
        return self.jobs.get(job_id)
    
    def get_performance_metrics(self):
        return {
            "job_count": len(self.jobs),
            "memory_usage": "N/A"
        }


# 注册示例存储类型
JobStoreFactory.register_store("example", ExampleJobStore)
