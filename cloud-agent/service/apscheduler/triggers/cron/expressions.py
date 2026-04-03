#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级Cron表达式解析器 - 支持所有标准Cron语法和扩展特性
包括工作日范围、位置表达式和月最后一天处理
"""

import re
from abc import ABC, abstractmethod
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Pattern, Tuple, Union

# 日志配置
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FieldType(Enum):
    """时间字段类型枚举"""
    SECOND = 0
    MINUTE = 1
    HOUR = 2
    DAY_OF_MONTH = 3
    MONTH = 4
    DAY_OF_WEEK = 5
    YEAR = 6


# 星期名称映射
WEEKDAY_NAMES = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, 
    "friday": 4, "saturday": 5, "sunday": 6
}

# 月份名称映射
MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, 
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12
}

# 特殊位置选项
POSITION_OPTIONS = ["1st", "2nd", "3rd", "4th", "5th", "last"]


def smart_int(value: str) -> int:
    """智能整数转换，支持名称映射"""
    # 尝试直接转换为整数
    if value.isdigit():
        return int(value)
    
    # 尝试周名称
    lower_val = value.lower()
    if lower_val in WEEKDAY_NAMES:
        return WEEKDAY_NAMES[lower_val]
    
    # 尝试月份名称
    if lower_val in MONTH_NAMES:
        return MONTH_NAMES[lower_val]
    
    # 无法解析
    raise ValueError(f"无法识别的值: '{value}'")


@dataclass
class ExpressionMatch:
    """表达式匹配结果"""
    matched: bool
    groups: Dict[str, str] = None
    error: str = None


class CronExpressionBase(ABC):
    """Cron表达式解析基类"""
    pattern: Pattern
    
    def __init__(self, expression: str, field_type: FieldType = None):
        self.expression = expression.strip()
        self.field_type = field_type
        self.compiled = False
        
    @abstractmethod
    def get_next_value(self, date: datetime, field):
        """计算下一个有效值"""
        pass
    
    def validate(self):
        """验证表达式有效性"""
        if not self.pattern.match(self.expression):
            raise ValueError(f"无效的表达式: '{self.expression}'")
    
    def parse_params(self):
        """解析模式参数"""
        match = self.pattern.match(self.expression)
        if not match:
            raise ValueError(f"表达式不匹配: '{self.expression}'")
        return match.groupdict()
    
    def __repr__(self):
        params = getattr(self, 'params', {})
        params_str = ", ".join(f"{k}='{v}'" for k, v in params.items())
        return f"{self.__class__.__name__}({params_str})"
    
    def __str__(self):
        return self.expression


class AllExpression(CronExpressionBase):
    """处理 '*' 表达式"""
    pattern = re.compile(r"^\s*\*(\/(?P<step>\d+))?\s*$")
    
    def __init__(self, expression: str, field_type: FieldType):
        super().__init__(expression, field_type)
        self.params = self.parse_params()
        self.step = smart_int(self.params.get("step", "1")) if self.params.get("step") else 1
        if self.step <= 0:
            raise ValueError("步长必须大于0")
    
    def get_next_value(self, date: datetime, field):
        """获取下一个匹配值"""
        current_value = field.get_value(date)
        min_val = field.get_min(date)
        max_val = field.get_max(date)
        
        # 如果值在范围内，尝试步长递增
        if min_val <= current_value <= max_val:
            next_val = ((current_value - min_val) // self.step) * self.step + self.step + min_val
            if next_val <= max_val:
                return next_val
        
        # 返回最小值作为下一个值
        return min_val


class RangeExpression(CronExpressionBase):
    """处理范围表达式"""
    pattern = re.compile(r"^\s*(?P<first>\d+|\w+)(\s*-\s*(?P<last>\d+|\w+))?(\s*/\s*(?P<step>\d+))?\s*$")
    
    def __init__(self, expression: str, field_type: FieldType):
        super().__init__(expression, field_type)
        self.params = self.parse_params()
        
        # 解析起始值
        self.first = smart_int(self.params["first"])
        
        # 解析结束值
        last_val = self.params.get("last")
        if last_val:
            self.last = smart_int(last_val)
        else:
            self.last = self.first
        
        # 解析步长
        step_val = self.params.get("step")
        self.step = smart_int(step_val) if step_val else 1
        
        # 验证范围
        if self.first > self.last:
            raise ValueError(f"起始值 {self.first} 不能大于结束值 {self.last}")
        if self.step <= 0:
            raise ValueError("步长必须大于0")
        
        # 生成有效值列表
        self.values = list(range(self.first, self.last + 1, self.step))
        logger.debug(f"范围表达式解析: {self.expression} -> {self.values} (步长={self.step})")
    
    def get_next_value(self, date: datetime, field):
        """获取下一个匹配值"""
        current_value = field.get_value(date)
        min_val = field.get_min(date)
        max_val = field.get_max(date)
        
        # 筛选在范围内的有效值
        valid_values = [v for v in self.values if min_val <= v <= max_val and v >= current_value]
        
        # 寻找最小值
        if valid_values:
            # 确保当前值之后的第一个值
            if valid_values[0] <= current_value:
                if len(valid_values) > 1:
                    return valid_values[1]
                return None  # 没有更大的值
            
            return valid_values[0]
        
        return None


class WeekdayRangeExpression(CronExpressionBase):
    """处理星期范围表达式"""
    pattern = re.compile(r"^\s*(?P<first>[a-z]+)(\s*-\s*(?P<last>[a-z]+))?\s*$", re.IGNORECASE)
    
    def __init__(self, expression: str, field_type: FieldType):
        super().__init__(expression, field_type)
        self.params = self.parse_params()
        
        # 解析起始星期
        first_lower = self.params["first"].lower()
        if first_lower not in WEEKDAY_NAMES:
            raise ValueError(f"无效的星期名称: {self.params['first']}")
        self.first = WEEKDAY_NAMES[first_lower]
        
        # 解析结束星期
        last_val = self.params.get("last")
        if last_val:
            last_lower = last_val.lower()
            if last_lower not in WEEKDAY_NAMES:
                raise ValueError(f"无效的星期名称: {last_val}")
            self.last = WEEKDAY_NAMES[last_lower]
        else:
            self.last = self.first
        
        # 生成有效值范围
        min_wd, max_wd = min(self.first, self.last), max(self.first, self.last)
        self.values = list(range(min_wd, max_wd + 1))
        logger.debug(f"周范围解析: {self.expression} -> {self.values}")
    
    def get_next_value(self, date: datetime, field):
        """获取下一个匹配值"""
        current_wd = date.weekday()
        
        # 查找值范围内的下一个工作日
        for wd in self.values:
            # 确保处理循环（周日之后是周一）
            if wd < current_wd:
                wd += 7
            
            if wd >= current_wd:
                return wd % 7  # 保证在0-6范围内
        
        return self.values[0] if self.values else None


class WeekdayPositionExpression(CronExpressionBase):
    """处理星期位置表达式"""
    pattern = re.compile(
        r"^\s*(?P<position>" + "|".join(POSITION_OPTIONS) + r")\s+(?P<weekday>[a-z]+)\s*$", 
        re.IGNORECASE
    )
    
    def __init__(self, expression: str, field_type: FieldType):
        super().__init__(expression, field_type)
        self.params = self.parse_params()
        
        # 解析位置参数
        position = self.params["position"].lower()
        if position not in POSITION_OPTIONS:
            raise ValueError(f"无效的位置标识: {position}")
        self.position = position
        
        # 解析星期参数
        weekday = self.params["weekday"].lower()
        if weekday not in WEEKDAY_NAMES:
            raise ValueError(f"无效的星期名称: {weekday}")
        self.weekday = WEEKDAY_NAMES[weekday]
        
        # 确定位置索引
        self.position_index = POSITION_OPTIONS.index(position)
        logger.debug(f"周位置解析: {self.position} {self.weekday}")
    
    def get_next_value(self, date: datetime, field):
        """获取下一个匹配值"""
        # 获取当月的第一天和最后一天信息
        first_weekday, days_in_month = monthrange(date.year, date.month)
        
        # 计算当月的第一个目标星期几
        # 注意：first_weekday 是一个整数（0-6，0为周一）
        first_target_day = (self.weekday - first_weekday + 7) % 7 + 1
        
        # 计算目标日期
        if self.position_index < 5:  # 1st, 2nd, 3rd, 4th, 5th
            target_day = first_target_day + self.position_index * 7
        else:  # last - 最后一周的目标星期几
            # 计算当月的最后一周的目标日
            last_week_target = days_in_month - (days_in_month - first_target_day) % 7
            target_day = last_week_target - 6  # 最后一整周
        
        # 如果目标日超出了当月天数，则使用最后一周
        if target_day > days_in_month and self.position_index < 5:
            target_day = days_in_month - (days_in_month - first_target_day) % 7
        
        # 检查目标日是否有效并在当前日之后
        if 1 <= target_day <= days_in_month and target_day >= date.day:
            return target_day
        
        return None


class LastDayOfMonthExpression(CronExpressionBase):
    """处理月份最后一天表达式"""
    pattern = re.compile(r"^\s*last\s*$", re.IGNORECASE)
    
    def get_next_value(self, date: datetime, field):
        """获取下一个匹配值"""
        # 计算当月的最后一天
        _, last_day = monthrange(date.year, date.month)
        
        # 如果当前日期小于最后一天，则返回最后一天
        if date.day < last_day:
            return last_day
        
        return None


class NthWeekdayExpression(CronExpressionBase):
    """处理第N个星期几表达式"""
    pattern = re.compile(r"^\s*(?P<weekday>\d)\s*#\s*(?P<nth>\d)\s*$")
    
    def __init__(self, expression: str, field_type: FieldType):
        super().__init__(expression, field_type)
        self.params = self.parse_params()
        
        # 解析参数
        self.nth = int(self.params["nth"])
        self.weekday = int(self.params["weekday"])
        
        # 验证参数
        if self.nth < 1 or self.nth > 5:
            raise ValueError(f"第N个值必须在1-5之间: {self.nth}")
        if self.weekday < 0 or self.weekday > 6:
            raise ValueError(f"星期值必须在0-6之间: {self.weekday}")
    
    def get_next_value(self, date: datetime, field):
        """获取下一个匹配值"""
        # 获取当月的第一天
        first_day = date.replace(day=1)
        
        # 计算当月第一个目标星期几
        # 0: Monday, 6: Sunday
        days_to_first_target = (self.weekday - first_day.weekday() + 7) % 7
        first_target = first_day + timedelta(days=days_to_first_target)
        
        # 计算第N个目标星期几
        target_day = first_target + timedelta(weeks=self.nth - 1)
        
        # 确保仍在当前月份
        if target_day.month != date.month:
            return None  # 超出月份范围
        
        # 检查是否在日期之后
        target_value = target_day.day
        if target_value < date.day:
            return None
            
        return target_value


class NearestWorkdayExpression(CronExpressionBase):
    """处理最近工作日表达式"""
    pattern = re.compile(r"^\s*(?P<day>\d+)\s*W\s*$")
    
    def __init__(self, expression: str, field_type: FieldType):
        super().__init__(expression, field_type)
        self.params = self.parse_params()
        self.day = int(self.params["day"])
        
        # 验证值范围
        min_val, max_val = FIELD_RANGES[FieldType.DAY_OF_MONTH]
        if self.day < min_val or self.day > max_val:
            raise ValueError(f"日期必须在{min_val}-{max_val}之间: {self.day}")
    
    def get_next_value(self, date: datetime, field):
        """获取最近的工作日"""
        if self.day < date.day:
            return None
            
        # 检查目标日是否为周末
        target_date = date.replace(day=self.day)
        weekday = target_date.weekday()
        
        # 检查是否为工作日（周一到周五）
        if weekday < 5:  # 0-4 = Monday-Friday
            return self.day
        
        # 处理非工作日的最近工作日
        return self._find_nearest_workday(target_date).day
    
    def _find_nearest_workday(self, date: datetime) -> datetime:
        """查找最近的工作日"""
        prev_day = date - timedelta(days=1)
        next_day = date + timedelta(days=1)
        
        # 优先检查前一天（业务规则）
        if 0 <= prev_day.weekday() < 5:
            return prev_day
        
        # 再检查后一天
        if 0 <= next_day.weekday() < 5:
            return next_day
        
        # 如果两天都不是工作日（罕见情况），返回后一天
        return next_day


# 字段范围定义
FIELD_RANGES = {
    FieldType.SECOND: (0, 59),
    FieldType.MINUTE: (0, 59),
    FieldType.HOUR: (0, 23),
    FieldType.DAY_OF_MONTH: (1, 31),
    FieldType.MONTH: (1, 12),
    FieldType.DAY_OF_WEEK: (0, 6),
    FieldType.YEAR: (1970, 9999),
}

# 表达式处理器映射
EXPRESSION_HANDLERS = {
    FieldType.SECOND: [AllExpression, RangeExpression],
    FieldType.MINUTE: [AllExpression, RangeExpression],
    FieldType.HOUR: [AllExpression, RangeExpression],
    FieldType.DAY_OF_MONTH: [
        AllExpression, RangeExpression, 
        WeekdayPositionExpression, 
        LastDayOfMonthExpression,
        NearestWorkdayExpression
    ],
    FieldType.MONTH: [AllExpression, RangeExpression],
    FieldType.DAY_OF_WEEK: [
        AllExpression, RangeExpression, 
        WeekdayRangeExpression, 
        NthWeekdayExpression
    ],
    FieldType.YEAR: [AllExpression, RangeExpression],
}


class CronField:
    """Cron表达式字段处理器"""
    __slots__ = ('field_type', 'expression', 'handler', 
                 'is_default', 'cache', 'cache_hits')
    
    def __init__(self, field_type: FieldType, expression: str, is_default: bool = False):
        self.field_type = field_type
        self.expression = expression.strip()
        self.is_default = is_default
        self.cache = {}
        self.cache_hits = 0
        self.handler = self._compile_expression()
        logger.debug(f"编译 {field_type.name} 字段: {expression} -> {self.handler}")
    
    def _compile_expression(self) -> CronExpressionBase:
        """编译Cron表达式"""
        # 尝试所有支持的处理器
        for handler_class in EXPRESSION_HANDLERS.get(self.field_type, []):
            try:
                handler = handler_class(self.expression, self.field_type)
                handler.validate()
                return handler
            except Exception as e:
                logger.debug(f"{handler_class.__name__} 编译失败: {e}")
                continue
        
        # 没有匹配的处理器
        raise ValueError(
            f"不支持的表达式类型 '{self.expression}' for field {self.field_type.name}"
        )
    
    def get_min(self, date: datetime) -> int:
        """获取字段的最小值"""
        if self.field_type == FieldType.DAY_OF_MONTH:
            _, last_day = monthrange(date.year, date.month)
            return 1
        return FIELD_RANGES[self.field_type][0]
    
    def get_max(self, date: datetime) -> int:
        """获取字段的最大值"""
        if self.field_type == FieldType.DAY_OF_MONTH:
            _, last_day = monthrange(date.year, date.month)
            return last_day
        return FIELD_RANGES[self.field_type][1]
    
    def get_value(self, date: datetime) -> int:
        """获取给定日期的字段值"""
        if self.field_type == FieldType.SECOND:
            return date.second
        elif self.field_type == FieldType.MINUTE:
            return date.minute
        elif self.field_type == FieldType.HOUR:
            return date.hour
        elif self.field_type == FieldType.DAY_OF_MONTH:
            return date.day
        elif self.field_type == FieldType.MONTH:
            return date.month
        elif self.field_type == FieldType.DAY_OF_WEEK:
            return date.weekday()  # Monday=0, Sunday=6
        elif self.field_type == FieldType.YEAR:
            return date.year
        return 0
    
    def get_next_value(self, date: datetime) -> Optional[int]:
        """
        获取字段的下一个有效值
        
        参数:
            date: 当前日期时间
            
        返回:
            下一个有效值（如果存在），否则返回None
        """
        # 使用缓存优化性能
        cache_key = (date.year, date.month, date.day, self.get_value(date))
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        # 计算下一个值
        next_val = self.handler.get_next_value(date, self)
        self.cache[cache_key] = next_val
        return next_val
    
    def __str__(self) -> str:
        return f"{self.field_type.name}: {self.expression}"
    
    def __repr__(self) -> str:
        return f"<CronField type={self.field_type.name} expr={self.expression}>"


class CronParser:
    """完整的Cron表达式解析器"""
    FIELD_ORDER = [
        FieldType.SECOND,
        FieldType.MINUTE,
        FieldType.HOUR,
        FieldType.DAY_OF_MONTH,
        FieldType.MONTH,
        FieldType.DAY_OF_WEEK,
        FieldType.YEAR,
    ]
    
    def __init__(self, cron_str: str):
        self.original_str = cron_str
        self.fields = {}
        self.parse(cron_str)
    
    def parse(self, cron_str: str):
        """解析Cron表达式字符串"""
        parts = cron_str.split()
        
        # 处理不同长度的Cron表达式
        field_count = len(parts)
        if field_count < 5 or field_count > 7:
            raise ValueError(
                f"无效的Cron表达式长度: {field_count}部分 (需要5-7个字段)"
            )
        
        # 为缺失的字段添加默认值
        final_parts = []
        missing_count = 7 - field_count
        
        for i, field_type in enumerate(self.FIELD_ORDER):
            if i < field_count:
                final_parts.append(parts[i])
            else:
                # 对于缺失的字段使用默认值
                if field_type == FieldType.YEAR:
                    final_parts.append("*")
                elif field_type == FieldType.SECOND:
                    final_parts.append("0")
                else:
                    final_parts.append("*")
        
        # 创建字段处理器
        for i, field_type in enumerate(self.FIELD_ORDER):
            self.fields[field_type] = CronField(
                field_type,
                final_parts[i],
                is_default=(i >= field_count)
            )
    
    def get_next(self, start_date: datetime) -> Optional[datetime]:
        """获取下一个触发时间"""
        # 增加1秒以避免包含当前秒
        current = start_date + timedelta(seconds=1)
        
        # 最大迭代次数（防止无限循环）
        max_iterations = 1000
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            next_time = self._find_next_date(current)
            
            if next_time is not None:
                return next_time
            
            # 下个月重新开始
            current = self._next_month(current)
        
        return None  # 在可接受迭代次数内未找到
    
    def _find_next_date(self, start: datetime) -> Optional[datetime]:
        """
        尝试从指定时间开始找下一个满足条件的日期时间
        
        参数:
            start: 开始查找的时间点
            
        返回:
            找到的时间点，如果找不到则返回None
        """
        candidate = start.replace(
            microsecond=0, 
            tzinfo=start.tzinfo  # 保持时区信息
        )
        
        # 调整年份
        year_valid = self._adjust_field(FieldType.YEAR, candidate)
        if year_valid is None:
            return None
        
        # 调整月份
        month_valid = self._adjust_field(FieldType.MONTH, year_valid)
        if month_valid is None:
            return None
        
        # 调整日期
        day_valid = self._adjust_field(FieldType.DAY_OF_MONTH, month_valid)
        if day_valid is None:
            return None
        
        # 调整周几
        weekday_valid = self._adjust_field(FieldType.DAY_OF_WEEK, day_valid)
        if weekday_valid is None:
            return None
        
        # 调整小时
        hour_valid = self._adjust_field(FieldType.HOUR, weekday_valid)
        if hour_valid is None:
            return None
        
        # 调整分钟
        minute_valid = self._adjust_field(FieldType.MINUTE, hour_valid)
        if minute_valid is None:
            return None
        
        # 调整秒
        second_valid = self._adjust_field(FieldType.SECOND, minute_valid)
        if second_valid is None:
            return None
        
        return second_valid
    
    def _adjust_field(self, field_type: FieldType, candidate: datetime) -> Optional[datetime]:
        """调整特定字段的值"""
        field = self.fields[field_type]
        current_value = field.get_value(candidate)
        
        # 获取下一个有效值
        next_value = field.get_next_value(candidate)
        
        if next_value is None:
            return None  # 没有满足条件的值
        
        if next_value == current_value:
            return candidate  # 值已满足，无需调整
        
        # 创建新的datetime对象（需要重置后续字段）
        new_candidate = self._create_datetime(field_type, candidate, next_value)
        
        # 递归处理以确保所有字段有效
        if field_type in [FieldType.YEAR, FieldType.MONTH, FieldType.DAY_OF_MONTH]:
            return self._find_next_date(new_candidate)
        
        return new_candidate
    
    def _create_datetime(self, field_type: FieldType, base: datetime, value: int) -> datetime:
        """根据字段类型创建新的datetime对象"""
        if field_type == FieldType.YEAR:
            return base.replace(year=value, month=1, day=1, hour=0, minute=0, second=0)
        elif field_type == FieldType.MONTH:
            return base.replace(month=value, day=1, hour=0, minute=0, second=0)
        elif field_type == FieldType.DAY_OF_MONTH:
            # 确保日期在当月有效范围内
            try:
                _, days_in_month = monthrange(base.year, base.month)
                safe_day = min(value, days_in_month)
                return base.replace(day=safe_day, hour=0, minute=0, second=0)
            except ValueError:
                return base.replace(month=base.month+1, day=1, hour=0, minute=0, second=0)
        elif field_type == FieldType.HOUR:
            return base.replace(hour=value, minute=0, second=0)
        elif field_type == FieldType.MINUTE:
            return base.replace(minute=value, second=0)
        elif field_type == FieldType.SECOND:
            return base.replace(second=value)
        return base
    
    def _next_month(self, date: datetime) -> datetime:
        """到下个月的第一天"""
        next_month = date.month % 12 + 1
        next_year = date.year + (1 if date.month == 12 else 0)
        return datetime(
            year=next_year,
            month=next_month,
            day=1,
            hour=0,
            minute=0,
            second=0,
            tzinfo=date.tzinfo
        )
    
    def explain(self) -> str:
        """解释Cron表达式"""
        explanations = []
        for ft in self.FIELD_ORDER:
            field = self.fields[ft]
            min_val, max_val = FIELD_RANGES.get(ft, (0, 0))
            default_note = " (默认)" if field.is_default else ""
            
            explanation = f"{ft.name.ljust(12)}: [{field.expression}]{default_note}"
            if ft == FieldType.DAY_OF_MONTH:
                explanation += f" (范围: {min_val}-{max_val} 取决于月份)"
            elif ft != FieldType.DAY_OF_WEEK:
                explanation += f" (范围: {min_val}-{max_val})"
            
            explanations.append(explanation)
        
        return "\n".join(explanations)
    
    def __str__(self):
        return " ".join(
            self.fields[ft].expression for ft in self.FIELD_ORDER
        )


if __name__ == "__main__":
    # 示例使用
    cron_expr = "0 0 12 15W * 1#1"
    
    try:
        parser = CronParser(cron_expr)
        print(f"解析成功的Cron表达式: {cron_expr}")
        print("表达式解释:")
        print(parser.explain())
        
        start_time = datetime.now()
        print(f"\n当前时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        next_time = parser.get_next(start_time)
        if next_time:
            print(f"下一个触发时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("没有未来的触发时间")
    except Exception as e:
        print(f"解析错误: {str(e)}")
