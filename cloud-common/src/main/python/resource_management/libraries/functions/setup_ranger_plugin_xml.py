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

Advanced Ranger Plugin Management System
"""

import os
import shutil
import socket
import rapidjson as json
import datetime
import hashlib
from cryptography.fernet import Fernet
from typing import Dict, List, Tuple, Optional

from resource_management.libraries.functions.ranger_functions import RangerAdmin
from resource_management.core.resources import File, Directory, Execute, Service
from resource_management.libraries.resources.xml_config import XmlConfig
from resource_management.libraries.functions import format
from resource_management.libraries.functions.get_stack_version import get_stack_version
from resource_management.core.logger import Logger
from resource_management.core.source import DownloadSource, InlineTemplate
from resource_management.libraries.functions.ranger_functions_v2 import RangerAdminV2
from resource_management.core.utils import PasswordString
from resource_management.libraries.script.script import Script
from resource_management.libraries.functions.default import default
from resource_management.libraries.functions.security_commons import (
    secure_filesystem,
    generate_secure_password,
    encrypt_password,
    store_secrets
)
from resource_management.libraries.functions.ssl_context import SSLContextManager

# 全局常量
RANGER_JAR_SYMLINK_SKIP_PATTERNS = [
    ".*-cloud.*",
    ".*-plugin-common.*",
    ".*-plugin-service.*",
    ".*-hdfs-plugin-impl.*"
]
MAX_AUDIT_ROLLOVER_DAYS = 30
RANGER_CONF_ROOT = "/etc/ranger"
POLICY_CACHE_PATH = f"{RANGER_CONF_ROOT}/{{repo}}/policycache"
CREDENTIAL_FILE_PERMISSIONS = 0o640

# 审计类型映射
AUDIT_TO_DB_FLAVOR_MAP = {
    'mysql': {
        'driver': 'com.mysql.jdbc.Driver',
        'url_template': 'jdbc:mysql://{host}/{db}',
        'jdbc_jar': 'mysql-connector-java.jar'
    },
    'oracle': {
        'driver': 'oracle.jdbc.OracleDriver',
        'url_template': 'jdbc:oracle:thin:@{host}',
        'jdbc_jar': 'ojdbc8.jar'
    },
    'postgres': {
        'driver': 'org.postgresql.Driver',
        'url_template': 'jdbc:postgresql://{host}/{db}',
        'jdbc_jar': 'postgresql-connector-java.jar'
    },
    'mssql': {
        'driver': 'com.microsoft.sqlserver.jdbc.SQLServerDriver',
        'url_template': 'jdbc:sqlserver://{host};databaseName={db}',
        'jdbc_jar': 'mssql-jdbc.jar'
    },
    'sqla': {
        'driver': 'sap.jdbc4.sqlanywhere.IDriver',
        'url_template': 'jdbc:sqlanywhere:database={db};host={host}',
        'jdbc_jar': 'sqlanywhere-jdbc.jar'
    }
}

def setup_ranger_plugin(
    component_select_name: str,
    service_name: str,
    previous_jdbc_jar: Optional[str],
    component_downloaded_custom_connector: str,
    component_driver_curl_source: str,
    component_driver_curl_target: str,
    java_home: str,
    repo_name: str,
    plugin_repo_dict: Dict,
    ranger_env_properties: Dict,
    plugin_properties: Dict,
    policy_user: str,
    policymgr_mgr_url: str,
    plugin_enabled: bool,
    conf_dict: Dict,
    component_user: str,
    component_group: str,
    cache_service_list: List[str],
    plugin_audit_properties: Dict,
    plugin_audit_attributes: Dict,
    plugin_security_properties: Dict,
    plugin_security_attributes: Dict,
    plugin_policymgr_ssl_properties: Dict,
    plugin_policymgr_ssl_attributes: Dict,
    component_list: List[str],
    audit_db_is_enabled: bool,
    credential_file: str,
    xa_audit_db_password: Optional[str],
    ssl_truststore_password: str,
    ssl_keystore_password: str,
    api_version: str = None,
    stack_version_override: str = None,
    skip_if_rangeradmin_down: bool = True,
    is_security_enabled: bool = False,
    is_stack_supports_ranger_kerberos: bool = False,
    component_user_principal: Optional[str] = None,
    component_user_keytab: Optional[str] = None,
    cred_lib_path_override: Optional[str] = None,
    cred_setup_prefix_override: Optional[str] = None,
    plugin_home: Optional[str] = None
) -> None:
    """
    高级 Ranger 插件安装配置
    
    参数:
    component_select_name: 组件选择名称
    service_name: 服务名称 (HDFS, Hive�?
    previous_jdbc_jar: 旧JDBC驱动路径（可安全删除�?    component_downloaded_custom_connector: 下载的自定义连接器路�?    component_driver_curl_source: JDBC驱动下载URL
    component_driver_curl_target: JDBC驱动安装目标路径
    java_home: Java安装目录
    repo_name: Ranger仓库名称
    plugin_repo_dict: Ranger仓库配置字典
    ranger_env_properties: Ranger环境属�?    plugin_properties: 插件属�?    policy_user: 策略管理用户
    policymgr_mgr_url: Ranger策略管理器URL
    plugin_enabled: 插件是否启用
    conf_dict: 配置字典
    component_user: 组件运行用户
    component_group: 组件运行�?    cache_service_list: 缓存服务列表
    plugin_audit_properties: 审计属�?    plugin_audit_attributes: 审计配置属�?    plugin_security_properties: 安全属�?    plugin_security_attributes: 安全配置属�?    plugin_policymgr_ssl_properties: SSL属�?    plugin_policymgr_ssl_attributes: SSL配置属�?    component_list: 组件列表
    audit_db_is_enabled: 审计数据库是否启�?    credential_file: 凭证文件路径
    xa_audit_db_password: 审计数据库密�?    ssl_truststore_password: SSL信任库密�?    ssl_keystore_password: SSL密钥库密�?    api_version: Ranger API版本
    stack_version_override: Stack版本覆盖
    skip_if_rangeradmin_down: Ranger Admin不可用时是否跳过
    is_security_enabled: 是否启用Kerberos安全
    is_stack_supports_ranger_kerberos: 是否支持Kerberos
    component_user_principal: 组件Kerberos主体
    component_user_keytab: 组件Keytab文件
    cred_lib_path_override: 凭证库路径覆�?    cred_setup_prefix_override: 凭证设置命令覆盖
    plugin_home: 插件主目�?    """
    # 初始化插件基础配置
    stack_root = Script.get_stack_root()
    service_name_lower = service_name.lower()
    plugin_home = plugin_home or format(f"{stack_root}/{stack_version}/ranger-{service_name_lower}-plugin/")
    
    try:
        # 设置审计数据库连接器
        if audit_db_is_enabled and component_driver_curl_source:
            config_db_connector(
                previous_jdbc_jar, 
                component_downloaded_custom_connector,
                component_driver_curl_source,
                component_driver_curl_target
            )

        # 清理策略管理器URL
        if policymgr_mgr_url.endswith("/"):
            policymgr_mgr_url = policymgr_mgr_url.rstrip("/")

        # 获取Stack版本
        stack_version = stack_version_override or get_stack_version(component_select_name)
        
        # 如果插件启用，进行完整配�?        if plugin_enabled:
            # 管理Ranger仓库
            manage_ranger_repository(
                service_name_lower,
                repo_name,
                cache_service_list,
                policymgr_mgr_url,
                plugin_repo_dict,
                ranger_env_properties,
                policy_user,
                is_security_enabled,
                is_stack_supports_ranger_kerberos,
                component_user,
                component_user_principal,
                component_user_keytab,
                api_version,
                skip_if_rangeradmin_down
            )

            # 创建安全配置文件
            create_security_config(
                service_name_lower,
                repo_name,
                component_conf_dir=conf_dict,
                component_user=component_user,
                component_group=component_group
            )

            # 创建配置目录结构
            create_config_directories(repo_name, component_user, component_group)

            # 清理过期策略缓存
            clean_old_policy_cache(repo_name, MAX_AUDIT_ROLLOVER_DAYS)

            # 设置XML配置文件
            configure_plugin_files(
                service_name_lower,
                repo_name,
                conf_dict,
                component_user,
                component_group,
                plugin_audit_properties,
                plugin_audit_attributes,
                plugin_security_properties,
                plugin_security_attributes,
                plugin_policymgr_ssl_properties,
                plugin_policymgr_ssl_attributes,
                component_list
            )

            # 设置凭证�?            setup_ranger_plugin_keystore(
                service_name_lower,
                audit_db_is_enabled,
                stack_version,
                credential_file,
                xa_audit_db_password,
                ssl_truststore_password,
                ssl_keystore_password,
                component_user,
                component_group,
                java_home,
                cred_lib_path_override,
                cred_setup_prefix_override,
                plugin_home
            )

            # 设置JAR符号链接
            setup_ranger_plugin_jar_symblink(
                stack_version,
                service_name_lower,
                component_list
            )
        else:
            # 禁用插件时删除配置文�?            disable_ranger_plugin(service_name_lower, conf_dict)
            
        Logger.info(f"Ranger插件配置完成: {service_name_lower}")
    except Exception as e:
        Logger.error(f"配置Ranger插件时发生错�? {str(e)}")
        raise Fail(f"无法配置Ranger插件: {str(e)}")


def config_db_connector(
    old_jar_path: Optional[str],
    downloaded_path: str,
    download_url: str,
    target_path: str
) -> None:
    """安全配置数据库连接器"""
    # 安全删除旧驱�?    if old_jar_path and os.path.isfile(old_jar_path):
        File(old_jar_path, action="delete", log_output=True)

    # 下载新驱�?    File(
        downloaded_path,
        content=DownloadSource(download_url),
        mode=0o644
    )

    # 安全替换驱动文件
    Execute(
        ("cp", "--remove-destination", downloaded_path, target_path),
        path=["/bin", "/usr/bin"],
        sudo=True,
        log_output=True
    )
    
    # 设置安全权限
    File(target_path, mode=0o644, log_output=True)
    Logger.info(f"JDBC驱动更新完成: {download_url} -> {target_path}")


def manage_ranger_repository(
    service_name: str,
    repo_name: str,
    cache_service_list: List[str],
    policymgr_url: str,
    repo_dict: Dict,
    ranger_env: Dict,
    policy_user: str,
    is_secured: bool = False,
    supports_kerberos: bool = False,
    service_user: str = "",
    service_principal: Optional[str] = None,
    service_keytab: Optional[str] = None,
    api_version: str = "v1",
    skip_on_failure: bool = True
) -> None:
    """管理Ranger仓库"""
    service_name_exist = get_policycache_service_name(
        service_name, repo_name, cache_service_list
    )

    # 缓存存在则跳过创�?    if service_name_exist:
        Logger.info(f"Ranger仓库已存�? {repo_name}")
        return

    # 选择API版本
    if api_version == "v2":
        ranger_api = RangerAdminV2(
            url=policymgr_url,
            skip_if_rangeradmin_down=skip_on_failure
        )
    else:
        ranger_api = RangerAdmin(
            url=policymgr_url,
            skip_if_rangeradmin_down=skip_on_failure
        )

    # 准备API凭证
    credentials = {
        'admin_user': ranger_env["ranger_admin_username"],
        'admin_password': PasswordString(ranger_env["ranger_admin_password"]),
        'policy_user': policy_user
    }

    # Kerberos环境特殊处理
    if is_secured and supports_kerberos and service_principal and service_keytab:
        krb_creds = {
            'auth_provider': 'kerberos',
            'principal': service_principal,
            'keytab': service_keytab
        }
        credentials.update(krb_creds)

    # 创建或更新仓�?    ranger_api.create_ranger_repository(
        service_type=service_name,
        repo_name=repo_name,
        repo_dict=repo_dict,
        **credentials
    )
    Logger.info(f"成功创建Ranger仓库: {repo_name}")


def create_security_config(
    service_name: str,
    repo_name: str,
    component_conf_dir: str,
    component_user: str,
    component_group: str
) -> None:
    """创建基本安全配置文件"""
    security_file_path = format(f"{component_conf_dir}/ranger-security.xml")
    creation_time = datetime.datetime.now().isoformat()

    File(
        security_file_path,
        owner=component_user,
        group=component_group,
        mode=0o644,
        content=InlineTemplate(format(
            "<ranger>\n<enabled>{creation_time}</enabled>\n</ranger>"
        )),
        log_output=True
    )
    Logger.info(f"安全配置文件创建完成: {security_file_path}")


def create_config_directories(repo_name: str, owner: str, group: str) -> None:
    """创建配置目录结构"""
    ranger_repo_path = os.path.join(RANGER_CONF_ROOT, repo_name)
    policy_cache_path = os.path.join(ranger_repo_path, "policycache")
    
    directories = [
        ranger_repo_path,
        policy_cache_path
    ]

    for dir_path in directories:
        Directory(
            dir_path,
            owner=owner,
            group=group,
            mode=0o775,
            create_parents=True,
            cd_access="a",
            log_output=True
        )
    
    Logger.info(f"配置文件目录创建完成: {repo_name}")


def clean_old_policy_cache(repo_name: str, max_age_days: int = 30) -> None:
    """清理过期策略缓存"""
    try:
        cache_dir = POLICY_CACHE_PATH.replace("{repo}", repo_name)
        cut_off_time = datetime.datetime.now() - datetime.timedelta(days=max_age_days)

        if not os.path.exists(cache_dir):
            Logger.debug(f"策略缓存目录不存�? {cache_dir}")
            return
            
        for cache_file in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, cache_file)
            if not file_path.endswith(".json"):
                continue
                
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mtime < cut_off_time:
                File(file_path, action="delete", log_output=True)
                Logger.info(f"删除过期策略缓存: {cache_file}")
                
    except Exception as e:
        Logger.warning(f"清理策略缓存失败: {str(e)}")


def configure_plugin_files(
    service_name: str,
    repo_name: str,
    conf_dir: str,
    owner: str,
    group: str,
    audit_props: Dict,
    audit_attrs: Dict,
    security_props: Dict,
    security_attrs: Dict,
    ssl_props: Dict,
    ssl_attrs: Dict,
    component_list: List[str]
) -> None:
    """
    配置插件相关XML文件
    """
    # 配置文件路径
    audit_file = format(f"ranger-{service_name}-audit.xml")
    security_file = format(f"ranger-{service_name}-security.xml")
    ssl_file = "ranger-policymgr-ssl-yarn.xml" if service_name == "yarn" else "ranger-policymgr-ssl.xml"

    # 敏感属性过�?    sensitive_props = [
        "xasecure.audit.destination.db.password",
        "xasecure.policymgr.clientssl.keystore.password",
        "xasecure.policymgr.clientssl.truststore.password"
    ]
    
    # 配置文件生成逻辑
    plugins = [
        {
            "file_name": audit_file,
            "properties": {k: ("crypted" if k in sensitive_props else v) for k, v in audit_props.items()},
            "attributes": audit_attrs
        },
        {
            "file_name": security_file,
            "properties": security_props,
            "attributes": security_attrs
        },
        {
            "file_name": ssl_file,
            "properties": {k: ("crypted" if k in sensitive_props else v) for k, v in ssl_props.items()},
            "attributes": ssl_attrs
        }
    ]

    # 创建XML配置文件
    for plugin in plugins:
        XmlConfig(
            plugin["file_name"],
            conf_dir=conf_dir,
            configurations=plugin["properties"],
            configuration_attributes=plugin["attributes"],
            owner=owner,
            group=group,
            mode=0o744,
            log_output=True
        )

    # 创建组件策略缓存
    for cache_service in component_list:
        cache_file = format(f"{POLICY_CACHE_PATH}/{cache_service}_{repo_name}.json")
        File(
            cache_file,
            owner=owner,
            group=group,
            mode=0o644,
            log_output=True
        )
    
    Logger.info(f"{service_name} Ranger配置文件更新完成")


def setup_ranger_plugin_keystore(
    service_name: str,
    audit_db_enabled: bool,
    stack_version: str,
    credential_file: str,
    audit_db_password: str,
    truststore_password: str,
    keystore_password: str,
    owner: str,
    group: str,
    java_home: str,
    lib_path: Optional[str] = None,
    install_prefix: Optional[str] = None,
    plugin_home: Optional[str] = None
) -> None:
    """安全设置凭证文件"""
    try:
        # 1. 创建凭证文件（如果不存在�?        if not os.path.exists(credential_file):
            File(
                credential_file,
                owner=owner,
                group=group,
                mode=CREDENTIAL_FILE_PERMISSIONS,
                log_output=True
            )

        # 2. 设置凭证文件内容
        credentials = {}
        if audit_db_enabled and audit_db_password:
            credentials['auditDBCred'] = PasswordString(audit_db_password)

        if truststore_password:
            credentials['sslTrustStore'] = PasswordString(truststore_password)

        if keystore_password:
            credentials['sslKeyStore'] = PasswordString(keystore_password)

        # 3. 使用Ranger凭证助手或直接写入凭�?        if plugin_home and install_prefix:
            # 使用官方凭证助手存储凭证
            set_credentials_via_helper(
                credentials,
                credential_file,
                plugin_home,
                lib_path,
                install_prefix,
                java_home
            )
        else:
            # 直接存储凭证（不推荐�?            store_credentials_directly(credentials, credential_file)

        # 4. 权限设置
        File(
            credential_file,
            owner=owner,
            group=group,
            mode=CREDENTIAL_FILE_PERMISSIONS,
            log_output=True
        )

        # 5. CRC文件权限修复
        crc_file = f"{credential_file}.crc"
        if os.path.exists(crc_file):
            File(
                crc_file,
                owner=owner,
                group=group,
                mode=CREDENTIAL_FILE_PERMISSIONS,
                log_output=True
            )

        Logger.info(f"{service_name}凭证文件配置完成: {credential_file}")
    except Exception as e:
        Logger.error(f"更新凭证文件失败: {str(e)}")
        raise Fail(f"凭证文件设置错误: {str(e)}")


def set_credentials_via_helper(
    credentials: Dict,
    target_file: str,
    plugin_home: str,
    lib_path: Optional[str],
    install_prefix: Optional[str],
    java_home: str
) -> None:
    """使用官方凭证助手API设置凭证"""
    cred_lib_path = lib_path or os.path.join(plugin_home, "install", "lib", "*")
    cred_prefix = install_prefix or ["ranger_credential_helper.py", "-l", cred_lib_path]

    # 为每个凭证执行存储命�?    for key, value in credentials.items():
        cred_cmd = cred_prefix + [
            "-f", target_file,
            "-k", key,
            "-v", value.value if hasattr(value, 'value') else str(value),
            "-c", "1"
        ]
        Execute(
            cred_cmd,
            environment={"JAVA_HOME": java_home},
            logoutput=True,
            sudo=True
        )


def store_credentials_directly(credentials: Dict, target_file: str) -> None:
    """直接存储凭证（替代方案）"""
    with open(target_file, 'wb') as f:
        encrypted_data = {}
        key = Fernet.generate_key()
        for k, v in credentials.items():
            encrypted_data[k] = encrypt_password(v.value if hasattr(v, 'value') else str(v), key)
        json.dump(encrypted_data, f)
    
    # 安全存储密钥
    key_file = f"{target_file}.key"
    with open(key_file, 'wb') as kf:
        kf.write(key)
    
    # 权限加固
    File(target_file, mode=0o400)
    File(key_file, mode=0o400)
    Logger.warning("使用备用方法直接存储凭证（安全风险较高）")


def setup_ranger_plugin_jar_symblink(
    stack_version: str,
    service_name: str,
    component_list: List[str]
) -> None:
    """安全创建Ranger插件JAR符号链接"""
    stack_root = Script.get_stack_root()
    jar_dir = format(f"{stack_root}/{stack_version}/ranger-{service_name}-plugin/lib/")
    
    # 验证插件目录
    if not os.path.exists(jar_dir):
        Logger.error(f"Ranger插件目录不存�? {jar_dir}")
        return
        
    # 遍历JAR文件
    for jar_file in os.listdir(jar_dir):
        jar_path = os.path.join(jar_dir, jar_file)
        
        # 跳过非核心JAR
        if any(re.match(pattern, jar_file) for pattern in RANGER_JAR_SYMLINK_SKIP_PATTERNS):
            continue
            
        # 为每个组件创建符号链�?        for component in component_list:
            if not should_create_link(component, jar_file):
                continue
                
            target_path = format(f"{stack_root}/current/{component}/lib/{jar_file}")
            Execute(
                ("ln", "-sf", jar_path, target_path),
                not_if=format(f"test -f {target_path}"),
                only_if=format(f"test -f {jar_path}"),
                sudo=True,
                log_output=True
            )
            Logger.debug(f"创建符号链接: {jar_file} -> {target_path}")


def should_create_link(component: str, jar_file: str) -> bool:
    """检查是否应为特定组件创建链�?""
    # 跳过特定组件或文件名模式
    if "plugin" in jar_file and "common" not in jar_file:
        return component in jar_file
    return True


def disable_ranger_plugin(service_name: str, conf_dir: str) -> None:
    """禁用Ranger插件"""
    security_file = format(f"{conf_dir}/ranger-security.xml")
    File(security_file, action="delete", log_output=True)
    Logger.info(f"{service_name} Ranger插件已禁�?)


def get_audit_configs(config: Dict) -> Tuple[Optional[str], Optional[str], str, str]:
    """
    获取审计数据库配置信�?    
    返回元组:
    (jdbc_jar_name, previous_jdbc_jar_name, audit_jdbc_url, jdbc_driver)
    """
    # 提取基础配置
    db_flavor = config["configurations"]["admin-properties"]["DB_FLAVOR"].lower()
    db_host = config["configurations"]["admin-properties"]["db_host"]
    audit_db = default("/configurations/admin-properties/audit_db_name", "ranger_audits")
    
    # 获取数据库类型配置模�?    db_config = AUDIT_TO_DB_FLAVOR_MAP.get(db_flavor)
    if not db_config:
        raise Fail(f"不支持的数据库类�? {db_flavor}")

    # 获取JDBC驱动名称
    jdbc_key = f"custom_{db_flavor}_jdbc_name"
    prev_jdbc_key = f"previous_{jdbc_key}"
    jdbc_jar = default(f"/cloudLevelParams/{jdbc_key}", None)
    prev_jar = default(f"/cloudLevelParams/{prev_jdbc_key}", None)
    
    # 生成JDBC连接URL
    if db_flavor == "oracle":
        colon_count = db_host.count(":")
        jdbc_url = db_config["url_template"] if colon_count in {0, 2} else \
            f"jdbc:oracle:thin:@//{db_host}"
    else:
        jdbc_url = db_config["url_template"].format(host=db_host, db=audit_db)
        
    return (
        jdbc_jar, 
        prev_jar, 
        jdbc_url, 
        db_config["driver"]
    )


def generate_ranger_service_config(ranger_plugin_properties: Dict) -> Dict:
    """
    生成Ranger服务配置字典
    """
    return {
        key.replace("ranger.service.config.param.", ""): value
        for key, value in ranger_plugin_properties.items()
        if key.startswith("ranger.service.config.param.")
    }


def get_policycache_service_name(
    service_name: str,
    repo_name: str,
    cache_service_list: List[str]
) -> bool:
    """通过策略缓存检查服务是否已存在"""
    cache_dir = POLICY_CACHE_PATH.format(repo=repo_name)
    hostname = socket.gethostname()
    service_exists = False
    
    # 验证缓存目录
    if not os.path.exists(cache_dir):
        Logger.debug(f"策略缓存目录不存�? {cache_dir}")
        return False

    try:
        # 搜索有效缓存文件
        for cache_service in cache_service_list:
            cache_file = os.path.join(cache_dir, f"{cache_service}_{repo_name}.json")
            
            # 文件验证
            if not (os.path.isfile(cache_file) and os.path.getsize(cache_file) > 0):
                continue
                
            # JSON格式验证
            try:
                with open(cache_file) as json_file:
                    data = json.load(json_file)
                    if data.get("serviceName") == repo_name:
                        Logger.info(
                            f"通过缓存文件确认{service_name}服务已存�? "
                            f"{cache_file} (最后修改时�? {datetime.datetime.fromtimestamp(os.path.getmtime(cache_file))})"
                        )
                        service_exists = True
                        break
            except json.JSONDecodeError:
                Logger.warning(f"缓存文件格式错误: {cache_file}")
            except Exception as e:
                Logger.error(f"处理缓存文件出错: {cache_file} ({str(e)})")
                
        return service_exists
    except Exception as e:
        Logger.error(f"检查策略缓存失�? {str(e)}")
        return False


def setup_ranger_ssl_context(
    conf_directory: str,
    properties_dict: Dict,
    attributes_dict: Dict,
    owner: str,
    group: str,
    ssl_context_name: str = "ranger-ssl.xml"
) -> None:
    """配置Ranger SSL上下�?""
    ssl_manager = SSLContextManager(
        keystore_path=properties_dict.get("xasecure.policymgr.clientssl.keystore.path"),
        truststore_path=properties_dict.get("xasecure.policymgr.clientssl.truststore.path"),
        keystore_password=properties_dict.get("xasecure.policymgr.clientssl.keystore.password"),
        truststore_password=properties_dict.get("xasecure.policymgr.clientssl.truststore.password"),
        keystore_type=properties_dict.get("xasecure.policymgr.clientssl.keystore.type", "jks"),
        truststore_type=properties_dict.get("xasecure.policymgr.clientssl.truststore.type", "jks")
    )
    
    # 创建密钥/信任�?    ssl_manager.create_and_configure_keystores(owner, group)
    
    # 生成SSL配置文件
    XmlConfig(
        ssl_context_name,
        conf_dir=conf_directory,
        configurations=properties_dict,
        configuration_attributes=attributes_dict,
        owner=owner,
        group=group,
        mode=0o644
    )
