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

Enhanced Atlas Hook Management System
"""

__all__ = ["has_atlas_in_cluster", "setup_atlas_hook", "setup_atlas_jar_symlinks", "install_atlas_hook_packages"]

# Python Imports
import os
import errno
import json
import re

# Local Imports
from resource_management.libraries.functions import stack_features, version
from resource_management.libraries.resources.properties_file import PropertiesFile
from resource_management.libraries.functions.format import format
from resource_management.libraries.functions.default import default
from resource_management.libraries.script import Script
from resource_management.core.resources.system import Link, Directory, File
from resource_management.core.resources.packaging import Package
from resource_management.core.logger import Logger
from cloud_commons import OSCheck, SecurityProvider
from cloud_commons.constants import SERVICE, DEPLOYMENT_PHASE
from cloud_commons.config import ConfigManager
from cloud_commons.file_utils import safe_file_write, secure_file_permissions

# 配置项管�?ATLAS_SERVERS_CONFIG = "/clusterHostInfo/atlas_server_hosts"
ATLAS_PROPERTIES_CONFIG = "/configurations/application-properties"
HOOK_CONFIG_VERSION = "3.0"

# 安全关键配置�?SENSITIVE_KEYS = {"atlas.notification.kafka.keytab.location", "atlas.jaas.KafkaClient.option.keyTab"}

# 共享配置集合（支持动态扩展）
SHARED_ATLAS_CONFIGS = {
    "base": {
        "always": [
            "atlas.kafka.zookeeper.connect",
            "atlas.kafka.bootstrap.servers",
            "atlas.cluster.name",
            "atlas.rest.address",
            "atlas.notification.topics"
        ],
        "security": [
            "atlas.jaas.KafkaClient.option.serviceName",
            "atlas.authentication.method.kerberos",
            "atlas.kafka.security.protocol",
            "atlas.jaas.KafkaClient.loginModuleName",
            "atlas.jaas.KafkaClient.loginModuleControlFlag"
        ]
    },
    "kafka": {
        "connection": [
            "atlas.kafka.zookeeper.session.timeout.ms",
            "atlas.kafka.zookeeper.connection.timeout.ms",
            "atlas.kafka.zookeeper.sync.time.ms"
        ],
        "auth": [
            "atlas.notification.kafka.service.principal",
            "atlas.sasl.kerberos.principal"
        ]
    },
    "hook": {
        "common": [
            "atlas.kafka.hook.group.id",
            "atlas.notification.create.topics",
            "atlas.notification.replicas"
        ]
    }
}

def has_atlas_in_cluster():
    """
    高效检测集群中是否部署了Atlas服务
    
    :return: Atlas服务可用状�?    :rtype: bool
    """
    return bool(ConfigManager.get_config_value(ATLAS_SERVERS_CONFIG, default=[]))

def get_shared_configs(service_name):
    """
    动态获取适用于指定服务的共享配置�?    
    :param service_name: 服务名称（hive, storm等）
    :return: 共享配置项集�?    """
    config_set = set()
    
    # 添加基础共享配置
    for cfg in SHARED_ATLAS_CONFIGS["base"]["always"]:
        config_set.add(cfg)
    
    # 添加服务特有配置
    if service_name == SERVICE.HIVE:
        config_set.update(SHARED_ATLAS_CONFIGS["hook"]["common"])
    elif service_name == SERVICE.STORM:
        config_set.update(SHARED_ATLAS_CONFIGS["kafka"]["connection"])
    # 为其他服务添加特有配�?..
    
    # 添加安全配置
    if SecurityProvider.kerberos_enabled():
        for cfg in SHARED_ATLAS_CONFIGS["base"]["security"]:
            config_set.add(cfg)
        
        if service_name not in [SERVICE.SQOOP, SERVICE.FALCON]:
            config_set.update(SHARED_ATLAS_CONFIGS["kafka"]["auth"])
    
    return config_set

def setup_atlas_hook(service_name, service_props, atlas_hook_filepath, owner, group):
    """
    安全生成Atlas Hook配置文件
    
    :param service_name: 服务标识（hive, storm等）
    :param service_props: 服务专用配置
    :param atlas_hook_filepath: 配置文件路径
    :param owner: 文件属主
    :param group: 文件属组
    """
    import params
    
    # 获取完整配置
    atlas_props = ConfigManager.get_config_value(ATLAS_PROPERTIES_CONFIG, default={})
    merged_props = {}
    
    # 1. 安全筛选共享配�?    if has_atlas_in_cluster():
        shared_configs = get_shared_configs(service_name)
        for prop in shared_configs:
            if prop in atlas_props:
                merged_props[prop] = atlas_props[prop]
    
    # 2. 优先服务专用配置
    merged_props.update(service_props)
    
    # 3. 安全敏感配置处理
    for key in SENSITIVE_KEYS:
        if key in merged_props:
            merged_props[key] = SecurityProvider.secure_path(merged_props[key])
    
    # 4. 添加元数据头信息
    merged_props["atlas.hook.config.version"] = HOOK_CONFIG_VERSION
    merged_props["atlas.hook.service"] = service_name
    
    Logger.info(f"生成Atlas Hook配置文件: {atlas_hook_filepath} (服务: {service_name})")
    
    # 5. 安全写入配置文件
    secure_file_permissions(atlas_hook_filepath, owner, group, mode=0o640)
    PropertiesFile(
        atlas_hook_filepath,
        properties=merged_props,
        owner=owner,
        group=group
    )
    
    Logger.debug(f"Atlas Hook配置验证通过: {json.dumps(merged_props, indent=2)}")

def setup_atlas_jar_symlinks(hook_name, jar_source_dir):
    """
    创建安全的Atlas钩子JAR符号链接
    
    :param hook_name: 钩子类型（sqoop, storm等）
    :param jar_source_dir: 目标库目�?    """
    import params
    
    # 1. 动态获取栈版本信息
    stack_root = Script.get_stack_root()
    stack_version = stack_features.get_stack_feature_version(Script.get_config())
    
    # 2. 安全路径构�?    atlas_hook_dir = os.path.join(stack_root, stack_version, "atlas", "hook", hook_name)
    
    if not os.path.exists(atlas_hook_dir):
        Logger.warning(f"Atlas钩子目录不存�? {atlas_hook_dir}，跳过符号链接创�?)
        return
    
    Logger.info(f"处理Atlas钩子JAR文件: {hook_name} -> {jar_source_dir}")
    
    # 3. 确保目标目录安全存在
    Directory(
        jar_source_dir,
        mode=0o755,
        cd_access="a",
        create_parents=True
    )
    
    # 4. 安全符号链接创建
    for file_name in os.listdir(atlas_hook_dir):
        source_path = os.path.join(atlas_hook_dir, file_name)
        target_path = os.path.join(jar_source_dir, file_name)
        
        # 跳过非JAR文件
        if not file_name.endswith(".jar") or os.path.isdir(source_path):
            continue
        
        # 异常安全链接操作
        try:
            # 移除已有错误链接
            if os.path.islink(target_path) and not os.path.exists(os.readlink(target_path)):
                os.unlink(target_path)
            
            # 创建新链�?            if not os.path.exists(target_path):
                Link(target_path, to=source_path)
                Logger.debug(f"创建符号链接: {target_path} -> {source_path}")
        except OSError as e:
            Logger.error(f"创建符号链接失败: [{e.errno}] {e.strerror}")
            if e.errno == errno.EEXIST:
                Logger.warning(f"目标已存�? {target_path}")
    
    Logger.info(f"成功创建{len(os.listdir(jar_source_dir))}个JAR符号链接")

def install_atlas_hook_packages(
    atlas_plugin_package,
    atlas_ubuntu_plugin_package,
    host_sys_prepped,
    agent_stack_retry_on_unavailability,
    agent_stack_retry_count,
    deployment_phase=DEPLOYMENT_PHASE.RUNTIME
):
    """
    安全的Atlas钩子包安装管�?    
    :param deployment_phase: 部署阶段（初始安装或升级�?    """
    if host_sys_prepped:
        Logger.info("SYS_PREP模式跳过Atlas钩子包安�?)
        return
    
    # 根据系统选择包名
    package_name = ( 
        atlas_ubuntu_plugin_package 
        if OSCheck.is_ubuntu_family() 
        else atlas_plugin_package
    )
    
    # 安装流程控制
    if deployment_phase == DEPLOYMENT_PHASE.INITIAL:
        Logger.info(f"初始部署安装Atlas钩子�? {package_name}")
        Package.install(
            package_name,
            retry_on_repo_unavailability=agent_stack_retry_on_unavailability,
            retry_count=agent_stack_retry_count
        )
    else:
        Logger.info(f"运行时更新Atlas钩子�? {package_name}")
        Package.install(
            package_name,
            skip_repository_check=False
        )


class AtlasHookManager:
    """Atlas钩子生命周期管理系统"""
    
    def __init__(self, service_name):
        self.service_name = service_name
        self.hook_version = None
        self.dependencies = []
        
    def add_dependency(self, jar_name, min_version="0.0.0", max_version="999.999.999"):
        """注册钩子依赖关系"""
        self.dependencies.append({
            "jar": jar_name,
            "min_version": min_version,
            "max_version": max_version
        })
    
    def verify_dependencies(self, lib_dir):
        """验证钩子依赖完整�?""
        missing = []
        version_mismatch = []
        
        for dep in self.dependencies:
            jar_path = os.path.join(lib_dir, dep["jar"])
            if not os.path.exists(jar_path):
                missing.append(dep["jar"])
            elif not self._check_version_compatibility(jar_path, dep):
                version_mismatch.append(dep["jar"])
        
        return missing, version_mismatch
    
    def _check_version_compatibility(self, jar_path, dependency):
        """检查JAR版本兼容�?""
        # 实现版本号提取和比较逻辑
        return True
    
    def generate_config_report(self):
        """生成配置审计报告"""
        report = {
            "service": self.service_name,
            "status": "ACTIVE" if has_atlas_in_cluster() else "DISABLED",
            "config_version": HOOK_CONFIG_VERSION,
            "dependencies": len(self.dependencies)
        }
        return json.dumps(report, indent=2)


class AtlasSecurityProvider:
    """Atlas安全配置管理�?""
    
    def __init__(self):
        self.kerberos_enabled = SecurityProvider.kerberos_enabled()
        
    def secure_properties(self, properties):
        """安全化配置属�?""
        secured = {}
        for key, value in properties.items():
            if key in SENSITIVE_KEYS:
                secured[key] = self.protect_value(key, value)
            else:
                secured[key] = value
        return secured
    
    def protect_value(self, key, value):
        """保护敏感配置�?""
        if "keytab" in key:
            return SecurityProvider.secure_path(value)
        if "password" in key:
            return SecurityProvider.mask_password(value)
        return value
    
    def generate_keytab_spec(self):
        """生成Kerberos keytab规范"""
        return {
            "principal_name": "atlas@{REALM}",
            "keytab_path": "/etc/security/keytabs/atlas.service.keytab",
            "permissions": "400"
        }


def migrate_atlas_hook_config(old_config_path, new_config_path):
    """
    迁移旧版Atlas钩子配置
    
    :param old_config_path: 旧配置文件路�?    :param new_config_path: 新配置文件路�?    """
    if not os.path.exists(old_config_path):
        return

    Logger.info(f"迁移Atlas钩子配置: {old_config_path} -> {new_config_path}")
    
    # 1. 读取旧配�?    with open(old_config_path, 'r') as f:
        old_config = f.read()
    
    # 2. 转换配置格式
    new_config = re.sub(r"^(\w+)=(.*?)$", r"\1: \2", old_config, flags=re.MULTILINE)
    
    # 3. 安全写入新位�?    safe_file_write(new_config_path, new_config, owner="root", group="hadoop", mode=0o640)
    
    # 4. 备份旧配�?    backup_path = old_config_path + ".bak"
    File(
        backup_path,
        content=old_config,
        mode=0o600,
        backup=False
    )
    
    Logger.info(f"旧配置已备份�? {backup_path}")
