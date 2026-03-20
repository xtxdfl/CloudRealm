#!/usr/bin/env python3
"""
优化的SQLAlchemy数据模型定义

使用声明式系统实现强类型数据模型，包含索引优化和关系映射。
"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, func, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import registry
from typing import Any, Optional

# --- ORM 基类定义 ---
BaseModel = declarative_base()
mapper_registry = registry()

class FrameModel(BaseModel):
    """消息帧的持久化数据模型"""
    
    __tablename__  = 'frames'
    __table_args__ = (
        Index('idx_destination_priority', 'destination', 'priority'),
        Index('idx_destination_queued', 'destination', 'queued'),
        {'comment': 'STOMP消息存储表'}
    )
    
    # 主键使用自增ID (比消息ID更高效)
    id = Column(BigInteger, primary_key=True, autoincrement=True, 
               comment='自增主键ID')
    
    # 业务唯一标识符
    message_id = Column(String(255), nullable=False, unique=True,
                      comment='消息唯一标识符(业务键)')
    
    destination = Column(String(255), nullable=False, 
                        comment='目标队列/主题路径')
    
    # 添加优先级支持 (STOMP标准)
    priority = Column(BigInteger, default=4, 
                     comment='消息优先级(0-9, 0最高)')
    
    # 消息帧序列化对象
    frame = Column(db.PickleType, nullable=False, 
                 comment='序列化的消息帧对象')
    
    # 自动时间戳管理
    created = Column(DateTime, server_default=func.now(), 
                   comment='消息创建时间')
    
    queued = Column(DateTime, server_default=func.now(), 
                  index=True, comment='入队时间')
    
    # 添加过期时间字段 - 可选
    expires = Column(DateTime, nullable=True, 
                   comment='消息过期时间', index=True)

    # ORM 关系映射 - 示例 (可根据需要扩展)
    # properties = relationship("FrameProperty", back_populates="frame")

    def __repr__(self) -> str:
        return f"<Frame {self.message_id} to '{self.destination}' at {self.queued}>"

class FramePropertyModel(BaseModel):
    """扩展属性表（示例模型）"""
    
    __tablename__ = 'frame_properties'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    frame_id = Column(BigInteger, ForeignKey('frames.id'))
    key = Column(String(100), nullable=False)
    value = Column(String(255), nullable=True)
    
    # 关系映射
    # frame = relationship("FrameModel", back_populates="properties")

# --- 辅助函数 ---
def register_mappers() -> None:
    """显式注册所有ORM映射"""
    mapper_registry.map_imperatively(FrameModel, FrameModel.__table__)
    # mapper_registry.map_imperatively(FramePropertyModel, FramePropertyModel.__table__)

def setup_database(
    engine: Engine, 
    *,
    create_all: bool = True,
    drop_all: bool = False
) -> None:
    """
    数据库初始化函数
    
    :param engine: SQLAlchemy引擎实例
    :param create_all: 是否创建所有表结构
    :param drop_all: 是否在创建前删除所有表（危险操作）
    """
    # 注册映射
    register_mappers()
    
    # 处理表结构操作
    if drop_all:
        BaseModel.metadata.drop_all(engine)
    
    if create_all:
        BaseModel.metadata.create_all(engine)

# --- 类型别名 ---
FrameType = FrameModel

