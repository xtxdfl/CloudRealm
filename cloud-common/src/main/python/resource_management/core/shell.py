#!/usr/bin/env python3

__all__ = [
    "non_blocking_call",
    "checked_call",
    "call",
    "quote_bash_args",
    "as_user",
    "as_sudo",
]

import time
import copy
import os
import select
import sys
import logging
import string
import subprocess
import threading
import traceback
from typing import List, Tuple, Optional, Dict, Union
from functools import reduce

from .exceptions import Fail, ExecutionFailed, ExecuteTimeoutException
from resource_management.core.logger import Logger
from cloud_commons.constants import cloud_SUDO_BINARY
from resource_management.core.signal_utils import TerminateStrategy, terminate_process

# 常量定义
INTERNAL_MODULE_PATH = "resource_management/core"
EXPORT_PLACEHOLDER = "[RMF_EXPORT_PLACEHOLDER]"
ENV_PLACEHOLDER = "[RMF_ENV_PLACEHOLDER]"
COMMAND_TIMEOUT_BUFFER = 3  # 超时处理缓冲区（秒）
MAX_READ_SIZE = 8192  # 最大读取缓冲区大小

PLACEHOLDERS_TO_STR = {
    EXPORT_PLACEHOLDER: "export {env_str} > /dev/null ; ",
    ENV_PLACEHOLDER: "{env_str}",
}

class CommandExecutionError(Exception):
    """命令执行异常基类"""
    def __init__(self, message, command=None, code=None, output=None, error=None):
        super().__init__(message)
        self.command = command
        self.code = code
        self.output = output
        self.error = error

def configure_process_group():
    """配置进程组设�?""
    try:
        # 创建一个新的进程组
        os.setpgid(0, 0)
    except OSError as e:
        Logger.error(f"进程组设置失�? {str(e)}")
        # 继续而非终止进程

def log_function_execution(function):
    """记录函数执行的装饰器"""
    def wrapper(command, **kwargs):
        # 判断是否为内部调�?        caller_frame = sys._getframe(1)
        caller_file = caller_frame.f_code.co_filename
        is_internal = INTERNAL_MODULE_PATH in caller_file
        
        # 处理 quiet 参数
        quiet = kwargs.get("quiet", None)
        should_log = not (quiet is True or (quiet is None and is_internal))
        
        # 记录函数调用
        if should_log:
            command_repr = Logger.format_command_for_output(command)
            arg_str = ", ".join(f"{k}={v}" for k, v in kwargs.items() if k != "logoutput")
            Logger.debug(f"{function.__name__}({command_repr}, {arg_str})")
        
        # 动态设�?logoutput
        if 'logoutput' in function.__code__.co_varnames:
            kwargs["logoutput"] = _determine_logoutput_setting(kwargs, is_internal)
        
        # 执行函数并记录结�?        try:
            result = function(command, **kwargs)
            if should_log:
                Logger.debug(f"{function.__name__} 返回: {str(result)[:100]}")
            return result
        except Exception as e:
            if should_log:
                Logger.exception(f"{function.__name__} 执行失败")
            raise
    
    return wrapper

def _determine_logoutput_setting(kwargs: dict, is_internal: bool) -> bool:
    """确定日志输出设置"""
    logoutput = kwargs.get("logoutput", None)
    
    # 显式设置�?True 且日志级别为 INFO 或更�?    if logoutput and Logger.isEnabledFor(logging.INFO):
        return True
    
    # 默认情况下在 DEBUG 级别记录（非内部调用�?    if logoutput is None and not is_internal and Logger.isEnabledFor(logging.DEBUG):
        return True
    
    # 设置�?False 或未达到日志级别
    return False

@log_function_execution
def checked_call(
    command: Union[str, List[str]],
    quiet: bool = False,
    logoutput: Optional[bool] = None,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    timeout: Optional[float] = None,
    on_timeout: Optional[str] = None,
    path: Optional[List[str]] = None,
    sudo: bool = False,
    on_new_line: Optional[callable] = None,
    tries: int = 1,
    try_sleep: float = 0,
    timeout_kill_strategy: TerminateStrategy = TerminateStrategy.TERMINATE_PARENT,
    returns: List[int] = [0],
    **kwargs
) -> Tuple[int, str]:
    """
    执行命令 - 失败时抛出异�?    
    参数说明:
    command: 要执行的命令（字符串或参数列表）
    quiet: 减少日志输出
    logoutput: 是否记录命令输出
    stdout: 标准输出处理（PIPE/文件/无）
    stderr: 标准错误处理（PIPE/文件/重定向）
    cwd: 工作目录
    env: 环境变量
    user: 执行用户
    timeout: 执行超时（秒�?    on_timeout: 超时后执行的命令
    path: 额外的PATH目录
    sudo: 是否使用sudo
    on_new_line: 逐行输出处理�?    tries: 最大尝试次�?    try_sleep: 尝试间等待时间（秒）
    timeout_kill_strategy: 超时终止策略
    returns: 接受的非零返回码列表
    
    返回: (返回�? 输出) �?(返回�? 输出, 错误) 如果stderr分离
    """
    return _execute_command(
        command, 
        throw_on_failure=True,
        quiet=quiet,
        logoutput=logoutput,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        env=env,
        user=user,
        wait_for_finish=True,
        timeout=timeout,
        on_timeout=on_timeout,
        path=path,
        sudo=sudo,
        on_new_line=on_new_line,
        tries=tries,
        try_sleep=try_sleep,
        timeout_kill_strategy=timeout_kill_strategy,
        returns=returns,
        **kwargs
    )

@log_function_execution
def call(
    command: Union[str, List[str]],
    quiet: bool = False,
    logoutput: Optional[bool] = None,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    timeout: Optional[float] = None,
    on_timeout: Optional[str] = None,
    path: Optional[List[str]] = None,
    sudo: bool = False,
    on_new_line: Optional[callable] = None,
    tries: int = 1,
    try_sleep: float = 0,
    timeout_kill_strategy: TerminateStrategy = TerminateStrategy.TERMINATE_PARENT,
    returns: List[int] = [0],
    **kwargs
) -> Tuple[int, str]:
    """
    执行命令 - 忽略失败
    
    参数与返回说明同 checked_call
    """
    return _execute_command(
        command, 
        throw_on_failure=False,
        quiet=quiet,
        logoutput=logoutput,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        env=env,
        user=user,
        wait_for_finish=True,
        timeout=timeout,
        on_timeout=on_timeout,
        path=path,
        sudo=sudo,
        on_new_line=on_new_line,
        tries=tries,
        try_sleep=try_sleep,
        timeout_kill_strategy=timeout_kill_strategy,
        returns=returns,
        **kwargs
    )

@log_function_execution
def non_blocking_call(
    command: Union[str, List[str]],
    quiet: bool = False,
    stdout=None,
    stderr=None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    timeout: Optional[float] = None,
    path: Optional[List[str]] = None,
    sudo: bool = False,
    **kwargs
) -> subprocess.Popen:
    """
    非阻塞命令执�?    
    返回: subprocess.Popen 对象
    """
    return _execute_command(
        command, 
        throw_on_failure=True,
        quiet=quiet,
        logoutput=False,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        env=env,
        user=user,
        wait_for_finish=False,
        timeout=timeout,
        path=path,
        sudo=sudo,
        **kwargs
    )

def _execute_command(
    command: Union[str, List[str]],
    **kwargs
) -> Union[Tuple[int, str], subprocess.Popen]:
    """
    命令执行核心函数
    
    处理重试逻辑和最终执�?    """
    # 处理重试
    for attempt in range(kwargs['tries']):
        is_final_attempt = attempt == kwargs['tries'] - 1
        
        # 非最终尝试时启用错误抛出
        if not is_final_attempt:
            kwargs_copy = copy.copy(kwargs)
            kwargs_copy['throw_on_failure'] = True
        else:
            kwargs_copy = kwargs
        
        try:
            try:
                return _run_command_safely(command, **kwargs_copy)
            except ExecuteTimeoutException as exc:
                if kwargs_copy.get('on_timeout'):
                    Logger.info(f"执行超时回调: {kwargs_copy['on_timeout']}")
                    checked_call(kwargs_copy['on_timeout'])
                raise
        except Fail as exc:
            if is_final_attempt:
                raise
            sleep_time = kwargs_copy['try_sleep'] or min(2 ** attempt, 60)
            Logger.warning(f"尝试失败 ({attempt+1}/{kwargs['tries']})，{sleep_time}秒后重试: {str(exc)}")
            time.sleep(sleep_time)
    
    # 理论上不会执行到此处
    return -999, "Unexpected execution state"

def _run_command_safely(
    command: Union[str, List[str]],
    logoutput: bool = False,
    throw_on_failure: bool = True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    user: Optional[str] = None,
    wait_for_finish: bool = True,
    timeout: Optional[float] = None,
    path: Optional[Union[str, List[str]]] = None,
    sudo: bool = False,
    on_new_line: Optional[callable] = None,
    timeout_kill_strategy: TerminateStrategy = TerminateStrategy.TERMINATE_PARENT,
    returns: List[int] = [0],
    **kwargs
) -> Union[Tuple[int, str], subprocess.Popen]:
    """
    安全执行命令
    """
    # 准备命令与环�?    env = _prepare_environment(env, path)
    command_str = _prepare_command(command, env, user, sudo)
    is_separated_stderr = stderr == subprocess.PIPE
    
    # 处理非等待执�?    if not wait_for_finish:
        return subprocess.Popen(
            command_str,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            env=env,
            shell=False,
            close_fds=True,
            start_new_session=True
        )
    
    # 执行并捕获输�?    with _open_file_descriptors(stdout, stderr) as (out_fd, err_fd, files_to_close):
        try:
            proc = subprocess.Popen(
                command_str,
                stdout=out_fd,
                stderr=err_fd,
                cwd=cwd,
                env=env,
                shell=False,
                close_fds=True,
                start_new_session=True
            )
            
            # 设置执行超时监控
            timer, timeout_event = _setup_timeout_monitor(proc, timeout, timeout_kill_strategy)
            
            # 读取进程输出
            output_data, stderr_data, merged_output = _read_process_output(
                proc, out_fd, err_fd, logoutput, on_new_line
            )
            
            # 等待进程结束
            _wait_for_process_exit(proc, timeout, timeout_event, timer)
            
            # 处理结果
            return _handle_process_result(
                proc.returncode, 
                output_data, 
                stderr_data, 
                merged_output, 
                command, 
                throw_on_failure, 
                returns, 
                is_separated_stderr
            )
        
        finally:
            # 确保清理资源
            timer.cancel() if timer and not timeout_event.is_set() else None

class _FileDescriptorManager:
    """文件描述符上下文管理�?""
    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self.files_to_close = []
    
    def __enter__(self):
        # 打开文件描述�?        out_fd = self._get_file_descriptor(self.stdout, "wb") 
        err_fd = self._get_file_descriptor(self.stderr, "wb")
        return (out_fd, err_fd, self.files_to_close)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 确保关闭所有文�?        for f in self.files_to_close:
            f.close()
    
    def _get_file_descriptor(self, spec, mode):
        """获取文件描述�?""
        if isinstance(spec, str):
            f = open(spec, mode)
            self.files_to_close.append(f)
            return f
        return spec

def _open_file_descriptors(stdout, stderr):
    return _FileDescriptorManager(stdout, stderr)

def _prepare_environment(base_env: Optional[dict], extra_path: Optional[Union[str, List[str]]]) -> dict:
    """准备执行环境"""
    # 基础环境
    env = copy.copy(base_env) if base_env else copy.copy(os.environ)
    
    # 确保PATH存在
    if "PATH" not in env:
        env["PATH"] = os.environ.get("PATH", "")
    
    # 添加额外PATH
    if extra_path:
        if isinstance(extra_path, list):
            extra_path = os.pathsep.join(extra_path)
        env["PATH"] = os.pathsep.join([env["PATH"], extra_path])
    
    return env

def _prepare_command(
    command: Union[str, List[str]], 
    env: dict, 
    user: Optional[str], 
    sudo: bool
) -> List[str]:
    """准备要执行的命令"""
    # 验证参数条件
    if sudo and user:
        raise ValueError("sudo �?user 参数是互斥的")
    
    # 处理shell命令
    if isinstance(command, (list, tuple)):
        command_str = string_cmd_from_args_list(command)
    else:
        command_str = command
    
    # 用户身份处理
    if sudo:
        return _wrap_sudo_command(command_str, env)
    elif user:
        return _wrap_user_command(command_str, user, env)
    
    # 直接返回命令
    return ["/bin/bash", "--login", "--noprofile", "-c", command_str]

def _wrap_sudo_command(command: str, env: Optional[dict]) -> List[str]:
    """包装sudo命令"""
    if isinstance(command, (list, tuple)):
        raise CommandExecutionError("sudo 命令不能使用参数列表")
    
    env_str = _get_environment_str(_add_current_path_to_env(env)) if env else ENV_PLACEHOLDER
    full_command = f"{cloud_SUDO_BINARY} {env_str} -H -E {command}"
    return ["/bin/bash", "--login", "--noprofile", "-c", full_command]

def _wrap_user_command(command: str, user: str, env: Optional[dict]) -> List[str]:
    """包装以指定用户运行命�?""
    export_env = f"export {_get_environment_str(_add_current_path_to_env(env))} ; " if env else EXPORT_PLACEHOLDER
    full_command = f"{cloud_SUDO_BINARY} su {user} -l -s /bin/bash -c {quote_bash_args(export_env + command)}"
    return ["/bin/bash", "--login", "--noprofile", "-c", full_command]

def _add_current_path_to_env(env: Optional[dict]) -> dict:
    """添加当前路径到环境变�?""
    result = copy.copy(env) if env else {}
    current_path = os.environ.get("PATH", "")
    
    if "PATH" not in result:
        result["PATH"] = current_path
    elif not set(current_path.split(os.pathsep)).issubset(result["PATH"].split(os.pathsep)):
        result["PATH"] = os.pathsep.join([current_path, result["PATH"]])
    
    return result

def _get_environment_str(env: dict) -> str:
    """生成环境变量字符�?""
    return " ".join(f"{k}={quote_bash_args(v)}" for k, v in env.items())

def quote_bash_args(command: str) -> str:
    """安全转义bash参数"""
    if not command:
        return "''"
    
    # 仅针对需要转义的字符
    if any(char in command for char in " \"'$!&*;<>?[\\]^`{|}~"):
        return "'" + command.replace("'", "'\"'\"'") + "'"
    
    return command

def string_cmd_from_args_list(command_list: Union[List[str], Tuple[str]]) -> str:
    """从参数列表生成字符串命令"""
    return " ".join(quote_bash_args(arg) for arg in command_list)

def _setup_timeout_monitor(proc: subprocess.Popen, timeout: Optional[float], strategy: TerminateStrategy):
    """设置超时监控"""
    if not timeout:
        return None, None
    
    timeout_event = threading.Event()
    timer = threading.Timer(
        timeout, 
        _handle_execution_timeout, 
        [proc, timeout_event, strategy]
    )
    timer.start()
    return timer, timeout_event

def _handle_execution_timeout(proc: subprocess.Popen, event: threading.Event, strategy: TerminateStrategy):
    """处理执行超时"""
    event.set()
    terminate_process(proc, strategy)

def _read_process_output(
    proc: subprocess.Popen,
    stdout,
    stderr,
    logoutput: bool,
    line_handler: Optional[callable]
) -> Tuple[str, str, str]:
    """
    读取并处理进程输�?    
    返回: (stdout内容, stderr内容, 合并输出)
    """
    # 准备读取�?    outputs = {
        proc.stdout: "", 
        proc.stderr: ""
    }
    
    fds = [fd for fd in [proc.stdout, proc.stderr] if fd is not None]
    merged = ""
    
    while fds:
        # 检查进程是否终�?        if proc.poll() is None:
            ready, _, _ = select.select(fds, [], [], 1)
            if not ready:
                continue
        
        # 处理所有准备好的文件描述符
        for fd in list(fds):
            try:
                data = os.read(fd.fileno(), MAX_READ_SIZE).decode()
                if not data:
                    fds.remove(fd)
                    fd.close()
                    continue
                
                outputs[fd] += data
                merged += data
                
                # 行处理回�?                if line_handler:
                    try:
                        line_handler(data, fd == proc.stderr)
                    except Exception:
                        Logger.exception("行处理器失败")
                
                # 实时日志
                if logoutput:
                    sys.stdout.write(data)
                    sys.stdout.flush()
            except OSError:
                fds.remove(fd)
                if not fds: break
    
    return outputs.get(proc.stdout, ""), outputs.get(proc.stderr, ""), merged

def _wait_for_process_exit(proc: subprocess.Popen, timeout: float, event: threading.Event, timer: threading.Timer):
    """等待进程退�?""
    if not timeout or not event.is_set():
        try:
            proc.communicate(timeout=timeout + COMMAND_TIMEOUT_BUFFER if timeout else None)
        except subprocess.TimeoutExpired:
            _handle_execution_timeout(proc, event, TerminateStrategy.TERMINATE_PARENT)
            raise ExecuteTimeoutException(f"命令超时 ({timeout}�?")
    
    if timer and not event.is_set():
        timer.cancel()

def _handle_process_result(
    code: int, 
    out: str, 
    err: str, 
    all_out: str, 
    command: Union[str, List[str]], 
    throw_on_failure: bool, 
    accepted_codes: List[int],
    separated_stderr: bool
) -> Tuple:
    """处理命令执行结果"""
    command_repr = string_cmd_from_args_list(command) if isinstance(command, list) else command
    
    # 处理失败情况
    if throw_on_failure and code not in accepted_codes:
        msg = f"命令 '{command_repr}' 失败，代�?{code}: {all_out[:500]}"
        filtered = Logger.filter_text(msg)
        raise ExecutionFailed(filtered, code, out, err)
    
    # 分离错误输出
    if separated_stderr:
        return code, out.strip(), err.strip()
    
    # 合并输出
    return code, all_out.strip()
