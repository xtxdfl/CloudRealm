#!/usr/bin/env python3
"""
高级任务调度器实现 - 核心组件封装了复杂的任务调度逻辑
"""

import os
import sys
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Callable, Any, Optional, Iterable, Union

# 导入优化的工具类
from apscheduler.util import combine_opts, ref_to_obj, asbool, time_difference
from apscheduler.triggers import SimpleTrigger, IntervalTrigger, CronTrigger
from apscheduler.jobstores.ram_store import RAMJobStore
from apscheduler.job import Job, MaxInstancesReachedError
from apscheduler.events import *
from apscheduler.threadpool import ThreadPool

# 获取日志对象
logger = logging.getLogger(__name__)


class SchedulerConfigurationError(Exception):
    """调度器配置错误异常基类"""
    pass


class SchedulerStateError(Exception):
    """调度器状态错误异常基类"""
    pass


class SchedulerAlreadyRunningError(SchedulerStateError):
    """尝试在调度器运行时进行无效操作时引发"""
    def __str__(self):
        return "调度器已在运行状态"


class SchedulerNotRunningError(SchedulerStateError):
    """尝试在调度器停止时进行无效操作时引发"""
    def __str__(self):
        return "调度器未在运行状态"


class JobScheduler:
    """
    高级任务调度器，提供完整的任务管理生命周期
    功能特点：
    1. 支持多种触发器类型（定时、间隔、Cron表达式）
    2. 灵活的作业存储机制（内存、数据库、文件等）
    3. 事件监听系统（作业添加、执行、错误等）
    4. 线程池管理任务执行
    5. 容错机制（异常处理、状态恢复）
    """
    
    # 默认配置
    DEFAULT_CONFIG = {
        "misfire_grace_time": 30,   # 任务延迟执行的宽限秒数
        "coalesce": True,           # 是否合并多次连续执行
        "standalone": False,        # 是否独立运行（阻塞模式）
        "daemonic": True,           # 工作线程是否为守护线程
        "jobstore.default.class": "apscheduler.jobstores.ram_store.RAMJobStore",
    }

    def __init__(self, global_config: Optional[Dict] = None, **options):
        """
        初始化任务调度器
        
        Args:
            global_config: 全局配置字典
            options: 调度器配置选项
        """
        # 初始化状态标志
        self._shutdown_flag = threading.Event()
        self._running = False
        self._thread = None
        
        # 初始化组件
        self._wakeup_event = threading.Event()
        self._jobstores: Dict[str, Any] = {}
        self._jobstores_lock = threading.RLock()
        self._listeners: List[Tuple[Callable, int]] = []
        self._listeners_lock = threading.RLock()
        self._pending_jobs: List[Tuple[Job, str]] = []
        self._threadpool: Optional[ThreadPool] = None
        
        # 应用配置
        self.configure(global_config or {}, **options)

    @property
    def running(self) -> bool:
        """判断调度器是否正在运行"""
        if self._standalone:
            return not self._shutdown_flag.is_set()
        return self._running and self._thread and self._thread.is_alive()

    def configure(self, global_config: Dict, **options) -> None:
        """
        配置调度器（只能在非运行状态下调用）
        
        Args:
            global_config: 全局配置字典
            options: 调度器配置选项
        """
        if self.running:
            raise SchedulerAlreadyRunningError()
        
        # 合并配置
        config = {**self.DEFAULT_CONFIG, **global_config}
        scheduler_opts = combine_opts(config, "apscheduler.", options)
        
        # 解析基础配置
        self.misfire_grace_time = scheduler_opts.get("misfire_grace_time", 30)
        self.coalesce = asbool(scheduler_opts.get("coalesce", True))
        self._standalone = asbool(scheduler_opts.get("standalone", False))
        self._daemonic = asbool(scheduler_opts.get("daemonic", True))
        
        # 配置线程池
        self._configure_threadpool(config, scheduler_opts)
        
        # 配置作业存储
        self._configure_jobstores(config)
        
        logger.info("调度器配置完成 [容错:%ds, 合并执行:%s]",
                    self.misfire_grace_time, self.coalesce)

    def _configure_threadpool(self, config: Dict, scheduler_opts: Dict) -> None:
        """配置执行任务的线程池"""
        if "threadpool" in scheduler_opts:
            self._threadpool = ref_to_obj(scheduler_opts["threadpool"])
            logger.debug("使用自定义线程池: %s", self._threadpool)
        else:
            threadpool_opts = combine_opts(config, "threadpool.")
            self._threadpool = ThreadPool(**threadpool_opts)
            logger.info("创建默认线程池: %s", self._threadpool)

    def _configure_jobstores(self, config: Dict) -> None:
        """配置作业存储系统"""
        # 解析存储配置
        jobstore_opts = combine_opts(config, "jobstore.")
        jobstore_configs = {}
        for key, value in jobstore_opts.items():
            store_name, option = key.split(".", 1)
            jobstore_configs.setdefault(store_name, {})[option] = value
        
        # 应用存储配置
        for alias, opts in jobstore_configs.items():
            try:
                classname = opts.pop("class")
                store_class = ref_to_obj(classname)
                jobstore = store_class(**opts)
                self.add_jobstore(jobstore, alias, quiet=True)
                logger.debug("添加作业存储: %s (%s)", alias, classname)
            except Exception as e:
                logger.error("配置作业存储失败 [%s]: %s", alias, str(e))
                raise SchedulerConfigurationError(
                    f"作业存储配置错误 [{alias}]: {str(e)}"
                ) from e

    def start(self) -> None:
        """
        启动调度器（分为独立运行模式和非独立运行模式）
        独立模式：阻塞当前线程直到调度器关闭
        非独立模式：在后台线程中运行
        """
        if self.running:
            raise SchedulerAlreadyRunningError()
        
        # 确保至少有一个作业存储
        if "default" not in self._jobstores:
            self.add_jobstore(RAMJobStore(), "default", True)
            logger.info("创建默认内存作业存储")
        
        # 调度挂起的作业
        self._schedule_pending_jobs()
        
        # 设置运行标志
        self._shutdown_flag.clear()
        self._running = True
        
        # 启动主循环
        if self._standalone:
            logger.info("以独立模式启动调度器")
            self._main_loop()
        else:
            logger.info("以守护模式启动调度器")
            self._thread = threading.Thread(
                target=self._main_loop, 
                name="APScheduler-Main",
                daemon=self._daemonic
            )
            self._thread.start()

    def shutdown(self, wait: bool = True, shutdown_pool: bool = True, close_stores: bool = True) -> None:
        """
        优雅关闭调度器
        
        Args:
            wait: 是否等待调度器和任务完成
            shutdown_pool: 是否关闭线程池
            close_stores: 是否关闭作业存储
        """
        if not self.running:
            raise SchedulerNotRunningError()
            
        logger.info("正在关闭调度器..")
        self._shutdown_flag.set()
        self._wakeup_event.set()  # 唤醒可能正在等待的主线程
        
        # 关闭线程池
        if shutdown_pool and self._threadpool:
            try:
                self._threadpool.shutdown(wait=wait)
            except Exception as e:
                logger.error("关闭线程池失败: %s", str(e))
        
        # 等待主线程退出
        if self._thread and self._thread.is_alive():
            if wait:
                self._thread.join(timeout=10.0)
                if self._thread.is_alive():
                    logger.warning("调度器主线程未正常退出")
            else:
                logger.info("异步关闭调度器主线程")
        
        # 关闭作业存储
        if close_stores:
            for alias, store in list(self._jobstores.items()):
                try:
                    store.close()
                    logger.debug("作业存储 %s 已关闭", alias)
                except Exception as e:
                    logger.error("关闭作业存储 %s 失败: %s", alias, str(e))
        
        # 更新状态标志
        self._running = False
        logger.info("调度器已关闭")

    def add_jobstore(self, jobstore: Any, alias: str, quiet: bool = False) -> None:
        """
        添加作业存储
        
        Args:
            jobstore: 作业存储对象
            alias: 存储别名
            quiet: 是否静默添加（不唤醒调度器）
        """
        with self._jobstores_lock:
            if alias in self._jobstores:
                raise KeyError(f"别名 '{alias}' 已被占用")
            
            try:
                jobstore.load_jobs()
                self._jobstores[alias] = jobstore
                event = JobStoreEvent(EVENT_JOBSTORE_ADDED, alias)
                self._notify_listeners(event)
                
                if not quiet:
                    self._wakeup_event.set()
                
                logger.info("已添加作业存储: %s", alias)
            except Exception as e:
                logger.error("添加作业存储失败 [%s]: %s", alias, str(e))
                raise SchedulerConfigurationError(
                    f"添加作业存储失败 [{alias}]: {str(e)}"
                ) from e

    def remove_jobstore(self, alias: str, close: bool = True) -> None:
        """
        移除作业存储
        
        Args:
            alias: 要移除的存储别名
            close: 是否关闭存储
        """
        with self._jobstores_lock:
            jobstore = self._jobstores.pop(alias, None)
            if not jobstore:
                raise KeyError(f"存储 '{alias}' 不存在")
            
            if close:
                try:
                    jobstore.close()
                    logger.debug("作业存储 %s 已关闭", alias)
                except Exception as e:
                    logger.error("关闭作业存储 %s 失败: %s", alias, str(e))
            
            event = JobStoreEvent(EVENT_JOBSTORE_REMOVED, alias)
            self._notify_listeners(event)
            logger.info("已移除作业存储: %s", alias)

    def add_listener(self, callback: Callable, event_mask: int = EVENT_ALL) -> None:
        """
        添加事件监听器
        
        Args:
            callback: 事件回调函数
            event_mask: 监听的事件掩码
        """
        with self._listeners_lock:
            self._listeners.append((callback, event_mask))
        logger.debug("添加事件监听器: %s", get_callable_name(callback))

    def remove_listener(self, callback: Callable) -> None:
        """移除事件监听器"""
        with self._listeners_lock:
            new_listeners = [
                (cb, mask) for cb, mask in self._listeners if cb != callback
            ]
            removed = len(self._listeners) - len(new_listeners)
            self._listeners = new_listeners
            
        if removed:
            logger.debug("移除了 %d 个回调监听器", removed)
        else:
            logger.warning("未找到要移除的事件监听器: %s", get_callable_name(callback))

    def _notify_listeners(self, event: Event) -> None:
        """通知所有匹配的监听器"""
        with self._listeners_lock:
            listeners = self._listeners.copy()
        
        for callback, mask in listeners:
            if event.code & mask:
                try:
                    callback(event)
                except Exception:
                    logger.exception("事件回调函数 %s 执行出错", get_callable_name(callback))

    def _schedule_pending_jobs(self) -> None:
        """调度所有挂起的任务"""
        if not self._pending_jobs:
            return
            
        logger.info("正在调度 %d 个挂起任务..", len(self._pending_jobs))
        for job, store_alias in self._pending_jobs:
            try:
                self._real_add_job(job, store_alias, True)
            except Exception as e:
                logger.error("调度挂起任务失败: %s", str(e))
        
        # 清空挂起队列
        self._pending_jobs.clear()

    def _real_add_job(self, job: Job, jobstore_alias: str, wake_scheduler: bool = True) -> None:
        """
        内部方法：将作业添加到存储并唤醒调度器
        
        Args:
            job: 要添加的作业对象
            jobstore_alias: 作业存储别名
            wake_scheduler: 是否唤醒调度器
        """
        # 确保作业有下次运行时间
        if job.next_run_time is None:
            job.compute_next_run_time(datetime.now())
            if job.next_run_time is None:
                raise ValueError("作业没有有效的下次运行时间")
        
        with self._jobstores_lock:
            jobstore = self._jobstores.get(jobstore_alias)
            if not jobstore:
                raise KeyError(f"存储 '{jobstore_alias}' 不存在")
            jobstore.add_job(job)
        
        # 触发作业添加事件
        event = JobStoreEvent(EVENT_JOBSTORE_JOB_ADDED, jobstore_alias, job)
        self._notify_listeners(event)
        logger.debug('已添加作业 "%s" 到存储 "%s"', job.name, jobstore_alias)
        
        if wake_scheduler:
            self._wakeup_event.set()

    def add_job(
        self, 
        trigger: Any,
        func: Callable,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict] = None,
        jobstore_alias: str = "default",
        **job_options
    ) -> Job:
        """
        添加新作业
        
        Args:
            trigger: 触发器对象
            func: 要执行的函数
            args: 函数位置参数
            kwargs: 函数关键字参数
            jobstore_alias: 作业存储别名
            job_options: 作业配置选项
        
        Returns:
            创建的作业对象
        """
        args = args or ()
        kwargs = kwargs or {}
        
        # 从作业选项或配置中获取容错时间和合并设置
        misfire_grace = job_options.pop("misfire_grace_time", self.misfire_grace_time)
        coalesce = job_options.pop("coalesce", self.coalesce)
        
        # 创建作业对象
        job = Job(trigger, func, args, kwargs, misfire_grace, coalesce, **job_options)
        
        if not self.running:
            # 调度器未运行时暂存作业
            self._pending_jobs.append((job, jobstore_alias))
            logger.info("添加挂起作业 %s (将在调度器启动后激活)", job.name)
        else:
            # 直接添加作业
            self._real_add_job(job, jobstore_alias)
        
        return job

    def add_single_job(
        self,
        func: Callable,
        run_date: datetime,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict] = None,
        **job_options
    ) -> Job:
        """
        添加单次运行作业
        
        Args:
            func: 要执行的函数
            run_date: 运行日期时间
            args: 函数位置参数
            kwargs: 函数关键字参数
            job_options: 作业配置选项
        
        Returns:
            创建的作业对象
        """
        trigger = SimpleTrigger(run_date)
        return self.add_job(trigger, func, args, kwargs, **job_options)

    def add_interval_job(
        self,
        func: Callable,
        interval: timedelta,
        start_date: Optional[datetime] = None,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict] = None,
        **job_options
    ) -> Job:
        """
        添加间隔运行作业
        
        Args:
            func: 要执行的函数
            interval: 运行间隔
            start_date: 首次运行时间
            args: 函数位置参数
            kwargs: 函数关键字参数
            job_options: 作业配置选项
        
        Returns:
            创建的作业对象
        """
        trigger = IntervalTrigger(interval, start_date)
        return self.add_job(trigger, func, args, kwargs, **job_options)

    def add_cron_job(
        self,
        func: Callable,
        year: Optional[str] = None,
        month: Optional[str] = None,
        day: Optional[str] = None,
        week: Optional[str] = None,
        day_of_week: Optional[str] = None,
        hour: Optional[str] = None,
        minute: Optional[str] = None,
        second: Optional[str] = None,
        start_date: Optional[datetime] = None,
        args: Optional[Tuple] = None,
        kwargs: Optional[Dict] = None,
        **job_options
    ) -> Job:
        """
        添加Cron表达式作业
        
        Args:
            func: 要执行的函数
            year: 年表达式
            month: 月表达式
            day: 日表达式
            week: 周表达式
            day_of_week: 周几表达式
            hour: 小时表达式
            minute: 分钟表达式
            second: 秒表达式
            start_date: 首次运行时间
            args: 函数位置参数
            kwargs: 函数关键字参数
            job_options: 作业配置选项
        
        Returns:
            创建的作业对象
        """
        trigger = CronTrigger(
            year=year, month=month, day=day, week=week,
            day_of_week=day_of_week, hour=hour, minute=minute,
            second=second, start_date=start_date
        )
        return self.add_job(trigger, func, args, kwargs, **job_options)

    def get_jobs(self) -> List[Job]:
        """获取所有作业列表"""
        jobs = []
        with self._jobstores_lock:
            for store in self._jobstores.values():
                jobs.extend(store.jobs)
        return jobs

    def get_job_by_id(self, job_id: str) -> Optional[Job]:
        """根据ID获取作业"""
        with self._jobstores_lock:
            for store in self._jobstores.values():
                job = next((j for j in store.jobs if j.id == job_id), None)
                if job:
                    return job
        return None

    def remove_job(self, job_id: str) -> None:
        """
        根据ID移除作业
        
        Args:
            job_id: 要移除的作业ID
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise KeyError(f"作业 {job_id} 不存在")
        
        self.remove_job_instance(job)

    def remove_job_instance(self, job: Job) -> None:
        """移除特定的作业实例"""
        with self._jobstores_lock:
            for alias, store in self._jobstores.items():
                if job in store.jobs:
                    store.remove_job(job)
                    
                    # 触发作业移除事件
                    event = JobStoreEvent(EVENT_JOBSTORE_JOB_REMOVED, alias, job)
                    self._notify_listeners(event)
                    logger.info('已移除作业 "%s"', job.name)
                    return
        
        logger.warning('作业 "%s" 未在任一存储中找到', job.name)

    def remove_all_jobs(self) -> None:
        """移除所有作业"""
        with self._jobstores_lock:
            for alias, store in self._jobstores.items():
                for job in list(store.jobs):
                    store.remove_job(job)
                    logger.debug('已移除作业 "%s"', job.name)
                
                # 触发存储清空事件
                event = JobStoreEvent(EVENT_JOBSTORE_JOBS_CLEARED, alias)
                self._notify_listeners(event)
            
        logger.info("已清除所有作业")

    def print_jobs(self, out: Any = None) -> None:
        """
        打印所有作业信息
        
        Args:
            out: 输出流对象
        """
        out = out or sys.stdout
        lines = ["已调度作业:"]
        
        with self._jobstores_lock:
            for alias, store in self._jobstores.items():
                lines.append(f"存储 '{alias}':")
                if store.jobs:
                    for job in store.jobs:
                        lines.append(f"  - {job.name} (ID: {job.id})")
                        lines.append(f"    下次运行: {job.next_run_time}")
                else:
                    lines.append("    无作业")
                
        out.write("\n".join(lines))

    def _process_jobs(self) -> Optional[datetime]:
        """处理所有待执行作业，返回下次唤醒时间"""
        now = datetime.now()
        next_wake_time = None
        logger.debug("正在处理作业 (当前时间: %s)", now.isoformat())
        
        with self._jobstores_lock:
            for alias, store in self._jobstores.items():
                for job in list(store.jobs):
                    if job.next_run_time is None:
                        # 计算作业下次运行时间
                        if not job.compute_next_run_time(now):
                            # 作业已完成运行
                            store.remove_job(job)
                            continue
                    
                    # 检查是否有待执行的运行时间
                    run_times = job.get_run_times(now)
                    if not run_times:
                        # 更新下次唤醒时间
                        if job.next_run_time and (next_wake_time is None or job.next_run_time < next_wake_time):
                            next_wake_time = job.next_run_time
                        continue
                    
                    # 提交作业到线程池
                    try:
                        self._threadpool.submit(self._execute_job, job, run_times)
                        logger.debug("已提交作业 %s 到线程池", job.name)
                    except Exception as e:
                        logger.error("提交作业 %s 失败: %s", job.name, str(e))
                    
                    # 更新作业的运行计数
                    if job.coalesce:
                        job.runs += 1
                    else:
                        job.runs += len(run_times)
                    
                    # 重新计算下次运行时间
                    if not job.compute_next_run_time(now + timedelta(microseconds=1)):
                        # 作业不再有未来运行时间
                        store.remove_job(job)
                        continue
                    
                    # 更新作业存储
                    store.update_job(job)
                    
                    # 更新下次唤醒时间
                    if job.next_run_time and (next_wake_time is None or job.next_run_time < next_wake_time):
                        next_wake_time = job.next_run_time
        
        return next_wake_time

    def _execute_job(self, job: Job, run_times: List[datetime]) -> None:
        """
        执行作业的实际逻辑
        处理可能的延迟执行和并发限制
        """
        for run_time in run_times:
            # 检查是否错过运行时间窗口
            difference = datetime.now() - run_time
            grace_time = timedelta(seconds=job.misfire_grace_time)
            
            if difference > grace_time:
                # 触发错过运行事件
                event = JobEvent(EVENT_JOB_MISSED, job, run_time)
                self._notify_listeners(event)
                logger.warning('作业 "%s" 在 %s 错过执行时间: 延迟 %s', 
                               job.name, run_time.isoformat(), difference)
                continue
            
            # 检查并发限制
            try:
                job.add_instance()
            except MaxInstancesReachedError:
                # 已达最大并发实例数
                event = JobEvent(EVENT_JOB_MISSED, job, run_time)
                self._notify_listeners(event)
                logger.warning('作业 "%s" 跳过运行: 已达最大并发数 (%d)', 
                               job.name, job.max_instances)
                break
            
            # 执行作业
            try:
                job_instance = job.func
                logger.info('开始执行作业 "%s" (计划时间: %s)', job.name, run_time.isoformat())
                
                # 触发开始执行事件
                event = JobEvent(EVENT_JOB_STARTED, job, run_time)
                self._notify_listeners(event)
                
                # 实际执行
                result = job_instance(*job.args, **job.kwargs)
                
                # 触发成功完成事件
                event = JobEvent(EVENT_JOB_EXECUTED, job, run_time, retval=result)
                self._notify_listeners(event)
                logger.info('作业 "%s" 执行完成', job.name)
                
            except Exception as exc:
                # 处理执行异常
                error_event = JobEvent(
                    EVENT_JOB_ERROR, 
                    job, 
                    run_time, 
                    exception=exc,
                    traceback=sys.exc_info()[2]
                )
                self._notify_listeners(error_event)
                logger.exception('作业 "%s" 执行出错', job.name)
            
            finally:
                # 确保减少实例计数
                try:
                    job.remove_instance()
                except Exception:
                    logger.warning("减少作业实例计数时出错")
            
            # 如果配置了合并执行，跳过后续执行
            if job.coalesce:
                break

    def _main_loop(self) -> None:
        """调度器的主运行循环"""
        try:
            logger.info("调度器主循环启动")
            self._notify_listeners(SchedulerEvent(EVENT_SCHEDULER_START))
            self._wakeup_event.clear()
            
            while not self._shutdown_flag.is_set():
                # 处理待运行作业
                next_wake_time = self._process_jobs()
                
                if next_wake_time is not None:
                    # 计算等待时间
                    now = datetime.now()
                    wait_seconds = max(0.0, (next_wake_time - now).total_seconds())
                    logger.debug("下一唤醒时间: %s (等待 %.1f 秒)", 
                                 next_wake_time.isoformat(), wait_seconds)
                    
                    # 等待唤醒事件或超时
                    if self._wakeup_event.wait(timeout=wait_seconds):
                        self._wakeup_event.clear()
                        logger.debug("被唤醒事件提前结束等待")
                else:
                    # 无作业时等待唤醒
                    if self._standalone:
                        logger.info("无待执行作业，准备关闭调度器")
                        self.shutdown()
                        break
                    
                    logger.debug("当前无待执行作业，等待唤醒事件")
                    self._wakeup_event.wait()
                    self._wakeup_event.clear()
                
        except Exception as e:
            logger.exception("调度器主循环出错: %s", str(e))
        finally:
            logger.info("调度器主循环退出")
            self._shutdown_flag.clear()
            self._running = False
            self._notify_listeners(SchedulerEvent(EVENT_SCHEDULER_SHUTDOWN))
