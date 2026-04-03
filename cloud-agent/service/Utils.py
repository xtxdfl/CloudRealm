#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import sys
import time
import threading
import traceback
import logging
from collections.abc import MutableMapping
from functools import wraps
from contextlib import contextmanager
from typing import Any, Dict, List, Tuple, Union, Callable, Optional, Iterator, Type

# 配置日志
logger = logging.getLogger(__name__)

# 常量定义
AGENT_AUTO_RESTART_EXIT_CODE = 77
DEFAULT_BLOCKING_TIMEOUT = 30.0  # 默认阻塞超时时间

class BlockingDictionaryTimeoutError(Exception):
    """当阻塞字典操作超时时抛出的异常"""
    pass

class BlockingDictionary:
    """
    线程安全的阻塞字典，支持阻塞式弹出操作
    
    特性和用例：
    1. 多线程环境中安全地存储和检索数据
    2. 允许消费者线程阻塞直到特定键的条目可用
    3. 适用于生产者-消费者模式的任务调度
    4. 提供带超时的阻塞操作防止永久阻塞
    
    设计原则：
    - 高并发场景下的线程安全保证
    - 最小化锁争用以提高性能
    - 清晰的异常和超时处理机制
    """
    
    def __init__(self, initial_dict: Optional[Dict] = None):
        """
        初始化阻塞字典
        
        Args:
            initial_dict: 初始字典数据
        """
        self._data = initial_dict.copy() if initial_dict else {}
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._item_events: Dict[Any, threading.Event] = {}
        
        logger.debug("BlockingDictionary 初始化完成, 初始大小: %d", len(self._data))

    def put(self, key: Any, value: Any) -> None:
        """
        向字典中添加键值对，唤醒等待该键的线程
        
        Args:
            key: 字典键
            value: 字典值
        """
        with self._lock:
            self._data[key] = value
            # 获取或创建该键的事件
            event = self._get_key_event(key)
            event.set()
            # 通知所有等待的线程
            self._condition.notify_all()
            
        logger.debug("添加键值对: key=%s, value=%s", key, type(value).__name__)

    def get(self, key: Any, default: Optional[Any] = None) -> Any:
        """
        非阻塞获取键值
        """
        with self._lock:
            return self._data.get(key, default)

    def blocking_take(self, key: Any, timeout: Optional[float] = None) -> Any:
        """
        阻塞式弹出键值对，如果没有则等待直到超时或可用
        
        Args:
            key: 要获取的键
            timeout: 超时时间（秒），None表示无限等待
            
        Returns:
            与键关联的值
            
        Raises:
            BlockingDictionaryTimeoutError: 如果在超时时间内未找到键
        """
        event = self._get_key_event(key)
        start_time = time.monotonic()
        timeout_left = timeout
        
        while True:
            with self._lock:
                if key in self._data:
                    value = self._data.pop(key)
                    # 清理事件
                    if key in self._item_events and event.is_set():
                        del self._item_events[key]
                    logger.debug("成功获取键: %s", key)
                    return value
                    
            # 如果已经超时
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                timeout_left = timeout - elapsed
                if timeout_left <= 0:
                    logger.warning("获取键超时: %s (%.2f秒)", key, timeout)
                    raise BlockingDictionaryTimeoutError(f"获取键 '{key}' 超时")
            
            # 等待事件或超时
            logger.debug("等待键可用: %s (超时剩余: %s)", key, timeout_left)
            event_occurred = event.wait(timeout_left)
            
            # 如果在等待期间超时
            if not event_occurred:
                logger.warning("获取键超时: %s (%.2f秒)", key, timeout)
                raise BlockingDictionaryTimeoutError(f"获取键 '{key}' 超时")
                
            # 重置事件以便下次使用
            event.clear()

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._data

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __repr__(self) -> str:
        with self._lock:
            return f"BlockingDictionary(size={len(self._data)}, keys={list(self._data.keys())})"

    def items(self) -> List[Tuple[Any, Any]]:
        """获取所有键值对的副本"""
        with self._lock:
            return list(self._data.items())
            
    def clear(self) -> None:
        """清空字典"""
        with self._lock:
            self._data.clear()
            # 清除所有事件
            self._item_events.clear()

    def _get_key_event(self, key: Any) -> threading.Event:
        """获取指定键的事件对象，如果不存在则创建"""
        with self._lock:
            if key not in self._item_events:
                self._item_events[key] = threading.Event()
            return self._item_events[key]


class ImmutableDictionary(MutableMapping):
    """
    不可变字典实现，禁止任何修改操作
    
    设计目的:
    1. 保证数据在传递过程中的完整性
    2. 避免意外的修改导致的数据不一致
    3. 提供深不可变的数据结构，所有嵌套对象也是不可变的
    4. 提高多线程环境中的数据安全性
    """
    
    def __init__(self, source: Dict):
        """
        从源字典创建不可变字典，递归转换所有嵌套字典
        
        Args:
            source: 要转换的字典
        """
        if not isinstance(source, dict):
            raise TypeError("source 必须是字典类型")
            
        self._data = {}
        for key, value in source.items():
            if isinstance(value, dict):
                # 递归转换嵌套字典
                self._data[key] = ImmutableDictionary(value)
            elif isinstance(value, list) or isinstance(value, tuple):
                # 转换列表和元组为不可变元组
                self._data[key] = tuple(self._make_immutable(v) for v in value)
            else:
                self._data[key] = value
                
        logger.debug("创建了不可变字典，大小: %d", len(self._data))

    def _make_immutable(self, value: Any) -> Any:
        """递归处理值使其不可变"""
        if isinstance(value, dict):
            return ImmutableDictionary(value)
        elif isinstance(value, list):
            return tuple(self._make_immutable(v) for v in value)
        else:
            return value

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __setitem__(self, key: Any, value: Any):
        """禁止修改操作"""
        self._raise_immutable_error()

    def __delitem__(self, key: Any):
        """禁止删除操作"""
        self._raise_immutable_error()

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)
        
    def __contains__(self, key: Any) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"ImmutableDictionary({self._data})"
        
    def __str__(self) -> str:
        return str(self._data)
        
    def copy_as_mutable(self) -> Dict:
        """创建可变副本"""
        return Utils.get_mutable_copy(self._data)

    @staticmethod
    def _raise_immutable_error():
        """抛出不可变错误异常"""
        raise TypeError("不可变字典: 禁止修改操作")


class Utils:
    """静态实用方法集合"""
    
    @staticmethod
    def are_dicts_equal(d1: Dict, d2: Dict, keys_to_ignore: List[Any] = None) -> bool:
        """
        深度比较两个字典是否相等，忽略指定键
        
        Args:
            d1: 第一个字典
            d2: 第二个字典
            keys_to_ignore: 忽略比较的键列表
            
        Returns:
            如果字典相等（忽略指定键）返回 True，否则返回 False
        """
        keys_to_ignore = keys_to_ignore or []
        
        # 处理一方为不可变字典的情况
        if isinstance(d1, ImmutableDictionary):
            d1 = d1.copy_as_mutable()
        if isinstance(d2, ImmutableDictionary):
            d2 = d2.copy_as_mutable()
        
        # 获取所有键的对称差集
        keys1 = set(d1.keys()) - set(keys_to_ignore)
        keys2 = set(d2.keys()) - set(keys_to_ignore)
        
        # 检查键集是否相同
        if keys1 != keys2:
            logger.debug("字典键不一致: %s vs %s", keys1, keys2)
            return False
            
        # 比较值
        for key in keys1:
            v1, v2 = d1[key], d2[key]
            
            # 递归比较嵌套字典
            if isinstance(v1, dict) and isinstance(v2, dict):
                if not Utils.are_dicts_equal(v1, v2, keys_to_ignore):
                    return False
                    
            # 比较其他类型
            elif v1 != v2:
                logger.debug("键 '%s' 的值不相等: %s vs %s", key, v1, v2)
                return False
                
        return True

    @staticmethod
    def deep_update(target: Dict, source: Dict) -> Dict:
        """
        递归更新目标字典的嵌套结构
        
        Args:
            target: 要更新的目标字典
            source: 包含更新数据的字典
            
        Returns:
            更新后的目标字典
        """
        logger.debug("深度更新字典: 源大小=%d, 目标大小=%d", len(source), len(target))
        
        for key, src_value in source.items():
            # 键存在且值是字典，则递归更新
            if key in target:
                tgt_value = target[key]
                
                if isinstance(tgt_value, dict) and isinstance(src_value, dict):
                    Utils.deep_update(tgt_value, src_value)
                    continue
                    
            # 否则直接设置值（或覆盖值）
            target[key] = src_value
                
        return target

    @staticmethod
    def make_immutable(value: Any) -> Union[ImmutableDictionary, tuple]:
        """
        递归将值转换为不可变形式
        
        Args:
            value: 要转换的值
            
        Returns:
            不可变对象
        """
        if isinstance(value, dict):
            return ImmutableDictionary(value)
        if isinstance(value, list):
            return tuple(Utils.make_immutable(v) for v in value)
        if isinstance(value, tuple):
            return tuple(Utils.make_immutable(v) for v in value)
        return value

    @staticmethod
    def get_mutable_copy(value: Any) -> Any:
        """
        创建对象的可变副本
        
        Args:
            value: 要复制的对象
            
        Returns:
            可变副本
        """
        if isinstance(value, ImmutableDictionary):
            return value.copy_as_mutable()
        if isinstance(value, dict):
            return {k: Utils.get_mutable_copy(v) for k, v in value.items()}
        if isinstance(value, list):
            return [Utils.get_mutable_copy(item) for item in value]
        if isinstance(value, tuple):
            return tuple(Utils.get_mutable_copy(item) for item in value)
        return value

    @staticmethod
    def read_agent_version(config: Dict, config_prefix: str = "agent") -> str:
        """
        读取代理版本信息
        
        Args:
            config: 包含配置信息的字典
            config_prefix: 配置前缀，默认为'agent'
            
        Returns:
            代理版本字符串
        """
        try:
            data_dir = config[config_prefix]["prefix"]
            ver_file = os.path.join(data_dir, "version")
            
            if not os.path.exists(ver_file):
                logger.error("版本文件不存在: %s", ver_file)
                return "unknown"
                
            with open(ver_file, "r", encoding="utf-8") as f:
                version = f.read().strip()
                
            logger.info("Agent 版本: %s", version)
            return version
        except KeyError as e:
            logger.error("配置中缺少必要字段: %s", e)
            return "unknown"
        except OSError as e:
            logger.error("读取版本文件失败: %s", e)
            return "unknown"

    @staticmethod
    def restart_agent(
        stop_event: threading.Event, 
        graceful_stop_timeout: int = 30, 
        exit_helper: Any = None
    ) -> None:
        """
        重新启动代理进程
        
        Args:
            stop_event: 停止事件，用于通知其他线程
            graceful_stop_timeout: 优雅停止超时时间
            exit_helper: 退出助手对象（如果存在）
        """
        if exit_helper:
            exit_helper.exitcode = AGENT_AUTO_RESTART_EXIT_CODE
        else:
            logger.warning("未使用 ExitHelper，直接退出")
            
        stop_event.set()
        logger.info("触发 Agent 重启...")

        # 使用定时器保证进程退出
        def delayed_exit():
            logger.info("重启超时，强制退出")
            sys.exit(AGENT_AUTO_RESTART_EXIT_CODE)
            
        t = threading.Timer(graceful_stop_timeout, delayed_exit)
        t.daemon = True
        t.start()
        
        logger.info("Agent重启定时器启动: %d秒", graceful_stop_timeout)

    @staticmethod
    def get_traceback_as_text(ex: Exception) -> str:
        """
        获取异常的完整堆栈跟踪文本
        
        Args:
            ex: 异常对象
            
        Returns:
            堆栈跟踪字符串
        """
        return "".join(traceback.format_exception(type(ex), ex, ex.__traceback__))

    @staticmethod
    def format_exception_info(ex: Exception) -> str:
        """
        格式化异常信息便于记录
        
        Args:
            ex: 异常对象
            
        Returns:
            格式化后的异常信息
        """
        try:
            tb_str = Utils.get_traceback_as_text(ex)
            return f"[EXCEPTION] {type(ex).__name__}: {str(ex)}\n{tb_str}"
        except:
            return f"[无法格式化的异常] {ex}"


def lazy_property(fn: Callable) -> property:
    """
    延迟初始化属性装饰器
    
    特性:
    - 函数仅首次访问时执行
    - 后续访问返回缓存值
    - 自动处理属性名，避免命名冲突
    
    使用示例:
        class MyClass:
            @lazy_property
            def expensive_calculation(self):
                print("首次加载，执行计算...")
                return 42
                
        obj = MyClass()
        print(obj.expensive_calculation)  # 首次调用
        print(obj.expensive_calculation)  # 后续返回缓存值
    """
    attr_name = f"_lazy_{fn.__name__}"
    
    @wraps(fn)
    def wrapper(instance):
        try:
            return getattr(instance, attr_name)
        except AttributeError:
            value = fn(instance)
            setattr(instance, attr_name, value)
            return value
            
    return property(wrapper)


@synchronized
def synchronized(lock: threading.RLock) -> Callable:
    """
    线程同步装饰器工厂
    
    作用:
    创建一个装饰器，保证函数在指定锁的保护下执行
    
    Args:
        lock: 要使用的锁对象
        
    Returns:
        同步装饰器
        
    Usage:
        lock = threading.RLock()
        
        @synchronized(lock)
        def my_safe_function():
            # 受锁保护的代码
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper
    return decorized


def execute_with_retries(
    max_retries: int, 
    retry_delay: float, 
    retry_exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]], 
    func: Callable, 
    *args, 
    **kwargs
) -> Any:
    """
    带重试的执行函数
    
    Args:
        max_retries: 最大重试次数（总尝试次数=重试次数+1）
        retry_delay: 重试间隔（秒）
        retry_exceptions: 触发重试的异常类型
        func: 要执行的函数
        args: 函数位置参数
        kwargs: 函数关键字参数
        
    Returns:
        函数的返回值
        
    Raises:
        最后一次尝试的异常，如果所有尝试都失败
    """
    for attempt in range(1, max_retries + 2):  # +1 包含初始尝试
        try:
            return func(*args, **kwargs)
        except retry_exceptions as ex:
            if attempt < max_retries + 1:
                logger.warning(
                    "重试 (尝试 %d/%d) | 异常: %s: %s | %d秒后重试",
                    attempt, max_retries + 1, type(ex).__name__, ex, retry_delay
                )
                time.sleep(retry_delay)
            else:
                logger.error("所有尝试失败 (%d次)", max_retries + 1)
                raise
        except Exception as ex:
            logger.error("非预期的异常类型: %s", type(ex).__name__)
            raise
