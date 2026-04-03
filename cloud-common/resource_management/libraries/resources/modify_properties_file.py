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

高级属性文件修改引擎
"""

from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
from typing import Dict, List, Optional, Union, Tuple
import os
import re
import logging
import tempfile
import shutil
from collections import OrderedDict

class ModifyPropertiesFile(Resource):
    """
    属性文件修改管理器
    
    提供智能化的属性文件修改能力，支持：
    - 非破坏性文件编辑（保留注释和格式）
    - 多级变更跟踪与审计
    - 敏感数据处理与掩码保护
    - 属性依赖检查与冲突解决
    - 版本控制与回滚机制
    
    使用示例：
        ModifyPropertiesFile(
            name="application.properties",
            properties={
                "server.port": "8080",
                "ssl.enabled": "true",
                "new.setting": "value"
            },
            remove_properties=["deprecated.setting"],
            owner="appuser",
            group="appgroup",
            mode=0o644,
            preserve_comments=True,
            sensitive_keys=["api.key", "db.password"]
        )
    """

    # 操作类型
    action = ForcedListArgument(
        default="apply",
        choices=["apply", "dry-run", "verify", "revert"],
        description="操作类型：应用变更(apply)/空运行(dry-run)/验证配置(verify)/回滚(revert)"
    )
    
    # 文件属性
    filename = ResourceArgument(
        default=lambda obj: obj.name,
        description="目标属性文件名（默认为资源name属性）"
    )
    
    # 属性管理
    properties = ResourceArgument(
        default={},
        description="要设置或更新的属性（键值对字典）"
    )
    remove_properties = ResourceArgument(
        default=[],
        description="要删除的属性列表"
    )
    update_comments = ResourceArgument(
        default={},
        description="属性的注释映射（属性名: 注释文本）"
    )
    
    # 属性格式设置
    key_value_delimiter = ResourceArgument(
        default="=",
        description="键值分隔符"
    )
    comment_symbols = ForcedListArgument(
        default=["#"],
        description="注释行符号列表"
    )
    
    # 处理行为选项
    preserve_comments = BooleanArgument(
        default=True,
        description="是否保留文件中的所有注释"
    )
    preserve_original_formatting = BooleanArgument(
        default=True,
        description="是否保留原文件格式"
    )
    ignore_missing = BooleanArgument(
        default=False,
        description="是否忽略不存在的文件"
    )
    require_confirmation = BooleanArgument(
        default=False,
        description="是否要求用户确认变更"
    )
    
    # 安全与权限
    sensitive_keys = ResourceArgument(
        default=[],
        description="敏感属性列表（日志和空运行时掩码值）"
    )
    mode = ResourceArgument(
        default=0o644,
        description="文件权限模式（八进制格式）"
    )
    owner = ResourceArgument(
        description="文件所有者（如未设置则保持原状）"
    )
    group = ResourceArgument(
        description="文件所属组（如未设置则保持原状）"
    )
    
    # 文件编码
    encoding = ResourceArgument(
        default="utf-8",
        choices=["utf-8", "latin-1", "iso-8859-1"],
        description="文件编码格式"
    )
    
    # 变更控制
    backup = BooleanArgument(
        default=True,
        description="是否在修改前创建备份"
    )
    max_backups = ResourceArgument(
        default=3,
        description="保留的最大备份数量"
    )
    change_tracking = BooleanArgument(
        default=True,
        description="是否跟踪变更历史"
    )
    
    # 支持的资源操作
    actions = Resource.actions + ["apply", "validate", "history", "rollback"]
    
    # 内部状态变量
    PROPERTY_REGEX = r"^\s*([\w\.-]+)\s*([=:]\s*)?(.*?)\s*(#.*)?$"

    def __init__(self, **kwargs):
        """
        初始化属性文件资源
        
        增强初始化逻辑：
            - 构建完整文件路径
            - 验证必要参数
            - 初始化审计跟踪系统
            - 准备临时工作空间
        """
        super().__init__(**kwargs)
        self._resolve_filepath()
        self._validate_parameters()
        self._init_audit_system()
        self._setup_workspace()
        self.changes = {
            "added": [],
            "removed": [],
            "changed": []
        }
    
    def _resolve_filepath(self):
        """解析完整文件路径"""
        import os
        self.fullpath = os.path.abspath(self.filename) 
        self._log_info(f"目标配置文件: {self.fullpath}")
    
    def _validate_parameters(self):
        """验证输入参数有效性"""
        # 检查属性名称有效性
        invalid_props = [k for k in self.properties 
                         if not re.match(r"^[\w\.-]+$", k)]
        
        if invalid_props:
            raise ValueError(f"无效的属性名: {', '.join(invalid_props)}")
        
        # 检查是否同时设置删除和添加相同属性
        conflict_props = [prop for prop in self.remove_properties 
                          if prop in self.properties]
        
        if conflict_props:
            raise ValueError(
                f"不能同时删除和设置相同属性: {', '.join(conflict_props)}"
            )
    
    def _init_audit_system(self):
        """初始化审计追踪系统"""
        if not self.change_tracking:
            return
            
        self.audit_dir = os.path.join(
            os.path.dirname(self.fullpath), 
            f".{os.path.basename(self.fullpath)}_changes"
        )
        self.changeset_file = os.path.join(
            self.audit_dir, 
            f"changeset_{int(time.time())}.json"
        )
        
        os.makedirs(self.audit_dir, exist_ok=True)
        self._log_debug(f"开启变更审计: {self.audit_dir}")
    
    def _setup_workspace(self):
        """创建工作临时空间"""
        self.tmp_dir = tempfile.mkdtemp(prefix="modify_prop_")
        self.orig_file = os.path.join(self.tmp_dir, "original.properties")
        self.new_file = os.path.join(self.tmp_dir, "modified.properties")
        self._log_debug(f"工作空间: {self.tmp_dir}")
    
    def apply(self):
        """应用属性变更主操作"""
        try:
            # 0. 检查文件可操作性
            if not self._precheck():
                return False
            
            # 1. 读取原始文件
            orig_properties, orig_lines = self._parse_file()
            
            # 2. 分析变更内容
            change_report = self._calculate_changes(orig_properties)
            
            # 3. 生成新文件内容
            new_content = self._generate_new_content(
                orig_lines, 
                orig_properties, 
                change_report
            )
            
            # 4. 验证和确认阶段
            if "dry-run" in self.action:
                self._log_info("执行空运行结果:")
                self._log_info("========================")
                print(new_content)
                self._log_info("========================")
                return True
                
            if "verify" in self.action:
                validation = self._validate_changes(change_report)
                return validation.get("valid", False)
                
            if self.require_confirmation:
                if not self._request_confirmation(change_report):
                    self._log_info("用户取消操作")
                    return False
            
            # 5. 备份原始文件
            backup_path = self._create_backup() if self.backup else None
            
            try:
                # 6. 写入新文件
                self._write_file(new_content)
                
                # 7. 保留原始权限/所有者
                self._preserve_or_set_permissions()
                
                # 8. 保留原始时间戳
                self._preserve_timestamps()
                
                # 9. 记录变更历史
                self._record_changeset(change_report, backup_path)
                
                # 10. 清理工作空间
                self._cleanup()
                
                return True
            except:
                # 恢复备份以防失败
                self._restore_backup(backup_path)
                raise
                
        except Exception as e:
            self._log_error(f"操作失败: {str(e)}")
            self._cleanup()
            return False
    
    def history(self, show_lines=5):
        """显示变更历史记录"""
        if not hasattr(self, 'audit_dir') or not os.path.exists(self.audit_dir):
            return "无变更记录"
            
        changesets = sorted(
            [f for f in os.listdir(self.audit_dir) if f.endswith(".json")],
            reverse=True
        )[:show_lines]
        
        history = []
        for cs in changesets:
            with open(os.path.join(self.audit_dir, cs)) as f:
                data = json.load(f)
                history.append({
                    "id": cs.split("_")[1].split(".")[0],
                    "timestamp": datetime.fromtimestamp(data['timestamp']).strftime("%Y-%m-%d %H:%M:%S"),
                    "user": data['user'],
                    "changes": f"↑{len(data['changes']['added'])} ↓{len(data['changes']['removed'])} ~{len(data['changes']['changed'])}",
                    "backup": data.get('backup', '')
                })
                
        return history
    
    def rollback(self, change_id=None):
        """回滚到先前版本"""
        if not hasattr(self, 'audit_dir') or not os.path.exists(self.audit_dir):
            raise Exception("没有可用的变更历史记录")
            
        # 定位最新变更记录
        if change_id is None:
            changesets = sorted(
                os.listdir(self.audit_dir), 
                reverse=True
            )
            if not changesets:
                raise Exception("没有可回滚的变更")
            latest_change = changesets[0]
            change_id = latest_change.split("_")[1].split(".")[0]
        
        # 查找匹配的变更记录
        for fname in os.listdir(self.audit_dir):
            if fname.endswith(f"{change_id}.json"):
                changefile = os.path.join(self.audit_dir, fname)
                break
        else:
            raise FileNotFoundError(f"未找到变更ID: {change_id}")
        
        # 读取变更信息
        with open(changefile) as f:
            changes = json.load(f)
            
        # 恢复备份
        if 'backup' in changes and os.path.exists(changes['backup']):
            self._log_info(f"从备份恢复: {changes['backup']}")
            shutil.copy2(changes['backup'], self.fullpath)
            
            # 删除变更记录（可选）
            os.remove(changefile)
            return True
        else:
            raise Exception(f"找不到关联的备份文件: {changes.get('backup', '')}")
    
    def _precheck(self) -> bool:
        """执行前置检查"""
        # 检查文件是否存在
        if not os.path.exists(self.fullpath) and not self.ignore_missing:
            raise FileNotFoundError(f"文件不存在: {self.fullpath}")
        
        # 检查文件可读性
        if not os.access(self.fullpath, os.R_OK):
            raise PermissionError(f"无法读取文件: {self.fullpath}")
            
        # 检查文件可写性（仅在apply操作时）
        if "apply" in self.action and not os.access(os.path.dirname(self.fullpath), os.W_OK):
            raise PermissionError(f"无法写入目标目录: {os.path.dirname(self.fullpath)}")
            
        return True
    
    def _parse_file(self) -> Tuple[Dict, List]:
        """
        解析属性文件
        :return: (属性字典, 原始行列表)
        """
        properties = {}
        lines = []
        
        # 读取文件
        try:
            with open(self.fullpath, "r", encoding=self.encoding) as f:
                raw_lines = f.readlines()
        except UnicodeDecodeError:
            # 如果默认解码失败，尝试其他编码
            return self._decode_with_fallback()
            
        current_key = None
        multiline_value = False
        
        for num, line in enumerate(raw_lines):
            lines.append(line)
            stripped = line.strip()
            
            # 空行处理
            if not stripped:
                continue
                
            # 检查是否为注释行
            if any(stripped.startswith(s) for s in self.comment_symbols):
                # 检查注释是否与属性关联
                if current_key and "=" not in stripped and ":" not in stripped:
                    # 关联多行注释
                    self._add_multiline_value(properties, current_key, stripped)
                continue
            
            # 属性解析
            match = re.match(self.PROPERTY_REGEX, line)
            if match:
                key = match.group(1)
                # 检查key有效性
                if not key.isidentifier():
                    self._log_warning(f"第{num+1}行：无效的属性名 {key}")
                    continue
                    
                value_part = match.group(3)
                value = value_part
                
                # 处理多行值（如果行末有\）
                if value.rstrip().endswith('\\'):
                    value = value.rstrip()[:-1]  # 移除行末的反斜杠
                    current_key = key
                    multiline_value = True
                else:
                    current_key = None
                    multiline_value = False
                
                # 存储属性
                if key in properties:
                    self._log_warning(f"第{num+1}行：重复的属性名 {key}")
                
                properties[key] = {
                    "value": value,
                    "original_value": value,
                    "line": num+1,
                    "comments": []
                }
            elif multiline_value and current_key:
                # 处理多行值的延续行
                self._add_multiline_value(properties, current_key, line)
        
        return properties, lines
    
    def _add_multiline_value(self, properties, key, line):
        """添加多行值"""
        if key in properties:
            # 移除行尾的续行符
            clean_line = line.rstrip("\n\\").rstrip()
            properties[key]["value"] += clean_line
    
    def _calculate_changes(self, existing: Dict) -> Dict:
        """
        计算需要应用的变更
        :return: change_report = {
            "added": {key: value},
            "removed": {key: value},
            "changed": {key: {"old": value, "new": value}}
        }
        """
        changes = {"added": {}, "removed": {}, "changed": {}}
        
        # 检查新添加的属性
        for key, new_value in self.properties.items():
            if key not in existing:
                changes["added"][key] = new_value
            else:
                old_value = existing[key]["value"]
                if str(old_value) != str(new_value):
                    changes["changed"][key] = {"old": old_value, "new": new_value}
        
        # 检查要移除的属性
        for key in self.remove_properties:
            if key in existing:
                changes["removed"][key] = existing[key]["value"]
            else:
                self._log_warning(f"尝试删除不存在的属性: {key}")
        
        return changes
    
    def _generate_new_content(
        self, 
        orig_lines: List[str], 
        existing: Dict, 
        changes: Dict
    ) -> str:
        """生成新的文件内容"""
        # 深拷贝原始行列表
        new_lines = list(orig_lines)
        
        # 跟踪处理的行（避免重复处理）
        processed_lines = set()
        
        # 创建更改映射：按行号分组
        change_map = {}
        
        # 对更改的属性的处理
        handled_keys = set()
        
        # 移除标记要删除的属性
        for key in changes["removed"]:
            if key in existing:
                info = existing[key]
                line_num = info["line"]
                # 标记所有受影响的行
                for i in range(info["line"], len(new_lines)):
                    if not new_lines[i].strip():
                        break
                    processed_lines.add(i)
                # 删除该属性及其关联注释
                new_lines[line_num-1] = ""
        
        # 处理现有的要更新的属性
        for key in changes["changed"]:
            if key in existing:
                info = existing[key]
                line_num = info["line"]
                # 只更新指定行
                old_line = orig_lines[line_num-1]
                new_value = changes["changed"][key]["new"]
                
                # 检测原格式并保持格式
                match = re.match(r"^(\s*)([^\s=:]+)(\s*[=:]\s*)(.*)$", old_line)
                if match:
                    indent, prop, delim, old_val = match.groups()
                    # 新建行，保持原缩进和分隔符
                    new_line = f"{indent}{prop}{delim}{new_value}"
                    # 保留原注释（如果有）
                    if "#" in old_line:
                        new_line += old_line.split("#", 1)[1].rstrip()
                    new_line += "\n"
                else:
                    # 如果无法解析格式，创建新行
                    new_line = f"{key}{self.key_value_delimiter}{new_value}\n"
                
                new_lines[line_num-1] = new_line
                processed_lines.add(line_num-1)
                handled_keys.add(key)
        
        # 添加新的属性
        new_props_lines = []
        for key, value in changes["added"].items():
            comment_text = ""
            if key in self.update_comments:
                comment_text = f" {self.comment_symbols[0]} {self.update_comments[key]}\n"
            new_line = f"{key}{self.key_value_delimiter}{value}\n"
            new_props_lines.append(f"{comment_text}{new_line}")
        
        # 找到文件中的最后一个属性
        last_prop_line = -1
        for i, line in enumerate(orig_lines):
            stripped = line.strip()
            if stripped and not any(stripped.startswith(s) for s in self.comment_symbols):
                last_prop_line = i
        
        # 在最后一个属性后添加新属性
        if new_props_lines:
            new_lines.insert(
                last_prop_line + 1, 
                "\n" + "#"*40 + "\n# 自动添加的属性\n" + "#"*40 + "\n"
            )
            new_lines.insert(last_prop_line + 2, "\n".join(new_props_lines) + "\n")
        
        # 构建最终内容
        return "".join(new_lines)
    
    def _create_backup(self) -> Optional[str]:
        """创建备份文件"""
        if not self.backup or not os.path.exists(self.fullpath):
            return None
            
        import time
        from datetime import datetime
        
        backup_dir = f"{self.fullpath}_backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"{os.path.basename(self.fullpath)}.backup_{timestamp}")
        
        shutil.copy2(self.fullpath, backup_file)
        self._log_info(f"创建文件备份: {backup_file}")
        
        # 清理旧备份
        self._cleanup_old_backups(backup_dir)
        
        return backup_file
    
    def _cleanup_old_backups(self, backup_dir):
        """清理旧备份（保留最新max_backups个）"""
        backups = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith("_backup") or f.endswith(".backup")],
            key=lambda x: os.path.getctime(os.path.join(backup_dir, x)),
            reverse=True
        )
        
        # 删除多余备份
        for old_backup in backups[self.max_backups:]:
            try:
                os.remove(os.path.join(backup_dir, old_backup))
                self._log_debug(f"删除旧备份: {old_backup}")
            except Exception as e:
                self._log_error(f"备份清理失败: {str(e)}")
    
    def _write_file(self, content: str):
        """写入新内容到文件"""
        with open(self.fullpath, 'w', encoding=self.encoding) as f:
            f.write(content)
        self._log_info(f"内容写入 {self.fullpath}")
    
    def _preserve_or_set_permissions(self):
        """保留或设置文件权限"""
        import os
        import grp
        import pwd
        
        # 设置权限
        os.chmod(self.fullpath, self.mode)
        
        # 设置所有者
        if self.owner:
            try:
                uid = pwd.getpwnam(self.owner).pw_uid
                os.chown(self.fullpath, uid, -1)
            except KeyError:
                self._log_warning(f"用户不存在: {self.owner}")
        
        # 设置组
        if self.group:
            try:
                gid = grp.getgrnam(self.group).gr_gid
                os.chown(self.fullpath, -1, gid)
            except KeyError:
                self._log_warning(f"组不存在: {self.group}")
    
    def _preserve_timestamps(self):
        """保留原始时间戳（仅当未更改权限时）"""
        if hasattr(self, 'orig_timestamps'):
            if self.owner or self.group or self.mode != self.orig_mode:
                return
                
            os.utime(self.fullpath, 
                    (self.orig_timestamps['atime'], 
                     self.orig_timestamps['mtime']))
    
    def _request_confirmation(self, changes: Dict) -> bool:
        """请求用户确认变更"""
        print("="*60)
        print(f"即将修改文件: {self.fullpath}")
        print("-"*60)
        
        # 显示变更摘要
        if changes["added"]:
            print("添加的属性:")
            for key, value in changes["added"].items():
                masked_value = self._mask_sensitive(key, value)
                print(f"  + {key} = {masked_value}")
        
        if changes["changed"]:
            print("\n修改的属性:")
            for key, vals in changes["changed"].items():
                old_val = self._mask_sensitive(key, vals["old"])
                new_val = self._mask_sensitive(key, vals["new"])
                print(f"  ~ {key} = {old_val} → {new_val}")
        
        if changes["removed"]:
            print("\n删除的属性:")
            for key, value in changes["removed"].items():
                print(f"  - {key} = {self._mask_sensitive(key, value)}")
        
        print("="*60)
        response = input("确认应用这些变更吗? (y/N) ").lower()
        return response == "y" or response == "yes"
    
    def _mask_sensitive(self, key: str, value: str) -> str:
        """掩码敏感数据值"""
        if (key in self.sensitive_keys or 
            any(word in key.lower() for word in ['password', 'secret', 'key'])):
            return "******"
        return value
    
    def _cleanup(self):
        """清理工作空间"""
        try:
            import shutil
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception as e:
            self._log_error(f"清理失败: {self.tmp_dir} - {str(e)}")
    
    def _log_info(self, message: str):
        logging.info(f"[ModifyPropertiesFile] {self.name}: {message}")
    
    def _log_warning(self, message: str):
        logging.warning(f"[ModifyPropertiesFile] {self.name}: {message}")
    
    def _log_error(self, message: str):
        logging.error(f"[ModifyPropertiesFile] {self.name}: {message}")
    
    def _log_debug(self, message: str):
        logging.debug(f"[ModifyPropertiesFile] {self.name}: {message}")
