#!/usr/bin/env cloud-python-wrap
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

自定义服务钩子执行框�?
提供灵活的钩子系统，支持在服务的任意操作前后执行自定义脚本：
�?可扩展的事件驱动架构
�?强大的参数动态替换机�?�?详细的错误处理与日志记录
�?灵活的输出重定向控制
"""

__all__ = ["Hook"]

import os
import sys
import shlex
import logging
import signal
import tempfile
import traceback
import subprocess
from textwrap import indent
from resource_management.libraries.script import Script

class Hook(Script):
    """
    自定义服务钩子执行框�?    
    功能特点�?    1. 动态钩子执�? 通过 HOOK_METHOD_NAME 指定执行方法
    2. 参数智能替换: 自动检测并修正 before-/after- 事件
    3. 完整错误处理: 提供详细的错误日志和诊断信息
    4. 输出捕获: 标准输出和错误记录到临时文件
    5. 钩子链支�? 可执行多个钩子操�?    
    使用场景�?    �?在服务启动前后执行环境检�?    �?在配置更改后重新加载服务
    �?在安装前验证系统依赖
    �?在操作失败后自动清理资源
    """
    
    # 常量定义
    HOOK_METHOD_NAME = "hook"          # 钩子执行方法�?    HOOK_PHASES = ("before", "after")  # 钩子支持的生命周期阶�?    DEFAULT_TMP_DIR = "/tmp/cloud"   # 默认临时目录
    TIMEOUT = 300                      # 钩子执行超时时间(�?
    
    def __init__(self):
        """初始化钩子执行环�?""
        super(Hook, self).__init__()
        
        # 设置日志记录�?        self.logger = logging.getLogger("HookFramework")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # 确保临时目录存在
        os.makedirs(self.DEFAULT_TMP_DIR, exist_ok=True)
        
        # 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.warning(f"接收到信�?{signum}，正在终止钩子执�?..")
        sys.exit(1)
    
    def choose_method_to_execute(self, command_name):
        """
        覆盖父类方法，始终执行预定义的钩子方�?        
        :param command_name: 命令名称(在钩子框架中始终重写�?HOOK_METHOD_NAME)
        :return: HOOK_METHOD_NAME
        """
        self.logger.debug(f"钩子方法重定�? {command_name} -> {self.HOOK_METHOD_NAME}")
        return super(Hook, self).choose_method_to_execute(self.HOOK_METHOD_NAME)
    
    def _parse_hook_type(self):
        """解析钩子类型(before|after)和目标命�?""
        try:
            full_command = sys.argv[1]
            for phase in self.HOOK_PHASES:
                if full_command.startswith(phase + "-"):
                    return phase, full_command[len(phase)+1:]
            
            self.logger.error(f"无效的钩子命令格�? {full_command}")
            self.logger.info("有效格式应为: [before|after]-<command>")
            sys.exit(1)
        except IndexError:
            self.logger.error("缺少钩子命令参数")
            sys.exit(1)
    
    def _create_temp_files(self, hook_name, hook_phase):
        """为钩子创建临时输出文�?""
        tmp_prefix = f"{hook_phase}-{hook_name}"
        out_file = tempfile.mktemp(prefix=tmp_prefix, suffix=".out", dir=self.DEFAULT_TMP_DIR)
        err_file = tempfile.mktemp(prefix=tmp_prefix, suffix=".err", dir=self.DEFAULT_TMP_DIR)
        
        self.logger.debug(f"标准输出重定向到: {out_file}")
        self.logger.debug(f"标准错误重定向到: {err_file}")
        
        return out_file, err_file
    
    def _update_cmd_args(self, target_command):
        """更新命令行参数以执行目标命令"""
        # 获取原始参数
        args = sys.argv.copy()
        
        # 替换脚本名称和命�?        script_path = args[0]
        target_script = script_path.replace(args[1], target_command)
        
        if os.path.exists(target_script):
            args[0] = target_script
            args[1] = target_command
        else:
            self.logger.error(f"无法定位钩子脚本: {target_script}")
            self.logger.debug(f"在当前路�? {os.getcwd()}")
            sys.exit(1)
        
        # 更新基础目录
        try:
            base_dir = args[3]
            updated_base_dir = base_dir.replace(os.path.basename(base_dir), target_command)
            if os.path.exists(updated_base_dir):
                args[3] = updated_base_dir
            else:
                self.logger.warning(f"基础目录不存�? {updated_base_dir}, 使用原始目录")
        except IndexError:
            pass  # �?args[3] 不存在时忽略
        
        return args
    
    def _run_command(self, cmd_args, out_file, err_file):
        """执行钩子命令并处理输�?""
        cmd_str = " ".join(shlex.quote(arg) for arg in cmd_args)
        self.logger.info(f"执行钩子命令: {cmd_str}")
        
        try:
            # 准备环境变量
            env = os.environ.copy()
            env['HOOK_PHASE'] = sys.argv[1].split('-')[0]
            env['HOOK_TARGET'] = self.target_command
            
            # 执行命令并捕获输�?            with open(out_file, 'w') as out_f, open(err_file, 'w') as err_f:
                process = subprocess.run(
                    cmd_args,
                    env=env,
                    stdout=out_f,
                    stderr=err_f,
                    timeout=self.TIMEOUT,
                    start_new_session=False
                )
            
            return process.returncode
        except subprocess.TimeoutExpired:
            self.logger.error(f"钩子执行超时: 超过 {self.TIMEOUT} �?)
            return 1
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(f"执行钩子时发生异�? {str(e)}\n错误详情:\n{indent(tb, '  ')}")
            return 2
    
    def _read_output_files(self, out_file, err_file):
        """读取输出文件内容并返�?""
        def safe_read(file_path):
            try:
                with open(file_path, 'r') as f:
                    return f.read()
            except Exception:
                return f"无法读取文件 {file_path}"
        
        return safe_read(out_file), safe_read(err_file)
    
    def run_custom_hook(self, hook_name=None):
        """
        执行自定义钩子入口点
        
        :param hook_name: 可选参数，指定要执行的钩子名称
        """
        self.hook_phase, self.target_command = self._parse_hook_type()
        hook_display_name = hook_name or sys.argv[1]
        
        # 创建临时输出文件
        out_file, err_file = self._create_temp_files(
            self.target_command, self.hook_phase
        )
        
        self.logger.info(f"开始执�?{self.hook_phase.upper()} 钩子: {hook_display_name}")
        
        # 更新命令行参�?        if hook_name:
            self.logger.debug(f"使用指定的钩子名�? {hook_name}")
            target_command = hook_name
        else:
            target_command = self.target_command
        
        cmd_args = self._update_cmd_args(target_command)
        self.logger.debug(f"更新后的命令行参�? {cmd_args}")
        
        # 执行钩子命令
        return_code = self._run_command(cmd_args, out_file, err_file)
        
        # 读取执行结果
        stdout_content, stderr_content = self._read_output_files(out_file, err_file)
        
        # 日志记录
        if stdout_content.strip():
            self.logger.info(f"钩子标准输出:\n{indent(stdout_content, '  ')}")
        else:
            self.logger.debug("钩子未产生标准输�?)
        
        if stderr_content.strip():
            if return_code == 0:
                self.logger.warning(f"钩子标准错误:\n{indent(stderr_content, '  ')}")
            else:
                self.logger.error(f"钩子标准错误:\n{indent(stderr_content, '  ')}")
        else:
            self.logger.debug("钩子未产生标准错�?)
        
        # 清理临时文件
        try:
            os.remove(out_file)
            os.remove(err_file)
        except OSError as e:
            self.logger.warning(f"清理临时文件失败: {str(e)}")
        
        # 处理返回�?        if return_code != 0:
            error_msg = f"钩子执行失败: {hook_display_name} (退出码: {return_code})"
            if stderr_content:
                error_msg += f"\n错误摘要: {stderr_content[:256]}{'...' if len(stderr_content) > 256 else ''}"
            
            self.logger.error(error_msg)
            sys.exit(return_code)
        
        self.logger.info(f"钩子执行成功: {hook_display_name}")
    
    def hook(self):
        """钩子方法入口点（框架自动调用�?""
        self.logger.info("=" * 60)
        self.logger.info("自定义钩子框架启�?)
        self.logger.info(f"命令行参�? {sys.argv}")
        self.logger.info("-" * 60)
        
        try:
            self.run_custom_hook()
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.critical(f"处理钩子时发生未捕获异常: {str(e)}\n堆栈跟踪:\n{indent(tb, '  ')}")
            sys.exit(255)
        
        self.logger.info("钩子框架执行完成")
        self.logger.info("=" * 60)


if __name__ == "__main__":
    # 确保在模块直接运行时能够执行钩子
    hook = Hook()
    hook.execute()
