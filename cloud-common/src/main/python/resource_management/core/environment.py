#!/usr/bin/env python3
import os
import types
import logging
import shutil
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Union, List, Tuple
from enum import IntEnum

from resource_management.core import shell
from resource_management.core.exceptions import Fail
from resource_management.core.providers import find_provider
from resource_management.core.utils import AttributeDictionary
from resource_management.core.system import System
from resource_management.core.logger import Logger

# 线程本地存储
_thread_local = threading.local()
_INSTANCE_NAME = "environment_instance"


class RunMode(IntEnum):
    """资源执行模式"""
    NORMAL = 0
    TEST = 1


class ConditionType(IntEnum):
    """条件类型枚举"""
    BOOLEAN = 0
    CALLABLE = 1
    SHELL_COMMAND = 2


class Environment:
    """
    环境管理器
    
    核心功能：
    1. 资源配置管理：存储和管理资源实例
    2. 执行上下文：提供全局配置、参数、备份路径
    3. 条件执行：支持 not_if 和 only_if 条件判断
    4. 延迟动作：支持资源动作的延迟执行
    5. 线程安全：基于线程本地存储实现单例模式
    
    生命周期：
    - __enter__：进入上下文，设置为当前线程实例
    - run()：执行所有待处理资源
    - __exit__：退出上下文，清理线程实例
    """
    
    def __init__(
        self,
        basedir: Optional[str] = None,
        tmp_dir: Optional[str] = None,
        test_mode: bool = False,
        logger: Optional[logging.Logger] = None,
        logging_level: int = logging.INFO,
    ):
        """
        初始化环境管理器
        
        Args:
            basedir: 基础目录，用于查找 templates/files 子目录
            tmp_dir: 临时目录路径
            test_mode: 测试模式开关（True 时资源需手动执行）
            logger: 自定义日志记录器
            logging_level: 日志级别
            
        配置项：
        - date: 当前时间
        - backup.path: 文件备份目录
        - backup.prefix: 备份文件名前缀
        - basedir: 资源基础目录
        - params: 模板参数字典
        """
        self.reset(basedir, test_mode, tmp_dir)
        
        if logger:
            Logger.logger = logger
        else:
            Logger.initialize_logger(__name__, logging_level)
    
    def reset(self, basedir: Optional[str], test_mode: bool, tmp_dir: Optional[str]) -> None:
        """重置环境状态"""
        self.system = System.get_instance()
        self.config = AttributeDictionary()
        self.resources: Dict[str, Any] = {}
        self.resource_list: List[Any] = []
        self.delayed_actions: List[Tuple[str, Any]] = []
        self.test_mode = test_mode
        self.tmp_dir = tmp_dir
        
        self.update_config({
            "date": datetime.now(),
            "backup.path": "/tmp/resource_management/backup",
            "backup.prefix": datetime.now().strftime("%Y%m%d%H%M%S"),
            "basedir": basedir,
            "params": AttributeDictionary(),
        })
    
    def backup_file(self, path: str) -> str:
        """
        备份文件到备份目录
        
        Args:
            path: 要备份的源文件路径
            
        Returns:
            备份文件完整路径
            
        实现逻辑：
        1. 确保备份目录存在（权限 0o700）
        2. 生成备份文件名：prefix + path.replace("/", "-")
        3. 复制文件到备份目录
        4. 记录备份日志
        """
        backup_path = self.config.backup.path
        backup_prefix = self.config.backup.prefix
        
        if not os.path.exists(backup_path):
            os.makedirs(backup_path, mode=0o700)
            Logger.debug(f"创建备份目录: {backup_path}")
        
        backup_name = f"{backup_prefix}{path.replace('/', '-')}"
        backup_full_path = os.path.join(backup_path, backup_name)
        
        Logger.info(f"备份文件: {path} -> {backup_full_path}")
        shutil.copy2(path, backup_full_path)  # 使用 copy2 保留元数据
        
        return backup_full_path
    
    def update_config(self, attributes: Dict[str, Any], overwrite: bool = True) -> None:
        """
        更新配置字典（支持嵌套路径）
        
        Args:
            attributes: 配置属性字典，键支持点号分隔（如 "backup.path"）
            overwrite: 是否覆盖已存在的配置项
            
        示例：
            update_config({
                "backup.path": "/new/path",
                "params.java_home": "/usr/lib/jvm/java"
            })
        """
        for key, value in attributes.items():
            attr = self.config
            path_parts = key.split(".")
            
            # 遍历到父级容器
            for part in path_parts[:-1]:
                if part not in attr:
                    attr[part] = AttributeDictionary()
                attr = attr[part]
            
            # 设置最终值
            final_key = path_parts[-1]
            if overwrite or final_key not in attr:
                attr[final_key] = value
    
    def set_params(self, arg: Union[Dict[str, Any], types.ModuleType]) -> None:
        """
        设置模板渲染参数
        
        Args:
            arg: 参数字典或包含配置的模块
            
        过滤规则：
        - 排除以 "__" 开头的系统变量
        - 排除可调用对象（方法/函数）
        - 排除模块对象（__file__ 属性）
        
        Args 可以是：
        - 普通字典：{"java_home": "/opt/java"}
        - 模块对象：import config_params
        """
        if isinstance(arg, dict):
            variables = arg
        elif isinstance(arg, types.ModuleType):
            variables = {var: getattr(arg, var) for var in dir(arg)}
        else:
            raise Fail(f"set_params 只支持 dict 或 module 类型，得到: {type(arg)}")
        
        for name, value in variables.items():
            try:
                if (not name.startswith("__") and
                    not callable(value) and
                    not hasattr(value, "__file__")):
                    self.config.params[name] = value
                    Logger.debug(f"设置参数: {name} = {value}")
            except Exception as ex:
                Logger.debug(f"跳过参数 '{name}': {ex}")
    
    def run_action(self, resource: Any, action: str) -> None:
        """
        执行资源的指定动作
        
        Args:
            resource: 资源实例
            action: 动作名称（如 "create", "delete"）
            
        流程：
        1. 查找对应的 Provider 类
        2. 实例化 Provider
        3. 调用 action_{action} 方法
        
        Raises:
            Fail: 当 Provider 不存在或动作未实现时
        """
        provider_class = find_provider(self, resource.__class__.__name__, resource.provider)
        provider = provider_class(resource)
        
        action_method = getattr(provider, f"action_{action}", None)
        if not action_method:
            raise Fail(f"Provider '{provider_class.__name__}' 未实现动作 '{action}'")
        
        Logger.debug(f"执行资源动作: {resource} -> {action}")
        action_method()
    
    def _check_condition(self, condition: Any) -> bool:
        """
        判断条件是否满足
        
        支持类型：
        - bool: 直接返回布尔值
        - Callable: 调用函数并返回结果
        - str: 作为 shell 命令执行，返回码为 0 表示 True
        
        Args:
            condition: 条件表达式
            
        Returns:
            bool: 条件是否满足
            
        Raises:
            Fail: 未知条件类型
        """
        if isinstance(condition, bool):
            return condition
        
        if callable(condition):
            return condition()
        
        if isinstance(condition, str):
            ret_code, _ = shell.call(condition)
            return ret_code == 0
        
        raise Fail(f"未知的条件类型 {type(condition)}: {condition!r}")
    
    def run(self) -> None:
        """
        执行所有待处理的资源和延迟动作
        
        执行流程：
        1. 按顺序执行 resource_list 中的资源
        2. 对每个资源检查 not_if/only_if 条件
        3. 执行资源的 action 列表
        4. 最后执行 delayed_actions 队列中的动作
        """
        # 执行资源列表
        while self.resource_list:
            resource = self.resource_list.pop(0)
            Logger.info_resource(resource)
            
            # 初始等待
            if getattr(resource, 'initial_wait', None):
                Logger.debug(f"初始等待 {resource.initial_wait}s")
                time.sleep(resource.initial_wait)
            
            # not_if 条件检查
            not_if = getattr(resource, 'not_if', None)
            if not_if is not None and self._check_condition(not_if):
                Logger.info(f"跳过 {resource} (not_if 条件满足)")
                continue
            
            # only_if 条件检查
            only_if = getattr(resource, 'only_if', None)
            if only_if is not None and not self._check_condition(only_if):
                Logger.info(f"跳过 {resource} (only_if 条件不满足)")
                continue
            
            # 执行所有动作
            actions = getattr(resource, 'action', [])
            for action in actions:
                ignore_failures = getattr(resource, 'ignore_failures', False)
                
                if not ignore_failures:
                    self.run_action(resource, action)
                else:
                    try:
                        self.run_action(resource, action)
                    except Exception as ex:
                        Logger.info(f"忽略 {resource} 的失败 (ignore_failures=True): {ex}")
        
        # 执行延迟动作队列
        while self.delayed_actions:
            action, resource = self.delayed_actions.pop(0)
            Logger.debug(f"执行延迟动作: {resource} -> {action}")
            self.run_action(resource, action)
    
    @classmethod
    def has_instance(cls) -> bool:
        """检查当前线程是否存在环境实例"""
        return hasattr(_thread_local, _INSTANCE_NAME)
    
    @classmethod
    def get_instance(cls) -> 'Environment':
        """
        获取当前线程的环境实例
        
        Raises:
            Exception: 当当前线程没有环境实例时
        """
        instance = getattr(_thread_local, _INSTANCE_NAME, None)
        if instance is None:
            raise Exception(f"当前线程 {threading.current_thread()} 未设置 Environment 实例")
        return instance
    
    @classmethod
    def get_instance_copy(cls) -> 'Environment':
        """
        创建环境实例的副本（仅复制配置，不复制执行状态）
        
        Returns:
            新的 Environment 实例（包含复制后的 config）
        """
        old_instance = cls.get_instance()
        new_instance = Environment()
        
        # 深拷贝配置（递归复制）
        new_instance.config = AttributeDictionary()
        for key, value in old_instance.config.items():
            if isinstance(value, AttributeDictionary):
                new_instance.config[key] = AttributeDictionary(value)
            else:
                new_instance.config[key] = value
        
        return new_instance
    
    def __enter__(self) -> 'Environment':
        """
        上下文管理器入口
        
        将当前实例设置为线程本地变量
        
        Raises:
            Exception: 当尝试嵌套进入 Environment 时
        """
        if hasattr(_thread_local, _INSTANCE_NAME):
            raise Exception(f"线程 {threading.current_thread()} 已存在 Environment，不支持嵌套")
        
        setattr(_thread_local, _INSTANCE_NAME, self)
        Logger.debug(f"进入 Environment 上下文 (线程: {threading.current_thread().name})")
        return self
    
    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> bool:
        """
        上下文管理器出口
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯
            
        Returns:
            bool: False 表示不吞掉异常，让其继续传播
        """
        if not hasattr(_thread_local, _INSTANCE_NAME):
            raise Exception(f"线程 {threading.current_thread()} 未进入 Environment 上下文")
        
        setattr(_thread_local, _INSTANCE_NAME, None)
        Logger.debug(f"退出 Environment 上下文 (线程: {threading.current_thread().name})")
        return False  # 不吞掉异常
    
    def __getstate__(self) -> Dict[str, Any]:
        """序列化状态（用于 pickle/deepcopy）"""
        return {
            "config": self.config,
            "resources": self.resources,
            "resource_list": self.resource_list,
            "delayed_actions": self.delayed_actions,
        }
    
    def __setstate__(self, state: Dict[str, Any]) -> None:
        """反序列化状态"""
        self.__init__()
        self.config = state["config"]
        self.resources = state["resources"]
        self.resource_list = state["resource_list"]
        self.delayed_actions = state["delayed_actions"]


# 便捷函数
def get_env() -> Environment:
    """
    获取当前线程的环境实例
    
    Returns:
        Environment: 当前线程的环境实例
    """
    return Environment.get_instance()


def create_env(**kwargs) -> Environment:
    """
    创建并进入新的环境上下文
    
    Args:
        **kwargs: Environment.__init__ 的参数
        
    Returns:
        Environment: 新的环境实例
    
    示例：
        with create_env(basedir="/opt/app", test_mode=True) as env:
            # 在环境中执行操作
            env.update_config({"backup.path": "/tmp/backup"})
    """
    return Environment(**kwargs)

