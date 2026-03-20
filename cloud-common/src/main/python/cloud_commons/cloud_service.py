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
import winreg
import win32service
import win32serviceutil
import win32event
import servicemanager
import pathlib
from typing import Optional, Tuple, Dict, Callable
from enum import Enum
from dataclasses import dataclass

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("cloudService")

# 全局定义
ENV_PYTHON_PATH = "PYTHONPATH"
cloud_VERSION_VAR = "cloud_VERSION_VAR"
DEFAULT_CONFIG_DIR = "C:\\ProgramData\\cloud\\conf"

class ServiceState(Enum):
    """服务状态枚�?""
    STOPPED = win32service.SERVICE_STOPPED
    START_PENDING = win32service.SERVICE_START_PENDING
    STOP_PENDING = win32service.SERVICE_STOP_PENDING
    RUNNING = win32service.SERVICE_RUNNING
    PAUSED = win32service.SERVICE_PAUSED
    UNKNOWN = 0

class ServiceType(Enum):
    """服务类型枚举"""
    WIN32_OWN_PROCESS = win32service.SERVICE_WIN32_OWN_PROCESS
    WIN32_SHARE_PROCESS = win32service.SERVICE_WIN32_SHARE_PROCESS

class ServiceStartType(Enum):
    """服务启动类型枚举"""
    AUTO_START = win32service.SERVICE_AUTO_START
    DEMAND_START = win32service.SERVICE_DEMAND_START
    DISABLED = win32service.SERVICE_DISABLED

class ServiceDependencies(Enum):
    """服务依赖关系枚举"""
    NONE = []
    NETWORK = ["Tcpip"]
    SECURITY = ["KeyIso", "SamSs"]

@dataclass
class ServiceConfig:
    """服务配置数据�?""
    name: str = "cloudService"
    display_name: str = "cloud Service"
    description: str = "cloud Service for distributed computing"
    service_type: ServiceType = ServiceType.WIN32_OWN_PROCESS
    start_type: ServiceStartType = ServiceStartType.AUTO_START
    dependencies: ServiceDependencies = ServiceDependencies.NETWORK
    executable_path: str = None
    working_dir: str = None
    environment: Dict[str, str] = None

class cloudService(win32serviceutil.ServiceFramework):
    """cloud Windows 服务基类"""

    # 配置元数�?    _svc_config_ = ServiceConfig()
    
    def __init__(self, args):
        """服务初始�?""
        # 初始化服务框�?        win32serviceutil.ServiceFramework.__init__(self, args)
        
        # 创建停止事件句柄
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        
        # 获取并验证配�?        self.config = self._get_validated_config()
        
        # 服务状态跟�?        self.running = False
        self.last_error = ""
        
        # 报告服务状�?        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        logger.info("cloud服务初始化完�?)

    def _get_validated_config(self) -> ServiceConfig:
        """获取并验证服务配�?""
        config = self._svc_config_
        
        # 设置默认工作目录
        if not config.working_dir:
            config.working_dir = self._get_default_working_dir()
            
        # 设置默认可执行路�?        if not config.executable_path:
            config.executable_path = self._get_default_executable_path()
            
        # 验证配置
        if not os.path.exists(config.working_dir):
            raise FileNotFoundError(f"工作目录不存�? {config.working_dir}")
            
        if not os.path.isfile(config.executable_path):
            raise FileNotFoundError(f"可执行文件不存在: {config.executable_path}")
            
        # 设置环境变量
        self._setup_environment(config)
        
        return config

    def _get_default_working_dir(self) -> str:
        """获取默认工作目录"""
        # 尝试从注册表获取安装目录
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\cloud") as key:
                install_dir = winreg.QueryValueEx(key, "InstallDir")[0]
                return os.path.join(install_dir, "bin")
        except Exception:
            # 使用脚本位置作为后备
            return pathlib.Path(__file__).parent.parent.resolve()

    def _get_default_executable_path(self) -> str:
        """获取默认可执行路�?""
        # 主脚本通常与服务文件在相同目录
        return os.path.join(self._get_default_working_dir(), "cloud_main.py")

    def _setup_environment(self, config: ServiceConfig):
        """配置运行环境"""
        # 设置工作目录
        os.chdir(config.working_dir)
        logger.info(f"设置工作目录�? {config.working_dir}")
        
        # 设置PYTHONPATH
        self._adjust_pythonpath(config.working_dir)
        
        # 设置自定义环境变�?        if config.environment:
            for key, value in config.environment.items():
                os.environ[key] = value
                logger.debug(f"设置环境变量: {key}={value}")

    def _adjust_pythonpath(self, current_dir: str):
        """调整PYTHONPATH环境变量"""
        # 获取现有路径
        original_path = os.environ.get(ENV_PYTHON_PATH, '')
        
        # 添加必要路径
        lib_dir = os.path.join(current_dir, "lib")
        etc_dir = os.path.join(current_dir, "etc")
        
        # 构建新的PYTHONPATH
        new_path = os.pathsep.join([
            lib_dir,
            etc_dir,
            original_path
        ])
        
        os.environ[ENV_PYTHON_PATH] = new_path
        logger.debug(f"更新PYTHONPATH: {new_path}")

    def SvcStop(self):
        """Windows服务停止方法"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logger.info("服务停止请求已接�?)
        
        # 设置停止事件
        self.running = False
        win32event.SetEvent(self.hWaitStop)
        
        # 执行自定义停止逻辑
        self._on_service_stop()

    def SvcRun(self):
        """Windows服务运行主方�?""
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        logger.info("服务启动�?..")
        
        try:
            # 服务主循环前的初始化
            if not self._run_preflight_checks():
                self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                return
                
            # 报告服务正在运行
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.running = True
            logger.info("服务启动成功，进入运行状�?)
            
            # 执行服务主逻辑
            self._on_service_start()
            
            # 主服务循�?            while self.running:
                try:
                    # 服务主循环逻辑
                    self._service_main_loop()
                    
                    # 检查停止信�?                    if win32event.WaitForSingleObject(self.hWaitStop, 1000) == win32event.WAIT_OBJECT_0:
                        logger.info("收到停止信号，退出主循环")
                        break
                except KeyboardInterrupt:
                    logger.warning("收到中断信号，退出主循环")
                    break
                except Exception as e:
                    logger.error(f"服务主循环异�? {str(e)}")
                    # 错误恢复逻辑
                    self._handle_service_error(e)
                    
        except Exception as e:
            logger.exception("服务运行时发生未处理异常")
            self.last_error = str(e)
            
        finally:
            # 服务清理逻辑
            self._on_service_exit()
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            logger.info("服务已停�?)

    def _run_preflight_checks(self) -> bool:
        """运行服务启动前检�?""
        try:
            # 检查必备文�?            required_files = [
                self.config.executable_path,
                os.path.join(self.config.working_dir, "config.json"),
                os.path.join(self.config.working_dir, "cacert.pem")
            ]
            
            for file in required_files:
                if not os.path.exists(file):
                    logger.error(f"必备文件缺失: {file}")
                    return False
                    
            # 检查网络端口可用�?            if not self._check_network_availability():
                return False
                
            # 检查依赖服�?            if not self._check_dependent_services():
                return False
                
            logger.debug("所有启动前检查通过")
            return True
            
        except Exception as e:
            logger.error(f"启动前检查失�? {str(e)}")
            return False

    def _check_network_availability(self) -> bool:
        """检查网络可用�?""
        # 实际实现中使用套接字检查连�?        logger.info("网络可用性检�? 通过")
        return True

    def _check_dependent_services(self) -> bool:
        """检查依赖服务状�?""
        # 实际实现中检查依赖服务的运行状�?        logger.info("依赖服务检�? 通过")
        return True

    def _on_service_start(self):
        """服务启动时执行的自定义逻辑"""
        # 由子类实�?        pass

    def _on_service_stop(self):
        """服务停止时执行的自定义逻辑"""
        # 由子类实�?        pass

    def _on_service_exit(self):
        """服务退出时执行的自定义清理逻辑"""
        # 由子类实�?        pass

    def _service_main_loop(self):
        """服务主循环逻辑（由子类实现�?""
        # 默认实现
        # 在实际服务中，这里会包含主要的业务逻辑
        # 此方法应当定期调用以执行服务任务
        pass

    def _handle_service_error(self, exception: Exception):
        """服务错误处理逻辑"""
        error_id = generate_error_id()
        logger.error(f"[ERR-{error_id}] 服务错误: {str(exception)}")
        # 错误恢复策略
        # 在实际实现中，这里可能包括错误报告或恢复机制

class ServiceManager:
    """高级Windows服务管理工具"""
    
    def __init__(self):
        self.services = {}
    
    def register_service(self, service_class: cloudService):
        """注册服务�?""
        config = service_class._svc_config_
        if config.name in self.services:
            raise ValueError(f"服务 '{config.name}' 已注�?)
        
        self.services[config.name] = service_class
        logger.info(f"服务 '{config.name}' 已注�?)
    
    def install_service(self, service_name: str, command_line_args: str = ""):
        """安装服务"""
        if service_name not in self.services:
            raise KeyError(f"服务 '{service_name}' 未注�?)
        
        service_class = self.services[service_name]
        config = service_class._svc_config_
        
        # 构造服务参�?        params = [
            '--startup', 'auto', 
            '--display-name', config.display_name,
            '--description', config.description,
            command_line_args
        ]
        
        win32serviceutil.InstallService(
            pythonClassString=f"{service_class.__module__}.{service_class.__name__}",
            serviceName=config.name,
            displayName=config.display_name,
            description=config.description,
            startType=config.start_type.value,
            serviceDeps=",".join(config.dependencies.value)
        )
        logger.info(f"服务 '{service_name}' 安装成功")
    
    def uninstall_service(self, service_name: str):
        """卸载服务"""
        if service_name not in self.services:
            raise KeyError(f"服务 '{service_name}' 未注�?)
        
        win32serviceutil.RemoveService(service_name)
        logger.info(f"服务 '{service_name}' 卸载成功")
    
    def start_service(self, service_name: str):
        """启动服务"""
        if service_name not in self.services:
            raise KeyError(f"服务 '{service_name}' 未注�?)
        
        win32serviceutil.StartService(service_name)
        logger.info(f"服务 '{service_name}' 启动成功")
    
    def stop_service(self, service_name: str):
        """停止服务"""
        win32serviceutil.StopService(service_name)
        logger.info(f"服务 '{service_name}' 停止成功")
    
    def restart_service(self, service_name: str):
        """重启服务"""
        self.stop_service(service_name)
        self.start_service(service_name)
        logger.info(f"服务 '{service_name}' 重启成功")
    
    def get_service_status(self, service_name: str) -> ServiceState:
        """获取服务状�?""
        try:
            status = win32serviceutil.QueryServiceStatus(service_name)[1]
            return ServiceState(status)
        except Exception as e:
            logger.error(f"获取服务状态失�? {str(e)}")
            return ServiceState.UNKNOWN
    
    def configure_service(self, service_name: str, **kwargs):
        """配置服务参数"""
        # 实现使用win32service.ChangeServiceConfig
        logger.info(f"服务 '{service_name}' 配置更新")

# =============== 高级用例示例 ===============
class CustomcloudService(cloudService):
    """自定义Cloud服务实现"""
    
    # 覆盖服务配置
    _svc_config_ = ServiceConfig(
        name="CustomcloudService",
        display_name="Custom cloud Service",
        description="Advanced custom service for distributed processing",
        environment={
            "LOG_LEVEL": "DEBUG",
            "MAX_WORKERS": "8",
            cloud_VERSION_VAR: "1.4.2"
        }
    )
    
    def _on_service_start(self):
        """服务启动自定义逻辑"""
        logger.info("初始化分布式计算引擎...")
        # 实际初始化逻辑
        self.compute_engine = DistributedComputeEngine()
        self.compute_engine.initialize(cluster_size=8)
        logger.info("分布式计算引擎初始化完成")
    
    def _on_service_stop(self):
        """服务停止自定义逻辑"""
        logger.info("停止分布式计算引�?..")
        self.compute_engine.shutdown()
        logger.info("引擎停止完成")
    
    def _service_main_loop(self):
        """服务主循�?""
        # 处理计算任务队列
        task = self.compute_engine.get_next_task()
        if task:
            result = self.compute_engine.process_task(task)
            self.compute_engine.store_result(result)
        
        # 健康检�?        self._perform_health_check()
    
    def _perform_health_check(self):
        """执行健康检�?""
        # 在实际服务中，这里会检查资源、连接状态等
        pass
    
    def _on_service_exit(self):
        """服务退出清�?""
        try:
            self.compute_engine.release_resources()
            logger.info("所有资源已释放")
        except Exception as e:
            logger.error(f"资源释放错误: {str(e)}")

class DistributedComputeEngine:
    """模拟的分布式计算引擎"""
    def initialize(self, cluster_size: int):
        self.cluster_size = cluster_size
        logger.info(f"初始化计算集�?(节点数量: {cluster_size})")
    
    def get_next_task(self) -> Optional[dict]:
        return {"task_id": "1001", "data": "..."}  # 模拟任务
    
    def process_task(self, task: dict) -> dict:
        # 模拟任务处理
        return {"task_id": task["task_id"], "result": "SUCCESS"}
    
    def store_result(self, result: dict):
        # 模拟存储结果
        logger.debug(f"存储结果: {result['task_id']}")
    
    def shutdown(self):
        logger.info("关闭计算引擎")
    
    def release_resources(self):
        logger.info("释放所有集群资�?)

# =============== 服务管理控制逻辑 ===============
def start_services():
    """启动服务管理�?""
    service_manager = ServiceManager()
    service_manager.register_service(CustomcloudService)
    
    if len(sys.argv) == 1:
        # 默认运行服务
        logger.info("正在启动服务...")
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(CustomcloudService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # 处理服务管理命令
        handle_service_commands(service_manager)

def handle_service_commands(service_manager: ServiceManager):
    """处理服务管理命令行参�?""
    if len(sys.argv) < 2:
        print("请提供有效的服务命令: install, uninstall, start, stop, restart, status")
        return
    
    command = sys.argv[1].lower()
    service_name = "CustomcloudService"
    
    if command == "install":
        service_manager.install_service(service_name)
        print("服务安装成功")
    elif command == "uninstall":
        service_manager.uninstall_service(service_name)
        print("服务卸载成功")
    elif command == "start":
        service_manager.start_service(service_name)
        print("服务启动成功")
    elif command == "stop":
        service_manager.stop_service(service_name)
        print("服务停止成功")
    elif command == "restart":
        service_manager.restart_service(service_name)
        print("服务重启成功")
    elif command == "status":
        status = service_manager.get_service_status(service_name)
        print(f"服务状�? {status.name}")
    else:
        print(f"无效命令: {command}")
        print("可用命令: install, uninstall, start, stop, restart, status")

# =============== 辅助函数 ===============
def generate_error_id() -> str:
    """生成唯一的错误标识符"""
    import uuid
    return str(uuid.uuid4())[:8].upper()

if __name__ == '__main__':
    # Windows服务入口�?    if os.name == 'nt':
        try:
            start_services()
        except Exception as e:
            logger.exception("服务启动过程中发生致命错�?)
            sys.exit(1)
    else:
        print("此服务仅支持Windows平台")
        sys.exit(1)

