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

Enhanced Unmanaged Resource Manager
"""

from typing import List, Dict
import json
import logging
from resource_management.libraries.script import Script
from resource_management.core.logger import Logger
from resource_management.libraries.functions.default import default

# 日志配置
logger = Logger
"""使用资源管理框架的标准日志记录器"""

class ConfigError(Exception):
    """配置相关异常基类"""
    pass

def _parse_path_list(path_str: str) -> List[str]:
    """
    解析逗号分隔的路径字符串为列表
    
    :param path_str: 逗号分隔的路径字符串
    :return: 清理后的路径列表
    """
    try:
        if not path_str.strip():
            return []
            
        return [
            path.strip()
            for path in path_str.split(",")
            if path.strip()  # 过滤空路径
        ]
    except Exception as e:
        logger.error(f"解析路径列表失败: {str(e)}")
        return []

def _get_json_config_value(config_key: str, default_value=None) -> List[str]:
    """
    安全获取和解析JSON配置值
    
    :param config_key: 配置键名
    :param default_value: 失败时返回的默认值
    :return: 解析后的列表或默认值
    """
    config = Script.get_config()
    
    try:
        # 检查键是否存在
        if config_key not in config["clusterLevelParams"]:
            logger.warning(f"配置键不存在: {config_key}")
            return default_value or []
            
        # 解析JSON值
        json_str = config["clusterLevelParams"][config_key]
        if not isinstance(json_str, str):
            logger.error(f"配置值不是字符串: {type(json_str)}")
            return default_value or []
            
        return json.loads(json_str)
    except json.JSONDecodeError as je:
        logger.error(f"JSON解析失败 ({je.msg}): {json_str[:30]}...")
        return default_value or []
    except KeyError as ke:
        logger.error(f"配置键不存在: {ke}")
        return default_value or []
    except Exception as e:
        logger.error(f"配置获取异常: {str(e)}")
        return default_value or []

def get_not_managed_resources() -> List[str]:
    """
    获取非托管HDFS资源路径列表
    
    流程:
    1. 从clusterLevelParams加载初始未管理路径列表
    2. 从cluster-env获取管理路径配置名
    3. 从指定配置加载管理路径
    4. 从非托管列表中移除管理路径
    
    :return: 最终的非托管路径列表
    :raises ConfigError: 关键配置缺失时抛出异常
    """
    # 获取初始非托管路径列表
    not_managed_paths = _get_json_config_value(
        "not_managed_hdfs_path_list", 
        default_value=[]
    )
    logger.info(f"初始非托管路径数: {len(not_managed_paths)}")
    
    config = Script.get_config()
    config_section = "configurations"
    config_key = "cluster-env"
    
    try:
        # 验证集群环境配置存在
        if config_key not in config[config_section]:
            raise ConfigError(f"关键配置段缺失: {config_key}")
            
        cluster_env = config[config_section][config_key]
        
        # 获取管理资源配置名
        if "managed_hdfs_resource_property_names" not in cluster_env:
            logger.info("未找到托管资源配置名称")
            return not_managed_paths
            
        managed_prop_names = cluster_env["managed_hdfs_resource_property_names"]
        if not managed_prop_names.strip():
            logger.info("托管资源配置名称为空")
            return not_managed_paths
            
        # 解析配置属性名称
        config_names = _parse_path_list(managed_prop_names)
        logger.info(f"托管资源配置数量: {len(config_names)}")
        
        # 遍历配置属性加载管理路径
        for prop_name in config_names:
            if not prop_name:
                continue
                
            # 获取配置路径值
            path_config = default(f"/{config_section}/{prop_name}", None)
            if path_config is None:
                logger.warning(
                    f"配置属性缺失: {prop_name} "
                    "(跳过此托管路径)"
                )
                continue
                
            # 确保路径配置为字符串
            if not isinstance(path_config, str):
                logger.error(
                    f"配置 {prop_name} 类型错误: {type(path_config)}. 应为字符串."
                )
                continue
                
            # 在多值情况下处理逗号分隔路径
            managed_paths = _parse_path_list(path_config)
            logger.debug(
                f"配置 {prop_name} 管理的路径数: {len(managed_paths)}"
            )
            
            # 从非托管列表中移除托管路径
            for path in managed_paths:
                while path in not_managed_paths:
                    not_managed_paths.remove(path)
                    logger.debug(
                        f"已移除托管路径: {path} "
                        f"(源配置: {prop_name})"
                    )
    except ConfigError as ce:
        logger.error(f"配置错误: {str(ce)}")
    except KeyError as ke:
        logger.error(f"配置缺失: {str(ke)}")
    except Exception as e:
        logger.error(f"计算非托管资源时异常: {str(e)}")
    
    logger.info(f"最终非托管路径数: {len(not_managed_paths)}")
    return not_managed_paths


# ================== 测试函数 ==================
if __name__ == "__main__":
    # 测试配置模拟
    test_config = {
        "clusterLevelParams": {
            "not_managed_hdfs_path_list": '["/tmp", "/system", "/custom/backup"]'
        },
        "configurations": {
            "cluster-env": {
                "managed_hdfs_resource_property_names": " core-site.prop1, core-site.prop2 "
            },
            "core-site": {
                "prop1": "/system,/public",
                "prop2": "/custom/backup"
            }
        }
    }
    
    # 覆盖框架方法
    Script.get_config = lambda: test_config
    default = lambda path, default_val: None if "missing" in path else test_config
    
    # 执行测试
    result = get_not_managed_resources()
    expected = ["/tmp"]
    status = "通过" if result == expected else f"失败: 期望 {expected} 得到 {result}"
    
    print("\n=== 测试结果 ===")
    print(f"最终结果: {result}")
    print(f"测试状态: {status}")
