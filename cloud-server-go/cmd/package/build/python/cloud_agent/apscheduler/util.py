#!/usr/bin/env python3
"""
通用实用工具模块 - 包含多种类型转换和辅助函数。
主要提供以下功能：
- 类型安全转换（整数、布尔值）
- 日期时间处理（转换、计算、取整）
- 配置选项合并
- 可调用对象名称处理
- 对象与引用互转
- Python版本兼容性处理
"""

__all__ = (
    "as_int",
    "as_bool",
    "to_datetime",
    "timedelta_to_seconds",
    "datetime_difference",
    "datetime_ceil",
    "merge_config",
    "get_callable_name",
    "obj_reference",
    "ref_object",
    "as_reference",
    "to_unicode",
    "items_view",
    "values_view",
    "range_x",
)

import re
import sys
from datetime import date, datetime, timedelta
from time import mktime
from typing import Any, Callable, Dict, Iterable, Tuple, Union, Optional

# Python版本兼容设置
PY3 = sys.version_info >= (3, 0)

if PY3:
    unicode_type = str
    range_x = range
    items_view = lambda d: d.items()
    values_view = lambda d: d.values()
else:
    unicode_type = unicode
    range_x = xrange
    items_view = lambda d: d.iteritems()
    values_view = lambda d: d.itervalues()

# 日期解析正则
DATE_REGEX = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"
    r"(?:[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
    r"(?::(?P<second>\d{1,2})(?:\.(?P<micro>\d{1,6}))?)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?$"
)

# 布尔值识别
TRUE_VALUES = {"true", "yes", "on", "y", "t", "1"}
FALSE_VALUES = {"false", "no", "off", "n", "f", "0"}

def as_int(value: Any) -> Optional[int]:
    """
    安全地将任何值转换为整数，如果输入为 None 则返回 None。
    
    参数:
        value: 需要转换的值
        
    返回:
        转换后的整数结果或 None
        
    示例:
        >>> as_int("42")
        42
        >>> as_int(None) is None
        True
        >>> as_int("invalid")
        ValueError
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"无法转换为整数: {value!r}") from e


def as_bool(value: Union[str, bool, Any]) -> bool:
    """
    将值解释为布尔值，支持多种字符串表示。
    
    参数:
        value: 需要转换的值
        
    返回:
        转换后的布尔值
        
    示例:
        >>> as_bool("yes")
        True
        >>> as_bool("off")
        False
        >>> as_bool([])
        False
        >>> as_bool(42)
        True
    """
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in TRUE_VALUES:
            return True
        if normalized in FALSE_VALUES:
            return False
        raise ValueError(f'无法识别为布尔值: "{value}"')
    return bool(value)


def to_datetime(value: Union[datetime, date, str]) -> datetime:
    """
    将输入转换为 datetime 对象。
    
    支持格式:
    - 完整日期时间: "2023-08-15 14:30:45" 或 "2023-08-15T14:30:45"
    - 含微秒: "2023-08-15 14:30:45.123456"
    - 日期: "2023-08-15"
    
    参数:
        value: 日期时间对象、日期对象或字符串
        
    返回:
        转换后的 datetime 对象
        
    示例:
        >>> to_datetime("2023-08-15")
        datetime(2023, 8, 15, 0, 0)
        >>> to_datetime(datetime(2023, 8, 15))
        datetime(2023, 8, 15)
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        raise TypeError(f"不支持的类型: {type(value)}")
    
    # 尝试匹配 ISO 8601 格式
    match = DATE_REGEX.match(value)
    if not match:
        raise ValueError(f"无效的日期格式: {value!r}")
    
    # 提取并转换日期部分
    groups = match.groupdict()
    parts = {k: int(v) if v is not None else 0 for k, v in groups.items()}
    
    # 处理微秒部分（最多6位）
    if "micro" in groups and groups["micro"]:
        # 确保微秒位数正确（最多6位）
        microsecond = groups["micro"].ljust(6, '0')[:6]
        parts['microsecond'] = int(microsecond)
    
    return datetime(**parts)


def timedelta_to_seconds(delta: timedelta) -> float:
    """
    将 timedelta 对象转换为总秒数（浮点型）。
    
    参数:
        delta: 时间间隔对象
        
    返回:
        时间间隔的总秒数
        
    示例:
        >>> timedelta_to_seconds(timedelta(minutes=1))
        60.0
    """
    return delta.total_seconds()


def datetime_difference(later: datetime, earlier: datetime) -> float:
    """
    计算两个日期时间之间的差值（单位：秒）。
    
    参数:
        later: 较晚的日期时间
        earlier: 较早的日期时间
        
    返回:
        两个日期时间的差值（later - earlier）
        
    示例:
        >>> dt1 = datetime(2023, 1, 1, 12, 0)
        >>> dt2 = datetime(2023, 1, 1, 12, 1)
        >>> datetime_difference(dt2, dt1)
        60.0
    """
    return (later - earlier).total_seconds()


def datetime_ceil(dt: datetime) -> datetime:
    """
    将 datetime 对象向上取整到最近的秒。
    
    参数:
        dt: 日期时间对象
        
    返回:
        向上取整后的日期时间对象
        
    示例:
        >>> datetime_ceil(datetime(2023,1,1,12,30,15,500000))
        datetime(2023,1,1,12,30,16)
    """
    if dt.microsecond > 0:
        return dt + timedelta(
            seconds=1, 
            microseconds=-dt.microsecond
        )
    return dt


def merge_config(global_config: Dict, prefix: str, 
                local_config: Optional[Dict] = None) -> Dict:
    """
    合并全局配置（带有指定前缀）和本地配置。
    
    参数:
        global_config: 全局配置字典
        prefix: 键名前缀
        local_config: 本地配置字典（可选）
        
    返回:
        合并后的配置字典
        
    示例:
        >>> global_conf = {'app.host': 'localhost', 'app.port': 8080}
        >>> merge_config(global_conf, 'app.', {'debug': True})
        {'host': 'localhost', 'port': 8080, 'debug': True}
    """
    prefix_len = len(prefix)
    merged = {}
    
    # 复制所有带有指定前缀的全局配置
    for key, value in global_config.items():
        if key.startswith(prefix):
            merged[key[prefix_len:]] = value
    
    # 合并本地配置
    if local_config:
        merged.update(local_config)
    
    return merged


def get_callable_name(func: Callable) -> str:
    """
    获取可调用对象的最佳显示名称。
    
    参数:
        func: 可调用对象（函数、方法、类等）
        
    返回:
        可调用对象的名称
    
    示例:
        >>> get_callable_name(lambda x: x)
        '<lambda>'
        >>> class MyClass:
        ...     def my_method(self): pass
        ...
        >>> get_callable_name(MyClass.my_method)
        'MyClass.my_method'
    """
    # 尝试获取方法所属对象
    bound_to = getattr(func, "__self__", None) or getattr(func, "im_self", None)
    
    # 处理绑定方法或类方法
    if bound_to and hasattr(func, "__name__"):
        if isinstance(bound_to, type):
            cls_name = getattr(bound_to, "__qualname__", bound_to.__name__)
            return f"{cls_name}.{func.__name__}"
        return f"{bound_to.__class__.__name__}.{func.__name__}"
    
    # 处理其他可调用对象
    if callable(func):
        # 尝试获取函数名
        if hasattr(func, "__name__"):
            return func.__name__
        # 处理实现了 __call__ 的类实例
        return func.__class__.__name__
    
    # 处理特殊情况
    name_attr = getattr(func, "__name__", None) or getattr(func.__class__, "__name__", None)
    if name_attr:
        return name_attr
    
    raise TypeError(f"无法确定名称: {func!r}")


def obj_reference(obj: Any) -> str:
    """
    生成对象的引用路径。
    
    参数:
        obj: 需要生成引用的对象
        
    返回:
        对象的引用路径字符串
        
    示例:
        >>> obj_reference(datetime.now)
        'datetime:now'
    """
    # 获取模块名和对象名
    module_name = obj.__module__
    obj_name = get_callable_name(obj)
    
    # 验证引用有效性
    ref = f"{module_name}:{obj_name}"
    try:
        restored = ref_object(ref)
        # 验证恢复的对象是否等价
        if obj != restored:
            raise ValueError("引用恢复的对象不一致")
    except Exception as e:
        raise ValueError(f"无效的对象引用: {obj!r}") from e
    
    return ref


def ref_object(reference: str) -> Any:
    """
    根据引用路径获取原始对象。
    
    参数:
        reference: 对象引用字符串
        
    返回:
        引用对应的对象
        
    示例:
        >>> ref_object('datetime:datetime')
        <class 'datetime.datetime'>
    """
    # 参数检查
    if not isinstance(reference, str):
        raise TypeError("引用必须是字符串")
    if ":" not in reference:
        raise ValueError(f"无效的引用格式: {reference!r}。应有'模块:对象'格式。")
    
    # 拆分为模块和对象路径
    module_name, obj_path = reference.split(":", 1)
    if not module_name or not obj_path:
        raise ValueError(f"无效的引用: {reference!r}")
    
    try:
        # 导入模块
        module = __import__(module_name, fromlist=["*"])
        
        # 递归获取对象
        current = module
        for part in obj_path.split("."):
            if not hasattr(current, part):
                raise AttributeError(f"模块中缺少对象: {part}")
            current = getattr(current, part)
        
        return current
    except ImportError as e:
        raise ImportError(f"无法导入模块 {module_name}: {e}") from e
    except AttributeError as e:
        raise AttributeError(f"引用路径中找不到对象: {reference}") from e


def as_reference(obj: Any) -> Any:
    """
    将引用转换为对象（如果是字符串引用），否则原样返回对象。
    
    参数:
        obj: 原始对象或引用字符串
        
    返回:
        对象本身或其引用的对象
        
    示例:
        >>> as_reference('datetime:datetime')
        <class 'datetime.datetime'>
        >>> as_reference(42)
        42
    """
    if isinstance(obj, str):
        try:
            return ref_object(obj)
        except Exception as e:
            # 如果无法解析为引用，则原样返回字符串
            return obj
    return obj


def to_unicode(value: Any, encoding: str = "utf-8") -> unicode_type:
    """
    安全地将输入转换为 unicode（Python2）或 str（Python3）。
    
    参数:
        value: 需要转换的值
        encoding: 解码时使用的编码格式
        
    返回:
        unicode 字符串或 str
        
    示例:
        >>> to_unicode(b'hello')
        'hello'
    """
    if isinstance(value, bytes):
        return value.decode(encoding, "ignore")
    return unicode_type(value)


# ================ 兼容性函数 ================
if not PY3:
    # Python 2兼容实现
    def datetime_difference(later, earlier):
        later_ts = mktime(later.timetuple()) + later.microsecond / 1000000.0
        earlier_ts = mktime(earlier.timetuple()) + earlier.microsecond / 1000000.0
        return later_ts - earlier_ts

    # Python 2中timedelta没有total_seconds()
    def timedelta_to_seconds(delta):
        return (delta.microseconds + (delta.seconds + delta.days * 24 * 3600) * 1000000.0) / 1000000.0
