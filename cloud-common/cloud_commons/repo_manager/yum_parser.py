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
import string
from typing import Dict, Generator, List, NamedTuple, Optional, Tuple, Union

# 预编译正则表达式提高性能
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
CONTROL_CHARS = {ord(c): None for c in string.ascii_letters + string.digits + ".-_@()"}
INVALID_CHARS_MAP = {ord(c): None for c in '\x00-\x1F\x7F-\x9F\t\n\r'}
REPO_MARKER_PATTERN = re.compile(r'^\s*\*\s+(\w+):\s+')
PACKAGE_VER_REGEX = re.compile(r'^(\d+[.:\-])')

# 包信息命名元组
class PackageInfo(NamedTuple):
    name: str
    version: str
    repo: str


class GenericParser:
    """解析器基类（保留用于未来扩展）"""
    pass


class YumParser(GenericParser):
    """高性能YUM输出解析器（优化版）"""
    
    @staticmethod
    def config_reader(stream: Generator[str, None, None]) -> Generator[Tuple[str, str], None, None]:
        """
        YUM配置读取器（待实现）
        :param stream: 配置文本流
        :return: 键值对生成器
        """
        # TODO: 实现YUM配置解析
        raise NotImplementedError("YUM config reader not implemented")
    
    @staticmethod
    def packages_reader(stream: Generator[str, None, None], 
                       exclude_repos: Optional[List[str]] = None) -> Generator[PackageInfo, None, None]:
        """
        解析YUM包列表输出（性能优化版本）
        :param stream: 文本行生成器
        :param exclude_repos: 要排除的仓库列表
        :return: 包信息生成器
        """
        # 状态标志
        in_package_section = False
        exclude_repos_set = set(exclude_repos) if exclude_repos else None
        
        for line_no, raw_line in enumerate(stream):
            try:
                # 1. 高效清洗输入行
                line = YumParser._sanitize_line(raw_line)
                if not line.strip():
                    continue
                
                # 2. 智能跳过头部信息
                if not in_package_section:
                    if YumParser._is_section_header(line):
                        in_package_section = True
                        continue
                    if REPO_MARKER_PATTERN.match(line):
                        continue  # 跳过仓库镜像标头
                    continue
                
                # 3. 高效解析包行
                parts = line.split(maxsplit=2)
                if len(parts) < 3:
                    continue
                    
                # 处理包名（去除架构信息）
                name_chunk = parts[0]
                if '.' in name_chunk:
                    name = name_chunk[:name_chunk.rindex('.')]
                else:
                    name = name_chunk
                    
                version = parts[1]
                repo_chunk = parts[2]
                
                # 验证关键字段
                if not (name and YumParser._is_valid_version(version)):
                    continue
                
                # 处理仓库名称（移除前缀标记）
                repo = repo_chunk.strip()
                if repo.startswith('@'):
                    repo = repo[1:]
                
                # 应用仓库过滤
                if exclude_repos_set and repo in exclude_repos_set:
                    continue
                
                yield PackageInfo(name, version, repo)
                
            except Exception as e:
                Logger.debug(f"Line parse error (#{line_no}): {str(e)}. Content: '{raw_line[:80]}'")
    
    @staticmethod
    def packages_installed_reader(stream: Generator[str, None, None]) -> Generator[PackageInfo, None, None]:
        """
        已安装包列表解析器（复用主解析逻辑）
        :param stream: 文本行生成器
        :return: 包信息生成器
        """
        # 直接复用通用解析器
        return YumParser.packages_reader(stream)
    
    @staticmethod
    def list_all_select_tool_packages_reader(stream: Generator[str, None, None]) -> Generator[Tuple[str, str], None, None]:
        """
        YUM配置解析器（格式：KEY "VALUE")
        :param stream: 文本行生成器
        :return: 键值对生成器
        """
        for line_no, line in enumerate(stream):
            clean_line = line.strip()
            if not clean_line or clean_line.endswith('"";') or clean_line.endswith('";'):
                continue
                
            try:
                # 分割键值对
                key, value = clean_line.split(maxsplit=1)
                
                # 移除尾部分号及引号
                value = value.split(';', 1)[0].strip('"').strip()
                if not value:
                    continue
                    
                # 标准化键名（去除可能的命名空间）
                if "::" in key:
                    key = key.replace('::', '_')
                
                yield key.rstrip(','), value
            except ValueError:
                pass
    
    # -------------------- 辅助工具方法 -------------------- 
    
    @staticmethod
    def _sanitize_line(line: str) -> str:
        """
        高效清洗输入行
        - 去除ANSI转义码
        - 去除控制字符
        - 避免重复操作
        """
        return ANSI_ESCAPE.sub('', line).translate(INVALID_CHARS_MAP)
    
    @staticmethod
    def _is_section_header(line: str) -> bool:
        """
        检测包列表部分头部标识
        """
        return "Available Packages" in line or \
               "Installed Packages" in line or \
               "Upgraded Packages" in line
    
    @staticmethod
    def _is_valid_version(version_str: str) -> bool:
        """
        高效验证版本号格式
        """
        return bool(PACKAGE_VER_REGEX.match(version_str))
    
    @staticmethod
    def analyze_dependency_tree(output: List[str]) -> Dict[str, List[str]]:
        """
        解析YUM依赖树输出
        :param output: 依赖树文本行列表
        :return: 依赖关系字典
        """
        dep_dict = {}
        current_pkg = None
        
        for line in output:
            line = line.strip()
            if not line:
                continue
                
            # 包名称行
            if "--> " in line:
                parts = line.split('-->', 1)
                current_pkg = parts[0].split()[-1]
                dep = parts[1].split()[0]
                dep_dict.setdefault(current_pkg, []).append(dep)
            # 子树缩进行
            elif line.startswith('|   '):
                if current_pkg:
                    dep = line.replace('|', '').split('.')[0].strip()
                    if dep:
                        dep_dict.setdefault(current_pkg, []).append(dep)
            # 新主树开始
            else:
                current_pkg = line.split()[-1] if ' ' in line else line
                
        return dep_dict
    
    @staticmethod
    def parse_history(output: List[str]) -> List[Dict[str, Union[int, str, List]]]:
        """
        解析YUM历史记录输出
        :param output: 历史记录文本行
        :return: 历史记录字典列表
        """
        history = []
        current = {}
        action_pattern = re.compile(r'^\s+(\d+)\s+(\w+)\s+(\d+:\d+)\s+([\w\d\-: ]+)')
        
        for line in output:
            line = line.strip()
            if not line:
                continue
                
            # 头部信息
            if line.startswith('Transaction ID'):
                if current:
                    history.append(current)
                    current = {}
                
                # 示例: "Transaction ID : 42"
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current['id'] = int(parts[1].strip())
            # 日期信息
            elif line.startswith('Begin time'):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current['begin'] = parts[1].strip()
            # 状态信息
            elif line.startswith('Status'):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current['status'] = parts[1].strip()
            # 操作行解析
            elif action_pattern.match(line):
                matches = action_pattern.findall(line)
                if matches:
                    transaction = matches[0]
                    if 'actions' not in current:
                        current['actions'] = []
                    current['actions'].append({
                        'id': int(transaction[0]),
                        'action': transaction[1],
                        'time': transaction[2],
                        'package': transaction[3]
                    })
        
        if current:
            history.append(current)
            
        return history
    
    @staticmethod
    def parse_update_info(output: List[str]) -> List[Dict[str, str]]:
        """
        解析YUM更新信息
        :param output: 更新信息文本行
        :return: 更新包信息字典列表
        """
        updates = []
        current = {}
        state = None
        key_pattern = re.compile(r'^\s*([A-Z][\w\s]+?)\s*:\s*')
        
        for line in output:
            clean_line = line.strip()
            if not clean_line:
                continue
                
            # 新记录开始
            if clean_line.startswith('='):
                if current:
                    updates.append(current)
                    current = {}
                state = 'head'
            # 头信息行
            elif state == 'head' and clean_line:
                match = key_pattern.search(clean_line)
                if match:
                    state = 'value'
                    key = match.group(1).lower().replace(' ', '_')
                    continue
            # 值信息
            elif state == 'value':
                current[key] = clean_line
                state = 'head'
        
        if current:
            updates.append(current)
            
        return updates
    
    @staticmethod
    def extract_version_info(version_str: str) -> Dict[str, str]:
        """
        从版本字符串中提取详细信息
        :param version_str: 完整版本字符串 (如 '1.2.3-4.el7')
        :return: 版本信息字典
        """
        # 分离版本和发行版
        version, _, release = version_str.partition('-')
        
        # 分离构建信息
        el_version = ""
        for el_prefix in ('.el', 'el', '.fc', 'fc'):
            if el_prefix in release:
                el_parts = release.split(el_prefix)
                release = el_parts[0]
                if len(el_parts) > 1:
                    el_version = el_prefix + el_parts[1]
                break
        
        # 架构检测
        arch = ""
        for known_arch in ('.x86_64', '.noarch', '.aarch64', '.ppc64le'):
            if release.endswith(known_arch):
                arch = known_arch.lstrip('.')
                release = release[:-len(known_arch)]
                break
        
        return {
            'version': version,
            'release': release,
            'build': el_version,
            'arch': arch
        }


