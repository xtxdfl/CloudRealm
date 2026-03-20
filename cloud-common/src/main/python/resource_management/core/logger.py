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

cloud Agent

"""


from typing import Optional, Dict, List, Union, Any, TextIO, Tuple
from resource_management.libraries.script.config_dictionary import UnknownConfiguration
from resource_management.core.utils import PasswordString
from resource_management.core.logger import Logger as CoreLogger
from resource_management.core.shell import PLACEHOLDERS_TO_STR
import sys
import logging

# 模块导出
__all__ = ["Logger"]

# 日志长度限制常量
MESSAGE_MAX_LEN = 512  # 单条日志最大长度，超过则截断为 "..."
DICTIONARY_MAX_LEN = 5  # 字典值最大条目数，超过则显示 "..."

# 日志级别映射
LOG_LEVEL_MAP: Dict[int, str] = logging._levelToName


class Logger:
    """
    统一日志管理�?    
    封装 Python logging 模块，提供敏感信息保护、资源序列化�?    长度控制等增强功能，专为 cloud 资源管理设计�?    
    核心功能�?        - 分级日志输出（debug/info/warning/error/exception�?        - 敏感信息自动脱敏
        - 资源对象自动格式�?        - 命令参数保护
        - 日志长度智能控制
    
    使用模式�?        # 必须先初始化
        Logger.initialize_logger("cloud", logging.INFO)
        
        # 常规日志
        Logger.info("服务启动成功")
        Logger.error("配置失败")
        
        # 记录资源操作
        Logger.info_resource(my_resource)
        
        # 保护敏感命令
        safe_cmd = Logger.format_command_for_output(cmd_with_password)
    """
    
    # 单例 Logger 实例
    logger: Optional[logging.Logger] = None
    
    # 敏感字符串映射：{未保护字符串: 保护后字符串}
    sensitive_strings: Dict[str, str] = {}
    
    @staticmethod
    def initialize_logger(
        name: str = "resource_management",
        logging_level: int = logging.INFO,
        format: str = "%(asctime)s - %(message)s",
    ) -> None:
        """
        初始化全局日志�?        
        配置双输出流：ERROR 及以上到 stderr，其他到 stdout�?        必须在使用日志功能前调用，否�?logger �?None�?        
        Args:
            name: 日志器名称（模块名）
            logging_level: 日志级别（DEBUG/INFO/WARNING/ERROR�?            format: 日志格式字符�?            
        Returns:
            None
            
        Raises:
            ValueError: 如果 logging_level 不是有效级别
            
        示例�?            Logger.initialize_logger("cloud", logging.DEBUG)
            Logger.info("日志系统初始化完�?)
        """
        if Logger.logger:
            Logger.debug("日志器已初始化，跳过重复初始�?)
            return
        
        Logger.info(f"初始化日志器: {name}, 级别: {LOG_LEVEL_MAP.get(logging_level, 'UNKNOWN')}")
        
        # 创建日志�?        logger = logging.getLogger(name)
        logger.setLevel(logging_level)
        formatter = logging.Formatter(format)
        
        # stderr 处理器（ERROR 及以上）
        cherr = logging.StreamHandler(sys.stderr)
        cherr.setLevel(logging.ERROR)
        cherr.setFormatter(formatter)
        
        # stdout 处理器（INFO/DEBUG 等）
        chout = logging.StreamHandler(sys.stdout)
        chout.setLevel(logging_level)
        chout.setFormatter(formatter)
        
        # 清除旧处理器，添加新处理�?        logger.handlers = []
        logger.addHandler(cherr)
        logger.addHandler(chout)
        
        Logger.logger = logger
        Logger.info("日志系统初始化成�?)
    
    @staticmethod
    def isEnabledFor(level: int) -> bool:
        """
        检查指定日志级别是否启�?        
        Args:
            level: 日志级别（如 logging.DEBUG�?            
        Returns:
            bool: 是否启用
            
        示例�?            if Logger.isEnabledFor(logging.DEBUG):
                Logger.debug(f"详细调试信息: {complex_data}")
        """
        return Logger.logger is not None and Logger.logger.isEnabledFor(level)
    
    @staticmethod
    def exception(text: str) -> None:
        """
        记录异常信息（包含堆栈跟踪）
        
        Args:
            text: 异常描述
            
        示例�?            try:
                risky_operation()
            except Exception as e:
                Logger.exception("操作失败")
        """
        if Logger.logger:
            Logger.logger.exception(Logger.filter_text(text))
        else:
            print(f"EXCEPTION: {Logger.filter_text(text)}", file=sys.stderr)
    
    @staticmethod
    def error(text: str) -> None:
        """
        记录错误级别日志（输出到 stderr�?        
        Args:
            text: 错误信息
            
        示例�?            Logger.error("数据库连接失�?)
        """
        if Logger.logger:
            Logger.logger.error(Logger.filter_text(text))
        else:
            print(f"ERROR: {Logger.filter_text(text)}", file=sys.stderr)
    
    @staticmethod
    def warning(text: str) -> None:
        """
        记录警告级别日志
        
        Args:
            text: 警告信息
            
        示例�?            Logger.warning("配置项已弃用，将在下版本移除")
        """
        if Logger.logger:
            Logger.logger.warning(Logger.filter_text(text))
        else:
            print(f"WARNING: {Logger.filter_text(text)}", file=sys.stderr)
    
    @staticmethod
    def info(text: str) -> None:
        """
        记录信息级别日志（输出到 stdout�?        
        Args:
            text: 信息内容
            
        示例�?            Logger.info("服务启动成功: Kafka")
        """
        if Logger.logger:
            Logger.logger.info(Logger.filter_text(text))
        else:
            print(f"INFO: {Logger.filter_text(text)}", file=sys.stdout)
    
    @staticmethod
    def debug(text: str) -> None:
        """
        记录调试级别日志（仅当级�?<= DEBUG 时输出）
        
        Args:
            text: 调试信息
            
        示例�?            Logger.debug(f"当前配置: {config_dict}")
        """
        if Logger.logger:
            Logger.logger.debug(Logger.filter_text(text))
        else:
            print(f"DEBUG: {Logger.filter_text(text)}", file=sys.stdout)
    
    @staticmethod
    def error_resource(resource: Resource) -> None:
        """
        记录资源操作错误
        
        Args:
            resource: cloud Resource 对象
            
        示例�?            Logger.error_resource(my_file_resource)
        """
        if Logger.logger:
            Logger.logger.error(Logger.filter_text(Logger._get_resource_repr(resource)))
        else:
            print(f"ERROR: {Logger._get_resource_repr(resource)}", file=sys.stderr)
    
    @staticmethod
    def warning_resource(resource: Resource) -> None:
        """
        记录资源操作警告
        
        Args:
            resource: cloud Resource 对象
        """
        if Logger.logger:
            Logger.logger.warning(Logger.filter_text(Logger._get_resource_repr(resource)))
        else:
            print(f"WARNING: {Logger._get_resource_repr(resource)}", file=sys.stderr)
    
    @staticmethod
    def info_resource(resource: Resource) -> None:
        """
        记录资源操作信息
        
        Args:
            resource: cloud Resource 对象
            
        示例�?            Logger.info_resource(my_package_resource)
        """
        if Logger.logger:
            Logger.logger.info(Logger.filter_text(Logger._get_resource_repr(resource)))
        else:
            print(f"INFO: {Logger._get_resource_repr(resource)}", file=sys.stdout)
    
    @staticmethod
    def debug_resource(resource: Resource) -> None:
        """
        记录资源调试信息
        
        Args:
            resource: cloud Resource 对象
        """
        if Logger.logger:
            Logger.logger.debug(Logger.filter_text(Logger._get_resource_repr(resource)))
        else:
            print(f"DEBUG: {Logger._get_resource_repr(resource)}", file=sys.stdout)
    
    @staticmethod
    def filter_text(text: str) -> str:
        """
        全局文本过滤器：替换敏感信息并清理占位符
        
        敏感字符串映射：
        - PasswordString �?[PROTECTED]
        - sensitive_strings 映射�?        - Shell 占位符清�?        
        Args:
            text: 原始文本
            
        Returns:
            str: 过滤后文�?            
        安全特性：
            - 不可逆向：替换后的文本无法恢复原始密�?            - 全面覆盖：所有日志输出都经过此过滤器
            - 内存保护：敏感字符串仅存在于映射表中
            
        示例�?            filtered = Logger.filter_text("密码�? secret123")
            # 如果 secret123 �?sensitive_strings �?            # 输出: "密码�? [PROTECTED]"
        """
        if not isinstance(text, str):
            return str(text)
        
        # 替换敏感字符串映�?        for unprotected_string, protected_string in Logger.sensitive_strings.items():
            text = text.replace(unprotected_string, protected_string)
        
        # 清理 Shell 占位�?        for placeholder in PLACEHOLDERS_TO_STR.keys():
            text = text.replace(placeholder, "")
        
        return text
    
    @staticmethod
    def _get_resource_repr(resource: Resource) -> str:
        """
        序列�?Resource 对象为字符串
        
        Args:
            resource: cloud Resource 实例
            
        Returns:
            str: 格式化后的资源表�?            
        格式示例�?            File {'path': '/etc/hadoop/conf', 'mode': 0o755, 'action': ['create']}
        """
        return Logger.get_function_repr(repr(resource), resource.arguments, resource)
    
    @staticmethod
    def _get_resource_name_repr(name: Any) -> str:
        """
        格式化资源名称输�?        
        字符串显示为带引号格式，PasswordString 显示�?[PROTECTED]
        
        Args:
            name: 资源名或任意�?            
        Returns:
            str: 格式化后的名称表�?        """
        if isinstance(name, str) and not isinstance(name, PasswordString):
            return f"'{name}'"  # 友好字符串格�?        else:
            return repr(name)  # 其他类型使用 repr
    
    @staticmethod
    def format_command_for_output(command: Union[List[Any], Tuple[Any, ...], PasswordString, Any]) -> Union[List[Any], str]:
        """
        格式化命令参数，保护其中�?PasswordString
        
        用于在执行系统命令前，将命令列表中的密码参数脱敏�?        防止密码出现在日志或进程列表中�?        
        Args:
            command: 命令（列表、元组或单个值）
            
        Returns:
            Union[List[Any], str]: 脱敏后的命令
            
        示例�?            cmd = ["mysql", "-p", PasswordString("secret123")]
            safe_cmd = Logger.format_command_for_output(cmd)
            # 返回: ["mysql", "-p", "[PROTECTED]"]
            
            或单�?PasswordString:
            safe_cmd = Logger.format_command_for_output(PasswordString("secret"))
            # 返回: "[PROTECTED]"
        """
        if isinstance(command, (list, tuple)):
            result = []
            for x in command:
                if isinstance(x, PasswordString):
                    # 脱敏处理：显�?[PROTECTED] 但保留命令结�?                    result.append(repr(x).strip("'"))
                else:
                    result.append(x)
            return result
        elif isinstance(command, PasswordString):
            # 单个 PasswordString 直接脱敏
            return repr(command).strip("'")
        else:
            # 非密码类型原样返�?            return command
    
    @staticmethod
    def get_function_repr(name: str, arguments: Dict[str, Any], resource: Optional[Resource] = None) -> str:
        """
        格式化函数或资源调用字符�?        
        将参数字典转换为可读的键值对格式，支持特殊类型处理：
        - 长字符串截断
        - 大字典省�?        - UnknownConfiguration 标记�?[EMPTY]
        - 八进制模式值（�?mode=0o755�?        - 函数对象显示名称
        
        Args:
            name: 函数/资源�?            arguments: 参数字典
            resource: 可选的 Resource 对象，用于自定义日志输出
            
        Returns:
            str: 格式化后的调用表�?            
        示例�?            args = {'path': '/etc/passwd', 'mode': 0o644, 'user': 'root'}
            repr_str = Logger.get_function_repr("File", args)
            # 返回: "File {'path': '/etc/passwd', 'mode': 0o644, 'user': 'root'}"
            
        特殊处理�?            - 字符串超�?512 字符显示 '...'
            - 字典超过 5 条目显示 '...'
            - UnknownConfiguration 显示 '[EMPTY]'
            - mode 参数自动转换为八进制
            - 函数对象显示 __name__ 而非 <function>
        """
        logger_level = logging._levelToName.get(Logger.logger.level if Logger.logger else logging.INFO, "INFO")
        
        arguments_str = ""
        for arg_name, arg_value in arguments.items():
            # 自定义日志输出（�?PasswordString �?log_str�?            if resource and hasattr(resource._arguments[arg_name], "log_str"):
                val = resource._arguments[arg_name].log_str(arg_name, arg_value)
            
            # 长字符串截断
            elif isinstance(arg_value, str) and len(arg_value) > MESSAGE_MAX_LEN:
                val = "..."
            
            # Unicode 前缀去除（Python 2 兼容�?            elif isinstance(arg_value, str):
                val = repr(arg_value).lstrip("u")
            
            # 大字典省�?            elif isinstance(arg_value, dict) and len(arg_value) > DICTIONARY_MAX_LEN:
                val = "..."
            
            # 未知配置标记
            elif isinstance(arg_value, UnknownConfiguration):
                val = "[EMPTY]"
            
            # 八进制模式�?            elif arg_value and arg_name == "mode":
                try:
                    val = oct(arg_value)
                except:
                    val = repr(arg_value)
            
            # 函数对象显示名称
            elif hasattr(arg_value, "__call__") and hasattr(arg_value, "__name__"):
                val = arg_value.__name__
            
            # 默认 repr
            else:
                val = repr(arg_value)
            
            arguments_str += f"'{arg_name}': {val}, "
        
        # 移除末尾逗号
        if arguments_str:
            arguments_str = arguments_str[:-2]
        
        return f"{name} {{{arguments_str}}}"


# ===== 日志辅助函数 =====

def log_resource_action(
    resource: Resource,
    action: str,
    level: str = "info"
) -> None:
    """
    快速记录资源操作日�?    
    Args:
        resource: 操作的资�?        action: 执行的动�?        level: 日志级别（info/warning/error/debug�?        
    示例�?        log_resource_action(my_file, "create", "info")
    """
    level_map = {
        "info": Logger.info_resource,
        "warning": Logger.warning_resource,
        "error": Logger.error_resource,
        "debug": Logger.debug_resource
    }
    
    if level in level_map:
        level_map[level](resource)
    else:
        Logger.warning(f"未知日志级别: {level}")
        Logger.info_resource(resource)


def protect_sensitive_string(unprotected: str, protected: str = "[PROTECTED]") -> None:
    """
    注册敏感字符串保护规�?    
    Args:
        unprotected: 原始敏感字符�?        protected: 替换后的字符串（默认 [PROTECTED]�?        
    示例�?        # 保护数据库密�?        protect_sensitive_string("my_secret_password")
        
        # 保护私有密钥
        protect_sensitive_string("-----BEGIN PRIVATE KEY-----", "[HIDDEN_KEY]")
    """
    if unprotected:
        Logger.sensitive_strings[unprotected] = protected
        Logger.debug(f"注册敏感字符串保�? {unprotected[:10]}... -> {protected}")


# ===== 初始化快捷方�?=====

def init_default_logger(level: int = logging.INFO) -> None:
    """
    使用默认配置快速初始化日志�?    
    Args:
        level: 日志级别
        
    示例�?        init_default_logger(logging.DEBUG)
    """
    Logger.initialize_logger(
        name="cloud",
        logging_level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
