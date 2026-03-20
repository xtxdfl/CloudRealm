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

高级集群配置管理
"""

from typing import Any, Dict, Optional

class ClusterSettings:
    """
    集群环境配置管理�?    
    此类管理 cluster-env 部分中的集群设置配置，提供类型安全的访问接口
    和智能默认值处理�?    
    配置源结构：
        "configurations": {
            "cluster-env": {
                "security_enabled": "true",
                "recovery_enabled": "true",
                "kerberos_domain": "example.com",
                ...
            }
        }
    """

    DEFAULT_VALUES = {
        "security_enabled": False,
        "recovery_enabled": False,
        "recovery_type": "AUTO_START",
        "recovery_max_count": 0,
        "smokeuser": "cloud-qa",
        "user_group": "hadoop",
        "override_uid": False,
        "ignore_groupsusers_create": False,
        "fetch_nonlocal_groups": True
    }

    SYS_PREP_OPTIONS = [
        "sysprep_skip_copy_fast_jar_hdfs",
        "sysprep_skip_lzo_package_operations",
        "sysprep_skip_setup_jce",
        "sysprep_skip_create_users_and_groups"
    ]

    def __init__(self, cluster_settings: Dict[str, Any]):
        """
        初始化集群配置管理器
        
        :param cluster_settings: cluster-env 部分的原始配置字�?        """
        self._cluster_settings = cluster_settings or {}
        self._cache = {}
        
    def _get_value(self, key: str, default: Any = None, transform: callable = None) -> Any:
        """
        获取并缓存配置值，可选进行类型转�?        
        :param key: 配置键名
        :param default: 默认值（未找到时使用�?        :param transform: 可选的转换函数
        :return: 配置值或默认�?        """
        if key in self._cache:
            return self._cache[key]
            
        # 获取原始值或默认�?        value = self._cluster_settings.get(key, default)
        if value is None:
            value = self.DEFAULT_VALUES.get(key, default)
        
        # 应用转换
        if transform and value is not None:
            try:
                value = transform(value)
            except (ValueError, TypeError):
                pass
        
        self._cache[key] = value
        return value

    # ================= 安全相关配置 =================
    @property
    def is_cluster_security_enabled(self) -> bool:
        """
        检查集群是否启用安全机�?        
        :return: 安全是否启用 (True/False)
        """
        return self._get_value(
            "security_enabled", 
            self.DEFAULT_VALUES["security_enabled"],
            lambda v: v.lower() == "true"
        )

    @property
    def kerberos_domain(self) -> str:
        """
        获取Kerberos域名
        
        :return: Kerberos域名
        """
        return self._get_value("kerberos_domain", "")

    # ================= 恢复与容错配�?=================
    @property
    def is_recovery_enabled(self) -> bool:
        """
        检查是否启用集群恢复机�?        
        :return: 恢复机制是否启用
        """
        return self._get_value(
            "recovery_enabled", 
            self.DEFAULT_VALUES["recovery_enabled"],
            lambda v: v.lower() == "true"
        )

    @property
    def recovery_type(self) -> str:
        """
        获取集群恢复类型
        
        :return: 恢复类型字符�?(�?"AUTO_START")
        """
        return self._get_value("recovery_type", self.DEFAULT_VALUES["recovery_type"])

    @property
    def recovery_max_count(self) -> int:
        """
        获取最大恢复重试次�?        
        :return: 最大恢复次�?(默认0)
        """
        try:
            return self._get_value("recovery_max_count", self.DEFAULT_VALUES["recovery_max_count"], int)
        except (ValueError, TypeError):
            return self.DEFAULT_VALUES["recovery_max_count"]

    # ================= 用户与组管理 =================
    @property
    def smokeuser(self) -> str:
        """
        获取smoke测试用户�?        
        :return: smoke用户名称
        """
        return self._get_value("smokeuser", self.DEFAULT_VALUES["smokeuser"])

    @property
    def user_group(self) -> str:
        """
        获取集群用户组名
        
        :return: 用户组名�?        """
        return self._get_value("user_group", self.DEFAULT_VALUES["user_group"])

    @property
    def should_override_uid(self) -> bool:
        """
        检查是否应该覆盖用户ID
        
        :return: 是否覆盖UID
        """
        return self._get_value(
            "override_uid", 
            self.DEFAULT_VALUES["override_uid"],
            lambda v: v.lower() == "true"
        )

    @property
    def should_ignore_groupsusers_create(self) -> bool:
        """
        检查是否应忽略用户/组创�?        
        :return: 是否忽略用户/组创�?        """
        return self._get_value(
            "ignore_groupsusers_create", 
            self.DEFAULT_VALUES["ignore_groupsusers_create"],
            lambda v: v.lower() == "true"
        )

    @property
    def should_fetch_nonlocal_groups(self) -> bool:
        """
        检查是否应提取非本地用户组
        
        :return: 是否提取非本地组
        """
        return self._get_value(
            "fetch_nonlocal_groups", 
            self.DEFAULT_VALUES["fetch_nonlocal_groups"],
            lambda v: v.lower() == "true"
        )

    # ================= 系统准备配置 =================
    def should_skip_sysprep(self, option_name: str) -> bool:
        """
        检查是否应跳过指定的系统准备步�?        
        :param option_name: 系统准备选项名称
        :return: 是否应跳过此步骤
        """
        if option_name not in self.SYS_PREP_OPTIONS:
            return False
            
        return self._get_value(
            option_name, 
            False,  # 默认为不跳过
            lambda v: v.lower() == "true"
        )

    # ================= Repository 配置 =================
    @property
    def repo_suse_rhel_template(self) -> str:
        """
        获取SUSE/RHEL的仓库模�?        
        :return: 仓库模板字符�?        """
        return self._get_value("repo_suse_rhel_template", "")

    @property
    def repo_ubuntu_template(self) -> str:
        """
        获取Ubuntu的仓库模�?        
        :return: 仓库模板字符�?        """
        return self._get_value("repo_ubuntu_template", "")

    # ================= 高级安全审计 =================
    def validate_security_config(self) -> bool:
        """
        验证安全配置有效�?        
        :return: 配置是否完整有效
        """
        # 如果启用安全机制但缺少Kerberos域名
        if self.is_cluster_security_enabled and not self.kerberos_domain:
            return False
            
        # 恢复机制启用但类型缺�?        if self.is_recovery_enabled and not self.recovery_type:
            return False
            
        return True

    # ================= 配置调试 =================
    def list_configuration(self) -> Dict[str, Any]:
        """
        获取所有集群环境配置（非敏感信息）
        
        :return: 配置字典（过滤了敏感值）
        """
        return {
            key: value 
            for key, value in self._cluster_settings.items()
            if "password" not in key.lower() and "secret" not in key.lower()
        }
