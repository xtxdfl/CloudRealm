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

Enhanced Secure Command Execution Framework
"""

import os
import sys
import tempfile
import logging
import shlex
import traceback
from contextlib import ExitStack
from typing import Tuple, Union, List, Dict, Optional, NoReturn, Callable
from resource_management.core import shell
from resource_management.core.logger import StructuredLogger
from resource_management.core.exceptions import SecureExecutionFailed

# Initialize structured logger
logger = StructuredLogger(__name__)

def execute_as_user(
    cmd: Union[str, List[str]], 
    username: str,
    *,
    quiet: bool = False,
    validate: bool = True,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    stdin_data: Optional[bytes] = None,
    security_profile: str = "restricted",
    umask: Optional[int] = None,
    output_encoding: str = "utf-8",
    error_callback: Optional[Callable[[int, str, str], None]] = None
) -> Tuple[int, str, str]:
    """
    以指定用户身份安全执行命令并捕获输出
    
    :param cmd: 要执行的命令（字符串或列表形式）
    :param username: 运行命令的用户名
    :param quiet: 是否抑制日志输出（默认False）
    :param validate: 是否在失败时抛出异常（默认True）
    :param timeout: 命令执行超时时间（秒）
    :param env: 自定义环境变量
    :param cwd: 工作目录路径
    :param stdin_data: 标准输入数据
    :param security_profile: 安全配置模式（'restricted'、'elevated'、'sandbox'）
    :param umask: 临时文件创建的umask
    :param output_encoding: 输出解码编码格式
    :param error_callback: 执行失败时的回调函数
    :return: (返回码, 标准输出, 标准错误)
    
    >>> rc, out, err = execute_as_user("ls -l", "appuser")
    """
    # 记录执行上下文
    if not quiet:
        logger.info(f"以用户 '{username}' 身份执行命令", 
                    command=cmd, 
                    security_profile=security_profile,
                    timeout=f"{timeout}s" if timeout else "无超时")
    
    original_umask = None
    if umask is not None:
        original_umask = os.umask(umask)
    
    try:
        # 创建安全的临时文件保存输出
        with ExitStack() as stack:
            out_files = [
                stack.enter_context(create_secure_tempfile(restrict=True)),
                stack.enter_context(create_secure_tempfile(restrict=True))
            ]
            
            out_filenames = [f.name for f in out_files]
            sanitized_cmd = build_command_string(cmd, out_filenames)
            
            # 构建完整的用户命令
            full_command = shell.as_user(sanitized_cmd, username)
            
            # 自定义环境
            exec_env = os.environ.copy()
            if env:
                exec_env.update(env)
            
            # 执行命令
            return_code = shell.call(
                full_command, 
                quiet=True, 
                timeout=timeout,
                env=exec_env,
                cwd=cwd,
                stdin_data=stdin_data
            )[0]
            
            # 读取输出并进行安全过滤
            stdout_content = safe_read_output(out_files[0], output_encoding, quiet)
            stderr_content = safe_read_output(out_files[1], output_encoding, quiet)
            
            # 处理执行结果
            return handle_execution_result(
                return_code, 
                stdout_content, 
                stderr_content, 
                sanitized_cmd,
                username,
                validate,
                quiet,
                error_callback
            )
    except Exception as exc:
        # 错误处理和资源清理
        handle_execution_exception(exc, quiet, validate, error_callback)
    finally:
        # 恢复原始umask
        if original_umask is not None:
            os.umask(original_umask)

def create_secure_tempfile(
    *, 
    restrict: bool = False, 
    mode: int = 0o600
) -> tempfile.NamedTemporaryFile:
    """
    创建安全的临时文件
    
    :param restrict: 是否限制其他用户访问
    :param mode: 文件权限模式
    :return: 临时文件对象
    """
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        os.chmod(temp_file.name, mode)
        
        # 限制访问权限（如有必要）
        if restrict:
            os.chmod(temp_file.name, 0o600)
        return temp_file
    except OSError as e:
        logger.error(f"无法创建临时文件: {str(e)}")
        raise SecureExecutionFailed(
            f"资源分配失败: {str(e)}", 
            code=-1001
        ) from e

def build_command_string(
    cmd: Union[str, List[str]], 
    output_files: List[str]
) -> str:
    """
    构建安全的命令字符串
    
    :param cmd: 原始命令
    :param output_files: 输出文件路径列表 [stdout, stderr]
    :return: 完整的命令字符串
    """
    if isinstance(cmd, (list, tuple)):
        command_str = shell.string_cmd_from_args_list(cmd)
    else:
        command_str = shlex.quote(str(cmd))
    
    # 添加输出重定向
    command_str += f" 1>'{output_files[0]}'"
    command_str += f" 2>'{output_files[1]}'"
    return command_str

def safe_read_output(
    file_obj: tempfile.NamedTemporaryFile, 
    encoding: str = "utf-8",
    quiet: bool = False
) -> str:
    """
    安全读取并过滤命令输出
    
    :param file_obj: 临时文件对象
    :param encoding: 文件编码
    :param quiet: 是否跳过敏感日志
    :return: 处理过的输出内容
    """
    try:
        with open(file_obj.name, "rb") as f:
            content = f.read().decode(encoding).strip("\n")
        
        safe_content = filter_sensitive_content(content, quiet)
        return safe_content
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"输出处理失败: {file_obj.name} - {str(e)}")
        return "<编码错误无法读取>"

def filter_sensitive_content(
    text: str, 
    quiet: bool = False
) -> str:
    """
    过滤输出中的敏感信息
    
    :param text: 原始文本
    :param quiet: 是否跳过敏感日志
    :return: 过滤后的文本
    """
    # 敏感数据模式 (可扩展)
    sensitive_patterns = [
        r"password\s*[:=]\s*\S+",  # 密码字段
        r"token\s*[:=]\s*\S+",      # 令牌字段
        r"key\s*[:=]\s*\S+",        # 密钥字段
        # 其他模式...
    ]
    
    sanitized = text
    for pattern in sensitive_patterns:
        sanitized = re.sub(pattern, r"\1*****", sanitized, flags=re.IGNORECASE)
    
    # 记录原始输出（如有必要）
    if not quiet and sanitized != text:
        logger.info("过滤敏感内容", before=sensitive_patterns, after=sanitized)
    
    return sanitized

def handle_execution_result(
    return_code: int, 
    stdout: str, 
    stderr: str, 
    command: str,
    username: str,
    validate: bool,
    quiet: bool,
    error_callback: Optional[Callable]
) -> Tuple[int, str, str]:
    """
    处理命令执行结果
    
    :return: (返回码, stdout, stderr)
    """
    if return_code != 0:
        error_ctx = {
            "user": username,
            "command": command,
            "exit_code": return_code,
            "stderr": stderr
        }
        
        # 调用错误回调（如有）
        if error_callback:
            try:
                error_callback(return_code, stdout, stderr)
            except Exception as cb_err:
                logger.warning("错误回调处理失败", error=str(cb_err))
        
        # 是否验证结果（抛出异常）
        if validate:
            error_summary = (f"命令 '{command}' 执行失败 (退出码 {return_code}) "
                             f"用户: {username}")
            logger.error(error_summary, context=error_ctx)
            raise SecureExecutionFailed(
                error_summary, 
                return_code, 
                stdout, 
                stderr
            )
        else:
            logger.warning("命令执行完成但有错误", context=error_ctx)
    
    # 记录成功执行
    if not quiet:
        logger.info(f"命令成功执行 (退出码 {return_code})", 
                    command=command, 
                    user=username,
                    stdout=stdout[:100] + ("..." if len(stdout) > 100 else ""),
                    stderr=stderr if return_code != 0 else "<无错误>")
    
    return return_code, stdout, stderr

def handle_execution_exception(
    exception: Exception,
    quiet: bool,
    validate: bool,
    error_callback: Optional[Callable]
) -> NoReturn:
    """
    统一处理执行异常
    
    :raises SecureExecutionFailed: 始终转换为核心异常类型
    """
    exc_info = {
        "type": type(exception).__name__,
        "message": str(exception),
        "traceback": traceback.format_exc()
    }
    
    # 调用错误回调（如有）
    if error_callback:
        try:
            error_callback(-1000, "EXECUTION_ABORTED", str(exception))
        except Exception as cb_err:
            logger.warning("错误回调处理失败", error=str(cb_err))
    
    # 是否记录完整日志
    if not quiet:
        logger.critical("命令执行意外终止", exception=exc_info)
    
    # 验证模式下包装原始异常
    if validate:
        raise SecureExecutionFailed(
            f"执行系统错误: {str(exception)}",
            code=-1000,
            orig_exception=exception
        ) from exception
    else:
        # 非验证模式返回占位符结果
        return -1000, "<执行中断>", "<执行中断>"

def benchmark_execution(cmd: str, username: str, iterations: int = 5) -> Dict:
    """
    执行性能基准测试
    
    :param cmd: 基准命令
    :param username: 执行用户
    :param iterations: 执行次数
    :return: 性能指标
    """
    from timeit import Timer
    timer = Timer(
        lambda: execute_as_user(cmd, username, quiet=True, validate=False)
    )
    times = timer.repeat(repeat=iterations, number=1)
    
    return {
        "command": cmd,
        "user": username,
        "iterations": iterations,
        "min_time": min(times),
        "max_time": max(times),
        "avg_time": sum(times)/len(times),
        "all_times": times
    }

# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 示例1: 基本执行
    try:
        rc, out, err = execute_as_user(
            ["ls", "-l", "/opt"],
            "appuser",
            quiet=False
        )
        print(f"文件列表 (exit {rc}):\n{out}")
    except SecureExecutionFailed as se:
        print(f"执行失败: {str(se)}")
        print(f"标准错误: {se.stderr}")

    # 示例2: 带安全限制的执行
    try:
        _, sensitive_out, _ = execute_as_user(
            "echo 'Password: secret123' && env | grep API",
            "admin",
            security_profile="sensitive",
            umask=0o077
        )
        print(f"过滤后的输出: {sensitive_out}")
    except SecureExecutionFailed:
        pass

    # 示例3: 自定义错误处理
    def on_exec_error(rc, stdout, stderr):
        print(f"自定义错误处理: RC={rc}, ERR={stderr}")

    execute_as_user(
        "non-existent-command",
        "appuser",
        validate=False,
        error_callback=on_exec_error
    )

    # 示例4: 基准测试
    perf = benchmark_execution("df -h", "root", 3)
    print(f"磁盘检查性能: {perf['min_time']:.3f}秒 (平均)")
