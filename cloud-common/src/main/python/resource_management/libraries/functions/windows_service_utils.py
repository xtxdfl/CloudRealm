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

Enhanced Windows Service Management
"""

__all__ = [
    "check_windows_service_status",
    "check_windows_service_exists",
    "start_windows_service",
    "stop_windows_service",
    "restart_windows_service",
    "get_service_dependencies",
    "get_service_properties"
]

import win32service
import win32serviceutil
import win32api
import winerror
import time
import logging
from contextlib import contextmanager
from typing import Dict, List, Tuple, Optional

from resource_management.core.exceptions import (
    ComponentIsNotRunning, 
    ServiceOperationTimeout,
    ServiceConfigurationError
)
from resource_management.core.providers.windows.service import (
    safe_open_scmanager,
    safe_open_service,
)

# 日志配置
service_logger = logging.getLogger('windows_service')
service_logger.addHandler(logging.FileHandler('C:\\Windows\\Logs\\service_manager.log'))
service_logger.setLevel(logging.INFO)

# 全局常量
DEFAULT_TIMEOUT = 30  # 默认操作超时时间（秒）
MAX_SERVICE_NAME_LEN = 80
RETRY_INTERVAL = 1  # 轮询间隔（秒）
AUDIT_LOG_NAME = "Application"
AUDIT_SOURCE_NAME = "ServiceManager"

# 初始化事件日志
try:
    win32api.RegisterEventSource(None, AUDIT_SOURCE_NAME)
except win32api.error:
    pass

@contextmanager
def service_manager_handle():
    """SCM管理器上下文处理器"""
    scm_handle = None
    try:
        scm_handle = safe_open_scmanager()
        yield scm_handle
    finally:
        if scm_handle:
            win32service.CloseServiceHandle(scm_handle)


def check_windows_service_status(service_name: str, detailed=False) -> Tuple[bool, Optional[Dict]]:
    """
    增强型服务状态检查
    
    :param service_name: 服务名称
    :param detailed: 是否返回详细信息
    :return: (运行状态, 服务详细信息)
    """
    _validate_service_name(service_name)
    service_logger.info(f"Checking status of service: {service_name}")
    
    with service_manager_handle() as scm_handle:
        service_handle = safe_open_service(scm_handle, service_name)
        if not service_handle:
            if detailed:
                return False, {"error": f"服务 '{service_name}' 不存在"}
            return False
        
        try:
            status_info = win32service.QueryServiceStatusEx(service_handle)
            current_state = status_info["CurrentState"]
            is_running = current_state != win32service.SERVICE_STOPPED
            
            if not detailed:
                return is_running
            
            service_type = status_info["ServiceType"]
            controls_accepted = status_info["ControlsAccepted"]
            
            return is_running, {
                "state": _state_to_text(current_state),
                "service_type": _type_to_text(service_type),
                "pid": status_info["ProcessId"],
                "exit_code": status_info["Win32ExitCode"],
                "accepts_stop": bool(controls_accepted & win32service.SERVICE_ACCEPT_STOP),
                "accepts_pause": bool(controls_accepted & win32service.SERVICE_ACCEPT_PAUSE),
                "last_change": status_info["CheckPoint"],
                "wait_hint": status_info["WaitHint"],
                "start_type": _start_type_to_text(service_name),
                "dependencies": get_service_dependencies(service_name),
                "binary_path": _get_service_binary_path(service_name),
            }
        finally:
            win32service.CloseServiceHandle(service_handle)


def check_windows_service_exists(service_name: str) -> bool:
    """
    优化的服务存在性检查
    
    :return: 服务是否存在
    """
    _validate_service_name(service_name)
    
    with service_manager_handle() as scm_handle:
        # 尝试直接打开服务
        service_handle = safe_open_service(scm_handle, service_name)
        if service_handle:
            win32service.CloseServiceHandle(service_handle)
            return True
        
        service_logger.debug(f"服务 '{service_name}' 不存在")
        return False


def start_windows_service(service_name: str, timeout: int = DEFAULT_TIMEOUT):
    """
    安全的服务启动操作
    
    :param service_name: 服务名称
    :param timeout: 操作超时时间
    """
    _validate_service_name(service_name)
    service_logger.info(f"Starting service: {service_name}")
    
    if not check_windows_service_exists(service_name):
        raise ServiceConfigurationError(f"服务 '{service_name}' 不存在")
    
    # 检查当前状态
    is_running, status = check_windows_service_status(service_name, detailed=True)
    if is_running:
        service_logger.info(f"服务 '{service_name}' 已在运行状态: {status['state']}")
        return
    
    # 尝试启动服务
    try:
        win32serviceutil.StartService(service_name)
        _log_service_audit(service_name, "启动请求")
    except Exception as e:
        _handle_service_exception(e, service_name, "start")
    
    # 等待服务进入运行状态
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_windows_service_status(service_name):
            _log_service_audit(service_name, "启动成功")
            return
        time.sleep(RETRY_INTERVAL)
    
    # 操作超时处理
    _log_service_audit(service_name, "启动超时", win32service.ERROR_SERVICE_REQUEST_TIMEOUT)
    raise ServiceOperationTimeout(f"{service_name} 无法在 {timeout} 秒内启动")


def stop_windows_service(service_name: str, timeout: int = DEFAULT_TIMEOUT, force=False):
    """
    安全的服务停止操作
    
    :param service_name: 服务名称
    :param timeout: 操作超时时间
    :param force: 是否强制停止
    """
    _validate_service_name(service_name)
    service_logger.info(f"Stopping service: {service_name}, force={force}")
    
    # 检查当前状态
    is_running, status = check_windows_service_status(service_name, detailed=True)
    if not is_running:
        service_logger.info(f"服务 '{service_name}' 已停止")
        return
    
    # 检查是否可以正常停止
    if not force and not status.get("accepts_stop", True):
        service_logger.warning(f"服务 '{service_name}' 不接受停止请求，使用强制模式")
        force = True
    
    try:
        if force:
            # 强制终止服务进程
            import psutil
            process = psutil.Process(status["pid"])
            process.terminate()
            _log_service_audit(service_name, "强制停止请求")
        else:
            # 正常停止请求
            win32serviceutil.StopService(service_name)
            _log_service_audit(service_name, "停止请求")
    except Exception as e:
        _handle_service_exception(e, service_name, "stop")
    
    # 等待服务停止
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not check_windows_service_status(service_name):
            _log_service_audit(service_name, "停止成功")
            return
        time.sleep(RETRY_INTERVAL)
    
    # 超时后强制终止
    if force:
        raise ServiceOperationTimeout(f"无法停止服务 '{service_name}'")
    
    # 尝试强制停止
    stop_windows_service(service_name, timeout=5, force=True)


def restart_windows_service(service_name: str, start_timeout: int = DEFAULT_TIMEOUT, stop_timeout: int = DEFAULT_TIMEOUT):
    """
    安全重启服务
    
    :param start_timeout: 启动超时时间
    :param stop_timeout: 停止超时时间
    """
    service_logger.info(f"Restarting service: {service_name}")
    
    # 安全停止服务
    try:
        stop_windows_service(service_name, timeout=stop_timeout)
    except ComponentIsNotRunning:
        pass  # 服务未运行，直接继续
    
    # 启动服务
    start_windows_service(service_name, timeout=start_timeout)
    _log_service_audit(service_name, "重启完成")


def get_service_dependencies(service_name: str) -> List[str]:
    """
    获取服务的依赖关系
    
    :return: 依赖服务列表
    """
    with service_manager_handle() as scm_handle:
        service_handle = safe_open_service(scm_handle, service_name)
        if not service_handle:
            raise ServiceConfigurationError(f"服务 '{service_name}' 不存在")
        
        config = win32service.QueryServiceConfig(service_handle)
        return config[5] or []  # 返回依赖列表


def _validate_service_name(service_name: str):
    """验证服务名称有效性"""
    if not service_name or len(service_name) > MAX_SERVICE_NAME_LEN:
        raise ValueError(f"无效的服务名称: '{service_name}'")
    
    # 检查非法字符
    if any(c in service_name for c in "\\/:*?\"<>|"):
        raise ValueError(f"服务名称包含非法字符: '{service_name}'")


def _state_to_text(state: int) -> str:
    """服务状态转换文本"""
    states = {
        win32service.SERVICE_STOPPED: "已停止",
        win32service.SERVICE_START_PENDING: "启动中",
        win32service.SERVICE_STOP_PENDING: "停止中",
        win32service.SERVICE_RUNNING: "运行中",
        win32service.SERVICE_CONTINUE_PENDING: "继续中",
        win32service.SERVICE_PAUSE_PENDING: "暂停中",
        win32service.SERVICE_PAUSED: "已暂停"
    }
    return states.get(state, f"未知状态({state})")


def _type_to_text(service_type: int) -> str:
    """服务类型转换文本"""
    types = {
        win32service.SERVICE_KERNEL_DRIVER: "内核驱动",
        win32service.SERVICE_FILE_SYSTEM_DRIVER: "文件系统驱动",
        win32service.SERVICE_WIN32_OWN_PROCESS: "独立进程",
        win32service.SERVICE_WIN32_SHARE_PROCESS: "共享进程",
        win32service.SERVICE_INTERACTIVE_PROCESS: "交互进程"
    }
    return types.get(service_type & ~win32service.SERVICE_DRIVER, "未知类型")


def _start_type_to_text(service_name: str) -> str:
    """启动类型转为文本"""
    try:
        start_types = {
            win32service.SERVICE_BOOT_START: "BOOT_START",
            win32service.SERVICE_SYSTEM_START: "SYSTEM_START",
            win32service.SERVICE_AUTO_START: "AUTO_START",
            win32service.SERVICE_DEMAND_START: "DEMAND_START",
            win32service.SERVICE_DISABLED: "DISABLED"
        }
        
        key = win32serviceutil.GetServiceStartup(service_name)[0]
        return start_types.get(key, "UNKNOWN")
    except:
        return "N/A"


def _get_service_binary_path(service_name: str) -> str:
    """获取服务二进制路径"""
    with service_manager_handle() as scm_handle:
        service_handle = safe_open_service(scm_handle, service_name)
        if not service_handle:
            return "N/A"
        
        config = win32service.QueryServiceConfig(service_handle)
        return config[3]  # 二进制路径字段


def _handle_service_exception(e: Exception, service_name: str, operation: str):
    """统一处理服务异常"""
    if isinstance(e, win32service.error):
        code = e.winerror
        
        # Winerror代码处理
        error_map = {
            winerror.ERROR_SERVICE_NOT_ACTIVE: f"服务 '{service_name}' 未运行",
            winerror.ERROR_SERVICE_ALREADY_RUNNING: f"服务 '{service_name}' 已在运行",
            winerror.ERROR_SERVICE_DOES_NOT_EXIST: f"服务 '{service_name}' 未安装",
            winerror.ERROR_SERVICE_CANNOT_ACCEPT_CTRL: f"服务 '{service_name}' 无法接收控制请求"
        }
        
        msg = error_map.get(code, f"服务 '{service_name}' {operation}操作失败: {e.strerror}")
        service_logger.error(msg)
        raise ServiceOperationTimeout(msg) from e
    else:
        msg = f"服务 '{service_name}' {operation}操作失败: {str(e)}"
        service_logger.exception(msg)
        raise


def _log_service_audit(service_name: str, action: str, event_id: int = 0):
    """服务操作审计日志"""
    event_type = {
        0: win32service.EVENTLOG_SUCCESS,
        win32service.ERROR_SERVICE_REQUEST_TIMEOUT: win32service.EVENTLOG_ERROR_TYPE,
        win32service.ERROR_SERVICE_ALREADY_RUNNING: win32service.EVENTLOG_WARNING_TYPE
    }.get(event_id, win32service.EVENTLOG_INFORMATION_TYPE)
    
    # 创建事件日志记录
    win32api.ReportEvent(
        AUDIT_SOURCE_NAME,
        event_id or 0,
        0,  # 事件分类
        event_type,
        [f"服务 '{service_name}' - {action}"]
    )


class ServiceDependencyGraph:
    """服务依赖关系解析器"""
    
    def __init__(self):
        self.graph = {}
        self.resolved = set()
        self.unresolved = set()
        self.cycles = []
    
    def build(self, service_list):
        """构建依赖关系图"""
        for service in service_list:
            dependencies = get_service_dependencies(service)
            self.graph[service] = [dep for dep in dependencies if dep in service_list]
    
    def resolve_order(self, service: str) -> List[str]:
        """解析服务启动顺序"""
        self.resolved = set()
        self.unresolved = set()
        self.cycles = []
        
        order = []
        self._resolve(service, order)
        return order
    
    def _resolve(self, node: str, order: list):
        """深度优先依赖解析"""
        self.unresolved.add(node)
        
        for edge in self.graph.get(node, []):
            if edge not in self.resolved:
                if edge in self.unresolved:
                    self.cycles.append((node, edge))
                    continue
                self._resolve(edge, order)
        
        self.resolved.add(node)
        self.unresolved.remove(node)
        order.append(node)
    
    def get_start_order(self, include_self=True) -> List[str]:
        """获取安全启动顺序"""
        if not self.cycles:
            # 拓扑排序
            in_degree = {node: 0 for node in self.graph}
            for node, edges in self.graph.items():
                for edge in edges:
                    if edge in in_degree:
                        in_degree[edge] += 1
            
            queue = [node for node, degree in in_degree.items() if degree == 0]
            order = []
            
            while queue:
                node = queue.pop(0)
                order.append(node)
                
                for neighbor in self.graph.get(node, []):
                    if neighbor not in in_degree:
                        continue
                    
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            
            if include_self:
                order.append(list(self.graph.keys())[0])
            
            return order
        
        return list(self.graph.keys())


def secure_service_config(service_name: str, config: Dict):
    """服务配置安全增强检查"""
    # 1. 二进制路径检测
    bin_path = config["binary_path"].lower()
    if "temp" in bin_path:
        service_logger.warning(f"警告: 服务 '{service_name}' 二进制文件位于临时区域")
    
    # 2. 权限检测
    if "users" in config["account_name"].lower():
        service_logger.warning(f"警告: 服务 '{service_name}' 以用户级权限运行")
    
    # 3. 启动类型检测
    if config["start_type"] == "DISABLED":
        service_logger.info(f"服务 '{service_name}' 被禁用")
    
    # 4. 依赖项检测
    if not config["dependencies"]:
        service_logger.debug(f"服务 '{service_name}' 没有依赖项")
    
    return True
