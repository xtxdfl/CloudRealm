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

高级Hadoop命令执行引擎
"""

from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
from typing import Dict, List, Optional, Union, Tuple, Any, Callable
import logging
import subprocess
import time

class ExecuteHadoop(Resource):
    """
    Hadoop命令执行资源
    
    提供安全、高效、可监控的Hadoop命令执行能力，支持：
    - 完整的Hadoop环境配置
    - 多级重试和超时控制
    - 命令安全验证和执行隔离
    - 实时进度跟踪和输出捕获
    - Kerberos认证集成

    使用示例：
        ExecuteHadoop(
            name="yarn_status_check",
            command="yarn application -list",
            user="yarnadmin",
            conf_dir="/etc/hadoop/conf",
            environment={ "HADOOP_USER_NAME": "admin" },
            retry_count=3,
            retry_delay=10,
            timeout=300,
            sensitive=True
        )
    """

    # 命令执行动作（run为默认动作）
    action = ForcedListArgument(
        default="run",
        choices=["run", "dry_run", "validate"],
        description="命令操作：执行(run)/空跑(dry_run)/验证(validate)"
    )
    
    # Hadoop命令（可以是字符串或列表）
    command = ResourceArgument(
        required=True,
        description="待执行的Hadoop命令（支持列表格式以避免注入风险）"
    )
    
    # 执行用户
    user = ResourceArgument(
        default="hdfs",
        description="执行命令的系统用户"
    )
    
    # 日志输出控制
    logoutput = ResourceArgument(
        default=True,
        description="是否记录命令输出（True/False/'on_failure'）"
    )
    
    # Hadoop主目录
    hadoop_home = ResourceArgument(
        default="/usr/hdp/current/hadoop-client",
        description="Hadoop安装目录"
    )
    
    # Hadoop配置目录
    conf_dir = ResourceArgument(
        default="/etc/hadoop/conf",
        description="Hadoop配置文件目录"
    )
    
    # Hadoop环境变量
    environment = ResourceArgument(
        default={},
        description="额外环境变量（键值对字典）"
    )
    
    # HDFS主节点信息
    fs_active_name = ResourceArgument(
        description="活动NameNode主机"
    )
    fs_standby_name = ResourceArgument(
        description="备用NameNode主机（可选）"
    )
    
    # Kerberos安全配置
    kerberos_principal = ResourceArgument(
        description="Kerberos认证主体"
    )
    kerberos_keytab = ResourceArgument(
        description="Kerberos密钥表路径"
    )
    
    # 安全控制
    sensitive = BooleanArgument(
        default=False,
        description="是否为敏感命令（日志中掩码输出）"
    )
    safe_mode = BooleanArgument(
        default=True,
        description="是否启用安全模式（验证命令合法性）"
    )
    allowed_commands = ResourceArgument(
        default=["hdfs", "mapred", "yarn"],
        description="允许执行的命令白名单"
    )
    
    # 执行控制
    max_retries = ResourceArgument(
        default=3,
        description="最大重试次数"
    )
    retry_delay = ResourceArgument(
        default=10,
        description="重试间隔（秒）"
    )
    timeout = ResourceArgument(
        default=600,
        description="命令超时时间（秒）"
    )
    
    # 结果处理
    success_codes = ResourceArgument(
        default=[0],
        description="表示成功的返回码列表"
    )
    failure_handler = ResourceArgument(
        description="失败回调函数（参数: result, attempt）"
    )
    
    # 支持的操作列表
    actions = Resource.actions + ["run", "status"]

    # 已知安全命令模式
    SAFE_COMMAND_PATTERNS = [
        r"^hdfs\s+(dfsadmin|dfs|haadmin|fsck|balancer)",
        r"^mapred\s+(job|historyserver|queue)",
        r"^yarn\s+(application|node|rmadmin|queue)"
    ]

    def __init__(self, **kwargs):
        """
        初始化Hadoop命令资源
        
        增强初始化逻辑：
            - 验证命令安全性
            - 设置Kerberos环境
            - 构建完整执行环境
        """
        super().__init__(**kwargs)
        self._resolve_command()
        self._validate_security()
        self._setup_kerberos()
        self._prepare_environment()
    
    def _resolve_command(self):
        """解析命令格式（支持字符串和列表）"""
        if isinstance(self.command, str):
            self._cmd_list = self.command.split()
        else:
            self._cmd_list = list(self.command)
        
        self._base_command = self._cmd_list[0]
        self._valid_command = True
    
    def _validate_security(self):
        """验证命令安全性"""
        if not self.safe_mode:
            return
            
        # 检查基本命令
        allowed_bases = set(self.allowed_commands)
        if self._base_command not in allowed_bases:
            self._log_warning(f"禁止的命令: {self._base_command} (不在白名单 {allowed_bases})")
            self._valid_command = False
            return
            
        # 检查命令模式（正则表达式）
        cmd_str = " ".join(self._cmd_list)
        for pattern in self.SAFE_COMMAND_PATTERNS:
            if re.match(pattern, cmd_str):
                return
                
        self._log_warning(f"不安全的命令模式: {cmd_str}")
        self._valid_command = False
    
    def _setup_kerberos(self):
        """设置Kerberos环境"""
        if not (self.kerberos_principal and self.kerberos_keytab):
            return
            
        kinit_path = os.path.join(self.hadoop_home, "bin", "kinit")
        kinit_cmd = [
            kinit_path, 
            "-kt", self.kerberos_keytab, 
            self.kerberos_principal
        ]
        
        # 添加kinit到预执行命令
        self._pre_commands.append(kinit_cmd)
        self._log_info(f"Kerberos认证: 主体={self.kerberos_principal}")
    
    def _prepare_environment(self):
        """准备执行环境变量"""
        self.env = {
            "HADOOP_HOME": self.hadoop_home,
            "HADOOP_CONF_DIR": self.conf_dir,
            "HADOOP_LOG_DIR": "/var/log/hadoop",
            "JAVA_HOME": self._get_java_home(),
            "PATH": f"{self.hadoop_home}/bin:{self._get_default_path()}",
        }
        
        # 设置NameNode信息（高可用场景）
        if self.fs_active_name:
            self.env["HDFS_ACTIVE_NAME"] = self.fs_active_name
            self.env["HADOOP_NAMENODE_OPTS"] = f"-Dfs.defaultFS=hdfs://{self.fs_active_name}"
        
        # 添加额外环境变量
        self.env.update(self.environment)
    
    def run(self):
        """执行Hadoop命令的工作流程"""
        if not self._valid_command:
            self._log_error("安全验证失败，拒绝执行命令")
            return False
            
        # 准备执行环境
        if not self._ready_environment():
            return False
            
        # 执行预操作
        if not self._run_pre_commands():
            return False
            
        # 主命令执行
        return self._run_main_command()
    
    def status(self):
        """检查命令执行状态（用于长时任务）"""
        return self._get_job_status(self.env["HADOOP_JOBID"])
    
    def _run_main_command(self):
        """执行主命令逻辑"""
        retry_count = 0
        last_result = None
        
        while retry_count <= self.max_retries:
            try:
                # 执行命令前准备新的Job ID（用于状态追踪）
                self.env["HADOOP_JOBID"] = self._generate_job_id()
                
                # 执行命令
                result = self._execute_subprocess(
                    self._cmd_list,
                    env=self.env,
                    timeout=self.timeout
                )
                
                # 处理结果
                if result.exit_code in self.success_codes:
                    self._log_success(result)
                    return True
                    
                # 处理失败
                self._log_failure(result)
                
                # 重试逻辑
                last_result = result
                if retry_count < self.max_retries:
                    retry_count += 1
                    self._log_info(f"将在 {self.retry_delay} 秒后重试 ({retry_count}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                else:
                    self._handle_final_failure(last_result, retry_count)
                    return False
                    
            except subprocess.TimeoutExpired as te:
                self._log_error(f"命令超时: {str(te)}")
                self._kill_timeout_process()
                last_result = te
                retry_count = self.max_retries  # 超时后不重试
            except Exception as e:
                self._log_error(f"执行异常: {str(e)}")
                last_result = e
                break
                
        self._handle_final_failure(last_result, retry_count)
        return False
    
    def _run_pre_commands(self):
        """执行预设命令（如Kerberos认证）"""
        for cmd in self._pre_commands:
            try:
                result = self._execute_subprocess(cmd, env=self.env)
                if result.exit_code != 0:
                    self._log_error(f"预命令执行失败: {cmd}")
                    return False
            except Exception as e:
                self._log_error(f"预命令异常: {cmd}, {str(e)}")
                return False
        return True
    
    def _execute_subprocess(self, cmd, env, timeout=None):
        """安全执行子进程"""
        self._log_info(f"执行命令: {self._mask_command(cmd)}")
        
        # 捕获输出
        stdout = ""
        stderr = ""
        exit_code = -1
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            
            # 实时输出处理
            while True:
                line_out = process.stdout.readline()
                if not line_out and process.poll() is not None:
                    break
                if line_out:
                    stdout += line_out
                    self._handle_output("stdout", line_out)
                    
                line_err = process.stderr.readline()
                if line_err:
                    stderr += line_err
                    self._handle_output("stderr", line_err)
            
            exit_code = process.wait(timeout=timeout)
        except Exception as e:
            # 确保进程终止
            if 'process' in locals():
                process.terminate()
            raise e
            
        return CommandResult(
            command=self._mask_command(cmd),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr
        )
    
    def _get_job_status(self, job_id):
        """获取作业状态（支持多种作业类型）"""
        if not job_id:
            return "UNKNOWN"
            
        # 根据作业ID前缀确定类型
        job_type = job_id.split("_")[0].lower()
        if job_type == "mapreduce":
            return self._check_mapreduce_job(job_id)
        elif job_type == "spark":
            return self._check_spark_application(job_id)
        else:
            return self._check_generic_job(job_id)
    
    def _handle_output(self, stream, line):
        """处理命令输出流"""
        # 敏感信息掩码
        if self.sensitive:
            line = self._mask_sensitive(line)
            
        # 实时日志记录
        if self.logoutput is True or (self.logoutput == "on_failure" and stream == "stderr"):
            logging.info(f"[{self.name}] {stream.upper()}: {line.strip()}")
            
        # 进度追踪
        self._detect_progress(line)
    
    def _handle_final_failure(self, result, attempt_count):
        """处理最终失败情况"""
        error_msg = (
            f"命令执行失败（重试 {attempt_count} 次）: " 
            f"{self._mask_command(self._cmd_list)}"
        )
        
        # 调用失败处理函数
        if callable(self.failure_handler):
            try:
                self.failure_handler(result, attempt_count)
            except Exception as handler_e:
                self._log_error(f"失败处理函数异常: {str(handler_e)}")
        
        # 标准错误日志
        if hasattr(result, "stderr") and result.stderr:
            self._log_error(f"错误输出: {self._mask_sensitive(result.stderr)}")
            
        self._log_error(error_msg)
        raise ExecutionError(error_msg, result)
    
    def _ready_environment(self):
        """准备执行环境（目录、权限等）"""
        try:
            # 创建日志目录（如果不存在）
            log_dir = self.env["HADOOP_LOG_DIR"]
            os.makedirs(log_dir, exist_ok=True)
            os.chmod(log_dir, 0o775)
            
            # 配置文件目录检查
            if not os.path.exists(self.conf_dir):
                self._log_error(f"{self.conf_dir} 配置目录不存在")
                return False
                
            return True
        except Exception as e:
            self._log_error(f"环境准备失败: {str(e)}")
            return False
    
    def _mask_command(self, command):
        """掩码敏感命令"""
        if not self.sensitive:
            return command
            
        clean_list = []
        for token in command:
            if token.startswith("--password") or token.startswith("--key"):
                clean_list.append(token.split("=")[0] + "=******")
            else:
                clean_list.append(token)
        return clean_list
    
    def _mask_sensitive(self, text):
        """掩码敏感文本"""
        patterns = [
            (r"(password=)\S+", r"\1******"),
            (r"(token=)[\w\.-]+", r"\1******"),
            (r"(api_key=)\S+", r"\1******")
        ]
        
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        return text
    
    def _log_info(self, message):
        logging.info(f"[ExecuteHadoop] {self.name}: {message}")
    
    def _log_warning(self, message):
        logging.warning(f"[ExecuteHadoop] {self.name}: {message}")
    
    def _log_error(self, message):
        logging.error(f"[ExecuteHadoop] {self.name}: {message}")
    
    # ---- 实用工具方法 ----    
    def _get_java_home(self):
        """查找Java Home路径"""
        java_home = os.environ.get("JAVA_HOME", "/usr/jdk/latest")
        if not os.path.exists(java_home):
            java_home = self._detect_java_home()
        return java_home
    
    def _detect_java_home(self):
        """自动探测Java安装路径"""
        possible_paths = [
            "/usr/jdk64/latest",
            "/usr/java/latest",
            "/usr/lib/jvm/java"
        ]
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "bin/java")):
                return path
        return "/usr/jdk/latest"  # 默认
    
    def _get_default_path(self):
        """获取系统默认PATH"""
        return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    
    def _generate_job_id(self):
        """生成唯一的作业ID"""
        import uuid
        timestamp = int(time.time())
        return f"job_{timestamp}_{uuid.uuid4().hex[:8]}"

    def _detect_progress(self, line):
        """从输出中检测进度信息"""
        progress_match = re.search(r"(\d+)%", line)
        if progress_match:
            progress = int(progress_match.group(1))
            self._report_progress(progress)
    
    def _report_progress(self, value):
        """报告进度（可扩展）"""
        logging.info(f"[{self.name}] 进度: {value}%")
        # 实际应用中可将进度推送到监控系统


class CommandResult:
    """命令执行结果封装"""
    def __init__(self, command, exit_code, stdout, stderr):
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
    
    def __str__(self):
        return (
            f"Command: {self.command}\n"
            f"Exit Code: {self.exit_code}\n"
            f"Stdout: {self.stdout[:200]}...\n"
            f"Stderr: {self.stderr[:200]}..."
        )


class ExecutionError(Exception):
    """自定义执行异常"""
    def __init__(self, message, result):
        super().__init__(message)
        self.result = result
        self.attempts = None
    
    def record_attempts(self, count):
        self.attempts = count

