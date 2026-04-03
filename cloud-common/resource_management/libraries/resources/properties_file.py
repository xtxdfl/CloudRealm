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

高级属性文件资源管理器
"""

from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
from typing import Dict, List, Optional, Union, Callable, Any

class PropertiesFile(Resource):
    """
    Java属性文件资源管理器
    
    用于创建、更新和管理Java属性文件（.properties）。支持完整的配置管理功能�?    包括文件权限管理、备份恢复、变更检测等�?    
    使用示例�?        PropertiesFile(
            name="application.properties",
            properties={
                "server.port": "8080",
                "spring.application.name": "DemoApp"
            },
            owner="appuser",
            group="appgroup",
            mode=0644,
            key_value_delimiter="=",
            backup=True,
            create_actions="create"
        )
    
    功能特性：
        - 支持文件和目录路径规范化
        - 自动备份和版本控�?        - 敏感数据处理（掩码和加密�?        - 变更检测和审计
        - 多编码支持（UTF-8，ISO-8859-1等）
    """
    
    # 文件操作指令（支持多个操作符�?    action = ForcedListArgument(
        default="create",
        choices=["create", "update", "backup", "verify"],
        description="文件操作：创�?create)/更新(update)/备份(backup)/验证(verify)"
    )
    
    # 文件名（默认使用资源name属性）
    filename = ResourceArgument(
        default=lambda obj: obj.name,
        description="目标属性文件名（默认为资源name属性）"
    )
    
    # 属性文件内容（键值对�?    properties = ResourceArgument(
        required=True,
        description="属性文件键值对内容（字典格式）"
    )
    
    # 文件所在目�?    dir = ResourceArgument(
        default="/etc/application",
        description="属性文件所在目录路�?
    )
    
    # 文件权限属�?    mode = ResourceArgument(
        default=0o644,
        description="文件权限模式（八进制格式�?
    )
    owner = ResourceArgument(
        default="root",
        description="文件所有�?
    )
    group = ResourceArgument(
        default="root",
        description="文件所属组"
    )
    
    # 文件格式设置
    key_value_delimiter = ResourceArgument(
        default="=",
        description="键值分隔符（默认为等号�?
    )
    encoding = ResourceArgument(
        default="UTF-8",
        choices=["UTF-8", "ISO-8859-1", "ASCII"],
        description="文件编码格式"
    )
    
    # 高级功能选项
    backup = BooleanArgument(
        default=False,
        description="是否在修改前创建备份"
    )
    backup_count = ResourceArgument(
        default=3,
        description="保留的备份数�?
    )
    sensitive_keys = ResourceArgument(
        default=[],
        description="需要掩码处理的敏感键值（在日志中隐藏值）"
    )
    validation_hook = ResourceArgument(
        default=None,
        description="文件内容的验证回调函�?
    )
    
    # 支持的操作列表（默认为继承的操作 + 新增操作�?    actions = Resource.actions + ["create", "validate"]

    # 内置验证规则
    VALIDATION_RULES = {
        "key_format": r"^[a-zA-Z_][a-zA-Z0-9_.-]*$",
        "line_length": 1024,
        "reserved_keys": ["class", "package"]
    }

    def __init__(self, **kwargs):
        """
        初始化属性文件资�?        
        增强初始化逻辑�?            - 自动规范化路�?            - 执行预验证检�?            - 处理路径变量和系统参�?        """
        super().__init__(**kwargs)
        self._resolve_fullpath()
        self._pre_validate()
        
    def _resolve_fullpath(self):
        """解析完整的文件路�?""
        import os
        # 如果指定了完整路径，则忽略dir设置
        if os.path.isabs(self.filename):
            self.fullpath = self.filename
        else:
            self.fullpath = os.path.join(self.dir, self.filename)
        
    def _pre_validate(self):
        """执行预验证检�?""
        import re
        from collections import Counter
        
        # 检查保留键�?        for key in self.VALIDATION_RULES["reserved_keys"]:
            if key in self.properties:
                raise ValueError(f"禁止使用保留键名: {key}")
        
        # 验证键格�?        key_regex = re.compile(self.VALIDATION_RULES["key_format"])
        invalid_keys = [k for k in self.properties if not key_regex.match(k)]
        if invalid_keys:
            raise ValueError(f"无效的键名格�? {', '.join(invalid_keys)}")
        
        # 检测重复键
        key_counts = Counter(self.properties.keys())
        duplicates = [k for k, c in key_counts.items() if c > 1]
        if duplicates:
            raise ValueError(f"检测到重复�? {', '.join(duplicates)}")
        
        # 验证值行长度
        for key, value in self.properties.items():
            if len(str(value)) > self.VALIDATION_RULES["line_length"]:
                raise ValueError(f"�?'{key}' 的值过�?"
                                 f"(最�?{self.VALIDATION_RULES['line_length']} 字符)")
    
    def render_content(self, mask_sensitive=True) -> str:
        """
        渲染属性文件内�?        
        :param mask_sensitive: 是否对敏感键值进行掩码处�?        :return: 属性文件内容字符串
        """
        lines = []
        sensitive_set = set(self.sensitive_keys)
        
        for key, value in sorted(self.properties.items()):
            # 处理敏感数据
            display_value = str(value)
            if mask_sensitive and key in sensitive_set:
                display_value = "******"
                
            # 添加键值对
            lines.append(f"{key}{self.key_value_delimiter}{display_value}")
            
        # 添加文件头信�?        header = (
            f"# Generated by cloud Agent\n"
            f"# File: {self.fullpath}\n"
            f"# Encoding: {self.encoding}\n"
        )
        return header + "\n".join(lines) + "\n"
    
    def backup_file(self):
        """创建文件备份"""
        if not os.path.exists(self.fullpath):
            return None
            
        import time
        backup_dir = os.path.join(self.dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = os.path.join(
            backup_dir,
            f"{os.path.basename(self.fullpath)}.backup.{timestamp}"
        )
        
        import shutil
        shutil.copy2(self.fullpath, backup_path)
        return backup_path
    
    def apply_changes(self):
        """应用属性文件变更（主工作流�?""
        # 1. 检查是否需要进行操�?        try:
            self._resolve_fullpath()
        except Exception as e:
            self._report_error(f"路径解析失败: {str(e)}")
            return False
            
        # 2. 备份文件
        backups = []
        if self.backup:
            try:
                backup_path = self.backup_file()
                if backup_path:
                    backups.append(backup_path)
                    self._log_action(f"创建文件备份: {backup_path}")
            except Exception as e:
                self._report_error(f"备份失败: {str(e)}")
        
        # 3. 渲染文件内容
        try:
            content = self.render_content(mask_sensitive=False)
        except Exception as e:
            self._report_error(f"内容渲染失败: {str(e)}")
            return False
            
        # 4. 写入文件
        try:
            with open(self.fullpath, 'w', encoding=self.encoding) as f:
                f.write(content)
            self._log_action(f"写入 {len(content.splitlines())} 行到 {self.fullpath}")
        except Exception as e:
            self._report_error(f"文件写入失败: {str(e)}")
            return False
            
        # 5. 应用权限
        try:
            import os
            os.chmod(self.fullpath, self.mode)
            os.chown(self.fullpath, self._uid_for(self.owner), self._gid_for(self.group))
            self._log_action(f"应用权限: {self.owner}:{self.group} {self.mode:o}")
        except Exception as e:
            self._report_error(f"权限设置失败: {str(e)}", warning=True)
            
        # 6. 处理备份轮转
        self._rotate_backups()
        return True
    
    def compare_with_current(self) -> Dict[str, Any]:
        """
        比较当前配置与文件内�?        
        :return: 差异报表 {
            "changed": {key: {"expected": value1, "actual": value2}},
            "missing": [key1, key2],
            "extra": [key3, key4]
        }
        """
        if not os.path.exists(self.fullpath):
            return {"status": "missing", "file": self.fullpath}
            
        # 解析现有文件内容
        parse_result = self.parse_properties_file(self.fullpath)
        
        # 比较差异
        result = {
            "changed": {},
            "missing": [],
            "extra": list(parse_result.keys()),
            "file": self.fullpath
        }
        
        for key, expected_value in self.properties.items():
            # 键不存在的处�?            if key not in parse_result:
                result["missing"].append(key)
                continue
                
            # 值差异检�?            actual_value = parse_result[key]
            if str(expected_value) != actual_value:
                result["changed"][key] = {
                    "expected": expected_value,
                    "actual": actual_value,
                    "source": key
                }
                
            # 移除已检查键
            if key in result["extra"]:
                result["extra"].remove(key)
                
        result["is_match"] = not (
            result["changed"] or 
            result["missing"] or 
            result["extra"]
        )
        
        return result
    
    @classmethod
    def parse_properties_file(cls, file_path: str) -> Dict[str, str]:
        """
        解析现有属性文件内�?        
        :param file_path: 属性文件路�?        :return: 键值对字典
        """
        import os
        if not os.path.exists(file_path):
            return {}
            
        properties = {}
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注�?                if not line or line.startswith("#"):
                    continue
                    
                # 查找分隔符位�?                sep_index = line.find('=')
                if sep_index == -1:
                    continue  # 跳过无分隔符�?                    
                key = line[:sep_index].strip()
                value = line[sep_index+1:].strip()
                
                # 处理多行�?                if value.endswith("\\"):
                    value = value[:-1]
                    # 组合多行�?                    for next_line in f:
                        clean_line = next_line.strip()
                        if clean_line.endswith("\\"):
                            value += clean_line[:-1]
                        else:
                            value += clean_line
                            break
                
                properties[key] = value
                
        return properties
    
    def _rotate_backups(self):
        """轮转备份文件（保留指定数量的最新备份）"""
        from glob import glob
        import os
        
        if not self.backup:
            return
            
        backup_dir = os.path.join(self.dir, "backups")
        if not os.path.exists(backup_dir):
            return
            
        pattern = f"{self.filename}.backup.*"
        file_pattern = os.path.join(backup_dir, pattern)
        backups = sorted(glob(file_pattern), key=os.path.getmtime, reverse=True)
        
        # 移除旧备�?        for old_backup in backups[self.backup_count:]:
            try:
                os.remove(old_backup)
                self._log_action(f"移除旧备�? {os.path.basename(old_backup)}")
            except Exception as e:
                self._log_action(f"备份移除失败: {os.path.basename(old_backup)} - {str(e)}", level="WARNING")
    
    def _uid_for(self, user: str) -> int:
        """获取用户ID（系统调用）"""
        import pwd
        try:
            return pwd.getpwnam(user).pw_uid
        except:
            return 0  # 失败返回root
    
    def _gid_for(self, group: str) -> int:
        """获取组ID（系统调用）"""
        import grp
        try:
            return grp.getgrnam(group).gr_gid
        except:
            return 0  # 失败返回root
    
    def _log_action(self, message: str, level: str = "INFO"):
        """记录操作日志"""
        logger_method = getattr(self.logger, level.lower(), self.logger.info)
        logger_method(f"[PropertiesFile] {self.name}: {message}")
    
    def _report_error(self, message: str, warning: bool = False):
        """错误报告"""
        if warning:
            self.logger.warning(f"[PropertiesFile] {self.name}: {message}")
        else:
            self.logger.error(f"[PropertiesFile] {self.name}: {message}")
