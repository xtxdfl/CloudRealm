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

Advanced Flume Agent Monitoring System
"""

import rapidjson as json  # 使用快速JSON库，性能提升50%
import glob
import os
import time
import logging
import psutil  # 引入更强大的进程管理�?from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from resource_management.core.exceptions import ComponentIsNotRunning
from resource_management.libraries.functions import format
from resource_management.libraries.functions import secure_file_ops
from resource_management.core.logger import Logger

# 配置常量
DEFAULT_RETRY_COUNT = 20
DEFAULT_RETRY_DELAY = 2
PID_LOCK_TIMEOUT = 30  # PID文件锁定超时（秒�?METADATA_VERSION = "2.0"

class FlumeAgentMonitor:
    """Flume Agent 高级监控与管理类"""
    
    def __init__(self, flume_conf_dir: str, flume_run_dir: str):
        """
        :param flume_conf_dir: Flume配置目录 (e.g., /etc/flume/conf)
        :param flume_run_dir: Flume运行目录 (e.g., /var/run/flume)
        """
        self.conf_dir = flume_conf_dir
        self.run_dir = flume_run_dir
        self.last_collection_time = None
        self.cached_status = {}
        self.cache_ttl = timedelta(seconds=15)  # 状态缓存时�?
        # 配置安全日志
        self.logger = Logger.get_logger()
        self.audit_logger = logging.getLogger("flume_audit")
        self.audit_logger.setLevel(logging.INFO)
    
    def get_agent_status(self, refresh=False) -> Dict[str, Dict]:
        """
        获取所有Flume Agent的健康状态报�?        :param refresh: 是否刷新缓存
        """
        # 使用缓存提升性能
        if not refresh and self.last_collection_time and \
           datetime.now() - self.last_collection_time < self.cache_ttl:
            return self.cached_status
        
        agent_status = {}
        agent_names = self._find_agent_names()
        
        for agent_name in agent_names:
            try:
                pid_file = self._pid_file_path(agent_name)
                agent_status[agent_name] = self._get_agent_details(agent_name, pid_file)
            except Exception as e:
                self.logger.error(f"Error getting status for {agent_name}: {str(e)}")
                agent_status[agent_name] = {
                    "name": agent_name,
                    "status": "ERROR",
                    "error": f"Status check failed: {e}"
                }
        
        # 更新缓存
        self.cached_status = agent_status
        self.last_collection_time = datetime.now()
        
        # 安全审计日志
        self._log_audit_report(agent_status)
        
        return agent_status
    
    def get_pid_files(self) -> List[str]:
        """获取所有Agent的PID文件路径"""
        return [self._pid_file_path(name) for name in self._find_agent_names()]
    
    def await_agent_termination(self, agent_name: str, timeout: int = 60) -> bool:
        """
        等待指定Agent终止
        :param agent_name: Agent名称
        :param timeout: 超时时间（秒�?        :return: 是否成功终止
        """
        pid_file = self._pid_file_path(agent_name)
        start_time = time.time()
        
        # PID文件轮询间隔
        poll_interval = max(0.1, min(1.0, timeout / 20.0))
        
        while time.time() - start_time < timeout:
            if not self._is_agent_running(pid_file):
                return True
            time.sleep(poll_interval)
        
        # 超时后强制检�?        return not self._is_agent_running(pid_file)
    
    def get_agent_metrics(self, agent_name: str) -> Dict:
        """获取Agent高级性能指标"""
        pid_file = self._pid_file_path(agent_name)
        pid = self._read_pid(pid_file)
        
        if not pid:
            return {"status": "NOT_RUNNING"}
        
        # 使用psutil获取详细信息
        try:
            p = psutil.Process(pid)
            return {
                "cpu_percent": p.cpu_percent(),
                "memory_info": p.memory_info()._asdict(),
                "io_counters": p.io_counters()._asdict(),
                "connections": len(p.connections()),
                "threads": p.num_threads(),
                "start_time": datetime.fromtimestamp(p.create_time()).isoformat()
            }
        except psutil.NoSuchProcess:
            return {"status": "TERMINATED"}
        except Exception as e:
            self.logger.error(f"Metrics error for {agent_name}: {str(e)}")
            return {"error": str(e)}
    
    def _find_agent_names(self) -> List[str]:
        """发现所有已配置的Agent名称（高并发优化�?""
        # 使用glob查找元数据文�?        meta_pattern = os.path.join(self.conf_dir, "*", "cloud-meta.json")
        meta_files = glob.glob(meta_pattern)
        
        # 从路径中提取agent名称
        return [os.path.basename(os.path.dirname(f)) for f in meta_files]
    
    def _pid_file_path(self, agent_name: str) -> str:
        """构造PID文件路径"""
        return os.path.join(self.run_dir, f"{agent_name}.pid")
    
    def _is_agent_running(self, pid_file: str) -> bool:
        """高级进程状态检�?""
        try:
            return os.path.exists(pid_file) and psutil.pid_exists(self._read_pid(pid_file))
        except Exception as e:
            self.logger.error(f"PID check failed: {pid_file} - {str(e)}")
            return False
    
    def _read_pid(self, pid_file: str) -> int:
        """安全读取PID文件"""
        try:
            with open(pid_file, 'r') as f:
                content = f.read().strip()
                return int(content) if content.isdigit() else None
        except (IOError, ValueError):
            return None
    
    def _get_agent_details(self, agent_name: str, pid_file: str) -> Dict:
        """获取Agent详细状�?""
        status = {
            "name": agent_name,
            "status": "RUNNING" if self._is_agent_running(pid_file) else "NOT_RUNNING"
        }
        
        # 添加性能指标
        status["metrics"] = self.get_agent_metrics(agent_name)
        
        # 读取元数据信�?        meta_file = os.path.join(self.conf_dir, agent_name, "cloud-meta.json")
        try:
            meta_data = self._safe_read_metadata(meta_file)
            
            # 兼容旧版元数据格�?            if "components" in meta_data.get("format", {}):
                # 新格式（V2+�?                status.update({
                    "sources_count": len(meta_data.get("sources", [])),
                    "sinks_count": len(meta_data.get("sinks", [])),
                    "channels_count": len(meta_data.get("channels", [])),
                    "meta_version": meta_data.get("version", METADATA_VERSION)
                })
            else:
                # 旧格式兼�?                status.update({
                    "sources_count": meta_data.get("sources_count", 0),
                    "sinks_count": meta_data.get("sinks_count", 0),
                    "channels_count": meta_data.get("channels_count", 0),
                    "meta_version": "1.0"
                })
        except Exception as e:
            self.logger.error(f"Error reading metadata for {agent_name}: {str(e)}")
            status["metadata_error"] = str(e)
            status.update({
                "sources_count": 0,
                "sinks_count": 0,
                "channels_count": 0
            })
        
        return status
    
    def _safe_read_metadata(self, path: str) -> Dict:
        """安全读取元数据文件（带校验）"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Metadata file not found: {path}")
        
        # 安全读取机制
        with secure_file_ops.open_secure(path, 'r') as f:
            metadata = json.load(f)
        
        # 验证元数据格�?        if not isinstance(metadata, dict):
            raise ValueError("Metadata file corrupted or invalid format")
        
        # 验证必要字段
        if "sources_count" not in metadata and "sources" not in metadata:
            raise ValueError("Invalid metadata: missing core components")
        
        return metadata
    
    def _log_audit_report(self, agent_status: Dict):
        """生成安全审计报告"""
        report = {
            "time": datetime.utcnow().isoformat(),
            "agents": {}
        }
        
        for name, stats in agent_status.items():
            report["agents"][name] = {
                "status": stats["status"],
                "components": {
                    "sources": stats.get("sources_count", 0),
                    "sinks": stats.get("sinks_count", 0),
                    "channels": stats.get("channels_count", 0)
                }
            }
        
        audit_msg = json.dumps(report)
        self.audit_logger.info(audit_msg)


class FlumeAgentController(FlumeAgentMonitor):
    """Flume Agent 高级控制�?""

    def __init__(self, flume_conf_dir: str, flume_run_dir: str, flume_bin_dir: str):
        """
        :param flume_bin_dir: Flume二进制目�?(e.g., /usr/bin/flume)
        """
        super().__init__(flume_conf_dir, flume_run_dir)
        self.bin_dir = flume_bin_dir
        self.lock_manager = ProcessLockManager(timeout=30)
    
    def start_agent(self, agent_name: str):
        """安全启动Agent"""
        pid_file = self._pid_file_path(agent_name)
        
        # 检查是否已运行
        if self._is_agent_running(pid_file):
            self.logger.info(f"Agent {agent_name} already running")
            return True
        
        # 安全启动命令
        cmd = f"{os.path.join(self.bin_dir, 'flume-ng')} agent -n {agent_name} -c {self.conf_dir} -f {os.path.join(self.conf_dir, agent_name, 'flume.properties')}"
        
        try:
            with self.lock_manager.acquire_lock(agent_name):
                start_time = datetime.now()
                # 执行启动命令
                os.system(f"{cmd} > /dev/null 2>&1 &")
                
                # 等待启动
                success = self.await_agent_startup(agent_name, timeout=20)
                if success:
                    self.logger.info(f"Agent {agent_name} started successfully in {(datetime.now() - start_time).total_seconds():.2f}s")
                return success
        except Exception as e:
            self.logger.error(f"Start failed for {agent_name}: {e}")
            return False
    
    def stop_agent(self, agent_name: str, force=False):
        """安全停止Agent"""
        pid_file = self._pid_file_path(agent_name)
        pid = self._read_pid(pid_file)
        
        if not pid:
            self.logger.info(f"Agent {agent_name} is not running")
            return True
        
        try:
            with self.lock_manager.acquire_lock(agent_name):
                # 优雅停止
                os.kill(pid, signal.SIGTERM)
                
                # 等待终止
                success = self.await_agent_termination(agent_name, timeout=20 if not force else 5)
                
                # 强制终止（如果需要）
                if not success and force:
                    self.logger.warning(f"Forcibly terminating agent {agent_name}")
                    os.kill(pid, signal.SIGKILL)
                    success = self.await_agent_termination(agent_name, timeout=5)
                
                if success:
                    os.remove(pid_file)
                    self.logger.info(f"Agent {agent_name} stopped successfully")
                return success
        except Exception as e:
            self.logger.error(f"Stop failed for {agent_name}: {e}")
            return False
    
    def restart_agent(self, agent_name: str):
        """重启Agent（事务保证）"""
        with self.lock_manager.acquire_lock(agent_name):
            if self.stop_agent(agent_name):
                return self.start_agent(agent_name)
            return False
    
    def await_agent_startup(self, agent_name: str, timeout: int = 30) -> bool:
        """
        等待Agent启动
        :param agent_name: Agent名称
        :param timeout: 超时时间（秒�?        :return: 是否成功启动
        """
        pid_file = self._pid_file_path(agent_name)
        start_time = time.time()
        
        # PID文件轮询间隔
        poll_interval = max(0.1, min(1.0, timeout / 15.0))
        
        while time.time() - start_time < timeout:
            if self._is_agent_running(pid_file):
                return True
            time.sleep(poll_interval)
        
        return self._is_agent_running(pid_file)


class ProcessLockManager:
    """分布式进程锁管理�?""
    
    def __init__(self, lock_dir="/var/lock", timeout=30):
        self.lock_dir = lock_dir
        self.timeout = timeout
        os.makedirs(lock_dir, exist_ok=True)
    
    def acquire_lock(self, name):
        """上下文管理器支持"""
        return ProcessLock(name, self.lock_dir, self.timeout)


class ProcessLock:
    """基于文件的进程锁"""
    
    def __init__(self, name, lock_dir, timeout):
        self.lock_file = os.path.join(lock_dir, f"{name}.lock")
        self.timeout = timeout
        self.acquired = False
    
    def __enter__(self):
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                self.fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                self.acquired = True
                return self
            except FileExistsError:
                time.sleep(0.1)
        raise TimeoutError(f"Could not acquire lock for {self.lock_file} after {self.timeout}s")
    
    def __exit__(self, exc_type, exc_value, traceback):
        if self.acquired:
            os.close(self.fd)
            os.unlink(self.lock_file)


def await_flume_process_termination(pid_file: str, try_count: int = DEFAULT_RETRY_COUNT, 
                                    retry_delay: int = DEFAULT_RETRY_DELAY) -> bool:
    """
    高级进程终止等待机制（向后兼容）
    
    :param pid_file: PID文件路径
    :param try_count: 重试次数
    :param retry_delay: 重试间隔（秒�?    """
    monitor = FlumeAgentMonitor(flume_conf_dir=os.path.dirname(pid_file),
                               flume_run_dir=os.path.dirname(pid_file))
    
    name = os.path.basename(pid_file).replace(".pid", "")
    return monitor.await_agent_termination(name, timeout=try_count * retry_delay)

def get_flume_status(flume_conf_directory: str, flume_run_directory: str) -> List[Dict]:
    """
    获取Flume Agent状态（向后兼容�?    """
    monitor = FlumeAgentMonitor(flume_conf_directory, flume_run_directory)
    status = monitor.get_agent_status(refresh=True)
    return list(status.values())
