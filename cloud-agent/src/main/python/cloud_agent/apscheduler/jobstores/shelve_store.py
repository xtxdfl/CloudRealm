#!/usr/bin/env python3
"""
高级 ShelveJobStore - 为 APScheduler 提供高效可靠的文件存储后端
提供缓存管理、并发控制、故障恢复和企业级功能扩展
"""

import shelve
import pickle
import logging
import threading
import contextlib
import uuid
import os
import time
import fcntl  # 用于文件锁定
from collections import OrderedDict, defaultdict

from apscheduler.jobstores.base import JobStore
from apscheduler.job import Job
from apscheduler.util import itervalues

logger = logging.getLogger(__name__)

class ShelveJobStore(JobStore):
    """高级文件存储作业管理器
    
    特性：
    1. 优化缓存管理，减少磁盘I/O
    2. 支持多线程/进程文件锁
    3. 自动故障恢复机制
    4. 任务快照和灾难恢复
    5. 性能监控和健康检查
    """
    
    # 任务状态常量
    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_COMPLETED = 'completed'
    
    def __init__(self, path, pickle_protocol=pickle.HIGHEST_PROTOCOL, max_jobs_in_memory=500):
        """
        初始化 Shelve 作业存储
        
        Args:
            path: shelve 文件路径
            pickle_protocol: 序列化协议
            max_jobs_in_memory: 内存中缓存的最大任务数
        """
        self.path = path
        self.pickle_protocol = pickle_protocol
        self.max_jobs_in_memory = max_jobs_in_memory
        self.lock = threading.RLock()  # 线程锁
        self.cache = OrderedDict()  # LRU 缓存
        self.stats = defaultdict(int)  # 操作统计
        
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        # 初始化存储
        self._open_store()
        
        logger.info("ShelveJobStore 初始化完成 (path: %s)", path)
    
    @contextlib.contextmanager
    def _locked_store(self, block=True):
        """提供线程安全和文件锁定的上下文管理器"""
        lock_file = self.path + '.lock'
        
        # 线程级锁定
        with self.lock:
            try:
                # 文件级锁定
                with open(lock_file, 'w') as lock_fd:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX if block else fcntl.LOCK_NB)
                    yield self.store
            except BlockingIOError:
                raise RuntimeError("数据库被其他进程锁定")
            except Exception as e:
                logger.error("文件锁定错误: %s", e)
                raise
    
    def _open_store(self):
        """打开存储数据库，带错误恢复"""
        try:
            self.store = shelve.open(
                self.path, 
                flag='c', 
                protocol=self.pickle_protocol,
                writeback=False  # 禁用自动写回,更好的内存控制
            )
            logger.debug("成功打开 shelve 数据库: %s", self.path)
        except Exception as e:
            # 尝试恢复数据库
            logger.error("打开数据库失败，尝试恢复: %s", str(e))
            self._attempt_recovery()
            self.store = shelve.open(
                self.path, 
                flag='c', 
                protocol=self.pickle_protocol
            )
    
    def _attempt_recovery(self):
        """尝试数据库恢复机制"""
        # 创建备份
        backup_path = f"{self.path}.bak.{int(time.time())}"
        try:
            with shelve.open(self.path, 'r') as corrupt_db:
                with shelve.open(backup_path, 'n') as backup_db:
                    for key, value in corrupt_db.items():
                        backup_db[key] = value
            logger.warning("已创建损坏数据库备份: %s", backup_path)
        except Exception:
            logger.exception("数据库备份失败")
            # 创建空数据库以恢复服务
            self._create_empty_db()
    
    def _create_empty_db(self):
        """创建新的空数据库"""
        try:
            # 尝试关闭可能存在的旧连接
            if hasattr(self, 'store'):
                try:
                    self.store.close()
                except Exception:
                    pass
            
            # 移除损坏文件
            if os.path.exists(self.path):
                os.remove(self.path)
                
            # 使用shelve创建新文件
            with shelve.open(self.path, 'n') as new_db:
                new_db['metadata'] = {
                    'version': '2.0',
                    'created_at': time.time()
                }
            logger.info("已创建新的空数据库: %s", self.path)
        except Exception as e:
            logger.exception("创建新数据库失败: %s", e)
            raise RuntimeError("无法初始化数据库") from e
    
    def _update_cache(self, job_id, job_state, action='add'):
        """管理内存缓存"""
        # 淘汰旧条目
        if len(self.cache) >= self.max_jobs_in_memory and job_id not in self.cache:
            self.cache.popitem(last=False)
        
        # 更新缓存
        self.cache.pop(job_id, None)
        if action == 'add':
            self.cache[job_id] = job_state
        
        # 记录缓存状态
        hit_rate = self.stats['cache_hits'] / max(1, self.stats['cache_requests'])
        logger.debug(
            "缓存状态: 大小=%d, 命中率=%.2f%%", 
            len(self.cache), hit_rate * 100
        )
    
    def add_job(self, job):
        """添加新任务"""
        with self._locked_store() as store:
            try:
                # 生成唯一ID
                job.id = uuid.uuid4().hex
                
                # 准备任务状态
                job_state = job.__getstate__()
                job_state['status'] = self.STATUS_ACTIVE
                job_state['created_at'] = time.time()
                
                # 存储状态
                store[job.id] = job_state
                store.sync()  # 立即同步到磁盘
                
                # 更新缓存和统计
                self._update_cache(job.id, job_state)
                self.stats['add_job'] += 1
                
                logger.info("添加任务: ID=%s, 名称=%s", job.id, job.name)
                return job
            except Exception as e:
                logger.exception("添加任务失败")
                raise
    
    def update_job(self, job):
        """更新任务状态"""
        with self._locked_store() as store:
            try:
                # 获取当前状态
                if job.id in self.cache:
                    job_state = self.cache[job.id].copy()
                else:
                    job_state = store.get(job.id, {})
                
                # 更新状态
                new_state = job.__getstate__()
                job_state.update({
                    'next_run_time': new_state['next_run_time'],
                    'runs': new_state['runs'],
                    'trigger': new_state['trigger']
                })
                
                # 存储更新
                store[job.id] = job_state
                store.sync()
                
                # 更新缓存和统计
                self._update_cache(job.id, job_state, 'update')
                self.stats['update_job'] += 1
                
                logger.debug("更新任务: ID=%s", job.id)
                return job
            except KeyError:
                logger.error("更新失败: 任务 ID=%s 不存在", job.id)
                raise
            except Exception as e:
                logger.exception("更新任务失败")
                raise
    
    def remove_job(self, job):
        """移除任务"""
        with self._locked_store() as store:
            try:
                # 删除任务
                if job.id in store:
                    del store[job.id]
                    store.sync()
                    
                    # 更新缓存和统计
                    self._update_cache(job.id, None, 'remove')
                    self.stats['remove_job'] += 1
                    
                    logger.info("删除任务: ID=%s", job.id)
                    return True
                
                logger.warning("删除失败: 任务 ID=%s 不存在", job.id)
                return False
            except Exception as e:
                logger.exception("删除任务失败")
                raise
    
    def load_jobs(self):
        """加载所有任务"""
        with self._locked_store() as store:
            jobs = []
            for job_id, job_dict in store.items():
                # 跳过元数据条目
                if job_id == 'metadata':
                    continue
                
                try:
                    # 检查缓存
                    self.stats['cache_requests'] += 1
                    if job_id in self.cache:
                        job_dict = self.cache[job_id]
                        self.stats['cache_hits'] += 1
                    
                    # 创建任务对象
                    job = Job.__new__(Job)
                    job.__setstate__(job_dict)
                    
                    # 更新缓存
                    if job_id not in self.cache:
                        self._update_cache(job_id, job_dict)
                    
                    jobs.append(job)
                except Exception as e:
                    job_name = job_dict.get("name", "未知任务")
                    logger.exception('无法恢复任务 "%s": %s', job_name, str(e))
            
            self.stats['load_jobs'] += 1
            logger.info("已加载 %d 个任务", len(jobs))
            return jobs
    
    def pause_job(self, job):
        """暂停任务"""
        with self._locked_store() as store:
            try:
                if job.id in store:
                    job_state = store[job.id]
                    job_state['status'] = self.STATUS_PAUSED
                    store[job.id] = job_state
                    store.sync()
                    logger.info("暂停任务: ID=%s", job.id)
                    return True
                return False
            except Exception as e:
                logger.exception("暂停任务失败")
                raise
    
    def resume_job(self, job):
        """恢复任务"""
        with self._locked_store() as store:
            try:
                if job.id in store:
                    job_state = store[job.id]
                    job_state['status'] = self.STATUS_ACTIVE
                    store[job.id] = job_state
                    store.sync()
                    logger.info("恢复任务: ID=%s", job.id)
                    return True
                return False
            except Exception as e:
                logger.exception("恢复任务失败")
                raise
    
    def archive_old_jobs(self, max_age=86400 * 30):
        """归档旧任务 (默认保留30天)"""
        with self._locked_store() as store:
            try:
                archived = []
                current_time = time.time()
                
                for job_id, job_state in list(store.items()):
                    # 仅处理任务数据
                    if job_id == 'metadata':
                        continue
                    
                    # 检查任务状态和年龄
                    status = job_state.get('status', self.STATUS_ACTIVE)
                    created_at = job_state.get('created_at', current_time)
                    
                    if status == self.STATUS_COMPLETED or (current_time - created_at) > max_age:
                        archived.append(job_id)
                        del store[job_id]
                        self.cache.pop(job_id, None)
                
                if archived:
                    store.sync()
                    logger.info("已归档 %d 个旧任务: %s", len(archived), ', '.join(archived[:5]) + 
                                ('...' if len(archived) > 5 else ''))
                
                return len(archived)
            except Exception as e:
                logger.exception("归档任务失败")
                return 0
    
    def create_snapshot(self, snapshot_path=None):
        """创建数据库快照"""
        try:
            # 默认快照路径
            if not snapshot_path:
                snapshot_path = f"{self.path}.snapshot.{int(time.time())}"
            
            with self._locked_store() as source:
                with shelve.open(snapshot_path, 'n') as snapshot:
                    # 复制所有数据
                    for key, value in source.items():
                        snapshot[key] = value
                    snapshot.sync()
            
            logger.info("成功创建数据库快照: %s (%d 条记录)", 
                        snapshot_path, len(source) - 1)  # 排除元数据条目
            return snapshot_path
        except Exception as e:
            logger.exception("创建快照失败")
            return None
    
    def get_stats(self):
        """获取操作统计"""
        return dict(self.stats)
    
    def optimize(self):
        """优化数据库存储"""
        with self._locked_store() as store:
            try:
                # 压缩数据库
                if hasattr(store, 'sync') and callable(store.sync):
                    store.sync()
                
                # 在Shelf对象中强制重建(特定于shelve实现)
                if hasattr(store, 'close') and hasattr(store, '_index'):
                    old_count = len(store)
                    store.close()
                    self._open_store()
                    logger.info("数据库优化完成: 原有记录=%d, 现有记录=%d", old_count, len(store))
                    return True
                    
                logger.info("数据库优化执行(同步)")
                return True
            except Exception as e:
                logger.exception("数据库优化失败")
                return False
    
    def close(self):
        """关闭数据库连接"""
        try:
            with contextlib.suppress(Exception):
                if hasattr(self.store, 'sync'):
                    self.store.sync()
                
                if hasattr(self.store, 'close'):
                    self.store.close()
            
            # 清理缓存
            self.cache.clear()
            logger.info("ShelveJobStore 已关闭")
        except Exception as e:
            logger.exception("关闭存储失败: %s", e)
    
    def __repr__(self):
        """提供有意义的表示"""
        active_jobs = 0
        total_jobs = 0
        
        # 快速统计而不加载所有任务
        with self._locked_store(block=False) as store:
            if store:
                total_jobs = len(store) - 1  # 忽略元数据
                # 无法在不加载的情况下获取状态，此处省略状态计数
        
        return (f"<{self.__class__.__name__} (路径={self.path}) "
                f"| 任务: {total_jobs} 存储中, {len(self.cache)} 缓存中>")
    
    
class JobStorageMonitor:
    """任务存储监控器 - 提供实时状态报告"""
    def __init__(self, job_store: ShelveJobStore, check_interval=30):
        self.job_store = job_store
        self.check_interval = check_interval
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.running = False
        
    def start(self):
        """启动监控线程"""
        self.running = True
        self.thread.start()
        logger.info("任务存储监控器启动")
    
    def stop(self):
        """停止监控线程"""
        self.running = False
        logger.info("任务存储监控器停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                self.check_health()
                time.sleep(self.check_interval)
            except Exception:
                logger.exception("存储监控错误")
    
    def check_health(self):
        """执行健康检查"""
        try:
            # 基本检查
            file_size = os.path.getsize(self.job_store.path) / 1024 / 1024  # MB
            stats = self.job_store.get_stats()
            
            # 准备报告
            report = {
                'timestamp': time.time(),
                'file_size_mb': round(file_size, 2),
                'cache_size': len(self.job_store.cache),
                'operations': dict(stats),
                'cache_hit_rate': stats.get('cache_hits', 0) / max(1, stats.get('cache_requests', 1))
            }
            
            # 高级检查: 验证元数据
            with self.job_store._locked_store() as store:
                metadata = store.get('metadata', {})
                if 'version' not in metadata:
                    logger.warning("元数据丢失或损坏")
                    report['metadata_status'] = 'invalid'
                else:
                    report['metadata_status'] = 'ok'
            
            # 日志报告
            logger.info(
                "存储健康报告: 大小=%.2fMB, 缓存=%d, 命中率=%.1f%%, 操作次数=%s",
                report['file_size_mb'],
                report['cache_size'],
                report['cache_hit_rate'] * 100,
                {k:v for k,v in report['operations'].items() if v > 0}
            )
            
            return report
        except Exception:
            logger.exception("健康检查失败")
            return {'status': 'failed'}


class JobStoreArchiver:
    """任务存储归档系统 - 周期性地归档旧任务"""
    def __init__(self, job_store: ShelveJobStore, archive_interval=86400, retention_days=90):
        self.job_store = job_store
        self.archive_interval = archive_interval
        self.retention_days = retention_days
        self.thread = threading.Thread(target=self._archive_cycle)
        self.thread.daemon = True
        self.running = False
        
    def start(self):
        """启动归档线程"""
        self.running = True
        self.thread.start()
        logger.info("任务归档器启动")
    
    def stop(self):
        """停止归档线程"""
        self.running = False
        logger.info("任务归档器停止")
    
    def _archive_cycle(self):
        """归档周期处理"""
        try:
            # 初始归档
            self.job_store.archive_old_jobs(max_age=self.retention_days * 86400)
            
            # 主循环
            while self.running:
                time.sleep(self.archive_interval)
                archived = self.job_store.archive_old_jobs(max_age=self.retention_days * 86400)
                logger.info("归档周期完成: 移动了 %d 个任务", archived)
        except Exception:
            logger.exception("归档周期错误")
