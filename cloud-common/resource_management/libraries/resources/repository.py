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

企业级软件仓库管理系统
"""

from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
import os
import logging
import re
import tempfile
import shutil
import json
from typing import Dict, List, Union

class Repository(Resource):
    """
    软件仓库管理资源
    
    提供全面的软件仓库管理功能，支持:
    - 多仓库格式支持(APT/YUM/Zypper/Pip/NPM等)
    - GPG密钥自动管理
    - 代理和镜像设置
    - 仓库优先级控制
    - 企业级安全验证
    - 多平台支持
    
    使用示例:
        Repository(
            name="cloudera-repo",
            repo_id="cloudera-repository",
            base_url="https://archive.cloudera.com/cm7/ubuntu/xenial/amd64/cm",
            distribution="xenial",
            components=["cloudera-manager"],
            repo_type="apt",
            gpg_key="https://archive.cloudera.com/cm7/ubuntu/xenial/amd64/cm/archive.key",
            priority=500,
            proxy="http://proxy.example.com:3128",
            action="create"
        )
    """
    
    # 操作类型
    ACTION_CHOICES = ["prepare", "create", "verify", "remove", "clean"]
    
    action = ForcedListArgument(
        default="create",
        choices=ACTION_CHOICES,
        description="操作类型: 准备(prepare)/创建(create)/验证(verify)/移除(remove)/清理(clean)"
    )
    
    # 仓库标识
    repo_id = ResourceArgument(
        default=lambda obj: obj.name,
        description="仓库唯一标识符"
    )
    
    # 仓库配置
    repo_type = ResourceArgument(
        default="apt",
        choices=["apt", "yum", "zypper", "pip", "npm"],
        description="仓库类型(apt/yum/zypper/pip/npm)"
    )
    base_url = ResourceArgument(
        description="仓库基础URL"
    )
    mirror_list = ResourceArgument(
        default=None,
        description="镜像列表URL(YUM专属)"
    )
    
    # 仓库组件(APT专属)
    distribution = ResourceArgument(
        description="发行版名称",
    )
    components = ForcedListArgument(
        default=[],
        description="仓库组件列表"
    )
    
    # 安全配置
    gpg_key = ResourceArgument(
        default=None,
        description="GPG密钥URL或文件路径"
    )
    gpg_check = BooleanArgument(
        default=True,
        description="启用GPG验证"
    )
    trusted = BooleanArgument(
        default=False,
        description="信任仓库(跳过验证)"
    )
    
    # 高级配置
    priority = ResourceArgument(
        default=None,
        description="仓库优先级(数值越小优先级越高)"
    )
    proxy = ResourceArgument(
        default=None,
        description="仓库访问的HTTP代理"
    )
    exclusive = BooleanArgument(
        default=False,
        description="独占仓库(禁用其他仓库)"
    )
    architecture = ResourceArgument(
        default="amd64",
        choices=["amd64", "x86_64", "arm64", "ppc64le"],
        description="目标架构"
    )
    
    # 模板配置
    repo_file_name = ResourceArgument(
        default=None,
        description="仓库文件路径"
    )
    repo_template = ResourceArgument(
        default=None,
        description="自定义模板路径"
    )
    
    # 验证配置
    verification_key = ResourceArgument(
        default=None,
        description="仓库验证密钥"
    )
    
    # 支持的操作
    actions = Resource.actions + ACTION_CHOICES
    
    # 仓库模板映射
    REPO_TEMPLATES = {
        "apt": "templates/apt_repo.j2",
        "yum": "templates/yum_repo.j2",
        "zypper": "templates/zypper_repo.j2",
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prepared = False
        self._gpg_imported = False
        self._repo_path = None
        self._prepare_repository()
        
    def _prepare_repository(self):
        """准备仓库资源"""
        if not self.repo_id:
            raise ValueError("必须提供仓库标识符(repo_id)")
            
        # 自动确定仓库路径
        self._determine_repo_path()
        
        # 自动确定模板
        self._determine_template()
        
        # 准备基础URL
        self._validate_base_url()
        
        self._prepared = True
    
    def _determine_repo_path(self):
        """确定仓库文件路径"""
        if self.repo_file_name:
            self._repo_path = self.repo_file_name
            return
            
        # 根据仓库类型选择默认路径
        base_path = "/etc/apt/sources.list.d" if self.repo_type == "apt" \
            else "/etc/yum.repos.d" if self.repo_type == "yum" \
            else "/etc/zypp/repos.d" if self.repo_type == "zypper" \
            else None
            
        if not base_path:
            self._log_warning("无法确定仓库文件位置")
            return None
            
        self._repo_path = os.path.join(base_path, f"{self.repo_id}.repo")
    
    def _determine_template(self):
        """确定仓库模板"""
        if self.repo_template:
            return
            
        # 默认模板路径
        default_template = self.REPO_TEMPLATES.get(self.repo_type)
        if default_template and os.path.exists(default_template):
            self.repo_template = default_template
    
    def _validate_base_url(self):
        """验证基础URL格式"""
        if not self.base_url:
            raise ValueError("必须提供基础URL(base_url)")
            
        # 添加协议前缀(如果缺少)
        if not self.base_url.startswith(("http://", "https://", "ftp://")):
            self._log_warning(f"URL缺少协议前缀: {self.base_url}")
            self.base_url = "https://" + self.base_url
    
    def prepare(self):
        """准备阶段:验证配置但不写入文件"""
        if not self._prepared:
            self._prepare_repository()
            return False
            
        try:
            # 验证关键配置
            self.validate_config()
            
            # 导入GPG密钥(如果需要)
            if self.gpg_key and not self._gpg_imported:
                self.import_gpg_key()
                
            # 验证仓库元数据(如果需要)
            if "verify" in self.action:
                return self.verify_repository()
                
            return True
        except Exception as e:
            self._log_error(f"准备失败: {str(e)}")
            return False
    
    def validate_config(self):
        """验证仓库配置"""
        errors = []
        
        # 检查必填字段
        if not self.distribution and self.repo_type in ["apt", "zypper"]:
            errors.append("必须提供distribution参数")
            
        if not self.components and self.repo_type == "apt":
            errors.append("必须提供components参数")
            
        # 检查URL安全性
        if not self.base_url.startswith("https://"):
            self._log_warning(f"不安全的HTTP仓库URL: {self.base_url}")
            
        if "verify" in self.action:
            if not self.verification_key:
                errors.append("仓库验证需要提供verification_key")
                
        # 抛出累积错误
        if errors:
            raise RepositoryConfigurationError("配置验证失败: " + "; ".join(errors))
            
        return True
    
    def import_gpg_key(self):
        """导入GPG密钥"""
        key_type = "url" if self.gpg_key.startswith("http") else "file"
        
        if key_type == "url":
            # 从URL下载并导入密钥
            import requests
            try:
                response = requests.get(self.gpg_key, timeout=10)
                response.raise_for_status()
                
                # 存储临时密钥文件
                key_data = response.text
                with tempfile.NamedTemporaryFile(delete=False) as tmp_key:
                    tmp_key.write(key_data.encode())
                    tmp_key_path = tmp_key.name
                    
                return self._import_gpg_file(tmp_key_path)
            except Exception as e:
                raise GPGKeyError(f"无法下载GPG密钥: {str(e)}")
        else:
            # 从文件导入
            return self._import_gpg_file(self.gpg_key)
            
    def _import_gpg_file(self, key_path):
        """从文件导入GPG密钥"""
        try:
            # 根据仓库类型导入密钥
            if self.repo_type == "apt":
                # 导入APT密钥
                os.system(f"apt-key add {key_path}")
                self._log_info(f"导入APT密钥: {key_path}")
                
            elif self.repo_type == "yum" or self.repo_type == "zypper":
                # 创建RPM-GPG目录
                gpg_dir = "/etc/pki/rpm-gpg"
                os.makedirs(gpg_dir, exist_ok=True)
                
                # 复制密钥到指定位置
                dest_path = os.path.join(gpg_dir, f"RPM-GPG-KEY-{self.repo_id}")
                shutil.copy2(key_path, dest_path)
                self._log_info(f"存储RPM-GPG密钥: {dest_path}")
                
                # 手动导入密钥
                os.system(f"rpm --import {dest_path}")
                
            self._gpg_imported = True
            return True
        except Exception as e:
            raise GPGKeyError(f"导入GPG密钥失败: {str(e)}")
    
    def verify_repository(self):
        """验证仓库元数据和签名"""
        if not self._prepared:
            self._log_error("仓库未准备就绪")
            return False
            
        # 验证签名密钥
        if not self._validate_gpg_signature():
            return False
            
        # 验证仓库完整性
        return self._validate_repo_integrity()
    
    def _validate_gpg_signature(self):
        """验证GPG签名"""
        if not self.gpg_key or not self.verification_key:
            self._log_warning("跳过GPG签名验证，缺少必要参数")
            return True
            
        # 模拟签名验证
        # 在实际实现中我们会使用pgp库进行验证
        self._log_info(f"验证仓库签名: {self.repo_id}")
        
        # 验证签名匹配
        expected_key = self.verification_key.strip().lower()
        provided_key = self.gpg_key_hash = self._hash_key(self.gpg_key)
        
        if expected_key == provided_key:
            self._log_info("GPG签名验证通过")
            return True
        else:
            self._log_error(f"GPG签名不匹配: 期望={expected_key}, 实际={provided_key}")
            return False
            
    def _hash_key(self, key_data):
        """计算密钥的模拟哈希值"""
        import hashlib
        if key_data.startswith("http"):
            key_content = requests.get(key_data).text.encode()
        else:
            with open(key_data, "rb") as f:
                key_content = f.read()
                
        return hashlib.sha256(key_content).hexdigest()[:8]  # 取短哈希
    
    def _validate_repo_integrity(self):
        """验证仓库元数据完整性"""
        # 检查URL是否可达
        return self._check_url_reachable(self.base_url)
        
    def _check_url_reachable(self, url):
        """检查URL是否可访问"""
        import requests
        try:
            response = requests.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def create(self):
        """创建仓库配置文件"""
        if "prepare" not in self.action and not self.prepare():
            return False
            
        if not self.repo_template:
            self._log_error("缺少仓库模板配置")
            return False
            
        # 生成仓库配置内容
        config_content = self._generate_repo_config()
        
        # 写入仓库文件
        return self._write_repo_file(config_content)
    
    def remove(self):
        """移除仓库配置"""
        if not self._repo_path:
            self._log_error("无法确定仓库文件位置")
            return False
            
        # 检查文件是否存在
        if not os.path.exists(self._repo_path):
            self._log_warning(f"仓库文件不存在: {self._repo_path}")
            return True
            
        try:
            # 备份原文件
            backup_path = f"{self._repo_path}.bak"
            shutil.copy2(self._repo_path, backup_path)
            self._log_info(f"创建备份: {backup_path}")
            
            # 删除仓库文件
            os.remove(self._repo_path)
            self._log_info(f"移除仓库文件: {self._repo_path}")
            
            # 移除GPG密钥(如果存在)
            if self.gpg_key and self._gpg_imported:
                self._remove_gpg_key()
                
            return True
        except Exception as e:
            self._log_error(f"移除仓库失败: {str(e)}")
            return False
    
    def _remove_gpg_key(self):
        """移除关联的GPG密钥"""
        # 根据仓库类型移除密钥
        if self.repo_type == "apt":
            # 获取密钥指纹
            key_fingerprint = self._get_gpg_fingerprint()
            if key_fingerprint and not self._is_key_used(key_fingerprint):
                os.system(f"apt-key del {key_fingerprint}")
                self._log_info(f"移除APT密钥: {key_fingerprint}")
            
        elif self.repo_type in ["yum", "zypper"]:
            # 移除RPM-GPG密钥文件
            key_path = os.path.join("/etc/pki/rpm-gpg", f"RPM-GPG-KEY-{self.repo_id}")
            if os.path.exists(key_path):
                os.remove(key_path)
                self._log_info(f"移除RPM-GPG密钥: {key_path}")
    
    def _get_gpg_fingerprint(self):
        """获取密钥指纹(模拟实现)"""
        # 实际实现会使用GPG解析密钥
        return "ABCD1234"
    
    def _is_key_used(self, fingerprint):
        """检查密钥是否被其他仓库使用(模拟实现)"""
        return False
    
    def _generate_repo_config(self) -> str:
        """生成仓库配置文件内容"""
        from jinja2 import Template
        
        # 准备模板上下文
        context = {
            "repo_id": self.repo_id,
            "name": self.name,
            "base_url": self.base_url,
            "mirror_list": self.mirror_list,
            "distribution": self.distribution,
            "components": self.components,
            "gpg_check": self.gpg_check,
            "gpg_key": self.gpg_key,
            "priority": self.priority,
            "proxy": self.proxy,
            "architecture": self.architecture,
            "exclusive": self.exclusive,
            "trusted": self.trusted,
        }
        
        # 加载模板
        try:
            with open(self.repo_template, "r") as template_file:
                template = Template(template_file.read())
                
            return template.render(context)
        except Exception as e:
            raise TemplateError(f"生成仓库配置失败: {str(e)}")
    
    def _write_repo_file(self, content) -> bool:
        """写入仓库文件"""
        if not self._repo_path:
            self._log_error("未指定仓库文件路径")
            return False
            
        try:
            # 创建目录(如果不存在)
            os.makedirs(os.path.dirname(self._repo_path), exist_ok=True)
            
            # 备份现有文件
            if os.path.exists(self._repo_path):
                backup_name = self._repo_path + ".bak"
                shutil.copy2(self._repo_path, backup_name)
                self._log_info(f"备份现有仓库文件: {backup_name}")
            
            # 写入新内容
            with open(self._repo_path, "w") as repo_file:
                repo_file.write(content)
                
            self._log_info(f"仓库配置文件已创建: {self._repo_path}")
            self._log_debug(f"配置文件内容:\n{'-'*30}\n{content}\n{'-'*30}")
            
            # 刷新仓库缓存
            return self._refresh_repository_cache()
        except Exception as e:
            self._log_error(f"写入仓库文件失败: {str(e)}")
            return False
    
    def _refresh_repository_cache(self) -> bool:
        """刷新仓库缓存"""
        refresh_command = {
            "apt": "apt-get update",
            "yum": "yum clean all && yum makecache",
            "zypper": "zypper refresh",
            "pip": "echo 'Pip cache refresh not implemented'",
            "npm": "npm cache verify"
        }.get(self.repo_type, None)
        
        if not refresh_command:
            return True
            
        try:
            self._log_info("刷新仓库缓存...")
            command = refresh_command.split()
            subprocess.run(command, capture_output=True, text=True, check=True)
            self._log_info("仓库缓存刷新成功")
            return True
        except Exception as e:
            self._log_error(f"刷新仓库缓存失败: {str(e)}")
            return False
    
    def clean(self):
        """清理仓库残留"""
        removed = True
        
        # 删除仓库文件
        if self._repo_path and os.path.exists(self._repo_path):
            try:
                os.remove(self._repo_path)
                self._log_info(f"移除仓库文件: {self._repo_path}")
            except:
                removed = False
                self._log_error(f"无法删除文件: {self._repo_path}")
        
        # 删除备份文件
        if self._repo_path:
            backup_path = f"{self._repo_path}.bak"
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                    self._log_info(f"移除备份文件: {backup_path}")
                except:
                    removed = False
                    self._log_error(f"无法删除文件: {backup_path}")
        
        # 移除GPG密钥
        if self.gpg_key and self._gpg_imported:
            try:
                self._remove_gpg_key()
                self._gpg_imported = False
            except:
                self._log_error("GPG密钥清理失败")
                removed = False
                
        return removed
    
    def _log_info(self, message):
        logging.info(f"[Repository] {self.repo_id}: {message}")
        
    def _log_warning(self, message):
        logging.warning(f"[Repository] {self.repo_id}: {message}")
        
    def _log_error(self, message):
        logging.error(f"[Repository] {self.repo_id}: {message}")
        
    def _log_debug(self, message):
        logging.debug(f"[Repository] {self.repo_id}: {message}")


# 自定义异常类
class RepositoryError(Exception):
    """仓库错误基类"""
    pass

class RepositoryConfigurationError(RepositoryError):
    """配置错误"""
    pass

class GPGKeyError(RepositoryError):
    """GPG密钥错误"""
    pass

class TemplateError(RepositoryError):
    """模板处理错误"""
    pass

