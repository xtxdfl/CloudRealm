#!/usr/bin/env python3
"""
高级 SQLAlchemy 任务存储系统 - 为 APScheduler 提供高效可靠的持久化存储
提供完整的事务支持、连接池管理和分布式工作负载优化
"""

import pickle
import logging
import threading
from contextlib import contextmanager

from apscheduler.jobstores.base import JobStore
from apscheduler.job import Job
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, BigInteger, 
    DateTime, Boolean, Sequence, Unicode, PickleType, Text, func
)
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import select, update, delete

logger = logging.getLogger(__name__)

# ORM 映射基类
Base = declarative_base()

class ScheduledJob(Base):
    """计划任务 ORM 模型"""
    __tablename__ = 'apscheduler_jobs'
    
    id = Column(Integer, Sequence('apscheduler_job_id_seq'), primary_key=True)
    trigger = Column(PickleType, nullable=False)
    func_ref = Column(String(1024), nullable=False)
    args = Column(PickleType, nullable=False)
    kwargs = Column(PickleType, nullable=False)
    name = Column(Unicode(1024))
    misfire_grace_time = Column(Integer, nullable=False)
    coalesce = Column(Boolean, nullable=False)
    max_runs = Column(Integer)
    max_instances = Column(Integer)
    next_run_time = Column(DateTime, nullable=False, index=True)  # 添加索引
    runs = Column(BigInteger)
    status = Column(String(20), default='active', index=True)  # 增加状态字段
    metadata = Column(Text)  # 任务元数据
    
    def __repr__(self):
        return f"<ScheduledJob(id={self.id}, name='{self.name}', next_run_time={self.next_run_time})>"

class SQLAlchemyJobStore(JobStore):
    """高性能 SQLAlchemy 任务存储实现
    
    特性：
    1. 使用 SQLAlchemy ORM 模型简化数据库操作
    2. 实现线程安全的会话管理
    3. 支持连接池和自动重连
    4. 增加任务状态管理和元数据存储
    5. 优化索引提升查询性能
    6. 完整的错误处理和事务管理
    """
    
    def __init__(
        self,
        url=None,
        engine=None,
        tablename="apscheduler_jobs",
        metadata=None,
        pickle_protocol=pickle.HIGHEST_PROTOCOL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=3600
    ):
        self.pickle_protocol = pickle_protocol
        
        # 引擎初始化
        if engine:
            self.engine = engine
        elif url:
            # 配置连接池和连接参数
            self.engine = create_engine(
                url,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                isolation_level="READ COMMITTED"
            )
        else:
            raise ValueError('必须提供 "engine" 或 "url" 参数')
        
        # 初始化表结构
        try:
            Base.metadata.create_all(self.engine, checkfirst=True)
            logger.info("计划任务表创建/验证完成")
        except Exception as e:
            logger.error("创建计划任务表失败: %s", e)
            raise
        
        # 创建线程安全的会话工厂
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=True,
            autocommit=False,
            expire_on_commit=False
        )
        self.Session = scoped_session(self.session_factory)
        
        # 初始化锁机制
        self.lock = threading.RLock()
        logger.info("SQLAlchemyJobStore 初始化完成 (URL: %s)", self.engine.url)

    @contextmanager
    def _session_scope(self):
        """提供会话作用域管理的上下文管理器"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except IntegrityError as e:
            session.rollback()
            logger.error("数据库唯一性冲突: %s", e)
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("数据库操作错误: %s", e)
            raise
        except Exception as e:
            session.rollback()
            logger.exception("未知错误: %s", e)
            raise
        finally:
            self.Session.remove()

    def add_job(self, job):
        """添加新任务到数据库"""
        with self.lock, self._session_scope() as session:
            job_dict = job.__getstate__()
            
            # 转换为 ORM 对象
            db_job = ScheduledJob(
                trigger=job_dict['trigger'],
                func_ref=job_dict['func_ref'],
                args=job_dict['args'],
                kwargs=job_dict['kwargs'],
                name=job_dict['name'],
                misfire_grace_time=job_dict['misfire_grace_time'],
                coalesce=job_dict['coalesce'],
                max_runs=job_dict.get('max_runs'),
                max_instances=job_dict.get('max_instances'),
                next_run_time=job_dict['next_run_time'],
                runs=job_dict['runs'],
                metadata=job_dict.get('metadata')
            )
            
            session.add(db_job)
            session.flush()  # 确保获取生成的ID
            
            # 更新任务ID
            job.id = db_job.id
            logger.info("添加新任务: ID=%d, 名称='%s'", job.id, job.name)

    def remove_job(self, job):
        """从数据库移除任务"""
        with self.lock, self._session_scope() as session:
            result = session.query(ScheduledJob).filter_by(id=job.id).delete()
            if result:
                logger.info("删除任务: ID=%d", job.id)
                return True
            logger.warning("任务删除失败: ID=%d 不存在", job.id)
            return False

    def update_job(self, job):
        """更新数据库中的任务信息"""
        job_dict = job.__getstate__()
        
        with self.lock, self._session_scope() as session:
            db_job = session.query(ScheduledJob).get(job.id)
            if not db_job:
                logger.error("更新任务失败: ID=%d 不存在", job.id)
                return
            
            # 更新所有相关字段
            db_job.trigger = job_dict['trigger']
            db_job.func_ref = job_dict['func_ref']
            db_job.args = job_dict['args']
            db_job.kwargs = job_dict['kwargs']
            db_job.name = job_dict['name']
            db_job.misfire_grace_time = job_dict['misfire_grace_time']
            db_job.coalesce = job_dict['coalesce']
            db_job.max_runs = job_dict.get('max_runs')
            db_job.max_instances = job_dict.get('max_instances')
            db_job.next_run_time = job_dict['next_run_time']
            db_job.runs = job_dict['runs']
            db_job.metadata = job_dict.get('metadata')
            
            logger.debug("更新任务: ID=%d", job.id)
    
    def load_jobs(self):
        """加载所有任务"""
        jobs = []
        
        with self.lock, self._session_scope() as session:
            db_jobs = session.query(ScheduledJob).filter_by(status='active').all()
            
            for db_job in db_jobs:
                try:
                    job_dict = {
                        'id': db_job.id,
                        'trigger': db_trigger,
                        'func_ref': db_job.func_ref,
                        'args': db_job.args,
                        'kwargs': db_job.kwargs,
                        'name': db_job.name,
                        'misfire_grace_time': db_job.misfire_grace_time,
                        'coalesce': db_job.coalesce,
                        'max_runs': db_job.max_runs,
                        'max_instances': db_job.max_instances,
                        'next_run_time': db_job.next_run_time,
                        'runs': db_job.runs
                    }
                    
                    job = Job.__new__(Job)
                    job.__setstate__(job_dict)
                    jobs.append(job)
                except Exception as e:
                    job_name = getattr(db_job, 'name', '未知任务')
                    logger.exception("还原任务失败: ID=%d '%s' - %s", db_job.id, job_name, str(e))
        
        logger.info("已加载 %d 个任务", len(jobs))
        return jobs

    def get_due_jobs(self, now):
        """获取当前应执行的任务"""
        due_jobs = []
        
        with self.lock, self._session_scope() as session:
            # 使用数据库原生过滤提高效率
            db_jobs = session.query(ScheduledJob).filter(
                ScheduledJob.next_run_time <= now,
                ScheduledJob.status == 'active'
            ).order_by(ScheduledJob.next_run_time).all()
            
            for db_job in db_jobs:
                try:
                    job_dict = {c.name: getattr(db_job, c.name) for c in ScheduledJob.__table__.columns}
                    
                    job = Job.__new__(Job)
                    job.__setstate__(job_dict)
                    due_jobs.append(job)
                except Exception as e:
                    job_id = getattr(db_job, 'id', '未知ID')
                    logger.error("无法处理任务 %s: %s", job_id, str(e))
        
        return due_jobs

    def get_next_run_time(self):
        """获取下一个任务的运行时间"""
        with self.lock, self._session_scope() as session:
            next_time = session.query(func.min(ScheduledJob.next_run_time)).filter(
                ScheduledJob.status == 'active'
            ).scalar()
            return next_time
    
    def pause_job(self, job):
        """暂停任务"""
        with self.lock, self._session_scope() as session:
            db_job = session.query(ScheduledJob).get(job.id)
            if db_job:
                db_job.status = 'paused'
                logger.info("任务暂停: ID=%d", job.id)
                return True
            return False
    
    def resume_job(self, job):
        """恢复任务"""
        with self.lock, self._session_scope() as session:
            db_job = session.query(ScheduledJob).get(job.id)
            if db_job and db_job.status == 'paused':
                db_job.status = 'active'
                logger.info("任务恢复: ID=%d", job.id)
                return True
            return False
    
    def get_job_metadata(self, job_id):
        """获取任务元数据"""
        with self.lock, self._session_scope() as session:
            db_job = session.query(ScheduledJob).get(job_id)
            return db_job.metadata if db_job else None
    
    def set_job_metadata(self, job_id, metadata):
        """设置任务元数据"""
        with self.lock, self._session_scope() as session:
            db_job = session.query(ScheduledJob).get(job_id)
            if db_job:
                db_job.metadata = metadata
                return True
            return False
    
    def archive_completed_jobs(self):
        """归档已完成的任务"""
        with self.lock, self._session_scope() as session:
            archived = session.query(ScheduledJob).filter(
                ScheduledJob.max_runs != None,
                ScheduledJob.runs >= ScheduledJob.max_runs
            ).update({"status": "archived"})
            
            logger.info("已归档 %d 个已完成的任务", archived)
            return archived
    
    def close(self):
        """清理资源"""
        self.engine.dispose()
        logger.info("数据库连接已关闭")
    
    def __repr__(self):
        return f"<{self.__class__.__name__} (url={self.engine.url}, pool_size={self.engine.pool.size()})>"


class DistributedLockManager:
    """分布式锁管理器 - 用于多实例调度器场景"""
    def __init__(self, jobstore: JobStore):
        self.jobstore = jobstore
    
    def acquire_lock(self, lock_name, timeout=30):
        """创建分布式锁"""
        # 在实际环境中这里应使用数据库锁（如SELECT FOR UPDATE）或Redis锁
        return True
    
    def release_lock(self, lock_name):
        """释放分布式锁"""
        pass


class JobStoreMetrics:
    """任务存储性能监控工具"""
    def __init__(self, jobstore: JobStore):
        self.jobstore = jobstore
        self.metrics = {
            'add_count': 0,
            'remove_count': 0,
            'update_count': 0,
            'load_count': 0,
            'load_duration': 0.0
        }
    
    def wrap_method(self, method):
        """包装方法以收集指标"""
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = method(*args, **kwargs)
            end_time = time.time()
            
            method_name = method.__name__
            self.metrics[f'{method_name}_count'] += 1
            self.metrics[f'{method_name}_duration'] += end_time - start_time
            
            return result
        return wrapper
    
    def instrument(self):
        """给JobStore方法添加仪表"""
        self.jobstore.add_job = self.wrap_method(self.jobstore.add_job)
        self.jobstore.remove_job = self.wrap_method(self.jobstore.remove_job)
        self.jobstore.update_job = self.wrap_method(self.jobstore.update_job)
        self.jobstore.load_jobs = self.wrap_method(self.jobstore.load_jobs)
    
    def get_metrics(self):
        """获取当前性能指标"""
        return self.metrics.copy()
