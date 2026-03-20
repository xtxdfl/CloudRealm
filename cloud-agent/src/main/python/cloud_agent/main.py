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

import os
import sys
import logging
import time
import configparser
import resource
import locale
import platform
import socket
from threading import Event
from logging.handlers import SysLogHandler, RotatingFileHandler
from optparse import OptionParser

from cloud_agent.CloudConfig import CloudConfig
from cloud_agent.PingPortListener import PingPortListener
from cloud_agent import hostname
from cloud_agent.DataCleaner import DataCleaner
from cloud_agent.ExitHelper import ExitHelper
from cloud_agent.NetUtil import NetUtil
from cloud_commons import OSConst, OSCheck
from cloud_commons.shell import shellRunner
from cloud_commons.constants import cloud_SUDO_BINARY
from cloud_agent.InitializerModule import InitializerModule
from cloud_agent.HeartbeatHandlers import bind_signal_handlers

# 全局定义
LOGGING_FORMAT = "%(levelname)s %(asctime)s [%(module)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
AGENT_VERSION = "1.5.0"

class AgentLogger:
    """统一的日志管理系�?""
    def __init__(self, config):
        self.config = config
        self.loggers = {}
        
    def setup_logger(self, logger_name, log_file=None, level=logging.INFO):
        """配置指定名称的日志记录器"""
        if logger_name in self.loggers:
            return self.loggers[logger_name]
            
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.setLevel(level)
        
        # 清除原有处理�?        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 创建文件处理�?        if log_file:
            self._add_file_handler(logger, log_file, level)
        
        # 添加syslog处理�?        self._add_syslog_handler(logger)
        
        self.loggers[logger_name] = logger
        return logger
    
    def _add_file_handler(self, logger, log_file, level):
        """添加滚动文件日志处理�?""
        try:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                filename=log_file,
                mode='a',
                maxBytes=10_000_000,  # 10MB
                backupCount=25
            )
            formatter = logging.Formatter(LOGGING_FORMAT, DATE_FORMAT)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"File handler setup error: {str(e)}")
    
    def _add_syslog_handler(self, logger):
        """添加系统日志处理�?仅Linux)"""
        if not self._syslog_enabled() or platform.system() != "Linux":
            return
            
        try:
            syslog_handler = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL1)
            syslog_formatter = logging.Formatter("cloud_agent - %(filename)s - [%(process)d] - %(name)s - %(levelname)s - %(message)s")
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logging.error(f"Syslog handler setup error: {str(e)}")
    
    def _syslog_enabled(self):
        """检查是否启用syslog"""
        return self.config.has_option("logging", "syslog_enabled") and (
            int(self.config.get("logging", "syslog_enabled")) == 1
        )
    
    def update_log_level(self):
        """更新所有日志记录器的日志级�?""
        level = self._get_config_log_level()
        for logger in self.loggers.values():
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)
        return level
    
    def _get_config_log_level(self):
        """从配置获取日志级�?""
        log_level_str = self.config.get("agent", "loglevel", fallback="INFO").upper()
        return getattr(logging, log_level_str, logging.INFO)

class ServiceManager:
    """服务生命周期管理�?""
    @staticmethod
    def resolve_pid_file(home_dir=""):
        """解析PID文件路径"""
        pid_dir = os.environ.get("cloud_PID_DIR", "/var/run/cloud-agent")
        return os.path.join(pid_dir, "cloud-agent.pid")
    
    def write_pid_file(self, pid_file):
        """写入PID文件"""
        pid_dir = os.path.dirname(pid_file)
        os.makedirs(pid_dir, exist_ok=True)
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
            
    def remove_pid_file(self, pid_file):
        """移除PID文件"""
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except Exception as e:
                logging.error(f"Failed to remove PID file: {str(e)}")

class AutoRecoverySystem:
    """代理自动恢复机制"""
    def __init__(self, logger):
        self.logger = logger
        self.error_counter = {}
        self.last_error_time = {}
    
    def record_error(self, error_type):
        """记录错误并决定恢复动�?""
        now = time.time()
        self.error_counter[error_type] = self.error_counter.get(error_type, 0) + 1
        last_time = self.last_error_time.get(error_type, 0)
        time_since = now - last_time
        
        self.last_error_time[error_type] = now
        
        # 决定恢复动作
        if error_type == "server_connection":
            return self._handle_connection_error(self.error_counter[error_type], time_since)
        elif error_type == "resource_limit":
            self.logger.warning("Resource limitation detected")
            self._increase_resource_limits()
            return "retry"
        else:
            self.logger.error(f"Unknown error type: {error_type}")
            return "continue"
    
    def _handle_connection_error(self, count, time_since):
        """处理连接错误"""
        if count <= 3:
            wait_time = min(count * 5, 15)  # 5, 10, 15�?            action = f"retry after {wait_time}s"
        elif time_since < 300:  # 5分钟内频繁错�?            wait_time = min(30 * (count - 2), 300)  # 最�?分钟
            action = f"retry after {wait_time}s"
            self.logger.critical(f"Persistent connection issues (count={count})")
        else:
            self.error_counter["server_connection"] = 0
            action = "continue"
        
        self.logger.warning(f"Connection failed, {action}")
        return {
            "action": "wait",
            "duration": wait_time
        } if "wait" in action else {
            "action": "retry"
        }
    
    def _increase_resource_limits(self):
        """增加资源限制"""
        try:
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            new_limit = min(soft_limit * 2, hard_limit, 65536)
            resource.setrlimit(resource.RLIMIT_NOFILE, (soft_limit, new_limit))
            self.logger.info(f"Increased open files limit to {new_limit}")
        except Exception as e:
            self.logger.error(f"Resource limit increase failed: {str(e)}")

class AgentCore:
    """Cloud代理核心容器"""
    MAX_RETRIES = 10
    GRACEFUL_STOP_TRIES = 300
    GRACEFUL_STOP_INTERVAL = 0.1
    
    def __init__(self, options, initializer_module):
        self.options = options
        self.home_dir = options.home_dir
        self.stop_event = Event()
        self.initializer = initializer_module
        self.start_time = time.time()
        self.agent_pid = os.getpid()
        self.connection_counter = 0
        self.recovery = None
        self.logger = None
        self.config = None
        self.active_server = None
        
        # 系统资源
        self.pid_file = ServiceManager.resolve_pid_file(self.home_dir)
        self.service_manager = ServiceManager()
    
    def execute(self):
        """执行代理主逻辑"""
        try:
            # 初始化阶�?            self._print_banner()
            self._resolve_config()
            self._setup_logging()
            self._set_locale()
            
            # 启动前检�?            self._check_sudo_permissions()
            self._check_running_instances()
            self._check_prefix_directory()
            self._update_resource_limits()
            
            # 守护进程和配�?            self._daemonize()
            self._update_log_level()
            self.recovery = AutoRecoverySystem(self.logger)
            
            # 启动服务
            data_cleaner, ping_port_listener = self._start_services()
            
            # 主处理循�?            self._main_loop()
            
            # 清理阶段
            self._cleanup(data_cleaner, ping_port_listener)
            
        except SystemExit:
            raise
        except Exception as e:
            self._handle_fatal_error(e)
    
    def _print_banner(self):
        """打印启动横幅"""
        print(f"\n{'=' * 50}")
        print(f" Cloud Agent v{AGENT_VERSION} Starting ".center(50, '~'))
        print(f" PID: {self.agent_pid} {' ' * 15} ")
        print(f" Home: {self.home_dir} {' ' * 13} ")
        print(f"{'=' * 50}\n")
    
    def _resolve_config(self):
        """解析配置文件"""
        self.config = CloudConfig()
        default_cfg = {"agent": {"prefix": "/home/cloud"}}
        self.config.load(default_cfg)
        
        config_file = CloudConfig.getConfigFile(self.home_dir)
        if os.path.exists(config_file):
            try:
                self.config.read(config_file)
            except Exception as e:
                raise RuntimeError(f"Config parse error: {str(e)}")
            self.logger.debug(f"Configuration loaded from {config_file}")
    
    def _setup_logging(self):
        """配置日志系统"""
        agent_logger = AgentLogger(self.config)
        
        # 主日�?        main_logger = agent_logger.setup_logger(
            "cloud_agent",
            CloudConfig.getLogFile()
        )
        
        # 警报日志
        agent_logger.setup_logger(
            "cloud_alerts",
            CloudConfig.getAlertsLogFile()
        )
        
        # 资源管理日志
        agent_logger.setup_logger(
            "resource_management",
            CloudConfig.getLogFile()
        )
        
        # 更新日志级别
        agent_logger.update_log_level()
        
        self.logger = main_logger
        self.logger.info(f"Agent logging initialized (PID: {self.agent_pid})")
    
    def _set_locale(self):
        """设置系统区域设置"""
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error as e:
            self.logger.warning(f"Locale setup issue: {str(e)}")
    
    def _check_sudo_permissions(self):
        """验证sudo权限"""
        if os.geteuid() == 0:  # root用户无需检�?            return

        runner = shellRunner()
        test_command = [cloud_SUDO_BINARY, "/usr/bin/test", "/"]
        
        try:
            start_time = time.time()
            res = runner.run(test_command)
            duration = time.time() - start_time
            
            if res["exitCode"] != 0:
                raise PermissionError("Sudo validation failed. Please check sudo configuration.")
            
            if duration > 2:
                self.logger.warning(f"Sudo commands are slow ({duration:.2f}s), may impact performance")
        except Exception as e:
            self.logger.critical(f"Sudo permission check failed: {str(e)}")
            raise
    
    def _check_hostname_consistency(self):
        """检查主机名一致�?""
        if not self.options.expected_hostname:
            return
            
        current_hostname = hostname.hostname(self.config)
        if current_hostname != self.options.expected_hostname:
            err_msg = (
                f"Hostname mismatch!\n"
                f"  Configured: {self.options.expected_hostname}\n"
                f"  Actual: {current_hostname}\n"
                "Verify system hostname configuration."
            )
            self.logger.critical(err_msg)
            raise RuntimeError(err_msg)
    
    def _check_running_instances(self):
        """检查是否有其他实例运行"""
        if not OSCheck.get_os_family() == OSConst.WINSRV_FAMILY and os.path.exists(self.pid_file):
            self.logger.error(f"Agent already running (PID file found: {self.pid_file})")
            raise RuntimeError("Agent instance already running")
    
    def _check_prefix_directory(self):
        """检查前缀目录是否存在"""
        prefix_dir = self.config.get("agent", "prefix", fallback="")
        if not prefix_dir:
            self.logger.error("Agent prefix directory not configured")
            raise RuntimeError("Prefix directory configuration missing")
            
        abs_path = os.path.abspath(prefix_dir)
        if not os.path.isdir(abs_path):
            self.logger.error(f"Agent prefix directory does not exist: {abs_path}")
            raise RuntimeError("Prefix directory not found")
    
    def _update_resource_limits(self):
        """更新资源限制"""
        try:
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            open_files_ulimit = self.config.get_ulimit_open_files()
            
            if open_files_ulimit > soft_limit:
                resource.setrlimit(resource.RLIMIT_NOFILE, (soft_limit, open_files_ulimit))
                self.logger.info(f"Open files limit set to: {open_files_ulimit}")
            else:
                self.logger.info(f"Open files limit: {hard_limit} (unchanged)")
        except (ValueError, resource.error) as e:
            self.logger.error(f"Resource limit update failed: {str(e)}")
    
    def _daemonize(self):
        """作为守护进程运行"""
        if OSCheck.get_os_family() != OSConst.WINSRV_FAMILY:
            self.service_manager.write_pid_file(self.pid_file)
    
    def _update_log_level(self):
        """更新日志级别"""
        log_level = self.logger.getEffectiveLevel()
        level_name = logging.getLevelName(log_level)
        self.logger.info(f"Log level: {level_name}")
    
    def _start_services(self):
        """启动服务"""
        # 数据清理服务
        data_cleaner = None
        if self.config.get_int("agent", "data_cleanup_interval", default=0) > 0:
            try:
                data_cleaner = DataCleaner(self.config)
                data_cleaner.start()
                self.logger.info("Data cleanup service started")
            except Exception as e:
                self.logger.error(f"Data cleaner startup failed: {str(e)}")
        
        # Ping端口监听�?        ping_port_listener = None
        try:
            ping_port_listener = PingPortListener(self.config)
            ping_port_listener.start()
            self.logger.info("Ping port listener started")
        except Exception as e:
            self.logger.error(f"Ping listener startup failed: {str(e)}")
            if data_cleaner:
                data_cleaner.stop()
            raise
        
        return data_cleaner, ping_port_listener
    
    def _main_loop(self):
        """主处理循�?""
        self.logger.info("Entering main processing loop")
        
        # 绑定信号处理�?        bind_signal_handlers(self.agent_pid, self.stop_event)
        
        # 初始化核心模�?        self.initializer.init()
        
        # 连接服务�?        self._connect_to_server()
    
    def _connect_to_server(self):
        """连接服务�?""
        server_hostnames = hostname.server_hostnames(self.config)
        self.logger.info(f"Configured servers: {', '.join(server_hostnames) if server_hostnames else 'None'}")
        
        if not server_hostnames:
            self.logger.error("No servers configured, exiting")
            self.stop_event.set()
            return
        
        connected = False
        while not connected and not self.stop_event.is_set():
            for server_hostname in server_hostnames:
                server_url = self.config.get_api_url(server_hostname)
                self.logger.info(f"Attempting connection to {server_url}")
                
                try:
                    netutil = NetUtil(self.config, self.stop_event)
                    retries = 0
                    max_retries = self.MAX_RETRIES
                    
                    while retries < max_retries and not self.stop_event.is_set():
                        connected, stopped = netutil.try_to_connect(server_url, 1, self.logger)
                        
                        if connected:
                            self.logger.info(f"Connected to Cloud server: {server_hostname}")
                            self.active_server = server_hostname
                            self.connection_counter += 1
                            break
                        
                        retries += 1
                        self.logger.warning(f"Connection failed, retry {retries}/{max_retries}")
                        
                        # 应用重试延迟
                        wait = min(2 ** retries, 30)  # 指数避退, 上限30�?                        time.sleep(wait)
                    
                    if connected:
                        break
                
                except Exception as e:
                    self.logger.error(f"Connection attempt failed: {str(e)}")
                
                # 错误恢复
                recovery_action = self.recovery.record_error("server_connection")
                if recovery_action.get("action") == "wait":
                    self.stop_event.wait(recovery_action.get("duration", 10))
            
            # 所有服务器连接失败时的处理
            if not connected and not self.stop_event.is_set():
                wait_time = min(self.connection_counter * 15, 300)
                self.logger.warning(f"All server connections failed, waiting {wait_time}s before retry")
                self.stop_event.wait(wait_time)
        
        # 连接成功后启动核心线�?        if connected:
            self._start_core_threads()
    
    def _start_core_threads(self):
        """启动核心工作线程"""
        threads = [
            self.initializer.alert_scheduler_handler,
            self.initializer.heartbeat_thread,
            self.initializer.component_status_executor,
            self.initializer.command_status_reporter,
            self.initializer.host_status_reporter,
            self.initializer.alert_status_reporter,
            self.initializer.action_queue
        ]
        
        # 启动所有线�?        for thread in threads:
            thread.daemon = True
            thread.start()
            self.logger.info(f"Started thread: {thread.name}")
        
        # 主监控循�?        self.logger.info("Agent operational, monitoring components")
        try:
            while not self.stop_event.is_set():
                time.sleep(1)
                
                # 周期健康检�?                if int(time.time()) % 30 == 0:
                    active_threads = sum(1 for t in threads if t.is_alive())
                    self.logger.debug(f"Thread status: {active_threads}/{len(threads)} alive")
        except KeyboardInterrupt:
            self.stop_event.set()
        finally:
            self._stop_threads(threads)
    
    def _stop_threads(self, threads):
        """停止所有工作线�?""
        self.logger.info("Stopping worker threads")
        
        # 先结束ActionQueue (它可能正在阻塞其他资�?
        if self.initializer.action_queue and self.initializer.action_queue.is_alive():
            self.initializer.action_queue.interrupt()
            self.initializer.action_queue.join(timeout=5)
        
        # 停止其他线程
        for thread in threads:
            if thread != self.initializer.action_queue and thread.is_alive():
                thread.join(timeout=3)
                if thread.is_alive():
                    self.logger.warning(f"Thread {thread.name} did not stop gracefully")
    
    def _cleanup(self, data_cleaner, ping_port_listener):
        """清理资源"""
        self.logger.info("Starting cleanup process")
        
        # 停止数据清理服务
        if data_cleaner:
            data_cleaner.stop()
            self.logger.info("Data cleaner stopped")
        
        # 停止Ping监听�?        if ping_port_listener:
            ping_port_listener.stop()
            self.logger.info("Ping listener stopped")
        
        # 移除PID文件
        try:
            self.service_manager.remove_pid_file(self.pid_file)
            self.logger.debug("PID file removed")
        except Exception as e:
            self.logger.error(f"PID file removal error: {str(e)}")
        
        # 执行全局清理
        try:
            ExitHelper().exit()
        except Exception as e:
            self.logger.error(f"Exit cleanup error: {str(e)}")
        
        uptime = time.time() - self.start_time
        self.logger.info(f"Agent shutdown completed (uptime: {uptime:.1f}s)")
    
    def _handle_fatal_error(self, error):
        """处理致命错误"""
        if self.logger:
            self.logger.critical(f"Fatal error: {str(error)}", exc_info=True)
        else:
            logging.critical(f"Fatal error before logging setup: {str(error)}", exc_info=True)
        
        # 尝试清理资源
        try:
            self.service_manager.remove_pid_file(self.pid_file)
            ExitHelper().exit()
        except Exception:
            pass
        
        sys.exit(1)

def setup_option_parser():
    """设置命令行选项解析�?""
    parser = OptionParser()
    parser.add_option(
        "-v", "--verbose",
        action="store_true", 
        dest="verbose", 
        default=False,
        help="Enable verbose debug logging"
    )
    parser.add_option(
        "-e", "--expected-hostname",
        dest="expected_hostname", 
        default=None,
        help="Verify hostname matches expected value"
    )
    parser.add_option(
        "--home", 
        dest="home_dir", 
        default="",
        help="Agent home directory"
    )
    (options, args) = parser.parse_args()
    return options

def main():
    """代理主入�?""
    # 配置默认日志
    logging.basicConfig(
        level=logging.INFO,
        format=LOGGING_FORMAT,
        datefmt=DATE_FORMAT
    )
    
    try:
        # 初始化选项
        options = setup_option_parser()
        
        # 设置早期日志记录
        startup_logger = logging.getLogger("AgentStartup")
        
        # 显示启动横幅
        banner = [
            "╔════════════════════════════════════════╗",
           f"�?       Cloud Agent v{AGENT_VERSION}        �?,
            "�?    Distributed Monitoring Platform    �?,
            "╚════════════════════════════════════════╝"
        ]
        print("\n" + "\n".join(banner) + "\n")
        startup_logger.info("Agent initialization started")
        
        # 创建初始化和核心容器
        initializer_module = InitializerModule()
        agent_core = AgentCore(options, initializer_module)
        
        # 执行主逻辑
        agent_core.execute()
        
    except Exception as e:
        logging.critical(f"Agent crashed: {str(e)}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Agent terminated by user request")
        sys.exit(0)

if __name__ == "__main__":
    main()
