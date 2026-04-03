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

Advanced Component Installation Decision System
"""

import os
from enum import Enum
from typing import Dict, List, Set, Optional, Callable
from resource_management.libraries.script import Script
from resource_management.libraries.functions import StackFeature
from resource_management.libraries.functions.default import default
from resource_management.libraries.functions.stack_features import check_stack_feature
from resource_management.libraries.functions.version import format_stack_version
from resource_management.core.exceptions import ClientComponentHasNoConfig
from resource_management.core.logger import Logger


class ComponentType(Enum):
    """组件类型分类"""
    CORE_SERVICE = 1        # 必须的核心服务组件
    DEPENDENCY = 2          # 基础依赖组件
    OPTIONAL_SERVICE = 3    # 可选服务组件
    MANAGEMENT = 4          # 管理平台组件
    INTEGRATION = 5         # 集成组件


class InstallationDecisionEngine:
    """组件安装决策引擎"""
    
    def __init__(self, config: Dict):
        self.config = config
        self._decision_cache = {}
        self._configured_components = set()
        self._init_component_cache()
        
    def _init_component_cache(self) -> None:
        """初始化组件缓存"""
        # 从配置中提取本地安装组件
        if "role" in self.config and self.config["role"] == "install_packages":
            self._configured_components = set(self.config.get("localComponents", []))
        else:
            role = self.config.get("role", "")
            if role:
                self._configured_components = {role}
    
    def should_install(self, component: str) -> bool:
        """判断是否应该安装指定组件"""
        # 首先检查缓存
        if component in self._decision_cache:
            return self._decision_cache[component]
        
        # 确定决策函数
        decision_func = self._get_decision_function(component)
        result = decision_func()
        
        # 记录决策过程
        self._log_decision(component, result)
        
        # 缓存结果
        self._decision_cache[component] = result
        return result
    
    def _get_decision_function(self, component: str) -> Callable[[], bool]:
        """获取组件的决策函数"""
        decision_strategy = {
            "PHOENIX": self._should_install_phoenix,
            "METRICS_COLLECTOR": self._should_install_ams_collector,
            "METRICS_GRAFANA": self._should_install_ams_grafana,
            "MYSQL_SERVER": self._should_install_mysql,
            "MYSQL_CONNECTOR": self._should_install_mysql_connector,
            "HIVE_ATLAS": self._should_install_hive_atlas,
            "FALCON_ATLAS_HOOK": self._should_install_falcon_atlas_hook,
            "RANGER_TAGSYNC": self._should_install_ranger_tagsync,
            "RPCBIND": self._should_install_rpcbind,
            "INFRA_SOLR": self._should_install_infra_solr,
            "INFRA_SOLR_CLIENT": self._should_install_infra_solr_client,
            "LOGSEARCH_PORTAL": self._should_install_logsearch_portal,
        }
        
        return decision_strategy.get(component, self._default_decision_strategy)
    
    def _default_decision_strategy(self) -> bool:
        """默认决策策略 - 当没有特定决策函数时使用"""
        return False
    
    def _log_decision(self, component: str, install: bool) -> None:
        """记录安装决策"""
        Logger.info(
            f"安装决策: 组件 '{component}' -> {'是' if install else '否'}",
            role=self.config.get("role", "未知"),
            current_components=self._configured_components,
            config_source=self.config.get("configSource", "未知")
        )
    
    def _has_local_component(self, components: Set[str], strict: bool = False) -> bool:
        """
        检查本地是否有指定的组件
        
        :param components: 需要检查的组件集合
        :param strict: 是否要求全部组件都存在
        :return: 是否满足条件
        """
        if not self._configured_components:
            return False
        
        component_check = all if strict else any
        
        return component_check(
            component in self._configured_components
            for component in components
        )
    
    def _should_install_phoenix(self) -> bool:
        """Phoenix 安装决策"""
        # 检查配置启用状态
        phoenix_enabled = self.config.get(
            "/configurations/hbase-env/phoenix_sql_enabled",
            default=False
        )
        
        # 检查集群中是否存在 Phoenix
        phoenix_hosts = default("/clusterHostInfo/phoenix_query_server_hosts", [])
        has_phoenix_hosts = len(phoenix_hosts) > 0
        
        # 决策逻辑：配置启用或存在Phoenix主机
        return phoenix_enabled or has_phoenix_hosts
    
    def _should_install_ams_collector(self) -> bool:
        """AMS Collector 安装决策"""
        return self._has_local_component({"METRICS_COLLECTOR"})
    
    def _should_install_ams_grafana(self) -> bool:
        """AMS Grafana 安装决策"""
        return self._has_local_component({"METRICS_GRAFANA"})
    
    def _should_install_infra_solr(self) -> bool:
        """Infra Solr 安装决策"""
        return self._has_local_component({"INFRA_SOLR"})
    
    def _should_install_infra_solr_client(self) -> bool:
        """Infra Solr Client 安装决策"""
        return self._has_local_component({
            "INFRA_SOLR_CLIENT", 
            "ATLAS_SERVER", 
            "RANGER_ADMIN", 
            "LOGSEARCH_SERVER"
        })
    
    def _should_install_logsearch_portal(self) -> bool:
        """Logsearch Portal 安装决策"""
        return self._has_local_component({"LOGSEARCH_SERVER"})
    
    def _should_install_mysql(self) -> bool:
        """MySQL Server 安装决策"""
        # 检查是否使用现有外部数据库
        try:
            hive_db_config = self.config["configurations"]["hive-env"]["hive_database"]
            use_existing_db = hive_db_config.startswith("Existing")
            if use_existing_db:
                return False
        except KeyError:
            Logger.warning("无法获取hive-env配置，跳过MySQL安装检查")
            return False
        
        # 检查是否需要安装MySQL服务端
        return self._has_local_component({"MYSQL_SERVER"})
    
    def _should_install_mysql_connector(self) -> bool:
        """MySQL Connector 安装决策"""
        # 检查是否使用现有的外部MySQL
        use_existing_db = False
        try:
            hive_db_config = self.config["configurations"]["hive-env"]["hive_database"]
            use_existing_db = hive_db_config.startswith("Existing")
        except KeyError:
            Logger.warning("无法获取hive-env配置，继续检查MySQL连接器安装条件")
        
        # 如果使用现有数据库，则不需要安装连接器
        if use_existing_db:
            return False
        
        # 需要MySQL连接器的组件
        dependent_components = {
            "MYSQL_SERVER",
            "HIVE_METASTORE",
            "HIVE_SERVER",
            "HIVE_SERVER_INTERACTIVE"
        }
        
        return self._has_local_component(dependent_components)
    
    def _should_install_hive_atlas(self) -> bool:
        """Hive Atlas 集成安装决策"""
        atlas_hosts = default("/clusterHostInfo/atlas_server_hosts", [])
        return len(atlas_hosts) > 0
    
    def _should_install_falcon_atlas_hook(self) -> bool:
        """Falcon Atlas Hook 安装决策"""
        try:
            # 检查Falcon组件是否存在
            if not self._has_local_component({"FALCON_SERVER"}):
                return False
            
            # 验证Stack版本是否支持Falcon Atlas集成
            stack_version = self.config["clusterLevelParams"]["stack_version"]
            formatted_version = format_stack_version(stack_version)
            
            return check_stack_feature(
                StackFeature.FALCON_ATLAS_SUPPORT_2_3, formatted_version
            ) or check_stack_feature(
                StackFeature.FALCON_ATLAS_SUPPORT, formatted_version
            )
            
        except Exception as e:
            Logger.error(f"Falcon Atlas Hook检查失败: {str(e)}")
            return False
    
    def _should_install_ranger_tagsync(self) -> bool:
        """Ranger Tagsync 安装决策"""
        tagsync_hosts = default("/clusterHostInfo/ranger_tagsync_hosts", [])
        return len(tagsync_hosts) > 0
    
    def _should_install_rpcbind(self) -> bool:
        """RPCBIND 安装决策"""
        return self._has_local_component({"NFS_GATEWAY"})


# ------------------- 对外接口函数 -------------------
# 保持兼容性的外部接口函数
def should_install_phoenix() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("PHOENIX")

def should_install_ams_collector() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("METRICS_COLLECTOR")

def should_install_ams_grafana() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("METRICS_GRAFANA")

def should_install_infra_solr() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("INFRA_SOLR")

def should_install_infra_solr_client() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("INFRA_SOLR_CLIENT")

def should_install_logsearch_portal() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("LOGSEARCH_PORTAL")

def should_install_mysql() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("MYSQL_SERVER")

def should_install_mysql_connector() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("MYSQL_CONNECTOR")

def should_install_hive_atlas() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("HIVE_ATLAS")

def should_install_falcon_atlas_hook() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("FALCON_ATLAS_HOOK")

def should_install_ranger_tagsync() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("RANGER_TAGSYNC")

def should_install_rpcbind() -> bool:
    decision_engine = InstallationDecisionEngine(Script.get_config())
    return decision_engine.should_install("RPCBIND")


# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 初始化模拟配置
    test_config = {
        "role": "install_packages",
        "localComponents": ["HIVE_METASTORE", "METRICS_COLLECTOR"],
        "clusterHostInfo": {
            "phoenix_query_server_hosts": ["host1"],
            "atlas_server_hosts": ["host2"]
        },
        "configurations": {
            "hbase-env": {
                "phoenix_sql_enabled": "true"
            },
            "hive-env": {
                "hive_database": "New"
            }
        },
        "clusterLevelParams": {
            "stack_version": "2.6.0"
        }
    }
    
    # 创建决策引擎
    engine = InstallationDecisionEngine(test_config)
    
    # 测试决策
    print("Phoenix 安装:", engine.should_install("PHOENIX"))  # 应为 True
    print("MySQL 安装:", engine.should_install("MYSQL_SERVER"))  # 应为 False
    print("连接器安装:", engine.should_install("MYSQL_CONNECTOR"))  # 应为 True
    print("Falcon Atlas:", engine.should_install("FALCON_ATLAS_HOOK"))  # 应为 False
    print("Tagsync安装:", engine.should_install("RANGER_TAGSYNC"))  # 应为 False
    print("RPCBIND安装:", engine.should_install("RPCBIND"))  # 应为 False
    print("AMS Collector:", engine.should_install("METRICS_COLLECTOR"))  # 应为 True
