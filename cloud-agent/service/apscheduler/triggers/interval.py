#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级时间间隔触发器 - 为任务调度系统提供高效的间隔触发功能
支持动态间隔调整、时区感知、漂移补偿和边界条件优化
"""

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Tuple, Callable
from math import ceil

logger = logging.getLogger(__name__)


class IntervalTrigger:
    """高级时间间隔触发器
    
    特性：
    1. 支持动态间隔调整
    2. 精确漂移补偿技术
    3. 高性能时间计算
    4. 时区感知支持
    5. 自定义间隔计算函数
    """
    
    def __init__(self, 
                 interval: Union[timedelta, float, int],
                 start_date: Optional[Union[datetime, str]] = None,
                 jitter: Optional[Union[timedelta, float]] = None,
                 timezone: Optional[timezone] = None,
                 max_interval: Optional[Union[timedelta, float]] = None,
                 interval_adjuster: Optional[Callable[[timedelta], timedelta]] = None):
        """
        初始化间隔触发器
        
        参数：
            interval: 触发间隔，可以是timedelta对象或秒数
            start_date: 首次触发时间（可选）
            jitter: 触发时间随机波动幅度（防止任务风暴）
            timezone: 时区信息
            max_interval: 最大允许间隔（安全限制）
            interval_adjuster: 动态调整间隔的函数
        """
        # 转换间隔为timedelta
        self.interval = self._parse_interval(interval)
        self.interval_seconds = self._get_total_seconds(self.interval)
        
        if self.interval_seconds <= 0:
            raise ValueError("Interval must be positive")
        
        # 处理时区
        self.tzinfo = timezone.utc if timezone is None else timezone
        
        # 设置首触发时间
        current_time = datetime.now(self.tzinfo)
        self.start_date = self._parse_date(start_date) if start_date else current_time + self.interval
        
        # 设置最大间隔限制
        self.max_interval = self._parse_interval(max_interval) if max_interval else None
        
        # 设置时间抖动
        self.jitter = self._parse_jitter(jitter) if jitter else None
        
        # 间隔调整函数
        self.interval_adjuster = interval_adjuster
        
        # 用于漂移补偿的内部跟踪
        self._last_fire_time = None
        self._drift_compensation = timedelta(0)
        logger.debug(
            f"IntervalTrigger initialized: "
            f"interval={self.interval}, "
            f"start={self.start_date}, "
            f"jitter={self.jitter}"
        )
    
    def _parse_interval(self, interval: Union[timedelta, float, int]) -> timedelta:
        """解析间隔参数"""
        if isinstance(interval, timedelta):
            return interval
        elif isinstance(interval, (float, int)):
            return timedelta(seconds=interval)
        else:
            raise TypeError("Interval must be timedelta or float/int seconds")
    
    def _parse_jitter(self, jitter: Union[timedelta, float]) -> timedelta:
        """解析时间抖动参数"""
        if isinstance(jitter, timedelta):
            return jitter
        elif isinstance(jitter, (float, int)):
            return timedelta(seconds=abs(jitter))
    
    def _parse_date(self, date: Union[datetime, str]) -> datetime:
        """解析日期参数"""
        if isinstance(date, datetime):
            if date.tzinfo is None:
                date = date.replace(tzinfo=self.tzinfo)
            return date
        return datetime.fromisoformat(date).replace(tzinfo=self.tzinfo)
    
    def _get_total_seconds(self, td: timedelta) -> float:
        """精确获取timedelta的总秒数（兼容所有Python版本）"""
        return td.total_seconds()
    
    def _apply_jitter(self, fire_time: datetime) -> datetime:
        """应用随机抖动"""
        if not self.jitter:
            return fire_time
        
        # 生成 ±jitter 范围内的随机偏移
        jitter_seconds = self._get_total_seconds(self.jitter)
        import random
        offset = random.uniform(-jitter_seconds, jitter_seconds)
        
        return fire_time + timedelta(seconds=offset)
    
    def _apply_interval_adjustment(self) -> timedelta:
        """应用动态间隔调整"""
        if not self.interval_adjuster:
            return self.interval
        
        new_interval = self.interval_adjuster(self.interval)
        
        # 应用最大间隔限制
        if self.max_interval:
            max_seconds = self._get_total_seconds(self.max_interval)
            new_seconds = self._get_total_seconds(new_interval)
            if new_seconds > max_seconds:
                new_interval = self.max_interval
        
        return self._parse_interval(new_interval)
    
    def _calculate_drift(self, actual_fire_time: datetime):
        """计算并补偿时间漂移"""
        if not self._last_fire_time or not actual_fire_time:
            return
        
        # 计算预期和实际触发时间的差异
        expected_fire_time = self._last_fire_time + self.interval
        time_drift = actual_fire_time - expected_fire_time
        
        # 应用漂移补偿策略
        drift_threshold = timedelta(seconds=self.interval_seconds * 0.1)
        if abs(time_drift) > drift_threshold:
            # 比例补偿策略
            compensation_factor = -0.5  # 50%补偿
            self._drift_compensation += time_drift * compensation_factor
            
            # 限制最大补偿量
            max_compensation = timedelta(seconds=self.interval_seconds * 0.2)
            self._drift_compensation = max(
                -max_compensation, 
                min(self._drift_compensation, max_compensation)
            )
            
            logger.debug(
                f"Drift detected: {time_drift.total_seconds()}s. "
                f"Applying compensation: {self._drift_compensation.total_seconds()}s"
            )
    
    def get_next_fire_time(self, 
                           start_date: Optional[datetime] = None,
                           last_fire_time: Optional[datetime] = None,
                           current_time: Optional[datetime] = None) -> datetime:
        """
        计算下一个触发时间
        
        参数：
            start_date: 计算起始时间
            last_fire_time: 上一次实际触发时间
            current_time: 当前时间（用于精度计算）
            
        返回：
            下一个触发时间
        """
        # 更新内部状态
        reference_time = current_time or datetime.now(self.tzinfo)
        self._last_fire_time = last_fire_time
        
        # 应用漂移补偿
        if last_fire_time:
            self._calculate_drift(last_fire_time)
        
        # 应用间隔调整
        adjusted_interval = self._apply_interval_adjustment()
        
        # 设置起始计算点
        if not start_date:
            start_date = self.start_date
        
        # 确保日期具有时区信息
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=self.tzinfo)
        
        # 如果起始时间早于首次触发时间，返回首次触发时间
        if start_date < self.start_date:
            fire_time = self.start_date
        else:
            # 计算从开始时间到当前时间经过了多少个间隔
            time_diff = (start_date - self.start_date).total_seconds()
            intervals_passed = ceil(time_diff / self.interval_seconds)
            
            # 计算下一个理论触发时间
            fire_time = self.start_date + timedelta(seconds=intervals_passed * self.interval_seconds)
        
        # 应用动态间隔调整
        fire_time += self._drift_compensation
        
        # 应用随机抖动
        fire_time = self._apply_jitter(fire_time)
        
        # 确保不会超过最大间隔
        if self.max_interval and last_fire_time:
            max_fire_time = last_fire_time + self.max_interval
            if fire_time > max_fire_time:
                fire_time = max_fire_time
        
        logger.debug(
            f"Calculated fire time: {fire_time.isoformat()} "
            f"(start: {start_date.isoformat()}, "
            f"last: {str(last_fire_time) if last_fire_time else 'None'})"
        )
        
        return fire_time
    
    def is_due(self, current_time: datetime) -> Tuple[bool, datetime]:
        """
        检查当前时间是否应该触发任务
        
        参数：
            current_time: 当前时间
            
        返回：
            (是否触发, 下次触发时间)
        """
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=self.tzinfo)
        
        # 获取下一个触发时间
        next_fire_time = self.get_next_fire_time(
            start_date=current_time,
            last_fire_time=self._last_fire_time,
            current_time=current_time
        )
        
        # 检查是否应该触发
        if (next_fire_time - current_time).total_seconds() <= 0:
            self._last_fire_time = current_time
            return True, next_fire_time
        
        return False, next_fire_time
    
    def get_schedule(self, 
                     start: datetime, 
                     end: datetime, 
                     count: int = 10) -> List[datetime]:
        """
        获取指定时间范围内的触发时间列表
        
        参数：
            start: 开始时间
            end: 结束时间
            count: 最大返回数量
            
        返回：
            触发时间列表
        """
        fire_times = []
        next_time = self.get_next_fire_time(start)
        
        while next_time <= end and len(fire_times) < count:
            fire_times.append(next_time)
            start = next_time + timedelta(seconds=1)
            next_time = self.get_next_fire_time(start)
        
        return fire_times
    
    def __str__(self):
        return f"IntervalTrigger[interval={self.interval}]"
    
    def __repr__(self):
        return (
            f"<{self.__class__.__name__}("
            f"interval={self.interval}, "
            f"start_date={self.start_date.isoformat()}, "
            f"jitter={self.jitter}, "
            f"tzinfo={self.tzinfo})>"
        )


class DynamicIntervalTrigger(IntervalTrigger):
    """动态间隔触发器 - 间隔可根据条件调整的增强版本"""
    
    def __init__(self, 
                 base_interval: Union[timedelta, float],
                 interval_multiplier: float = 1.0,
                 max_interval_multiplier: float = 10.0,
                 min_interval: Optional[Union[timedelta, float]] = None,
                 **kwargs):
        """
        初始化动态间隔触发器
        
        参数：
            base_interval: 基础间隔
            interval_multiplier: 间隔乘数
            max_interval_multiplier: 最大乘数限制
            min_interval: 最小间隔限制
        """
        super().__init__(base_interval, **kwargs)
        self.base_interval = self.interval
        self.interval_multiplier = interval_multiplier
        self.max_interval_multiplier = max_interval_multiplier
        self.min_interval = self._parse_interval(min_interval) if min_interval else None
    
    def adjust_multiplier(self, multiplier: float):
        """调整间隔乘数"""
        self.interval_multiplier = max(0.1, min(multiplier, self.max_interval_multiplier))
        logger.info(f"Interval multiplier adjusted to: {self.interval_multiplier}")
    
    def _apply_interval_adjustment(self) -> timedelta:
        """应用动态间隔调整"""
        # 计算新的间隔
        factor = max(0.1, min(self.interval_multiplier, self.max_interval_multiplier))
        new_interval = self.base_interval * factor
        
        # 应用安全限制
        if self.min_interval and new_interval < self.min_interval:
            return self.min_interval
        
        return new_interval


class TimeWindowIntervalTrigger(IntervalTrigger):
    """时间段内生效的间隔触发器"""
    
    def __init__(self,
                 interval: Union[timedelta, float],
                 time_window_start: Union[datetime, str, int] = 0,
                 time_window_end: Union[datetime, str, int] = 86400,
                 **kwargs):
        """
        初始化时间段间隔触发器
        
        参数：
            interval: 时间间隔
            time_window_start: 生效窗口开始时间（时间戳、时间对象或小时整数）
            time_window_end: 生效窗口结束时间
        """
        super().__init__(interval, **kwargs)
        self.time_window_start = self._parse_time_window(time_window_start)
        self.time_window_end = self._parse_time_window(time_window_end)
    
    def _parse_time_window(self, window_spec):
        """解析时间窗口参数"""
        if isinstance(window_spec, datetime):
            return window_spec.time()
        elif isinstance(window_spec, str):
            return datetime.strptime(window_spec, "%H:%M").time()
        elif isinstance(window_spec, int):
            # 0-24小时表示法
            if not 0 <= window_spec <= 24:
                raise ValueError("Hour must be between 0 and 24")
            return datetime.strptime(f"{window_spec:02d}:00", "%H:%M").time()
        else:
            raise TypeError("Invalid time window specification")
    
    def get_next_fire_time(self, 
                           start_date: Optional[datetime] = None,
                           last_fire_time: Optional[datetime] = None,
                           current_time: Optional[datetime] = None) -> datetime:
        """获取下一个触发时间（在时间窗口内）"""
        base_time = super().get_next_fire_time(start_date, last_fire_time, current_time)
        
        # 调整到时间窗口内
        while not self._in_time_window(base_time):
            # 如果不在窗口内，移动到窗口开始时间
            next_day = base_time.date() + timedelta(days=1)
            window_start = datetime.combine(base_time.date(), self.time_window_start)
            
            if base_time.time() > self.time_window_end:
                base_time = datetime.combine(next_day, self.time_window_start)
            else:
                base_time = window_start
        
        return base_time
    
    def _in_time_window(self, time_point: datetime) -> bool:
        """检查时间点是否在时间窗口内"""
        time_start = self.time_window_start
        time_end = self.time_window_end
        
        # 处理跨天时间窗口
        if time_end < time_start:
            return (time_point.time() >= time_start) or (time_point.time() < time_end)
        
        return time_start <= time_point.time() < time_end
