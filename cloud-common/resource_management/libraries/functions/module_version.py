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

Advanced Module Version Management System
"""

import re
from typing import NamedTuple, Optional, Tuple, Union, List, Dict, Any
from functools import total_ordering
from packaging import version as pack_version
from collections.abc import Iterable
from enum import Enum, auto
from dataclasses import dataclass

class VersionType(Enum):
    SEMANTIC = auto()     # 语义化版本 (1.2.3)
    APACHE_STD = auto()   # Apache标准版本 (1.2.3.4)
    MODULE = auto()       # 模块化版本 (1.2.3.4-h5-b6)
    DATETIME = auto()     # 日期时间版本 (2023.12.01.1830)
    ALPHA_NUM = auto()    # 字母数字版本 (v1.2.3rc4)
    UNKNOWN = auto()      # 无法识别的版本

@dataclass
class VersionMetadata:
    """版本元数据容器"""
    label: str = ""       # 版本标签 (stable, beta, etc.)
    revision: int = 0     # 修订号
    build: int = 0        # 构建号
    platform: str = ""    # 平台标识
    architecture: str = "" # 系统架构
    branch: str = ""      # 代码分支
    commit: str = ""      # Git提交哈希
    changelist: str = ""  # 变更列表ID

class VersionSchemeException(Exception):
    """版本方案异常基类"""
    pass

@total_ordering
class ModuleVersion(NamedTuple):
    """
    高级模块版本管理类
    支持多种版本格式的检测、解析和比较
    """
    apache_major: int
    apache_minor: int
    internal_minor: int
    internal_maint: int
    hotfix: int = 0
    build: int = 0
    meta: VersionMetadata = VersionMetadata()
    
    @classmethod
    def from_string(cls, version_str: str, strict: bool = False) -> "ModuleVersion":
        """
        从字符串解析版本信息
        支持多种版本格式的自动检测
        
        :param version_str: 版本字符串
        :param strict: 是否严格模式
        :return: 解析后的ModuleVersion对象
        :raise VersionSchemeException: 解析失败时抛出
        """
        version_str = version_str.lower().strip()
        
        # 尝试识别版本类型
        version_type = cls.detect_version_type(version_str)
        
        try:
            # 根据识别类型选择解析方法
            if version_type == VersionType.SEMANTIC:
                return cls.parse_semantic(version_str)
            elif version_type == VersionType.MODULE:
                return cls.parse_module(version_str, strict)
            elif version_type == VersionType.APACHE_STD:
                return cls.parse_apache_std(version_str)
            elif version_type == VersionType.DATETIME:
                return cls.parse_datetime(version_str)
            elif version_type == VersionType.ALPHA_NUM:
                return cls.parse_alpha_numeric(version_str)
            else:
                return cls.parse_universal(version_str)
        except Exception as e:
            if strict:
                raise VersionSchemeException(f"无法解析版本: {version_str} - {str(e)}")
            return cls.parse_universal(version_str)

    @staticmethod
    def detect_version_type(version_str: str) -> VersionType:
        """自动检测版本类型"""
        if re.match(r"^\d+\.\d+\.\d+-\w+$", version_str):
            return VersionType.SEMANTIC
        elif re.match(r"^\d+\.\d+\.\d+\.\d+$", version_str):
            return VersionType.APACHE_STD
        elif re.match(r"^\d+\.\d+\.\d+\.\d+(-h\d+)*-b\d+", version_str):
            return VersionType.MODULE
        elif re.match(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}$", version_str):
            return VersionType.DATETIME
        elif re.match(r"^v?\d+\.\d+\.\d+[a-z]+\d+$", version_str, re.IGNORECASE):
            return VersionType.ALPHA_NUM
        return VersionType.UNKNOWN
    
    @classmethod
    def parse_module(cls, module_version: str, strict: bool = False) -> "ModuleVersion":
        """
        解析模块版本字符串 (1.2.3.4-h5-b6)
        
        :param module_version: 模块版本字符串
        :param strict: 是否严格模式（严格要求格式）
        :return: ModuleVersion对象
        """
        # 灵活的正则表达式适配多种格式
        pattern = (
            r"^(?P<a_major>\d+)\.(?P<a_minor>\d+)\.?"         # apache_major, apache_minor
            r"(?P<i_minor>\d+)\.?(?P<i_maint>\d+)"            # internal_minor, internal_maint
            r"(-h(?P<hotfix>\d+))?"                           # 热修复版本（可选）
            r"(-b(?P<build>\d+))?"                            # 构建号（可选）
            r"(-(?P<label>\w+))?"                             # 标签（可选）
            r"(?P<metadata>(:?[-_].+)?)$"                     # 附加元数据
        )
        
        match = re.match(pattern, module_version)
        if not match:
            if strict:
                raise VersionSchemeException(f"无效的模块版本格式: {module_version}")
            return cls(0, 0, 0, 0, meta=VersionMetadata(label="invalid"))
        
        groups = match.groupdict()
        
        # 解析元数据部分（如果存在）
        metadata_str = groups.pop("metadata") or ""
        metadata = cls._parse_metadata(metadata_str)
        
        # 设置缺失值为0
        for key in ['hotfix', 'build']:
            groups[key] = groups[key] or '0'
        
        # 更新元数据标签
        if groups.get('label'):
            metadata.label = groups.pop('label')
            
        return cls(
            int(groups['a_major']),
            int(groups['a_minor']),
            int(groups['i_minor']),
            int(groups['i_maint']),
            int(groups['hotfix']),
            int(groups['build']),
            meta=metadata
        )
    
    @classmethod
    def parse_universal(cls, version_str: str) -> "ModuleVersion":
        """通用解析器（适配未知格式）"""
        # 提取所有数字部分
        parts = [int(d) for d in re.findall(r'\d+', version_str)]
        padding = [0] * max(0, 6 - len(parts))
        parts.extend(padding)
        
        # 提取额外信息
        label = next((m.group(0) for m in re.finditer(r'(?<=-)[a-z]+', version_str, re.IGNORECASE)), "")
        commit = next((m.group(0) for m in re.finditer(r'[0-9a-f]{7,}', version_str)), "")
        
        return cls(
            parts[0] if len(parts) > 0 else 0,
            parts[1] if len(parts) > 1 else 0,
            parts[2] if len(parts) > 2 else 0,
            parts[3] if len(parts) > 3 else 0,
            parts[4] if len(parts) > 4 else 0,
            parts[5] if len(parts) > 5 else 0,
            meta=VersionMetadata(label=label, commit=commit)
        )
    
    @classmethod
    def parse_alpha_numeric(cls, version_str: str) -> "ModuleVersion":
        """解析字母数字组合版本 (v1.2.3rc4)"""
        # ...
        return cls(0, 0, 0, 0)  # 简化的实现
    
    @classmethod
    def parse_datetime(cls, version_str: str) -> "ModuleVersion":
        """解析日期时间版本 (2023.12.01.1830)"""
        # ...
        return cls(0, 0, 0, 0)  # 简化的实现
    
    @classmethod
    def parse_semantic(cls, semver: str) -> "ModuleVersion":
        """解析语义化版本 (1.2.3-beta.4+5)"""
        try:
            v = pack_version.parse(semver)
            return cls(
                v.major,
                v.minor,
                v.micro,
                int(v.post or 0) if v.pre is None else 0,
                meta=VersionMetadata(
                    label=str(v.pre[0] if v.pre else '').lstrip(''),
                    build=v.post or 0
                )
            )
        except:
            return cls.parse_universal(semver)
    
    @classmethod
    def parse_apache_std(cls, apache_ver: str) -> "ModuleVersion":
        """解析标准Apache版本 (1.2.3.4)"""
        parts = apache_ver.split('.')
        padded = (parts + ['0', '0', '0', '0'])[:6]
        return cls(*(int(p) for p in padded[:6]))
    
    @staticmethod
    def _parse_metadata(metadata_str: str) -> VersionMetadata:
        """解析版本元数据"""
        # 示例格式: _platform=linux_arch=x64_branch=main_commit=a1b2c3d
        metadata = VersionMetadata()
        
        if not metadata_str:
            return metadata
        
        # 提取键值对
        pairs = dict(re.findall(r'[_\-](\w+)=([\w\.]+)', metadata_str))
        metadata.label = pairs.get('label', '')
        metadata.revision = int(pairs.get('rev', '0') or '0')
        metadata.build = int(pairs.get('build', '0') or '0')
        metadata.platform = pairs.get('platform', '')
        metadata.architecture = pairs.get('arch', '')
        metadata.branch = pairs.get('branch', '')
        metadata.commit = pairs.get('commit', '')
        
        # 特殊提取变更列表ID
        metadata.changelist = next(re.findall(r'cl(\d+)', metadata_str), "")
        
        return metadata
    
    def __eq__(self, other: "ModuleVersion") -> bool:
        """等于运算"""
        if not isinstance(other, ModuleVersion):
            return NotImplemented
        return self.to_comparable() == other.to_comparable()
    
    def __lt__(self, other: "ModuleVersion") -> bool:
        """小于运算"""
        if not isinstance(other, ModuleVersion):
            return NotImplemented
        return self.to_comparable() < other.to_comparable()
    
    def compare(self, other: "ModuleVersion", include_metadata: bool = False) -> int:
        """
        高级版本比较
        
        :param other: 待比较的版本
        :param include_metadata: 是否包含元数据
        :return: 1（大于）, 0（等于）, -1（小于）
        """
        if not isinstance(other, ModuleVersion):
            raise TypeError("只能比较ModuleVersion对象")
        
        base_comparison = self._compare_base(other)
        if base_comparison != 0:
            return base_comparison
        
        # 比较热修复版本
        if self.hotfix != other.hotfix:
            return 1 if self.hotfix > other.hotfix else -1
        
        # 比较构建号
        if self.build != other.build:
            return 1 if self.build > other.build else -1
        
        # 需要时比较元数据
        if include_metadata:
            return self._compare_metadata(other.meta)
        
        return 0
    
    def _compare_base(self, other: "ModuleVersion") -> int:
        """基础四段版本比较"""
        for i, attr in enumerate(['apache_major', 'apache_minor', 'internal_minor', 'internal_maint']):
            self_val = getattr(self, attr)
            other_val = getattr(other, attr)
            if self_val != other_val:
                return 1 if self_val > other_val else -1
        return 0
    
    def _compare_metadata(self, other_meta: VersionMetadata) -> int:
        """元数据比较策略"""
        # 比较标签类型：stable > rc > beta > alpha > 无标签
        label_priority = {"stable": 5, "rc": 4, "beta": 3, "alpha": 2}
        self_priority = label_priority.get(self.meta.label, 1)
        other_priority = label_priority.get(other_meta.label, 1)
        
        if self_priority != other_priority:
            return 1 if self_priority > other_priority else -1
        
        # 相同标签下比较修订号
        if self.meta.revision != other_meta.revision:
            return 1 if self.meta.revision > other_meta.revision else -1
        
        # 比较更改列表（更高为更新）
        if self.meta.changelist and other_meta.changelist:
            return int(self.meta.changelist) - int(other_meta.changelist)
        
        return 0
    
    def to_comparable(self) -> Tuple[int, ...]:
        """转换为可比较元组"""
        return (
            self.apache_major,
            self.apache_minor,
            self.internal_minor,
            self.internal_maint,
            self.hotfix,
            self.build
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            'apache_major': self.apache_major,
            'apache_minor': self.apache_minor,
            'internal_minor': self.internal_minor,
            'internal_maint': self.internal_maint,
            'hotfix': self.hotfix,
            'build': self.build,
            'label': self.meta.label,
            'revision': self.meta.revision,
            'platform': self.meta.platform,
            'architecture': self.meta.architecture,
            'commit': self.meta.commit,
            'changelist': self.meta.changelist
        }
    
    def __repr__(self) -> str:
        """标准表示形式"""
        parts = [
            f"{self.apache_major}.{self.apache_minor}",
            f"{self.internal_minor}.{self.internal_maint}"
        ]
        
        if self.hotfix > 0:
            parts.append(f"h{self.hotfix}")
        
        parts.append(f"b{self.build}")
        
        if self.meta.label:
            parts.append(self.meta.label)
            
        # 附加元数据表示
        meta_repr = self._metadata_repr()
        if meta_repr:
            parts.append(meta_repr)
            
        return "-".join(parts)
    
    def _metadata_repr(self) -> str:
        """生成元数据表示"""
        meta_parts = []
        if self.meta.platform:
            meta_parts.append(f"platform={self.meta.platform}")
        if self.meta.architecture:
            meta_parts.append(f"arch={self.meta.architecture}")
        if self.meta.branch:
            meta_parts.append(f"branch={self.meta.branch}")
        if self.meta.commit:
            meta_parts.append(f"commit={self.meta.commit[:7]}")
        if self.meta.changelist:
            meta_parts.append(f"cl={self.meta.changelist}")
            
        return "_".join(meta_parts) if meta_parts else ""
    
    def is_stable(self) -> bool:
        """是否为稳定版本"""
        return not self.meta.label or self.meta.label == "stable"
    
    def is_pre_release(self) -> bool:
        """是否为预发布版本"""
        return self.meta.label in {"alpha", "beta", "rc"} and self.build == 0
    
    def is_compatible(self, other: "ModuleVersion", level: str = "major") -> bool:
        """
        检查版本兼容性
        
        :param other: 待比较版本
        :param level: 兼容级别 (major, minor, patch)
        :return: 是否兼容
        """
        if not isinstance(other, ModuleVersion):
            return False
            
        if level == "major":
            return self.apache_major == other.apache_major
            
        elif level == "minor":
            return (self.apache_major == other.apache_major and 
                   self.apache_minor == other.apache_minor)
            
        elif level == "patch":
            return (self.apache_major == other.apache_major and
                   self.apache_minor == other.apache_minor and
                   self.internal_minor == other.internal_minor)
            
        return False

# 辅助函数和工具类
class VersionManager:
    """版本管理器 - 处理多个版本集合"""
    
    def __init__(self):
        self.versions = []
        
    def add_versions(self, versions: Iterable[str]):
        """添加多个版本字符串"""
        for ver in versions:
            self.versions.append(ModuleVersion.from_string(ver))
        
    def sort_versions(self, reverse: bool = False) -> List[ModuleVersion]:
        """排序版本"""
        return sorted(self.versions, reverse=reverse)
    
    def get_latest(self, include_pre_release: bool = False) -> ModuleVersion:
        """获取最新版本"""
        stable_versions = [v for v in self.versions 
                          if include_pre_release or v.is_stable()]
        return max(stable_versions) if stable_versions else None
    
    def find_compatible(self, base_version: str, compatibility_level: str) -> List[ModuleVersion]:
        """查找兼容版本"""
        base = ModuleVersion.from_string(base_version)
        return [v for v in self.versions 
               if v.is_compatible(base, compatibility_level)]
    
    def filter_by_metadata(self, **kwargs) -> List[ModuleVersion]:
        """根据元数据过滤版本"""
        results = []
        for ver in self.versions:
            match = True
            for key, value in kwargs.items():
                if hasattr(ver.meta, key):
                    if getattr(ver.meta, key) != value:
                        match = False
                        break
                elif key == 'label':
                    if ver.meta.label != value:
                        match = False
                        break
            if match:
                results.append(ver)
        return results

# 兼容层
def validate_version_string(version_str: str) -> bool:
    """验证版本字符串有效性"""
    try:
        ModuleVersion.from_string(version_str, strict=True)
        return True
    except VersionSchemeException:
        return False
    
def parse_version_string(version_str: str) -> ModuleVersion:
    """解析版本字符串（兼容函数）"""
    return ModuleVersion.from_string(version_str)

def compare_versions(left: Union[str, ModuleVersion], right: Union[str, ModuleVersion]) -> int:
    """比较两个版本（兼容函数）"""
    if isinstance(left, str):
        left = ModuleVersion.from_string(left)
    if isinstance(right, str):
        right = ModuleVersion.from_string(right)
    return left.compare(right)

