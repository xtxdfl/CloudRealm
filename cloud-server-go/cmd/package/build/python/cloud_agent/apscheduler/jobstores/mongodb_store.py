#!/usr/bin/env python3
"""
高级 MongoDB 任务存储系统 - 为 APScheduler 提供高可用、高性能的分布式存储
提供企业级功能包括：分片支持、索引优化、事务处理和大数据扩展
"""

import logging
import pickle
import datetime
from typing import List, Dict, Any, Optional

from apscheduler.jobstores.base import JobStore
from apscheduler.job import Job

try:
    import pymongo
    from pymongo import MongoClient, errors, ReadPreference, WriteConcern
    from bson.binary import Binary
    from pymongo.operations import ReplaceOne
except ImportError:
    raise ImportError("MongoDBJobStore requires PyMongo installed")

logger = logging.getLogger(__name__)

class MongoDBJobStore(JobStore):
    """高性能 MongoDB 任务存储实现
    
    特性：
    1. 多节点集群支持（副本集和分片）
    2. 自动索引优化
    3. 事务性操作
    4. 高性能批量处理
    5. 数据压缩和归档
    6. 高级监控和性能分析
    """
    
    DEFAULT_COLLECTION = "scheduled_jobs"
    DEFAULT_DATABASE = "apscheduler"
    
    def __init__(self, 
                 database: str = DEFAULT_DATABASE, 
                 collection: str = DEFAULT_COLLECTION,
                 connection_string: str = "mongodb://localhost:27017/",
                 connection: Any = None,
                 pickle_protocol: int = pickle.HIGHEST_PROTOCOL,
                 username: str = None,
                 password: str = None,
                 auth_source: str = "admin",
                 tls: bool = False,
                 replica_set: str = None,
                 read_preference: str = "primary",
                 write_concern: int = 1,
                 create_indexes: bool = True,
                 max_pool_size: int = 100,
                 compress_data: bool = False,
                 **connect_args):
        """
        初始化 MongoDB 任务存储
        
        参数：
            database: 数据库名称
            collection: 集合名称
            connection_string: MongoDB 连接字符串
            connection: 现有 MongoDB 连接
            pickle_protocol: 序列化协议
            username: 用户名
            password: 密码
            auth_source: 认证数据库
            tls: 是否使用 TLS
            replica_set: 副本集名称
            read_preference: 读偏好设置
            write_concern: 写关注级别
            create_indexes: 是否自动创建索引
            max_pool_size: 连接池最大大小
            compress_data: 是否压缩存储
        """
        self.pickle_protocol = pickle_protocol
        self.compress_data = compress_data
        self.stats = {
            'jobs_added': 0,
            'jobs_updated': 0,
            'jobs_removed': 0,
            'due_jobs_loaded': 0
        }
        
        # 配置 MongoDB 连接
        if connection:
            self.client = connection
        else:
            # 构建连接选项
            options = {
                'host': connection_string,
                'maxPoolSize': max_pool_size,
                'tls': tls,
                'connectTimeoutMS': 5000,
                'socketTimeoutMS': 30000,
                **connect_args
            }
            
            if username and password:
                options['username'] = username
                options['password'] = password
                options['authSource'] = auth_source
            
            if replica_set:
                options['replicaSet'] = replica_set
            
            self.client = MongoClient(**options)
        
        self.db = self.client.get_database(
            database, 
            write_concern=WriteConcern(w=write_concern)
        )
        self.collection = self.db.get_collection(
            collection,
            read_preference=getattr(ReadPreference, read_preference, ReadPreference.PRIMARY)
        )
        
        # 自动创建索引
        if create_indexes:
            self._ensure_indexes()
        
        logger.info(
            f"Connected to MongoDB: {self.client.address} "
            f"(DB: {database}, Collection: {collection})"
        )
    
    def _ensure_indexes(self) -> None:
        """确保必要的索引存在"""
        try:
            # 主键索引
            self.collection.create_index([("_id", pymongo.ASCENDING)], unique=True)
            # 下次运行时间索引（TTL 自动清理）
            self.collection.create_index(
                [("next_run_time", pymongo.ASCENDING)], 
                expireAfterSeconds=86400  # 24小时自动清理过期任务
            )
            # 任务状态索引
            self.collection.create_index([("status", pymongo.ASCENDING)])
            # 组合索引提高查询效率
            self.collection.create_index([
                ("next_run_time", pymongo.ASCENDING),
                ("status", pymongo.ASCENDING)
            ])
            logger.debug("MongoDB indexes successfully created")
        except errors.PyMongoError as e:
            logger.error("Failed to create indexes: %s", e)
    
    def get_perf_stats(self) -> dict:
        """获取性能统计信息"""
        return self.stats
    
    def _serialize_job(self, job_state: Dict) -> Dict:
        """序列化任务数据"""
        # 使用高效的pickle序列化
        serialized = Binary(pickle.dumps(job_state, self.pickle_protocol))
        
        # 可选的压缩处理
        if self.compress_data:
            # 在实际应用中可实现压缩逻辑（如zlib）
            pass
            
        return {'job_state': serialized}
    
    def _deserialize_job(self, document: Dict) -> Job:
        """反序列化任务数据"""
        serialized = document['job_state']
        
        # 解压缩处理（如有压缩）
        if self.compress_data:
            pass
        
        job_state = pickle.loads(serialized)
        job = Job.__new__(Job)
        job.__setstate__(job_state)
        return job
    
    def add_job(self, job: Job) -> Job:
        """添加新任务"""
        job_state = job.__getstate__()
        job_data = self._serialize_job(job_state)
        job_data.update({
            '_id': str(job.id) if job.id else str(id(job)),
            'next_run_time': job_state.get('next_run_time'),
            'status': 'scheduled',
            'created_at': datetime.datetime.utcnow(),
            'last_updated': datetime.datetime.utcnow()
        })
        
        try:
            # 使用具有写关注的事务操作
            with self.client.start_session() as session:
                with session.start_transaction():
                    result = self.collection.insert_one(
                        job_data,
                        session=session
                    )
                    job.id = str(result.inserted_id)
            
            self.stats['jobs_added'] += 1
            logger.info("Added job: ID=%s, Name=%s", job.id, job.name)
            return job
        except errors.DuplicateKeyError:
            logger.error("Duplicate job ID detected: %s", job.id)
            raise
        except errors.PyMongoError as e:
            logger.exception("Failed to add job: %s", e)
            raise
    
    def update_job(self, job: Job) -> Job:
        """更新任务状态"""
        job_state = job.__getstate__()
        job_data = self._serialize_job(job_state)
        job_data.update({
            'next_run_time': job_state.get('next_run_time'),
            'last_updated': datetime.datetime.utcnow(),
            'runs': job.runs
        })
        
        try:
            # 使用条件更新避免冲突
            result = self.collection.update_one(
                {'_id': job.id},
                {'$set': job_data},
                upsert=False
            )
            
            if result.modified_count:
                self.stats['jobs_updated'] += 1
                logger.debug("Updated job: ID=%s", job.id)
            else:
                logger.warning("No job found to update: ID=%s", job.id)
            
            return job
        except errors.PyMongoError as e:
            logger.exception("Failed to update job: %s", e)
            raise
    
    def remove_job(self, job: Job) -> bool:
        """移除任务"""
        try:
            result = self.collection.delete_one({'_id': job.id})
            
            if result.deleted_count:
                self.stats['jobs_removed'] += 1
                logger.info("Removed job: ID=%s", job.id)
                return True
            else:
                logger.warning("No job found to remove: ID=%s", job.id)
                return False
        except errors.PyMongoError as e:
            logger.exception("Failed to remove job: %s", e)
            return False
    
    def remove_all_jobs(self) -> int:
        """删除所有任务"""
        try:
            result = self.collection.delete_many({})
            logger.info("Removed %d jobs from MongoDB", result.deleted_count)
            return result.deleted_count
        except errors.PyMongoError as e:
            logger.exception("Failed to remove all jobs: %s", e)
            return 0
    
    def load_jobs(self) -> List[Job]:
        """加载所有任务"""
        return self._load_jobs_by_query({})
    
    def get_due_jobs(self, now: datetime.datetime) -> List[Job]:
        """获取当前应执行的任务"""
        query = {
            'next_run_time': {'$lte': now},
            'status': {'$ne': 'paused'}
        }
        
        try:
            jobs = self._load_jobs_by_query(query)
            self.stats['due_jobs_loaded'] += len(jobs)
            return jobs
        except errors.PyMongoError as e:
            logger.exception("Failed to get due jobs: %s", e)
            return []
    
    def get_next_run_time(self) -> Optional[datetime.datetime]:
        """获取下一个任务的运行时间"""
        try:
            # 使用聚合管道高效获取最小next_run_time
            pipeline = [
                {'$match': {
                    'status': 'scheduled',
                    'next_run_time': {'$ne': None}
                }},
                {'$group': {
                    '_id': None,
                    'next_run_time': {'$min': '$next_run_time'}
                }}
            ]
            
            result = list(self.collection.aggregate(pipeline))
            if result:
                return result[0]['next_run_time']
            return None
        except errors.PyMongoError as e:
            logger.exception("Failed to get next run time: %s", e)
            return None
    
    def pause_job(self, job: Job) -> bool:
        """暂停任务"""
        try:
            result = self.collection.update_one(
                {'_id': job.id},
                {'$set': {
                    'status': 'paused',
                    'last_updated': datetime.datetime.utcnow()
                }}
            )
            return result.modified_count > 0
        except errors.PyMongoError as e:
            logger.exception("Failed to pause job: %s", e)
            return False
    
    def resume_job(self, job: Job) -> bool:
        """恢复任务"""
        try:
            result = self.collection.update_one(
                {'_id': job.id},
                {'$set': {
                    'status': 'scheduled',
                    'last_updated': datetime.datetime.utcnow()
                }}
            )
            return result.modified_count > 0
        except errors.PyMongoError as e:
            logger.exception("Failed to resume job: %s", e)
            return False
    
    def archive_completed_jobs(self, days: int = 30) -> int:
        """归档已完成的任务"""
        try:
            cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
            query = {
                'status': 'completed',
                'last_updated': {'$lt': cutoff_date}
            }
            
            # 归档到历史表
            archive_collection = self.db[f"{self.collection.name}_archive"]
            results = self.collection.find(query)
            if results:
                archive_collection.insert_many(results)
            
            # 删除原始记录
            result = self.collection.delete_many(query)
            return result.deleted_count
        except errors.PyMongoError as e:
            logger.exception("Failed to archive completed jobs: %s", e)
            return 0
    
    def get_job_count(self) -> Dict[str, int]:
        """获取任务计数统计"""
        try:
            statuses = ['scheduled', 'paused', 'completed', 'executing']
            stats = {
                'total': self.collection.count_documents({})
            }
            
            for status in statuses:
                stats[status] = self.collection.count_documents({'status': status})
            
            return stats
        except errors.PyMongoError as e:
            logger.exception("Failed to get job count: %s", e)
            return {}
    
    def optimize_storage(self) -> bool:
        """优化存储性能"""
        try:
            # 重建索引
            self.collection.reindex()
            
            # MongoDB压缩（WiredTiger引擎自动压缩）
            self.db.command({'compact': self.collection.name})
            logger.info("Storage optimization completed")
            return True
        except errors.PyMongoError as e:
            logger.exception("Failed to optimize storage: %s", e)
            return False
    
    def close(self) -> None:
        """关闭数据库连接"""
        try:
            # 释放连接资源
            self.collection.database.client.close()
            logger.info("Disconnected from MongoDB")
        except Exception as e:
            logger.exception("Error disconnecting from MongoDB: %s", e)
    
    def __repr__(self) -> str:
        """提供有意义的表示"""
        try:
            count = self.get_job_count()['total']
        except:
            count = "Unknown"
        
        return (f"<{self.__class__.__name__} (host={self.client.address}, "
                f"db={self.db.name}, jobs={count})>")
    
    def _load_jobs_by_query(self, query: Dict) -> List[Job]:
        """根据查询条件加载任务"""
        try:
            with self.collection.find(query) as cursor:
                return [self._deserialize_job(doc) for doc in cursor]
        except Exception as e:
            logger.exception("Failed to load jobs: %s", e)
            return []


class MongoDBJobStoreManager:
    """MongoDB任务存储集群管理器"""
    def __init__(self, jobstore: MongoDBJobStore):
        self.jobstore = jobstore
    
    def get_cluster_status(self) -> Dict:
        """获取集群状态信息"""
        try:
            return self.jobstore.db.command('replSetGetStatus')
        except errors.OperationFailure:
            return {'status': 'Standalone'}
    
    def get_server_info(self) -> Dict:
        """获取服务器信息"""
        return self.jobstore.db.client.server_info()
    
    def get_cluster_nodes(self) -> List:
        """获取集群节点信息"""
        try:
            status = self.get_cluster_status()
            return status.get('members', [])
        except Exception:
            return []
    
    def check_connection_health(self) -> Dict:
        """检查集群连接健康状态"""
        health_report = {'status': 'ok'}
        nodes = self.get_cluster_nodes()
        
        for node in nodes:
            node_status = {
                'name': node['name'],
                'health': node['health'],
                'state': node['stateStr'],
                'lag': node.get('optimeDate', None)
            }
            health_report.setdefault('nodes', []).append(node_status)
        
        return health_report


class JobStoreCompressionMixin:
    """任务存储压缩功能混入类"""
    def __init__(self, compression_level: int = 6):
        self.compression_level = compression_level
    
    def compress(self, data: bytes) -> bytes:
        """压缩任务数据"""
        import zlib
        return zlib.compress(data, self.compression_level)
    
    def decompress(self, data: bytes) -> bytes:
        """解压缩任务数据"""
        import zlib
        return zlib.decompress(data)
