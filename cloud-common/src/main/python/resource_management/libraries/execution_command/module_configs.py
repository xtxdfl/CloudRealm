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

高级模块配置管理系统
"""

from typing import Any, Dict, List, Optional, Union, Tuple
from collections import defaultdict

class ModuleConfigs:
    """
    模块配置管理器
    
    此类提供对服务配置和配置属性的统一访问接口，支持：
    - 配置值和属性的高效查询
    - 类型安全的属性访问
    - 配置验证和变更检测
    - 敏感数据处理
    
    数据源结构：
        configurations: {
            "config-type1": {
                "property1": "value1",
                "property2": "value2"
            },
            "config-type2": {...}
        }
        
        configurationAttributes: {
            "config-type1": {
                "property1": {
                    "type": "string", 
                    "required": true
                },
                "property2": {...}
            },
            "config-type2": {...}
        }
    """

    def __init__(self, configs: Dict[str, Dict], config_attributes: Dict[str, Dict]):
        """
        初始化模块配置管理器
        
        :param configs: 配置字典，格式为 {config_type: {property: value}}
        :param config_attributes: 配置属性字典，格式为 {config_type: {property: attributes}}
        """
        # 原始配置数据
        self._raw_configs = configs or {}
        self._raw_attributes = config_attributes or {}
        
        # 索引结构
        self._config_index = self._build_config_index()
        self._attribute_index = self._build_attribute_index()

    def _build_config_index(self) -> Dict[Tuple, Any]:
        """构建(配置类型, 属性名)到配置值的索引"""
        index = {}
        for config_type, properties in self._raw_configs.items():
            for prop, value in properties.items():
                index[(config_type, prop)] = value
        return index

    def _build_attribute_index(self) -> Dict[Tuple, Dict]:
        """构建(配置类型, 属性名)到属性元数据的索引"""
        index = {}
        for config_type, properties in self._raw_attributes.items():
            for prop, attrs in properties.items():
                index[(config_type, prop)] = attrs
        return index

    @property
    def all_config_types(self) -> List[str]:
        """获取所有配置类型列表"""
        return list(self._raw_configs.keys())

    @property
    def all_attributes_config_types(self) -> List[str]:
        """获取所有包含属性的配置类型列表"""
        return list(self._raw_attributes.keys())

    def get_raw_config_dict(self) -> Dict[str, Dict]:
        """获取原始配置字典"""
        return self._raw_configs

    def get_raw_attribute_dict(self) -> Dict[str, Dict]:
        """获取原始属性字典"""
        return self._raw_attributes

    def get_all_configs_for_type(self, config_type: str) -> Dict[str, Any]:
        """
        获取指定配置类型的所有属性
        
        :param config_type: 配置类型
        :return: 属性值与配置字典
        """
        return self._raw_configs.get(config_type, {}).copy()

    def get_all_attributes_for_type(self, config_type: str) -> Dict[str, Dict]:
        """
        获取指定配置类型的所有属性元数据
        
        :param config_type: 配置类型
        :return: 属性元数据字典
        """
        return self._raw_attributes.get(config_type, {}).copy()

    def get_property(
        self, 
        config_type: str, 
        property_name: str, 
        default: Any = None
    ) -> Any:
        """
        获取特定属性值
        
        :param config_type: 配置类型
        :param property_name: 属性名称
        :param default: 默认值
        :return: 配置值或默认值
        """
        return self._config_index.get((config_type, property_name), default)

    def get_property_with_metadata(
        self, 
        config_type: str, 
        property_name: str
    ) -> Dict[str, Any]:
        """
        获取属性及其元数据
        
        :param config_type: 配置类型
        :param property_name: 属性名称
        :return: 包含值和元数据的字典
        """
        value = self.get_property(config_type, property_name)
        attributes = self.get_property_attributes(config_type, property_name)
        
        return {
            "value": value,
            "attributes": attributes,
            "is_sensitive": attributes.get("sensitive", False),
            "is_required": attributes.get("required", False),
            "config_type": config_type
        }

    def get_property_attributes(
        self, 
        config_type: str, 
        property_name: str
    ) -> Dict:
        """获取属性的元数据信息"""
        return self._attribute_index.get((config_type, property_name), {})

    def get_properties(
        self, 
        config_type: str, 
        property_names: List[str], 
        default: Any = None
    ) -> Dict[str, Any]:
        """
        批量获取多个属性值
        
        :param config_type: 配置类型
        :param property_names: 属性名称列表
        :param default: 默认值
        :return: 属性字典 {property: value}
        """
        return {
            prop: self.get_property(config_type, prop, default)
            for prop in property_names
        }

    def get_resources_by_type(self, resource_type: str) -> List[Dict]:
        """
        按资源类型检索资源
        
        :param resource_type: 资源类型名称 (如 "hdfs-site" 或 "yarn-site")
        :return: 资源字典列表
        """
        if resource_type not in self._raw_configs:
            return []
            
        return [{
            "type": resource_type,
            "properties": self._raw_configs[resource_type]
        }]

    def validate_required_properties(self) -> Dict:
        """验证所有必需属性是否已配置"""
        missing = defaultdict(list)
        
        for (config_type, prop), attrs in self._attribute_index.items():
            if attrs.get("required") and self.get_property(config_type, prop) is None:
                missing[config_type].append(prop)
                
        return dict(missing)

    def detect_config_changes(self, old_configs: Dict) -> Dict[str, Dict]:
        """
        检测配置变更
        
        :param old_configs: 先前配置字典
        :return: 变更报告
        """
        changes = {
            "added": defaultdict(dict),
            "removed": defaultdict(dict),
            "modified": defaultdict(dict)
        }
        
        # 检测新增配置
        for config_type, props in self._raw_configs.items():
            if config_type not in old_configs:
                changes["added"][config_type] = props
                continue
                
            for prop, value in props.items():
                old_value = old_configs[config_type].get(prop)
                if old_value is None:
                    changes["added"][config_type][prop] = value
                elif old_value != value:
                    changes["modified"][config_type][prop] = {
                        "old": old_value,
                        "new": value
                    }
        
        # 检测被移除的配置
        for config_type, props in old_configs.items():
            if config_type not in self._raw_configs:
                changes["removed"][config_type] = props
                continue
                
            for prop, value in props.items():
                if prop not in self._raw_configs.get(config_type, {}):
                    changes["removed"][config_type][prop] = value
        
        return changes

    def mask_sensitive_data(self, config: Optional[Dict] = None) -> Dict:
        """
        掩码敏感数据
        
        :param config: 可选-指定配置字典，默认为当前配置
        :return: 掩码后的配置
        """
        masked_config = (config if config is not None else self._raw_configs).copy()
        
        for config_type, props in list(masked_config.items()):
            if not isinstance(props, dict):
                continue
                
            for prop, attributes in self._raw_attributes.get(config_type, {}).items():
                if attributes.get("sensitive") and prop in props:
                    masked_config[config_type][prop] = "******"
                    
        return masked_config

    def get_dependencies(self, config_type: str) -> List[str]:
        """获取配置依赖关系"""
        attributes = self._raw_attributes.get(config_type, {})
        return attributes.get("dependencies", [])
    
    def resolve_expression(self, expression: str) -> Optional[Any]:
        """
        解析配置表达式
        
        :param expression: 形如 "${config-type/property}" 的表达式
        :return: 解析后的值或None
        """
        if not expression.startswith("${") or not expression.endswith("}"):
            return expression
            
        ref_path = expression[2:-1].strip()
        if "/" not in ref_path:
            return expression
            
        parts = ref_path.split("/", 1)
        config_type, property_name = parts[0], parts[1]
        return self.get_property(config_type, property_name)
    
    def to_full_path(self, relative_path: str) -> Optional[str]:
        """
        将相对路径解析为绝对路径
        
        :param relative_path: 相对路径
        :return: 绝对路径或None
        """
        # 实际实现中需要根据具体环境解析路径
        return relative_path if relative_path.startswith("/") else f"/opt/configs/{relative_path}"


class SecureModuleConfigs(ModuleConfigs):
    """安全增强型模块配置管理"""
    
    SECURE_PROPERTIES = {"password", "secret", "key", "credential", "token"}
    ENCRYPTION_KEY = "config_encryption_key"
    
    def __init__(self, configs, config_attributes, encryption_key=None):
        super().__init__(configs, config_attributes)
        self.encryption_key = encryption_key or self._detect_encryption_key()
        self._decrypted_cache = {}
        
    def _detect_encryption_key(self) -> Optional[str]:
        """从安全存储中检索加密密钥"""
        # 实际实现中使用安全存储检索
        return self.get_property("security", self.ENCRYPTION_KEY)
    
    def get_property(self, config_type, property_name, default=None) -> Any:
        """获取属性值（自动解密敏感数据）"""
        value = super().get_property(config_type, property_name, default)
        
        # 检查是否为敏感属性
        if not self._is_sensitive_property(config_type, property_name):
            return value
            
        # 如果已解密则返回缓存
        cache_key = (config_type, property_name)
        if cache_key in self._decrypted_cache:
            return self._decrypted_cache[cache_key]
            
        # 非加密值直接返回
        if not isinstance(value, str) or not value.startswith("ENC|"):
            self._decrypted_cache[cache_key] = value
            return value
            
        # 解密敏感值
        try:
            decrypted = self._decrypt(value)
            self._decrypted_cache[cache_key] = decrypted
            return decrypted
        except Exception as e:
            return value
    
    def _is_sensitive_property(self, config_type, property_name) -> bool:
        """检查属性是否为敏感属性"""
        # 基于元数据标记
        attrs = self.get_property_attributes(config_type, property_name)
        if attrs.get("sensitive"):
            return True
            
        # 基于属性名推断
        if any(kw in property_name.lower() for kw in self.SECURE_PROPERTIES):
            return True
            
        return False
    
    def _decrypt(self, encrypted_value: str) -> Optional[str]:
        """实际解密方法（占位实现）"""
        if not encrypted_value.startswith("ENC|"):
            return encrypted_value
            
        if not self.encryption_key:
            raise ValueError("No encryption key available")
            
        # 实际实现中使用环境特定的解密机制
        data = encrypted_value[4:]
        # 解密实现
        return f"DECRYPTED_{data}"


# =================== 配置管理实用工具 ===================
class ConfigManagerUtils:
    """配置管理实用工具类"""
    
    @staticmethod
    def flatten_configs(configs: Dict) -> Dict:
        """展平层级配置结构"""
        flat = {}
        for config_type, props in configs.items():
            for prop, value in props.items():
                flat[f"{config_type}.{prop}"] = value
        return flat
    
    @staticmethod
    def unflatten_configs(flat_configs: Dict) -> Dict:
        """将扁平配置恢复层级结构"""
        hierarchical = defaultdict(dict)
        for key, value in flat_configs.items():
            if "." not in key:
                continue
            config_type, prop = key.split(".", 1)
            hierarchical[config_type][prop] = value
        return dict(hierarchical)
    
    @staticmethod
    def filter_by_type(configs: Dict, config_type: str) -> Dict:
        """按配置类型过滤"""
        return {k: v for k, v in configs.items() if k.startswith(config_type)}
    
    @staticmethod
    def generate_template(
        configs: Dict, 
        attributes: Dict, 
        include_sensitive=False
    ) -> Dict:
        """生成配置模板"""
        template = {}
        for config_type, props in configs.items():
            template[config_type] = {}
            config_attrs = attributes.get(config_type, {})
            
            for prop, value in props.items():
                prop_attrs = config_attrs.get(prop, {})
                is_sensitive = prop_attrs.get("sensitive", False)
                
                template[config_type][prop] = {
                    "value": "******" if is_sensitive and not include_sensitive else value,
                    "description": prop_attrs.get("description", ""),
                    "type": prop_attrs.get("type", "string"),
                    "required": prop_attrs.get("required", False),
                    "sensitive": is_sensitive,
                    "default": prop_attrs.get("default", None)
                }
        return template

