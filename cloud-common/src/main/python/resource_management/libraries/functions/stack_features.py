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

Enhanced Stack Feature Validation Utilities
"""

# Standard library imports
import json
import logging
from typing import Dict, Any, Optional, Tuple, Union

# Package imports
from resource_management.core.exceptions import ConfigurationError, StackFeatureError
from resource_management.core.logger import StructuredLogger
from resource_management.libraries.functions.constants import Direction, StackFeature
from resource_management.libraries.functions.version import compare_versions, parse_stack_version, format_stack_version

# Constants
ROLE_COMMAND_STOP = "STOP"
ROLE_COMMAND_CUSTOM = "CUSTOM_COMMAND"

# Initialize structured logger
logger = StructuredLogger(__name__)

class StackFeatureValidator:
    """提供堆栈特性版本检查的高级接口"""

    def __init__(self, cluster_config: Dict[str, Any]):
        """
        初始化堆栈特性验证器
        
        :param cluster_config: 集群配置字典
        """
        self.config = cluster_config
        self.stack_name = self._get_stack_name()
        self.stack_features = self._load_stack_features()
        
    def _get_stack_name(self) -> str:
        """安全获取堆栈名称"""
        try:
            stack_name = self.config["clusterLevelParams"]["stack_name"]
            if not stack_name:
                raise ConfigurationError("堆栈名称不可为空")
            return stack_name
        except KeyError:
            logger.warning("配置中缺少堆栈名称")
            raise ConfigurationError("无法找到堆栈名称")
    
    def _load_stack_features(self) -> Dict[str, Any]:
        """加载并解析堆栈特性配置"""
        try:
            features_config = self.config["configurations"]["cluster-env"]["stack_features"]
            return json.loads(features_config).get(self.stack_name, {})
        except KeyError:
            logger.error("配置中缺少堆栈特性定义")
            raise ConfigurationError("无法找到堆栈特性配置")
        except json.JSONDecodeError:
            logger.error("堆栈特性配置解析失败")
            raise ConfigurationError("堆栈特性配置格式错误")
    
    def is_feature_supported(self, feature: StackFeature, context_version: str = None) -> bool:
        """
        验证特定堆栈版本是否支持给定特性
        
        :param feature: 要检查的特性
        :param context_version: 上下文版本（可选）
        :return: 是否支持该特性
        """
        version = context_version or get_stack_context_version(self.config)
        
        if not version:
            logger.debug(f"未提供堆栈版本，无法验证特性 '{feature}'")
            return False
        
        try:
            feature_def = next(f for f in self.stack_features["stack_features"] if f["name"] == feature.value)
        except StopIteration:
            logger.debug(f"未找到特性 '{feature}' 的配置定义")
            return False
        
        min_version = feature_def.get("min_version")
        max_version = feature_def.get("max_version")
        
        is_supported = True
        
        # 检查最低版本要求
        if min_version:
            if compare_versions(version, min_version, format=True) < 0:
                is_supported = False
                
        # 检查最高版本限制
        if is_supported and max_version:
            if compare_versions(version, max_version, format=True) >= 0:
                is_supported = False
        
        logger.info(f"堆栈特性验证: 特性='{feature}', "
                    f"版本='{version}', 支持={is_supported}, "
                    f"范围=[{min_version or '-∞'}, {max_version or '∞'})")
        
        return is_supported

def get_stack_context_version(config: Dict[str, Any]) -> str:
    """
    根据操作上下文确定正确的堆栈版本
    
    :param config: 包含集群级别和命令参数的配置字典
    :return: 用于堆栈特性检查的版本字符串
    
    >>> config = {
    ...     "clusterLevelParams": {"stack_version": "2.7.0.0"},
    ...     "commandParams": {"version": "2.7.1.0"}
    ... }
    >>> get_stack_context_version(config)
    '2.7.1.0'
    """
    # 获取基础堆栈版本
    cluster_stack_version = config["clusterLevelParams"]["stack_version"]
    
    # 获取命令相关参数
    command_params = config.get("commandParams", {})
    command_version = command_params.get("version")
    command_stack = command_params.get("target_stack")
    upgrade_direction = command_params.get("upgrade_direction", "").lower()
    
    # 初始值（90%情况适用）
    feature_version = command_version or cluster_stack_version
    
    # 不是升级操作直接返回
    if not upgrade_direction:
        logger.info("标准上下文版本确定", 
                   cluster_version=cluster_stack_version, 
                   command_version=command_version,
                   feature_version=feature_version)
        return feature_version
    
    # 处理STOP命令的特殊情况
    if _is_stop_command(config):
        feature_version = _determine_stop_command_version(
            cluster_stack_version, 
            command_version, 
            upgrade_direction
        )
    
    logger.info("操作上下文版本确定",
                operation_type="升级" if upgrade_direction else "标准",
                operation_direction=upgrade_direction,
                cluster_version=cluster_stack_version,
                command_version=command_version,
                feature_version=feature_version)
    
    return feature_version

def _is_stop_command(config: Dict[str, Any]) -> bool:
    """
    检查配置是否对应STOP命令
    
    :param config: 配置字典
    :return: 是否是STOP命令
    
    >>> config = {"roleCommand": "STOP"}
    >>> _is_stop_command(config)
    True
    """
    role_command = config["roleCommand"]
    
    # 直接STOP命令
    if role_command == ROLE_COMMAND_STOP:
        return True
    
    # 自定义的STOP命令
    if role_command == ROLE_COMMAND_CUSTOM:
        custom_command = config.get("commandParams", {}).get("custom_command")
        return custom_command == ROLE_COMMAND_STOP
    
    return False

def _determine_stop_command_version(
    cluster_version: str,
    command_version: str,
    upgrade_direction: str
) -> str:
    """
    确定STOP命令的正确版本上下文
    
    :param cluster_version: 集群基础版本
    :param command_version: 命令指定的版本
    :param upgrade_direction: 升级方向
    :return: 正确的版本字符串
    """
    # 降级操作
    if upgrade_direction == Direction.DOWNGRADE:
        try:
            from resource_management.libraries.functions import upgrade_summary
            return upgrade_summary.get_source_version(command_version or cluster_version)
        except ImportError:
            logger.error("降级操作需要upgrade_summary模块")
            return command_version or cluster_version
    
    # 升级操作
    return command_version or cluster_version

def validate_stack_configuration(config: Dict[str, Any]) -> None:
    """
    验证堆栈配置的完整性
    
    :param config: 集群配置字典
    :raises ConfigurationError: 配置不完整时抛出
    """
    required_keys = [
        "clusterLevelParams",
        "commandParams",
        "configurations/cluster-env/stack_features"
    ]
    
    missing_keys = []
    
    # 检查顶级配置部分
    for key in ["clusterLevelParams", "commandParams"]:
        if key not in config:
            missing_keys.append(key)
    
    # 检查集群环境配置
    try:
        if "cluster-env" not in config["configurations"]:
            missing_keys.append("configurations/cluster-env")
        elif "stack_features" not in config["configurations"]["cluster-env"]:
            missing_keys.append("configurations/cluster-env/stack_features")
    except KeyError:
        missing_keys.append("configurations/cluster-env")
    
    if missing_keys:
        logger.critical("堆栈配置不完整，缺少关键参数", missing=missing_keys)
        raise ConfigurationError(f"配置缺少必要字段: {', '.join(missing_keys)}")

# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 示例配置数据
    sample_config = {
        "clusterLevelParams": {
            "stack_name": "HDP",
            "stack_version": "2.6.5.0"
        },
        "commandParams": {
            "version": "3.0.1.0",
            "target_stack": "HDP",
            "upgrade_direction": "UPGRADE",
            "custom_command": "STOP"
        },
        "roleCommand": "CUSTOM_COMMAND",
        "configurations": {
            "cluster-env": {
                "stack_features": json.dumps({
                    "HDP": {
                        "stack_features": [
                            {"name": "rolling_upgrade", "min_version": "2.3.0.0"},
                            {"name": "config_versioning", "min_version": "2.4.0.0"},
                            {"name": "downgrade", "max_version": "3.0.0.0"}
                        ]
                    }
                })
            }
        }
    }
    
    try:
        validate_stack_configuration(sample_config)
        
        # 创建堆栈特性验证器
        validator = StackFeatureValidator(sample_config)
        
        # 获取操作上下文版本
        context_version = get_stack_context_version(sample_config)
        print(f"操作上下文版本: {context_version}")
        
        # 检查特性支持
        print(f"滚动升级支持: {validator.is_feature_supported(StackFeature.ROLLING_UPGRADE, context_version)}")
        print(f"降级支持: {validator.is_feature_supported(StackFeature.DOWNGRADE, context_version)}")
        
    except ConfigurationError as ce:
        print(f"配置错误: {str(ce)}")
    except StackFeatureError as sfe:
        print(f"堆栈特性错误: {str(sfe)}")

