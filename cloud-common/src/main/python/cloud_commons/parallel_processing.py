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
"""

import logging
import time
import signal
import traceback
from multiprocessing import Process, Queue, cpu_count, Manager
from typing import Any, Callable, Dict, List, Tuple, Union, Optional
from enum import Enum

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("ParallelProcessing")

class ProcessType(Enum):
    """进程执行模式"""
    # 所有任务执行完成
    ALL_COMPLETE = "all_complete"
    # 第一个任务成功完成时停止
    FIRST_SUCCESS = "first_success"
    # 第一个任务完成时停止（无论成功与否）
    FIRST_COMPLETE = "first_complete"

class ProcessExecutionError(Exception):
    """自定义进程执行异常"""
    def __init__(self, message: str, element: Any = None):
        super().__init__(message)
        self.element = element
        self.message = message
    
    def __str__(self):
        if self.element:
            return f"{self.message} (element: {self.element})"
        return self.message

class ProcessResult:
    """并行任务执行结果"""
    def __init__(
            self, 
            element: Any, 
            status: str, 
            result: Any, 
            duration: float,
            process_id: int
        ):
        self.element = element
        self.status = status
        self.result = result
        self.duration = duration
        self.process_id = process_id
    
    def is_success(self) -> bool:
        return self.status == "SUCCESS"
    
    def is_failure(self) -> bool:
        return self.status == "FAILED"
    
    def __repr__(self) -> str:
        return (
            f"ProcessResult(element={self.element}, status={self.status}, "
            f"duration={self.duration:.4f}s, pid={self.process_id})"
        )

class SafeSignalHandler:
    """安全信号处理器，确保异常处理中不被中断"""
    def __init__(self):
        self.signals_received = []
        self.original_handlers = {}
    
    def __enter__(self):
        # 捕获常见信号
        signals = [signal.SIGINT, signal.SIGTERM]
        for sig in signals:
            self.original_handlers[sig] = signal.signal(sig, self.signal_handler)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 恢复原始信号处理
        for sig, handler in self.original_handlers.items():
            signal.signal(sig, handler)
    
    def signal_handler(self, signum, frame):
        """信号处理函数"""
        signal_name = signal.Signals(signum).name
        logger.warning(f"接收到信号: {signal_name}")
        self.signals_received.append((signum, frame))

class ParallelProcessor(Process):
    """并行处理器"""
    def __init__(
            self, 
            function: Callable,
            element: Any,
            params: Dict[str, Any],
            queue: Queue,
            timeout: Optional[float] = None,
            processor_name: str = None
        ):
        # 初始化进程
        super().__init__(daemon=True)
        self.function = function
        self.element = element
        self.params = params
        self.queue = queue
        self.timeout = timeout
        self.processor_name = processor_name or f"{function.__name__}_{element}"
    
    @property
    def description(self) -> str:
        """获取处理器描述信息"""
        return f"处理器 '{self.processor_name}' (元素: {self.element})"
    
    def run(self) -> None:
        """核心运行方法"""
        start_time = time.monotonic()
        result = None
        status = "SUCCESS"
        exception_info = None
        pid = self.pid
        
        try:
            logger.debug(f"{self.description} 开始执行 (PID={pid})")
            
            # 带有超时控制的执行
            if self.timeout:
                with SafeSignalHandler() as signal_handler:
                    # 创建管理器处理带超时的执行
                    with Manager() as manager:
                        result_queue = manager.Queue(1)
                        worker = Process(
                            target=self._run_worker,
                            args=(result_queue,)
                        )
                        worker.start()
                        worker.join(timeout=self.timeout)
                        
                        if worker.is_alive():
                            worker.terminate()
                            worker.join()
                            raise TimeoutError(
                                f"{self.description} 超时 ({self.timeout} 秒)"
                            )
                        
                        if not result_queue.empty():
                            result = result_queue.get()
            
            # 不带超时的执行
            else:
                result = self.function(self.element, self.params)
            
            # 计算执行时间
            duration = time.monotonic() - start_time
            logger.debug(
                f"{self.description} 成功完成 "
                f"(结果: {str(result)[:100]}, 耗时: {duration:.4f}秒)"
            )
        
        except TimeoutError as e:
            duration = time.monotonic() - start_time
            status = "TIMEOUT"
            exception_info = str(e)
            logger.error(f"{self.description} 执行超时 ({self.timeout} 秒)")
        
        except Exception as e:
            duration = time.monotonic() - start_time
            status = "FAILED"
            exception_info = traceback.format_exc()
            logger.error(
                f"{self.description} 执行失败: {str(e)}\n{exception_info}",
                exc_info=False
            )
        
        # 发送结果到队列
        self.queue.put(ProcessResult(
            element=self.element,
            status=status,
            result=result if status == "SUCCESS" else exception_info,
            duration=duration,
            process_id=pid
        ))
    
    def _run_worker(self, result_queue: Queue) -> None:
        """实际的工作函数（在单独进程中运行）"""
        try:
            result = self.function(self.element, self.params)
            result_queue.put(("SUCCESS", result))
        except Exception as e:
            result_queue.put(("FAILED", traceback.format_exc()))

def execute_in_parallel(
        function: Callable,
        elements: List[Any],
        params: Optional[Dict[str, Any]] = None,
        execution_type: ProcessType = ProcessType.ALL_COMPLETE,
        max_workers: Optional[int] = None,
        per_process_timeout: Optional[float] = None,
        poll_interval: float = 0.1,
        progress_callback: Optional[Callable] = None
    ) -> Dict[Any, ProcessResult]:
    """
    并行执行任务
    
    参数:
        function: 要执行的函数 (element, params) -> result
        elements: 要处理的元素列表
        params: 额外的函数参数
        execution_type: 执行模式:
            ALL_COMPLETE - 所有元素处理完成（默认）
            FIRST_SUCCESS - 第一个成功后停止所有进程
            FIRST_COMPLETE - 第一个完成（无论成功与否）后停止所有进程
        max_workers: 最大并行进程数 (默认为CPU核心数)
        per_process_timeout: 单个任务的超时时间（秒）
        poll_interval: 结果轮询间隔（秒）
        progress_callback: 进度回调函数 (completed, total) -> None
    
    返回:
        Dict[Any, ProcessResult]: 每个元素的执行结果
    """
    logger.info(
        f"开始并行处理 {len(elements)} 个元素 (执行模式: {execution_type.name}, "
        f"超时: {per_process_timeout or '无'}, 最大进程数: {max_workers or '自动'})"
    )
    
    # 参数初始化
    params = params or {}
    max_workers = max_workers or min(len(elements), cpu_count() or 4)
    queue = Queue()
    processes: Dict[Any, ParallelProcessor] = {}
    results: Dict[Any, ProcessResult] = {}
    
    # 跟踪已完成元素
    completed_count = 0
    total_elements = len(elements)
    
    # 创建所有进程对象
    elements_to_process = list(elements)
    elements_processed = set()
    
    # 创建初始进程
    for i in range(min(max_workers, len(elements_to_process))):
        element = elements_to_process.pop(0)
        process = ParallelProcessor(
            function=function,
            element=element,
            params=params,
            queue=queue,
            timeout=per_process_timeout,
            processor_name=f"Worker{i+1}"
        )
        processes[process.process_id] = process
        process.start()
        logger.debug(f"启动进程处理元素: {element} (PID={process.process_id})")
    
    # 主处理循环
    try:
        while processes:
            # 等待结果
            try:
                result: ProcessResult = queue.get(True, poll_interval)
            except Exception:
                # 检查是否收到终止信号
                for pid, process in list(processes.items()):
                    if not process.is_alive():
                        try:
                            process.join()
                            logger.debug(f"进程 {pid} 已退出")
                            if pid not in results:
                                # 处理未返回结果但进程终止的情况
                                results[process.element] = ProcessResult(
                                    element=process.element,
                                    status="UNKNOWN",
                                    result="进程终止但未返回结果",
                                    duration=0.0,
                                    process_id=pid
                                )
                        except:
                            pass
                        processes.pop(pid, None)
                continue
            
            # 记录结果
            element = result.element
            results[element] = result
            elements_processed.add(element)
            completed_count += 1
            
            # 调用进度回调
            if progress_callback:
                progress_callback(completed_count, total_elements)
            
            # 检查是否满足终止条件
            terminate_all = False
            if execution_type == ProcessType.FIRST_SUCCESS:
                if result.is_success():
                    logger.info(f"元素 {element} 成功执行，终止所有进程")
                    terminate_all = True
            
            elif execution_type == ProcessType.FIRST_COMPLETE:
                logger.info(f"元素 {element} 第一个完成，终止所有进程")
                terminate_all = True
            
            # 处理终止信号
            if terminate_all:
                # 停止所有活动进程
                for pid, process in processes.items():
                    if process.is_alive():
                        logger.warning(f"终止进程 (PID={pid})")
                        process.terminate()
                processes.clear()
                # 从队列中取出所有剩余结果
                while not queue.empty():
                    try:
                        remaining_result = queue.get_nowait()
                        results[remaining_result.element] = remaining_result
                        elements_processed.add(remaining_result.element)
                        completed_count += 1
                    except: 
                        break
                break
            
            # 移除已完成进程
            processes.pop(result.process_id, None)
            
            # 添加新进程（如果还有待处理元素）
            if elements_to_process and not (terminate_all or processes):
                element = elements_to_process.pop(0)
                process = ParallelProcessor(
                    function=function,
                    element=element,
                    params=params,
                    queue=queue,
                    timeout=per_process_timeout,
                    processor_name=f"Worker{len(processes)}"
                )
                processes[process.process_id] = process
                process.start()
                logger.debug(f"启动进程处理元素: {element} (PID={process.process_id})")
    
    except KeyboardInterrupt:
        logger.warning("用户中断，终止所有进程")
        for pid, process in processes.items():
            if process.is_alive():
                logger.warning(f"终止进程 (PID={pid})")
                process.terminate()
    
    finally:
        # 确保所有进程都已终止
        for pid, process in processes.items():
            if process.is_alive():
                logger.warning(f"强制终止进程 (PID={pid})")
                process.terminate()
    
    # 分析结果
    success_count = sum(1 for r in results.values() if r.is_success())
    failed_count = sum(1 for r in results.values() if r.is_failure())
    
    logger.info(
        f"并行处理完成。成功: {success_count}, 失败: {failed_count}, "
        f"总共: {len(results)}, 执行模式: {execution_type.name}"
    )
    
    # 返回处理结果
    return results

def analyze_results(
        results: Dict[Any, ProcessResult], 
        raise_on_error: bool = False
    ) -> Tuple[List[Any], List[Any], List[Any]]:
    """
    分析并行处理结果
    
    返回:
        (success_list, failed_list, timed_out_list)
    """
    success = []
    failed = []
    timed_out = []
    
    for element, result in results.items():
        if result.status == "SUCCESS":
            success.append((result.element, result.result))
        elif result.status == "TIMEOUT":
            timed_out.append(element)
        else:
            failed.append((element, result.result))
    
    # 有失败时选择是否抛出异常
    if raise_on_error and (failed or timed_out):
        error_messages = []
        for element, error in failed:
            error_messages.append(f"{element}: {error}")
        for element in timed_out:
            error_messages.append(f"{element}: 进程超时")
        
        raise ProcessExecutionError(
            f"{len(failed)} 个任务失败, {len(timed_out)} 个任务超时",
            details=dict(failed=failed, timed_out=timed_out)
        )
    
    return success, failed, timed_out

# ================ 示例用法 ================
def sample_task(element: str, params: dict) -> str:
    """示例任务函数"""
    # 模拟不同类型的任务行为
    task_type = params.get('type', 'normal')
    sleep_time = params.get('sleep', 0.5)
    
    # 模拟异常行为
    if element == "EXPLODE":
        raise ValueError("元素要求模拟爆炸错误")
    
    # 模拟超长任务
    if element == "SLEEPY":
        sleep_time = 3.0
    
    # 执行任务
    name = params.get('name', 'sample_task')
    logger.info(f"[{name}] 处理元素: {element} (耗时: {sleep_time}秒)")
    time.sleep(sleep_time)
    
    # 生成结果
    if task_type == "upper":
        return element.upper()
    elif task_type == "reverse":
        return element[::-1]
    else:
        return f"{element}_processed"

def progress_reporter(completed: int, total: int):
    """进度报告回调函数"""
    print(f"\r进度: {completed}/{total} ({completed/total*100:.1f}%)", end='', flush=True)

if __name__ == "__main__":
    # 1. 普通测试 - 所有元素完成
    print("\n测试1: 所有元素完成")
    task_params = {"type": "upper", "sleep": 0.3, "name": "测试1"}
    sample_elements = ["apple", "banana", "cherry", "date", "elderberry"]
    
    results = execute_in_parallel(
        function=sample_task,
        elements=sample_elements,
        params=task_params,
        execution_type=ProcessType.ALL_COMPLETE,
        max_workers=2,
        per_process_timeout=1.0,
        progress_callback=progress_reporter
    )
    
    success, failed, timed_out = analyze_results(results)
    print("\n\n成功任务:", [elem for elem, _ in success])
    print("失败任务:", [elem for elem, _ in failed])
    print("超时任务:", timed_out)
    
    # 2. 测试失败情况
    print("\n测试2: 包含失败元素")
    error_elements = ["valid1", "EXPLODE", "valid2", "SLEEPY"]
    task_params["name"] = "测试2"
    
    results = execute_in_parallel(
        function=sample_task,
        elements=error_elements,
        params=task_params,
        execution_type=ProcessType.ALL_COMPLETE,
        max_workers=3,
        per_process_timeout=1.0,
        progress_callback=progress_reporter
    )
    
    try:
        success, failed, timed_out = analyze_results(results, raise_on_error=True)
    except ProcessExecutionError as e:
        print(f"\n捕获错误: {e}")
        # 在实际应用中处理错误
    
    # 3. 测试 FIRST_SUCCESS 模式
    print("\n测试3: FIRST_SUCCESS 模式")
    target_elements = ["task1", "target_task", "task3", "task4"]
    task_params.update({"name": "测试3", "sleep": 0.2})
    
    print("正常启动模式:")
    results = execute_in_parallel(
        function=sample_task,
        elements=target_elements,
        params=task_params,
        execution_type=ProcessType.FIRST_SUCCESS,
        max_workers=4
    )
    print(f"实际完成: {len(results)} (预期应少于{len(target_elements)})")
    
    # 4. 测试 FIRST_COMPLETE 模式
    print("\n测试4: FIRST_COMPLETE 模式")
    mixed_elements = ["slow_task", "fast_task", "faster_task", "slowest_task"]
    task_params.update({"name": "测试4", "sleep": 0.0})
    
    for i, elem in enumerate(mixed_elements):
        task_params['sleep'] = 0.5 * (len(mixed_elements) - i)
        print(f"任务 '{elem}' 耗时: {task_params['sleep']}秒")
    
    results = execute_in_parallel(
        function=sample_task,
        elements=mixed_elements,
        params=task_params,
        execution_type=ProcessType.FIRST_COMPLETE,
        max_workers=4
    )
    
    completed_elements = list(results.keys())
    print(f"完成元素: {completed_elements}")
    print(f"第一个完成的元素: {completed_elements[0]} (预期: 'fast_task' 或 'faster_task')")
