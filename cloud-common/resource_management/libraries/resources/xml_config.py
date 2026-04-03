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

高级XML配置管理引擎
"""

from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
from typing import Dict, List, Optional, Union, Tuple, Any
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import tempfile

class XmlConfig(Resource):
    """
    XML配置文件管理资源
    
    提供安全、智能的XML配置文件管理能力，支持：
    - 结构化XML配置生成与验证
    - 自动化XML语法检查
    - 配置模板继承与变量替换
    - XML补丁与差异合并
    - 配置文件版本控制与审计
    
    使用示例：
        XmlConfig(
            name="core-site.xml",
            configurations={
                "hadoop.tmp.dir": "/tmp/hadoop",
                "io.file.buffer.size": "131072"
            },
            configuration_attributes={
                "hadoop.tmp.dir": {"final": True}
            },
            conf_dir="/etc/hadoop/conf",
            template_file="templates/core-site.xml.j2",
            strict_mode=True,
            schema_validation="hadoop"
        )
    """

    # 文件操作动作
    action = ForcedListArgument(
        default="create",
        choices=["create", "validate", "update", "patch"],
        description="XML操作：创建(create)/验证(validate)/更新(update)/打补丁(patch)"
    )
    
    # XML文件定义
    filename = ResourceArgument(
        default=lambda obj: obj.name,
        description="目标XML文件名（默认为资源name属性）"
    )
    conf_dir = ResourceArgument(
        required=True,
        description="配置文件目录路径"
    )
    
    # XML内容配置
    configurations = ResourceArgument(
        required=True,
        description="XML配置键值对（字典格式）"
    )
    configuration_attributes = ResourceArgument(
        default={},
        description="XML属性配置（双层字典格式）"
    )
    
    # 模板与继承机制
    template_file = ResourceArgument(
        description="基础模板文件路径（可选）"
    )
    default_section = ResourceArgument(
        default="configuration",
        description="根节点下的默认配置节名称"
    )
    
    # XML文件属性
    xml_include_file = ResourceArgument(
        description="包含的外部XML文件"
    )
    encoding = ResourceArgument(
        default="UTF-8",
        choices=["UTF-8", "ISO-8859-1", "ASCII"],
        description="文件编码格式"
    )
    
    # 权限与安全控制
    mode = ResourceArgument(
        default=0o644,
        description="文件权限模式（八进制格式）"
    )
    owner = ResourceArgument(
        default="root",
        description="文件所有者"
    )
    group = ResourceArgument(
        default="root",
        description="文件所属组"
    )
    sensitive_properties = ResourceArgument(
        default=[],
        description="敏感属性列表（日志中掩码值）"
    )
    
    # 验证与约束
    schema_validation = ResourceArgument(
        default=None,
        description="XML模式验证（'hadoop'或自定义Schema文件路径）"
    )
    strict_mode = BooleanArgument(
        default=False,
        description="严格模式（禁用特殊字符）"
    )
    required_properties = ResourceArgument(
        default=[],
        description="必需属性列表"
    )
    
    # 高级功能
    version_control = BooleanArgument(
        default=True,
        description="启用版本控制（保存版本历史）"
    )
    patch_mode = ResourceArgument(
        default="merge",
        choices=["merge", "overwrite"],
        description="更新模式：合并(merge)或覆盖(overwrite)"
    )
    
    # 支持的资源操作
    actions = Resource.actions + ["create", "compare", "migrate"]

    # XML保留字符（禁用列表）
    DISALLOWED_CHARACTERS = {
        '<': '&lt;',
        '>': '&gt;',
        '&': '&amp;',
        '"': '&quot;',
        "'": '&apos;'
    }

    def __init__(self, **kwargs):
        """
        初始化XML配置资源
        
        增强初始化逻辑：
            - 构建完整文件路径
            - 验证必备属性
            - 加载模板文件
            - 初始化版本系统
        """
        super().__init__(**kwargs)
        
        self._resolve_fullpath()
        self._validate_requirements()
        self._load_template()
        self._init_versioning()
        self._current_xml = None
    
    def _resolve_fullpath(self):
        """解析完整文件路径"""
        import os
        # 如果指定了完整路径，则忽略conf_dir
        if os.path.isabs(self.filename):
            self.fullpath = self.filename
        else:
            self.fullpath = os.path.join(self.conf_dir, self.filename)
        self._log_debug(f"目标配置文件: {self.fullpath}")
    
    def _validate_requirements(self):
        """验证必备属性是否存在"""
        missing = [prop for prop in self.required_properties 
                   if self.configurations.get(prop) is None]
        if missing:
            raise MissingConfigurationError(
                f"缺少必备配置属性: {', '.join(missing)}", 
                missing
            )
    
    def _load_template(self):
        """加载XML模板文件"""
        if not self.template_file:
            return
        import jinja2
        
        try:
            with open(self.template_file, 'r', encoding=self.encoding) as f:
                self.base_template = jinja2.Template(f.read())
            self._log_info(f"加载模板文件: {self.template_file}")
        except Exception as e:
            raise TemplateLoadError(
                f"无法加载模板 {self.template_file}: {str(e)}"
            )
    
    def _init_versioning(self):
        """初始化版本控制系统"""
        self.version_dir = os.path.join(self.conf_dir, ".versions")
        self.max_versions = 3

        if self.version_control:
            os.makedirs(self.version_dir, exist_ok=True)
            self._log_info(f"版本控制系统启用: {self.version_dir}")
    
    def create(self):
        """创建XML配置文件"""
        try:
            # 1. 生成XML内容
            xml_content = self.generate_xml()
            
            # 2. 验证XML格式
            validation_result = self.validate_xml(xml_content)
            if not validation_result["valid"]:
                raise XmlValidationError("XML验证失败", validation_result)
            
            # 3. 备份现有文件
            self._create_backup()
            
            # 4. 写入文件
            self._write_xml_file(xml_content)
            
            # 5. 设置文件权限
            self._apply_permissions()
            
            # 6. 保存版本
            self._save_version(xml_content)
            
            return True
        except Exception as e:
            self._log_error(f"创建失败: {str(e)}")
            self._restore_backup()
            return False
    
    def generate_xml(self) -> str:
        """
        生成XML文件内容
        
        :return: 格式化后的XML字符串
        """
        try:
            # 如果有模板，则使用模板作为基础
            if hasattr(self, 'base_template'):
                root = ET.fromstring(self.base_template.render(
                    configurations=self.configurations,
                    attributes=self.configuration_attributes
                ))
            else:
                # 从头创建XML结构
                root = ET.Element(self.default_section)
            
            # 添加/更新配置属性
            self._update_xml_config(root)
            
            # 添加外部包含文件
            if self.xml_include_file:
                self._add_xml_include(root)
            
            # 转换XML内容为字符串
            rough_string = ET.tostring(root, self.encoding)
            parsed = minidom.parseString(rough_string)
            return parsed.toprettyxml(indent="  ", encoding=self.encoding).decode()
        except Exception as e:
            raise XmlGenerationError(f"XML生成失败: {str(e)}")
    
    def _update_xml_config(self, root):
        """
        更新XML配置
        
        :param root: XML根元素
        """
        # 查找现有配置元素
        existing_configs = {elem.findtext("name"): elem for elem in root.findall("property")}
        
        # 添加/更新配置
        for key, value in self.configurations.items():
            clean_key = self._sanitize_string(key)
            clean_value = self._sanitize_string(value) if value else ""
            
            if clean_key in existing_configs:
                # 更新现有属性
                prop_elem = existing_configs[clean_key]
                # 查找value元素并更新
                value_elem = prop_elem.find("value")
                if value_elem is not None:
                    value_elem.text = clean_value
                else:
                    new_val = ET.SubElement(prop_elem, "value")
                    new_val.text = clean_value
                self._log_debug(f"更新属性: {clean_key}={self._mask_value(clean_key, clean_value)}")
            else:
                # 创建新属性
                prop_elem = ET.SubElement(root, "property")
                ET.SubElement(prop_elem, "name").text = clean_key
                ET.SubElement(prop_elem, "value").text = clean_value
                self._log_debug(f"新增属性: {clean_key}={self._mask_value(clean_key, clean_value)}")
        
        # 添加属性参数
        for key, attributes in self.configuration_attributes.items():
            clean_key = self._sanitize_string(key)
            if clean_key not in existing_configs:
                self._log_warning(f"尝试为不存在的属性添加特性: {clean_key}")
                continue
                
            prop_elem = existing_configs[clean_key]
            for attr_name, attr_value in attributes.items():
                clean_attr = self._sanitize_string(attr_name)
                clean_val = self._sanitize_string(str(attr_value))
                
                if clean_attr not in prop_elem.attrib:
                    # 添加新属性
                    prop_elem.set(clean_attr, clean_val)
                    self._log_debug(f"添加特性: {clean_key}: {clean_attr}={clean_val}")
                else:
                    # 更新现有属性
                    if prop_elem.get(clean_attr) != clean_val:
                        prop_elem.set(clean_attr, clean_val)
                        self._log_debug(f"更新特性: {clean_key}: {clean_attr}={clean_val}")
    
    def _add_xml_include(self, root):
        """添加外部XML包含文件"""
        if not os.path.exists(self.xml_include_file):
            self._log_warning(f"包含文件不存在: {self.xml_include_file}")
            return
            
        try:
            # 读取XML包含文件
            with open(self.xml_include_file, 'r') as inc_file:
                content = inc_file.read()
            
            # 创建XML包含指令
            includes = ET.SubElement(root, "include")
            includes.text = f"\n  {content}\n"
            self._log_info(f"包含外部XML文件: {self.xml_include_file}")
        except Exception as e:
            self._log_error(f"包含外部文件失败: {str(e)}")
    
    def validate_xml(self, xml_string: str) -> Dict:
        """
        验证XML格式与内容
        
        :param xml_string: XML内容
        :return: 验证结果字典 {
          "valid": bool,
          "errors": list,
          "warnings": list
        }
        """
        from xml.parsers.expat import ExpatError
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # 1. 基础XML格式验证
        try:
            ET.fromstring(xml_string)
        except ExpatError as ee:
            result["valid"] = False
            result["errors"].append(f"XML语法错误: {str(ee)}")
        
        # 2. Hadoop模式验证
        if self.schema_validation == "hadoop":
            if not self._validate_hadoop_structure(xml_string):
                result["valid"] = False
                result["errors"].append("Hadoop结构验证失败")
        
        # 3. 自定义Schema验证（如果提供）
        elif self.schema_validation and os.path.exists(self.schema_validation):
            if not self._validate_with_schema(xml_string, self.schema_validation):
                result["valid"] = False
                result["errors"].append("Schema模式验证失败")
        
        # 4. 关键属性验证
        for key in self.required_properties:
            if key not in self.configurations:
                result["warnings"].append(f"必要属性缺失: {key}")
        
        # 5. 敏感数据检测
        if self.sensitive_properties:
            for prop in self.sensitive_properties:
                if prop in self.configurations:
                    val = self.configurations[prop]
                    if "****" not in val:  # 检查是否已掩码
                        result["warnings"].append(f"敏感属性未掩码: {prop}")
        
        return result
    
    def compare(self, reference_file: str) -> Dict[str, Any]:
        """
        比较当前配置与参考文件的差异
        
        :param reference_file: 参考配置文件路径
        :return: 差异报告 {
          "added": {key: value},
          "removed": {key: value},
          "changed": {key: {"current": value, "new": value}}
        }
        """
        import xml.etree.ElementTree as ET
        if not os.path.exists(self.fullpath):
            return {"status": "missing", "file": self.fullpath}
        
        # 解析现有文件内容
        current_config = self._parse_xml_file(self.fullpath)
        reference_config = self._parse_xml_file(reference_file)
        
        # 执行比较
        return self._compare_configs(current_config, reference_config)
    
    def migrate(self, new_format: str) -> bool:
        """
        迁移配置到新格式
        
        :param new_format: 目标格式（'yaml'/'json'）
        :return: 迁移成功状态
        """
        # 读取现有配置
        current_content = self._read_current_file()
        if not current_content:
            return False
            
        # 创建迁移路径
        migrate_dir = os.path.join(self.conf_dir, "migrated")
        os.makedirs(migrate_dir, exist_ok=True)
        
        # 执行格式转换
        output_file = os.path.join(
            migrate_dir,
            f"{os.path.splitext(self.filename)[0]}.{new_format}"
        )
        
        try:
            if new_format == "yaml":
                self._convert_to_yaml(current_content, output_file)
            elif new_format == "json":
                self._convert_to_json(current_content, output_file)
            elif new_format == "xml":  # 实际上是再生成一次XML
                self._write_xml_file(current_content, output_file)
            else:
                raise UnsupportedFormatError(f"不支持的目标格式: {new_format}")
                
            return True
        except Exception as e:
            self._log_error(f"配置迁移失败: {str(e)}")
            return False
    
    # ----- XML处理工具方法 -----
    def _parse_xml_file(self, file_path: str) -> Dict:
        """
        解析XML文件为配置字典
        
        :param file_path: XML文件路径
        :return: 配置字典 {key: value}
        """
        if not os.path.exists(file_path):
            return {}
            
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            config_dict = {}
            for prop in root.findall("property"):
                name = prop.findtext("name")
                value = prop.findtext("value")
                if name:
                    config_dict[name] = value
                    
            return config_dict
        except Exception as e:
            raise XmlParseError(f"解析XML文件失败 {file_path}: {str(e)}")
    
    def _compare_configs(self, current: Dict, reference: Dict) -> Dict:
        """比较两个配置字典的差异"""
        result = {
            "added": {},
            "removed": {},
            "changed": {},
            "unchanged": {}
        }
        
        # 当前配置中的所有键
        all_keys = set(current.keys()) | set(reference.keys())
        
        for key in all_keys:
            curr_val = current.get(key)
            ref_val = reference.get(key)
            
            if key not in current:
                result["removed"][key] = ref_val
            elif key not in reference:
                result["added"][key] = curr_val
            elif curr_val != ref_val:
                result["changed"][key] = {"current": curr_val, "new": ref_val}
            else:
                result["unchanged"][key] = curr_val
                
        return result
    
    # ----- 安全与权限方法 -----
    def _sanitize_string(self, input_str: str) -> str:
        """清理字符串中的特殊字符"""
        if not input_str:
            return ""
            
        if self.strict_mode:
            for char, replacement in self.DISALLOWED_CHARACTERS.items():
                input_str = input_str.replace(char, replacement)
        return input_str
    
    def _mask_value(self, key: str, value: str) -> str:
        """掩码敏感值（用于日志）"""
        if key in self.sensitive_properties:
            return "******"
        if value and (value.lower().startswith("jceks://") or "password" in key.lower()):
            return "******"
        return value
    
    # ----- 文件系统操作 -----
    def _create_backup(self):
        """创建配置文件备份"""
        if not os.path.exists(self.fullpath):
            return
            
        import shutil
        import time
        
        try:
            backup_dir = os.path.join(self.conf_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            filename = os.path.basename(self.fullpath)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"{filename}.bak_{timestamp}")
            
            shutil.copy2(self.fullpath, backup_file)
            self._log_info(f"已创建备份: {backup_file}")
            self.backup_path = backup_file
        except Exception as e:
            self._log_error(f"备份失败: {str(e)}")
            self.backup_path = None
    
    def _restore_backup(self):
        """从备份恢复"""
        if not self.backup_path or not os.path.exists(self.backup_path):
            return False
            
        try:
            shutil.copy2(self.backup_path, self.fullpath)
            self._log_info(f"从备份恢复: {self.backup_path}")
            return True
        except Exception as e:
            self._log_error(f"恢复备份失败: {str(e)}")
            return False
    
    def _apply_permissions(self):
        """应用文件系统权限"""
        if not os.path.exists(self.fullpath):
            return
            
        try:
            import os
            os.chmod(self.fullpath, self.mode)
            uid = self._uid_for(self.owner)
            gid = self._gid_for(self.group)
            os.chown(self.fullpath, uid, gid)
            self._log_info(f"设置权限: {self.owner}:{self.group} {self.mode:o}")
        except Exception as e:
            self._log_error(f"权限设置失败: {str(e)}")
    
    def _save_version(self, content: str):
        """保存配置文件版本"""
        if not self.version_control:
            return
            
        version_file = os.path.join(
            self.version_dir,
            f"{self.filename}.v{len(self._get_versions()) + 1}"
        )
        
        try:
            with open(version_file, 'w', encoding=self.encoding) as vf:
                vf.write(content)
            self._log_debug(f"保存配置版本: {version_file}")
            
            # 删除旧版本（保留最新max_versions个）
            self._remove_old_versions()
        except Exception as e:
            self._log_error(f"保存版本失败: {str(e)}")
    
    # ----- 辅助方法 -----
    def _log_info(self, message: str):
        logging.info(f"[XmlConfig] {self.name}: {message}")
    
    def _log_warning(self, message: str):
        logging.warning(f"[XmlConfig] {self.name}: {message}")
    
    def _log_error(self, message: str):
        logging.error(f"[XmlConfig] {self.name}: {message}")
    
    def _log_debug(self, message: str):
        logging.debug(f"[XmlConfig] {self.name}: {message}")
    
    def _uid_for(self, user: str) -> int:
        """获取用户ID（系统调用）"""
        import pwd
        try:
            return pwd.getpwnam(user).pw_uid
        except:
            return 0
    
    def _gid_for(self, group: str) -> int:
        """获取组ID（系统调用）"""
        import grp
        try:
            return grp.getgrnam(group).gr_gid
        except:
            return 0


# 自定义异常类
class XmlConfigException(Exception):
    """XML配置异常基类"""
    pass

class TemplateLoadError(XmlConfigException):
    pass

class XmlValidationError(XmlConfigException):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details

class XmlGenerationError(XmlConfigException):
    pass

class XmlParseError(XmlConfigException):
    pass

class MissingConfigurationError(XmlConfigException):
    pass

class UnsupportedFormatError(XmlConfigException):
    pass
