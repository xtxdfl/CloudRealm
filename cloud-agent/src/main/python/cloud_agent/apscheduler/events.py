#!/usr/bin/env python3
"""
高级调度器事件系统 - 为任务调度框架提供全面的事件通知机制
定义了调度器生命周期事件、存储操作事件和作业执行事件类型
使用位掩码技术实现事件类型的灵活组合
"""

__all__ = (
    "EVENT_SCHEDULER_START",
    "EVENT_SCHEDULER_SHUTDOWN",
    "EVENT_JOBSTORE_ADDED",
    "EVENT_JOBSTORE_REMOVED",
    "EVENT_JOBSTORE_JOB_ADDED",
    "EVENT_JOBSTORE_JOB_REMOVED",
    "EVENT_JOBSTORE_JOBS_CLEARED",
    "EVENT_JOB_STARTED",
    "EVENT_JOB_EXECUTED",
    "EVENT_JOB_ERROR",
    "EVENT_JOB_MISSED",
    "EVENT_ALL",
    "SchedulerEvent",
    "JobStoreEvent",
    "JobExecutionEvent",
)

from typing import Optional, Any

# ================= 事件类型常量 - 位掩码设计 =================
EVENT_SCHEDULER_START = 1 << 0         # 调度器启动事件
EVENT_SCHEDULER_SHUTDOWN = 1 << 1      # 调度器关闭事件
EVENT_JOBSTORE_ADDED = 1 << 2          # 作业存储添加事件
EVENT_JOBSTORE_REMOVED = 1 << 3        # 作业存储移除事件
EVENT_JOBSTORE_JOB_ADDED = 1 << 4      # 作业添加到存储事件
EVENT_JOBSTORE_JOB_REMOVED = 1 << 5    # 作业从存储移除事件
EVENT_JOBSTORE_JOBS_CLEARED = 1 << 6   # 作业存储清空事件

EVENT_JOB_STARTED = 1 << 7             # 作业开始执行事件
EVENT_JOB_EXECUTED = 1 << 8            # 作业执行完成事件
EVENT_JOB_ERROR = 1 << 9               # 作业执行错误事件
EVENT_JOB_MISSED = 1 << 10             # 作业错过执行事件

# 所有事件的组合掩码
EVENT_ALL = (
    EVENT_SCHEDULER_START | EVENT_SCHEDULER_SHUTDOWN |
    EVENT_JOBSTORE_ADDED | EVENT_JOBSTORE_REMOVED |
    EVENT_JOBSTORE_JOB_ADDED | EVENT_JOBSTORE_JOB_REMOVED | EVENT_JOBSTORE_JOBS_CLEARED |
    EVENT_JOB_STARTED | EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
)

# 事件类型转名称的映射
EVENT_NAMES = {
    EVENT_SCHEDULER_START: "SCHEDULER_START",
    EVENT_SCHEDULER_SHUTDOWN: "SCHEDULER_SHUTDOWN",
    EVENT_JOBSTORE_ADDED: "JOBSTORE_ADDED",
    EVENT_JOBSTORE_REMOVED: "JOBSTORE_REMOVED",
    EVENT_JOBSTORE_JOB_ADDED: "JOB_ADDED",
    EVENT_JOBSTORE_JOB_REMOVED: "JOB_REMOVED",
    EVENT_JOBSTORE_JOBS_CLEARED: "JOBS_CLEARED",
    EVENT_JOB_STARTED: "JOB_STARTED",
    EVENT_JOB_EXECUTED: "JOB_EXECUTED",
    EVENT_JOB_ERROR: "JOB_ERROR",
    EVENT_JOB_MISSED: "JOB_MISSED",
}


class Event:
    """
    事件基类，定义所有事件的通用结构和行为
    
    属性:
        code (int): 事件类型代码（位掩码）
        timestamp (float): 事件发生的时间戳
    """
    
    __slots__ = ("code", "timestamp", "_event_name")
    
    def __init__(self, code: int):
        """
        初始化事件实例
        
        Args:
            code: 事件类型代码
        """
        self.code = code
        self.timestamp = self._current_time()
        self._event_name = EVENT_NAMES.get(code, f"UNKNOWN_{code}")
    
    @staticmethod
    def _current_time() -> float:
        """获取当前时间戳（用于测试时可重写此方法）"""
        import time
        return time.time()
    
    @property
    def name(self) -> str:
        """获取事件的人类可读名称"""
        return self._event_name
    
    def __repr__(self) -> str:
        """返回事件的正式表示形式"""
        return f"<{self.__class__.__name__} code={self.code} time={self.timestamp}>"
    
    def __str__(self) -> str:
        """返回事件的友好描述"""
        return f"{self.__class__.__name__}({self.name}) at {self.timestamp}"


class SchedulerEvent(Event):
    """
    调度器生命周期事件
    
    表示调度器状态变化的事件，如启动、关闭
    
    属性:
        code (int): 事件类型代码
    """
    
    __slots__ = ()
    
    def __init__(self, code: int):
        """
        初始化调度器事件
        
        支持的事件类型:
            EVENT_SCHEDULER_START
            EVENT_SCHEDULER_SHUTDOWN
        """
        if code not in (EVENT_SCHEDULER_START, EVENT_SCHEDULER_SHUTDOWN):
            raise ValueError(f"无效的调度器事件代码: {code}")
        super().__init__(code)


class JobStoreEvent(Event):
    """
    作业存储操作事件
    
    表示作业存储系统的变更事件
    
    属性:
        code (int): 事件类型代码
        alias (str): 作业存储的别名
        job (Optional[Job]): 相关作业（如果适用）
    """
    
    __slots__ = ("alias", "job")
    
    def __init__(
        self, 
        code: int, 
        alias: str, 
        job: Optional[Any] = None
    ):
        """
        初始化作业存储事件
        
        支持的事件类型:
            EVENT_JOBSTORE_ADDED
            EVENT_JOBSTORE_REMOVED
            EVENT_JOBSTORE_JOB_ADDED
            EVENT_JOBSTORE_JOB_REMOVED
            EVENT_JOBSTORE_JOBS_CLEARED
        
        Args:
            code: 事件类型代码
            alias: 作业存储的别名
            job: 关联的作业对象（仅适用于作业变更事件）
        """
        if code not in (
            EVENT_JOBSTORE_ADDED, EVENT_JOBSTORE_REMOVED,
            EVENT_JOBSTORE_JOB_ADDED, EVENT_JOBSTORE_JOB_REMOVED,
            EVENT_JOBSTORE_JOBS_CLEARED
        ):
            raise ValueError(f"无效的作业存储事件代码: {code}")
        
        super().__init__(code)
        self.alias = alias
        self.job = job
    
    def __str__(self) -> str:
        """返回事件的友好描述"""
        base_str = f"{super().__str__()} store={self.alias}"
        if self.job:
            # 假设Job对象有name或id属性
            job_id = getattr(self.job, "id", "N/A")
            job_name = getattr(self.job, "name", "Unnamed Job")
            base_str += f" job={job_name} (id={job_id})"
        return base_str


class JobExecutionEvent(Event):
    """
    作业执行过程事件
    
    表示作业执行过程中的关键节点事件
    
    属性:
        code (int): 事件类型代码
        job (Job): 关联的作业对象
        scheduled_run_time (datetime): 作业的计划执行时间
        retval (Optional[Any]): 作业的返回值（成功执行时）
        exception (Optional[Exception]): 抛出的异常（执行失败时）
        traceback (Optional[TracebackType]): 异常的堆栈信息
    """
    
    __slots__ = ("job", "scheduled_run_time", "retval", "exception", "traceback")
    
    def __init__(
        self, 
        code: int, 
        job: Any, 
        scheduled_run_time: Any = None,
        retval: Optional[Any] = None,
        exception: Optional[Exception] = None,
        traceback: Optional[Any] = None
    ):
        """
        初始化作业执行事件
        
        支持的事件类型:
            EVENT_JOB_STARTED
            EVENT_JOB_EXECUTED
            EVENT_JOB_ERROR
            EVENT_JOB_MISSED
        
        Args:
            code: 事件类型代码
            job: 关联的作业对象
            scheduled_run_time: 作业的计划执行时间
            retval: 作业的返回值（仅在成功执行时）
            exception: 抛出的异常（仅在执行失败时）
            traceback: 异常的堆栈信息
        """
        if code not in (
            EVENT_JOB_STARTED, EVENT_JOB_EXECUTED, 
            EVENT_JOB_ERROR, EVENT_JOB_MISSED
        ):
            raise ValueError(f"无效的作业执行事件代码: {code}")
        
        super().__init__(code)
        self.job = job
        self.scheduled_run_time = scheduled_run_time
        self.retval = retval
        self.exception = exception
        self.traceback = traceback
        
        # 验证事件类型和数据一致性
        if code == EVENT_JOB_EXECUTED and exception is not None:
            raise ValueError("EVENT_JOB_EXECUTED cannot have exception")
        
        if code in (EVENT_JOB_ERROR, EVENT_JOB_MISSED) and exception is None:
            # 对于错误事件，没有异常时生成一个通用异常
            if exception is None:
                self.exception = RuntimeError("Job execution failed with no exception")
    
    @property
    def job_id(self) -> str:
        """获取作业ID（假设Job对象有id属性）"""
        return getattr(self.job, "id", "N/A")
    
    @property
    def job_name(self) -> str:
        """获取作业名称（假设Job对象有name属性）"""
        return getattr(self.job, "name", "Unnamed Job")
    
    def __str__(self) -> str:
        """返回事件的友好描述"""
        base_str = f"{super().__str__()} job={self.job_name} (id={self.job_id}) time={self.scheduled_run_time}"
        
        if self.code == EVENT_JOB_EXECUTED and self.retval is not None:
            base_str += f" result={self.retval}"
        
        if self.code == EVENT_JOB_ERROR and self.exception is not None:
            base_str += f" error={self.exception.__class__.__name__}"
        
        return base_str
    
    def get_error_details(self) -> str:
        """
        获取错误事件的详细信息（如果有）
        
        Returns:
            包含错误信息的字符串
        """
        if not self.exception:
            return ""
        
        lines = [f"Job {self.job_name} (id={self.job_id}) failed with exception:"]
        lines.append(f"  Type: {type(self.exception).__name__}")
        lines.append(f"  Message: {str(self.exception)}")
        
        if self.traceback:
            import traceback
            tb_lines = traceback.format_tb(self.traceback)
            lines.append("  Traceback:")
            lines.extend(f"    {line}" for line in tb_lines)
        
        return "\n".join(lines)


# ================= 工具函数 =================

def event_mask_to_names(mask: int) -> str:
    """将事件掩码转换为人类可读的事件名称列表"""
    names = []
    for code, name in EVENT_NAMES.items():
        if mask & code:
            names.append(name)
    return ", ".join(names) or "NONE"


def match_event_types(mask: int, event_codes: Iterable[int]) -> bool:
    """检查事件掩码是否包含任一给定事件类型"""
    return any(mask & code for code in event_codes)
