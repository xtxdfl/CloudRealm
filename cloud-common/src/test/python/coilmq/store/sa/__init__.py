#!/usr/bin/env python3
"""
现代版 SQLAlchemy 队列存储实现

使用 SQLAlchemy Core API 提供高性能的持久化队列服务，
支持多线程环境和高并发访问。
"""

from sqlalchemy import create_engine, MetaData, select, func, distinct, delete
from sqlalchemy.orm import scoped_session, sessionmaker
from contextlib import contextmanager

from .. import QueueStore
from ...config import config
from ...exception import ConfigError
from . import model

# --- 全局元数据管理 ---
_db_meta = {
    'engine': None,
    'metadata': MetaData(),
    'session_factory': None,
}

# --- 数据库连接管理 ---
def get_sa_engine():
    """获取 SQLAlchemy 引擎实例"""
    if not _db_meta['engine']:
        raise RuntimeError("Database engine not initialized. Call init_model() first.")
    return _db_meta['engine']

@contextmanager
def session_scope():
    """提供事务作用域的会话管理"""
    session = _db_meta['session_factory']()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# --- 存储工厂函数 ---
def make_sa_store():
    """创建 SQLAlchemy 队列存储实例"""
    configuration = config.to_dict()
    connection_str = configuration.get('qstore.sqlalchemy.url', 
                                      'sqlite:///coilmq_queues.db')
    
    # 创建数据库引擎并根据配置进行调整
    engine_params = {
        'pool_size': configuration.getint('qstore.sqlalchemy.pool_size', 5),
        'max_overflow': configuration.getint('qstore.sqlalchemy.max_overflow', 10),
        'pool_recycle': configuration.getint('qstore.sqlalchemy.pool_recycle', 3600),
        'echo': configuration.getboolean('qstore.sqlalchemy.echo', False)
    }
    
    engine = create_engine(connection_str, **engine_params)
    init_model(engine)
    return SAQueueStore()

# --- 模型初始化 ---
def init_model(engine, create_tables=True, drop_tables=False):
    """
    初始化 SQLAlchemy 模型
    
    :param engine: SQLAlchemy 引擎实例
    :param create_tables: 是否创建缺失的表结构
    :param drop_tables: 是否在创建前删除现有表（危险操作）
    """
    # 更新全局元数据
    _db_meta.update({
        'engine': engine,
        'metadata': model.Base.metadata,
        'session_factory': scoped_session(sessionmaker(bind=engine))
    })
    
    # 处理表结构操作
    if drop_tables:
        model.Base.metadata.drop_all(engine)
    if create_tables:
        model.Base.metadata.create_all(engine)

# --- 队列存储实现 ---
class SAQueueStore(QueueStore):
    """使用 SQLAlchemy 实现的队列存储系统"""
    
    def enqueue(self, destination, frame):
        """将消息放入指定目的地队列"""
        if not frame.headers.get("message-id"):
            raise ValueError("消息必须包含 message-id 头部")
        
        with session_scope() as session:
            session.execute(
                model.Frame.__table__.insert().values(
                    message_id=frame.headers["message-id"],
                    destination=destination,
                    frame=frame,
                    priority=int(frame.headers.get("priority", 4))
                )
            )
    
    def dequeue(self, destination):
        """从指定队列取出并删除最早的消息"""
        with session_scope() as session:
            # 获取最旧消息（按优先级排序）
            stmt = (
                select(model.Frame)
                .where(model.Frame.destination == destination)
                .order_by(model.Frame.priority.asc(), model.Frame.queued.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            
            frame_rec = session.execute(stmt).scalar()
            if not frame_rec:
                return None
                
            # 删除消息并提交事务
            session.execute(
                delete(model.Frame).where(
                    model.Frame.message_id == frame_rec.message_id
                )
            )
            
            return frame_rec.frame
    
    def has_frames(self, destination):
        """检查指定队列是否有消息"""
        with session_scope() as session:
            stmt = (
                select(func.count())
                .select_from(model.Frame)
                .where(model.Frame.destination == destination)
            )
            return session.execute(stmt).scalar() > 0
    
    def size(self, destination):
        """返回指定队列的消息数量"""
        with session_scope() as session:
            stmt = (
                select(func.count())
                .select_from(model.Frame)
                .where(model.Frame.destination == destination)
            )
            return session.execute(stmt).scalar()
    
    def destinations(self):
        """获取所有存在的队列目标"""
        with session_scope() as session:
            stmt = select(distinct(model.Frame.destination))
            return {dest[0] for dest in session.execute(stmt)}
    
    def close(self):
        """清理资源，关闭连接池"""
        engine = get_sa_engine()
        engine.dispose()
        _db_meta['session_factory'].remove()

# --- 辅助函数 ---
def get_session():
    """获取当前线程范围的会话（用于直接数据库操作）"""
    return _db_meta['session_factory']()

def clean_expired_messages(max_age=timedelta(hours=24)):
    """清理过期消息（默认为24小时以上）"""
    with session_scope() as session:
        cutoff = datetime.utcnow() - max_age
        stmt = delete(model.Frame).where(model.Frame.queued < cutoff)
        result = session.execute(stmt)
        return result.rowcount
