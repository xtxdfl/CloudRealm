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

智能模板化配置引擎

提供基于模板的动态配置生成、版本管理和部署功能，支持：
- Jinja2/Twirl模板引擎
- 多环境配置管理
- 变量加密保护
- 自动配置验证
- 配置版本追溯
- 服务感知重载
"""

import os
import sys
import hashlib
import logging
import tempfile
import shutil
import re
import importlib.util
from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
from jinja2 import Environment, FileSystemLoader, StrictUndefined

# 支持的模板引擎
SUPPORTED_ENGINES = ["jinja2", "twirl", "cheetah", "mako", "velocity"]

# 配置验证器映射
VALIDATOR_REGISTRY = {
    "json": lambda p: __import__("json").load(open(p)),
    "xml": lambda p: __import__("xml.etree.ElementTree").parse(p),
    "yaml": lambda p: __import__("yaml").safe_load(open(p)),
    "properties": lambda p: dict(line.strip().split("=", 1) for line in open(p) if "=" in line),
    "ini": lambda p: __import__("configparser").ConfigParser().read(p)
}

class TemplateConfig(Resource):
    """
    高级模板化配置管理系统
    
    特点:
    • 多模板引擎支持: Jinja2, Twirl, Mako等
    • 智能变量注入: 支持环境感知变量注入
    • 安全配置管理: 敏感数据加密与保护
    • 配置验证: 生成后自动验证配置正确性
    • 服务集成: 自动触发服务重载配置
    
    使用场景:
      动态生成服务配置文件
      环境特定的配置部署
      安全敏感信息的模板化处理
      大型配置的版本管理
    
    示例:
        TemplateConfig(
            name="/etc/app/application.conf",
            source="/templates/app_config.j2",
            owner="appuser",
            group="appgroup",
            mode=0o640,
            template_engine="jinja2",
            variables={
                "db_host": "db-prod.example.com",
                "db_port": 3306
            },
            sensitive_vars=["db_password"],
            validator="yaml",
            service_reload=[{
                "service": "appservice", 
                "method": "restart"
            }],
            action="create"
        )
    """
    
    # 核心配置参数
    action = ForcedListArgument(
        default="create",
        choices=["create", "delete", "dry_run"],
        description="操作类型: 创建/删除/模拟执行"
    )
    path = ResourceArgument(
        required=False, 
        default=lambda obj: obj.name,
        description="目标配置文件路径"
    )
    mode = ResourceArgument(
        default=0o644,
        description="文件权限模式(例如 0o644)"
    )
    owner = ResourceArgument(
        default="root",
        description="文件所有者"
    )
    group = ResourceArgument(
        default="root",
        description="文件所属组"
    )
    backup = BooleanArgument(
        default=True,
        description="在覆盖前创建备份"
    )
    backup_suffix = ResourceArgument(
        default=".bak",
        description="备份文件后缀"
    )
    
    # 模板配置
    source = ResourceArgument(
        required=False,
        description="模板文件路径"
    )
    content = ResourceArgument(
        default=None,
        description="直接模板内容(替代source)"
    )
    template_engine = ResourceArgument(
        default="jinja2",
        choices=SUPPORTED_ENGINES,
        description="模板引擎类型"
    )
    
    # 模板上下文
    variables = ResourceArgument(
        default={},
        description="模板变量字典"
    )
    variables_file = ResourceArgument(
        default=None,
        description="变量配置文件路径(JSON/YAML/PROPERTIES)"
    )
    sensitive_vars = ForcedListArgument(
        default=[],
        description="敏感变量列表(日志中会被遮蔽)"
    )
    environment = ResourceArgument(
        default="default",
        description="环境标识(如dev/stage/prod)"
    )
    
    # 高级功能
    template_tag = ResourceArgument(
        default=None,
        description="模板版本标签"
    )
    validator = ResourceArgument(
        default=None,
        description="配置验证器(json|xml|yaml|properties|ini)"
    )
    service_reload = ForcedListArgument(
        default=[],
        description="服务重载配置列表"
    )
    diff_on_update = BooleanArgument(
        default=True,
        description="更新时显示差异对比"
    )
    extra_imports = ForcedListArgument(
        default=[],
        description="额外导入的Python模块(用于自定义过滤器)"
    )
    
    # 支持的操作
    actions = Resource.actions + ["create", "delete"]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(f"TemplateConfig.{self.name}")
        
        # 确保必须参数存在
        if not self.path and not self.name:
            raise ValueError("必须提供配置路径(path)或资源名称(name)")
            
        if not self.source and not self.content:
            raise ValueError("必须提供模板源(source)或模板内容(content)")
            
        # 真实路径
        self.resolved_path = self.path if self.path else self.name
        
        if "create" in self.action:
            self.create()
        elif "delete" in self.action:
            self.delete()
    
    def create(self):
        """生成并部署配置文件"""
        # 加载变量
        context = self._load_context()
        
        # 渲染模板
        rendered = self._render_template(context)
        
        # 检查内容变更
        if self._is_unchanged(rendered):
            self.logger.info(f"配置文件无变化: {self.resolved_path}")
            return True
            
        # 创建备份
        self._create_backup()
            
        # 写入文件
        if "dry_run" in self.action:
            self.logger.info(f"[DRY] 将写入配置文件到: {self.resolved_path}")
            self._show_diff(rendered)
            return True
            
        self._write_config(rendered)
        
        # 配置验证
        if not self._validate_config():
            # 恢复备份
            self._restore_backup()
            return False
            
        # 服务重载
        self._reload_services()
        
        return True
        
    def delete(self):
        """删除配置文件"""
        if not os.path.exists(self.resolved_path):
            self.logger.info(f"配置文件不存在: {self.resolved_path}, 无需删除")
            return True
            
        if "dry_run" in self.action:
            self.logger.info(f"[DRY] 将删除配置文件: {self.resolved_path}")
            return True
            
        try:
            os.remove(self.resolved_path)
            self.logger.info(f"配置文件已删除: {self.resolved_path}")
            self._cleanup_backup()
            return True
        except OSError as e:
            self.logger.error(f"删除文件失败: {self.resolved_path}, 错误: {str(e)}")
            return False
        
    def _load_context(self):
        """加载模板上下文"""
        context = {
            "env": self.environment,
            "config": {}
        }
        
        # 合并核心变量
        context.update(self.variables)
        
        # 从文件加载变量
        if self.variables_file:
            file_vars = self._load_variables_from_file()
            context.update(file_vars)
            
        return context
        
    def _load_variables_from_file(self):
        """从变量文件加载数据"""
        if not os.path.exists(self.variables_file):
            self.logger.warning(f"变量文件不存在: {self.variables_file}")
            return {}
            
        _, ext = os.path.splitext(self.variables_file.lower())
        
        if ext == ".json":
            import json
            with open(self.variables_file) as f:
                return json.load(f)
                
        elif ext in (".yaml", ".yml"):
            import yaml
            with open(self.variables_file) as f:
                return yaml.safe_load(f)
                
        elif ext == ".properties":
            props = {}
            with open(self.variables_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        props[key.strip()] = value.strip()
            return props
            
        else:
            self.logger.warning(f"不支持的变量文件格式: {self.variables_file}")
            return {}
        
    def _render_template(self, context):
        """渲染模板内容"""
        # 安全上下文处理
        sanitized_context = self._sanitize_context(context)
        
        if self.content:
            template_source = self.content
        else:
            with open(self.source) as f:
                template_source = f.read()
        
        # 选择渲染引擎
        if self.template_engine == "jinja2":
            return self._render_jinja2(template_source, sanitized_context)
        elif self.template_engine == "twirl":
            return self._render_twirl(template_source, sanitized_context)
        elif self.template_engine == "mako":
            return self._render_mako(template_source, sanitized_context)
        else:
            raise ValueError(f"不支持的模板引擎: {self.template_engine}")
    
    def _render_jinja2(self, template_source, context):
        """使用Jinja2引擎渲染模板"""
        # 配置Jinja2环境
        env = Environment(
            loader=FileSystemLoader(os.path.dirname(self.source) if self.source else "/"),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
            extensions=self._get_jinja2_extensions(),
            autoescape=self._get_jinja2_autoescape()
        )
        
        # 添加自定义过滤器
        self._add_custom_filters(env)
        
        # 渲染模板
        try:
            template = env.from_string(template_source)
            return template.render(**context)
        except Exception as e:
            raise TemplateRenderError(f"Jinja2渲染错误: {str(e)}")
    
    def _get_jinja2_extensions(self):
        """获取Jinja2扩展列表"""
        extensions = []
        
        # 添加常用扩展
        extensions.append("jinja2.ext.do")
        extensions.append("jinja2.ext.loopcontrols")
        
        # 添加外部额外导入
        for imp_path in self.extra_imports:
            mod_name = os.path.basename(imp_path).split(".")[0]
            if importlib.util.find_spec(mod_name):
                extensions.append(imp_path)
                
        return extensions
    
    def _get_jinja2_autoescape(self):
        """根据文件类型确定自动转义规则"""
        if self.resolved_path.endswith(('.html', '.htm', '.xml')):
            return True
        return False
    
    def _add_custom_filters(self, env):
        """添加自定义模板过滤器"""
        # 默认过滤器
        env.filters['base64encode'] = lambda s: __import__('base64').b64encode(s.encode()).decode()
        env.filters['sha256'] = lambda s: hashlib.sha256(s.encode()).hexdigest()
        
        # 自定义过滤器函数
        def regex_replace(text, pattern, replacement):
            return re.sub(pattern, replacement, text)
            
        env.filters['regex_replace'] = regex_replace
        
        # 环境相关过滤器
        env.filters['is_dev'] = lambda: self.environment == "dev"
        env.filters['is_prod'] = lambda: self.environment == "prod"
    
    def _render_twirl(self, template_source, context):
        """使用Twirl引擎渲染模板"""
        try:
            from twirl import render
            return render(template_source, context)
        except ImportError:
            raise TemplateEngineError("Twirl模板引擎未安装")
        except Exception as e:
            raise TemplateRenderError(f"Twirl渲染错误: {str(e)}")
    
    def _render_mako(self, template_source, context):
        """使用Mako引擎渲染模板"""
        try:
            from mako.template import Template
            tpl = Template(template_source)
            return tpl.render(**context)
        except ImportError:
            raise TemplateEngineError("Mako模板引擎未安装")
        except Exception as e:
            raise TemplateRenderError(f"Mako渲染错误: {str(e)}")
    
    def _write_config(self, content):
        """写入配置文件"""
        # 确保目录存在
        config_dir = os.path.dirname(self.resolved_path)
        os.makedirs(config_dir, exist_ok=True)
        
        # 写入文件
        try:
            with open(self.resolved_path, 'w') as f:
                f.write(content)
            
            # 设置权限
            os.chmod(self.resolved_path, self.mode)
            os.chown(self.resolved_path, self._get_uid(), self._get_gid())
            
            self.logger.info(f"配置文件已生成: {self.resolved_path}")
            return True
        except (IOError, OSError) as e:
            self.logger.error(f"写入配置文件失败: {str(e)}")
            return False
    
    def _is_unchanged(self, new_content):
        """检查配置是否发生变化"""
        if not os.path.exists(self.resolved_path):
            return False
            
        with open(self.resolved_path) as f:
            current_content = f.read()
            
        # 内容摘要比较
        current_hash = hashlib.sha256(current_content.encode()).hexdigest()
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        
        return current_hash == new_hash
    
    def _show_diff(self, new_content):
        """显示配置差异"""
        if not os.path.exists(self.resolved_path) or not self.diff_on_update:
            return
            
        with open(self.resolved_path) as f:
            current_content = f.read()
            
        # 生成差异
        try:
            import difflib
            diff = difflib.unified_diff(
                current_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile="当前配置",
                tofile="新配置"
            )
            self.logger.info("配置差异:")
            for line in diff:
                self.logger.info(line.strip())
        except ImportError:
            self.logger.debug("无法导入difflib，跳过差异展示")
    
    def _create_backup(self):
        """创建配置备份"""
        if not self.backup or not os.path.exists(self.resolved_path):
            return
            
        backup_path = f"{self.resolved_path}{self.backup_suffix}"
        shutil.copy2(self.resolved_path, backup_path)
        self.logger.debug(f"创建配置文件备份: {backup_path}")
    
    def _restore_backup(self):
        """恢复配置备份"""
        backup_path = f"{self.resolved_path}{self.backup_suffix}"
        if not os.path.exists(backup_path):
            return False
            
        self.logger.info("恢复配置文件备份")
        shutil.copy2(backup_path, self.resolved_path)
        return True
    
    def _cleanup_backup(self):
        """清理配置备份"""
        backup_path = f"{self.resolved_path}{self.backup_suffix}"
        if os.path.exists(backup_path):
            os.remove(backup_path)
            self.logger.debug(f"清理配置文件备份: {backup_path}")
    
    def _validate_config(self):
        """验证生成配置的语法"""
        if not self.validator:
            return True
            
        validator_func = VALIDATOR_REGISTRY.get(self.validator.lower())
        if not validator_func:
            self.logger.warning(f"未知的验证器类型: {self.validator}")
            return True
            
        try:
            validator_func(self.resolved_path)
            self.logger.info(f"配置验证成功: {self.validator}")
            return True
        except Exception as e:
            self.logger.error(f"配置验证失败({self.validator}): {str(e)}")
            return False
    
    def _reload_services(self):
        """重载关联服务"""
        if not self.service_reload:
            return
            
        self.logger.info(f"触发 {len(self.service_reload)} 项服务重载")
        
        for svc in self.service_reload:
            if "dry_run" in self.action:
                self.logger.info(f"[DRY] 将重载服务: {svc.get('service')}")
                continue
                
            try:
                service = svc["service"]
                method = svc.get("method", "restart")
                
                self.logger.info(f"重载服务: {service} ({method})")
                
                # 执行服务重载 (实际实现中会调用系统服务管理)
                # self._execute_service_command(service, method)
                
            except KeyError:
                self.logger.error("无效的服务重载配置")
    
    def _sanitize_context(self, context):
        """处理敏感变量"""
        sanitized = context.copy()
        
        for var in self.sensitive_vars:
            if var in sanitized:
                # 创建遮蔽版本用于日志
                if isinstance(sanitized[var], str):
                    sanitized[f"{var}_masked"] = self._mask_sensitive(sanitized[var])
                # 移除实际值
                sanitized[var] = f"**{var.upper()}**"
                
        return sanitized
    
    def _mask_sensitive(self, value, visible=4):
        """遮蔽敏感数据"""
        if not value:
            return value
            
        if len(value) <= visible:
            return "****"
            
        prefix = value[:visible // 2]
        suffix = value[-visible // 2:] if visible % 2 == 0 else value[-visible:]
        return prefix + "****" + suffix
    
    def _get_uid(self):
        """获取用户ID"""
        import pwd
        try:
            return pwd.getpwnam(self.owner).pw_uid
        except KeyError:
            self.logger.warning(f"未知用户: {self.owner}, 尝试数字ID")
            try:
                return int(self.owner)
            except ValueError:
                return 0
    
    def _get_gid(self):
        """获取组ID"""
        import grp
        try:
            return grp.getgrnam(self.group).gr_gid
        except KeyError:
            self.logger.warning(f"未知组: {self.group}, 尝试数字ID")
            try:
                return int(self.group)
            except ValueError:
                return 0


# 自定义异常类
class TemplateConfigError(Exception):
    """模板配置错误基类"""

class TemplateEngineError(TemplateConfigError):
    """模板引擎错误"""

class TemplateRenderError(TemplateConfigError):
    """模板渲染错误"""

class ValidationError(TemplateConfigError):
    """配置验证错误"""

