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
import logging
import threading
import traceback
import time
import signal
import platform
import enum
from typing import Callable, Any, Dict, Optional

# 配置日志
logger = logging.getLogger("SignalHandler")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class SignalHandlerError(Exception):
    """信号处理异常基类"""
    pass

class SignalType(enum.Enum):
    """支持的信号类型"""
    STOP = 0
    HEARTBEAT = 1
    RELOAD_CONFIG = 2
    DEBUG = 3
    METRICS = 4

class OSFamily(enum.Enum):
    """操作系统类型标识"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "darwin"
    UNIX = "unix"
    UNKNOWN = "unknown"

class EventManager:
    """线程安全事件管理系统"""
    def __init__(self):
        self._events: Dict[SignalType, threading.Event] = {}
        self._event_lock = threading.Lock()
        
    def register_event(self, signal_type: SignalType) -> threading.Event:
        """注册并返回特定事件"""
        with self._event_lock:
            if signal_type not in self._events:
                self._events[signal_type] = threading.Event()
            return self._events[signal_type]
    
    def set_event(self, signal_type: SignalType):
        """触发指定事件"""
        event = self.register_event(signal_type)
        event.set()
    
    def clear_event(self, signal_type: SignalType):
        """清除指定事件"""
        event = self.register_event(signal_type)
        event.clear()
    
    def wait_for_event(self, signal_type: SignalType, timeout=None):
        """等待指定事件发生"""
        event = self.register_event(signal_type)
        return event.wait(timeout)
    
    def is_set(self, signal_type: SignalType) -> bool:
        """检查事件是否已设置"""
        event = self.register_event(signal_type)
        return event.is_set()

class CrossPlatformSignalHandler:
    """跨平台信号处理服务
    
    提供统一接口处理多种系统信号：
    - 优雅停止控制
    - 心跳信号处理
    - 调试信号管理
    - 实时指标收集
    - 配置热重载
    
    支持多种操作系统：Linux, Windows, macOS等
    """
    
    def __init__(self):
        self.os_family = self.detect_os_family()
        self.event_manager = EventManager()
        self.callbacks = {}
        self.stop_requested = False
        logger.info(f"信号处理器已初始化 - 操作系统: {self.os_family.value}")
    
    @staticmethod
    def detect_os_family() -> OSFamily:
        """检测操作系统类型"""
        system_name = platform.system().lower()
        if system_name == "linux":
            return OSFamily.LINUX
        elif system_name == "windows":
            return OSFamily.WINDOWS
        elif system_name == "darwin":
            return OSFamily.MACOS
        elif system_name.startswith("aix") or "bsd" in system_name:
            return OSFamily.UNIX
        return OSFamily.UNKNOWN

    def register_callback(self, signal_type: SignalType, callback: Callable):
        """注册信号回调函数"""
        self.callbacks[signal_type] = callback
        logger.debug(f"已注册 {signal_type.name} 的回调函数")

    def bind_signals(self):
        """绑定操作系统信号"""
        if self.os_family in (OSFamily.LINUX, OSFamily.MACOS, OSFamily.UNIX):
            self._bind_unix_signals()
        elif self.os_family == OSFamily.WINDOWS:
            self._bind_windows_signals()
        else:
            logger.warning("不支持的操作系统类型，无法绑定信号处理器")

    def _bind_unix_signals(self):
        """绑定Unix-like系统的信号处理器"""
        try:
            # 优雅停止信号
            signal.signal(signal.SIGTERM, self.handle_term_signal)
            signal.signal(signal.SIGINT, self.handle_term_signal)
            
            # 配置重载信号
            signal.signal(signal.SIGHUP, self.handle_reload_signal)
            
            # 调试信号
            signal.signal(signal.SIGUSR1, self.handle_debug_signal)
            signal.signal(signal.SIGUSR2, self.handle_metrics_signal)
            
            logger.info("Unix信号处理器已成功绑定")
        except ValueError as e:
            logger.error(f"绑定Unix信号处理器失败: {str(e)}")
            raise SignalHandlerError("信号处理器绑定失败")

    def _bind_windows_signals(self):
        """绑定Windows系统的信号处理器"""
        try:
            if sys.platform == "win32":
                import win32api
                win32api.SetConsoleCtrlHandler(self.handle_windows_signal, True)
                logger.info("Windows控制台信号处理器已注册")
        except ImportError:
            logger.warning("缺少win32api库，无法创建Windows控制台处理器")
        except Exception as e:
            logger.error(f"绑定Windows信号处理器失败: {str(e)}")

    def handle_windows_signal(self, sig_type):
        """Windows控制台信号处理器"""
        # Windows控制台事件映射
        CTRL_EVENTS = {
            0: SignalType.STOP,        # CTRL_C_EVENT
            1: SignalType.STOP,        # CTRL_BREAK_EVENT
            2: SignalType.DEBUG,       # CTRL_CLOSE_EVENT
            5: SignalType.HEARTBEAT,   # CTRL_LOGOFF_EVENT
            6: SignalType.STOP         # CTRL_SHUTDOWN_EVENT
        }
        
        if sig_type in CTRL_EVENTS:
            event_type = CTRL_EVENTS[sig_type]
            logger.info(f"收到Windows控制台信号: {event_type.name}")
            self._process_signal(event_type)
            return True  # 表示处理了信号
        return False  # 表示未处理信号

    def handle_term_signal(self, signum, frame):
        """处理终止信号 (SIGTERM, SIGINT)"""
        logger.info(f"收到终止信号: {signal.Signals(signum).name}")
        self._process_signal(SignalType.STOP)

    def handle_reload_signal(self, signum, frame):
        """处理配置重载信号 (SIGHUP)"""
        logger.info(f"收到配置重载信号: SIGHUP")
        self._process_signal(SignalType.RELOAD_CONFIG)

    def handle_debug_signal(self, signum, frame):
        """处理调试信号 (SIGUSR1)"""
        logger.info(f"收到调试信号: SIGUSR1")
        self._process_signal(SignalType.DEBUG, frame=frame)

    def handle_metrics_signal(self, signum, frame):
        """处理指标收集信号 (SIGUSR2)"""
        logger.info(f"收到指标收集信号: SIGUSR2")
        self._process_signal(SignalType.METRICS)

    def send_heartbeat(self):
        """发送心跳信号"""
        self._process_signal(SignalType.HEARTBEAT)
        logger.debug("心跳信号已发送")

    def _process_signal(self, signal_type: SignalType, frame=None):
        """处理信号的核心逻辑"""
        # 触发事件通知
        self.event_manager.set_event(signal_type)
        
        # 执行注册的回调函数
        callback = self.callbacks.get(signal_type)
        if callback:
            try:
                # 捕获回溯信息用于调试
                debug_info = traceback.format_stack(frame) if frame else []
                if debug_info:
                    logger.debug(f"回溯信息:\n{''.join(debug_info)}")
                
                callback(signal_type)
            except Exception as e:
                logger.exception(f"处理信号 {signal_type} 的回调函数时出错: {str(e)}")
        
        # 特殊处理：停止信号
        if signal_type == SignalType.STOP:
            self.stop_requested = True
            logger.info("停止信号已处理，服务终止中...")

    def wait_for_signal(self, signal_types: list, timeout: float = None) -> Optional[SignalType]:
        """等待指定信号发生"""
        if not signal_types:
            return None
        
        # 创建复合等待事件
        stop_condition = threading.Event()
        stop_condition.clear()
        
        def trigger_condition():
            """检查信号条件是否满足"""
            for st in signal_types:
                if self.event_manager.is_set(st):
                    stop_condition.set()
                    return True
            return False
        
        # 设置等待超时
        start_time = time.time()
        remaining_time = timeout
        
        while True:
            # 检查条件
            if trigger_condition():
                for st in signal_types:
                    if self.event_manager.is_set(st):
                        self.event_manager.clear_event(st)
                        return st
            
            # 超时检查
            if timeout is not None:
                elapsed = time.time() - start_time
                remaining_time = timeout - elapsed
                if remaining_time <= 0:
                    return None
            
            # 避免CPU满载
            wait_time = min(0.5, remaining_time) if timeout else 0.5
            stop_condition.wait(wait_time)
            stop_condition.clear()

    def run_heartbeat_cycle(self, heartbeat_interval: float, task: Callable):
        """执行周期性心跳任务"""
        while not self.stop_requested:
            if self.wait_for_signal([SignalType.STOP], heartbeat_interval) is not None:
                break
            
            try:
                self.send_heartbeat()
                task()  # 执行心跳任务
            except Exception as e:
                logger.exception(f"心跳任务执行失败: {str(e)}")
                # 失败后等待较短时间后重试
                time.sleep(5)

    def generate_debug_report(self, frame=None) -> str:
        """生成调试报告"""
        report = []
        report.append(f"=== 调试报告 {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        report.append(f"操作系统: {platform.system()} {platform.release()}")
        report.append(f"Python版本: {platform.python_version()}")
        report.append(f"当前工作目录: {os.getcwd()}")
        report.append(f"命令行参数: {' '.join(sys.argv)}")
        
        # 活动线程信息
        report.append("\n*** 活动线程信息 ***")
        for thread_id, thread in threading._active_items():
            report.append(f"Thread {thread_id}: {thread.name} - {'Alive' if thread.is_alive() else 'Dead'}")
        
        # 内存信息（简化）
        try:
            import psutil
            mem = psutil.virtual_memory()
            report.append(f"\n内存使用: {mem.percent}% ({mem.used/1024/1024:.2f} MB / {mem.total/1024/1024:.2f} MB)")
        except ImportError:
            pass
        
        # 堆栈回溯信息
        if frame:
            report.append("\n*** 堆栈回溯 ***")
            report.extend(traceback.format_stack(frame))
        
        return "\n".join(report)


# 使用示例
if __name__ == "__main__":
    handler = CrossPlatformSignalHandler()
    
    # 注册回调函数
    def stop_callback(sig_type):
        print(f"收到停止信号: {sig_type.name}")
        # 执行清理操作...
    
    def reload_callback(sig_type):
        print(f"收到配置重载信号: {sig_type.name}")
        # 重载配置...
    
    handler.register_callback(SignalType.STOP, stop_callback)
    handler.register_callback(SignalType.RELOAD_CONFIG, reload_callback)
    
    # 绑定信号处理器
    handler.bind_signals()
    
    # 自定义心跳任务
    def heartbeat_task():
        print(f"心跳 - {time.strftime('%H:%M:%S')}")
    
    print("服务运行中. 使用:")
    print("  - CTRL+C 或 kill-sigterm 停止")
    print("  - kill-sighup 重载配置")
    print("  - kill-sigusr1 触发调试")
    
    # 运行心跳循环
    try:
        handler.run_heartbeat_cycle(heartbeat_interval=5.0, task=heartbeat_task)
    except KeyboardInterrupt:
        print("手动停止请求已收到")
    
    print("服务已安全停止")
