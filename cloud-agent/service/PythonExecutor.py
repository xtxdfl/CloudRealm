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

import logging
import os
import pprint
import threading
import sys
import time
import traceback

import cloud_simplejson as json

import subprocess
from cloud_commons import shell

from Grep import Grep
from BackgroundCommandExecutionHandle import BackgroundCommandExecutionHandle
from resource_management.libraries.functions.log_process_information import log_process_information

logger = logging.getLogger()


class PythonExecutor:
    """高效安全的Python脚本执行器，支持超时控制和后台执行"""
    
    NO_ERROR = "none"

    def __init__(self, tmp_dir, config):
        self.logger = logger
        self.grep = Grep()
        self.max_log_symbols = config.log_max_symbols_size
        self.tmp_dir = tmp_dir
        self.config = config
        self.pid_to_process = {}  # 用于跟踪PID与进程的映射
        self.lock = threading.Lock()  # 线程安全锁

    def open_subprocess_files(self, stdout_file, stderr_file, overwrite=True, backup_logs=True):
        """打开子进程的标准输出和标准错误文件"""
        if overwrite and backup_logs and os.path.exists(stdout_file):
            self.back_up_log_file(stdout_file)
        if overwrite and backup_logs and os.path.exists(stderr_file):
            self.back_up_log_file(stderr_file)
            
        mode = 'w' if overwrite else 'a'
        return open(stdout_file, mode), open(stderr_file, mode)

    @staticmethod
    def back_up_log_file(file_path):
        """备份现有的日志文件"""
        if not os.path.isfile(file_path):
            return
            
        base_name, extension = os.path.splitext(file_path)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        backup_path = f"{base_name}.bak_{timestamp}{extension}"
        os.rename(file_path, backup_path)

    def run_file(
        self,
        script,
        params,
        stdout_file,
        stderr_file,
        timeout,
        structured_outfile,
        callback,
        task_id,
        overwrite_logs=True,
        backup_logs=True,
        handle=None,
        log_failure_info=True
    ):
        """
        执行Python脚本文件
        
        参数说明：
        script: 要执行的Python脚本路径
        params: 传递给脚本的参数列表
        stdout_file: 标准输出日志文件路径
        stderr_file: 标准错误日志文件路径
        timeout: 执行超时时间（秒）
        structured_outfile: 结构化输出文件路径
        callback: 执行完成的回调函数
        task_id: 任务ID
        overwrite_logs: 是否覆盖现有日志文件
        backup_logs: 是否备份现有日志
        handle: 后台执行句柄
        log_failure_info: 失败时是否记录详细信息
        """
        command = self._build_command(script, params)
        
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("执行命令: %s", pprint.pformat(command))

        # 后台执行模式
        if handle:
            return self._run_in_background(
                command, stdout_file, stderr_file, structured_outfile, handle, task_id
            )
            
        # 前台执行模式
        return self._run_in_foreground(
            command, stdout_file, stderr_file, structured_outfile, timeout, 
            callback, task_id, overwrite_logs, backup_logs, log_failure_info
        )

    def _run_in_background(self, command, stdout_file, stderr_file, structured_outfile, handle, task_id):
        """后台执行Python脚本"""
        def executor():
            try:
                with self.lock:
                    if handle.status == BackgroundCommandExecutionHandle.CANCELLED_STATUS:
                        return
                        
                with self.open_subprocess_files(stdout_file, stderr_file) as (out_f, err_f):
                    proc = self._launch_subprocess(command, out_f, err_f)
                    
                    with self.lock:
                        if handle.status == BackgroundCommandExecutionHandle.CANCELLED_STATUS:
                            shell.kill_process_with_children(proc.pid)
                            return
                            
                        handle.pid = proc.pid
                        self.pid_to_process[proc.pid] = proc
                        handle.status = BackgroundCommandExecutionHandle.RUNNING_STATUS
                        handle.on_background_command_started(task_id, proc.pid)
                        
                    proc.communicate()  # 等待进程结束
                    
                    with self.lock:
                        handle.exitCode = proc.returncode
                        result = self._prepare_result(
                            proc.returncode, stdout_file, stderr_file, structured_outfile
                        )
                        handle.on_background_command_complete_callback(result, handle)
            except Exception as e:
                self.logger.error("后台执行错误 [task %s]: %s", task_id, str(e), exc_info=True)
                
        threading.Thread(target=executor, daemon=True).start()
        return {"exitcode": 777, "message": "启动后台执行"}

    def _run_in_foreground(
        self, command, stdout_file, stderr_file, structured_outfile, timeout, 
        callback, task_id, overwrite_logs, backup_logs, log_failure_info
    ):
        """前台执行Python脚本"""
        killed_by_timeout = False
        
        try:
            with self.open_subprocess_files(
                stdout_file, stderr_file, overwrite_logs, backup_logs
            ) as (out_f, err_f):
                proc = self._launch_subprocess(command, out_f, err_f)
                callback(task_id, proc.pid)
                
                # 启动看门狗线程监控超时
                watchdog = threading.Thread(
                    target=self._watchdog, args=(proc, timeout), daemon=True
                )
                watchdog.start()
                
                try:
                    # 等待进程完成
                    proc.communicate()
                finally:
                    killed_by_timeout = self._is_timed_out(proc)
                
                # 确保看门狗线程退出
                watchdog.join(timeout=1.0)
                
                if watchdog.is_alive():
                    self.logger.warning("看门狗线程未及时退出")
                
                result = self._prepare_result(
                    proc.returncode, stdout_file, stderr_file, structured_outfile, 
                    killed_by_timeout, timeout
                )
                
                if log_failure_info and result["exitcode"] != 0:
                    self._log_failure_details(command, result)
                    
                return result
        except Exception as e:
            self.logger.error("前台执行错误 [task %s]: %s", task_id, str(e), exc_info=True)
            return {
                "exitcode": 999,
                "stderr": f"执行错误: {str(e)}\n{traceback.format_exc()}",
                "stdout": "",
                "structuredOut": {}
            }

    def _watchdog(self, process, timeout):
        """监控进程执行时间，超时则终止进程"""
        if timeout <= 0:  # 没有超时设置
            return
            
        start_time = time.monotonic()
        while process.poll() is None:  # 进程仍在运行
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                try:
                    self.logger.warning("进程 %d 超时 (%d秒), 被终止", process.pid, timeout)
                    shell.kill_process_with_children(process.pid)
                    return
                except Exception:
                    return
            time.sleep(0.5)  # 间隔检查

    def _is_timed_out(self, process):
        """检查进程是否因超时被终止"""
        if process.returncode is None:
            return False
            
        # 通常，我们终止的进程会有特定的退出码
        return process.returncode < 0 or process.returncode == 999

    def _prepare_result(
        self, exitcode, stdout_file, stderr_file, structured_outfile, 
        killed_by_timeout=False, timeout=None
    ):
        """处理执行结果并返回结构化的响应"""
        stdout, stderr, structured_out = self._read_output_files(
            stdout_file, stderr_file, structured_outfile
        )
        
        if killed_by_timeout:
            stderr += f"\nERROR: 进程因超时被终止 (timeout={timeout}秒)"
            exitcode = 999
            
        # 截断大日志
        if self.max_log_symbols:
            stdout = self.grep.tail_by_symbols(stdout, self.max_log_symbols)
            stderr = self.grep.tail_by_symbols(stderr, self.max_log_symbols)
            
        return {
            "exitcode": exitcode,
            "stdout": stdout,
            "stderr": stderr,
            "structuredOut": structured_out,
            "killedByTimeout": killed_by_timeout
        }

    def _read_output_files(self, stdout_file, stderr_file, structured_outfile):
        """从文件中读取标准输出、标准错误和结构化输出"""
        def read_file(file_path):
            try:
                if os.path.exists(file_path) and os.path.getsize(file_path) < 100 * 1024 * 1024:  # 100MB限制
                    with open(file_path, 'r') as f:
                        return f.read()
                return "[文件过大，未读取完整内容]"
            except Exception as e:
                self.logger.warning("读取文件 %s 失败: %s", file_path, str(e))
                return f"[文件读取失败: {str(e)}]"
                
        # 结构化输出处理
        def read_structured(file_path):
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        return json.load(f)
                return {}
            except json.JSONDecodeError:
                return {"error": "结构化输出格式错误", "file": file_path}
            except Exception as e:
                return {"error": f"读取结构化输出失败: {str(e)}"}
        
        return (
            read_file(stdout_file),
            read_file(stderr_file),
            read_structured(structured_outfile)
        )

    def _log_failure_details(self, command, result):
        """记录任务失败的详细信息"""
        self.logger.error(
            "命令执行失败: \n命令: %s\n退出码: %d",
            pprint.pformat(command),
            result["exitcode"]
        )
        
        short_stderr = self.grep.tail_by_symbols(result["stderr"], 1000) if result["stderr"] else ""
        if short_stderr:
            self.logger.error("错误摘要: %s", short_stderr)
            
        log_process_information(self.logger)

    def cancel_background_task(self, handle):
        """取消后台任务"""
        if not handle or not handle.pid:
            return False
            
        self.logger.info("取消后台任务 [pid: %s]", handle.pid)
        
        with self.lock:
            if handle.status != BackgroundCommandExecutionHandle.RUNNING_STATUS:
                return False
                
            handle.status = BackgroundCommandExecutionHandle.CANCELLED_STATUS
            handle.cancel_time = time.time()
            
            try:
                if handle.pid in self.pid_to_process:
                    proc = self.pid_to_process[handle.pid]
                    if proc.poll() is None:  # 仍在运行
                        shell.kill_process_with_children(handle.pid)
                        return True
            except Exception as e:
                self.logger.error("取消任务失败 [pid %s]: %s", handle.pid, str(e))
                
        return False

    def _build_command(self, script, params):
        """构建Python执行命令"""
        return [sys.executable, script] + params

    def _launch_subprocess(self, command, stdout, stderr):
        """启动子进程"""
        env = dict(os.environ)
        try:
            # 创建新的进程组，便于整体终止
            return subprocess.Popen(
                command,
                stdout=stdout,
                stderr=stderr,
                close_fds=True,
                env=env,
                start_new_session=True,  # 创建新会话/进程组
            )
        except Exception as e:
            self.logger.error("启动子进程失败: %s", str(e))
            raise

    def cleanup(self):
        """清理资源，终止所有子进程"""
        self.logger.info("清理执行器资源...")
        with self.lock:
            for pid, proc in list(self.pid_to_process.items()):
                if proc.poll() is None:  # 仍在运行
                    try:
                        os.killpg(os.getpgid(pid), 9)
                        self.logger.warning("强制终止运行中的进程: %s", pid)
                    except Exception:
                        pass
            self.pid_to_process.clear()

    def __del__(self):
        """析构函数 - 确保清理资源"""
        try:
            self.cleanup()
        except Exception:
            pass
