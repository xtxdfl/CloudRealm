#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务调度系统中的作业表示类。

此模块定义了Job类，用于封装调度任务的元数据、状态和行为。
"""

from threading import RLock
from datetime import datetime, timedelta
from typing import Callable, Any, Dict, List, Optional, Tuple, Union
from apscheduler.util import to_unicode, ref_to_obj, get_callable_name, obj_to_ref

class MaxInstancesReachedError(Exception):
    """作业实例数达到最大限制时引发此异常"""
    pass

class JobTerminationError(Exception):
    """停止作业时引发的异常"""
    pass

class Job:
    """
    封装调度任务及其元数据。Job实例由调度器在添加作业时创建，不应直接实例化。
    
    属性:
        id: 作业唯一标识符
        trigger: 决定执行时间的触发器对象
        func: 被调用执行的函数
        args: 调用函数的参数列表
        kwargs: 调用函数的关键字参数
        name: 作业的可读名称
        misfire_grace_time: 作业允许在预定时间后延迟秒数
        coalesce: 当调度器判断作业应连续多次运行时是否只运行一次
        max_runs: 作业最多允许运行次数
        max_instances: 作业允许同时运行的最大实例数
        runs: 作业已运行次数
        instances: 当前运行中的作业实例数
    """

    __slots__ = (
        'id', 'trigger', 'func', 'args', 'kwargs', 'name', 
        'misfire_grace_time', 'coalesce', 'max_runs', 
        'max_instances', 'runs', 'instances', '_lock',
        'next_run_time', 'last_run_start', 'last_run_finish',
        'last_run_result', 'last_run_exception'
    )
    
    def __init__(
        self,
        trigger: Any,
        func: Callable,
        args: Tuple[Any, ...] = (),
        kwargs: Dict[str, Any] = None,
        misfire_grace_time: int = 60,
        coalesce: bool = True,
        name: Optional[str] = None,
        max_runs: Optional[int] = None,
        max_instances: int = 1,
        job_id: Optional[str] = None
    ):
        """
        初始化新作业实例。
        
        Args:
            trigger: 触发作业执行的触发器对象
            func: 作业要执行的回调函数
            args: 传递给函数的参数元组
            kwargs: 传递给函数的关键字参数字典
            misfire_grace_time: 允许作业延迟执行的秒数
            coalesce: 是否合并连续多次调用
            name: 作业的可读名称
            max_runs: 作业最大运行次数限制
            max_instances: 作业最大并发实例数
            job_id: 作业唯一标识符
        """
        # 验证输入参数
        self._validate_init_params(
            trigger, func, args, kwargs, 
            misfire_grace_time, max_runs, max_instances
        )
        
        # 线程安全锁
        self._lock = RLock()
        
        # 作业标识
        self.id = job_id or self.generate_job_id()
        
        # 作业核心属性
        self.trigger = trigger
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.name = to_unicode(name) if name else get_callable_name(func)
        self.misfire_grace_time = misfire_grace_time
        self.coalesce = coalesce
        self.max_runs = max_runs
        self.max_instances = max_instances
        
        # 作业状态跟踪
        self.runs = 0
        self.instances = 0
        self.next_run_time: Optional[datetime] = None
        self.last_run_start: Optional[datetime] = None
        self.last_run_finish: Optional[datetime] = None
        self.last_run_result: Any = None
        self.last_run_exception: Optional[Exception] = None

    @staticmethod
    def generate_job_id() -> str:
        """生成唯一的作业ID"""
        # 在实际应用中可替换为更健壮的ID生成机制
        return f"job_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    @staticmethod
    def _validate_init_params(
        trigger, func, args, kwargs, 
        misfire_grace_time, max_runs, max_instances
    ) -> None:
        """验证初始化参数的有效性"""
        if trigger is None:
            raise ValueError("触发器不能为None")
        if not callable(func):
            raise TypeError("func参数必须是可调用对象")
        if not isinstance(args, (tuple, list)):
            raise TypeError("args必须是序列类型")
        if kwargs is not None and not isinstance(kwargs, dict):
            raise TypeError("kwargs必须是字典类型")
        if misfire_grace_time <= 0:
            raise ValueError("misfire_grace_time必须为正数")
        if max_runs is not None and max_runs <= 0:
            raise ValueError("max_runs必须为None或正整数")
        if max_instances <= 0:
            raise ValueError("max_instances必须为正整数")

    def compute_next_run_time(self, now: datetime) -> Optional[datetime]:
        """
        计算作业的下一次运行时间。
        
        Args:
            now: 当前时间
            
        Returns:
            下一次运行时间(如果作业已运行完成则为None)
        """
        # 检查是否达到最大运行次数
        if self.max_runs is not None and self.runs >= self.max_runs:
            self.next_run_time = None
            return None
        
        # 计算下一次运行时间
        with self._lock:
            self.next_run_time = self.trigger.get_next_fire_time(now)
            return self.next_run_time

    def get_run_times(self, now: datetime, max_count: int = 1000) -> List[datetime]:
        """
        获取从下一个运行时间到当前时间之间的所有计划运行时间。
        
        Args:
            now: 查询截止时间
            max_count: 最大返回运行时间数(用于避免过长的列表)
            
        Returns:
            计划运行时间列表(按时间顺序排列)
        """
        run_times: List[datetime] = []
        increment = timedelta(microseconds=1)
        run_time = self.next_run_time
        
        while (
            run_time is not None 
            and run_time <= now
            and (self.max_runs is None or self.runs + len(run_times) < self.max_runs)
            and len(run_times) < max_count
        ):
            run_times.append(run_time)
            run_time = self.trigger.get_next_fire_time(run_time + increment)
        
        return run_times

    def increment_instances(self) -> None:
        """增加当前运行实例计数(使用锁确保线程安全)"""
        with self._lock:
            if self.instances >= self.max_instances:
                raise MaxInstancesReachedError(
                    f"作业 '{self.name}' 已达到最大实例数 {self.max_instances}"
                )
            self.instances += 1
            logger.debug(f"作业 '{self.name}' 增加实例计数: {self.instances}/{self.max_instances}")

    def decrement_instances(self) -> None:
        """减少当前运行实例计数(使用锁确保线程安全)"""
        with self._lock:
            if self.instances <= 0:
                logger.warning("尝试减少已为0的实例计数")
                return
            
            self.instances -= 1
            logger.debug(f"作业 '{self.name}' 减少实例计数: {self.instances}/{self.max_instances}")

    def execute(self) -> Any:
        """执行作业任务并处理生命周期事件"""
        with self._lock:
            # 记录开始时间并运行作业
            self.last_run_start = datetime.now()
            try:
                result = self.func(*self.args, **self.kwargs)
                self.last_run_result = result
                self.last_run_exception = None
            except Exception as e:
                self.last_run_result = None
                self.last_run_exception = e
                result = None
                logger.error(f"作业 '{self.name}' 执行中出错: {str(e)}", exc_info=True)
            finally:
                self.last_run_finish = datetime.now()
                self.runs += 1
            
            return result

    def log_run_stats(self) -> Dict[str, Any]:
        """记录作业的运行统计信息"""
        stats = {
            'job_id': self.id,
            'name': self.name,
            'next_run': self.next_run_time.isoformat() if self.next_run_time else None,
            'total_runs': self.runs,
            'current_instances': self.instances,
        }
        
        if self.last_run_start:
            run_duration = self.last_run_finish - self.last_run_start
            stats['last_run'] = {
                'start': self.last_run_start.isoformat(),
                'finish': self.last_run_finish.isoformat(),
                'duration_secs': run_duration.total_seconds(),
                'success': self.last_run_exception is None
            }
            
            if self.last_run_exception:
                stats['last_run']['error'] = str(self.last_run_exception)
        
        return stats

    def set_max_instances(self, max_instances: int) -> None:
        """设置新的最大实例数(需大于0)"""
        if max_instances <= 0:
            raise ValueError("max_instances must be a positive value")
        
        with self._lock:
            self.max_instances = max_instances
        logger.info(f"作业 '{self.name}' 最大实例数更新为: {max_instances}")

    def reset(self) -> None:
        """重置作业的运行计数器"""
        with self._lock:
            self.runs = 0
            self.instances = 0
            self.last_run_result = None
            self.last_run_exception = None
            self.last_run_start = None
            self.last_run_finish = None
        logger.info(f"作业 '{self.name}' 已重置运行计数")

    def is_active(self) -> bool:
        """判断作业是否处于活跃状态"""
        return (
            self.next_run_time is not None and 
            (self.max_runs is None or self.runs < self.max_runs)
        )

    def can_run(self) -> bool:
        """检查作业是否可以创建新实例"""
        return self.is_active() and self.instances < self.max_instances

    @property
    def run_stats(self) -> Dict[str, Any]:
        """获取作业的运行统计数据(只读属性)"""
        with self._lock:
            stats = {
                'job_id': self.id,
                'name': self.name,
                'next_run': self.next_run_time,
                'total_runs': self.runs,
                'remaining_runs': None if self.max_runs is None else self.max_runs - self.runs,
                'max_instances': self.max_instances,
                'current_instances': self.instances,
                'last_run_status': 'N/A',
                'last_run_duration': None,
                'last_run_exception': str(self.last_run_exception) if self.last_run_exception else None
            }
            
            if self.last_run_start:
                stats['last_run_start'] = self.last_run_start
                if self.last_run_finish:
                    stats['last_run_finish'] = self.last_run_finish
                    stats['last_run_duration'] = self.last_run_finish - self.last_run_start
                    stats['last_run_status'] = 'success' if self.last_run_exception is None else 'failed'
            
            return stats

    def __getstate__(self) -> Dict[str, Any]:
        """用于对作业进行序列化的状态表示"""
        state = {attr: getattr(self, attr) for attr in self.__slots__ if attr != '_lock'}
        state['func_ref'] = obj_to_ref(self.func)
        state.pop('func', None)
        state.pop('args', None)
        state.pop('kwargs', None)
        state.pop('instances', None)
        state.pop('last_run_start', None)
        state.pop('last_run_finish', None)
        state.pop('last_run_result', None)
        state.pop('last_run_exception', None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """从序列化状态恢复作业"""
        state['func'] = ref_to_obj(state.pop('func_ref'))
        state['args'] = state.get('args', ())
        state['kwargs'] = state.get('kwargs', {})
        state['_lock'] = RLock()
        state['instances'] = 0
        state['last_run_start'] = None
        state['last_run_finish'] = None
        state['last_run_result'] = None
        state['last_run_exception'] = None
        
        for attr, value in state.items():
            setattr(self, attr, value)

    def __eq__(self, other: Any) -> bool:
        """作业相等比较(基于ID或实例)"""
        if not isinstance(other, Job):
            return NotImplemented
        return self.id == other.id if self.id is not None else self is other

    def __repr__(self) -> str:
        """作业的可读表示"""
        return (
            f"<Job(id={self.id!r}, name={self.name!r}, "
            f"trigger={type(self.trigger).__name__!r}, "
            f"status={'active' if self.is_active() else 'inactive'})>"
        )

    def __str__(self) -> str:
        """作业的用户友好描述"""
        next_run = self.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if self.next_run_time else "None"
        status = f"{self.runs}/{self.max_runs}" if self.max_runs else str(self.runs)
        return (
            f"Job '{self.name}' (ID: {self.id})\n"
            f"- Status: {'Active' if self.is_active() else 'Inactive'}\n"
            f"- Next Run: {next_run}\n"
            f"- Runs: {status} | Instances: {self.instances}/{self.max_instances}\n"
            f"- Coalesce: {self.coalesce} | Grace time: {self.misfire_grace_time}s"
        )

# 设置日志器
import logging
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    """Job类示例用法"""
    job = Job(
        trigger=MockTrigger(),
        func=lambda x: x*x,
        args=(5,),
        name="测试平方作业",
        max_runs=3,
        max_instances=2
    )
    print(job)
    print(repr(job))
    print(f"作业是否活跃: {job.is_active()}")
    
    # 模拟运行环境
    print("\n运行作业...")
    try:
        job.increment_instances()
        result = job.execute()
        print(f"作业结果: {result}")
    finally:
        job.decrement_instances()
        print(f"\n运行后统计: {job.log_run_stats()}")

