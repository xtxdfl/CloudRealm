#!/usr/bin/env python3
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

Enhanced Resilience Utilities
"""

import time
import random
import datetime
import functools
import logging
from typing import Callable, Any, Tuple, Union, Optional, Dict

__all__ = ["retry", "advanced_retry", "experimental", "circuit_breaker"]

# 日志配置
logger = logging.getLogger("resilience_utils")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class RetryStrategy:
    """预定义的重试策略常量"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避策略
    RANDOM_JITTER = "random_jitter"               # 随机抖动策略
    FIXED_INTERVAL = "fixed_interval"             # 固定间隔策略
    FIBONACCI_BACKOFF = "fibonacci_backoff"       # Fibonacci退避策略
    
class RetryLimit:
    """
    重试限制配置
    :param max_attempts: 最大尝试次数
    :param time_limit: 总时间限制（秒）
    :param error_threshold: 失败率阈值（百分比，0-100）
    """
    def __init__(self, 
                 max_attempts: int = 3, 
                 time_limit: float = None, 
                 error_threshold: float = None):
        self.max_attempts = max_attempts
        self.time_limit = time_limit
        self.error_threshold = error_threshold

def retry(
    times: int = 3,
    sleep_time: float = 1,
    max_sleep_time: float = 10,
    backoff_factor: float = 2,
    err_class: Union[Exception, Tuple[Exception]] = Exception,
    retry_strategy: str = RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter_factor: float = 0.1,
    log_errors: bool = True,
    retry_logger: logging.Logger = None
) -> Callable:
    """
    增强的重试装饰器，提供多种重试策略和高级控制
    
    :param times: 最大尝试次数
    :param sleep_time: 初始重试间隔（秒）
    :param max_sleep_time: 最大重试间隔（秒）
    :param backoff_factor: 退避因子（指数策略使用）
    :param err_class: 需要捕获并重试的异常类型（单个或元组）
    :param retry_strategy: 重试策略（指数退避、随机抖动等）
    :param jitter_factor: 随机抖动因子（0-1之间）
    :param log_errors: 是否记录重试错误
    :param retry_logger: 自定义日志记录器
    :return: 装饰器函数
    """

    if retry_logger is None:
        retry_logger = logger
        
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            _sleep_time = sleep_time
            _attempts = 0
            
            while _attempts < times:
                _attempts += 1
                try:
                    return func(*args, **kwargs)
                except err_class as err:
                    if not log_errors and _attempts < times:
                        pass  # 不记录中间错误
                    else:
                        retry_logger.warning(
                            f"[Attempt {_attempts}/{times}] Retryable error: {type(err).__name__} - {err}",
                            exc_info=log_errors
                        )
                    
                    if _attempts >= times:
                        raise
                        
                    # 计算下一个等待时间
                    next_delay = _calculate_delay(
                        _sleep_time, 
                        max_sleep_time, 
                        backoff_factor,
                        retry_strategy,
                        jitter_factor
                    )
                    retry_logger.info(
                        f"Next attempt in {next_delay:.2f}s (strategy: {retry_strategy})"
                    )
                    time.sleep(next_delay)
                    _sleep_time = min(_sleep_time * backoff_factor, max_sleep_time)
                    
        return wrapper
    return decorator

def advanced_retry(
    retry_limit: RetryLimit = RetryLimit(),
    base_delay: float = 1,
    max_delay: float = 30,
    backoff_factor: float = 2,
    err_classes: Tuple[Exception] = (Exception,),
    retry_strategy: str = RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter_factor: float = 0.2,
    result_validator: Callable[[Any], bool] = None,
    on_retry: Callable[[int, float], None] = None,
    on_failure: Callable[[Exception], None] = None,
    retry_logger: logging.Logger = None
) -> Callable:
    """
    高级重试装饰器，提供全功能的重试机制
    
    :param retry_limit: 重试限制配置
    :param base_delay: 初始重试间隔（秒）
    :param max_delay: 最大重试间隔（秒）
    :param backoff_factor: 退避因子
    :param err_classes: 需要捕获并重试的异常类型
    :param retry_strategy: 重试策略
    :param jitter_factor: 随机抖动因子
    :param result_validator: 结果验证函数（返回True表示成功）
    :param on_retry: 重试时触发的回调函数（参数：尝试次数，延迟时间）
    :param on_failure: 最终失败时触发的回调函数
    :param retry_logger: 自定义日志记录器
    :return: 装饰器函数
    """
    
    if retry_logger is None:
        retry_logger = logger
        
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.monotonic()
            attempt = 0
            errors = []
            current_delay = base_delay
            
            while True:
                attempt += 1
                try:
                    result = func(*args, **kwargs)
                    
                    # 验证结果是否符合预期
                    if result_validator is None or result_validator(result):
                        return result
                        
                    # 处理无效结果
                    raise ValueError(f"Invalid result: {result} (validator check failed)")
                        
                except err_classes as err:
                    errors.append(err)
                    error_percent = (len(errors) / attempt) * 100 if attempt > 0 else 0
                    
                    # 检查是否达到终止条件
                    stop_retry = False
                    reason = ""
                    
                    if retry_limit.max_attempts and attempt >= retry_limit.max_attempts:
                        stop_retry = True
                        reason = f"max attempts reached ({retry_limit.max_attempts})"
                    
                    if retry_limit.time_limit and (time.monotonic() - start_time) > retry_limit.time_limit:
                        stop_retry = True
                        reason = f"time limit exceeded ({retry_limit.time_limit}s)"
                        
                    if retry_limit.error_threshold and error_percent >= retry_limit.error_threshold:
                        stop_retry = True
                        reason = f"error threshold exceeded ({error_percent:.1f}% >= {retry_limit.error_threshold}%)"
                    
                    if stop_retry:
                        if on_failure:
                            on_failure(errors)
                            
                        combined_error = "\n".join(f"{i+1}. {type(e).__name__}: {e}" for i, e in enumerate(errors))
                        retry_logger.error(
                            f"Retry stopped ({reason}) after {attempt} attempts. Errors:\n{combined_error}",
                            exc_info=True
                        )
                        raise
                    
                    # 应用重试延迟
                    next_delay = _calculate_delay(
                        current_delay,
                        max_delay,
                        backoff_factor,
                        retry_strategy,
                        jitter_factor
                    )
                    
                    status_msg = (
                        f"Attempt {attempt}/{retry_limit.max_attempts or '∞'} failed: "
                        f"{type(err).__name__} - {err}. "
                        f"Delaying next attempt by {next_delay:.2f}s"
                    )
                    
                    if retry_limit.time_limit:
                        remaining_time = retry_limit.time_limit - (time.monotonic() - start_time)
                        status_msg += f", time left: {remaining_time:.1f}s"
                        
                    retry_logger.warning(status_msg)
                    
                    if on_retry:
                        on_retry(attempt, next_delay)
                    
                    time.sleep(next_delay)
                    current_delay = min(current_delay * backoff_factor, max_delay)
                
        return wrapper
    return decorator

def _calculate_delay(
    base: float, 
    max_val: float, 
    factor: float, 
    strategy: str,
    jitter: float
) -> float:
    """计算实际延迟时间，应用指定策略"""
    # 基础延迟计算
    if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = min(base * factor, max_val)
    elif strategy == RetryStrategy.FIBONACCI_BACKOFF:
        delay = min((base * factor) * 1.618, max_val)  # 使用黄金比例
    else:  # FIXED_INTERVAL or default
        delay = min(base, max_val)
    
    # 添加随机抖动
    if strategy == RetryStrategy.RANDOM_JITTER or jitter > 0:
        jitter_amount = delay * jitter * random.uniform(-1, 1)
        delay = max(0.1, delay + jitter_amount)
    
    return min(delay, max_val)

class CircuitBreaker:
    """
    高级断路器实现，快速拒绝失败率高的调用
    
    :param failure_threshold: 触发跳闸的失败率（百分比）
    :param recovery_timeout: 恢复期时长（秒）
    :param min_calls: 最小调用次数后才开始计算错误率
    :param exclude_exceptions: 不计数这些异常为失败
    """
    
    def __init__(
        self, 
        failure_threshold: float = 50, 
        recovery_timeout: float = 30,
        min_calls: int = 10,
        exclude_exceptions: Tuple[Exception] = ()
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.min_calls = min_calls
        self.exclude_exceptions = exclude_exceptions
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_failure_time = 0
        self.stats = {"success": 0, "failure": 0}
    
    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 断路器打开状态：立即失败
            if self.state == "OPEN":
                if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                    self.state = "HALF_OPEN"  # 进入半开状态尝试恢复
                else:
                    raise CircuitOpenError(f"Circuit is OPEN, failing fast. Time left: "
                     f"{self.recovery_timeout - (time.monotonic() - self.last_failure_time):.1f}s")
            
            try:
                result = func(*args, **kwargs)
                
                # 处理半开状态成功：恢复为闭合状态
                if self.state == "HALF_OPEN":
                    self._reset_breaker()
                    self.state = "CLOSED"
                
                self.stats["success"] += 1
                return result
            except Exception as err:
                # 忽略排除的异常
                if any(isinstance(err, ex) for ex in self.exclude_exceptions):
                    raise
                
                self.stats["failure"] += 1
                
                # 检查是否需触发跳闸
                total_calls = self.stats["success"] + self.stats["failure"]
                error_rate = (self.stats["failure"] / total_calls) * 100 if total_calls > 0 else 0
                
                if total_calls >= self.min_calls and error_rate >= self.failure_threshold:
                    self.state = "OPEN"
                    self.last_failure_time = time.monotonic()
                    logger.error(f"Circuit opened! Error rate: {error_rate:.1f}%")
                
                raise
        return wrapper
    
    def _reset_breaker(self):
        """重置断路器统计信息"""
        self.stats = {"success": 0, "failure": 0}

class CircuitOpenError(Exception):
    """断路器打开时的自定义异常"""
    pass

def experimental(
    feature: Optional[str] = None,
    comment: Optional[str] = None,
    stable_date: Optional[datetime.date] = None,
    log_level: Union[int, str] = logging.INFO,
    disable: bool = False,
    warn_only: bool = False
) -> Callable:
    """
    增强的实验性特性装饰器，提供详细的特性信息和警告
    
    :param feature: 实验性特性的名称或标识
    :param comment: 关于该特性的描述或警告
    :param stable_date: 预期的稳定版本日期
    :param log_level: 日志级别 (logging.INFO, logging.WARNING等)
    :param disable: 是否禁用该特性
    :param warn_only: 是否仅警告但不禁止调用
    :return: 装饰器函数
    """
    
    def decorator(func: Callable) -> Callable:
        nonlocal comment
        
        if not comment:
            comment = "This is an experimental feature and may change without notice"
            
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 构建特性消息
            feature_msg = f"[experimental: {feature}] " if feature else "[experimental] "
            expiration_msg = f" - Stabilization planned for {stable_date.isoformat()}" if stable_date else ""
            full_message = feature_msg + comment + expiration_msg
            
            # 记录特性状态
            logger.log(log_level, full_message)
            
            if disable:
                logger.warning(f"Experimental feature {feature or func.__name__} is disabled")
                return None
                
            if warn_only:
                return func(*args, **kwargs)
                
            # 获取用户最终确认
            user_choice = input(f"⚠️ WARNING: {full_message}\nProceed? (y/n): ").strip().lower()
            if user_choice != "y":
                logger.error("User declined to use experimental feature")
                return None
                
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ========================== 测试代码 ==========================
if __name__ == "__main__":
    
    # 模拟故障的API函数
    class UnstableService:
        self_fail_count = 3
        
        @advanced_retry(
            retry_limit=RetryLimit(max_attempts=5, time_limit=10),
            err_classes=(ConnectionError, ValueError),
            retry_strategy=RetryStrategy.RANDOM_JITTER,
            jitter_factor=0.3
        )
        def get_data(self):
            "模拟不稳定的API调用"
            self.self_fail_count -= 1
            if self.self_fail_count > 0:
                raise ConnectionError("Service temporarily unavailable")
            return {"data": "Success after failures"}
    
    # 断路器演示
    class ProtectedService:
        def __init__(self):
            self.counter = 0
            self.cb = CircuitBreaker(failure_threshold=50, recovery_timeout=5)
        
        @circuit_breaker
        def process(self):
            if self.counter < 5:
                self.counter += 1
                raise RuntimeError("Transient error")
            return "Operation succeeded"
    
    # 测试函数
    @retry(
        times=4, 
        sleep_time=0.5, 
        backoff_factor=2,
        retry_strategy=RetryStrategy.FIBONACCI_BACKOFF
    )
    def test_function(fail_count=2):
        """测试重试机制的函数"""
        nonlocal fail_count
        if fail_count > 0:
            fail_count -= 1
            raise ValueError("Simulated failure")
        return "Success"
    
    # 实验性特性演示
    @experimental(
        feature="Quantum Computing API",
        comment="This feature may cause spacetime displacement",
        stable_date=datetime.date(2023, 12, 31),
        warn_only=True
    )
    def quantum_compute():
        return str(42)  # 答案
    
    # 运行测试
    print("="*40)
    print("Starting resilience utilities test")
    print("="*40)
    
    try:
        service = UnstableService()
        print("UnstableService result:", service.get_data())
        
        protected = ProtectedService()
        for _ in range(10):
            try:
                print("ProtectedService result:", protected.process())
            except CircuitOpenError as coe:
                print(coe)
                time.sleep(1.5)
        
        print("Test function result:", test_function())
        print("Quantum compute result:", quantum_compute())
        
    except Exception as e:
        print("Test failed with:", str(e))
    else:
        print("All tests completed successfully!")
    finally:
        print("="*40)
        print("End of resilience utilities test")
        print("="*40)
