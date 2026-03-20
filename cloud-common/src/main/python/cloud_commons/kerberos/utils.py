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
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union

class ConfigUtils:
    """高级配置处理实用工具类"""
    
    @staticmethod
    def get_property_value(
        dictionary: Dict[str, Any],
        property_name: str,
        default_value: Any = None,
        *,
        trim_type: Optional[str] = "auto",
        nullable: bool = False,
        empty_value: Any = ""
    ) -> Any:
        """
        增强型属性获取器
        - 支持自动类型检测与处理
        - 可选空值处理策略
        
        :param dictionary: 源数据字典
        :param property_name: 属性键名
        :param default_value: 默认返回值
        :param trim_type: 可选处理类型 ('auto', 'string', 'whitespace', None)
        :param nullable: 是否允许返回None值
        :param empty_value: 空值替换值
        :return: 处理后的属性值
        """
        # 获取原始值
        value = dictionary.get(property_name, default_value)
        
        # 值处理逻辑
        if value is None:
            if nullable:
                return None
            return empty_value
        
        # 类型敏感处理
        if trim_type is not None:
            if trim_type == "auto":
                if isinstance(value, (str, list, tuple)):
                    return ConfigUtils._auto_trim(value, empty_value)
            
            elif trim_type == "whitespace" and isinstance(value, str):
                value = value.strip()
                
            elif trim_type == "string":
                value = str(value).strip()
        
        # 空值条件检查
        if value == "" and empty_value != "":
            return empty_value
        
        return value

    @staticmethod
    def _auto_trim(value: Any, empty_value: Any) -> Any:
        """智能值修剪器"""
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or empty_value
            
        elif isinstance(value, (list, tuple)):
            # 递归处理嵌套结构
            return [ConfigUtils._auto_trim(v, empty_value) for v in value]
            
        return value
   
    @staticmethod
    def get_structured_properties(
        dictionary: Dict[str, Any],
        prefix: str,
        *,
        flatten_objects: bool = True,
        array_delimiter: str = ",",
        deep_copy: bool = False,
        ignore_case: bool = False
    ) -> Dict[str, Any]:
        """
        结构化分组配置提取器
        - 支持嵌套对象重建
        - 带前缀数组的智能展开
        
        :param dictionary: 源数据字典
        :param prefix: 配置前缀（自动添加尾部斜线）
        :param flatten_objects: 是否展开嵌套对象
        :param array_delimiter: 数组值分隔符
        :param deep_copy: 是否创建原始数据副本
        :param ignore_case: 是否忽略大小写
        :return: 结构化字典
        """
        full_prefix = f"{prefix.rstrip('/')}/" if not prefix.endswith('/') else prefix
        prefix_len = len(full_prefix)
        prefix_match = full_prefix.lower() if ignore_case else full_prefix
        
        result_dict = {}
        
        # 遍历所有匹配键
        for key, value in dictionary.items():

            # 大小写敏感处理
            key_check = key.lower() if ignore_case else key
            if not key_check.startswith(prefix_match):
                continue

            subkey = key[prefix_len:]
            if not subkey:
                continue  # 跳过完全匹配键
            
            # 创建/更新结果结构
            current_dict = result_dict
            if deep_copy:
                value = value.copy() if hasattr(value, 'copy') else value
            
            parts = subkey.split('/', 2)  # 最多分解两级
            
            for i, part in enumerate(parts):
                # 数组解析逻辑
                is_index = None
                if part.startswith('[') and part.endswith(']'):
                    if part[1:-1].isdigit():
                        is_index = part[1:-1]
                
                # 对象构建
                if i == len(parts) - 1:  # 最后一级
                    if array_delimiter and isinstance(value, str):
                        # 自动检测数组类型
                        if array_delimiter in value and not value.lstrip().startswith('{'):
                            value = [v.strip() for v in value.split(array_delimiter)]
                    
                    if is_index is not None and not flatten_objects:
                        # 数组值处理
                        if part not in current_dict:
                            current_dict[part] = []
                        if int(is_index) >= len(current_dict[part]):
                            current_dict[part] += [None] * (int(is_index) - len(current_dict[part]) + 1)
                        current_dict[part][int(is_index)] = value
                    else:
                        # 简单键值
                        current_key = part.replace('[', '').replace(']', '')
                        current_dict[current_key] = value
                else:
                    # 中间级
                    if part not in current_dict:
                        current_dict[part] = {}
                    current_dict = current_dict[part]
        
        return result_dict

    @staticmethod
    def parse_host_spec(
        host_spec: str,
        *,
        default_port: Optional[int] = None,
        force_ipv6: bool = False,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        增强型主机规范解析器
        - 支持所有主机格式: IPv4, IPv6, 域名
        - 可选格式验证
        - 自动识别封装格式
        
        :param host_spec: 主机字符串
        :param default_port: 默认端口
        :param force_ipv6: 是否强制解析为IPv6
        :param validate: 是否执行基本格式验证
        :return: 包含完整信息的字典
        """
        if not host_spec:
            return {"host": "", "port": default_port}
        
        # IPv6封装格式处理 (如: [2001:db8::1]:80)
        if force_ipv6 or (host_spec.startswith('[') and ']' in host_spec):
            host_with_port = host_spec
            if host_with_port.count(']') > 1:  # 格式错误
                return {"error": f"Invalid IPv6 format: {host_spec}"}
            
            # 分离主机与端口
            if ']:' in host_with_port:
                host_part, port_part = host_with_port.rsplit(']:', 1)
                host = host_part.lstrip('[')
                port = int(port_part) if port_part.isdigit() else default_port
            else:
                host = host_with_port.strip('[]')
                port = default_port
            
            return {
                "host": host,
                "port": port,
                "type": "ipv6" if force_ipv6 or ':' in host else "domain",
                "original": host_spec
            }
        
        # 标准主机:端口格式
        port = None
        host = host_spec
        
        # 检查端口部分
        if ':' in host_spec:
            last_colon = host_spec.rfind(':')
            if last_colon > host_spec.rfind(']') and '/' not in host_spec[last_colon:]:
                port_part = host_spec[last_colon+1:]
                if port_part.isdigit() and 1 <= int(port_part) <= 65535:
                    try:
                        port = int(port_part)
                        host = host_spec[:last_colon]
                    except ValueError:
                        pass
        
        # 类型推断
        host_type = "ipv4" if re.match(r'\d{1,3}(\.\d{1,3}){3}$', host) else (
            "ipv6" if ':' in host else "domain"
        )
        
        # DNS域名验证
        if validate:
            if host_type == "domain" and not re.match(
                r'^([a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z0-9]{2,}$', 
                host, 
                re.IGNORECASE
            ):
                host_type = "invalid"
        
        return {
            "host": host,
            "port": port or default_port,
            "type": host_type,
            "original": host_spec
        }

    @staticmethod
    def set_host_port(
        host_spec: str,
        port: Union[int, str, None],
        *,
        preserve_ipv6: bool = True,
        format_as_url: bool = False
    ) -> str:
        """
        高级主机端口设置器
        - 智能保留原格式
        - 支持URL格式化输出
        
        :param host_spec: 原始主机字符串
        :param port: 目标端口值
        :param preserve_ipv6: 是否保留IPv6封装格式
        :param format_as_url: 是否返回完整URL格式 (host:port)
        :return: 更新后的主机字符串
        """
        if not host_spec or ',' in host_spec:
            # 处理多主机情况
            return ','.join(ConfigUtils.set_host_port(h, port) for h in host_spec.split(','))
        
        # 解析现有信息
        parsed = ConfigUtils.parse_host_spec(host_spec)
        
        # 转换端口
        if port is None:
            port = parsed.get("port")
        elif isinstance(port, str):
            port = int(port) if port.isdigit() else None
        
        # 特殊端口处理
        if port == 80 and format_as_url:
            port = None
        
        # 格式构建
        host = parsed["host"]
        
        # IPv6格式化选择
        if preserve_ipv6 and parsed["type"] == "ipv6" and ':' in host:
            host = f"[{host}]"
        
        # 端口处理
        if port is not None:
            return f"{host}:{port}" if not format_as_url else f"{host}:{port}"
        
        # URL格式特殊处理
        if format_as_url and parsed.get("port") and parsed["port"] not in (80, 443):
            return f"{host}:{parsed['port']}"
        
        return host

    @staticmethod
    def transform_dict_keys(
        data: Dict[str, Any], 
        *,
        case_style: str = "snake_case",
        prefix: str = "",
        strip_keys: bool = True
    ) -> Dict[str, Any]:
        """
        字典键名转换工具
        - 支持多种命名风格转换
        - 可选键名前缀/后缀
        
        :param data: 源字典
        :param case_style: 目标命名风格 (snake_case, camelCase, PascalCase, kebab-case)
        :param prefix: 键名前缀
        :param strip_keys: 是否清理键名
        :return: 转换后的字典
        """
        result = {}
        
        for key, value in data.items():
            # 键名清理
            if strip_keys:
                key = key.strip()
                
            # 嵌套字典处理
            if isinstance(value, dict):
                value = ConfigUtils.transform_dict_keys(value, case_style=case_style)
            # 列表中的字典处理
            elif isinstance(value, list):
                value = [
                    ConfigUtils.transform_dict_keys(v, case_style=case_style) 
                    if isinstance(v, dict) else v
                    for v in value
                ]
            
            # 应用命名风格转换
            transformed_key = ConfigUtils.convert_case(key, case_style)
            full_key = f"{prefix}{transformed_key}" if prefix else transformed_key
            
            result[full_key] = value
        
        return result

    @staticmethod
    def convert_case(key: str, style: str) -> str:
        """键名风格转换器"""
        # 清理特殊字符
        key = re.sub(r'[^\w\s-]', '', key)
        
        # 风格检测
        is_camel = re.match(r'^[a-z]+([A-Z][a-z]*)+$', key)
        is_pascal = re.match(r'^[A-Z][a-z]+([A-Z][a-z]*)*$', key)
        is_snake = '_' in key
        is_kebab = '-' in key
        
        # 风格转换逻辑
        words = []
        
        if is_snake:
            words = key.split('_')
        elif is_kebab:
            words = key.split('-')
        elif is_camel or is_pascal:
            words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', key)
        else:
            words = [key]
        
        # 清理空词
        words = [w for w in words if w]
        
        # 应用目标风格
        if style == "snake_case":
            return '_'.join(w.lower() for w in words)
        elif style == "camelCase":
            return words[0].lower() + ''.join(w.capitalize() for w in words[1:])
        elif style == "PascalCase":
            return ''.join(w.capitalize() for w in words)
        elif style == "kebab-case":
            return '-'.join(w.lower() for w in words)
        else:
            return key  # 未知风格返回原值

    @staticmethod
    def deep_merge_dicts(
        base_dict: Dict[str, Any], 
        override_dict: Dict[str, Any], 
        *,
        priority: str = "override",
        array_strategy: str = "combine",
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        深度字典合并工具
        - 支持多种合并策略
        - 可配置的数组处理
        - 深度控制
        
        :param base_dict: 基础字典
        :param override_dict: 覆盖字典
        :param priority: 优先策略 (base|override|extend)
        :param array_strategy: 数组策略 (combine|replace|union)
        :param max_depth: 最大递归深度
        :return: 合并后的字典
        """
        if max_depth <= 0:
            return override_dict if priority == "override" else base_dict
        
        merged = base_dict.copy()
        
        for key, value in override_dict.items():
            # 处理嵌套字典
            if (key in base_dict and 
                isinstance(base_dict[key], dict) and 
                isinstance(value, dict)):
                
                merged[key] = ConfigUtils.deep_merge_dicts(
                    base_dict[key], 
                    value, 
                    priority=priority,
                    array_strategy=array_strategy,
                    max_depth=max_depth-1
                )
                
            # 处理数组
            elif (array_strategy != "replace" and
                  key in base_dict and 
                  isinstance(base_dict[key], list) and 
                  isinstance(value, list)):
                
                if array_strategy == "combine":
                    merged[key] = base_dict[key] + value
                elif array_strategy == "union":
                    merged[key] = list(set(base_dict[key] + value))
                else:  # replace
                    merged[key] = value
                    
            # 简单值处理
            elif key in base_dict:
                if priority == "override":
                    merged[key] = value
                elif priority == "base":
                    pass  # 保留基础值
                elif priority == "extend" and isinstance(value, set):
                    if not isinstance(merged[key], set):
                        merged[key] = set(merged[key])
                    merged[key] |= value
                elif priority == "extend" and isinstance(value, list):
                    if not isinstance(merged[key], list):
                        merged[key] = [merged[key]]
                    merged[key].extend(value)
                elif priority == "extend":
                    if isinstance(merged[key], list):
                        merged[key].append(value)
                    elif isinstance(merged[key], set):
                        merged[key].add(value)
                    else:
                        merged[key] = [merged[key], value]
            else:
                merged[key] = value
        
        return merged
