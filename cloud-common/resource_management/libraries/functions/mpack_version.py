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

Enhanced Semantic Version Parser
"""

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Optional, Tuple, Pattern, Match, Any
from packaging.version import parse as parse_semver, Version


@total_ordering
@dataclass
class VersionSegment:
    """表示版本号的单个分段，支持数值和字符串比较"""
    value: Any
    
    def __post_init__(self):
        # 优先数值转换，失败转为字符串
        try:
            self.value = int(self.value)
        except (ValueError, TypeError):
            try:
                self.value = float(self.value)
            except (ValueError, TypeError):
                self.value = str(self.value)
    
    def __lt__(self, other: 'VersionSegment') -> bool:
        """智能比较不同类型的分段值"""
        if isinstance(self.value, type(other.value)):
            return self.value < other.value
            
        # 数值和字符串比较：数字总是小于字符串
        if isinstance(self.value, (int, float)) and isinstance(other.value, str):
            return True
        if isinstance(self.value, str) and isinstance(other.value, (int, float)):
            return False
            
        # 其他混合类型比较
        return str(self.value) < str(other.value)
    
    def __eq__(self, other: 'VersionSegment') -> bool:
        """智能判断不同类型的分段值是否相等"""
        if isinstance(self.value, type(other.value)):
            return self.value == other.value
        return str(self.value) == str(other.value)


class MpackVersion:
    """
    高级MPack版本解析和比较类
    
    支持多种版本格式：
    1. 新版MPack格式：1.2.3-h4-b567
    2. 传统堆栈格式：1.2.3.4-567
    3. 语义化版本：1.2.3+hotfix.4.b567
    
    提供丰富的比较操作和转换功能
    """
    
    # 预编译版本模式
    PACK_VERSION_PATTERNS = {
        "mpack": r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<maint>\d+)(?:-h(?P<hotfix>\d+))*-b(?P<build>\d+)$",
        "legacy": r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<maint>\d+)\.(?P<hotfix>\d+)-(?P<build>\d+)$",
        "semantic": r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<maint>\d+)(?:\+(?P<extra>[a-z0-9.]+))?$"
    }
    
    # 带错误信息的格式定义
    VERSION_FORMATS = {
        "mpack": {
            "pattern": re.compile(PACK_VERSION_PATTERNS["mpack"]),
            "error": "版本格式应为: <主版本>.<次版本>.<维护版本>-h<热修复版本>-b<构建号> (例如: 3.1.0-h0-b123)"
        },
        "legacy": {
            "pattern": re.compile(PACK_VERSION_PATTERNS["legacy"]),
            "error": "传统版本格式应为: <主版本>.<次版本>.<维护版本>.<热修复版本>-<构建号> (例如: 2.7.5.0-4321)"
        },
        "semantic": {
            "pattern": re.compile(PACK_VERSION_PATTERNS["semantic"]),
            "error": "语义化版本格式应为: <主版本>.<次版本>.<维护版本>+<扩展信息> (例如: 4.2.1+hotfix.0.b456)"
        }
    }
    
    # 特殊版本标识符权重
    SPECIAL_WEIGHTS = {
        "snapshot": -4,
        "alpha": -3,
        "beta": -2,
        "rc": -1,
        "sp": 1
    }
    
    def __init__(self, 
                 major: int = 0, 
                 minor: int = 0, 
                 maint: int = 0, 
                 hotfix: int = 0, 
                 build: int = 0,
                 extra: str = "",
                 version_str: str = "",
                 schema: str = "mpack"):
        """
        初始化版本对象
        
        :param major: 主版本号
        :param minor: 次版本号
        :param maint: 维护版本号
        :param hotfix: 热修复版本号
        :param build: 构建号
        :param extra: 扩展信息
        :param version_str: 原始版本字符串
        :param schema: 版本模式 (mpack/legacy/semantic)
        """
        self._major = int(major)
        self._minor = int(minor)
        self._maint = int(maint)
        self._hotfix = int(hotfix) if hotfix != "" else 0
        self._build = int(build) if build != "" else 0
        self._extra = extra if extra is not None else ""
        self._segments = []  # 用于非标准版本的分段存储
        self._original = version_str
        self._schema = schema
        self._semantic: Optional[Version] = None
        
        # 尝试解析为语义化版本
        if not extra and version_str:
            try:
                self._semantic = parse_semver(version_str)
            except Exception:
                pass
    
    @property
    def major(self) -> int:
        return self._major
    
    @property
    def minor(self) -> int:
        return self._minor
    
    @property
    def maint(self) -> int:
        return self._maint
    
    @property
    def hotfix(self) -> int:
        return self._hotfix
    
    @property
    def build(self) -> int:
        return self._build
    
    @property
    def extra(self) -> str:
        return self._extra
    
    @property
    def schema(self) -> str:
        return self._schema
    
    @property
    def is_semantic(self) -> bool:
        """检查是否是语义化版本"""
        return self._semantic is not None
    
    @property
    def is_legacy(self) -> bool:
        """检查是否是传统堆栈版本"""
        return self._schema == "legacy"
    
    @property
    def is_mpack(self) -> bool:
        """检查是否是MPack格式版本"""
        return self._schema == "mpack"
    
    @classmethod
    def parse(cls, version_str: str, force_schema: str = None) -> 'MpackVersion':
        """
        智能解析版本字符串，自动检测格式
        
        :param version_str: 版本字符串
        :param force_schema: 强制使用特定格式
        :return: Version对象
        :raises ValueError: 当无法解析时抛出
        """
        # 处理空值
        if not version_str or not version_str.strip():
            raise ValueError("版本号不能为空")
            
        version_str = version_str.strip()
        
        # 尝试强制模式
        if force_schema and force_schema in cls.VERSION_FORMATS:
            return cls._parse_by_schema(version_str, force_schema)
            
        # 自动检测最佳格式
        for schema, fmt_def in cls.VERSION_FORMATS.items():
            matcher = fmt_def["pattern"].match(version_str)
            if matcher:
                try:
                    return cls._create_from_match(matcher, version_str, schema)
                except Exception as e:
                    continue  # 尝试下一个模式
        
        # 尝试语义化版本作为回退
        try:
            parsed = parse_semver(version_str)
            return cls(
                parsed.major, parsed.minor or 0, 
                parsed.micro or 0, 0, 0, 
                extra=str(parsed.local) if parsed.local else "",
                version_str=version_str,
                schema="semantic"
            )
        except Exception:
            pass
            
        # 终极回退：分段解析
        segments = []
        for part in re.split(r"[\._-]", version_str):
            segment = VersionSegment(part)
            segments.append(segment.value if isinstance(segment.value, (int, float)) else part)
            
        version = cls(version_str=version_str, schema="freeform")
        version._segments = segments
        return version
    
    @classmethod
    def parse_stack_version(cls, stack_version: str) -> 'MpackVersion':
        """
        专用方法解析传统堆栈版本
        
        :param stack_version: 堆栈版本字符串
        :return: Version对象
        """
        return cls.parse(stack_version, force_schema="legacy")
    
    def _to_list(self) -> list:
        """转换为比较列表"""
        if self._schema in ("mpack", "legacy"):
            return [self._major, self._minor, self._maint, self._hotfix, self._build]
        elif self._schema == "semantic" and self._semantic:
            return [
                self._semantic.major,
                self._semantic.minor or 0,
                self._semantic.micro or 0,
                self._parse_extra_weight(self._extra),
                self._parse_extra_build(self._extra) or 0
            ]
        else:
            return self._segments.copy()
    
    def _parse_extra_weight(self, extra: str) -> int:
        """解析扩展信息中的特殊标识权重"""
        extra = (extra or "").lower()
        for keyword, weight in self.SPECIAL_WEIGHTS.items():
            if keyword in extra:
                return weight
        return 0
    
    def _parse_extra_build(self, extra: str) -> Optional[int]:
        """从扩展信息中提取构建号"""
        matches = re.search(r"\b(b|build|bld)?(\d{2,})\b", extra or "")
        if matches and matches.group(2):
            try:
                return int(matches.group(2))
            except (ValueError, TypeError):
                pass
        return None
    
    def __repr__(self) -> str:
        if self._schema == "freeform":
            return ".".join(str(s) for s in self._segments)
            
        parts = []
        parts.append(f"{self._major}.{self._minor}.{self._maint}")
        
        if self._hotfix > 0 and self._schema != "semantic":
            parts.append(f".{self._hotfix}")
            
        if self._schema == "mpack":
            if self._hotfix > 0:
                parts.append(f"-h{self._hotfix}")
            parts.append(f"-b{self._build}")
        elif self._schema == "legacy":
            parts.append(f"-{self._build}")
        elif self._schema == "semantic" and self._extra:
            parts.append(f"+{self._extra}")
            
        return "".join(parts)
    
    def __str__(self) -> str:
        return self._original if self._original else self.__repr__()
    
    def _cmp_version(self, other: 'MpackVersion') -> int:
        """版本比较核心方法"""
        # 类型检查
        if not isinstance(other, self.__class__):
            raise TypeError(f"无法比较不同类型: {type(self)} 和 {type(other)}")
        
        # 使用语义化版本进行比较
        if self._semantic and other._semantic:
            if self._semantic < other._semantic:
                return -1
            elif self._semantic > other._semantic:
                return 1
            else:
                return 0
        
        # 标准比较逻辑
        this_list = self._to_list()
        other_list = other._to_list()
        
        # 填充长度差异
        max_len = max(len(this_list), len(other_list))
        this_list += [0] * (max_len - len(this_list))
        other_list += [0] * (max_len - len(other_list))
        
        # 按段比较
        for this_part, other_part in zip(this_list, other_list):
            this_seg = VersionSegment(this_part)
            other_seg = VersionSegment(other_part)
            
            if this_seg < other_seg:
                return -1
            elif this_seg > other_seg:
                return 1
        return 0
    
    def __lt__(self, other: 'MpackVersion') -> bool:
        return self._cmp_version(other) < 0
    
    def __gt__(self, other: 'MpackVersion') -> bool:
        return self._cmp_version(other) > 0
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._cmp_version(other) == 0
    
    def __hash__(self) -> int:
        return hash(str(self))
    
    def is_compatible(self, other: 'MpackVersion') -> bool:
        """检查是否与另一版本兼容（主版本相同）"""
        return self._major == other._major and self._minor == other._minor
    
    def next_major(self) -> 'MpackVersion':
        """生成下一个主版本"""
        return type(self)(self._major + 1, 0, 0, 0, 0, self._extra)
    
    def next_minor(self) -> 'MpackVersion':
        """生成下一个次要版本"""
        return type(self)(self._major, self._minor + 1, 0, 0, 0, self._extra)
    
    @classmethod
    def _parse_by_schema(cls, version_str: str, schema: str) -> 'MpackVersion':
        """按指定模式解析版本"""
        fmt_def = cls.VERSION_FORMATS.get(schema)
        if not fmt_def:
            raise ValueError(f"无效的模式: {schema}")
        
        matcher = fmt_def["pattern"].match(version_str)
        if not matcher:
            raise ValueError(fmt_def["error"])
        
        return cls._create_from_match(matcher, version_str, schema)
    
    @classmethod
    def _create_from_match(cls, matcher: Match, version_str: str, schema: str) -> 'MpackVersion':
        """从正则匹配结果创建版本对象"""
        groups = matcher.groupdict()
        
        # 处理语义化版本的特殊情况
        if schema == "semantic":
            extra = groups.get("extra", "")
            build = cls._extract_extra_build(extra)
            return cls(
                groups.get("major", 0),
                groups.get("minor", 0),
                groups.get("maint", 0),
                0,
                build,
                extra=extra,
                version_str=version_str,
                schema=schema
            )
        
        return cls(
            groups.get("major", 0),
            groups.get("minor", 0),
            groups.get("maint", 0),
            groups.get("hotfix", 0),
            groups.get("build", 0),
            version_str=version_str,
            schema=schema
        )
    
    @classmethod
    def _extract_extra_build(cls, extra: str) -> int:
        """从扩展信息提取构建号"""
        if not extra:
            return 0
        
        # 尝试提取显式构建号
        build_match = re.search(r"\b(build|b|)(?P<build>\d+)\b", extra)
        if build_match and build_match.group("build"):
            try:
                return int(build_match.group("build"))
            except (ValueError, TypeError):
                pass
        
        # 尝试提取版本片段
        version_match = re.search(r"\d{2,}", extra)
        if version_match:
            try:
                return int(version_match.group())
            except (ValueError, TypeError):
                pass
                
        return 0


if __name__ == "__main__":
    # 测试用例
    def test_parse(version_str: str, expected: str):
        """版本解析测试"""
        try:
            v = MpackVersion.parse(version_str)
            result = str(v)
            status = "✓" if result == expected else f"✗ 预期: {expected}"
            print(f"输入: '{version_str}' -> 解析: '{result}' {status}")
        except ValueError as e:
            print(f"输入: '{version_str}' -> 错误: {str(e)}")

    def test_comparison(v1: str, op: str, v2: str):
        """版本比较测试"""
        try:
            a = MpackVersion.parse(v1)
            b = MpackVersion.parse(v2)
            ops = {
                '<': a < b,
                '<=': a <= b,
                '==': a == b,
                '!=': a != b,
                '>=': a >= b,
                '>': a > b
            }
            if op in ops:
                result = ops[op]
                status = "✓" if result else "✗"
                print(f"比较: '{v1}' {op} '{v2}' -> {result} {status}")
            else:
                print(f"无效操作符: '{op}'")
        except ValueError as e:
            print(f"比较错误: {v1} {op} {v2} -> {str(e)}")

    print("="*50)
    print("版本解析测试")
    print("="*50)
    test_parse("3.1.0-h0-b123", "3.1.0-h0-b123")
    test_parse("2.7.5.0-4321", "2.7.5.0-4321")  # 传统格式转换
    test_parse("4.2.1+hotfix.0.b456", "4.2.1+hotfix.0.b456")
    test_parse("5.0.0", "5.0.0")
    test_parse("", "版本号不能为空")
    test_parse("invalid-version", "5.0.0")  # 自由格式测试

    print("\n" + "="*50)
    print("版本比较测试")
    print("="*50)
    test_comparison("3.1.0", ">", "2.9.5")
    test_comparison("2.7.5.0-4321", "==", "2.7.5.0.4321")
    test_comparison("4.2.1-beta", "<", "4.2.1")
    test_comparison("1.2.0-h1-b100", ">", "1.2.0-h0-b200")
    test_comparison("3.0.0", "!=", "3.0.0+hotfix")

    print("\n" + "="*50)
    print("兼容性测试")
    print("="*50)
    v1 = MpackVersion.parse("3.1.0")
    v2 = MpackVersion.parse("3.2.0")
    print(f"3.1.0 与 3.2.0 兼容: {'是' if v1.is_compatible(v2) else '否'} (预期: 是)")

    v3 = MpackVersion.parse("4.0.0")
    v4 = MpackVersion.parse("3.9.9")
    print(f"4.0.0 与 3.9.9 兼容: {'是' if v3.is_compatible(v4) else '否'} (预期: 否)")

    print("\n" + "="*50)
    print("版本生成测试")
    print("="*50)
    v5 = MpackVersion.parse("2.8.3")
    print(f"下一个主版本: {v5.next_major()} (预期: 3.0.0)")
    print(f"下一个次要版本: {v5.next_minor()} (预期: 2.9.0)")
