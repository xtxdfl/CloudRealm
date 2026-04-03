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

Enhanced Version Management Utilities
"""

import re
import logging
from typing import List, Tuple, Optional, Union

# 日志配置
logger = logging.getLogger("version_utils")
logger.setLevel(logging.INFO)

# 预编译正则表达式提高效率
VERSION_NUM_DELIMITER_RE = r"[\s\-_]"  # 版本号分隔符
LEADING_NONDIGIT_RE = re.compile(r"^\D+")  # 开头的非数字字符
TRAILING_NONDIGIT_RE = re.compile(r"\D+$")  # 结尾的非数字字符
DOT_REPLACE_RE = re.compile(r"[^\d.]+")  # 非数字和点的字符
MAJOR_VERSION_RE = re.compile(r"(\d+\.\d+)")  # 主版本检测

class VersionError(Exception):
    """版本处理异常基类"""
    pass

class NormalizationError(VersionError):
    """版本标准化异常"""
    pass

def normalize_version(
    version_str: str, 
    min_segments: int = 0,
    max_segments: int = 4
) -> List[int]:
    """
    标准化版本字符串为整数列表
    
    流程:
    1. 清理非版本字符
    2. 分割版本段
    3. 转换为整数列表
    4. 按需填充段数
    
    :param version_str: 原始版本字符串
    :param min_segments: 最小段数要求
    :param max_segments: 最大段数限制
    :return: 整数版本段列表
    :raises NormalizationError: 格式错误或不支持版本
    """
    # 空值处理
    if not version_str or not isinstance(version_str, str):
        raise NormalizationError(
            "无效版本字符串: 必须非空字符串"
        )
    
    original = version_str.strip()
    
    try:
        # 清理特殊标记和符号
        clean_str = re.sub(r"\.{2,}", ".", original)  # 处理连续点
        clean_str = DOT_REPLACE_RE.sub("", clean_str)  # 移除非数字点号字符
        clean_str = clean_str.strip(".")
        
        # 验证至少包含一个数字段
        if not clean_str or not any(char.isdigit() for char in clean_str):
            raise ValueError(f"无效版本: 无数字段 - {original}")
        
        # 分割并转换数字段
        segments = []
        for segment in clean_str.split(".")[:max_segments]:
            if segment:  # 跳过空段
                segments.append(int(segment))
        
        # 段数完整性校验
        if not segments:
            raise ValueError(f"无有效数字段: {original}")
            
        # 填充缺失段数为0
        if len(segments) < min_segments:
            padding = min_segments - len(segments)
            segments += [0] * padding
        elif len(segments) > max_segments:
            segments = segments[:max_segments]
            
        return segments
        
    except ValueError as ve:
        raise NormalizationError(
            f"版本转换错误: {original} - {str(ve)}"
        ) from ve
    except Exception as e:
        raise NormalizationError(
            f"未知异常处理版本: {original} - {str(e)}"
        ) from e

def format_stack_version(raw_version: str) -> str:
    """
    标准化处理堆栈版本字符串
    
    :param raw_version: 原始版本字符串
    :return: 标准化版本字符串 (格式 #.#.#.#)
    """
    if not raw_version:
        return ""
    
    original = str(raw_version).strip()
    logger.debug(f"格式化原始版本: {original}")
    
    try:
        # 提取最长的数字序列段
        number_segments = []
        current_segment = []
        
        for char in original:
            if char.isdigit() or char == '.':
                current_segment.append(char)
            elif current_segment:  # 非数字中断当前段
                completed = ''.join(current_segment).strip('.')
                if completed:
                    number_segments.append(completed)
                current_segment = []
        
        # 收集最后一段
        if current_segment:
            completed = ''.join(current_segment).strip('.')
            if completed:
                number_segments.append(completed)
        
        # 选择最长数字段作为主版本候选
        if not number_segments:
            logger.warning(f"无数字段: {original}")
            return ""
            
        version_candidate = max(number_segments, key=len)
        
        # 标准化段数
        normalized = normalize_version(version_candidate, min_segments=2)
        if len(normalized) == 2:
            normalized.extend([0, 0])  # 扩展到四位版本
        return ".".join(map(str, normalized))
        
    except Exception as e:
        logger.error(f"版本格式化失败: {original} - {str(e)}")
        return ""

def compare_versions(
    ver1: str, 
    ver2: str, 
    format_version: bool = False
) -> int:
    """
    比较版本大小
    
    :param ver1: 版本字符串1
    :param ver2: 版本字符串2
    :param format_version: 是否先格式化版本
    :return: 比较结果(-1: ver1<ver2, 0:相等, 1:ver1>ver2)
    """
    try:
        # 格式化版本
        if format_version:
            v1 = format_stack_version(ver1)
            v2 = format_stack_version(ver2)
        else:
            v1, v2 = ver1, ver2
            
        # 获取版本段列表
        v1_segments = normalize_version(v1, min_segments=0)
        v2_segments = normalize_version(v2, min_segments=0)
        
        # 统一长度进行比较
        max_len = max(len(v1_segments), len(v2_segments))
        
        for i in range(max_len):
            v1_val = v1_segments[i] if i < len(v1_segments) else 0
            v2_val = v2_segments[i] if i < len(v2_segments) else 0
            
            if v1_val < v2_val:
                return -1
            elif v1_val > v2_val:
                return 1
        
        return 0  # 所有段相等
            
    except Exception as e:
        logger.error(f"版本比较失败: '{ver1}' vs '{ver2}' - {str(e)}")
        raise VersionError("版本比较无效") from e

def get_major_version(full_version: str) -> Optional[str]:
    """
    提取主版本号
    
    :param full_version: 完整版本字符串
    :return: 主版本字符串 (格式 #.#)
    """
    if not full_version:
        return None
        
    try:
        # 尝试提取标准主版本
        if formatted := format_stack_version(full_version):
            segments = formatted.split('.')
            return f"{segments[0]}.{segments[1]}"
            
        # 备用检测方法
        if match := MAJOR_VERSION_RE.search(full_version):
            major_ver = match.group(1)
            if '.' in major_ver:
                return major_ver
                
        # 版本太短的情况
        if '.' in full_version:
            parts = full_version.split('.')
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                return f"{parts[0]}.{parts[1]}"
                
        logger.warning(f"无法提取主版本: {full_version}")
        return None
        
    except Exception as e:
        logger.error(f"主版本提取失败: {full_version} - {str(e)}")
        return None

def get_current_component_version() -> Optional[str]:
    """
    获取当前组件版本
    
    优先级:
    1. 命令行参数版本
    2. 仓库版本
    3. 堆栈信息
    
    :return: 最佳版本字符串
    """
    from resource_management.core.exceptions import Fail
    from resource_management.libraries.functions.default import default
    from resource_management.libraries.functions.stack_select import (
        get_role_component_current_stack_version
    )
    from resource_management.libraries.functions.repository_util import CommandRepository
    
    version = None
    
    try:
        # 优先级1: 命令行参数版本
        version = default("/commandParams/version", None)
        if version:
            logger.debug(f"通过命令参数获取版本: {version}")
            return str(version)
            
        # 优先级2: 仓库版本
        repo_file = default("/repositoryFile", None)
        if repo_file:
            repository = CommandRepository(repo_file)
            if repository.resolved and is_valid_version(repository.version_string):
                logger.debug(f"通过仓库获取版本: {repository.version_string}")
                return repository.version_string
                
        # 优先级3: 堆栈版本
        try:
            version = get_role_component_current_stack_version()
            if version:
                logger.debug(f"通过堆栈选择获取版本: {version}")
                return version
        except Fail as fe:
            logger.warning(f"堆栈版本获取失败: {str(fe)}")
        except TypeError as te:
            logger.warning(f"堆栈版本类型错误: {str(te)}")
            
        logger.warning("无法确定当前组件版本")
        return None
        
    except Exception as e:
        logger.exception("组件版本获取关键异常")
        return version

def is_valid_version(version: str) -> bool:
    """验证版本字符串是否有效"""
    try:
        return bool(normalize_version(version))
    except:
        return False


# ============= 单元测试 =============
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    def test_normalization():
        print("\n=== 版本标准化测试 ===")
        test_cases = [
            ("2.2", [2, 2]),
            ("GlusterFS", []),
            ("2.0.6.GlusterFS", [2, 0, 6]),
            ("2.2.0.1-885", [2, 2, 0, 1]),
            ("HDP-2.3.4.0", [2, 3, 4, 0]),
            ("4.1", [4, 1]),
            ("3..0", [3, 0]),
            ("5.0-alpha", [5, 0]),
        ]
        
        for input_val, expected in test_cases:
            try:
                result = normalize_version(input_val)
                status = "通过" if result == expected else f"失败: 期望{expected} 得到{result}"
                print(f"{input_val:>15} => {status}")
            except VersionError as ve:
                status = "无效" if not expected else "错误"
                print(f"{input_val:>15} => {status}: {str(ve).split(':')[-1].strip()}")
    
    def test_formatting():
        print("\n=== 版本格式化测试 ===")
        tests = [
            (None, ""),
            ("", ""),
            ("2.2", "2.2.0.0"),
            ("2", "2.0.0.0"),  # 单版本号
            ("2.0.6", "2.0.6.0"),
            ("2.1", "2.1.0.0"),
            ("GlusterFS", ""),
            ("2.0.6.GlusterFS", "2.0.6.0"),
            ("2.2.0.1-885", "2.2.0.1"),
            ("HDP-2.3.4.0", "2.3.4.0"),
            ("BigInsights-4.0", "4.0.0.0"),
            ("v3.5.0-preview", "3.5.0.0"),
        ]
        
        for input_val, expected in tests:
            result = format_stack_version(input_val)
            status = "通过" if result == expected else f"失败: 期望{expected} 得到{result}"
            print(f"{str(input_val):>20} => {result:>12} | {status}")
    
    def test_comparison():
        print("\n=== 版本比较测试 ===")
        test_pairs = [
            ("2.2", "2.2.0", 0),
            ("2.0", "2.1", -1),
            ("2.3.4", "2.3.3", 1),
            ("1.9", "2.0", -1),
            ("3.0", "3.0.0", 0),
            ("4.0.1", "4.0.0", 1),
            ("HDP-2.2", "2.1.0", 1),
        ]
        
        for v1, v2, expected in test_pairs:
            result = compare_versions(v1, v2, True)
            sign = '=' if expected == 0 else '>' if expected > 0 else '<'
            status = "通过" if result == expected else f"失败: 期望{sign} 得到{result}"
            print(f"{v1:>10} vs {v2:<10} : 结果={result} | {status}")
    
    def test_major_version():
        print("\n=== 主版本提取测试 ===")
        tests = [
            ("2.1.3.0", "2.1"),
            ("2.2.0.1-885", "2.2"),
            ("HDP-3.1.5.0", "3.1"),
            ("4.0", "4.0"),  # 短版本处理
            ("InvalidVersion", None),
        ]
        
        for input_val, expected in tests:
            result = get_major_version(input_val)
            status = "通过" if result == expected else f"失败: 期望{expected} 得到{result}"
            print(f"{input_val:>15} => {str(result):<6} | {status}")
    
    test_normalization()
    test_formatting()
    test_comparison()
    test_major_version()
