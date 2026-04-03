#!/usr/bin/env python3

__all__ = ["Script", "Dummy"]

import os
import re
import sys
import ssl
import json
import logging
import tempfile
import platform
import traceback
import contextlib
from distutils.version import LooseVersion
from functools import lru_cache
from optparse import OptionParser

# 核心库导�?from resource_management.core import sudo
from resource_management.core.environment import Environment
from resource_management.core.logger import Logger
from resource_management.core.resources import File, Directory
from resource_management.core.exceptions import (
    Fail, 
    ClientComponentHasNoStatus,
    ComponentIsNotRunning,
    ConfigurationError
)
from resource_management.core.source import InlineTemplate
from resource_management.libraries.resources import XmlConfig, PropertiesFile
from resource_management.libraries.script.config_dictionary import (
    ConfigDictionary, 
    UnknownConfiguration
)
from resource_management.libraries.functions import (
    stack_tools,
    version_select_util,
    conf_select,
    stack_select
)
from resource_management.libraries.functions.constants import (
    Direction, 
    StackFeature
)
from resource_management.libraries.functions.version import (
    format_stack_version,
    compare_versions
)
from resource_management.libraries.functions.repository_util import (
    CommandRepository,
    RepositoryUtil
)
from resource_management.libraries.execution_command.execution_command import ExecutionCommand

# 平台兼容模块
if sys.platform == 'win32':
    from resource_management.libraries.functions.win_utils import (
        reload_windows_env,
        install_windows_msi,
        archive_dir
    )
else:
    from resource_management.libraries.functions.unix_utils import (
        archive_dir,
        configure_system_proxy
    )

# 全局常量
USAGE = """{name} <COMMAND> <JSON_CONFIG> <BASEDIR> <STROUT_OUTPUT> <LOG_LEVEL> <TMP_DIR> [PROTOCOL] [CA_CERT]

命令说明:
  COMMAND        - 操作类型 (INSTALL/CONFIGURE/START/STOP/SERVICE_CHECK...)
  JSON_CONFIG    - 命令配置文件路径 (e.g. /var/lib/cloud-agent/data/command-2.json)
  BASEDIR        - 服务元数据目�?(e.g. /var/lib/cloud-agent/cache/common-services/HDFS/2.1.0.2/package)
  STROUT_OUTPUT  - 结构化输出文件路�?(执行时创�?
  LOG_LEVEL      - 日志级别 (DEBUG/INFO/WARN/ERROR)
  TMP_DIR        - 临时脚本目录 (e.g. /var/lib/cloud-agent/tmp)
  PROTOCOL       - HTTPS协议版本 (可�? 默认 TLS1.2)
  CA_CERT        - 可信证书路径 (可�?
"""
STACK_VERSION_PLACEHOLDER = "${stack_version}"
DEFAULT_HTTPS_PROTOCOL = "PROTOCOL_TLSv1_2"
TLS_PROTOCOL_MAP = {
    "PROTOCOL_TLSv1_2": ssl.PROTOCOL_TLSv1_2,
    "PROTOCOL_TLSv1_3": getattr(ssl, "PROTOCOL_TLSv1_3", ssl.PROTOCOL_TLSv1_2)
}

class cloudAgentException(Exception):
    """cloud Agent自定义异常基�?""
    pass

class Script:
    """分布式服务管理核心框�?""
    
    # 类单例实�?    _instance = None
    
    # 类级配置缓存
    config = None
    execution_command = None
    module_configs = None
    cluster_settings = None
    stack_settings = None
    
    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化框架实�?""
        if not hasattr(self, '_initialized'):
            self.tmp_dir = ""
            self.ca_cert_path = None
            self.https_protocol = DEFAULT_HTTPS_PROTOCOL
            self.log_level = "INFO"
            self._structured_out = {}
            self._initialized = True

    @classmethod
    def get_instance(cls):
        """获取框架单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def execute(self):
        """执行主工作流�?""
        try:
            # 参数解析与基础配置
            self._parse_arguments()
            
            # 日志系统初始�?            self._init_logger()
            
            # 环境安全配置
            self._configure_environment()
            
            # 命令执行分发
            self._dispatch_command()
            
        except cloudAgentException as e:
            Logger.error(f"框架执行异常: {str(e)}")
            sys.exit(1)
        except Exception as e:
            Logger.exception("未处理的系统异常")
            sys.exit(2)
        finally:
            # 确保资源清理
            self._cleanup_resources()

    def _parse_arguments(self):
        """解析命令行参�?""
        parser = OptionParser(usage=USAGE.format(name=os.path.basename(sys.argv[0])))
        parser.add_option("-o", "--log-out-files", dest="log_out_files", 
                         action="store_true", help="启用服务日志文件输出")
        options, args = parser.parse_args()

        # 验证参数数量
        if len(args) < 6:
            parser.print_help()
            raise cloudAgentException("参数不足")
        
        self.command_name = str.lower(args[1])
        self.command_data_file = args[2]
        self.basedir = args[3]
        self.stroutfile = args[4]
        self.log_level = args[5] if len(args) >= 6 else "INFO"
        self.tmp_dir = args[6] if len(args) >= 7 else tempfile.gettempdir()
        self.https_protocol = args[7] if len(args) >= 8 else DEFAULT_HTTPS_PROTOCOL
        self.ca_cert_path = args[8] if len(args) >= 9 else None
        self.options = options

    def _init_logger(self):
        """初始化日志系�?""
        Logger.initialize_logger(__name__, logging_level=self.log_level)
        Logger.info(f"cloud Agent启动 (命令: {self.command_name})")
        Logger.debug(f"参数详情: {sys.argv}")
        Logger.debug(f"临时目录: {self.tmp_dir}")
        Logger.debug(f"加密协议: {self.https_protocol}")
        Logger.debug(f"CA证书: {self.ca_cert_path or '系统默认'}")

    def _configure_environment(self):
        """配置运行时环�?""
        # Windows环境变量刷新
        if sys.platform == "win32":
            reload_windows_env()
        
        # 非Windows环境代理配置
        else:
            configure_system_proxy()
            
        # 强制安全协议
        self._enforce_https_protocol()

    def _enforce_https_protocol(self):
        """强制HTTPS协议版本"""
        protocol_value = TLS_PROTOCOL_MAP.get(
            self.https_protocol, 
            ssl.PROTOCOL_TLSv1_2
        )
        ssl._create_default_https_context = lambda: ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=self.ca_cert_path,
            protocol=protocol_value
        )
        Logger.info(f"安全协议强制使用: {self.https_protocol}")

    def _load_configuration(self):
        """加载服务配置数据"""
        try:
            with open(self.command_data_file, 'r') as config_file:
                config_data = json.load(config_file)
                Script.config = ConfigDictionary(config_data)
                Script.execution_command = ExecutionCommand(Script.config)
                Script.module_configs = self.execution_command.get_module_configs()
                Script.cluster_settings = self.execution_command.get_cluster_settings()
                Script.stack_settings = self.execution_command.get_stack_settings()
                
        except IOError:
            msg = f"配置文件读取失败: {self.command_data_file}"
            Logger.exception(msg)
            raise cloudAgentException(msg)
        except json.JSONDecodeError:
            msg = "配置文件JSON格式错误"
            Logger.exception(msg)
            raise cloudAgentException(msg)

    def _dispatch_command(self):
        """分发命令执行"""
        # 加载配置数据
        self._load_configuration()
        
        # 加载结构化输�?        self._load_structured_out()

        # 命令路由
        Logger.info(f"处理命令: {self.command_name.upper()}")
        try:
            method = self._resolve_command_method()
            with Environment(self.basedir, tmp_dir=self.tmp_dir) as env:
                # 前置钩子执行
                if not self._is_hook():
                    self._execute_prefix_function("pre", env)
                
                # 主命令执�?                method(env)
                
                # 后置钩子执行
                if not self._is_hook():
                    self._execute_prefix_function("post", env)
                
        except (ComponentIsNotRunning, ClientComponentHasNoStatus) as e:
            Logger.info(f"组件状态正常退�? {str(e)}")
        except Fail as e:
            Logger.error(f"命令执行失败: {str(e)}")
            traceback.print_exc()
            sys.exit(10)
        finally:
            # 保存组件版本信息
            if self._should_expose_version():
                self._save_component_version()

    def _resolve_command_method(self):
        """解析命令对应方法"""
        method_name = self.command_name
        if not hasattr(self, method_name):
            raise cloudAgentException(f"无效命令: {method_name}")
        return getattr(self, method_name)

    def _execute_prefix_function(self, affix, env):
        """执行附加操作(�?后缀)"""
        func_name = f"{affix}_{self.command_name}"
        if not hasattr(self, func_name):
            Logger.debug(f"附加操作未实�? {func_name}")
            return
        Logger.debug(f"执行附加操作: {func_name}")
        getattr(self, func_name)(env)

    def _is_hook(self):
        """检查当前是否为钩子脚本"""
        from resource_management.libraries.script.hook import Hook
        return Hook in self.__class__.__bases__

    def _load_structured_out(self):
        """加载结构化输出数�?""
        Script.structuredOut = {}
        if os.path.exists(self.stroutfile) and os.path.getsize(self.stroutfile) > 0:
            try:
                with open(self.stroutfile, 'r') as f:
                    Script.structuredOut = json.load(f)
            except Exception:
                Logger.warning("结构化输出加载失败，忽略历史数据")
        
        # 清理安全相关信息
        for key in ["version", "securityIssuesFound", "securityStateErrorInfo"]:
            if key in Script.structuredOut:
                del Script.structuredOut[key]

    def put_structured_out(self, data):
        """更新结构化输�?""
        Script.structuredOut.update(data)
        try:
            with open(self.stroutfile, 'w') as f:
                json.dump(Script.structuredOut, f, indent=2)
        except IOError:
            Logger.error(f"结构化输出写入失�? {self.stroutfile}")
            Script.structuredOut.update({"error": "文件写入失败"})

    # ------------ 核心功能方法 ------------
    def install(self, env):
        """服务安装接口"""
        self._install_packages(env)

    def configure(self, env):
        """服务配置接口"""
        self._fail_with_error("配置功能未实�?)

    def start(self, env):
        """服务启动接口"""
        self._fail_with_error("启动功能未实�?)

    def stop(self, env):
        """服务停止接口"""
        self._fail_with_error("停止功能未实�?)

    def restart(self, env):
        """服务重启接口"""
        Logger.info("执行复合操作: 停止->启动")
        self.stop(env)
        self.start(env)

    def status(self, env):
        """服务状态检�?""
        # 默认实现检查PID文件
        if not os.path.exists(self._get_pid_file()):
            raise ComponentIsNotRunning()

    # ------------ 工具方法 ------------
    @lru_cache(maxsize=128)
    def get_stack_version(self):
        """获取标准化的堆栈版本"""
        if "clusterLevelParams" not in Script.config or "stack_version" not in Script.config["clusterLevelParams"]:
            return None
        
        raw_version = Script.config["clusterLevelParams"]["stack_version"]
        return format_stack_version(raw_version)

    def format_package_name(self, name):
        """格式化包�?替换版本占位�?"""
        if STACK_VERSION_PLACEHOLDER not in name:
            return name
            
        version_str = self.get_stack_version_before_install().replace(
            '.', '_').replace('-', '_')
        return name.replace(STACK_VERSION_PLAEHLODER, version_str)

    def get_config(self, path, default=None):
        """安全获取配置�?""
        keys = [_f for _f in path.split("/") if _f]
        conf = Script.config
        for key in keys:
            if key in conf:
                conf = conf[key]
            else:
                return default
        return conf

    def _fail_with_error(self, message):
        """优雅失败处理"""
        Logger.error(message)
        sys.stderr.write(f"Error: {message}\n")
        sys.exit(1)

    # ------------ 生命周期钩子 ------------
    def pre_start(self, env):
        """启动前钩�?- 日志文件展示"""
        if not self.options.log_out_files:
            return
            
        log_dir = self.get_log_folder()
        if not log_dir:
            Logger.warning("未配置日志目�?)
            return
            
        show_logs(log_dir, self.get_user(), 
                 mask="*.out", 
                 max_lines=100)

    def post_start(self, env):
        """启动后钩�?- 进程验证"""
        pid_files = self.get_pid_files()
        if not pid_files:
            Logger.warning("未配置PID文件")
            return
            
        active_pids = []
        for pid_file in pid_files:
            if os.path.exists(pid_file):
                pid_val = sudo.read_file(pid_file).strip()
                active_pids.append(pid_val)
                
        if active_pids:
            Logger.info(f"服务已启�?- PIDs: {', '.join(active_pids)}")
        else:
            Logger.warning("未检测到活动进程")

    def post_stop(self, env):
        """停止后钩�?- 状态验�?""
        for _ in range(30):  # 最多等�?�?            try:
                self.status(env)
                time.sleep(0.1)
            except (ComponentIsNotRunning, ClientComponentHasNoStatus):
                Logger.info("服务已完全停�?)
                return
                
        Logger.warning("服务停止状态未确认")

def get_config_lock_file():
    """获取配置锁文件路�?""
    return os.path.join(Script.get_tmp_dir(), "cloud_config.lock")

class Dummy(Script):
    """虚拟服务组件 - 用于性能测试和功能原�?""
    
    def __init__(self):
        super().__init__()
        self.component_name = "dummy"
        self.pid_file = "/var/run/dummy.pid"
        self.user = "nobody"
        self.user_group = "nogroup"
        
    def install(self, env):
        """虚拟安装流程"""
        Logger.info("执行虚拟安装流程")
        # 模拟真实安装耗时
        time.sleep(1.5)
        Logger.success("虚拟组件安装完成")

    def start(self, env):
        """启动虚拟服务"""
        Logger.info("启动虚拟服务组件")
        # 模拟服务启动
        with open(self.pid_file, "w") as pid_fd:
            pid_fd.write(str(os.getpid()))
        Logger.success("服务启动成功 (虚拟)")

    def stop(self, env):
        """停止虚拟服务"""
        Logger.info("停止虚拟服务组件")
        # 清除服务标记
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
            Logger.success("服务已停�?)
        else:
            Logger.warning("PID文件不存�?)
            
    def status(self, env):
        """检查服务状�?""
        if not os.path.exists(self.pid_file):
            raise ComponentIsNotRunning()
        Logger.info("服务运行�?(虚拟)")

if __name__ == "__main__":
    # 启动框架主入�?    script_instance = Script.get_instance()
    try:
        script_instance.execute()
    except KeyboardInterrupt:
        Logger.warning("进程被用户中�?)
        sys.exit(130)
    except Exception as e:
        Logger.critical(f"未处理的系统异常: {traceback.format_exc()}")
        sys.exit(255)
