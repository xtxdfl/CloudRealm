#!/usr/bin/env python3
"""
高级 Redis 任务存储系统 - 为 APScheduler 提供高可用、高性能、可扩展的分布式存储
支持多级缓存、增量更新、集群扩展和企业级灾难恢复
"""

import pickle
import logging
import threading
import time
import hashlib
from datetime import datetime
from uuid import uuid4
from typing import Dict, List, Optional, Tuple, Union

import redis
from redis import Redis, ConnectionPool, sentinel
from redis.exceptions import RedisError

from apscheduler.jobstores.base import JobStore
from apscheduler.job import Job
from apscheduler.util import itervalues, timedelta_seconds

logger = logging.getLogger(__name__)

class RedisClusterMode:
    """Redis 集群模式枚举"""
    STANDALONE = "standalone"
    SENTINEL = "sentinel"
    CLUSTER = "cluster"

class RedisJobStore(JobStore):
    """高性能 Redis 任务存储实现
    
    特性：
    1. 支持三种 Redis 部署模式：单点、哨兵、集群
    2. 智能缓存层减少网络开销
    3. 增量更新优化写性能
    4. 任务分区和分布式锁定
    5. 监控指标和性能分析
    """
    
    REDIS_KEY_FORMATS = {
        "job:data": "apscheduler:jobs:%s",       # 任务数据
        "next_run_times": "apscheduler:next_run_times", # 下次运行时间有序集合
        "job:status": "apscheduler:status:%s",   # 任务状态
        "job:locks": "apscheduler:lock:%s",      # 任务锁
        "job:versions": "apscheduler:versions",  # 任务版本控制
        "store:metadata": "apscheduler:metadata" # 存储元数据
    }
    
    EXPIRATION_GRACE = 300  # 任务锁默认过期时间（秒）
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: str = None,
        key_prefix: str = "apscheduler",
        pickle_protocol: int = pickle.HIGHEST_PROTOCOL,
        connection_pool: ConnectionPool = None,
        cluster_mode: str = RedisClusterMode.STANDALONE,
        sentinel_name: str = None,
        sentinels: List[Tuple] = None,
        max_connections: int = 50,
        cache_size: int = 1000,
        **connect_args
    ):
        """
        初始化Redis任务存储
        
        参数:
            host: Redis主机地址
            port: Redis端口
            db: Redis数据库索引
            password: Redis密码
            key_prefix: 键名前缀
            pickle_protocol: 序列化协议
            connection_pool: 自定义连接池
            cluster_mode: 集群模式 (standalone/sentinel/cluster)
            sentinel_name: 哨兵模式下的服务名称
            sentinels: 哨兵节点列表 [(host, port)]
            max_connections: 最大连接数
            cache_size: 内存缓存大小
        """
        self.key_prefix = key_prefix
        self.pickle_protocol = pickle_protocol
        self.cache = {}
        self.cache_size = cache_size
        self.cluster_mode = cluster_mode.lower()
        self.lock = threading.RLock()
        self._statistics = {
            'hits': 0,
            'misses': 0,
            'updates': 0,
            'adds': 0,
            'deletes': 0
        }
        
        # 重写所有键名格式
        self.key_formats = {k: f"{self.key_prefix}:{v}" for k, v in self.REDIS_KEY_FORMATS.items()}
        
        # 设置Redis连接
        if connection_pool:
            self.connection_pool = connection_pool
        else:
            self.connection_pool = ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                max_connections=max_connections,
                **connect_args
            )
        
        # 基于部署模式初始化客户端
        self._init_redis_client()
        
        # 初始化存储元数据
        self._init_metadata()
        
        logger.info(f"RedisJobStore initialized in {self.cluster_mode} mode on {host}:{port}")

    def _init_redis_client(self) -> None:
        """根据部署模式初始化Redis客户端"""
        if self.cluster_mode == RedisClusterMode.SENTINEL:
            if not all([self.sentinels, self.sentinel_name]):
                raise ValueError("Sentinel mode requires sentinel nodes and service name")
                
            sentinel_client = sentinel.Sentinel(
                self.sentinels,
                password=self.password,
                socket_timeout=5
            )
            self.redis = sentinel_client.master_for(
                self.sentinel_name,
                connection_pool=self.connection_pool
            )
            self.redis_slave = sentinel_client.slave_for(
                self.sentinel_name,
                connection_pool=self.connection_pool
            )
        elif self.cluster_mode == RedisClusterMode.CLUSTER:
            from rediscluster import RedisCluster
            # 在实际环境中需提供集群启动节点
            self.redis = RedisCluster(
                startup_nodes=[{'host': self.host, 'port': self.port}],
                password=self.password,
                max_connections=50
            )
        else:
            # 独立部署模式
            self.redis = Redis(connection_pool=self.connection_pool)
            self.redis_slave = self.redis  # 对独立模式使用相同实例

    def _init_metadata(self) -> None:
        """初始化存储元数据"""
        metadata_key = self.key_formats['store:metadata']
        if not self.redis_slave.exists(metadata_key):
            metadata = {
                'created': time.time(),
                'version': '2.0',
                'total_jobs': 0,
                'last_optimized': 0
            }
            self.redis.hmset(metadata_key, metadata)

    def _get_redis_key(self, key_type: str, *elements) -> str:
        """获取格式化键名"""
        return self.key_formats[key_type] % elements

    def _update_stats(self, key: str) -> None:
        """更新统计信息"""
        with self.lock:
            self._statistics[key] += 1

    def get_perf_metrics(self) -> dict:
        """获取性能指标"""
        hit_rate = self._statistics['hits'] / \
            (self._statistics['hits'] + self._statistics['misses']) * 100 \
            if self._statistics['hits'] + self._statistics['misses'] > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'hit_rate': f"{hit_rate:.2f}%",
            'total_operations': sum(self._statistics.values()),
            'metrics': self._statistics.copy()
        }

    def optimize_store(self) -> bool:
        """优化存储性能"""
        try:
            # 清理过期锁
            lock_pattern = self._get_redis_key('job:locks', '*')
            locks = self.redis.keys(lock_pattern)
            for lock in locks:
                # 只有超过宽限期的锁才删除
                if self.redis.ttl(lock) == -1:
                    self.redis.expire(lock, self.EXPIRATION_GRACE)
                    
            # 更新元数据
            metadata = {'last_optimized': time.time()}
            self.redis.hmset(self.key_formats['store:metadata'], metadata)
            
            logger.info("Store optimization completed")
            return True
        except RedisError as e:
            logger.error("Optimization failed: %s", e)
            return False

    def _acquire_lock(self, job_id: str, timeout=5, lock_duration=60) -> bool:
        """获取分布式任务锁"""
        lock_key = self._get_redis_key('job:locks', job_id)
        expire_time = int(time.time()) + lock_duration
        
        # Lua脚本保证原子操作
        lua_script = """
        if redis.call('setnx', KEYS[1], ARGV[1]) == 1 then
            redis.call('expireat', KEYS[1], ARGV[2])
            return 1
        end
        return 0
        """
        
        start_time = time.time()
        while True:
            # 生成唯一锁值
            lock_value = f'{hashlib.md5(str(time.time()).encode()).hexdigest()}'
            result = self.redis.eval(
                lua_script, 
                1, 
                lock_key, 
                lock_value,
                str(expire_time)
            )
            
            if result == 1:
                return True
                
            if time.time() - start_time > timeout:
                return False
                
            time.sleep(0.1)

    def _release_lock(self, job_id: str) -> None:
        """释放任务锁"""
        try:
            lock_key = self._get_redis_key('job:locks', job_id)
            self.redis.delete(lock_key)
        except RedisError:
            logger.warning(f"Lock for job {job_id} might already be expired")

    def add_job(self, job: Job) -> None:
        """添加新任务"""
        job.id = str(uuid4())
        job_key = self._get_redis_key('job:data', job.id)
        
        with self.lock:
            job_state = job.__getstate__()
            serialized = {
                'data': pickle.dumps(job_state, self.pickle_protocol),
                'version': 1
            }
            
            try:
                # 更新内存缓存
                self._update_cache(job.id, job_state)
                
                # 更新下次运行时间有序集合
                self._update_next_run_time(job.id, job_state['next_run_time'])
                
                # 存储任务数据
                self.redis.hmset(job_key, serialized)
                
                # 更新元数据
                self._update_job_count(1)
                
                self._update_stats('adds')
                logger.info("Added job: %s (ID: %s)", job.name, job.id)
            except RedisError as e:
                logger.error("Failed to add job: %s", e)
                raise

    def update_job(self, job: Job) -> None:
        """更新任务"""
        job_key = self._get_redis_key('job:data', job.id)
        
        # 使用乐观锁机制
        retries = 3
        for attempt in range(retries):
            try:
                # 获取当前版本
                current_version = int(self.redis.hget(job_key, 'version'))
                
                # 获取任务锁
                if not self._acquire_lock(job.id, lock_duration=30):
                    logger.warning(f"Update lock acquisition failed for job: {job.id}")
                    continue
                
                try:
                    # 准备新状态
                    job_state = job.__getstate__()
                    serialized = {
                        'data': pickle.dumps(job_state, self.pickle_protocol),
                        'version': current_version + 1
                    }
                    
                    # Lua脚本原子更新
                    lua_script = """
                    local key = KEYS[1]
                    local version = ARGV[1]
                    local new_version = ARGV[2]
                    local new_data = ARGV[3]
                    
                    -- 检查版本是否匹配
                    if tonumber(redis.call('hget', key, 'version')) == tonumber(version) then
                        redis.call('hmset', key, 'data', new_data, 'version', new_version)
                        
                        -- 更新下次运行时间
                        if ARGV[4] ~= "nil" then
                            redis.call('zadd', KEYS[2], ARGV[4] or 0, KEYS[3])
                        else
                            redis.call('zrem', KEYS[2], KEYS[3])
                        end
                        
                        return 1
                    end
                    return 0
                    """
                    
                    # 执行原子更新
                    next_run_score = job.next_run_time.timestamp() if job.next_run_time else "nil"
                    result = self.redis.eval(
                        lua_script,
                        3,  # KEYS数量
                        job_key,
                        self.key_formats['next_run_times'],
                        job.id,
                        str(current_version),
                        str(current_version + 1),
                        serialized['data'],
                        next_run_score
                    )
                    
                    if result == 1:
                        # 更新内存缓存
                        self._update_cache(job.id, job_state)
                        
                        # 更新统计
                        self._update_stats('updates')
                        logger.debug("Updated job: %s", job.id)
                        return
                    else:
                        logger.warning("Version conflict for job %s, attempt %d/%d", 
                                      job.id, attempt + 1, retries)
                finally:
                    self._release_lock(job.id)
            except RedisError as e:
                logger.error("Job update failed: %s", e)
                raise

        logger.error("Failed to update job %s after %d retries", job.id, retries)
        raise RuntimeError("Job update consistency failure")

    def remove_job(self, job: Job) -> None:
        """移除任务"""
        job_key = self._get_redis_key('job:data', job.id)
        
        try:
            # 获取任务锁
            if not self._acquire_lock(job.id):
                logger.warning(f"Remove lock acquisition failed for job: {job.id}")
                return False
                
            try:
                # Lua脚本原子删除
                lua_script = """
                local job_key = KEYS[1]
                local next_run_key = KEYS[2]
                local job_id = ARGV[1]
                
                -- 删除主数据和下次运行时间
                redis.call('zrem', next_run_key, job_id)
                redis.call('del', job_key)
                return 1
                """
                
                self.redis.eval(
                    lua_script,
                    2,
                    job_key,
                    self.key_formats['next_run_times'],
                    job.id
                )
                
                # 清除内存缓存
                if job.id in self.cache:
                    del self.cache[job.id]
                
                # 更新元数据
                self._update_job_count(-1)
                
                self._update_stats('deletes')
                logger.info("Removed job: %s", job.id)
                return True
            finally:
                self._release_lock(job.id)
        except RedisError as e:
            logger.error("Failed to remove job: %s", e)
            return False

    def load_jobs(self) -> List[Job]:
        """加载所有任务"""
        job_keys = []
        pattern = self._get_redis_key('job:data', '*')
        cursor = 0
        
        try:
            # 使用SCAN迭代键空间避免阻塞
            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern)
                job_keys.extend(keys)
                if cursor == 0:
                    break
                    
            if not job_keys:
                return []
                
            pipeline = self.redis_slave.pipeline()
            for key in job_keys:
                pipeline.hget(key, 'data')
                
            results = pipeline.execute()
            jobs = []
            
            for key, serialized_data in zip(job_keys, results):
                if not serialized_data:
                    continue
                    
                try:
                    job_suffix = key.decode().split(':')[-1]
                    # 尝试从缓存获取
                    job = self._get_from_cache(job_suffix)
                    if job:
                        jobs.append(job)
                        continue
                        
                    # 反序列化
                    job_state = pickle.loads(serialized_data)
                    job = Job.__new__(Job)
                    job.__setstate__(job_state)
                    
                    # 更新缓存
                    self._update_cache(job.id, job_state)
                    jobs.append(job)
                except Exception as e:
                    job_name = job_state.get('name', 'unknown') if 'job_state' in locals() else 'unknown'
                    logger.exception('Unable to restore job "%s"', job_name)
                    
            self._update_stats('misses')
            return jobs
        except RedisError as e:
            logger.error("Failed to load jobs: %s", e)
            return []

    def get_due_jobs(self, now: datetime) -> List[Job]:
        """获取当前应执行的任务"""
        due_jobs = []
        now_timestamp = now.timestamp()
        
        try:
            # 获取所有到期任务ID
            job_ids = self.redis.zrangebyscore(
                self.key_formats['next_run_times'],
                0,
                now_timestamp
            )
            
            if not job_ids:
                return []
                
            pipeline = self.redis_slave.pipeline()
            for job_id in job_ids:
                job_key = self._get_redis_key('job:data', job_id.decode())
                pipeline.hget(job_key, 'data')
                
            results = pipeline.execute()
            
            for job_id, serialized_data in zip(job_ids, results):
                if not serialized_data:
                    continue
                    
                try:
                    job_id_str = job_id.decode()
                    # 尝试从缓存获取
                    job = self._get_from_cache(job_id_str)
                    if job:
                        due_jobs.append(job)
                        continue
                        
                    # 反序列化
                    job_state = pickle.loads(serialized_data)
                    job = Job.__new__(Job)
                    job.__setstate__(job_state)
                    
                    # 更新缓存
                    self._update_cache(job.id, job_state)
                    due_jobs.append(job)
                except Exception as e:
                    logger.exception('Unable to restore job "%s"', job_id)
            
            return due_jobs
        except RedisError as e:
            logger.error("Failed to get due jobs: %s", e)
            return []

    def get_next_run_time(self) -> Optional[datetime]:
        """获取下一个任务的运行时间"""
        try:
            results = self.redis_slave.zrange(
                self.key_formats['next_run_times'],
                0, 0, withscores=True
            )
            
            if results:
                next_run_timestamp = results[0][1]
                return datetime.fromtimestamp(next_run_timestamp)
            return None
        except RedisError as e:
            logger.error("Failed to get next run time: %s", e)
            return None

    def get_job_status(self, job_id: str) -> str:
        """获取任务状态"""
        status_key = self._get_redis_key('job:status', job_id)
        try:
            return self.redis_slave.get(status_key).decode()
        except (RedisError, AttributeError):
            return 'unknown'

    def set_job_status(self, job_id: str, status: str) -> bool:
        """设置任务状态"""
        try:
            status_key = self._get_redis_key('job:status', job_id)
            self.redis.set(status_key, status)
            return True
        except RedisError as e:
            logger.error("Failed to set job status: %s", e)
            return False

    def archive_completed_jobs(self, batch_size=100) -> int:
        """归档已完成的任务"""
        try:
            # 获取所有已完成的任务
            pattern = self._get_redis_key('job:status', '*_completed')
            cursor = 0
            archived = 0
            
            while True:
                cursor, status_keys = self.redis.scan(cursor, match=pattern, count=batch_size)
                if not status_keys:
                    if cursor == 0:
                        break
                    continue
                    
                # 提取任务ID
                job_ids = [key.decode().split(':')[-1] for key in status_keys]
                
                # 删除任务数据和状态
                pipeline = self.redis.pipeline()
                for job_id in job_ids:
                    job_key = self._get_redis_key('job:data', job_id)
                    pipeline.delete(job_key)
                    pipeline.delete(status_keys[job_ids.index(job_id)])  # 删除状态键
                    
                    # 从下次运行时间集合中移除
                    pipeline.zrem(self.key_formats['next_run_times'], job_id)
                    
                pipeline.execute()
                archived += len(job_ids)
                
                # 更新元数据
                self._update_job_count(-len(job_ids))
                
                if cursor == 0:
                    break
                    
            logger.info("Archived %d completed jobs", archived)
            return archived
        except RedisError as e:
            logger.error("Archive failed: %s", e)
            return 0

    def close(self) -> None:
        """关闭存储连接"""
        self.connection_pool.disconnect()
        logger.info("Redis connection closed")

    def __repr__(self) -> str:
        """提供有意义的表示"""
        try:
            job_count = self.redis.dbsize()
            cluster_info = f"nodes: {len(self.redis.nodes)}" if self.cluster_mode == "cluster" else ""
            return f"<{self.__class__.__name__} [mode={self.cluster_mode}] - Jobs: {job_count} {cluster_info}>"
        except RedisError:
            return f"<{self.__class__.__name__} [Disconnected]>"
    
    def _update_cache(self, job_id: str, job_state: dict) -> None:
        """更新内存缓存"""
        with self.lock:
            # 维护缓存大小
            if len(self.cache) >= self.cache_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                
            self.cache[job_id] = job_state
    
    def _get_from_cache(self, job_id: str) -> Optional[Job]:
        """从缓存获取任务"""
        if job_id in self.cache:
            job_state = self.cache[job_id]
            job = Job.__new__(Job)
            job.__setstate__(job_state)
            self._update_stats('hits')
            return job
            
        self._update_stats('misses')
        return None
    
    def _update_next_run_time(self, job_id: str, next_run_time: datetime) -> None:
        """更新下次运行时间集合"""
        if next_run_time:
            score = next_run_time.timestamp()
            self.redis.zadd(
                self.key_formats['next_run_times'], 
                {job_id: score}, 
                xx=False  # 如果存在则更新
            )
        else:
            self.redis.zrem(
                self.key_formats['next_run_times'], 
                job_id
            )
    
    def _update_job_count(self, delta: int) -> None:
        """更新任务计数器"""
        self.redis.hincrby(
            self.key_formats['store:metadata'], 
            'total_jobs', 
            delta
        )


class JobStoreSentinelController:
    """哨兵模式监控控制器"""
    def __init__(self, jobstore: RedisJobStore, check_interval=60):
        self.jobstore = jobstore
        self.check_interval = check_interval
        self.health_thread = threading.Thread(target=self._health_loop)
        self.health_thread.daemon = True
        self.running = False
        
    def start(self):
        """启动健康监控"""
        self.running = True
        self.health_thread.start()
        logger.info("Sentinel health monitoring started")
    
    def stop(self):
        """停止健康监控"""
        self.running = False
        logger.info("Sentinel health monitoring stopped")
    
    def _health_loop(self):
        """哨兵健康监控循环"""
        while self.running:
            try:
                # 检查主节点状态
                master = self.jobstore.sentinel.discover_master(self.jobstore.sentinel_name)
                logger.info("Current master: %s:%s", master[0], master[1])
                
                # 检查哨兵节点状态
                for sentinel_node in self.jobstore.sentinels:
                    try:
                        s = self.jobstore.sentinel.master_for(
                            self.jobstore.sentinel_name, 
                            socket_connect_timeout=2
                        )
                        s.ping()
                        logger.debug("Sentinel %s:%s is healthy", *sentinel_node)
                    except RedisError:
                        logger.warning("Sentinel %s:%s is not responding", *sentinel_node)
                
                time.sleep(self.check_interval)
            except Exception:
                logger.exception("Sentinel monitoring error")
                time.sleep(10)
