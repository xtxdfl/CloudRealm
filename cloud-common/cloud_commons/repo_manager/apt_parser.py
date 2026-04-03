#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
"""

import re
from collections import defaultdict
from typing import Dict, Generator, List, Optional, Tuple, Union

from .generic_parser import GenericParser

# 预编译正则表达式提高性能
DPKG_LINE_REGEX = re.compile(
    r'^([a-z]{2})\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)$', 
    re.IGNORECASE
)
APT_CONFIG_LINE_REGEX = re.compile(
    r'^(?P<key>[a-zA-Z:_]+)\s+"?(?P<value>[^;]+)"?;$'
)
PACKAGE_SECTION_REGEX = re.compile(
    r'^Package:\s*(?P<name>\S+)'
)
VERSION_SECTION_REGEX = re.compile(
    r'^Version:\s*(?P<version>.+)'
)
FILE_SECTION_REGEX = re.compile(
    r'^File:\s*(?P<file>.+)'
)


class AptParser(GenericParser):
    """高性能APT/Dpkg输出解析器（优化版）"""

    @staticmethod
    def config_reader(
        stream: Generator[str, None, None]
    ) -> Generator[Tuple[str, str], None, None]:
        """
        APT配置解析器（支持多级属性）
        
        解析apt-config dump输出:
          PROPERTY "";
          PROPERTY::ITEM1:: "value";
          PROPERTY::ITEM2:: "value";
        
        :param stream: 输入文本流
        :return: (键, 值) 生成器
        """
        for line in stream:
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
                
            # 使用正则匹配键值对
            match = APT_CONFIG_LINE_REGEX.match(line)
            if not match:
                continue
                
            key = match.group('key').rstrip(':')
            value = match.group('value').strip('"').strip()
            
            # 转换多级键为点分隔形式
            if '::' in key:
                key = key.replace('::', '.')
            
            if value:
                yield key, value

    @staticmethod
    def packages_reader(
        stream: Generator[str, None, None],
        include_size: bool = False,
        include_arch: bool = False
    ) -> Generator[Tuple[str, str, str, Optional[int], Optional[str], Optional[str]], None, None]:
        """
        高级APT软件包信息解析器
        
        解析apt-cache dump输出:
          Package: test_package
          Version: 0.1.1-0
          Architecture: amd64
          Size: 123456
          File: /var/lib/apt/lists/repo_dists_stable_Packages.gz
        """
        current_pkg = defaultdict(lambda: None)
        pending_yield = False
        
        for line in stream:
            line = line.strip()
            
            # 检测新包段
            if not line:
                if pending_yield:
                    yield AptParser._construct_package_record(current_pkg, include_size, include_arch)
                    pending_yield = False
                current_pkg.clear()
                continue
                
            # 解析包名
            if line.startswith('Package:'):
                match = PACKAGE_SECTION_REGEX.match(line)
                if match:
                    current_pkg['name'] = match.group('name')
                    continue
            
            # 解析版本
            if line.startswith('Version:'):
                match = VERSION_SECTION_REGEX.match(line)
                if match:
                    current_pkg['version'] = match.group('version')
                    continue
            
            # 解析关联文件
            if line.startswith('File:'):
                match = FILE_SECTION_REGEX.match(line)
                if match:
                    file_path = match.group('file')
                    # 仅保留文件名
                    file_name = file_path.split('/')[-1] if '/' in file_path else file_path
                    current_pkg['file'] = file_name
                    # 标记有完整记录
                    if current_pkg['name'] and current_pkg['version']:
                        pending_yield = True
                    continue
            
            # 可选：解析架构信息
            if include_arch and line.startswith('Architecture:'):
                current_pkg['arch'] = line.split(':', 1)[1].strip()
                continue
            
            # 可选：解析软件包大小
            if include_size and line.startswith('Size:'):
                try:
                    current_pkg['size'] = int(line.split(':', 1)[1].strip())
                except (ValueError, IndexError):
                    current_pkg['size'] = None
        
        # 处理最后一个包
        if pending_yield:
            yield AptParser._construct_package_record(current_pkg, include_size, include_arch)
    
    @staticmethod
    def _construct_package_record(
        pkg_data: Dict[str, Union[str, int, None]], 
        include_size: bool,
        include_arch: bool
    ) -> Tuple[str, str, str, Optional[int], Optional[str], Optional[str]]:
        """构造包信息元组"""
        return (
            pkg_data['name'],
            pkg_data['version'],
            pkg_data['file'],
            pkg_data.get('size') if include_size else None,
            pkg_data.get('arch') if include_arch else None,
            f"{pkg_data['version']}_{pkg_data['file']}" if 'file' in pkg_data else None
        )

    @staticmethod
    def packages_installed_reader(
        stream: Generator[str, None, None],
        include_description: bool = False,
        include_arch: bool = False
    ) -> Generator[Tuple[str, str, Optional[str], Optional[str]], None, None]:
        """
        强大的已安装软件包解析器
        
        解析dpkg -l输出:
          ii  pkg-name  1.2.3-0  amd64  Package description
          rc  old-pkg   0.5.1    all    Removed package
          hi  hold-pkg  3.4.5    arm64  Held back
        """
        # dpkg命令会输出表头和分隔行
        # 使用更智能的状态机跳过非数据行
        
        # | Status | Package | Version | Architecture | Description |
        # |--------|---------|---------|--------------|-------------|
        # | ii     | bash    | 5.0-4   | amd64        | GNU Bourne... |
        # | ii     | coreutils | 8.30-3 | all          | GNU core... |
        
        # 状态标记
        header_passed = False
        separator_passed = False
        
        # 版本号正则 - 允许复杂的版本号格式
        version_regex = re.compile(
            r'^[0-9][\w\.\+\-\:\~]+$'
        )
        
        for line in stream:
            # 跳过空行
            if not line.strip():
                continue
                
            # 检测标题行和分隔行
            if not header_passed:
                # 检测包含"+++--------"的模式
                if re.match(r'^\+\+-\s+', line.strip()):
                    header_passed = True
                continue
            
            if not separator_passed:
                # 检测虚线分隔符
                if re.match(r'^[\-]+\s+', line.strip()):
                    separator_passed = True
                continue
            
            # 尝试使用正则表达式处理
            if line.startswith(('ii', 'hi', 'rc')):
                match = DPKG_LINE_REGEX.match(line)
                if match:
                    status, pkg_data = match.groups()[0], match.groups()[1:]
                    
                    # 验证状态码是有效的
                    if not re.match(r'^[a-z]{2}$', status, re.IGNORECASE):
                        continue
                    
                    # 包名可能包含:架构后缀 (e.g., libc6:amd64)
                    pkg_name = pkg_data[0]
                    if ':' in pkg_name:
                        pkg_name = pkg_name.split(':', 1)[0]
                    
                    # 提取版本
                    version = pkg_data[1]
                    if not version_regex.match(version):
                        continue
                        
                    # 输出结果
                    yield (
                        pkg_name,
                        version,
                        pkg_data[2] if include_arch else None,
                        pkg_data[3] if include_description else None
                    )
                else:
                    # 回退处理: 智能列分解
                    parts = AptParser._smart_split_dpkg_line(line)
                    if len(parts) >= 4:
                        # 状态应该总在前2字符
                        if len(parts[0]) < 3:
                            status = parts[0]
                            pkg_name = parts[1]
                            version = parts[2]
                            arch = parts[3] if len(parts) > 3 else None
                            desc = " ".join(parts[4:]) if len(parts) > 4 else None
                            
                            # 处理包名架构
                            if ':' in pkg_name:
                                pkg_name = pkg_name.split(':', 1)[0]
                            
                            if version_regex.match(version):
                                yield (
                                    pkg_name,
                                    version,
                                    arch if include_arch else None,
                                    desc if include_description else None
                                )
    
    @staticmethod
    def _smart_split_dpkg_line(line: str, min_columns=4) -> List[str]:
        """智能分割dpkg输出行，处理可能存在的空格"""
        parts = []
        current = ''
        min_widths = [0, 24, 36, 48, 60]  # 预期的最小列宽度
        
        for i, char in enumerate(line):
            if char == ' ' and current and (len(parts) < len(min_widths) and i > min_widths[len(parts)]):
                parts.append(current.strip())
                current = ''
            else:
                current += char
        
        if current:
            parts.append(current.strip())
        
        return parts if len(parts) >= min_columns else []

    @staticmethod
    def parse_apt_cache_policy(
        stream: Generator[str, None, None]
    ) -> Generator[Tuple[str, List[Tuple[str, int, str]]], None, None]:
        """
        解析apt-cache policy输出
        格式:
          Package:
            Installed: 1.2.3-0
            Candidate: 1.2.3-0
            Version table:
              1.2.3-0 500
                500 <URL> stable/main amd64 Packages
              1.2.2-0 500
                500 <URL> stable/main amd64 Packages
        """
        current_package = ""
        versions = []
        in_version_table = False
        
        for line in stream:
            line = line.strip()
            
            # 包名行
            if line.startswith('Installed:') or line.startswith('Candidate:'):
                continue
                
            # 新包开始
            if line and not line.startswith(' ') and line.endswith(':'):
                # 保存前一个包的信息
                if current_package and versions:
                    yield (current_package, versions)
                
                # 重置状态
                current_package = line.rstrip(':')
                versions = []
                in_version_table = False
                continue
                
            # 版本表示头
            if "Version table:" in line:
                in_version_table = True
                continue
                
            # 处理版本行
            if in_version_table and current_package:
                # 版本号通常以空白开始，包含版本和优先级
                if line.startswith(' ') and 'none' not in line:
                    try:
                        # 拆版本和优先级
                        version_part, prio_part = line.split(None, 1)
                        prio = int(prio_part.split()[0])
                        
                        # 确定源URL（可能没有）
                        source_match = re.search(r'\d+\s+(.*?)\s+', prio_part)
                        source = source_match.group(1) if source_match else None
                        
                        # 创建版本记录
                        versions.append((version_part, prio, source))
                    except (ValueError, IndexError):
                        # 记录但跳过失败行
                        continue
        
        # 输出最后一个包
        if current_package and versions:
            yield (current_package, versions)

    @staticmethod
    def parse_dpkg_status(
        stream: Generator[str, None, None]
    ) -> Dict[str, Dict[str, str]]:
        """
        解析/var/lib/dpkg/status文件
        格式:
          Package: package_name
          Status: install ok installed
          Priority: optional
          Section: admin
          Version: 1.2.3-0
          ...
        """
        status_db = {}
        current_pkg = {}
        current_key = None
        
        for line in stream:
            line = line.strip()
            
            # 新包开始，存储前一个
            if not line and current_pkg:
                pkg_name = current_pkg.get('Package')
                if pkg_name:
                    status_db[pkg_name] = current_pkg
                current_pkg = {}
                current_key = None
                continue
                
            # 键值行
            if line and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 多行键处理
                if key == "Description" and value == "":
                    continue
                    
                current_key = key
                if key not in current_pkg:
                    current_pkg[key] = value
                else:
                    # 处理多行值
                    current_pkg[key] += '\n' + value
                continue
                
            # 多行续行
            if current_key and line.startswith(' '):
                if current_key in current_pkg:
                    current_pkg[current_key] += '\n' + line.strip()
        
        # 添加最后一个包（如果存在）
        if current_pkg:
            pkg_name = current_pkg.get('Package')
            if pkg_name:
                status_db[pkg_name] = current_pkg
        
        return status_db

    @staticmethod
    def parse_apt_list(
        stream: Generator[str, None, None],
        status_filter: Optional[str] = "all"
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        """
        解析apt list [--installed|--upgradeable]输出
        格式: 
          package_name/version,revision [arch] [installed,automatic]
          vim/2:8.1.2269-1ubuntu5.20 amd64 [upgradable from: 2:8.1.2269-1ubuntu5]
        
        :param status_filter: "all", "installed", "upgradeable"
        """
        # 样本: wget/stable,stable 1.21.1-1+b1 amd64 [upgradable from: 1.18-5+deb9u1]
        pkg_regex = re.compile(
            r'^(?P<name>\S+)/(?P<version>\S+)'
            r'\s+(?P<arch>\S+)'
            r'\s+\[?(?P<status>\S+)?]?'
            r'(\s+from:\s+\S+)?$'  # 忽略"upgradable from"信息
        )
        
        for line in stream:
            if not line.strip() or line.startswith('Listing...'):
                continue
                
            match = pkg_regex.match(line)
            if match:
                name = match.group('name')
                version = match.group('version').split(',')[0]  # 取第一个版本
                arch = match.group('arch')
                status = match.group('status') or 'available'
                
                # 应用状态过滤
                if (status_filter == "installed" and "installed" not in status) or \
                   (status_filter == "upgradeable" and status != "upgradable"):
                    continue
                
                yield (name, version, arch, status)

    @staticmethod
    def analyze_package_changes(
        current: List[Tuple[str, str, str]],
        previous: List[Tuple[str, str, str]]
    ) -> Dict[str, Dict[str, List]]:
        """比较两份包状态，检测安装/更新/移除"""
        # 转换当前状态到字典 {包名: (版本, 架构)}
        current_dict = {pkg[0]: (pkg[1], pkg[2]) for pkg in current}
        previous_dict = {pkg[0]: (pkg[1], pkg[2]) for pkg in previous}
        
        changes = {
            "installed": [],   # (包名, 版本, 架构)
            "upgraded": [],    # (包名, 旧版本, 新版本, 架构)
            "downgraded": [],  # (包名, 旧版本, 新版本, 架构)
            "removed": [],     # (包名, 版本, 架构)
            "unchanged": []    # (包名, 版本, 架构)
        }
        
        # 检测新安装包
        for pkg in current_dict:
            if pkg not in previous_dict:
                changes["installed"].append(
                    (pkg, *current_dict[pkg])
                )
        
        # 检测移除包
        for pkg in previous_dict:
            if pkg not in current_dict:
                changes["removed"].append(
                    (pkg, *previous_dict[pkg])
                )
        
        # 检测版本变化
        for pkg in current_dict:
            if pkg in previous_dict:
                cur_ver, cur_arch = current_dict[pkg]
                prev_ver, prev_arch = previous_dict[pkg]
                
                # 确保架构一致
                if cur_arch != prev_arch:
                    changes["installed"].append((pkg, cur_ver, cur_arch))
                    changes["removed"].append((pkg, prev_ver, prev_arch))
                    continue
                
                # 版本比较
                from distutils.version import LooseVersion
                try:
                    if cur_ver == prev_ver:
                        changes["unchanged"].append((pkg, cur_ver, cur_arch))
                    elif LooseVersion(cur_ver) > LooseVersion(prev_ver):
                        changes["upgraded"].append(
                            (pkg, prev_ver, cur_ver, cur_arch)
                        )
                    else:
                        changes["downgraded"].append(
                            (pkg, prev_ver, cur_ver, cur_arch)
                        )
                except Exception:
                    # 无法比较时视为更改
                    changes["upgraded"].append(
                        (pkg, prev_ver, cur_ver, cur_arch)
                    )
        
        return changes
