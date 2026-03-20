#!/usr/bin/env python3
"""
现代化的SQLAlchemy状态管理模块

使用强类型和线程安全方式管理SQLAlchemy核心资源。
"""
from typing import Optional
from sqlalchemy.orm import scoped_session
from sqlalchemy.engine import Engine
from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker

class SQLAlchemyContext:
    """
    SQLAlchemy资源上下文管理器
    
    提供类型安全的engine、session_factory和metadata管理
    支持自动清理和依赖注入
    """
    
    __slots__ = ('engine', 'session_factory', 'metadata')
    
    def __init__(self):
        """初始化空状态"""
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[scoped_session] = None
        self.metadata: Optional[MetaData] = None
    
    def configure(self, connection_url: str, **engine_kwargs) -> None:
        """
        配置SQLAlchemy上下文
        
        :param connection_url: 数据库连接字符串
        :param engine_kwargs: 引擎配置参数 (pool_size, echo等)
        """
        # 创建引擎
        from sqlalchemy import create_engine
        self.engine = create_engine(connection_url, **engine_kwargs)
        
        # 创建元数据
        self.metadata = MetaData()
        
        # 创建会话工厂 (加入事务自动处理)
        self.session_factory = scoped_session(
            sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        )
    
    def get_session(self) -> scoped_session:
        """获取线程安全的会话实例"""
        if not self.session_factory:
            raise RuntimeError("上下文未配置，请先调用configure()")
        return self.session_factory
    
    def dispose(self) -> None:
        """释放所有连接资源"""
        if self.engine:
            self.engine.dispose()
        if self.session_factory:
            self.session_factory.remove()
        
        # 清空状态
        self.engine = None
        self.session_factory = None
        self.metadata = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()
    
    def is_configured(self) -> bool:
        """检查上下文是否已配置"""
        return all([
            self.engine is not None,
            self.session_factory is not None,
            self.metadata is not None
        ])

# --- 单例全局上下文 (线程安全) ---
db_context = SQLAlchemyContext()

# --- 向后兼容别名 (可选) ---
engine = property(lambda _: db_context.engine)
Session = property(lambda _: db_context.session_factory)
metadata = property(lambda _: db_context.metadata)

# --- 快捷函数 ---
def get_engine() -> Engine:
    """获取当前数据库引擎"""
    return db_context.engine

def get_session() -> scoped_session:
    """获取当前会话工厂"""
    return db_context.get_session()

def get_metadata() -> MetaData:
    """获取元数据实例"""
    return db_context.metadata

def init_context(connection_url: str, **engine_kwargs) -> None:
    """初始化全局上下文 (应首先调用)"""
    db_context.configure(connection_url, **engine_kwargs)

def shutdown() -> None:
    """清理所有数据库资源"""
    db_context.dispose()

