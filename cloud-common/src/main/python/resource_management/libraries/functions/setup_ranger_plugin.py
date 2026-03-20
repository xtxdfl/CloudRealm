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

Advanced Ranger Plugin Management Framework
"""

import os
import re
import sys
import shutil
import tarfile
import logging
import tempfile
import datetime
import time
import ssl
import base64
import hashlib
import urllib.parse
from pathlib import Path
from multiprocessing.pool import ThreadPool

from resource_management.libraries.functions import ranger_functions_v2
from resource_management.libraries.functions import format, get_stack_version, safe_repr
from resource_management.libraries.functions.ranger_functions import Rangeradmin
from resource_management.libraries.functions.ranger_functions_v2 import RangeradminV2
from resource_management.core.resources import File, Execute, Directory, InlineTemplate
from resource_management.core.source import DownloadSource, Template
from resource_management.core.properties import PropertiesFile
from resource_management.core.logger import Logger
from resource_management.core.exceptions import Fail, ExecutionFailed
from resource_management.libraries.resources import ModifyPropertiesFile
from resource_management.libraries.script.script import Script
from resource_management.libraries.functions.crypto import save_ks_file
from resource_management.libraries.functions.network import wait_for_url_availability
from cloud_commons import os_utils, security_utils

__all__ = ["setup_ranger_plugin", "RollingRestartHandler", "validate_ranger_configuration"]

# Ranger 仓库状�?REPO_STATUS = ["INSTALLED", "CONFIGURING", "ACTIVE", "ERROR"]
PLUGIN_API_TIMEOUT = 300  # 插件API超时(�?
CONNECTION_RETRIES = 5
RETRY_DELAY = 10

# Ranger服务类型映射
SERVICE_TYPES = {
    "hdfs": "hadoop",
    "yarn": "yarn",
    "hbase": "hbase",
    "hive": "hive",
    "kafka": "kafka",
    "knox": "knox",
    "solr": "solr",
    "atlas": "atlas",
    "storm": "storm",
    "nifi": "nifi",
    "nifiregistry": "nifiregistry"
}

class RollingRestartHandler:
    """滚动重启管理�?""
    
    def __init__(self, service_name, timestamp_file):
        self.service_name = service_name
        self.timestamp_file = timestamp_file
        
    def requires_restart(self):
        """检查是否需要重启服�?""
        if not os.path.exists(self.timestamp_file):
            return True
            
        with open(self.timestamp_file, 'r') as f:
            last_setup = datetime.datetime.fromisoformat(f.read().strip())
            
        return (datetime.datetime.now() - last_setup) > datetime.timedelta(hours=24)
        
    def mark_completed(self):
        """标记配置完成时间"""
        os.makedirs(os.path.dirname(self.timestamp_file), exist_ok=True)
        with open(self.timestamp_file, 'w') as f:
            f.write(datetime.datetime.now().isoformat())
            
    def perform_rolling_restart(self):
        """执行滚动重启（需在服务脚本中实现�?""
        Logger.info(f"配置变更需�?{self.service_name} 服务重启")

class RangerPluginManager:
    """Ranger 插件生命周期管理�?""
    
    def __init__(self, component_name, service_name):
        self.component_name = component_name
        self.service_name = service_name
        self.stack_root = Script.get_stack_root()
        self.stack_version = get_stack_version(component_name)
        self.plugin_dir = Path(self.stack_root) / self.stack_version / f"ranger-{service_name}-plugin"
        self.install_properties_path = self.plugin_dir / "install.properties"
        self.rolling_handler = RollingRestartHandler(
            service_name, 
            f"/tmp/.last_ranger_setup_{service_name}.timestamp"
        )
        
    def install_jdbc_driver(self, driver_meta):
        """安装和更新自定义JDBC驱动"""
        try:
            # 参数解包
            source_url = driver_meta.get("source_url")
            old_driver_path = driver_meta.get("old_driver_path")
            download_target = driver_meta.get("download_target")
            final_target = driver_meta.get("final_target")
            
            if not source_url or source_url.endswith("/None"):
                Logger.info("跳过JDBC安装: 未提供有效URL")
                return
            
            # 移除旧的JDBC驱动
            if old_driver_path and os.path.exists(old_driver_path):
                Logger.info(f"移除旧的JDBC驱动: {old_driver_path}")
                File(old_driver_path, action="delete")
            
            # 下载新驱�?            Logger.info(f"下载JDBC驱动: {source_url} -> {download_target}")
            File(
                download_target,
                content=DownloadSource(source_url, execution_timeout=300),
                mode=0o644,
            )
            
            # 备份现有驱动
            if os.path.exists(final_target):
                backup_path = f"{final_target}.bak.{int(time.time())}"
                shutil.copy2(final_target, backup_path)
                Logger.info(f"备份当前驱动�? {backup_path}")
            
            # 部署新驱�?            Logger.info(f"部署JDBC驱动�? {final_target}")
            os_utils.copy_with_perms(
                download_target,
                final_target,
                owner_name=driver_meta.get("owner", "root"),
                group_name=driver_meta.get("group", "root"),
                mode=0o644
            )
            
            # 验证驱动程序
            if not os.path.exists(final_target) or os.path.getsize(final_target) == 0:
                raise Fail("JDBC驱动部署失败: 目标文件缺失或为�?)
            
        except Exception as e:
            Logger.error(f"JDBC驱动安装失败: {safe_repr(e)}")
            raise
        
    def configure_plugin(self, plugin_params):
        """配置插件安装属性文�?""
        # 验证属性文件是否存�?        if not self.install_properties_path.exists():
            raise Fail(f"Ranger插件安装文件不存�? {self.install_properties_path}")
        
        # 准备标准属性及元数�?        plugin_properties = {
            "POLICY_MGR_URL": plugin_params["policymgr_mgr_url"].rstrip("/"),
            "REPOSITORY_NAME": plugin_params["repo_name"],
            "XAAUDIT.DESTINATION.HDFS.IS_ENABLED": "true",
            "XAAUDIT.SUMMARY.ENABLED": "true",
            "CUSTOM_USER": plugin_params["component_user"],
            "CUSTOM_GROUP": plugin_params["component_group"]
        }
        
        # 合并用户自定义属�?        if plugin_params.get("plugin_properties"):
            plugin_properties.update(plugin_params["plugin_properties"])
        
        # 添加特殊组件特定配置
        self._add_service_specific_config(plugin_properties, plugin_params)
        
        Logger.info(f"更新Ranger插件配置: {self.install_properties_path}")
        Logger.debug(f"插件属�? {plugin_properties}")
        
        # 使用属性文件工具进行配�?        try:
            with PropertiesFile(self.install_properties_path) as props:
                for key, value in plugin_properties.items():
                    props[key] = value
        except Exception as e:
            Logger.error(f"修改安装属性失�? {safe_repr(e)}")
            raise Fail("无法更新插件配置文件")
        
    def _add_service_specific_config(self, props, params):
        """添加特定于服务的配置�?""
        svc_type = SERVICE_TYPES.get(self.service_name, self.service_name.lower())
        
        # 基础服务配置
        props.update({
            "RANGER_SERVICE_TYPE": svc_type,
            "COMPONENT_INSTALL_DIR": params.get("component_home", ""),
            "SQL_CONNECTOR_JAR": params.get("driver_curl_target", "")
        })
        
        # SSL相关配置
        if params.get("ssl_enabled", False):
            self._configure_ssl_options(props, params)
            
        # HDFS审计路径配置
        if self.service_name.lower() == "hdfs":
            props["XAAUDIT.DESTINATION.HDFS.HDFS_DIR"] = params.get(
                "hdfs_audit_dir", 
                "hdfs:///ranger/audit"
            )
            
    def _configure_ssl_options(self, props, params):
        """配置SSL相关选项"""
        props.update({
            "SSL_KEYSTORE_FILE_PATH": params["ssl_keystore_path"],
            "SSL_TRUSTSTORE_FILE_PATH": params["ssl_truststore_path"],
            "SSL_KEYSTORE_PASSWORD": security_utils.decrypt_password(params["ssl_keystore_password"]),
            "SSL_TRUSTSTORE_PASSWORD": security_utils.decrypt_password(params["ssl_truststore_password"])
        })
        
        # 如果启双向SSL验证
        if params.get("client_authentication_required", False):
            props["SSL_CLIENT_AUTH"] = "true"
            
    def manage_plugin_state(self, admin_params, plugin_enabled):
        """管理插件状态（启用/禁用�?""
        # 创建Ranger仓库（仅当启用插件时�?        if plugin_enabled:
            self.create_ranger_repository(admin_params)
        
        # 执行插件状态管理脚�?        action = "enable" if plugin_enabled else "disable"
        script_name = f"{action}-{self.service_name}-plugin.sh"
        
        Logger.info(f"执行 Ranger 插件操作: {action.upper()}")
        
        # 准备执行环境
        exec_env = {
            "JAVA_HOME": admin_params["java_home"],
            "PWD": str(self.plugin_dir),
            "PATH": f"{os.environ.get('PATH', '')}:{self.plugin_dir}",
            "RANGER_COMPONENT": self.service_name.upper()
        }
        
        # 执行插件管理脚本
        try:
            Execute(
                (script_name,),
                environment=exec_env,
                cwd=str(self.plugin_dir),
                logoutput=True,
                sudo=True,
                timeout=PLUGIN_API_TIMEOUT
            )
            
            # 标记滚动重启需求（仅在启用或配置变更时�?            if plugin_enabled:
                self.rolling_handler.mark_completed()
                
        except ExecutionFailed as e:
            Logger.error(f"插件{action}脚本执行失败: {safe_repr(e)}")
            if plugin_enabled:
                raise Fail("插件启用失败，检查Ranger服务状�?)
            
    def create_ranger_repository(self, admin_params):
        """创建/更新Ranger仓库服务"""
        # 创建API客户�?        if admin_params.get("api_version") == "v2":
            ranger_client = RangeradminV2(
                url=admin_params["policymgr_mgr_url"],
                skip_if_rangeradmin_down=admin_params["skip_if_rangeradmin_down"]
            )
        else:
            ranger_client = Rangeradmin(
                url=admin_params["policymgr_mgr_url"],
                skip_if_rangeradmin_down=admin_params["skip_if_rangeradmin_down"]
            )
        
        # 等待Ranger服务可用
        self._wait_for_ranger_service(admin_params["policymgr_mgr_url"])
        
        # 配置仓库参数
        repo_config = admin_params["plugin_repo_dict"].copy()
        repo_config["username"] = admin_params.get(
            "ranger_admin_username", 
            admin_params["admin_username"]
        )
        repo_config["password"] = admin_params.get(
            "ranger_admin_password",
            admin_params["admin_password"]
        )
        
        # 创建或更新仓�?        Logger.info(f"在Ranger中配置{self.service_name}仓库: {admin_params['repo_name']}")
        
        try:
            result = ranger_client.create_ranger_repository(
                self.service_name,
                admin_params["repo_name"],
                repo_config,
                admin_params["admin_username"],
                admin_params["admin_password"],
                admin_params["policy_user"]
            )
            
            if result and result.get("success") is not True:
                raise Fail(f"仓库创建失败: {result.get('message')}")
                
        except Exception as e:
            Logger.error(f"Ranger仓库配置失败: {safe_repr(e)}")
            if not admin_params["skip_if_rangeradmin_down"]:
                raise Fail(f"无法创建Ranger仓库: {e}")
                
    def _wait_for_ranger_service(self, ranger_url):
        """等待Ranger管理服务可用"""
        test_url = ranger_url.rstrip("/") + "/public/api/js/session.js"
        wait_for_url_availability(
            test_url,
            "Ranger Admin",
            timeout_seconds=PLUGIN_API_TIMEOUT,
            retry_interval=5,
            skip_on_failure=True
        )
            
    def generate_ssl_certificates(self, ssl_config):
        """生成SSL证书（如果需要）"""
        # 仅当提供证书配置时执�?        if not isinstance(ssl_config, dict) or not ssl_config.get("generate_certs", False):
            return
            
        Logger.info("为Ranger集成生成自签名证�?)
        
        key_path = ssl_config.get("key_path", "/etc/security/server.key")
        cert_path = ssl_config.get("cert_path", "/etc/security/server.cert")
        
        # 证书生成命令
        cert_cmd = (
            "openssl req -x509 -newkey rsa:4096 -nodes "
            f"-keyout {key_path} -out {cert_path} -days 3650 "
            f"-subj '/C={ssl_config.get('country', 'US')}/"
            f"ST={ssl_config.get('state', 'CA')}/"
            f"L={ssl_config.get('locality', 'Sunnyvale')}/"
            f"O={ssl_config.get('org', 'cloud')}/CN={ssl_config.get('hostname', 'localhost')}'"
        )
        
        # 生成证书
        Execute(cert_cmd, logoutput=True, sudo=True)
        
        # 创建Java key store
        if ssl_config.get("create_keystore", True):
            self._create_keystore(key_path, cert_path, ssl_config)
            
    def _create_keystore(self, key_path, cert_path, ssl_config):
        """创建Java KeyStore文件"""
        keystore_path = ssl_config["keystore_path"]
        keystore_pass = ssl_config["keystore_password"]
        
        Logger.info(f"创建Java Keystore: {keystore_path}")
        
        # 将私钥和证书导入PKCS12
        pkcs12_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".p12")
        pkcs12_cmd = (
            f"openssl pkcs12 -export -in {cert_path} -inkey {key_path} "
            f"-out {pkcs12_temp.name} -name 'ranger-tls' "
            f"-password pass:'{keystore_pass}'"
        )
        Execute(pkcs12_cmd, logoutput=True, sudo=True)
        
        # 转换为JKS格式
        save_ks_file(
            keystore_path,
            keystore_pass,
            pkcs12_temp.name,
            "pkcs12",
            "jks",
            "ranger-tls"
        )

def setup_ranger_plugin(
    component_select_name,
    service_name,
    driver_meta=None,
    plugin_params=None,
    admin_params=None,
    ssl_config=None
):
    """
    Ranger插件集成接口
    
    :param component_select_name: 组件选择名称（用于栈版本�?    :param service_name: 服务名称（hdfs, yarn等）
    :param driver_meta: JDBC驱动元数据字典（可选）
        - old_driver_path: 旧驱动路�?        - source_url: 下载URL
        - download_target: 下载临时位置
        - final_target: 驱动安装位置
        - owner: 文件所有者（默认root�?        - group: 文件组（默认root�?    :param plugin_params: 插件配置字典
        - component_user: 组件系统用户
        - component_group: 组件系统�?        - policymgr_mgr_url: Ranger管理器URL
        - repo_name: Ranger仓库名称
        - plugin_properties: 额外插件属性（可选）
        - plugin_enabled: 是否启用插件
    :param admin_params: Ranger管理员配�?        - java_home: JAVA_HOME路径
        - ranger_env_properties: Ranger环境属�?            - ranger_admin_username
            - ranger_admin_password
            - admin_username
            - admin_password
        - policy_user: 策略用户�?        - plugin_repo_dict: 仓库配置字典
        - api_version: API版本 (v1/v2)
        - skip_if_rangeradmin_down: Ranger管理员挂起时是否跳过
    :param ssl_config: SSL配置字典（可选）
        - enabled: 是否启用SSL
        - generate_certs: 是否生成自签名证�?        - keystore_path: KeyStore路径
        - truststore_path: TrustStore路径
        - keystore_password: KeyStore密码
        - truststore_password: TrustStore密码
    """
    # 参数合规性校�?    _validate_required_params(service_name, plugin_params, admin_params)
    
    # 初始化管理器
    manager = RangerPluginManager(component_select_name, service_name)
    
    # 生成SSL证书（如果需要）
    manager.generate_ssl_certificates(ssl_config or {})
    
    # 安装/更新JDBC驱动
    if driver_meta:
        manager.install_jdbc_driver(driver_meta)
    
    # 配置插件文件
    manager.configure_plugin(_merge_params(plugin_params, admin_params, ssl_config))
    
    # 管理插件状�?    manager.manage_plugin_state(
        admin_params=_merge_params(plugin_params, admin_params, ssl_config), 
        plugin_enabled=plugin_params["plugin_enabled"]
    )
    
    # 提示后续操作
    if plugin_params["plugin_enabled"]:
        manager.rolling_handler.perform_rolling_restart()

def validate_ranger_configuration(service_name, conf_dir, required_keys):
    """
    验证Ranger集成所需配置项是否存�?    
    :param service_name: 服务名称（例如：hive�?    :param conf_dir: 配置目录路径
    :param required_keys: 必须存在的配置项列表
    :return: 缺失的配置项列表
    """
    config_file = os.path.join(conf_dir, f"ranger-{service_name}-security.xml")
    missing_props = []
    
    if not os.path.exists(config_file):
        return [f"配置文件缺失: {config_file}"]
    
    try:
        tree = ET.parse(config_file)
        root = tree.getroot()
        
        for key in required_keys:
            prop = root.find(f".//property[name='{key}']/value")
            if prop is None or not prop.text.strip():
                missing_props.append(key)
                
    except Exception as e:
        Logger.error(f"解析Ranger配置失败: {safe_repr(e)}")
        return [f"配置解析错误: {config_file}"]
    
    return missing_props

def _validate_required_params(service_name, plugin_params, admin_params):
    """验证必要参数是否存在"""
    required_plugin = [
        "component_user", "component_group", 
        "policymgr_mgr_url", "repo_name", "plugin_enabled"
    ]
    
    required_admin = [
        "java_home", "ranger_env_properties", 
        "policy_user", "plugin_repo_dict"
    ]
    
    missing_plugin = [p for p in required_plugin if p not in plugin_params]
    missing_admin = [p for p in required_admin if p not in admin_params]
    
    if missing_plugin or missing_admin:
        msg = "缺少必要参数:"
        if missing_plugin:
            msg += f"\n插件配置: {', '.join(missing_plugin)}"
        if missing_admin:
            msg += f"\n管理员配�? {', '.join(missing_admin)}"
        raise Fail(msg)

def _merge_params(plugin_params, admin_params, ssl_config):
    """合并多层参数为单层字�?""
    merged = {}
    merged.update(plugin_params)
    merged.update(admin_params)
    
    # 合并Ranger管理员凭�?    if "ranger_env_properties" in admin_params:
        merged.update(admin_params["ranger_env_properties"])
    
    # 合并SSL配置
    if isinstance(ssl_config, dict):
        merged.update(ssl_config)
    
    return merged
