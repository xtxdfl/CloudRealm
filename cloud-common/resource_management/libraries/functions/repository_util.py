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

Advanced Repository Management System
"""

import json
from typing import Dict, List, Set, Tuple, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from resource_management.core.exceptions import Fail
from resource_management.core.logger import Logger
from resource_management.libraries.resources.repository import Repository

# 自定义导�?from cloud_commons.os_check import OSCheck
from cloud_commons.utils import is_empty
import cloud_simplejson as simplejson

__all__ = ["RepositoryManager", "RepositoryConfig", "RepositoryItem", "LicensePolicy"]

# 常量定义
UBUNTU_REPO_COMPONENTS_POSTFIX = "main"
DEFAULT_REPO_FILENAME = "cloud.repo"

class RepoManagementLevel(Enum):
    """仓库管理级别配置"""
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"
    
class LicensePolicy(Enum):
    """许可证处理策�?""
    ALLOW_ALL = "allow_all"
    SKIP_GPL = "skip_gpl"
    STRICT = "strict"

@dataclass
class RepositoryItem:
    """
    仓库项数据结�?    :param repo_id: 仓库唯一标识�?    :param name: 仓库名称
    :param base_url: 基础URL
    :param mirrors: 镜像URL列表
    :param distribution: 发行版信息（Ubuntu专用�?    :param components: 组件列表（Ubuntu专用�?    :param tags: 仓库标签集合
    :param management_level: 管理级别
    :param applicable_services: 适用的服务列�?    """
    repo_id: str
    name: str
    base_url: str
    mirrors: List[str] = field(default_factory=list)
    distribution: Optional[str] = None
    components: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    management_level: RepoManagementLevel = RepoManagementLevel.FULL
    applicable_services: List[str] = field(default_factory=list)
    
    @property
    def ubuntu_components(self) -> List[str]:
        """获取Ubuntu系统的完整组件列�?""
        return [
            self.distribution if self.distribution else self.name,
            self.components.replace(",", " ") if self.components else UBUNTU_REPO_COMPONENTS_POSTFIX
        ]
    
    @property
    def is_managed(self) -> bool:
        """检查仓库是否由系统管理"""
        return self.management_level != RepoManagementLevel.NONE

@dataclass
class RepositoryConfig:
    """
    仓库配置文件结构
    :param version_id: 仓库版本ID
    :param stack_name: 所属技术栈名称
    :param version_string: 仓库版本�?    :param filename: 仓库文件�?    :param resolved: 是否已解析所有依�?    :param features: 仓库特性配�?    :param repositories: 包含的仓库列表项
    """
    version_id: str
    stack_name: str
    version_string: str
    filename: str = DEFAULT_REPO_FILENAME
    resolved: bool = False
    features: Dict = field(default_factory=dict)
    repositories: List[RepositoryItem] = field(default_factory=list)
    
    def __post_init__(self):
        """添加版本标识到仓库文件名"""
        if self.version_id and self.version_id not in self.filename:
            self.filename = f"{self.version_id}-{self.filename}"

class RepositoryManager:
    """
    高级仓库管理系统
    
    功能:
    - 多操作系统支�?(Ubuntu, RHEL, SUSE)
    - 智能仓库文件生成
    - 许可证策略管�?    - 统一API简化仓库操�?    - 详细的审计日�?    """
    
    def __init__(self, config: Dict, license_policy: LicensePolicy = LicensePolicy.SKIP_GPL):
        """
        初始化仓库管理器
        
        :param config: 系统配置字典
        :param license_policy: 许可证处理策�?        """
        self._config = config
        self.license_policy = license_policy
        
        # 解析仓库配置
        self.repository_config = self._parse_repository_config()
        if not self.repository_config:
            Logger.warning("未找到有效的仓库配置，跳过仓库文件创�?)
            return
            
        # 选择系统模板
        os_family = "ubuntu" if OSCheck.is_ubuntu_family() else \
                   "rhel" if OSCheck.is_redhat_family() else \
                   "suse" if OSCheck.is_suse_family() else "default"
                   
        self.repo_template = self.config.get(f"repo_{os_family}_template", "")
        
        if not self.repo_template:
            Logger.error(f"未找到适合 {os_family} 的仓库模�?)
    
    @property
    def config(self) -> Dict:
        """获取配置字典"""
        return self._config
        
    def apply_configuration(self) -> Dict[str, str]:
        """
        应用仓库配置并创建仓库文�?        
        :return: 包含仓库ID到文件名映射的字�?        :raises Fail: 当配置无效时抛出
        """
        if not self.repository_config:
            return {}
            
        repo_config = self.repository_config
        
        if repo_config.version_id is None:
            raise Fail("仓库版本ID缺失，无法处理仓库配�?)
            
        if not repo_config.repositories:
            Logger.warning(
                f"{repo_config.stack_name}/{repo_config.version_string} "
                f"没有可用的仓库配置，cloud可能不管理此版本"
            )
            return {}
            
        repo_files = {}
        
        # 审计日志
        Logger.info(f"开始生成仓库文�? {repo_config.filename} "
                   f"({len(repo_config.repositories)} 个仓�?")
        
        for repo_item in repo_config.repositories:
            # 跳过特定license政策的仓�?            if not self._is_allowed_repo(repo_item):
                continue
                
            # 仅处理受管理的仓�?            if repo_item.is_managed:
                self._create_repository_file(repo_item, repo_config.filename)
                repo_files[repo_item.repo_id] = repo_config.filename
            else:
                Logger.info(f"跳过不受管理的仓�? {repo_item.repo_id}")
                
        # 执行仓库创建操作
        Repository(None, action="create")
        
        Logger.info(f"成功创建 {len(repo_files)} 个仓库文�?)
        return repo_files
    
    def validate_repository(self, repo_id: str) -> bool:
        """
        验证指定仓库是否存在且可�?        
        :param repo_id: 仓库ID
        :return: 是否验证成功
        """
        if not self.repository_config:
            return False
            
        for repo in self.repository_config.repositories:
            if repo.repo_id == repo_id:
                return self._is_allowed_repo(repo) and repo.is_managed
                
        return False
    
    def list_managed_repositories(self) -> List[str]:
        """获取所有受管理的仓库ID列表"""
        if not self.repository_config:
            return []
            
        return [
            repo.repo_id for repo in self.repository_config.repositories 
            if repo.is_managed and self._is_allowed_repo(repo)
        ]
    
    def _is_allowed_repo(self, repo_item: RepositoryItem) -> bool:
        """检查仓库是否满足许可证策略要求"""
        # 允许所有许可证
        if self.license_policy == LicensePolicy.ALLOW_ALL:
            return True
            
        # 检查是否需要跳过GPL
        skip_tags = set()
        if self.license_policy == LicensePolicy.SKIP_GPL and "GPL" in repo_item.tags:
            skip_tags.add("GPL")
            
        # 严格模式跳过所有受限标�?        if self.license_policy == LicensePolicy.STRICT and any(
            tag.startswith("RESTRICTED") for tag in repo_item.tags
        ):
            skip_tags.add("RESTRICTED")
            
        # 记录跳过原因
        if skip_tags:
            Logger.info(
                f"基于许可证策�?{self.license_policy.name} 跳过仓库 {repo_item.repo_id} "
                f"原因: {', '.join(skip_tags)}"
            )
            return False
            
        return True
    
    def _create_repository_file(
        self, 
        repo_item: RepositoryItem, 
        filename: str
    ) -> None:
        """
        创建单个仓库文件
        
        :param repo_item: 仓库项配�?        :param filename: 仓库文件�?        """
        try:
            Repository(
                repo_item.repo_id,
                action="prepare",
                base_url=repo_item.base_url,
                mirror_list="|".join(repo_item.mirrors) if repo_item.mirrors else None,
                repo_file_name=filename,
                repo_template=self.repo_template,
                components=repo_item.ubuntu_components if OSCheck.is_ubuntu_family() else None,
            )
            Logger.debug(f"仓库 {repo_item.repo_id} 配置完成")
        except Exception as e:
            Logger.error(f"创建仓库 {repo_item.repo_id} 失败: {str(e)}")
            raise Fail(f"仓库配置失败: {repo_item.repo_id}") from e
    
    def _parse_repository_config(self) -> Optional[RepositoryConfig]:
        """解析仓库配置信息"""
        repo_config = self.config.get("repositoryFile", {})
        if not repo_config or is_empty(repo_config):
            return None
            
        # 处理JSON字符串或字典配置
        if isinstance(repo_config, str):
            try:
                json_dict = simplejson.loads(repo_config)
            except (simplejson.JSONDecodeError, TypeError) as e:
                raise Fail(f"仓库配置JSON解析失败: {str(e)}") from e
        elif isinstance(repo_config, dict):
            json_dict = dict(repo_config)
        else:
            raise Fail(f"无效的仓库配置类�? {type(repo_config).__name__}")
            
        # 解析基本配置
        version_id = json_dict.get("repoVersionId")
        stack_name = json_dict.get("stackName", "unknown")
        version_string = json_dict.get("repoVersion", "unknown")
        repo_filename = json_dict.get("repoFileName", DEFAULT_REPO_FILENAME)
        resolved = json_dict.get("resolved", False)
        features = json_dict.get("feature", {})
        
        # 解析仓库�?        repo_items = []
        repos_def = json_dict.get("repositories", [])
        if not isinstance(repos_def, list):
            repos_def = [repos_def] if repos_def else []
            
        for repo_def in repos_def:
            try:
                repo_item = RepositoryItem(
                    repo_id=repo_def.get("repoId", ""),
                    name=repo_def.get("repoName", "unnamed"),
                    base_url=repo_def.get("baseUrl", ""),
                    mirrors=repo_def.get("mirrorsList", []),
                    distribution=repo_def.get("distribution"),
                    components=repo_def.get("components"),
                    tags=set(repo_def.get("tags", [])),
                    management_level=RepoManagementLevel(
                        repo_def.get("managementLevel", "full").lower()
                    ),
                    applicable_services=repo_def.get("applicableServices", []),
                )
                repo_items.append(repo_item)
            except ValueError as e:
                Logger.warning(f"解析仓库项失�? {str(e)}")
        
        return RepositoryConfig(
            version_id=version_id,
            stack_name=stack_name,
            version_string=version_string,
            filename=repo_filename,
            resolved=resolved,
            features=features,
            repositories=repo_items,
        )

# ======================= 兼容性函�?=======================
def create_repo_files(
    template: Optional[str] = None, 
    command_repository: Optional[RepositoryConfig] = None
) -> Dict[str, str]:
    """
    向后兼容的仓库创建函数（已弃用）
    
    :param template: 仓库模板
    :param command_repository: 仓库配置对象
    :return: 仓库ID到文件名的映�?    """
    if not template or not command_repository:
        return {}
        
    Logger.warning("create_repo_files() 已弃用，请使�?RepositoryManager")
    
    repo_files = {}
    for repo_item in command_repository.repositories:
        if not repo_item.is_managed:
            continue
            
        Repository(
            repo_item.repo_id,
            action="prepare",
            base_url=repo_item.base_url,
            mirror_list="|".join(repo_item.mirrors) if repo_item.mirrors else None,
            repo_file_name=command_repository.filename,
            repo_template=template,
            components=repo_item.ubuntu_components if OSCheck.is_ubuntu_family() else None,
        )
        repo_files[repo_item.repo_id] = command_repository.filename
        
    Repository(None, action="create")
    return repo_files

# ====================== 测试代码 ======================
if __name__ == "__main__":
    # 测试配置
    TEST_CONFIG = {
        "repositoryFile": {
            "repoVersionId": "cloud-1.0",
            "stackName": "BigData",
            "repoVersion": "1.0.0",
            "repoFileName": "cloud.repo",
            "resolved": True,
            "feature": {"preInstalled": False, "scoped": True},
            "repositories": [
                {
                    "repoId": "cloud-core",
                    "repoName": "cloud Core",
                    "baseUrl": "https://repos.example.com/core",
                    "mirrorsList": ["https://mirror1.example.com/core"],
                    "distribution": "xenial",
                    "components": "main,contrib",
                    "tags": ["ESSENTIAL", "GPL"],
                    "managementLevel": "full",
                    "applicableServices": ["HDFS", "YARN"]
                },
                {
                    "repoId": "cloud-extra",
                    "repoName": "cloud Extras",
                    "baseUrl": "https://repos.example.com/extras",
                    "tags": ["OPTIONAL"],
                    "managementLevel": "partial"
                }
            ]
        },
        "configurations": {
            "cluster-env": {
                "repo_ubuntu_template": "deb {base_url} {distribution} {components}",
                "repo_rhel_template": "[{repo_id}]\nname={repo_name}\nbaseurl={base_url}",
                "repo_suse_template": "[{repo_id}]\nname={repo_name}\nbaseurl={base_url}"
            }
        }
    }
    
    # 测试仓库管理�?    def test_repository_manager():
        print("="*50)
        print("仓库管理器测�?)
        print("="*50)
        
        # 测试不同许可证策�?        policies = [
            (LicensePolicy.ALLOW_ALL, "允许所有许可证", 2),
            (LicensePolicy.SKIP_GPL, "跳过GPL许可�?, 1),
            (LicensePolicy.STRICT, "严格许可证策�?, 1)
        ]
        
        for policy, desc, expected in policies:
            manager = RepositoryManager(TEST_CONFIG, license_policy=policy)
            repos = manager.list_managed_repositories()
            print(f"{desc}: 找到 {len(repos)} 个仓�?(期望: {expected})")
            print(f"仓库列表: {repos}")
            
            # 应用配置
            print(f"应用配置结果 ({desc}):")
            repo_files = manager.apply_configuration()
            print(f"创建的仓库文�? {len(repo_files)}")
            print()
        
        print("仓库验证测试:")
        manager = RepositoryManager(TEST_CONFIG)
        print("cloud-core 存在:", manager.validate_repository("cloud-core"))
        print("cloud-extra 存在:", manager.validate_repository("cloud-extra"))
        print("未知仓库:", manager.validate_repository("unknown-repo"))
    
    # 运行测试
    test_repository_manager()
