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

import sys
import signal
import os
import traceback
import codeop
import io
import pickle
import tempfile
import shutil
import logging
import platform
from pathlib import Path
from types import FrameType
from typing import Optional, Tuple, Dict, Any

# 设置日志记录
logger = logging.getLogger(__name__)

def bind_debug_signal_handlers():
    """将调试信号绑定到处理函数"""
    if signal.getsignal(signal.SIGUSR1) == signal.SIG_DFL:
        signal.signal(signal.SIGUSR1, print_threads_stack_traces)
        
    if signal.getsignal(signal.SIGUSR2) == signal.SIG_DFL:
        signal.signal(signal.SIGUSR2, remote_debug)
    
    # Windows 系统特殊处理
    if platform.system() == 'Windows':
        logger.info("Windows 系统不支持 SIGUSR1/SIGUSR2 信号")
        
    logger.debug("调试信号处理器已绑定")

def print_threads_stack_traces(sig: int, frame: FrameType):
    """打印当前所有线程的堆栈跟踪信息到错误流
    
    Args:
        sig: 信号编号
        frame: 当前堆栈帧
    """
    logger.debug("接收到 SIGUSR1 信号，打印线程堆栈跟踪")
    sys.stderr.flush()
    
    # 使用缓冲构建堆栈跟踪信息
    buffer = io.StringIO()
    buffer.write("\n*** STACKTRACE - START ***\n")
    buffer.write(f"Process: {os.getpid()} ({os.getpid()})\n")
    buffer.write(f"Platform: {platform.platform()}\n\n")
    
    # 收集所有线程的堆栈跟踪
    for thread_id, stack in sys._current_frames().items():
        buffer.write(f"\n## Thread ID: {thread_id}\n")
        for line in traceback.format_stack(stack):
            buffer.write(line)
            
    buffer.write("\n*** STACKTRACE - END ***\n")
    buffer.write("\n")
    
    # 一次性写入错误流
    sys.stderr.write(buffer.getvalue())
    sys.stderr.flush()

def pipename(pid: int) -> str:
    """生成管道基础名称
    
    Args:
        pid: 进程ID
        
    Returns:
        管道基础路径
    """
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, f"cloud-debug-{pid}")

class NamedPipe:
    """通过命名管道进行安全进程间通信"""
    
    BUFFER_SIZE = 2048  # 读操作缓冲区大小
    
    def __init__(self, name: str, server_end: bool = False):
        """初始化命名管道
        
        Args:
            name: 管道基础名称
            server_end: 是否作为服务器端
        """
        self.name = name
        self.in_pipe = f"{name}.in"
        self.out_pipe = f"{name}.out"
        self._server_end = server_end
        
        # 确保管道文件不存在
        self._clean_pipes()
        
        # 创建管道文件
        try:
            os.mkfifo(self.in_pipe, mode=0o600)
            os.mkfifo(self.out_pipe, mode=0o600)
            logger.debug("创建命名管道: %s.in 和 %s.out", name, name)
        except FileExistsError:
            # 管道已存在，可能从之前的会话遗留
            logger.debug("命名管道已存在: %s", name)
        except Exception as e:
            logger.error("创建命名管道失败: %s", e)
            raise
        
        # 根据角色打开管道
        if server_end:
            # 服务器端: 读取管道输入，写入管道输出
            self.out_file = open(self.in_pipe, 'w', buffering=1)
            self.in_file = open(self.out_pipe, 'r', buffering=1)
        else:
            # 客户端: 写入管道输入，读取管道输出
            self.in_file = open(self.in_pipe, 'r', buffering=1)
            self.out_file = open(self.out_pipe, 'w', buffering=1)
        
        logger.debug("成功打开命名管道: %s", name)
    
    def is_open(self) -> bool:
        """检查管道是否仍打开"""
        return not (self.in_file.closed or self.out_file.closed)
    
    def put(self, obj: Any):
        """序列化并发送对象
        
        Args:
            obj: 要发送的Python对象
        """
        try:
            data = pickle.dumps(obj)
            self.out_file.write(f"{len(data)}\n")
            self.out_file.write(data.decode('latin1'))
            self.out_file.flush()
            logger.debug("发送数据: %d 字节", len(data))
        except (BrokenPipeError, OSError) as e:
            logger.debug("发送数据时管道断开: %s", e)
            self.close()
        except Exception as e:
            logger.error("发送数据失败: %s", e)
            self.close()
    
    def get(self) -> Optional[Any]:
        """接收并反序列化对象
        
        Returns:
            反序列化的对象，或管道关闭时为 None
        """
        try:
            # 读取第一行获取数据长度
            size_line = self.in_file.readline()
            if not size_line:
                logger.debug("读取大小行时遇到EOF")
                self.close()
                return None
                
            data_size = int(size_line.strip())
            logger.debug("等待接收 %d 字节数据", data_size)
            
            # 读取序列化数据
            data = self.in_file.read(data_size)
            if len(data) < data_size:
                logger.warning("数据不完整: 期待 %d 字节, 接收 %d 字节", data_size, len(data))
                self.close()
                return None
                
            logger.debug("成功接收 %d 字节数据", len(data))
            return pickle.loads(data.encode('latin1'))
        except (BrokenPipeError, OSError) as e:
            logger.debug("接收数据时管道断开: %s", e)
            self.close()
        except Exception as e:
            logger.error("接收数据失败: %s", e, exc_info=True)
            self.close()
        
        return None
    
    def close(self):
        """安全关闭管道和清理资源"""
        # 关闭文件句柄
        if hasattr(self, 'in_file') and not self.in_file.closed:
            self.in_file.close()
        
        if hasattr(self, 'out_file') and not self.out_file.closed:
            self.out_file.close()
        
        # 清理管道文件
        self._clean_pipes()
    
    def _clean_pipes(self):
        """移除管道文件（如果存在）"""
        for pipe_path in [self.in_pipe, self.out_pipe]:
            if os.path.exists(pipe_path):
                try:
                    os.remove(pipe_path)
                    logger.debug("已清理管道文件: %s", pipe_path)
                except Exception as e:
                    logger.warning("清理管道文件失败 %s: %s", pipe_path, e)
    
    def __enter__(self):
        """支持上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """退出上下文时清理资源"""
        self.close()
        # 不捕获异常，允许传播
        return False

def remote_debug(sig: int, frame: FrameType):
    """远程调试信号处理函数
    
    Args:
        sig: 信号编号
        frame: 当前堆栈帧
    """
    logger.info("接收到 SIGUSR2 信号，开启远程调试会话")
    
    # 保存原始标准流
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # 准备临时流
    temp_pipe = None
    
    try:
        pid = os.getpid()
        debug_session = DebugSession(frame, pid)
        debug_session.start()
    except Exception as e:
        # 确保原始流在异常情况下恢复
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        # 记录错误但不要中断主进程
        logger.critical("远程调试会话初始化失败: %s", e, exc_info=True)
        traceback.print_exc(file=sys.stderr)

class DebugSession:
    """管理远程调试会话状态"""
    
    def __init__(self, frame: FrameType, pid: int):
        self.frame = frame
        self.pid = pid
        self.locals = {}
        self.globals = frame.f_globals
        self.exit_exception = None
        self.pipe = None
    
    def start(self):
        """启动调试会话"""
        # 构建调试上下文
        self.locals = self._build_debug_context()
        
        logger.debug("在 PID %d 上启动调试会话", self.pid)
        logger.debug("堆栈位置:\n%s", ''.join(traceback.format_stack(self.frame)))
        
        # 使用上下文管理器处理管道
        try:
            with NamedPipe(pipename(self.pid), server_end=True) as pipe:
                self.pipe = pipe
                self._send_start_message()
                self._run_session()
        except Exception as e:
            # 确保在失败时清理
            logger.error("调试会话错误: %s", e, exc_info=True)
            raise
    
    def _build_debug_context(self) -> Dict:
        """构建调试上下文环境"""
        context = {
            "debug": True,  # 调试模式标志
            "__debug_session__": self,  # 提供对会话的访问
            "_raise": self._set_exit_exception  # 用于触发异常
        }
        
        # 添加当前栈帧的本地变量
        context.update(self.frame.f_locals)
        
        # 避免覆盖内置函数
        context.update({k: v for k, v in __builtins__.items() if k not in context})
        
        return context
    
    def _set_exit_exception(self, ex: Exception):
        """设置要在退出时引发的异常"""
        self.exit_exception = ex
        logger.debug("设置退出异常: %s", ex)
    
    def _send_start_message(self):
        """发送初始化消息给客户端"""
        stack_trace = "".join(traceback.format_stack(self.frame))
        banner = f"""
        ==== Cloud Debug Console (PID: {self.pid}) ====
        Type 'exit()' or Ctrl-D to end the session.
        Use '_raise(SomeException())' to raise an exception.
        Current stack position:
        {stack_trace}
        >>> 
        """.strip() + "\n>>> "
        
        self.pipe.put(banner)
    
    def _run_session(self):
        """运行调试会话主循环"""
        command_buffer = ""
        
        while self.pipe.is_open() and self.exit_exception is None:
            # 从管道获取输入
            line = self.pipe.get()
            if line is None:
                logger.debug("接收到空行，终止会话")
                break
                
            # 添加到命令缓冲区
            command_buffer += line + "\n"
            logger.debug("接收到的命令: %s", command_buffer.strip())
            
            # 尝试编译和执行
            try:
                code_obj = codeop.compile_command(command_buffer)
                if code_obj is not None:
                    # 重置缓冲区
                    command_buffer = ""
                    
                    # 重定向输出到缓冲区
                    output_buffer = io.StringIO()
                    sys.stdout = output_buffer
                    sys.stderr = output_buffer
                    
                    # 执行代码并捕获输出
                    try:
                        exec(code_obj, self.globals, self.locals)
                    except SystemExit:
                        logger.debug("调用了 sys.exit()")
                        break
                    except Exception as e:
                        logger.debug("执行命令错误: %s", e)
                        traceback.print_exc(file=sys.stdout)
                    
                    # 恢复标准输出
                    sys.stdout = sys.__stdout__
                    sys.stderr = sys.__stderr__
                    
                    # 发送输出结果
                    result = output_buffer.getvalue().rstrip() + "\n>>> "
                    self.pipe.put(result)
                else:
                    # 需要更多输入
                    self.pipe.put("... ")
            except SyntaxError as se:
                # 语法错误，重置缓冲区
                command_buffer = ""
                error_msg = f"Syntax Error: {se}\n>>> "
                self.pipe.put(error_msg)
                logger.debug("语法错误: %s", se)
            except ValueError as ve:
                # 编译错误
                command_buffer = ""
                error_msg = f"Compile Error: {ve}\n>>> "
                self.pipe.put(error_msg)
                logger.debug("编译错误: %s", ve)
    
    def end_session(self):
        """结束调试会话，必要时清理资源"""
        if self.exit_exception is not None:
            logger.debug("结束调试会话并引发异常: %s", self.exit_exception)
            raise self.exit_exception
