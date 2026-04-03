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

强化的HDFS操作执行引擎
"""

from resource_management.core.base import Resource, ForcedListArgument, ResourceArgument
import os
import logging
import time
import re
import subprocess
from functools import wraps

class ExecuteHDFS(Resource):
    """
    HDFS操作执行资源
    
    提供安全、可靠、可监控的HDFS文件系统操作能力，支持：
    - Kerberos安全认证集成
    - 高可用HDFS集群操作
    - 智能重试与超时控制
    - 操作安全性校验
    - 实时进度追踪
    - 跨版本兼容支持
    
    使用示例：
        ExecuteHDFS(
            name="hdfs_data_migration",
            command="hdfs dfs -put /local/data /hdfs/data",
            user="hdfsadmin",
            conf_dir="/etc/hadoop/conf",
            kerberos_principal="hdfs@EXAMPLE.COM",
            kerberos_keytab="/etc/security/keytabs/hdfs.keytab",
            retries=5,
            backup=True,
            safe_mode=True
        )
    """
    
    ACTION_CHOICES = ["run", "dry-run", "simulate", "verify"]
    
    # Action参数配置
    action = ForcedListArgument(
        default="run",
        choices=ACTION_CHOICES,
        description="操作类型: 执行(run)/空运行(dry)/模拟(simulate)/验证(verify)"
    )
    
    # HDFS命令配置
    command = ResourceArgument(
        required=True,
        description="要执行的HDFS命令（字符串或列表形式）"
    )
    command_type = ResourceArgument(
        default="dfs",
        choices=["dfs", "dfsadmin", "fsck", "balancer", "zkfc"],
        description="HDFS命令类型"
    )
    
    # 执行控制
    retries = ResourceArgument(
        default=3,
        description="操作重试次数"
    )
    retry_delay = ResourceArgument(
        default=5,
        description="重试间隔时间(秒)"
    )
    timeout = ResourceArgument(
        default=600,
        description="命令超时时间(秒)"
    )
    
    # 安全与控制
    user = ResourceArgument(
        required=True,
        description="执行操作的系统用户"
    )
    kerberos_principal = ResourceArgument(
        description="Kerberos认证主体(principal@REALM)"
    )
    kerberos_keytab = ResourceArgument(
        description="Kerberos密钥表路径"
    )
    safe_mode = BooleanArgument(
        default=True,
        description="启用安全模式(限制危险操作)"
    )
    allowed_operations = ResourceArgument(
        default=["ls", "mkdir", "copyFromLocal", "copyToLocal", "get", "put", "test"],
        description="允许执行的操作列表"
    )
    
    # 环境配置
    logoutput = ResourceArgument(
        default="on_failure",
        choices=[True, False, "on_failure"],
        description="日志输出控制"
    )
    bin_dir = ForcedListArgument(
        default=[],
        description="自定义二进制目录(加入PATH)"
    )
    environment = ResourceArgument(
        default={},
        description="额外环境变量"
    )
    conf_dir = ResourceArgument(
        required=True,
        description="Hadoop配置目录"
    )
    hadoop_home = ResourceArgument(
        default="/usr/hdp/current/hadoop-client",
        description="Hadoop安装目录"
    )
    
    # 集群配置
    active_namenode = ResourceArgument(
        description="活动NameNode地址(用于高可用配置)"
    )
    standby_namenode = ResourceArgument(
        description="备用NameNode地址(用于高可用配置)"
    )
    
    # 备份与恢复
    backup = BooleanArgument(
        default=False,
        description="关键操作前自动备份受影响的HDFS路径"
    )
    backup_dir = ResourceArgument(
        default="/hdfs_backup",
        description="HDFS备份目录"
    )
    
    # 支持的资源操作
    actions = Resource.actions + ACTION_CHOICES
    
    # 安全危险命令模式
    DANGEROUS_COMMAND_PATTERNS = [
        r"hdfs\s+dfs\s+-rm\s+(-r|-f|-rf|-rR|--skipTrash)\s+[/\w]",
        r"hdfs\s+dfs\s+-rmdir\s+[/\w]",
        r"hdfs\s+zkfc\s+-formatZk",
        r"hdfs\s+dfs\s+(-expunge|df)",
        r"hdfs\s+dfsadmin\s+-finalizeUpgrade|saveNamespace"
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prepared = False
        self._safe_command = True
        self._error_message = None
        self._prepare_execution()
        
    def _prepare_execution(self):
        """准备执行环境"""
        try:
            self._resolve_command()
            self._validate_command()
            self._prepare_environment()
            self._prepare_kerberos()
            self._prepared = True
        except Exception as e:
            self._error_message = f"准备失败: {str(e)}"
            
    def _resolve_command(self):
        """解析命令格式"""
        if isinstance(self.command, str):
            # 分割命令字符串，但保留带空格的路径
            self._cmd_list = []
            temp = []
            in_quotes = False
            for char in self.command:
                if char == '"':
                    in_quotes = not in_quotes
                if char.isspace() and not in_quotes:
                    if temp:
                        self._cmd_list.append(''.join(temp))
                        temp = []
                else:
                    temp.append(char)
            if temp:
                self._cmd_list.append(''.join(temp))
        else:
            self._cmd_list = list(self.command)
        
        # 确保hdfs命令在第一位
        if "hdfs" not in self._cmd_list[0]:
            self._cmd_list = ["hdfs"] + self._cmd_list
            
    def _validate_command(self):
        """验证命令安全性"""
        if not self.safe_mode:
            self._safe_command = True
            return
            
        cmd_line = " ".join(self._cmd_list)
        
        # 1. 检查基本操作类型
        if self.command_type not in cmd_line:
            self._safe_command = False
            self._log_warning(f"命令类型不匹配: {self.command_type} vs {cmd_line}")
            return
            
        # 2. 检查允许的操作
        operation_found = False
        for op in self.allowed_operations:
            if op in cmd_line:
                operation_found = True
                break
                
        if not operation_found:
            self._safe_command = False
            self._log_warning(f"未检测到允许的操作: {cmd_line}")
            return
            
        # 3. 检查危险命令模式
        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if re.match(pattern, cmd_line):
                self._safe_command = False
                self._log_warning(f"检测到危险命令: {cmd_line}")
                return
                
        self._safe_command = True
        
    def _prepare_environment(self):
        """准备执行环境变量"""
        self._env = os.environ.copy()
        
        # 配置HADOOP环境
        self._env["HADOOP_HOME"] = self.hadoop_home
        self._env["HADOOP_CONF_DIR"] = self.conf_dir
        self._env["HADOOP_LOG_DIR"] = "/var/log/hadoop"
        self._env["HADOOP_USER_NAME"] = self.user
        
        # 配置Java环境
        java_home = os.environ.get("JAVA_HOME", "/usr/jdk64/latest")
        self._env["JAVA_HOME"] = java_home
        
        # 配置NameNode高可用
        if self.active_namenode:
            self._env["HDFS_NAMENODE_RPC_ADDRESS"] = self.active_namenode
            self._env["HADOOP_OPTS"] = (
                f"{self._env.get('HADOOP_OPTS', '')} "
                f"-Dfs.defaultFS=hdfs://{self.active_namenode}"
            )
        
        # 配置自定义PATH
        bin_paths = [f"{self.hadoop_home}/bin"] + self.bin_dir
        self._env["PATH"] = ":".join(bin_paths) + ":" + self._env.get("PATH", "")
        
        # 添加额外环境变量
        self._env.update(self.environment)
        
    def _prepare_kerberos(self):
        """准备Kerberos认证"""
        if not self.kerberos_principal or not self.kerberos_keytab:
            return
            
        kinit_cmd = [
            f"{self.hadoop_home}/bin/kinit", 
            "-kt", self.kerberos_keytab, 
            self.kerberos_principal
        ]
        
        try:
            result = subprocess.run(
                kinit_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                timeout=10,
                check=True
            )
            self._log_info(f"Kerberos认证成功: {self.kerberos_principal}")
        except Exception as e:
            self._log_error(f"Kerberos认证失败: {str(e)}")
            self._prepared = False
            return False
        return True
    
    def run(self):
        """执行HDFS命令的主方法"""
        if not self._prepared:
            self._log_error(f"无法执行: {self._error_message or '准备不充分'}")
            return False
            
        if not self._safe_command and "run" in self.action:
            self._log_error("安全验证失败，拒绝执行命令")
            return False
            
        if "dry-run" in self.action or "simulate" in self.action:
            self._log_info(f"模拟执行: {' '.join(self._cmd_list)}")
            return True
            
        backup_success = True
        try:
            # 关键操作前备份
            if self.backup and self._is_critical_operation():
                backup_success = self._create_hdfs_backup()
                if not backup_success:
                    self._log_warning("备份失败，继续执行操作...")
            
            return self._execute_with_retry()
        except Exception as e:
            self._log_error(f"执行失败: {str(e)}")
            return False
            
    def _is_critical_operation(self) -> bool:
        """检查是否是需要备份的关键操作"""
        critical_keywords = ["rm", "rename", "mv", "chown", "chmod", "del", "delete"]
        cmd_str = " ".join(self._cmd_list).lower()
        return any(kw in cmd_str for kw in critical_keywords)
        
    def _create_hdfs_backup(self) -> bool:
        """创建HDFS路径备份"""
        self._log_info("检测到关键操作，执行备份...")
        
        # 解析受影响的路径
        paths = self._parse_affected_paths()
        if not paths:
            self._log_warning("未识别到受影响路径，跳过备份")
            return True
            
        try:
            # 创建备份目录
            timestamp = int(time.time())
            backup_path = f"{self.backup_dir}/{timestamp}"
            mkdir_cmd = [
                "hdfs", "dfs", "-mkdir", "-p", backup_path
            ]
            self._execute_command(mkdir_cmd, "创建备份目录")
            
            # 备份每个路径
            for path in paths:
                base_name = os.path.basename(path.rstrip("/"))
                dest_path = f"{backup_path}/{base_name}"
                cp_cmd = [
                    "hdfs", "dfs", "-cp", path, dest_path
                ]
                self._execute_command(cp_cmd, f"备份 {path}")
            
            self._log_info(f"备份完成: {backup_path}")
            return True
        except Exception as e:
            self._log_error(f"备份失败: {str(e)}")
            return False
            
    def _parse_affected_paths(self) -> list:
        """解析命令中受影响的HDFS路径"""
        # 识别命令路径参数的位置
        path_keywords = ["-cp", "-mv", "-rm", "mkdir", "touch", "chown", "chmod"]
        paths = []
        cmd_length = len(self._cmd_list)
        
        for i, token in enumerate(self._cmd_list):
            token = token.strip().lower()
            
            # 处理目标路径参数
            if token in path_keywords and i + 2 < cmd_length:
                # 下一个或下下个可能是路径
                if self._cmd_list[i+1].startswith("/") and "hdfs:" not in self._cmd_list[i+1]:
                    paths.append(self._cmd_list[i+1])
                if i + 2 < cmd_length and self._cmd_list[i+2].startswith("/") and "hdfs:" not in self._cmd_list[i+2]:
                    paths.append(self._cmd_list[i+2])
            
            # 处理直接路径参数
            if token.startswith("hdfs:/") or token.startswith("/"):
                paths.append(token)
        
        # 去重并过滤
        return list(set([p for p in paths if p.startswith("/") and len(p) > 1]))
    
    def _execute_command(self, command: list, context: str = "HDFS操作") -> bool:
        """执行单个命令"""
        try:
            self._log_info(f"执行 {context}: {' '.join(command)}")
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                text=True
            )
            
            # 实时输出处理
            out_lines = []
            err_lines = []
            
            while True:
                line_out = process.stdout.readline()
                if line_out:
                    out_lines.append(line_out)
                    self._log_output("STDOUT", line_out)
                    
                line_err = process.stderr.readline()
                if line_err:
                    err_lines.append(line_err)
                    self._log_output("STDERR", line_err)
                    
                if process.poll() is not None:
                    break
                time.sleep(0.1)
            
            # 等待进程结束
            return_code = process.wait(self.timeout)
            
            # 成功状态
            if return_code == 0:
                self._log_info(f"{context} 成功完成")
                return True
            else:
                self._log_error(f"{context} 失败: 错误码 {return_code}")
                return False
                
        except Exception as e:
            self._log_error(f"{context} 异常: {str(e)}")
            return False
            
    def _execute_with_retry(self) -> bool:
        """带重试机制的执行"""
        attempt = 1
        success = False
        
        while attempt <= self.retries and not success:
            try:
                self._log_info(f"尝试 {attempt}/{self.retries}: 执行HDFS操作")
                
                process = subprocess.Popen(
                    self._cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=self._env,
                    text=True
                )
                
                # 实时处理和监控
                if self._monitor_command(process):
                    success = True
                    self._log_info(f"操作成功 [尝试 #{attempt}]")
                else:
                    self._log_warning(f"操作失败 [尝试 #{attempt}]")
                    attempt += 1
                    time.sleep(self.retry_delay)
                    
            except subprocess.TimeoutExpired:
                self._log_error(f"操作超时 [尝试 #{attempt}]")
                process.kill()
                attempt += 1
                
            except Exception as e:
                self._log_error(f"执行异常: {str(e)} [尝试 #{attempt}]")
                attempt += 1
                
        return success
        
    def _monitor_command(self, process) -> bool:
        """监控命令执行过程并处理输出"""
        start_time = time.time()
        last_progress = 0
        progress_detected = False
        
        # 进度监控正则表达式
        progress_patterns = [
            r"(\d+)%",
            r"(\d+\.\d+)%",
            r"Copied: (\d+)/\d+ files",
            r"Transferred \d+ bytes in \d+ files and (\d+)/\d+ directories"
        ]
        
        while True:
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                process.kill()
                raise subprocess.TimeoutExpired("命令执行超时", self.timeout)
                
            # 检查进程状态
            return_code = process.poll()
            if return_code is not None:
                # 收集剩余输出
                stdout, stderr = process.communicate()
                for line in stdout.splitlines():
                    self._log_output("STDOUT", line)
                for line in stderr.splitlines():
                    self._log_output("STDERR", line)
                    
                # 处理结果
                if return_code == 0:
                    if progress_detected:
                        self._log_info("操作完成: 100%")
                    return True
                else:
                    return False
                    
            # 处理输出
            line_out = process.stdout.readline()
            if line_out:
                progress = self._detect_progress(line_out, progress_patterns)
                if progress is not None:
                    if progress != last_progress:
                        self._log_info(f"操作进度: {progress}%")
                        last_progress = progress
                    progress_detected = True
                self._log_output("STDOUT", line_out)
                
            line_err = process.stderr.readline()
            if line_err:
                self._log_output("STDERR", line_err)
                
            time.sleep(0.1)
            
    def _detect_progress(self, line, patterns):
        """检测输出中的进度信息"""
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
        return None
        
    def _log_output(self, stream, line):
        """处理命令输出日志"""
        context = f"[HDFS] {self.name}"
        message = f"{context} {stream}: {line.rstrip()}"
        
        # 敏感信息掩码
        sensitive_patterns = [
            r"(password=)\S+",
            r"(SECRET )\"\w+\"",
            r"'[\w-]+\.key'",
            r"Kerberos key: \w+"
        ]
        for pattern in sensitive_patterns:
            line = re.sub(pattern, r"\1******", line)
            
        if self.logoutput is True:
            logging.info(message)
        elif self.logoutput == "on_failure":
            # 错误优先输出
            if stream == "STDERR":
                logging.error(message)
    
    def _log_info(self, message):
        logging.info(f"[ExecuteHDFS] {self.name}: {message}")
        
    def _log_warning(self, message):
        logging.warning(f"[ExecuteHDFS] {self.name}: {message}")
        
    def _log_error(self, message):
        logging.error(f"[ExecuteHDFS] {self.name}: {message}")

