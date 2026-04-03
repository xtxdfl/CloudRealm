#!/usr/bin/env python3
"""
高级日期触发器 - 提供高精度的一次性触发功能
支持时区感知、容差处理、时间验证和边界条件处理
"""

import datetime
from typing import Union, Optional, Any
from apscheduler.util import convert_to_datetime


class SimpleTrigger:
    """精确日期触发器，用于在特定时间点执行一次任务"""
    
    __slots__ = ('run_date', '_original_date', '_has_fired', '_timezone')
    
    def __init__(self, run_date: Union[datetime.datetime, str]):
        """
        初始化日期触发器
        
        参数:
            run_date: 触发时间，可以是datetime对象或符合ISO 8601的字符串
        """
        self._original_date = run_date
        self.run_date = convert_to_datetime(run_date)
        self._has_fired = False
        
        # 检查触发时间是否合理
        self._validate_trigger_time()
        
    def _validate_trigger_time(self):
        """验证触发时间的有效性"""
        current_time = datetime.datetime.now(self.run_date.tzinfo) if self.run_date.tzinfo else datetime.datetime.utcnow()
        
        # 检查是否在合理的时间范围内
        if self.run_date.year < 1970:
            raise ValueError(f"Invalid year {self.run_date.year} - must be >= 1970")
        
        # 检查是否在遥远的未来（超过100年）
        if self.run_date.year > current_time.year + 100:
            raise ValueError(f"Trigger date is too far in the future ({self.run_date.year})")
        
    def get_next_fire_time(self, 
                           base_time: Optional[datetime.datetime] = None
                          ) -> Optional[datetime.datetime]:
        """
        获取下一次触发时间
        
        参数:
            base_time: 计算的基准时间，默认为当前时间
            
        返回:
            触发时间（如果满足条件），否则返回None
        """
        # 如果已经触发过，直接返回None
        if self._has_fired:
            return None
            
        # 确定基准时间
        base_time = base_time or datetime.datetime.now(self.run_date.tzinfo)
        
        # 如果触发器没有时区信息，转换为UTC
        if self.run_date.tzinfo is None:
            self.run_date = self.run_date.replace(tzinfo=datetime.timezone.utc)
            base_time = base_time.replace(tzinfo=datetime.timezone.utc)
        
        # 检查时区一致性
        if base_time.tzinfo != self.run_date.tzinfo:
            base_time = base_time.astimezone(self.run_date.tzinfo)
        
        # 使用时间戳进行精确比较
        run_timestamp = self.run_date.timestamp()
        base_timestamp = base_time.timestamp()
        
        # 使用微小容差处理边界条件
        if run_timestamp - base_timestamp <= 1e-3:  # 1毫秒容差
            self._has_fired = True
            return self.run_date
        elif run_timestamp > base_timestamp:
            return self.run_date
        
        # 超过触发时间但未触发（不应该发生）
        self._has_fired = True
        return None
    
    @property
    def time_until_fire(self) -> Optional[float]:
        """获取距离触发时间的秒数（如果未触发）"""
        if self._has_fired:
            return None
            
        current_time = datetime.datetime.now(self.run_date.tzinfo)
        delta = self.run_date - current_time
        return max(0.0, delta.total_seconds() if delta.days >= 0 else -1.0)
    
    def reset(self) -> None:
        """重置触发状态（用于测试和特殊场景）"""
        self._has_fired = False
    
    def __str__(self) -> str:
        """友好的字符串表示"""
        formatted_date = self.run_date.isoformat(sep=' ', timespec='milliseconds')
        tz_info = self.run_date.tzinfo.tzname(self.run_date) if self.run_date.tzinfo else "UTC"
        status = "pending" if not self._has_fired else "triggered"
        return f"Trigger[date={formatted_date} {tz_info}, status={status}]"
    
    def __repr__(self) -> str:
        """完整的对象表示"""
        formatted_date = self.run_date.isoformat() 
        tz_info = self.run_date.tzinfo.zone if self.run_date.tzinfo else "UTC"
        status = "triggered" if self._has_fired else "active"
        return f"<{self.__class__.__name__}(date={formatted_date} {tz_info}, status={status})>"
    
    def __eq__(self, other: Any) -> bool:
        """比较两个触发器是否相等"""
        if not isinstance(other, SimpleTrigger):
            return False
        return (self.run_date == other.run_date and
                self._has_fired == other._has_fired)
    
    def __hash__(self) -> int:
        """计算哈希值"""
        return hash((self.run_date, self._has_fired))


class DelayedTrigger(SimpleTrigger):
    """延迟触发器，基于基准时间计算触发时间"""
    
    def __init__(self, delay: Union[int, float, datetime.timedelta]):
        """
        初始化延迟触发器
        
        参数:
            delay: 延迟时间（秒数或timedelta对象）
        """
        if isinstance(delay, (int, float)):
            delay = datetime.timedelta(seconds=delay)
        elif not isinstance(delay, datetime.timedelta):
            raise TypeError("延迟时间必须是数字或timedelta对象")
            
        super().__init__(datetime.datetime.utcnow() + delay)
    
    @property
    def delay(self) -> float:
        """获取当前延迟时间（基于当前时间）"""
        return self.time_until_fire or 0.0


class ToleranceTrigger(SimpleTrigger):
    """带宽容差的日期触发器，处理边缘情况"""
    
    def __init__(self, 
                 run_date: Union[datetime.datetime, str],
                 tolerance: float = 0.1):
        """
        初始化带宽容差的触发器
        
        参数:
            run_date: 触发时间
            tolerance: 时间容差（秒），允许在这个时间范围内触发
        """
        super().__init__(run_date)
        self.tolerance = tolerance
    
    def get_next_fire_time(self, 
                          base_time: Optional[datetime.datetime] = None
                         ) -> Optional[datetime.datetime]:
        """获取下一次触发时间（考虑容差）"""
        if self._has_fired:
            return None
            
        base_time = base_time or datetime.datetime.now(self.run_date.tzinfo)
        
        # 计算时间差（考虑时区）
        if base_time.tzinfo != self.run_date.tzinfo:
            base_time = base_time.astimezone(self.run_date.tzinfo)
        
        time_delta = (self.run_date - base_time).total_seconds()
        
        # 检查是否在容差范围内
        if -self.tolerance <= time_delta <= self.tolerance:
            self._has_fired = True
            return base_time  # 返回当前时间而不是理论时间
        
        # 正常触发检查
        if self.run_date > base_time:
            return self.run_date
        
        # 超过容差范围，标记为已触发
        self._has_fired = True
        return None


class FutureDateTrigger:
    """未来时间复合触发器，适用于日历事件"""
    
    def __init__(self, date_func: callable):
        """
        初始化未来时间触发器
        
        参数:
            date_func: 返回下一个触发时间的函数
        """
        self.date_func = date_func
        self._next_run_date = None
        self._update_next_run_date()
    
    def _update_next_run_date(self):
        """计算下一个触发时间"""
        self._next_run_date = self.date_func()
        if not self._next_run_date:
            raise ValueError("Date function must return a valid datetime")
        
        if not isinstance(self._next_run_date, datetime.datetime):
            self._next_run_date = convert_to_datetime(self._next_run_date)
    
    def get_next_fire_time(self, 
                           base_time: Optional[datetime.datetime] = None
                          ) -> Optional[datetime.datetime]:
        """获取下一个触发时间"""
        if not self._next_run_date:
            return None
            
        base_time = base_time or datetime.datetime.now(self._next_run_date.tzinfo)
        
        # 如果已经过了当前计划的触发时间，计算下一个
        if self._next_run_date <= base_time:
            self._update_next_run_date()
            
        # 检查是否在合理时间内
        if self._next_run_date <= base_time:
            return None
            
        return self._next_run_date
    
    @property
    def next_run_date(self) -> Optional[datetime.datetime]:
        """获取下一个计划的运行日期"""
        return self._next_run_date
    
    @property
    def is_expired(self) -> bool:
        """检查是否还有未来触发时间"""
        try:
            self._update_next_run_date()
            return False
        except (StopIteration, ValueError):
            return True
