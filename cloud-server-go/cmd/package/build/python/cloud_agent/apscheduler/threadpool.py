#!/usr/bin/env python3
"""
高级线程池实现，模拟Java的ThreadPoolExecutor行为
提供可扩展的线程池管理，支持核心线程、最大线程数和线程空闲超时设置
"""

__all__ = ("ThreadPool", )

import threading
import logging
import time
import weakref
from queue import Queue, Empty
from typing import Callable, Dict, Set, Optional, Tuple, Any
from threading import Thread, Lock, current_thread

# 设置日志
logger = logging.getLogger(__name__)
_thread_pools_registry = weakref.WeakSet()  # 使用WeakSet防止内存泄漏

def _shutdown_all_pools():
    """优雅关闭所有已创建的线程池"""
    logger.info("在程序退出时关闭所有线程池")
    
    for pool in tuple(_thread_pools_registry):
        try:
            logger.debug("关闭线程池: %s", pool)
            pool.shutdown(wait=True)
        except Exception as e:
            logger.exception("关闭线程池时出错: %s", str(e))

class ThreadPoolException(Exception):
    """线程池相关异常的基类"""
    pass

class PoolShutdownError(ThreadPoolException):
    """尝试在关闭后向线程池提交任务时引发"""
    pass

class WorkerThread(Thread):
    """自定义工作线程，提供更多监控能力"""
    pool_ref: Optional[weakref.ReferenceType]
    core_worker: bool
    
    def __init__(self, pool: 'ThreadPool', core: bool = False):
        """
        创建工作线程
        
        Args:
            pool: 所属线程池
            core: 是否为池的核心工作线程
        """
        super().__init__(daemon=True)
        self.pool_ref = weakref.ref(pool)  # 避免循环引用
        self.core_worker = core
        self.last_task_time = 0.0
        self.tasks_completed = 0
        self.active = True
        self.setName(f"WorkerThread-{self.ident}")

    def run(self):
        """工作线程主执行函数"""
        try:
            if self.pool_ref is None:
                logger.error("启动工作线程时失去线程池引用")
                return
            
            pool = self.pool_ref()
            if pool is None or pool.shutdown_flag:
                logger.warning("线程池已被关闭，停止线程")
                return
                
            # 初始化线程上下文
            if pool.context_injector:
                try:
                    pool.context_injector(pool.agent_config)
                except Exception as e:
                    logger.error("上下文注入失败: %s", str(e))
            
            logger.info("%s启动(核心:%s)", self.name, self.core_worker)
            pool._thread_started(self)
            
            # 主工作循环
            while self.active and not pool.shutdown_flag:
                try:
                    # 确定等待超时策略
                    if self.core_worker:
                        block = True
                        timeout = None
                    else:
                        block = True
                        timeout = pool.keepalive
                    
                    # 获取任务
                    task = pool.task_queue.get(block, timeout)
                except Empty:
                    # 非核心线程在空闲超时后退出
                    if not self.core_worker:
                        logger.debug("%s非核心线程空闲超时，退出循环", self.name)
                        break
                    continue
                
                # 检查关闭前任务
                if task is None:  # 关闭信号
                    logger.debug("%s收到关闭信号", self.name)
                    break
                    
                # 执行任务
                self.last_task_time = time.time()
                try:
                    func, args, kwargs = task
                    func_name = getattr(func, "__name__", "anonymous")
                    logger.debug(f"{self.name}开始任务 {func_name}({args},{kwargs})")
                    func(*args, **kwargs)
                    self.tasks_completed += 1 
                except Exception as e:
                    logger.exception(f"{self.name}任务执行出错: {str(e)}")
                finally:
                    # 标记任务完成
                    if pool.task_queue.unfinished_tasks > 0:
                        pool.task_queue.task_done()
            
            logger.info("%s退出(完成任务:%s)", self.name, self.tasks_completed)
        finally:
            # 清理操作
            if pool and not pool.shutdown_flag:
                pool._thread_exiting(self)

class DynamicThreadPool:
    """
    可动态调整大小的线程池，支持核心线程和非核心线程
    核心线程：持续运行，即使没有任务
    非核心线程：空闲超过keepalive时间后自动退出
    """
    
    def __init__(
        self,
        core_threads: int = 2,
        max_threads: int = 10,
        keepalive: float = 30.0,
        context_injector: Optional[Callable] = None,
        agent_config: Optional[Any] = None,
        name_prefix: str = "Pool"
    ):
        """
        Args:
            core_threads: 核心线程数
            max_threads: 最大线程数（需≥core_threads）
            keepalive: 非核心线程空闲时间（秒），0表示立即退出
            context_injector: 工作线程初始化时的上下文注入函数
            agent_config: 传递给上下文注入器的配置对象
            name_prefix: 线程池名称前缀
        """
        # 验证参数
        if max_threads < core_threads:
            raise ValueError("最大线程数必须大于或等于核心线程数")
        
        if keepalive < 0:
            raise ValueError("空闲超时必须是非负数")
            
        # 初始化线程池属性
        self.core_threads = core_threads
        self.max_threads = max_threads
        self.keepalive = keepalive
        self.context_injector = context_injector
        self.agent_config = agent_config
        self.name_prefix = name_prefix
        
        # 任务队列
        self.task_queue = Queue()
        
        # 线程管理
        self.thread_lock = threading.RLock()
        self.worker_threads: Set[WorkerThread] = set()
        self.active_threads = 0
        self.shutdown_flag = False
        
        # 注册全局关闭钩子
        _thread_pools_registry.add(self)
        logger.info(
            "创建线程池 [%s]：核心线程=%d, 最大线程=%d, 空闲超时=%.1fs",
            self.name_prefix, core_threads, max_threads, keepalive
        )
        
        # 启动初始核心线程
        self._adjust_thread_count()

    def __str__(self) -> str:
        """线程池状态字符串表示"""
        thread_count = len(self.worker_threads)
        return (f"<ThreadPool '{self.name_prefix}' "
                f"threads={thread_count}/{self.max_threads} "
                f"active={self.active_threads} "
                f"tasks={self.task_queue.qsize()}>")

    def __repr__(self) -> str:
        """开发人员用表示"""
        return (f"<{self.__class__.__name__} '{self.name_prefix}' "
                f"at 0x{id(self):x}>")

    @property
    def pending_tasks(self) -> int:
        """当前队列中待处理任务数量"""
        return self.task_queue.qsize()

    @property
    def active_workers(self) -> int:
        """当前活动工作线程数"""
        return self.active_threads

    def _thread_started(self, thread: WorkerThread):
        """线程开始执行的钩子"""
        with self.thread_lock:
            self.active_threads += 1
        logger.debug("线程 %s 开始执行任务", thread.name)

    def _thread_exiting(self, thread: WorkerThread):
        """线程即将退出的钩子"""
        with self.thread_lock:
            self.active_threads -= 1
            if thread in self.worker_threads:
                self.worker_threads.remove(thread)
            
            # 检查是否需要创建新线程
            if not self.shutdown_flag and self.active_threads < self.core_threads:
                self._launch_thread(core=True)
        logger.debug("线程 %s 退出", thread.name)

    def _launch_thread(self, core: bool = False) -> Optional[WorkerThread]:
        """创建一个新的工作线程"""
        if len(self.worker_threads) >= self.max_threads:
            logger.debug("已达到最大线程数(%d)，无法创建新线程", self.max_threads)
            return None
            
        try:
            thread = WorkerThread(self, core)
            thread.start()
            with self.thread_lock:
                self.worker_threads.add(thread)
            return thread
        except Exception as e:
            logger.exception("创建新线程失败: %s", str(e))
            return None

    def _adjust_thread_count(self):
        """
        根据当前工作负载动态调整线程数
        
        策略:
        1. 确保至少core_threads个核心线程
        2. 当任务积压时增加非核心线程
        """
        current_threads = len(self.worker_threads)
        
        # 满足核心线程数
        if current_threads < self.core_threads:
            for _ in range(self.core_threads - current_threads):
                self._launch_thread(core=True)
        
        # 当任务队列过大时启用非核心线程
        elif self.task_queue.qsize() > 0 and current_threads < self.max_threads:
            self._launch_thread(core=False)

    def submit(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> None:
        """
        向线程池提交新任务
        
        Args:
            func: 要执行的目标函数
            args: 函数的位置参数
            kwargs: 函数的关键字参数
        """
        # 检查线程池状态
        if self.shutdown_flag:
            raise PoolShutdownError("线程池已关闭，无法提交新任务")
        
        # 添加任务并调整线程数
        logger.debug("提交新任务: %s(%s, %s)", func.__name__, args, kwargs)
        self.task_queue.put((func, args, kwargs))
        
        # 检查是否需增加工作线程
        self._adjust_thread_count()

    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        """
        优雅关闭线程池
        
        Args:
            wait: 是否等待当前所有任务完成
            cancel_pending: 是否取消所有挂起的任务
        """
        if self.shutdown_flag:
            logger.info("线程池已关闭")
            return
            
        logger.info("正在关闭线程池 [%s]...", self.name_prefix)
        self.shutdown_flag = True
        
        # 清理全局注册
        try:
            _thread_pools_registry.discard(self)
        except KeyError:
            pass
        
        # 取消未开始的任务
        if cancel_pending:
            self._cancel_pending_tasks()
        
        # 向所有工作线程发送关闭信号
        with self.thread_lock:
            # 发送与线程数匹配的终止信号
            for _ in range(len(self.worker_threads)):
                self.task_queue.put(None)  # None为终止信号
        
        # 等待工作线程完成
        if wait:
            attempts = 0
            max_wait = max(self.keepalive * 2, 10.0)
            
            while self.worker_threads and attempts < 10:
                logger.debug("等待 %d 个线程终止...", len(self.worker_threads))
                
                # 收集活动线程的快照
                with self.thread_lock:
                    threads = list(self.worker_threads)
                
                # 等待所有线程终止
                for thread in threads:
                    try:
                        thread.join(max_wait)
                    except Exception as e:
                        logger.warning("等待线程终止时出错: %s", str(e))
                
                attempts += 1
                max_wait *= 1.5  # 指数退避算法
            
            if self.worker_threads:
                logger.warning("某些线程未正常退出: %s", self.worker_threads)
        
        logger.info("线程池 [%s] 关闭完成", self.name_prefix)

    def _cancel_pending_tasks(self) -> None:
        """从队列中删除所有待处理任务"""
        pending_tasks = []
        while not self.task_queue.empty():
            try:
                task = self.task_queue.get_nowait()
                if task is not None:  # 忽略终止信号
                    pending_tasks.append(task)
            except Empty:
                break
        
        for task in pending_tasks:
            self.task_queue.task_done()  # 标记这些任务为无需处理
        
        if pending_tasks:
            logger.info("已取消 %d 个挂起任务", len(pending_tasks))

    def map(self, func: Callable, iterable: Iterable, chunksize: int = 1) -> Iterator:
        """
        对可迭代对象并行应用函数
        简化版本的实现，完整实现可参考concurrent.futures
        
        Args:
            func: 要应用的函数
            iterable: 输入数据
            chunksize: 分块大小
        """
        # 实现思路：为每个元素提交任务，收集结果
        # 注意：这是一个简单实现，不适合大迭代对象
        results = []
        semaphore = threading.Semaphore(chunksize)
        event = threading.Event()
        
        def wrapper(*items):
            try:
                result = func(*items)
                with self.thread_lock:
                    results.append(result)
            finally:
                semaphore.release()
                if len(results) == len(iterable):
                    event.set()
        
        for item in iterable:
            semaphore.acquire()
            self.submit(wrapper, item)
        
        event.wait()
        return results

# 兼容性别名
ThreadPool = DynamicThreadPool

# 注册全局关闭钩子
if __name__ != "__main__":
    import atexit
    atexit.register(_shutdown_all_pools)
    logger.debug("已注册全局线程池关闭钩子")

if __name__ == "__main__":
    """线程池示例用法"""
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 创建线程池
    pool = DynamicThreadPool(
        core_threads=2,
        max_threads=4,
        keepalive=2,
        name_prefix="DemoPool"
    )
    
    # 测试任务函数
    def task_worker(task_id: int, duration: float = 0.5):
        tid = threading.get_ident()
        logger.info("任务 %d 在线程 %d 上开始", task_id, tid)
        time.sleep(duration)
        logger.info("任务 %d 在线程 %d 上完成", task_id, tid)
        return task_id * 100
    
    # 提交一组任务
    for i in range(10):
        duration = 0.1 * (i % 3 + 1)
        pool.submit(task_worker, i, duration=duration)
    
    # 等待部分任务完成
    logger.info("等待队列清空...")
    time.sleep(1)
    logger.info("队列状态: 等待任务=%d", pool.pending_tasks)
    
    # 提前关闭线程池
    logger.info("启动关闭序列")
    pool.shutdown(wait=True, cancel_pending=False)
    
    logger.info("示例执行结束")
