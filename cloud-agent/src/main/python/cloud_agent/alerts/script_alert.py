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

import logging
import os
import re
import importlib.util
from typing import Dict, Any, Optional, Tuple, Callable
from pathlib import Path

from alerts.base_alert import BaseAlert, AlertState
from resource_management.core.environment import Environment
from resource_management.core.exceptions import ScriptExecutionException
from resource_management.libraries.script.script import Script
from cloud_commons.constants import AGENT_TMP_DIR

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 类常量
PATH_TO_SCRIPT_REGEXP = re.compile(r"((.*)services(.*)package)")
DEFAULT_KINIT_TIMEOUT = 14400  # 默认 Kerberos 票据超时时间（4小时）

class ScriptExecutor:
    """
    脚本执行器类，封装脚本加载和执行逻辑
    """
    DIRECTORIES = ["stacks", "common_services", "host_scripts", "extensions"]
    
    def __init__(self, alert_name: str, paths: Dict[str, str]):
        """
        初始化脚本执行器
        
        Args:
            alert_name: 告警名称
            paths: 脚本路径配置字典
        """
        self.alert_name = alert_name
        self.paths = paths
        self.script_path = None
        self.module = None
        
    def find_script(self) -> Path:
        """查找脚本文件路径"""
        # 优先使用明确指定的路径
        if not self.paths["path"]:
            raise ScriptExecutionException(f"[Alert][{self.alert_name}] 未定义脚本路径")
            
        script_name = self.paths["path"]
        script_path = Path(script_name)
        
        # 检查是否是绝对路径
        if script_path.is_absolute() and script_path.exists():
            return script_path
            
        # 检查备用目录
        for dir_type in self.DIRECTORIES:
            if dir_key := f"{dir_type}_dir":
                if dir_path := self.paths.get(dir_key):
                    candidate = Path(dir_path) / Path(script_name).name
                    if candidate.exists():
                        return candidate
                        
        # 尝试从模块路径中查找
        for dir_type in self.DIRECTORIES:
            if dir_path := self.paths.get(f"{dir_type}_dir"):
                for part in Path(script_name).parts:
                    candidate = Path(dir_path) / part
                    if candidate.exists():
                        return candidate
                        
        # 所有尝试都失败
        searched_dirs = ", ".join([
            self.paths.get(f"{d}_dir", "") for d in self.DIRECTORIES 
            if f"{d}_dir" in self.paths
        ])
        raise ScriptExecutionException(
            f"[Alert][{self.alert_name}] 无法找到脚本 '{script_name}'。"
            f"搜索目录: {searched_dirs}"
        )
    
    def load_script(self) -> Callable:
        """加载脚本作为可执行模块"""
        self.script_path = self.find_script()
        
        if self.script_path.suffix != ".py":
            raise ScriptExecutionException(
                f"[Alert][{self.alert_name}] 无法执行非Python脚本: {self.script_path}"
            )
            
        module_name = f"alert_script_{self.alert_name}"
        spec = importlib.util.spec_from_file_location(module_name, str(self.script_path))
        
        if spec is None or spec.loader is None:
            raise ScriptExecutionException(
                f"[Alert][{self.alert_name}] 无法加载脚本: {self.script_path}"
            )
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        logger.info("[Alert][%s] 成功加载脚本: %s", self.alert_name, self.script_path)
        return module
    
    def execute_script(
        self, 
        configurations: Dict, 
        params: Dict, 
        hostname: str
    ) -> Tuple[AlertState, list]:
        """执行脚本并处理结果"""
        script_module = self.load_script()
        
        # 获取需要的配置信息
        try:
            tokens_func = getattr(script_module, "get_tokens", None)
            tokens = tokens_func() if callable(tokens_func) else []
            token_values = {
                token: self._get_config_value(configurations, token) 
                for token in tokens
            }
        except Exception as e:
            logger.warning(
                "[Alert][%s] 获取配置令牌失败: %s", self.alert_name, str(e)
            )
            token_values = {}
            
        # 设置脚本执行环境
        Script.config = configurations
        
        try:
            # 尝试确定basedir
            match = PATH_TO_SCRIPT_REGEXP.match(str(self.script_path))
            basedir = match.group(1) if match else os.getcwd()
            
            # 使用资源管理环境执行
            with Environment(
                basedir=basedir,
                tmp_dir=AGENT_TMP_DIR or os.getcwd(),
                logger=logging.getLogger(f"alerts.{self.alert_name}")
            ) as env:
                result = script_module.execute(
                    config=token_values, 
                    params=params, 
                    host_name=hostname
                )
                
            log_level = logging.DEBUG
            if result[0] == AlertState.CRITICAL:
                log_level = logging.ERROR
            elif result[0] in (AlertState.WARNING, AlertState.UNKNOWN):
                log_level = logging.WARNING
                
            logger.log(
                log_level,
                "[Alert][%s] 脚本执行结果: %s - %s",
                self.alert_name,
                result[0].name,
                result[1] if isinstance(result[1], str) else str(result[1])
            )
                
            return result[0], [result[1]] if isinstance(result[1], str) else list(result[1])
        except Exception as e:
            logger.exception("[Alert][%s] 脚本执行失败", self.alert_name)
            return AlertState.UNKNOWN, [f"脚本执行错误: {str(e)}"]
    
    def _get_config_value(self, configurations: Dict, key: str) -> Optional[str]:
        """安全获取配置值"""
        try:
            # 尝试使用点分割路径访问嵌套配置
            parts = key.split('.')
            value = configurations
            for part in parts:
                if part in value:
                    value = value[part]
                else:
                    return None
            return value
        except Exception:
            return None

class ScriptAlert(BaseAlert):
    """自定义脚本执行告警类"""
    
    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        初始化脚本告警
        
        Args:
            alert_meta: 告警元数据
            alert_source_meta: 告警来源元数据
            config: 配置对象
        """
        # 配置默认报告格式
        alert_source_meta.setdefault("reporting", {
            "ok": {"text": "{0}"},
            "warning": {"text": "{0}"},
            "critical": {"text": "{0}"},
            "unknown": {"text": "{0}"},
        })
        
        super().__init__(alert_meta, alert_source_meta, config)
        
        # 初始化脚本路径信息
        self.path_config = {
            "path": alert_source_meta.get("path"),
            "stacks_dir": alert_source_meta.get("stacks_directory"),
            "common_services_dir": alert_source_meta.get("common_services_directory"),
            "host_scripts_dir": alert_source_meta.get("host_scripts_directory"),
            "extensions_dir": alert_source_meta.get("extensions_directory"),
        }
        
        # 初始化参数
        self.parameters = {
            param["name"]: param["value"]
            for param in alert_source_meta.get("parameters", [])
            if "name" in param and "value" in param
        }
        
        # 设置Kerberos超时参数
        kerb_timeout = config.get("agent", "alert_kinit_timeout", DEFAULT_KINIT_TIMEOUT)
        self.parameters["kerberos_kinit_timer"] = kerb_timeout
        
        # 初始化脚本执行器
        self.executor = ScriptExecutor(self.get_name(), self.path_config)
    
    def _collect(self) -> Tuple[AlertState, list]:
        """
        执行脚本收集告警数据
        
        Returns:
            元组 (告警状态, 结果详情)
        """
        try:
            # 获取配置信息
            configurations = self.configuration_builder.get_configuration(
                self.cluster_id, None, None
            )
            
            # 执行脚本
            return self.executor.execute_script(
                configurations=configurations,
                params=self.parameters,
                hostname=self.host_name
            )
        except ScriptExecutionException as e:
            logger.error(str(e))
            return AlertState.UNKNOWN, [str(e)]
        except Exception as e:
            logger.exception("[Alert][%s] 告警收集过程中发生错误", self.get_name())
            return AlertState.CRITICAL, [f"系统错误: {str(e)}"]
    
    def _get_reporting_text(self, state: AlertState) -> str:
        """
        获取告警报告文本模板
        
        Args:
            state: 告警状态
            
        Returns:
            报告文本模板字符串
        """
        return "{0}"
