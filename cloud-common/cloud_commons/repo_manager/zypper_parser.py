#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from typing import Dict, Generator, List, Tuple, Optional
from .generic_parser import GenericParser, ANSI_ESCAPE, REMOVE_CHARS

class ZypperParser(GenericParser):
    # 正则表达式模式预编译
    PACKAGE_PATTERN = re.compile(
        r'\s*[iv]+\s*\|\s*(\S[^|]+)\s*\|\s*package\s*\|\s*(\S[^|]+)\s*\|\s*\S+\s*\|\s*(\S[^|]+)'
    )
    REPO_PATTERN = re.compile(
        r'\s*\d+\s*\|\s*(\S[^|]+)\s*\|\s*(\S[^|]+)\s*\|\s*(Yes|No)\s*\|\s*(Yes|No)'
    )
    HEADER_DIVIDER = re.compile(r'-+\+-+')
    
    # 包状态映射
    PACKAGE_STATUS_MAP = {
        'i': 'installed',
        'v': 'virtual',
        ' ': 'available'
    }

    @classmethod
    def _sanitize_line(cls, line: str) -> str:
        """移除 ANSI 转义码和不需要的字符"""
        return ANSI_ESCAPE.sub("", line).translate(str.maketrans('', '', REMOVE_CHARS))
    
    @classmethod
    def config_reader(cls, stream) -> Dict[str, str]:
        """解析 zypper 配置文件（待实现）
        
        Args:
            stream: 输入流（文件或列表）
        
        Returns:
            包含配置键值对的字典
        """
        raise NotImplementedError("Zypper 配置文件解析暂未实现")
    
    @classmethod
    def packages_reader(
        cls, 
        stream: Generator[str, None, None], 
        filter_status: Optional[List[str]] = None
    ) -> Generator[Tuple[str, str, str], None, None]:
        """解析 zypper 包列表输出
        
        Args:
            stream: 输入行迭代器
            filter_status: 过滤包状态 ['installed', 'available']

        Yields:
            包含 (包名, 版本, 仓库) 的元组
        """
        in_package_section = False
        
        for line in stream:
            clean_line = cls._sanitize_line(line)
            
            # 检测头部分割线
            if cls.HEADER_DIVIDER.match(clean_line):
                in_package_section = True
                continue
                
            if not in_package_section:
                continue
            
            # 尝试模式匹配
            match = cls.PACKAGE_PATTERN.match(clean_line)
            if match:
                pkg_name, pkg_version, repo_name = match.groups()
                status_char = clean_line.split('|', 1)[0].strip()[0]
                
                # 状态过滤
                pkg_status = cls.PACKAGE_STATUS_MAP.get(status_char, 'unknown')
                if filter_status and pkg_status not in filter_status:
                    continue
                
                yield pkg_name.strip(), pkg_version.strip(), repo_name.strip()
    
    @classmethod
    def packages_installed_reader(
        cls, 
        stream: Generator[str, None, None]
    ) -> Generator[Tuple[str, str, str], None, None]:
        """仅解析已安装的包
        
        Args:
            stream: 输入行迭代器

        Yields:
            包含 (包名, 版本, 仓库) 的元组
        """
        yield from cls.packages_reader(stream, filter_status=['installed'])
    
    @staticmethod
    def lookup_packages(lines, skip_till="--+--"):
        """
        废弃方法（保留用于向后兼容）
        
        Args:
            lines: 文本行列表
            skip_till: 起始分隔符
            
        Returns:
            包信息列表
        """
        packages = []
        skip_index = None

        for index, line in enumerate(lines):
            if skip_till in line:
                skip_index = index + 1
                break

        if skip_index:
            for line in lines[skip_index:]:
                items = line.strip(" \t\n\r").split("|")
                if len(items) >= 5:
                    packages.append([items[1].strip(), items[3].strip(), items[5].strip()])

        return packages
    
    @classmethod
    def repo_list_reader(
        cls, 
        stream: Generator[str, None, None]
    ) -> Generator[Tuple[str, str, bool, bool], None, None]:
        """解析 zypper 仓库列表输出
        
        Args:
            stream: 输入行迭代器

        Yields:
            包含 (仓库别名, 仓库名, 启用状态, 刷新状态) 的元组
        """
        in_repo_section = False
        skip_columns = False
        
        for line in stream:
            clean_line = cls._sanitize_line(line)
            
            # 检测头部分割线
            if cls.HEADER_DIVIDER.match(clean_line):
                in_repo_section = True
                skip_columns = "GPG" in line or "GPG" in clean_line
                continue
                
            if not in_repo_section:
                continue
            
            # 尝试模式匹配
            match = cls.REPO_PATTERN.match(clean_line)
            if match:
                repo_alias, repo_name, enabled_str, refresh_str = match.groups()
                
                # 处理额外列的情况
                if skip_columns:
                    *_, repo_name, enabled_str, refresh_str = clean_line.split('|', 5)[1:6]
                    enabled_str = enabled_str.strip()
                    refresh_str = refresh_str.split('|')[0].strip() if '|' in refresh_str else refresh_str.strip()
                
                enabled = enabled_str.lower() in ('yes', 'true', '1', 'enabled')
                refresh = refresh_str.lower() in ('yes', 'true', '1', 'enabled')
                
                yield repo_alias.strip(), repo_name.strip(), enabled, refresh
    
    @classmethod
    def parse_patch_info(
        cls, 
        stream: Generator[str, None, None]
    ) -> Generator[Dict[str, str], None, None]:
        """解析 zypper 补丁信息（新增方法）
        
        Args:
            stream: 输入行迭代器

        Yields:
            补丁信息字典
        """
        # 示例实现，具体业务逻辑依据实际输出格式
        patch_info = {}
        pattern = re.compile(r'(\w[\w\s-]+)\s*\|\s*([A-Z]+)\s*\|\s*([\d\.-]+)')

        for line in stream:
            clean_line = cls._sanitize_line(line)
            match = pattern.match(clean_line)
            if match:
                patch_info = {
                    'package': match.group(1).strip(),
                    'severity': match.group(2).strip(),
                    'version': match.group(3).strip()
                }
                yield patch_info
    
    @classmethod
    def parse_dependency_tree(
        cls, 
        stream: Generator[str, None, None],
        package_name: str
    ) -> Dict[str, List[str]]:
        """解析包依赖树（新增方法）
        
        Args:
            stream: 输入行迭代器
            package_name: 目标包名

        Returns:
            依赖关系字典
        """
        dep_tree = {}
        current_package = package_name
        dep_pattern = re.compile(r'├──\s*(\S+)|\└──\s*(\S+)')
        
        for line in stream:
            clean_line = cls._sanitize_line(line)
            
            # 检测主要包
            if line.startswith(package_name):
                dep_tree[current_package] = []
                continue
            
            # 检测依赖
            match = dep_pattern.search(clean_line)
            if match:
                dep_name = match.group(1) or match.group(2)
                if dep_name and dep_name != "`":
                    dep_tree[current_package].append(dep_name)
        
        return dep_tree

