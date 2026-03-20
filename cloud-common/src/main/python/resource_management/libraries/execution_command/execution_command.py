#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
Regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

高级命令执行管理�?"""

from resource_management.libraries.execution_command import module_configs
from resource_management.libraries.execution_command import stack_settings
from resource_management.libraries.execution_command import cluster_settings
from typing import Any, Dict, List, Optional, Union, Set
import json
import logging

class ExecutionCommand:
    """
    命令执行协调中枢
    
    此类封装了执行命令的所有相关信息和服务访问点，
    是服务部署、配置管理的核心枢纽
    
    主要功能�?    - 中央化命令配置访�?    - 服务与组件元数据管理
    - 环境参数提供和安全访�?    - 集群拓扑信息查询
    - 执行状态追�?    """
    
    CONFIG_MAPPING = {
        "stack_settings": "configurations/cluster-env",
        "cluster_settings": "configurations/cluster-env",
        "module_configs": ["configurations", "configurationAttributes"]
    }

    def __init__(self, command: Dict):
        """
        初始化命令执行管理器
        
        :param command: 命令JSON字典
        """
        self._command = command
        self._log = logging.getLogger(self.__class__.__name__)
        self._cached_values = {}
        
        # 初始化子系统
        self._module_configs = self._init_module_configs()
        self._stack_settings = self._init_stack_settings()
        self._cluster_settings = self._init_cluster_settings()
    
    def _init_module_configs(self) -> module_configs.ModuleConfigs:
        """初始化模块配置管�?""
        return module_configs.ModuleConfigs(
            self._get_value("configurations", {}),
            self._get_value("configurationAttributes", {})
        )
    
    def _init_stack_settings(self) -> stack_settings.StackSettings:
        """初始化堆栈设置管�?""
        cluster_env = self._get_value("configurations/cluster-env", {})
        return stack_settings.StackSettings(cluster_env)
    
    def _init_cluster_settings(self) -> cluster_settings.ClusterSettings:
        """初始化集群设置管�?""
        cluster_env = self._get_value("configurations/cluster-env", {})
        return cluster_settings.ClusterSettings(cluster_env)
    
    def _get_value(self, key_path: str, default: Any = None) -> Any:
        """递归查询嵌套字典�?""
        if key_path in self._cached_values:
            return self._cached_values[key_path]
            
        keys = key_path.split('/')
        value = self._command
        try:
            for key in keys:
                value = value[key]
            self._cached_values[key_path] = value
            return value
        except (KeyError, TypeError):
            self._cached_values[key_path] = default
            return default

    @property
    def module_configs(self) -> module_configs.ModuleConfigs:
        """获取模块配置管理�?""
        return self._module_configs

    @property
    def stack_settings(self) -> stack_settings.StackSettings:
        """获取堆栈设置管理�?""
        return self._stack_settings

    @property
    def cluster_settings(self) -> cluster_settings.ClusterSettings:
        """获取集群设置管理�?""
        return self._cluster_settings

    @property
    def service_name(self) -> str:
        """获取服务名称 (�?'ZOOKEEPER', 'HDFS')"""
        return self._get_value("serviceName", "UNKNOWN_SERVICE")

    @property
    def component_type(self) -> str:
        """获取组件类型 (�?'ZOOKEEPER_SERVER', 'NAMENODE')"""
        return self._get_value("role", "UNKNOWN_COMPONENT")

    @property
    def component_name(self) -> str:
        """获取组件实例�?(默认为服务名)"""
        if "_CLIENTS" in self.service_name:  # 客户端特殊处�?            return "default"
        return self.service_name

    @property
    def cluster_name(self) -> str:
        """获取集群名称"""
        return self._get_value("clusterName", "default_cluster")

    @property
    def role_command(self) -> str:
        """获取当前执行的命�?(�?'INSTALL', 'START', 'ACTIONEXECUTE')"""
        return self._get_value("roleCommand", "UNKNOWN_COMMAND")

    @property
    def host_name(self) -> str:
        """获取执行主机�?""
        return self._get_value("agentLevelParams/hostname", "localhost")

    # ================= 智能环境检�?=================
    @property
    def is_client_component(self) -> bool:
        """检查是否为客户端组�?""
        return "_CLIENT" in self.component_type.upper()
    
    @property
    def is_master_component(self) -> bool:
        """检查是否为主模�?(Master/Server类型)"""
        return "_MASTER" in self.component_type.upper() or "_SERVER" in self.component_type.upper()
    
    @property
    def requires_system_preparation(self) -> bool:
        """系统准备是否完成"""
        return self._get_value("cloudLevelParams/host_sys_prepped", False)
    
    @property
    def is_secure_cluster(self) -> bool:
        """检查集群是否启用安全模�?""
        return self.cluster_settings.is_cluster_security_enabled
    
    # ================= 环境路径管理 =================
    @property
    def agent_cache_dir(self) -> str:
        """获取Agent缓存目录"""
        return self._get_value(
            "agentLevelParams/agentCacheDir", 
            "/var/lib/cloud-agent/cache"
        )
    
    @property
    def java_home(self) -> str:
        """获取Java HOME路径"""
        return self._get_value("cloudLevelParams/java_home", "/usr/jdk/latest")
    
    @property
    def java_version(self) -> int:
        """获取Java主版本号"""
        return self._get_value("cloudLevelParams/java_version", 8)
    
    @property
    def agent_stack_retry_count(self) -> int:
        """获取Agent部署重试次数"""
        return self._get_value("cloudLevelParams/agent_stack_retry_count", 5)
    
    @property
    def agent_parallel_execution(self) -> bool:
        """检查Agent是否允并行执�?""
        return bool(self._get_value(
            "agentLevelParams/agentConfigParams/agent/parallel_execution", 
            0
        ))
    
    def get_repository_file_path(self) -> str:
        """获取软件仓库文件路径 (带完整路径解�?"""
        repo_relpath = self._get_value("repositoryFile", "repositories.json")
        return self.resolve_path(repo_relpath)
    
    def resolve_path(self, relative_path: str) -> str:
        """
        解析相对路径为绝对路�?        
        :param relative_path: 相对路径
        :return: 绝对路径
        """
        # 简单实�?- 完整系统会使用配置的基础目录
        if relative_path.startswith("/"):
            return relative_path
        return f"{self.agent_cache_dir}/{relative_path}"

    # ================= 集群拓扑服务 =================
    def get_component_hosts(self, component_name: str) -> List[str]:
        """获取组件部署主机列表"""
        key_template = "clusterHostInfo/{0}"
        
        # 特殊组件处理
        if component_name == "oozie_server":
            return self._get_value(key_template.format("oozie_server"), [])
            
        keys_to_try = [
            key_template.format(component_name + "_hosts"),
            key_template.format(component_name)
        ]
        
        for key in keys_to_try:
            hosts = self._get_value(key, [])
            if hosts:
                return hosts
        return []

    def get_master_hosts(self) -> List[str]:
        """获取所有主节点主机列表 (包括NameNode, ResourceManager�?"""
        master_services = [
            "namenode", "resourcemanager", "hbase_master",
            "historyserver", "zookeeper_server", "spark_thriftserver",
            "kafka_broker", "flink_historyserver"
        ]
        
        hosts_set = set()
        for service in master_services:
            hosts_set.update(self.get_component_hosts(service))
        return list(hosts_set)
    
    def get_peer_component_hosts(self) -> List[str]:
        """获取同类型组件的所有主�?""
        component_key = self.component_type.split('_')[0].lower()  # �? "ZOOKEEPER_SERVER" -> "zookeeper"
        return self.get_component_hosts(component_key + "_hosts")
    
    def get_cluster_all_hosts(self) -> List[str]:
        """获取集群所有主机名"""
        return self._get_value("clusterHostInfo/all_hosts", [])

    # ================= 安全与连接管�?=================
    @property
    def cloud_server_host(self) -> str:
        """获取cloud服务器主�?""
        return self._get_value("cloudLevelParams/cloud_server_host", "localhost")
    
    @property
    def cloud_server_port(self) -> str:
        """获取cloud服务器端�?""
        return self._get_value("cloudLevelParams/cloud_server_port", "8080")
    
    @property
    def cloud_use_ssl(self) -> bool:
        """检查是否使用SSL连Cloud服务�?""
        return self._get_value("cloudLevelParams/cloud_server_use_ssl", False)
    
    def get_cloud_server_url(self) -> str:
        """构建cloud服务器完整URL"""
        protocol = "https" if self.cloud_use_ssl else "http"
        return f"{protocol}://{self.cloud_server_host}:{self.cloud_server_port}"

    # ================= 资源与部署管�?=================
    @property
    def jdk_location(self) -> str:
        """JDK安装包位置URL"""
        return self._get_value("cloudLevelParams/jdk_location", "")
    
    @property
    def jdk_name(self) -> str:
        """JDK安装包文件名"""
        return self._get_value("cloudLevelParams/jdk_name", "")
    
    @property
    def jce_name(self) -> Optional[str]:
        """JCE策略文件�?""
        return self._get_value("cloudLevelParams/jce_name")
    
    @property
    def module_package_folder(self) -> str:
        """模块软件包存储目�?""
        return self._get_value("commandParams/service_package_folder", "")
    
    def get_database_driver_url(self, db_type: str) -> Optional[str]:
        """数据库驱动程序URL获取"""
        driver_map = {
            "mysql": ("mysql_jdbc_url", "mysql-connector-java.jar"),
            "oracle": ("oracle_jdbc_url", "ojdbc8.jar"),
            "postgresql": ("postgres_jdbc_url", "postgresql.jar")
        }
        
        key, default = None, None
        if db_type.lower() in driver_map:
            key, default = driver_map[db_type.lower()]
        
        return self._get_value(f"cloudLevelParams/{key}", default) if key else None

    # ================= 状态追踪与审计 =================
    def record_execution_status(self, status: str, message: str = "") -> None:
        """记录执行状�?(实现为日�?"""
        self._log.info(f"Execution status: {status} | Component: {self.component_type} | Message: {message}")
    
    def get_execution_context(self) -> Dict:
        """获取当前执行上下文摘�?""
        return {
            "service": self.service_name,
            "component": self.component_type,
            "command": self.role_command,
            "host": self.host_name,
            "cluster": self.cluster_name,
            "system_prepared": self.requires_system_preparation,
            "secure_mode": self.is_secure_cluster,
            "java_version": self.java_version,
            "component_hosts": self.get_component_hosts(self.component_type)
        }
    
    def validate_execution_prerequisites(self) -> bool:
        """验证执行前置条件"""
        # 安全模式检�?        if self.is_secure_cluster and not self.cluster_settings.kerberos_domain:
            return False
            
        # Java版本验证
        min_java_version = 8
        if self.java_version < min_java_version:
            return False
            
        # 主机可达性验�?        if not self.get_peer_component_hosts():
            return False
            
        return True


class ExecutionCommandBuilder:
    """命令构建器工�?""
    
    @staticmethod
    def from_file(file_path: str) -> ExecutionCommand:
        """
        从JSON文件创建执行命令
        
        :param file_path: JSON文件路径
        :return: 初始化的ExecutionCommand实例
        """
        with open(file_path, 'r') as f:
            command_data = json.load(f)
        return ExecutionCommand(command_data)
    
    @staticmethod
    def from_dict(data: Dict) -> ExecutionCommand:
        """
        从字典创建执行命�?        
        :param data: 命令字典
        :return: 初始化的ExecutionCommand实例
        """
        return ExecutionCommand(data)
    
    @staticmethod
    def for_service_install(service: str, comp_type: str, host: str) -> 'ExecutionCommandBuilder':
        """创建服务安装命令构建�?""
        return ExecutionCommandBuilder(service, "INSTALL", comp_type, host)

    
    class _Builder:
        """命令构建器子�?""
        
        def __init__(self, service: str, command: str, comp_type: str, host: str):
            self._context = {
                "serviceName": service,
                "roleCommand": command,
                "role": comp_type,
                "agentLevelParams": {"hostname": host},
                "configurations": {},
                "configurationAttributes": {}
            }
        
        def with_config(self, config_type: str, properties: Dict) -> 'ExecutionCommandBuilder._Builder':
            if "configurations" not in self._context:
                self._context["configurations"] = {}
            self._context["configurations"][config_type] = properties
            return self
        
        def with_attribute(self, config_type: str, attributes: Dict) -> 'ExecutionCommandBuilder._Builder':
            if "configurationAttributes" not in self._context:
                self._context["configurationAttributes"] = {}
            self._context["configurationAttributes"][config_type] = attributes
            return self
        
        def build(self) -> ExecutionCommand:
            return ExecutionCommand(self._context)


# =================== 运行时环境管理器 ===================
class ExecutionEnvironment:
    """命令执行运行时环境封�?""
    
    def __init__(self, command: ExecutionCommand):
        self.command = command
        self.context = {}
        self._resource_provider = ResourceProvider()
        
    def init_environment(self) -> bool:
        """初始化执行环�?""
        # 配置日志
        self._configure_logging()
        
        # 设置路径
        self._setup_paths()
        
        # 检测依�?        if not self._validate_dependencies():
            return False
            
        # 安全环境准备
        return self._prepare_security_environment()
    
    def _configure_logging(self) -> None:
        """配置命令日志系统"""
        log_file = f"/var/log/cloud/{self.command.service_name}.log"
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s %(levelname)s [%(name)s]: %(message)s'
        )
        
    def _setup_paths(self) -> None:
        """配置环境变量PATH"""
        import os
        java_home = self.command.java_home
        if java_home:
            os.environ['JAVA_HOME'] = java_home
            os.environ['PATH'] = f"{java_home}/bin:{os.environ['PATH']}"
        
        # 添加模块包路�?        if self.command.module_package_folder:
            os.environ['PATH'] = f"{self.command.module_package_folder}/bin:{os.environ['PATH']}"
    
    def _validate_dependencies(self) -> bool:
        """验证环境依赖"""
        # JDK检�?        if not self._resource_provider.is_jdk_installed():
            self._log.error("JDK not installed")
            return False
            
        # 安全依赖检�?        if self.command.is_secure_cluster:
            if not self._resource_provider.is_kerberos_configured():
                self._log.error("Kerberos not configured")
                return False
                
        return True
    
    def _prepare_security_environment(self) -> bool:
        """准备安全环境"""
        if not self.command.is_secure_cluster:
            return True
            
        # Kerberos初始�?        return self._resource_provider.init_kerberos(
            self.command.cluster_settings.kerberos_domain,
            self.command.host_name
        )
    
    def get_resource_archive(self, resource_name: str) -> Optional[str]:
        """获取资源包路�?""
        archive_path = f"{self.command.agent_cache_dir}/resources/{resource_name}"
        if not os.path.exists(archive_path):
            self._log.warning(f"Resource not found: {resource_name}")
            return None
        return archive_path


class ResourceProvider:
    """基础设施资源提供�?""
    
    def __init__(self):
        import os
        self.os = os
        
    def is_jdk_installed(self) -> bool:
        """检查JDK是否安装"""
        java_home = self.os.environ.get("JAVA_HOME", "")
        if not java_home:
            return False
        return self.os.path.exists(f"{java_home}/bin/java")
    
    def is_kerberos_configured(self) -> bool:
        """检查Kerberos是否配置"""
        krb_conf = "/etc/krb5.conf"
        return self.os.path.exists(krb_conf) and self.os.path.getsize(krb_conf) > 0
    
    def init_kerberos(self, domain: str, host: str) -> bool:
        """初始化Kerberos环境"""
        # 实际实现会创建keytab等操�?        return True
