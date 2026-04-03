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
import yaml
import logging
import json
from typing import (
    Any, 
    Optional, 
    Union, 
    List, 
    Dict, 
    Tuple, 
    Pattern
)
from yaml import SafeLoader, safe_dump
from datetime import datetime
from collections.abc import Iterable, Mapping

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [YAML-PROCESSOR] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('yaml_processor')

class YamlSyntax:
    """YAML 语法模式定义"""
    # 预编译正则表达式提高性能
    LIST_REGEX: Pattern = re.compile(r"^\s*\[\s*[\s\S]*\s*\]\s*$")
    DICT_REGEX: Pattern = re.compile(r"^\s*\{\s*[\s\S]*\s*\}\s*$")
    NESTED_MAP_REGEX: Pattern = re.compile(
        r"^\s*\S+\s*:\s*(?:[^\n]*\n)?(?:\s*\S+\s*:\s*){2,}", 
        re.MULTILINE
    )
    TIMESTAMP_REGEX: Pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
    )
    SPECIAL_FLOAT_REGEX: Pattern = re.compile(
        r"^[-+]?(\d*\.\d+|\.\d+|\d+\.?)(?:[eE][-+]?\d+)?$"
    )
    ISO_DATE_REGEX: Pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}$"
    )
    BOOLEAN_VALUES = {
        "null", "Null", "NULL",
        "true", "True", "TRUE",
        "false", "False", "FALSE",
        "yes", "Yes", "YES",
        "no", "No", "NO",
        "on", "On", "ON",
        "off", "Off", "OFF"
    }
    
class YamlProcessor:
    """高级 YAML 处理工具"""
    
    def __init__(self, preserve_quotes: bool = False, safe_mode: bool = True,
                 extended_types: bool = True):
        """
        初始化 YAML 处理器
        
        参数:
            preserve_quotes: 是否保留字符串引号
            safe_mode: 是否启用安全模式 (防止危险结构)
            extended_types: 是否识别扩展类型 (日期、时间等)
        """
        self.preserve_quotes = preserve_quotes
        self.safe_mode = safe_mode
        self.extended_types = extended_types
        self.native_types = (int, float, bool, type(None))
        
    def escape_yaml_value(self, value: Any, indent_level: int = 0) -> str:
        """
        智能转义 YAML 值，根据内容选择最佳表示方式
        
        参数:
            value: 需要转义的值
            indent_level: 嵌套缩进级别
            
        返回:
            转义后的 YAML 字符串
        """
        # 处理基本数据类型
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, float):
            return self._format_float_value(value)
        
        # 处理字符串类型
        if isinstance(value, str):
            return self._process_string_value(value, indent_level)
        
        # 处理日期时间类型
        if isinstance(value, datetime) and self.extended_types:
            return value.isoformat()
        
        # 处理容器类型
        if isinstance(value, list) or isinstance(value, tuple):
            return self._format_list_value(value, indent_level)
        elif isinstance(value, dict) or isinstance(value, Mapping):
            return self._format_dict_value(value, indent_level)
        
        # 默认处理
        return str(value)
    
    def parse_yaml_value(self, yaml_str: str) -> Any:
        """
        解析 YAML 值字符串为 Python 对象
        
        参数:
            yaml_str: YAML 格式的字符串
            
        返回:
            解析后的 Python 对象
        """
        # 空值处理
        if not yaml_str.strip():
            return ""
        
        # 尝试解析为基本数据类型
        try:
            # 使用 SafeLoader 安全解析单值
            return yaml.load(yaml_str, Loader=SafeLoader)
        except Exception as e:
            logger.warning(
                f"无法解析为单值 YAML: {str(e)}, 将作为字符串处理"
            )
            return self._cleanup_yaml_string(yaml_str)
    
    def extract_list_values(self, yaml_str: str) -> Optional[List[Any]]:
        """
        从 YAML 列表字符串中提取值
        
        参数:
            yaml_str: YAML 列表字符串 (如 '[a, b, c]')
            
        返回:
            解析出的列表或 None
        """
        # 尝试完全解析为列表
        try:
            result = yaml.safe_load(yaml_str)
            if isinstance(result, list):
                return result
        except Exception as e:
            logger.debug(f"无法完整解析列表: {str(e)}")
        
        # 回退到正则匹配提取
        return self._extract_via_regex(yaml_str)
    
    def convert_to_json_compatible(self, data: Union[str, List, Dict]) -> Union[Dict, List]:
        """
        将 YAML 数据转换为 JSON 兼容格式
        
        参数:
            data: 原始 YAML 数据或字符串
            
        返回:
            JSON 兼容的数据结构
        """
        # 如果是字符串，则尝试按 YAML 解析
        if isinstance(data, str):
            return self._parse_yaml_string_to_json(data)
        
        # 如果是容器类型，则递归处理
        if isinstance(data, list):
            return [self.convert_to_json_compatible(item) for item in data]
        elif isinstance(data, dict):
            return {key: self.convert_to_json_compatible(value) for key, value in data.items()}
        
        # 基本数据类型直接返回
        return data
    
    def safe_dump(self, data: Any, indent: int = 2) -> str:
        """
        安全序列化数据为 YAML 格式
        
        参数:
            data: 需要序列化的数据
            indent: YAML 缩进级别
            
        返回:
            格式良好的 YAML 字符串
        """
        try:
            if self.safe_mode:
                # 在安全模式下进行数据清洗
                cleaned_data = self._sanitize_yaml_data(data)
                return safe_dump(cleaned_data, indent=indent, allow_unicode=True)
            return safe_dump(data, indent=indent, allow_unicode=True)
        except Exception as e:
            logger.error(f"YAML 序列化失败: {str(e)}")
            # 回退到 JSON 格式
            return json.dumps(data, indent=indent, ensure_ascii=False)
    
    def _process_string_value(self, value: str, indent_level: int) -> str:
        """处理字符串值"""
        # 处理已知的布尔/空值
        if value in YamlSyntax.BOOLEAN_VALUES:
            return value
        
        # 处理日期时间格式
        if self._is_datetime_value(value):
            return value
        
        # 处理 ISO 日期格式
        if self.extended_types and self._is_date_value(value):
            return value
        
        # 特殊列表和字典检测
        if YamlSyntax.LIST_REGEX.match(value) and not self.preserve_quotes:
            return value
        
        if YamlSyntax.DICT_REGEX.match(value) and not self.preserve_quotes:
            return value
        
        # 检测嵌套结构
        if YamlSyntax.NESTED_MAP_REGEX.search(value) and not self.preserve_quotes:
            # 添加适当的缩进
            indent_prefix = '  ' * (indent_level + 1)
            formatted_value = '\n'.join(
                f"{indent_prefix}{line}" 
                for line in value.strip().split('\n')
            )
            return f"\n{formatted_value}"
            
        # 添加引号并转义内部引号
        if '"' in value:
            value = value.replace('"', '\\"')
            return f'"{value}"'
        elif "'" in value:
            value = value.replace("'", "''")
            return f"'{value}'"
        elif '\\' in value:
            value = value.replace("\\", "\\\\")
            return f"'{value}'"
        
        # 需要转义的特殊字符
        if any(char in value for char in ':{}[],*&#?|-<>=!%@^'):
            return f"'{value}'"
        
        # 多行字符串处理
        if '\n' in value:
            indent_prefix = '  ' * (indent_level + 1)
            formatted_value = '\n'.join(
                f"{indent_prefix}{line}" 
                for line in value.split('\n')
            )
            return f"|\n{formatted_value}"

        return value
    
    def _format_list_value(self, value_list: Iterable, indent_level: int) -> str:
        """格式化列表值"""
        indent_prefix = '  ' * (indent_level + 1)
        items = [
            '- ' + self.escape_yaml_value(item, indent_level + 1).lstrip() 
            for item in value_list
        ]
        return '\n'.join(items) if indent_level > 0 else f"[{', '.join(items)}]"
    
    def _format_dict_value(self, value_dict: Mapping, indent_level: int) -> str:
        """格式化字典值"""
        indent_prefix = '  ' * (indent_level + 1)
        items = []
        
        for key, value in value_dict.items():
            # 转义键
            escaped_key = self.escape_yaml_value(key, indent_level)
            escaped_value = self.escape_yaml_value(value, indent_level + 1)
            
            # 处理多行值
            if '\n' in escaped_value:
                items.append(f"{indent_prefix}{escaped_key}: {escaped_value}")
            else:
                items.append(f"{indent_prefix}{escaped_key}: {escaped_value}")
                
        return "\n".join(items)
    
    def _format_float_value(self, value: float) -> str:
        """特殊处理浮点数值"""
        str_value = str(value)
        
        # 避免科学计数法的混淆
        if 'e' in str_value.lower():
            if abs(value) < 1e-6 or abs(value) > 1e15:
                return f"'{str_value}'" if self.preserve_quotes else str_value
            return str_value
        
        # 特殊值处理
        if value == float('inf'):
            return ".inf"
        if value == float('-inf'):
            return "-.inf"
        if value != value:  # NaN
            return ".nan"
            
        return str_value
    
    def _extract_via_regex(self, yaml_str: str) -> Optional[List[Any]]:
        """使用正则表达式提取列表值"""
        # 尝试匹配带引号的值
        quoted_matches = re.findall(r"""['"](.*?)['"]""", yaml_str)
        if quoted_matches:
            return [self._cleanup_yaml_string(m) for m in quoted_matches]
        
        # 尝试匹配无引号的值
        unquoted_matches = re.findall(r""",?([^,\[\]]+?)\s*(?:,|\])""", yaml_str)
        if unquoted_matches:
            cleaned_matches = [m.strip() for m in unquoted_matches if m.strip()]
            
            # 尝试转换可能的基本类型
            converted = []
            for m in cleaned_matches:
                try:
                    # 尝试为每个项解析
                    converted.append(yaml.safe_load(m))
                except:
                    converted.append(m)
                    
            return converted if any(not isinstance(i, str) for i in converted) else cleaned_matches
            
        return None
    
    def _is_datetime_value(self, value: str) -> bool:
        """检查是否为日期时间值"""
        return YamlSyntax.TIMESTAMP_REGEX.match(value) is not None
    
    def _is_date_value(self, value: str) -> bool:
        """检查是否为日期值"""
        return YamlSyntax.ISO_DATE_REGEX.match(value) is not None
    
    def _cleanup_yaml_string(self, value: str) -> str:
        """清理 YAML 字符串"""
        # 移除多余的空白
        cleaned = re.sub(r'\s+', ' ', value).strip()
        
        # 移除首尾引号
        if (cleaned.startswith('"') and cleaned.endswith('"')) or \
           (cleaned.startswith("'") and cleaned.endswith("'")):
            return cleaned[1:-1]
            
        return cleaned
    
    def _sanitize_yaml_data(self, data: Any) -> Any:
        """在安全模式下清洗 YAML 数据"""
        if isinstance(data, dict):
            return {key: self._sanitize_yaml_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_yaml_data(item) for item in data]
        elif isinstance(data, str) and self._is_dangerous_value(data):
            # 对危险值进行清洗
            return "SANITIZED: potential unsafe structure"
        return data
    
    def _is_dangerous_value(self, value: str) -> bool:
        """检测可能危险的 YAML 值"""
        # 检查潜在的序列化攻击（如 Python 的 !!python/object）
        if re.search(r"!!python/\w+", value):
            return True
            
        # 检查执行上下文相关值
        if re.search(r"\{\{\s*[\w\W]+\s*\}\}", value):  # Jinja2 模板
            return True
            
        # 其他潜在危险模式
        dangerous_patterns = [
            r"<\s*%",  # 内联脚本
            r"`.*`",   # 反引号命令执行
            r"\$\(.*\)",  # shell 命令
            r"(\x00|\x1f|\x90)"  # 二进制代码
        ]
        
        return any(re.search(pattern, value) for pattern in dangerous_patterns)
    
    def _parse_yaml_string_to_json(self, yaml_str: str) -> Union[Dict, List, str]:
        """将 YAML 字符串转换为 JSON 兼容格式"""
        # 尝试完整解析为 YAML
        try:
            data = yaml.safe_load(yaml_str)
            return self._convert_to_json(data)
        except Exception as e:
            logger.debug(f"无法完整解析 YAML: {str(e)}")
            
        # 尝试检测列表结构
        if YamlSyntax.LIST_REGEX.match(yaml_str):
            extracted = self._extract_via_regex(yaml_str)
            if extracted is not None:
                return extracted
                
        # 尝试检测字典结构
        if YamlSyntax.NESTED_MAP_REGEX.match(yaml_str):
            # 手动提取键值对
            try:
                lines = yaml_str.strip().split('\n')
                parsed_dict = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        parsed_dict[key.strip()] = value.strip()
                return parsed_dict
            except:
                pass
                
        # 最终回退为字符串
        return self._cleanup_yaml_string(yaml_str)
    
    def _convert_to_json(self, data: Any) -> Any:
        """递归转换数据为 JSON 兼容格式"""
        if isinstance(data, list):
            return [self._convert_to_json(item) for item in data]
        if isinstance(data, dict):
            return {key: self._convert_to_json(value) for key, value in data.items()}
        if isinstance(data, datetime):
            return data.isoformat()
        if isinstance(data, (tuple, set, bytes)):
            return str(data)
        return data


# 使用示例
if __name__ == "__main__":
    processor = YamlProcessor(
        preserve_quotes=False, 
        safe_mode=True, 
        extended_types=True
    )
    
    # 示例数据
    sample_data = {
        "service": {
            "name": "Apache Hadoop",
            "version": "3.3.5",
            "ports": [8080, 8443],
            "config": {
                "env": "production",
                "memory": "16GB"
            }
        },
        "hosts": ["server1", "server2", "server3"],
        "credentials": "admin:secret@123",
        "special_chars": "key:{value}; another[item]",
        "multiline_text": "第一行\n第二行\n第三行",
        "date_value": "2023-06-15",
        "datetime_value": "2023-06-15T14:30:00Z",
        "boolean_value": True,
        "nested_map": {
            "inner": {
                "deep": "value"
            }
        }
    }
    
    def demo_yaml_conversion(processor):
        """演示 YAML 转换功能"""
        print("=== YAML 转义演示 ===")
        
        test_cases = [
            ("admin:secret@123", "包含特殊字符"),
            ("key:{value}; another[item]", "包含 YAML 保留字符"),
            ("true", "布尔值"),
            ("Null", "空值表示"),
            ("3.14159", "浮点数"),
            ("2023-06-15", "日期值"),
            ("2023-06-15T14:30:00Z", "日期时间值"),
            ("[item1, item2, item3]", "列表表示"),
            ("{key: value}", "字典表示"),
            ("multi\nline\ntext", "多行文本"),
        ]
        
        for value, description in test_cases:
            print(f"\n原始值: {value} ({description})")
            escaped = processor.escape_yaml_value(value)
            print(f"转义后: {repr(escaped)}")
        
        # 列表提取演示
        print("\n\n=== 列表提取演示 ===")
        yaml_list_str = "['server1', 'server2', 'server3', 'server4']"
        print(f"原始字符串: {yaml_list_str}")
        parsed_list = processor.extract_list_values(yaml_list_str)
        print(f"解析结果: {parsed_list}")
        
        # JSON 兼容性转换演示
        print("\n\n=== JSON 兼容转换 ===")
        yaml_content = """
        service:
          name: DataService
          version: 1.0
          ports: [8080, 8443]
          config:
            env: production
            debug: false
        timestamp: 2023-06-15T14:30:00Z
        """
        print(f"原始 YAML:\n{yaml_content}")
        json_data = processor.convert_to_json_compatible(yaml_content)
        print(f"JSON 兼容格式:\n{json.dumps(json_data, indent=2)}")
        
        # YAML 序列化演示
        print("\n\n=== YAML 序列化 ===")
        print("Python 数据结构转 YAML:")
        print(processor.safe_dump(sample_data))
    
    # 运行演示
    demo_yaml_conversion(processor)

