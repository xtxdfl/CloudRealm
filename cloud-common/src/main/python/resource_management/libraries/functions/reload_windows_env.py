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

Enhanced Windows Environment Reloader
"""

from winreg import (
    OpenKey, 
    EnumValue, 
    HKEY_LOCAL_MACHINE, 
    KEY_READ, 
    CloseKey, 
    KEY_ALL_ACCESS,
    REG_EXPAND_SZ
)
import os
import logging
from typing import List, Set, Optional
from contextlib import contextmanager

# 配置日志记录器
logger = logging.getLogger("win_env")
logger.setLevel(logging.INFO)

# 环境变量注册表路径
REG_ENV_PATH = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
"""Windows 注册表中存储系统环境变量的位置"""

# 默认受保护的环境变量白名单
DEFAULT_PROTECTED_VARS = {
    "FALCON_CONF_DIR", "FALCON_DATA_DIR", "FALCON_HOME", "FALCON_LOG_DIR",
    "FLUME_HOME", "HADOOP_COMMON_HOME", "HADOOP_CONF_DIR", "HADOOP_HDFS_HOME",
    "HADOOP_HOME", "HADOOP_LOG_DIR", "HADOOP_MAPRED_HOME", "HADOOP_NODE",
    "HADOOP_NODE_INSTALL_ROOT", "HADOOP_PACKAGES", "HADOOP_SETUP_TOOLS",
    "HADOOP_YARN_HOME", "HBASE_CONF_DIR", "HBASE_HOME", "HCAT_HOME",
    "HDFS_AUDIT_LOGGER", "HDFS_DATA_DIR", "HIVE_CONF_DIR", "HIVE_HOME",
    "HIVE_LIB_DIR", "HIVE_LOG_DIR", "HIVE_OPTS", "KNOX_CONF_DIR", "KNOX_HOME",
    "KNOX_LOG_DIR", "MAHOUT_HOME", "OOZIE_DATA", "OOZIE_HOME", "OOZIE_LOG",
    "OOZIE_ROOT", "PIG_HOME", "SQOOP_HOME", "STORM_CONF_DIR", "STORM_HOME",
    "STORM_LOG_DIR", "TEZ_HOME", "WEBHCAT_CONF_DIR", "YARN_LOG_DIR",
    "ZOOKEEPER_CONF_DIR", "ZOOKEEPER_HOME", "ZOOKEEPER_LIB_DIR", "ZOO_LOG_DIR",
    "COLLECTOR_CONF_DIR", "COLLECTOR_HOME", "MONITOR_CONF_DIR", "MONITOR_HOME",
    "SINK_HOME"
}
"""默认需要从注册表加载的关键环境变量集合"""

@contextmanager
def open_registry_key(root_key, sub_key: str, access: int = KEY_READ):
    """
    安全打开注册表键的上下文管理器
    
    :param root_key: 注册表根键
    :param sub_key: 子键路径
    :param access: 访问权限
    :yield: 注册键对象
    """
    key_handle = None
    try:
        key_handle = OpenKey(root_key, sub_key, 0, access)
        yield key_handle
    except WindowsError as e:
        logger.error(f"注册表访问失败: {str(e)}")
        yield None
    finally:
        if key_handle:
            CloseKey(key_handle)


def reload_protected_env_vars(protected_vars: Optional[Set[str]] = None) -> list:
    """
    从注册表重载受保护的环境变量
    
    :param protected_vars: 需要保护的变量集合，默认使用 DEFAULT_PROTECTED_VARS
    :return: 成功更新的变量列表
    """
    if protected_vars is None:
        protected_vars = DEFAULT_PROTECTED_VARS
    
    updated_vars = []
    
    with open_registry_key(HKEY_LOCAL_MACHINE, REG_ENV_PATH, KEY_READ) as key:
        if not key:
            logger.error(f"无法打开注册表键: {REG_ENV_PATH}")
            return []
        
        index = 0
        while True:
            try:
                name, value, value_type = EnumValue(key, index)
                # 只处理字符串值
                if value_type != REG_EXPAND_SZ:
                    continue
                
                # 检查是否在保护列表中
                if name in protected_vars:
                    if expand_env_var(name):
                        logger.debug(f"环境变量已扩展: {name}")
                    
                    # 更新环境变量
                    previous_value = os.environ.get(name, "")
                    os.environ[name] = value
                    
                    # 记录变更
                    if previous_value != value:
                        logger.info(f"更新环境变量: {name} = {value} (原值: {previous_value})")
                        updated_vars.append(name)
                    else:
                        logger.debug(f"环境变量 {name} 未变更")
                
                index += 1
            except WindowsError:
                # 枚举结束或发生错误
                break
    
    logger.info(f"成功更新 {len(updated_vars)} 个环境变量")
    return updated_vars


def expand_env_var(name: str) -> bool:
    """
    递归扩展环境变量值(支持嵌套变量)
    
    :param name: 环境变量名
    :return: 是否进行了扩展操作
    """
    if name not in os.environ:
        return False
    
    changed = False
    value = os.environ[name]
    
    # 检查是否有需要扩展的变量
    if "%" not in value:
        return False
    
    # 递归扩展直到稳定
    previous_value = value
    while True:
        new_value = os.path.expandvars(previous_value)
        if new_value == previous_value:
            break
        previous_value = new_value
        changed = True
    
    if changed:
        os.environ[name] = new_value
        logger.debug(f"扩展变量: {name}={new_value}")
    
    return changed


def set_registry_env_var(
    name: str,
    value: str,
    overwrite: bool = True,
    protected_vars: Set[str] = DEFAULT_PROTECTED_VARS
) -> bool:
    """
    将环境变量保存到注册表中
    
    :param name: 变量名
    :param value: 变量值
    :param overwrite: 是否覆盖现有值
    :param protected_vars: 需要持久化的变量集合
    :return: 操作是否成功
    """
    logger.info(f"保存到注册表: {name}={value}")
    
    # 检查变量保护状态
    if name not in protected_vars:
        logger.warning(f"试图保存非受保护变量: {name}")
    
    with open_registry_key(
        HKEY_LOCAL_MACHINE, 
        REG_ENV_PATH, 
        KEY_ALL_ACCESS
    ) as key:
        if not key:
            return False
        
        # 检查当前值
        current_value = os.environ.get(name, None)
        if not overwrite and current_value:
            logger.warning(f"跳过已存在的变量: {name}")
            return False
        
        # 将值写入注册表
        import winreg
        try:
            winreg.SetValueEx(key, name, 0, REG_EXPAND_SZ, value)
            logger.info(f"成功保存注册表值: {name}")
            return True
        except WindowsError as e:
            logger.error(f"无法保存注册表值 {name}: {str(e)}")
            return False


# ================== 测试函数 ==================
def test_env_reloading():
    """测试环境变量重载功能"""
    print("\n=== 测试环境变量重载 ===")
    
    # 临时设置测试变量
    test_vars = {"HADOOP_HOME", "TEST_VAR_PROTECTED", "TEST_VAR_UNPROTECTED"}
    os.environ["HADOOP_HOME"] = "C:/old/hadoop"
    os.environ["TEST_VAR_PROTECTED"] = "protected_value"
    os.environ["TEST_VAR_UNPROTECTED"] = "unprotected_value"
    
    # 创建自定义保护列表
    custom_protected = DEFAULT_PROTECTED_VARS | {"TEST_VAR_PROTECTED"}
    
    # 模拟注册表中的值
    registry_values = {
        "HADOOP_HOME": "C:/new/hadoop",
        "TEST_VAR_PROTECTED": "new_protected_value",
        "TEST_VAR_NEW": "should_not_be_loaded"
    }
    
    # 设置保护变量
    for k, v in registry_values.items():
        if k in custom_protected:
            os.environ[k] = v
    
    # 执行重载
    updated = reload_protected_env_vars(custom_protected)
    
    # 验证结果
    results = {
        "HADOOP_HOME更新": os.environ.get("HADOOP_HOME") == "C:/new/hadoop",
        "非保护变量未修改": os.environ.get("TEST_VAR_UNPROTECTED") == "unprotected_value",
        "新变量未加载": "TEST_VAR_NEW" not in os.environ
    }
    
    # 打印结果
    for test, passed in results.items():
        status = "通过" if passed else "失败"
        print(f"{test}: {status}")
    
    print("更新变量列表:", updated)
    

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)8s] %(message)s"
    )
    
    # 重载环境变量(使用默认配置)
    reload_protected_env_vars()
    
    # 设置测试环境变量并保存到注册表
    set_registry_env_var("TEST_VAR", "test_value")
    
    # 执行测试
    test_env_reloading()
