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
import os
import subprocess
import signal
import threading
import time
import psutil  # 需要安装: pip install psutil
import shlex
from collections import namedtuple
from enum import Enum, auto
from contextlib import contextmanager
from typing import List, Dict, Tuple, Callable, Iterator, Union, Optional, Any

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("CommandExecutor")

# 常量定义
DEFAULT_TIMEOUT = 300  # 5分钟默认超时
SUDO_BINARY = "sudo"
TERM_WIDTH = 120  # 默认终端宽度

# 类型别名
ProcessResult = namedtuple('ProcessResult', ['stdout', 'stderr', 'code'])
ExecutionStrategy = Enum('ExecutionStrategy', ['BUFFERED_QUEUE', 'BUFFERED_CHUNKS'])
ExecutionMode = Enum('ExecutionMode', ['USER_PROMPT', 'IMMEDIATE_EXIT', 'RETRY', 'FORCE_CONTINUE'])

class CommandExecutionError(Exception):
    """命令执行错误异常"""
    def __init__(self, message, command=None, exit_code=None, output=None):
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.output = output

class ExecutionPolicy:
    """命令执行策略配置"""
    def __init__(self,
                 timeout: int = DEFAULT_TIMEOUT,
                 strategy: ExecutionStrategy = ExecutionStrategy.BUFFERED_CHUNKS,
                 env_vars: Dict[str, str] = None,
                 user: Optional[str] = None,
                 root_required: bool = False,
                 retries: int = 0,
                 retry_delay: int = 5,
                 capture_output: bool = True,
                 mode: ExecutionMode = ExecutionMode.USER_PROMPT):
        self.timeout = timeout
        self.strategy = strategy
        self.env_vars = env_vars or os.environ.copy()
        self.user = user
        self.root_required = root_required
        self.retries = max(retries, 0)
        self.retry_delay = retry_delay
        self.capture_output = capture_output
        self.mode = mode

class TerminalController:
    """终端控制工具类"""
    @staticmethod
    def get_terminal_size() -> Tuple[int, int]:
        """获取终端尺寸 (行, 列)"""
        try:
            from shutil import get_terminal_size
            size = get_terminal_size()
            return size.lines, size.columns
        except:
            return (25, TERM_WIDTH)  # 默认值
    
    @staticmethod
    def resize_terminal(rows: int = 40, cols: int = TERM_WIDTH):
        """重置终端尺寸"""
        try:
            # Linux/Unix终端尺寸调整
            sys.stdout.write(f"\x1b[8;{rows};{cols}t")
        except:
            pass
    
    @staticmethod
    def hide_cursor():
        """隐藏终端光标"""
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
    
    @staticmethod
    def show_cursor():
        """显示终端光标"""
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

class CommandValidator:
    """命令输入验证工具"""
    @staticmethod
    def validate_command(command: Union[str, List[str]]) -> List[str]:
        """验证并规范化命令输入"""
        if not command:
            raise CommandExecutionError("执行的命令不能为空")
        
        if isinstance(command, str):
            # 使用shlex安全分割命令字符串
            return shlex.split(command)
        elif isinstance(command, list) and all(isinstance(item, str) for item in command):
            return command
        else:
            raise CommandExecutionError(
                f"无效的命令格式: 必须是字符串或字符串列表, 实际类型: {type(command)}"
            )
    
    @staticmethod
    def check_root_required(root_required: bool):
        """检查是否满足root权限要求"""
        if root_required and os.geteuid() != 0:
            raise CommandExecutionError("此命令需要root权限")

class ProcessManager:
    """进程管理工具类"""
    
    @staticmethod
    def launch(command: List[str], env_vars: Dict[str, str], strategy: ExecutionStrategy, **kwargs) -> subprocess.Popen:
        """启动进程"""
        stdout = subprocess.PIPE if strategy == ExecutionStrategy.BUFFERED_CHUNKS else subprocess.PIPE
        stderr = subprocess.STDOUT if kwargs.get('combine_err', True) else subprocess.PIPE
        
        # 特殊处理sudo命令
        if command[0] == SUDO_BINARY:
            command[1:] = [shlex.quote(arg) for arg in command[1:]]
        
        return subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.PIPE,
            env=env_vars,
            universal_newlines=True,
            start_new_session=True,  # 创建新会话便于进程树管理
            **kwargs
        )
    
    @staticmethod
    def terminate_tree(process: subprocess.Popen, timeout: int = 5):
        """终止整个进程树"""
        try:
            if not process or process.poll() is not None:
                return
            
            # 使用psutil获取整个进程树
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            
            # 首先尝试SIGTERM终止
            for child in children + [parent]:
                try:
                    child.send_signal(signal.SIGTERM)
                except psutil.NoSuchProcess:
                    continue
            
            # 等待正常退出
            _, alive = psutil.wait_procs(children + [parent], timeout=timeout/2)
            
            # 强制终止剩余进程
            for process in alive:
                try:
                    process.send_signal(signal.SIGKILL)
                except psutil.NoSuchProcess:
                    continue
        except Exception as e:
            logger.warning(f"终止进程树失败: {str(e)}")
    
    @staticmethod
    def monitor_process(process: subprocess.Popen, timeout: int) -> threading.Timer:
        """监控进程执行时间，超时则终止"""
        def terminate_handler():
            if process.poll() is None:
                logger.warning(f"进程超时 ({timeout}秒)，正在强制终止")
                ProcessManager.terminate_tree(process)
        
        timer = threading.Timer(timeout, terminate_handler)
        timer.daemon = True
        timer.start()
        return timer

class OutputStrategyHandler:
    """输出处理策略实现"""
    
    @staticmethod
    def handle_chunks(process: subprocess.Popen) -> Iterator[str]:
        """分块输出处理策略"""
        try:
            while True:
                # 非阻塞读取
                chunk = process.stdout.readline()
                if chunk == '' and process.poll() is not None:
                    break
                if chunk:
                    yield chunk.strip()
        finally:
            # 清理资源
            process.stdout.close()
    
    @staticmethod
    def handle_queue(process: subprocess.Popen, timeout: int) -> Iterator[str]:
        """队列输出处理策略"""
        from queue import Queue, Empty
        data_queue = Queue()
        
        def reader_thread():
            try:
                for line in iter(process.stdout.readline, ''):
                    data_queue.put(line)
            finally:
                data_queue.put(None)  # 结束信号
        
        # 启动读取线程
        reader = threading.Thread(target=reader_thread, daemon=True)
        reader.start()
        
        # 主线程从队列读取
        while True:
            try:
                line = data_queue.get(timeout=0.1)
                if line is None:  # 结束信号
                    break
                yield line.strip()
            except Empty:
                if process.poll() is not None:  # 进程已结束
                    break
    
    @staticmethod
    def realtime_handler(process: subprocess.Popen) -> Iterator[str]:
        """实时输出处理策略（直接输出到终端）"""
        try:
            while True:
                char = process.stdout.read(1)
                if char == '' and process.poll() is not None:
                    break
                sys.stdout.write(char)
                sys.stdout.flush()
                yield char
        finally:
            process.stdout.close()

class RetryExecutor:
    """命令重试执行器"""
    
    def __init__(self, policy: ExecutionPolicy):
        self.policy = policy
    
    def execute(self, command: List[str], error_handler: Callable = None) -> ProcessResult:
        """执行命令并支持重试"""
        attempt = 0
        last_result = None
        
        while attempt <= self.policy.retries:
            try:
                attempt += 1
                logger.info(f"尝试执行命令 (尝试 #{attempt}/{self.policy.retries+1}): {' '.join(command)}")
                return CommandExecutor.execute(command, self.policy, error_handler)
            except CommandExecutionError as e:
                last_result = e
                if attempt <= self.policy.retries:
                    logger.warning(f"命令执行失败 [{e.exit_code}]，将在 {self.policy.retry_delay} 秒后重试... 原因: {str(e)}")
                    time.sleep(self.policy.retry_delay)
        
        # 所有重试失败后的处理
        msg = f"命令在 {self.policy.retries+1} 次尝试后失败:"
        # 应用配置的处理策略
        if self.policy.mode == ExecutionMode.IMMEDIATE_EXIT:
            logger.error(msg)
            raise SystemExit(1)
        elif self.policy.mode == ExecutionMode.FORCE_CONTINUE:
            logger.warning(msg + " 配置为强制继续，可能影响后续操作")
            return last_result.output if last_result else ProcessResult('', '', -1)
        else:  # USER_PROMPT (默认)
            logger.error(msg)
            user_input = input("是否继续执行程序? (y/n): ").strip().lower()
            if user_input != 'y':
                raise SystemExit(1)
            return last_result.output if last_result else ProcessResult('', '', -1)

class CommandExecutor:
    """高级命令执行器"""
    
    @staticmethod
    def execute(command: Union[str, List[str]], 
                policy: ExecutionPolicy = None, 
                error_handler: Callable = None) -> ProcessResult:
        """
        执行命令并获取结果
        
        参数:
            command: 要执行的命令（字符串或列表）
            policy: 执行策略配置
            error_handler: 错误处理回调函数
            
        返回:
            ProcessResult: 包含输出(stdout, stderr)和返回码(code)的结果对象
        """
        # 参数初始化
        policy = policy or ExecutionPolicy()
        command = CommandValidator.validate_command(command)
        CommandValidator.check_root_required(policy.root_required)
        
        # 根据用户要求调整执行权限
        if policy.user and policy.user != os.getlogin():
            command = [SUDO_BINARY, '-u', policy.user] + command
        
        # 执行命令
        logger.debug(f"执行命令: {' '.join(command)}")
        try:
            output = []
            
            # 执行命令并处理输出
            with CommandExecutor.process_executor(command, policy) as stdout:
                for line in stdout:
                    if policy.capture_output:
                        output.append(line)
                    # 可以在这里添加实时处理逻辑
                    
            # 获取最终结果
            code = process.poll()
            stderr = process.stderr.read() if not policy.capture_output else ''.join(output)
            result = ProcessResult(stdout=''.join(output), stderr=stderr, code=code)
            
            # 检查执行结果
            if code != 0:
                error_msg = f"命令执行失败 (退出码: {code})"
                if error_handler:
                    error_handler(command, result.stderr, code)
                else:
                    raise CommandExecutionError(
                        message=error_msg, 
                        command=' '.join(command), 
                        exit_code=code, 
                        output=result
                    )
            return result
            
        except Exception as e:
            if isinstance(e, CommandExecutionError):
                raise
            raise CommandExecutionError(f"命令执行时发生异常: {str(e)}") from e
    
    @staticmethod
    def execute_background(command: Union[str, List[str]],
                           policy: ExecutionPolicy = None) -> subprocess.Popen:
        """
        后台执行命令（非阻塞）
        
        返回:
            subprocess.Popen 对象
        """
        policy = policy or ExecutionPolicy(timeout=None, capture_output=False)
        command = CommandValidator.validate_command(command)
        CommandValidator.check_root_required(policy.root_required)
        
        # 分离模式执行
        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=policy.env_vars,
            start_new_session=True
        )
    
    @contextmanager
    def process_executor(command: List[str], policy: ExecutionPolicy) -> Iterator[str]:
        """
        命令执行上下文管理器
        
        用法示例:
          with CommandExecutor.process_executor(["ls", "-l"], policy) as stdout:
            for line in stdout:
                print(line)
        """
        process = None
        timer = None
        
        try:
            # 创建进程
            process = ProcessManager.launch(
                command=command,
                env_vars=policy.env_vars,
                strategy=policy.strategy
            )
            
            # 设置超时监控
            if policy.timeout > 0:
                timer = ProcessManager.monitor_process(process, policy.timeout)
            
            # 选择输出处理策略
            if policy.strategy == ExecutionStrategy.BUFFERED_CHUNKS:
                yield OutputStrategyHandler.handle_chunks(process)
            elif policy.strategy == ExecutionStrategy.BUFFERED_QUEUE:
                yield OutputStrategyHandler.handle_queue(process, policy.timeout)
            else:  # 默认实时输出
                yield OutputStrategyHandler.realtime_handler(process)
                
        except KeyboardInterrupt:
            logger.warning("用户中断命令执行")
            if process:
                ProcessManager.terminate_tree(process)
            raise
        finally:
            # 清理资源
            if timer:
                timer.cancel()
            if process:
                if process.poll() is None:
                    process.terminate()
                process.stdout.close()
                if process.stderr != process.stdout:
                    process.stderr.close()
    
    @staticmethod
    def execute_shell(script: str, user: Optional[str] = None) -> ProcessResult:
        """
        执行shell脚本
        
        参数:
            script: 要执行的shell脚本内容
            user: 运行脚本的用户
            
        返回:
            ProcessResult对象
        """
        policy = ExecutionPolicy(
            strategy=ExecutionStrategy.BUFFERED_CHUNKS,
            user=user
        )
        
        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=True) as f:
            f.write(script)
            f.flush()
            
            # 设置执行权限
            os.chmod(f.name, 0o755)
            
            # 执行脚本
            return CommandExecutor.execute([f.name], policy)

class PackageManager:
    """包管理器操作工具"""
    
    def __init__(self, retries: int = 3, retry_delay: int = 10):
        self.retries = retries
        self.retry_delay = retry_delay
    
    def install(self, packages: Union[str, List[str]], 
                repository: Optional[str] = None) -> ProcessResult:
        """安装软件包"""
        policy = ExecutionPolicy(
            retries=self.retries,
            retry_delay=self.retry_delay,
            mode=ExecutionMode.RETRY
        )
        
        if isinstance(packages, list):
            packages = " ".join(packages)
        
        # 检测系统包管理器
        if os.path.exists('/usr/bin/apt'):
            cmd = ['apt', 'install', '-y', packages]
            if repository:
                cmd.insert(2, f'--repos="{repository}"')
        elif os.path.exists('/usr/bin/yum'):
            cmd = ['yum', 'install', '-y', packages]
            if repository:
                cmd.insert(2, f'--enablerepo="{repository}"')
        else:
            raise CommandExecutionError("未识别的包管理器")
        
        return CommandExecutor.execute(cmd, policy)
    
    def remove(self, packages: Union[str, List[str]]) -> ProcessResult:
        """移除软件包"""
        policy = ExecutionPolicy(
            retries=self.retries,
            retry_delay=self.retry_delay,
            mode=ExecutionMode.RETRY
        )
        
        if isinstance(packages, list):
            packages = " ".join(packages)
        
        # 检测系统包管理器
        if os.path.exists('/usr/bin/apt'):
            cmd = ['apt', 'remove', '-y', packages]
        elif os.path.exists('/usr/bin/yum'):
            cmd = ['yum', 'remove', '-y', packages]
        else:
            raise CommandExecutionError("未识别的包管理器")
        
        return CommandExecutor.execute(cmd, policy)
    
    def update(self, repository: Optional[str] = None) -> ProcessResult:
        """更新软件包列表"""
        policy = ExecutionPolicy(
            retries=self.retries,
            retry_delay=self.retry_delay,
            mode=ExecutionMode.RETRY
        )
        
        # 检测系统包管理器
        if os.path.exists('/usr/bin/apt'):
            cmd = ['apt', 'update']
            if repository:
                cmd.append(f'-r="{repository}"')
        elif os.path.exists('/usr/bin/yum'):
            cmd = ['yum', 'update']
            if repository:
                cmd.append(f'--enablerepo="{repository}"')
        else:
            raise CommandExecutionError("未识别的包管理器")
        
        return CommandExecutor.execute(cmd, policy)
    
    def upgrade(self, packages: Optional[Union[str, List[str]]] = None) -> ProcessResult:
        """升级软件包"""
        policy = ExecutionPolicy(
            retries=self.retries,
            retry_delay=self.retry_delay,
            mode=ExecutionMode.RETRY
        )
        
        package_list = " ".join(packages) if packages else ''
        
        # 检测系统包管理器
        if os.path.exists('/usr/bin/apt'):
            cmd = ['apt', 'upgrade', '-y']
            if package_list:
                cmd.append(package_list)
        elif os.path.exists('/usr/bin/yum'):
            cmd = ['yum', 'upgrade', '-y']
            if package_list:
                cmd.append(package_list)
        else:
            raise CommandExecutionError("未识别的包管理器")
        
        return CommandExecutor.execute(cmd, policy)

class CommandWatcher(threading.Thread):
    """命令执行监控线程"""
    
    def __init__(self, command: str, callback: Callable[[str], None], interval: int = 1):
        """
        参数:
            command: 要周期性执行的命令
            callback: 输出处理回调函数
            interval: 执行间隔（秒）
        """
        super().__init__()
        self.command = command
        self.callback = callback
        self.interval = interval
        self._stop_event = threading.Event()
        self.daemon = True
    
    def run(self):
        while not self._stop_event.is_set():
            try:
                # 执行命令并获取输出
                result = CommandExecutor.execute(self.command)
                self.callback(result.stdout)
            except CommandExecutionError as e:
                self.callback(f"命令执行错误: {str(e)}")
            time.sleep(self.interval)
    
    def stop(self):
        self._stop_event.set()

# =============== 高级用例示例 ===============
def monitor_system_resources():
    """系统资源监控示例"""
    watcher = CommandWatcher(
        command="top -b -n 1 | head -n 20",
        callback=lambda output: logger.info(f"系统资源状态:\n{output}"),
        interval=5
    )
    
    try:
        watcher.start()
        logger.info("系统资源监控已启动，按Ctrl+C停止...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        logger.info("监控已停止")

def disk_space_check():
    """磁盘空间检查"""
    policy = ExecutionPolicy(
        mode=ExecutionMode.FORCE_CONTINUE,
        root_required=True
    )
    
    try:
        result = CommandExecutor.execute("df -h", policy)
        logger.info("磁盘空间使用情况:\n%s", result.stdout)
        
        # 检查磁盘使用率是否超过90%
        for line in result.stdout.splitlines()[1:]:  # 跳过标题行
            parts = line.split()
            if len(parts) > 4:
                usage = int(parts[4].rstrip('%'))
                if usage > 90:
                    logger.warning(f"磁盘分卷 {parts[0]} 使用率过高: {parts[4]}!")
    except CommandExecutionError as e:
        logger.error(f"磁盘空间检查失败: {str(e)}")

def package_installation_demo():
    """软件包安装演示"""
    logger.info("开始软件包安装过程")
    
    # 配置包管理器
    pm = PackageManager(retries=3, retry_delay=10)
    
    # 更新仓库
    try:
        pm.update()
        logger.info("软件仓库更新成功")
    except CommandExecutionError as e:
        logger.error(f"软件仓库更新失败: {str(e)}")
        return
    
    # 安装软件包
    try:
        result = pm.install(["nginx", "redis-server"])
        logger.info("软件包安装成功:\n%s", result.stdout)
    except CommandExecutionError as e:
        logger.error(f"软件包安装失败: {str(e)}")

def critical_system_command_demo():
    """关键系统命令执行演示"""
    logger.info("执行关键系统命令")
    
    try:
        retry_policy = ExecutionPolicy(
            retries=2,
            retry_delay=5,
            timeout=60,
            mode=ExecutionMode.RETRY
        )
        
        # 高可用性的关键命令执行
        command = ["systemctl", "restart", "important-service"]
        CommandExecutor.execute(command, retry_policy)
        logger.info("系统服务成功重启")
    except CommandExecutionError as e:
        logger.error(f"服务重启失败: {str(e)}")
        # 高级错误处理逻辑

if __name__ == "__main__":
    # 使用示例
    logger.info("命令行执行框架演示")
    
    try:
        # 执行简单命令
        result = CommandExecutor.execute("ls -l", ExecutionPolicy(timeout=10))
        logger.info("目录列表:\n%s", result.stdout)
        
        # 执行带管道的高级命令
        complex_cmd = "find . -name '*.py' | xargs wc -l | sort -n"
        result = CommandExecutor.execute(complex_cmd, ExecutionPolicy(timeout=30))
        logger.info("Python代码行数统计:\n%s", result.stdout)
        
        # 后台执行命令
        logger.info("后台启动服务...")
        process = CommandExecutor.execute_background("python -m http.server 8000")
        
        # 进行其他操作
        time.sleep(1)
        logger.info("在前台进程中检查服务状态...")
        CommandExecutor.execute("curl http://localhost:8000")
        
        # 结束后台进程
        logger.info("停止后台服务")
        ProcessManager.terminate_tree(process)
        
        # 资源监控演示
        monitor_system_resources()
    except Exception as e:
        logger.exception("演示过程中发生错误")
