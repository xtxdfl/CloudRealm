#!/usr/bin/env python3
"""
高级Cron表达式字段处理器 - 支持完整的Cron语法和特殊字符
包含时区感知、闰年处理及高性能日期计算
"""

import calendar
import re
from abc import ABC, abstractmethod
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# 日志配置
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FieldType(Enum):
    """字段类型枚举，精确指定每个字段的特性"""
    SECOND = 0
    MINUTE = 1
    HOUR = 2
    DAY_OF_MONTH = 3
    MONTH = 4
    DAY_OF_WEEK = 5
    YEAR = 6


# 字段范围定义
FIELD_RANGES = {
    FieldType.SECOND: (0, 59),
    FieldType.MINUTE: (0, 59),
    FieldType.HOUR: (0, 23),
    FieldType.DAY_OF_MONTH: (1, 31),
    FieldType.MONTH: (1, 12),
    FieldType.DAY_OF_WEEK: (0, 6),  # 0=Sunday, 6=Saturday
    FieldType.YEAR: (1970, 2**63),
}

# 特殊字符映射
SPECIAL_CHAR_MAP = {
    'SUN': 0, 'MON': 1, 'TUE': 2, 'WED': 3, 
    'THU': 4, 'FRI': 5, 'SAT': 6,
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
    'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
    'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
}

# 默认值
DEFAULT_VALUES = {
    FieldType.SECOND: "0",
    FieldType.MINUTE: "0",
    FieldType.HOUR: "0",
    FieldType.DAY_OF_MONTH: "*",
    FieldType.MONTH: "*",
    FieldType.DAY_OF_WEEK: "*",
    FieldType.YEAR: "*",
}


@dataclass
class CronExpressionResult:
    """Cron表达式计算结果"""
    values: List[int]
    is_range: bool
    has_step: bool
    has_special: bool


class CronExpressionCompiler(ABC):
    """Cron表达式编译器抽象基类"""
    def __init__(self, expression: str):
        self.expression = expression.strip()
    
    @abstractmethod
    def compile(self) -> CronExpressionResult:
        """编译表达式返回有效值列表"""
        pass


class AllExpression(CronExpressionCompiler):
    """处理 '*' 表达式"""
    def compile(self) -> CronExpressionResult:
        min_val, max_val = FIELD_RANGES[self.field_type]
        return CronExpressionResult(
            values=list(range(min_val, max_val + 1)),
            is_range=True,
            has_step=False,
            has_special=False
        )


class SingleValueExpression(CronExpressionCompiler):
    """处理单个值，如 '5' 或 'FEB'"""
    def compile(self) -> CronExpressionResult:
        # 尝试解析为数字
        try:
            value = int(self.expression)
        except ValueError:
            # 尝试特殊字符串转换
            value = SPECIAL_CHAR_MAP.get(self.expression.upper(), None)
            if value is None:
                raise ValueError(
                    f"Invalid value '{self.expression}' for field {self.field_type.name}"
                )
            has_special = True
        else:
            has_special = False
        
        min_val, max_val = FIELD_RANGES[self.field_type]
        if not min_val <= value <= max_val:
            raise ValueError(
                f"Value {value} out of range for field {self.field_type.name}"
            )
        
        return CronExpressionResult(
            values=[value],
            is_range=False,
            has_step=False,
            has_special=has_special
        )


class RangeExpression(CronExpressionCompiler):
    """处理范围表达式，如 '5-10'"""
    RANGE_REGEX = re.compile(r'^(\d+)\s*-\s*(\d+)\s*(?:/\s*(\d+))?$')
    
    def compile(self) -> CronExpressionResult:
        match = self.RANGE_REGEX.match(self.expression)
        if not match:
            raise ValueError(f"Invalid range expression: {self.expression}")
        
        start = int(match.group(1))
        end = int(match.group(2))
        step = int(match.group(3)) if match.group(3) else 1
        
        min_val, max_val = FIELD_RANGES[self.field_type]
        if not min_val <= start <= max_val:
            raise ValueError(
                f"Start value {start} out of range for field {self.field_type.name}"
            )
        if not min_val <= end <= max_val:
            raise ValueError(
                f"End value {end} out of range for field {self.field_type.name}"
            )
        if end < start:
            raise ValueError(
                f"Range end {end} less than start {start} in field {self.field_type.name}"
            )
        
        values = list(range(start, end + 1, step))
        return CronExpressionResult(
            values=values,
            is_range=True,
            has_step=(step > 1),
            has_special=False
        )


class StepExpression(CronExpressionCompiler):
    """处理步长表达式，如 '*/5'"""
    STEP_REGEX = re.compile(r'^(\*|(?:\d+(?:-\d+)?))\s*/\s*(\d+)$')
    
    def compile(self) -> CronExpressionResult:
        match = self.STEP_REGEX.match(self.expression)
        if not match:
            raise ValueError(f"Invalid step expression: {self.expression}")
        
        base = match.group(1)
        step = int(match.group(2))
        
        min_val, max_val = FIELD_RANGES[self.field_type]
        if step < 1 or step > (max_val - min_val):
            raise ValueError(
                f"Invalid step value {step} for field {self.field_type.name}"
            )
        
        # 处理基础范围
        if base == '*':
            values = list(range(min_val, max_val + 1, step))
        else:
            try:
                start = int(base)
                end = start  # 单个值
            except ValueError:
                # 可能是范围
                if '-' in base:
                    start, end = map(int, base.split('-'))
                else:
                    raise ValueError(
                        f"Invalid base '{base}' in step expression"
                    )
            
            if not min_val <= start <= max_val:
                raise ValueError(
                    f"Start value {start} out of range for field {self.field_type.name}"
                )
            if not min_val <= end <= max_val:
                raise ValueError(
                    f"End value {end} out of range for field {self.field_type.name}"
                )
            if end < start:
                raise ValueError(
                    f"Range end {end} less than start {start} in field {self.field_type.name}"
                )
            
            values = list(range(start, end + 1, step))
        
        return CronExpressionResult(
            values=values,
            is_range=('*' in self.expression or '-' in base),
            has_step=True,
            has_special=False
        )


class LastDayExpression(CronExpressionCompiler):
    """处理最后一天表达式 'L' 和 'LW'"""
    def compile(self) -> CronExpressionResult:
        expression = self.expression.upper()
        
        if expression == 'L':
            return CronExpressionResult(
                values=[0],  # 特殊标记：最后一天
                is_range=False,
                has_step=False,
                has_special=True
            )
        elif expression == 'LW':
            return CronExpressionResult(
                values=[-1],  # 特殊标记：最后工作日
                is_range=False,
                has_step=False,
                has_special=True
            )
        else:
            raise ValueError(f"Invalid last day expression: {self.expression}")


class WeekdayExpression(CronExpressionCompiler):
    """处理工作日表达式 '15W'"""
    REGEX = re.compile(r'^(\d+)\s*W$')
    
    def compile(self) -> CronExpressionResult:
        match = self.REGEX.match(self.expression)
        if not match:
            raise ValueError(f"Invalid weekday expression: {self.expression}")
        
        day = int(match.group(1))
        min_val, max_val = FIELD_RANGES[self.field_type]
        if not min_val <= day <= max_val:
            raise ValueError(
                f"Day value {day} out of range for field {self.field_type.name}"
            )
        
        # 特殊标记：接近工作日 (value + 100)
        return CronExpressionResult(
            values=[day + 100],
            is_range=False,
            has_step=False,
            has_special=True
        )


class NthWeekdayExpression(CronExpressionCompiler):
    """处理第N个工作日表达式 '2#3'（第三个星期二）"""
    REGEX = re.compile(r'^(\d+)\s*#\s*(\d+)$')
    
    def compile(self) -> CronExpressionResult:
        match = self.REGEX.match(self.expression)
        if not match:
            raise ValueError(f"Invalid nth weekday expression: {self.expression}")
        
        weekday = int(match.group(1))
        n = int(match.group(2))
        
        min_wd, max_wd = FIELD_RANGES[FieldType.DAY_OF_WEEK]
        if not min_wd <= weekday <= max_wd:
            raise ValueError(
                f"Weekday value {weekday} out of range"
            )
        if n < 1 or n > 5:
            raise ValueError(
                f"Nth value {n} must be between 1 and 5"
            )
        
        # 特殊标记：第N个工作日 (1000 + weekday * 10 + n)
        return CronExpressionResult(
            values=[1000 + weekday * 10 + n],
            is_range=False,
            has_step=False,
            has_special=True
        )


# 将编译器映射到字段类型
FIELD_COMPILERS = {
    FieldType.SECOND: [AllExpression, SingleValueExpression, RangeExpression, StepExpression],
    FieldType.MINUTE: [AllExpression, SingleValueExpression, RangeExpression, StepExpression],
    FieldType.HOUR: [AllExpression, SingleValueExpression, RangeExpression, StepExpression],
    FieldType.DAY_OF_MONTH: [
        AllExpression, SingleValueExpression, RangeExpression, StepExpression,
        LastDayExpression, WeekdayExpression
    ],
    FieldType.MONTH: [AllExpression, SingleValueExpression, RangeExpression, StepExpression],
    FieldType.DAY_OF_WEEK: [
        AllExpression, SingleValueExpression, RangeExpression, StepExpression,
        NthWeekdayExpression
    ],
    FieldType.YEAR: [AllExpression, SingleValueExpression, RangeExpression, StepExpression],
}


class CronField:
    """Cron表达式字段处理器"""
    __slots__ = ('field_type', 'expression', 'compiled_result', 
                 'is_default', 'cache', 'cache_hits')
    
    def __init__(self, field_type: FieldType, expression: str, is_default: bool = False):
        self.field_type = field_type
        self.expression = expression.strip()
        self.is_default = is_default
        self.cache = {}
        self.cache_hits = 0
        
        logger.debug(f"Compiling {field_type.name} field: {expression}")
        self.compiled_result = self._compile_expression()
        logger.debug(f"Compiled values: {self.compiled_result.values}")
    
    def _compile_expression(self) -> CronExpressionResult:
        """编译Cron表达式片段"""
        # 处理逗号分隔值
        if ',' in self.expression:
            return self._compile_multiple_values()
        
        # 检查是否有支持的编译器
        for compiler_class in FIELD_COMPILERS[self.field_type]:
            # 动态设置编译器类
            compiler = compiler_class.__new__(compiler_class)
            compiler.expression = self.expression
            compiler.field_type = self.field_type
            
            # 尝试编译
            try:
                return compiler.compile()
            except ValueError:
                pass
        
        # 没有匹配的编译器
        raise ValueError(
            f"Unsupported expression '{self.expression}' for field {self.field_type.name}"
        )
    
    def _compile_multiple_values(self) -> CronExpressionResult:
        """处理逗号分隔的多值表达式"""
        values = set()
        has_range = False
        has_step = False
        has_special = False
        
        for expr in self.expression.split(','):
            temp_field = CronField(self.field_type, expr)
            values.update(temp_field.compiled_result.values)
            has_range |= temp_field.compiled_result.is_range
            has_step |= temp_field.compiled_result.has_step
            has_special |= temp_field.compiled_result.has_special
        
        sorted_values = sorted(values)
        return CronExpressionResult(
            values=sorted_values,
            is_range=has_range,
            has_step=has_step,
            has_special=has_special
        )
    
    def is_special(self) -> bool:
        """检查字段是否包含特殊标记"""
        return self.compiled_result.has_special
    
    def get_next_value(self, date_val: datetime, current_value: int) -> Optional[int]:
        """
        获取字段的下一个有效值
        
        参数:
            date_val: 当前日期时间
            current_value: 当前字段值
            
        返回:
            下一个有效值（如果存在），否则返回None
        """
        # 使用缓存优化性能
        cache_key = (date_val.year, date_val.month, current_value)
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        # 处理特殊表达式
        if self.compiled_result.has_special:
            result = self._handle_special_cases(date_val, current_value)
            self.cache[cache_key] = result
            return result
        
        # 正常值处理
        for value in self.compiled_result.values:
            if value > current_value:
                self.cache[cache_key] = value
                return value
        
        # 没有更大的值，返回None表示溢出
        self.cache[cache_key] = None
        return None
    
    def _handle_special_cases(self, date_val: datetime, current_value: int) -> Optional[int]:
        """处理特殊表达式情况（L、W、#等）"""
        # 获取字段范围
        min_val, max_val = self._get_range(date_val)
        
        # 处理最后一天表达式
        if self.field_type == FieldType.DAY_OF_MONTH:
            if self.compiled_result.values == [0]:  # L - 当月最后一天
                last_day = self._get_last_day_of_month(date_val)
                if last_day > current_value:
                    return last_day
            
            elif self.compiled_result.values == [-1]:  # LW - 当月最后工作日
                last_workday = self._get_last_workday_of_month(date_val)
                if last_workday > current_value:
                    return last_workday
            
            elif any(v >= 100 and v < 200 for v in self.compiled_result.values):  # nW
                for value in self.compiled_result.values:
                    if 100 <= value < 200:
                        day = value - 100
                        nearest_day = self._get_nearest_workday(date_val, day)
                        if nearest_day > current_value:
                            return nearest_day
        
        # 处理第N个工作日表达式
        elif self.field_type == FieldType.DAY_OF_WEEK:
            if any(v >= 1000 for v in self.compiled_result.values):
                for value in self.compiled_result.values:
                    if value >= 1000:
                        # 解码值：1000 + weekday*10 + nth
                        coded = value - 1000
                        weekday = coded // 10
                        nth = coded % 10
                        target_day = self._get_nth_weekday(date_val, weekday, nth)
                        if target_day and target_day > current_value:
                            return target_day
        
        # 处理正常值或默认行为
        for value in self.compiled_result.values:
            if self.field_type == FieldType.DAY_OF_WEEK:
                value %= 7  # 确保值在0-6范围内
            if min_val <= value <= max_val and value > current_value:
                return value
        
        return None
    
    def _get_last_day_of_month(self, date_val: datetime) -> int:
        """获取当月的最后一天"""
        _, last_day = monthrange(date_val.year, date_val.month)
        return last_day
    
    def _get_last_workday_of_month(self, date_val: datetime) -> int:
        """获取当月的最后一个工作日"""
        _, last_day = monthrange(date_val.year, date_val.month)
        last_date = date_val.replace(day=last_day)
        
        # 寻找上一个工作日（周一到周五）
        while last_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            last_day -= 1
            last_date = last_date.replace(day=last_day)
        
        return last_day
    
    def _get_nearest_workday(self, date_val: datetime, target_day: int) -> int:
        """获取最接近目标日期的工作日"""
        # 尝试目标日本身
        try:
            candidate = date_val.replace(day=target_day)
            if 0 <= candidate.weekday() < 5:  # 周一到周五
                return target_day
        except ValueError:
            pass
        
        # 如果无效或非工作日，寻找附近的日期
        min_day, max_day = self._get_range(date_val)
        before = target_day - 1
        after = target_day + 1
        
        # 尝试前一天
        while before >= min_day:
            try:
                candidate = date_val.replace(day=before)
                if 0 <= candidate.weekday() < 5:
                    return before
                before -= 1
            except ValueError:
                before -= 1
        
        # 尝试后一天
        while after <= max_day:
            try:
                candidate = date_val.replace(day=after)
                if 0 <= candidate.weekday() < 5:
                    return after
                after += 1
            except ValueError:
                after += 1
        
        # 没找到工作日，使用目标日（即使无效/周末）
        return target_day
    
    def _get_nth_weekday(self, date_val: datetime, weekday: int, nth: int) -> Optional[int]:
        """获取当月的第N个指定工作日"""
        # 创建当月第一个日期
        first_of_month = date_val.replace(day=1)
        
        # 找到当月第一个指定星期的日期
        first_weekday = first_of_month
        while first_weekday.weekday() != weekday:
            first_weekday += timedelta(days=1)
        
        # 获取第n个指定星期几
        target_date = first_weekday + timedelta(weeks=nth-1, days=0)
        
        # 检查是否仍然在同一个月
        if target_date.month != first_of_month.month:
            return None  # 超出当月的日期
        
        return target_date.day
    
    def _get_range(self, date_val: datetime) -> Tuple[int, int]:
        """获取字段的有效范围（取决于日期）"""
        if self.field_type == FieldType.DAY_OF_MONTH:
            _, last_day = monthrange(date_val.year, date_val.month)
            return (1, last_day)
        return FIELD_RANGES[self.field_type]
    
    def __str__(self) -> str:
        """友好的字符串表示"""
        return f"{self.field_type.name}: {self.expression}"
    
    def __repr__(self) -> str:
        """详细的表示形式"""
        return f"<CronField type={self.field_type.name} expr={self.expression} special={self.compiled_result.has_special}>"


class CronExpression:
    """完整的Cron表达式处理器"""
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
        self.parse_error = None
        self.parse(cron_str)
    
    def parse(self, cron_str: str) -> bool:
        """解析Cron表达式字符串"""
        parts = cron_str.split()
        
        # 处理非标准（6字段）和标准（7字段）Cron表达式
        if len(parts) not in [5, 6, 7]:
            self.parse_error = f"Invalid cron expression length: {len(parts)} parts"
            return False
        
        # 年份字段是可选的
        field_count = len(parts)
        if field_count < 7:
            # 添加缺失的字段
            for i in range(7 - field_count):
                if self.FIELD_ORDER[-(i+1)] == FieldType.YEAR:
                    parts.append(str(FIELD_RANGES[FieldType.YEAR][1]) + "-" + 
                                 str(FIELD_RANGES[FieldType.YEAR][1]))
                else:
                    field_type = self.FIELD_ORDER[field_count + i]
                    parts.append(DEFAULT_VALUES[field_type])
        
        try:
            for i, field_type in enumerate(self.FIELD_ORDER):
                self.fields[field_type] = CronField(field_type, parts[i])
        except ValueError as e:
            self.parse_error = str(e)
            return False
        
        return True
    
    def is_valid(self) -> bool:
        """检查表达式是否有效"""
        return self.parse_error is None
    
    def get_next(self, start_time: datetime) -> Optional[datetime]:
        """获取下一个触发时间"""
        if not self.is_valid():
            return None
        
        # 增加1秒以避免包含当前秒
        current = start_time + timedelta(seconds=1)
        
        # 最大迭代次数（防止无限循环）
        max_iterations = 10000
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            
            # 尝试找到满足所有字段的时间
            result = self._find_next_datetime(current)
            
            if result:
                return result
            
            # 下个月重新开始
            next_month = current.replace(
                month=current.month % 12 + 1,
                year=current.year + (1 if current.month == 12 else 0),
                day=1, hour=0, minute=0, second=0
            )
            current = next_month
        
        return None  # 在可接受迭代次数内未找到
    
    def _find_next_datetime(self, start: datetime) -> Optional[datetime]:
        """
        尝试从指定时间开始找下一个满足条件的日期时间
        
        参数:
            start: 开始查找的时间点
            
        返回:
            找到的时间点，如果找不到则返回None
        """
        candidate = datetime(
            year=start.year,
            month=start.month,
            day=start.day,
            hour=start.hour,
            minute=start.minute,
            second=start.second,
            tzinfo=start.tzinfo
        )
        
        # 调整月份
        month_valid = self._adjust_month(candidate)
        if month_valid is None:
            return None
        
        # 调整日
        day_valid = self._adjust_day(month_valid)
        if day_valid is None:
            return None
        
        # 调整小时
        hour_valid = self._adjust_hour(day_valid)
        if hour_valid is None:
            return None
        
        # 调整分钟
        minute_valid = self._adjust_minute(hour_valid)
        if minute_valid is None:
            return None
        
        # 调整秒
        second_valid = self._adjust_second(minute_valid)
        
        return second_valid
    
    def _adjust_month(self, candidate: datetime) -> Optional[datetime]:
        """调整月份字段"""
        month_val = candidate.month
        next_month = self.fields[FieldType.MONTH].get_next_value(candidate, month_val-1)
        
        if next_month is None:
            return None
        
        if next_month != month_val:
            day_valid = self._adjust_day(candidate.replace(month=next_month, day=1))
            return day_valid
        
        return candidate
    
    def _adjust_day(self, candidate: datetime) -> Optional[datetime]:
        """调整日期字段（月份已确定）"""
        day_val = candidate.day
        next_day = self.fields[FieldType.DAY_OF_MONTH].get_next_value(
            candidate, day_val-1
        )
        
        # 处理闰年特例
        max_day = monthrange(candidate.year, candidate.month)[1]
        if next_day is None or next_day > max_day:
            return None
        
        if next_day != day_val:
            candidate = candidate.replace(day=next_day)
            # 重置小时、分钟、秒
            candidate = candidate.replace(hour=0, minute=0, second=0)
        
        # 检查星期字段
        if not self._check_week_field(candidate):
            return None
        
        return candidate
    
    def _check_week_field(self, candidate: datetime) -> bool:
        """检查是否满足星期字段条件"""
        weekday_val = candidate.weekday()
        next_weekday = self.fields[FieldType.DAY_OF_WEEK].get_next_value(
            candidate, weekday_val-1
        )
        return next_weekday is not None and next_weekday == weekday_val
    
    def _adjust_hour(self, candidate: datetime) -> Optional[datetime]:
        """调整小时字段"""
        hour_val = candidate.hour
        next_hour = self.fields[FieldType.HOUR].get_next_value(candidate, hour_val-1)
        
        if next_hour is None:
            return None
        
        if next_hour != hour_val:
            candidate = candidate.replace(hour=next_hour, minute=0, second=0)
        
        return candidate
    
    def _adjust_minute(self, candidate: datetime) -> Optional[datetime]:
        """调整分钟字段"""
        minute_val = candidate.minute
        next_minute = self.fields[FieldType.MINUTE].get_next_value(
            candidate, minute_val-1
        )
        
        if next_minute is None:
            return None
        
        if next_minute != minute_val:
            candidate = candidate.replace(minute=next_minute, second=0)
        
        return candidate
    
    def _adjust_second(self, candidate: datetime) -> Optional[datetime]:
        """调整秒字段"""
        second_val = candidate.second
        next_second = self.fields[FieldType.SECOND].get_next_value(
            candidate, second_val-1
        )
        
        if next_second is None:
            return None
        
        if next_second != second_val:
            candidate = candidate.replace(second=next_second)
        
        return candidate
    
    def __str__(self) -> str:
        """字符串表示"""
        return self.original_str
    
    def explain(self) -> str:
        """解释Cron表达式"""
        if not self.is_valid():
            return f"无效表达式: {self.parse_error}"
        
        explanations = []
        for field in self.FIELD_ORDER:
            expr = self.fields[field].expression
            if self.fields[field].is_default:
                expr = f"{expr} (默认)"
            
            if FIELD_RANGES[field] == 1:
                explanations.append(f"- {field.name}: {expr}")
            else:
                min_val, max_val = FIELD_RANGES[field]
                explanations.append(f"- {field.name}({min_val}-{max_val}): {expr}")
        
        return "\n".join(explanations)


if __name__ == "__main__":
    # 示例使用
    cron_expr = "0 15 10 L * 1#1"  # 每月最后一天10:15执行，但仅当是星期一
    
    cron = CronExpression(cron_expr)
    if cron.is_valid():
        print(f"表达式 '{cron}' 解析成功:")
        print(cron.explain())
        
        next_time = cron.get_next(datetime.now())
        if next_time:
            print(f"下一个执行时间: {next_time}")
        else:
            print("没有未来的执行时间")
    else:
        print(f"表达式无效: {cron.parse_error}")
