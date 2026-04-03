#!/usr/bin/env python3

import os
from typing import Optional, Union, Callable, List, Tuple
from functools import lru_cache

from resource_management.core import shell
from resource_management.core.base import Fail
from resource_management.core.providers import Provider
from resource_management.core.logger import Logger


class ServiceProvider(Provider):
    """
    通用服务管理Provider
    
    支持三种服务管理方式（按优先级排序）：
    1. systemd - 现代Linux系统标准（systemctl命令）
    2. Upstart - Ubuntu等系统的传统方式（/sbin/start等命令）
    3. SysV init - 通用传统方式（/etc/init.d/脚本）
    
    使用示例：
        service = ServiceProvider()
        service.resource.service_name = "hdfs-namenode"
        service.action_start()  # 启动服务
    """
    
    # 服务管理类型枚举
    SERVICE_TYPE_SYSTEMD = "systemd"
    SERVICE_TYPE_UPSTART = "upstart"
    SERVICE_TYPE_SYSV = "sysv"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 缓存服务类型检测结果
        self._service_type: Optional[str] = None
        # 缓存systemd服务可用性
        self._systemd_service_available: Optional[bool] = None
    
    def action_start(self) -> None:
        """
        启动服务操作
        
        执行逻辑：
        1. 检查当前服务状态
        2. 如未运行则执行启动命令
        3. 验证启动结果
        """
        if self._is_running():
            Logger.info(f"服务 {self.resource.service_name} 已在运行，跳过启动")
            return
        
        Logger.info(f"正在启动服务: {self.resource.service_name}")
        self._execute_service_command("start", expect_code=0)
        Logger.info(f"服务启动成功: {self.resource.service_name}")
    
    def action_stop(self) -> None:
        """
        停止服务操作
        
        执行逻辑：
        1. 检查当前服务状态
        2. 如正在运行则执行停止命令
        3. 验证停止结果
        """
        if not self._is_running():
            Logger.info(f"服务 {self.resource.service_name} 未运行，跳过停止")
            return
        
        Logger.info(f"正在停止服务: {self.resource.service_name}")
        self._execute_service_command("stop", expect_code=0)
        Logger.info(f"服务停止成功: {self.resource.service_name}")
    
    def action_restart(self) -> None:
        """
        重启服务操作
        
        执行逻辑：
        1. 优先使用原生restart命令（如果支持）
        2. 否则执行stop+start组合
        3. 验证重启结果
        """
        Logger.info(f"正在重启服务: {self.resource.service_name}")
        
        # 尝试使用restart命令（systemd支持）
        if self._service_type == self.SERVICE_TYPE_SYSTEMD:
            try:
                self._execute_service_command("restart", expect_code=0)
                Logger.info(f"服务重启成功: {self.resource.service_name}")
                return
            except Fail:
                Logger.warning("restart命令失败，尝试stop+start方式")
        
        # 回退到stop+start方式
        self.action_stop()
        self.action_start()
        Logger.info(f"服务重启完成: {self.resource.service_name}")
    
    def action_reload(self) -> None:
        """
        重载服务配置操作
        
        执行逻辑：
        1. 检查服务是否运行（不可重载未启动的服务）
        2. 执行reload命令
        3. 验证重载结果
        """
        if not self._is_running():
            raise Fail(
                f"无法重载配置，服务 {self.resource.service_name} 未运行"
            )
        
        Logger.info(f"正在重载服务配置: {self.resource.service_name}")
        self._execute_service_command("reload", expect_code=0)
        Logger.info(f"配置重载成功: {self.resource.service_name}")
    
    def action_status(self) -> bool:
        """
        查询服务状态
        
        返回: True=运行中, False=未运行
        
        实现说明：
        - 调用status_command或系统状态查询
        - 根据返回码判断状态（0=运行）
        """
        return self._is_running()
    
    # -------------------------------------------------------------------------
    # 内部实现方法
    # -------------------------------------------------------------------------
    
    def _is_running(self) -> bool:
        """
        检查服务是否正在运行
        
        实现逻辑：
        1. 优先使用自定义status_command
        2. 否则使用系统服务状态查询
        3. 返回码0表示运行中
        """
        try:
            return self._execute_service_command("status") == 0
        except Fail:
            return False
    
    def _execute_service_command(
        self, 
        command: str, 
        expect_code: Optional[int] = None
    ) -> int:
        """
        执行服务命令核心方法
        
        参数:
            command: 命令类型（start/stop/restart/reload/status）
            expect_code: 期望的返回码（None表示不验证）
        
        返回: 实际返回码
        
        异常:
            Fail: 当expect_code指定且实际返回码不匹配时
        """
        # 调试日志
        if command != "status":
            Logger.info(f"执行服务命令: {self.resource.service_name} -> {command}")
        
        # 尝试执行自定义命令
        custom_cmd = self._get_custom_command(command)
        if custom_cmd:
            return self._execute_custom_command(custom_cmd, command, expect_code)
        
        # 执行系统服务命令
        return self._execute_system_command(command, expect_code)
    
    def _get_custom_command(self, command: str) -> Optional[Union[str, Callable]]:
        """
        获取自定义命令
        
        支持两种形式：
        1. 字符串：直接执行shell命令
        2. 可调用对象：执行函数并返回布尔值
        """
        attr_name = f"{command}_command"
        return getattr(self.resource, attr_name, None)
    
    def _execute_custom_command(
        self, 
        custom_cmd: Union[str, Callable], 
        command_name: str,
        expect_code: Optional[int]
    ) -> int:
        """
        执行自定义命令
        
        实现逻辑：
        1. 如果是可调用对象，执行并返回布尔值转换的返回码
        2. 如果是字符串，通过shell执行
        3. 验证返回码是否符合预期
        """
        Logger.debug(f"使用自定义命令执行 {self.resource.service_name}.{command_name}")
        
        # 处理可调用对象
        if callable(custom_cmd):
            try:
                success = custom_cmd()
                return 0 if success else 1
            except Exception as e:
                Logger.exception(f"自定义命令执行失败: {str(e)}")
                raise Fail(f"自定义命令 {command_name} 执行异常: {str(e)}")
        
        # 处理字符串命令
        try:
            ret_code, output = shell.call(
                custom_cmd,
                logoutput=False,  # 避免重复日志
                timeout=300,  # 服务命令默认5分钟超时
            )
            
            return self._validate_return_code(
                ret_code, command_name, output, expect_code
            )
        except Exception as e:
            Logger.error(f"命令执行异常: {custom_cmd}")
            raise Fail(f"执行失败: {str(e)}")
    
    def _execute_system_command(
        self, 
        command: str, 
        expect_code: Optional[int]
    ) -> int:
        """
        执行系统服务管理命令
        
        实现逻辑：
        根据检测到的服务类型，调用对应的系统命令
        """
        service_type = self._detect_service_type()
        service_name = self.resource.service_name
        
        try:
            if service_type == self.SERVICE_TYPE_SYSTEMD:
                return self._execute_systemd_command(command, service_name, expect_code)
            elif service_type == self.SERVICE_TYPE_UPSTART:
                return self._execute_upstart_command(command, service_name, expect_code)
            else:
                return self._execute_sysv_command(command, service_name, expect_code)
        except Exception as e:
            Logger.error(
                f"系统命令执行失败 [{service_type}]: {service_name}.{command}"
            )
            raise Fail(f"服务命令执行失败: {str(e)}")
    
    def _execute_systemd_command(
        self, 
        command: str, 
        service_name: str,
        expect_code: Optional[int]
    ) -> int:
        """
        执行systemd服务命令
        
        systemd特性：
        - status返回码：0=运行，3=未运行，其他=错误
        - 支持原生restart操作
        """
        full_command = ["systemctl", command, f"{service_name}.service"]
        
        # status命令特殊处理（systemctl返回码定义不同）
        if command == "status":
            ret_code, output = shell.call(full_command, logoutput=False)
            # systemd: 0=active, 3=inactive, 其他=错误
            if ret_code == 0:
                return 0  # 运行中
            elif ret_code == 3:
                return 1  # 未运行
            else:
                # 未知错误状态
                Logger.warning(f"systemd状态异常: {output}")
                return ret_code
        
        # 其他命令（start/stop/restart/reload）
        ret_code, output = shell.call(full_command, timeout=300)
        return self._validate_return_code(
            ret_code, f"systemd {command}", output, expect_code
        )
    
    def _execute_upstart_command(
        self, 
        command: str, 
        service_name: str,
        expect_code: Optional[int]
    ) -> int:
        """
        执行Upstart服务命令
        
        Upstart特性：
        - 使用/sbin/start, /sbin/stop等独立命令
        - status返回文本信息需要解析
        """
        if command == "status":
            # Upstart status特殊处理
            ret_code, output = shell.call(
                ["/sbin/status", service_name],
                logoutput=False
            )
            # 解析状态文本（如 "hadoop-hdfs-namenode start/running, process 1234"）
            output_lower = output.lower()
            if "start/running" in output_lower or "running" in output_lower:
                return 0
            elif "stop/waiting" in output_lower or "stopping" in output_lower:
                return 1
            else:
                # 未知状态
                Logger.warning(f"Upstart状态解析失败: {output}")
                return ret_code if ret_code != 0 else 1
        
        # 其他命令
        full_command = [f"/sbin/{command}", service_name]
        ret_code, output = shell.call(full_command, timeout=300)
        return self._validate_return_code(
            ret_code, f"upstart {command}", output, expect_code
        )
    
    def _execute_sysv_command(
        self, 
        command: str, 
        service_name: str,
        expect_code: Optional[int]
    ) -> int:
        """
        执行SysV init服务命令
        
        传统方式：
        - 直接调用/etc/init.d/脚本
        - status返回码标准：0=运行，其他=未运行/错误
        """
        script_path = f"/etc/init.d/{service_name}"
        
        if not os.path.exists(script_path):
            raise Fail(f"服务脚本不存在: {script_path}")
        
        if not os.access(script_path, os.X_OK):
            raise Fail(f"服务脚本不可执行: {script_path}")
        
        full_command = [script_path, command]
        ret_code, output = shell.call(full_command, timeout=300)
        
        return self._validate_return_code(
            ret_code, f"sysv {command}", output, expect_code
        )
    
    def _validate_return_code(
        self, 
        ret_code: int, 
        command_desc: str, 
        output: str,
        expect_code: Optional[int]
    ) -> int:
        """
        验证返回码是否符合预期
        
        参数:
            ret_code: 实际返回码
            command_desc: 命令描述（用于错误信息）
            output: 命令输出
            expect_code: 期望返回码（None表示不验证）
        
        返回: 实际返回码
        
        异常:
            Fail: 当期望码与实际不符时
        """
        if expect_code is not None and ret_code != expect_code:
            raise Fail(
                f"服务命令执行结果不符合预期\n"
                f"服务: {self.resource.service_name}\n"
                f"命令: {command_desc}\n"
                f"期望返回码: {expect_code}\n"
                f"实际返回码: {ret_code}\n"
                f"命令输出: {output[:500]}"
            )
        return ret_code
    
    @lru_cache(maxsize=32)
    def _detect_service_type(self) -> str:
        """
        自动检测服务管理类型
        
        检测优先级（从高到低）：
        1. systemd - 检查systemctl命令和服务单元文件
        2. Upstart - 检查/sbin/start命令和/etc/init/配置文件
        3. SysV init - 检查/etc/init.d/脚本
        
        结果缓存以避免重复检测（使用functools.lru_cache）
        
        返回: SERVICE_TYPE_SYSTEMD|SERVICE_TYPE_UPSTART|SERVICE_TYPE_SYSV
        """
        service_name = self.resource.service_name
        
        # 检测systemd
        if self._is_systemd_available():
            service_unit = f"{service_name}.service"
            if self._systemd_service_exists(service_unit):
                Logger.debug(f"服务 {service_name} 使用systemd管理")
                return self.SERVICE_TYPE_SYSTEMD
        
        # 检测Upstart
        if os.path.exists("/sbin/start"):
            init_conf = f"/etc/init/{service_name}.conf"
            if os.path.exists(init_conf):
                Logger.debug(f"服务 {service_name} 使用Upstart管理")
                return self.SERVICE_TYPE_UPSTART
        
        # 检测SysV init
        init_script = f"/etc/init.d/{service_name}"
        if os.path.exists(init_script):
            Logger.debug(f"服务 {service_name} 使用SysV init管理")
            return self.SERVICE_TYPE_SYSV
        
        # 未找到任何服务定义
        raise Fail(
            f"无法检测服务 {service_name} 的管理类型\n"
            f"请确保服务已正确安装，或提供自定义命令"
        )
    
    def _is_systemd_available(self) -> bool:
        """
        检查systemd是否可用
        
        检查条件：
        1. systemctl命令存在
        2. 当前系统是systemd启动的（/run/systemd/system存在）
        """
        if self._systemd_available is not None:
            return self._systemd_available
        
        has_systemctl = os.path.exists("/bin/systemctl") or os.path.exists("/usr/bin/systemctl")
        is_systemd_boot = os.path.exists("/run/systemd/system")
        
        self._systemd_available = has_systemctl and is_systemd_boot
        return self._systemd_available
    
    def _systemd_service_exists(self, service_unit: str) -> bool:
        """
        检查systemd服务单元是否存在
        
        检查路径：
        - /usr/lib/systemd/system/
        - /etc/systemd/system/
        - /lib/systemd/system/
        """
        search_paths = [
            "/usr/lib/systemd/system",
            "/etc/systemd/system",
            "/lib/systemd/system"
        ]
        
        for path in search_paths:
            unit_path = os.path.join(path, service_unit)
            if os.path.exists(unit_path):
                return True
        
        # 尝试查询systemd（处理别名服务）
        try:
            ret_code, _ = shell.call(
                ["systemctl", "list-unit-files", service_unit],
                logoutput=False,
                timeout=5
            )
            return ret_code == 0
        except:
            return False


class ServiceConfigProvider(Provider):
    """
    服务配置Provider（占位类）
    
    说明：
    该类预留用于服务配置的加载和应用，
    具体实现由子类完成。
    """
    pass
