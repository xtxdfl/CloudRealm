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

Advanced Security Configuration Management Toolkit
"""

import os
import re
import json
import time
import hashlib
import logging
import tempfile
import configparser
import contextlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, OrderedDict
from typing import Dict, List, Tuple, Union, Optional, Any, Callable

import rapidjson as rjson
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from resource_management import Execute, File
from resource_management.core.source import StaticFile, InlineTemplate, ConfigTemplate
from resource_management.core.logger import Logger
from resource_management.core.exceptions import Fail, ExecutionFailed
from cloud_commons import os_utils, security_utils

# 配置文件类型常量
FILE_TYPE_XML = "XML"
FILE_TYPE_PROPERTIES = "PROPERTIES"
FILE_TYPE_JSON = "JSON"
FILE_TYPE_YAML = "YAML"
FILE_TYPE_JAAS_CONF = "JAAS_CONF"

# 凭证提供程序属性名
HADOOP_CREDENTIAL_PROVIDER_PROPERTY = "hadoop.security.credential.provider.path"
CREDENTIAL_PROVIDER_TYPES = {
    "jceks": "jceks",
    "localjceks": "localjceks",
    "vault": "vault",
    "cloud": "cloudkms"
}

# 安全配置验证规则
VALIDATION_RULES = {
    "value_checks": dict,
    "empty_checks": list,
    "read_checks": list,
    "pattern_checks": list,
    "relation_checks": dict
}

# 凭证缓存设置
KINIT_CACHE_DURATION = timedelta(minutes=15)
MAX_KINIT_CACHE_SIZE = 100

class SecurityConfigError(Exception):
    """安全配置异常基类"""
    pass

class CredentialProviderError(SecurityConfigError):
    """凭证提供程序异常"""
    pass

class ConfigValidationError(SecurityConfigError):
    """配置验证异常"""
    pass

class KerberosTicketManager:
    """Kerberos票据管理系统"""
    _cache = OrderedDict()
    
    def __init__(self, kinit_path: str, temp_dir: str):
        self.kinit_path = kinit_path
        self.temp_dir = Path(temp_dir) / "krb5_cache"
        self.temp_dir.mkdir(exist_ok=True, mode=0o700)
        
    def kinit(self, exec_user: str, keytab_file: str, principal: str, hostname: str) -> None:
        """执行kinit并缓存结�?""
        cache_key = self._get_cache_key(principal, keytab_file)
        
        # 检查有效缓�?        if self._is_cached_valid(cache_key):
            Logger.debug(f"使用缓存的Kerberos票据: {principal}")
            return
            
        # 创建加密缓存文件
        try:
            ccache_file = self._create_temp_ccache(exec_user)
            self._execute_kinit(exec_user, keytab_file, principal, hostname, ccache_file)
            self._update_cache(cache_key, ccache_file)
            Logger.info(f"Kerberos认证成功: {principal}")
        except Exception as e:
            Logger.error(f"Kerberos认证失败: {principal}, 错误: {str(e)}")
            raise SecurityConfigError(f"Kerberos认证失败: {str(e)}")
            
    def _get_cache_key(self, principal: str, keytab_file: str) -> str:
        """生成唯一缓存�?""
        keytag = security_utils.file_checksum(keytab_file)
        return f"{principal}@{keytag}"
        
    def _is_cached_valid(self, cache_key: str) -> bool:
        """检查缓存是否有�?""
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            
            # 更新访问顺序
            self._cache.move_to_end(cache_key)
            
            # 检查票据有效期
            return (datetime.now() - entry['timestamp']) < KINIT_CACHE_DURATION
        return False
        
    def _create_temp_ccache(self, owner: str) -> Path:
        """创建临时票据缓存文件"""
        fd, temp_path = tempfile.mkstemp(dir=str(self.temp_dir), suffix=".ccache")
        os.close(fd)
        ccache_file = Path(temp_path)
        os.chmod(ccache_file, 0o600)
        os_utils.chown(ccache_file, owner)
        return ccache_file
        
    def _execute_kinit(
        self,
        exec_user: str,
        keytab_file: str,
        principal: str,
        hostname: str,
        ccache_file: Path
    ) -> None:
        """执行kinit命令"""
        principal = principal.replace("_HOST", hostname)
        cmd = f"{self.kinit_path} -c {ccache_file} -kt {keytab_file} {principal}"
        Execute(cmd, user=exec_user, tries=3, try_sleep=5, timeout=90)
        
    def _update_cache(self, cache_key: str, ccache_file: Path) -> None:
        """更新缓存记录"""
        self._cache[cache_key] = {
            'ccache_file': ccache_file,
            'timestamp': datetime.now()
        }
        
        # 淘汰最老的缓存
        while len(self._cache) > MAX_KINIT_CACHE_SIZE:
            self._cache.popitem(last=False)

class CredentialProviderManager:
    """凭证提供程序管理系统"""
    
    def update_credential_provider_path(
        self,
        config: Dict,
        credential_name: str,
        dest_provider_path: str,
        file_owner: str,
        file_group: str,
        provider_type: str = "jceks",
        migrate_credentials: bool = True
    ) -> Dict:
        """
        更新凭证提供程序配置
        
        :param config: 配置字典
        :param credential_name: 凭证名称
        :param dest_provider_path: 目标提供程序路径
        :param file_owner: 文件所有�?        :param file_group: 文件所属组
        :param provider_type: 提供程序类型 (jceks/localjceks/vault/cloud)
        :param migrate_credentials: 是否迁移现有凭证
        :return: 更新后的配置字典
        """
        if HADOOP_CREDENTIAL_PROVIDER_PROPERTY not in config:
            Logger.info(f"配置未使用凭证提供程�? {credential_name}")
            return config
            
        # 处理不同提供程序类型
        provider_url = config[HADOOP_CREDENTIAL_PROVIDER_PROPERTY]
        provider_prefix = CREDENTIAL_PROVIDER_TYPES.get(provider_type, "jceks")
        
        # 迁移现有凭证（如果配置迁移）
        if migrate_credentials and provider_type != "vault":
            try:
                self._migrate_credentials(
                    provider_url, 
                    dest_provider_path,
                    file_owner,
                    file_group
                )
            except Exception as e:
                Logger.error(f"凭证迁移失败: {str(e)}")
                if provider_type == "jceks":
                    raise CredentialProviderError(f"凭证迁移失败: {str(e)}")
        
        # 创建配置副本并更�?        config_copy = config.copy()
        config_copy[HADOOP_CREDENTIAL_PROVIDER_PROPERTY] = f"{provider_prefix}://file{dest_provider_path}"
        
        # 创建凭证文件（如果不存在�?        if not os.path.exists(dest_provider_path):
            self._create_credential_store(
                dest_provider_path,
                file_owner,
                file_group
            )
        
        return config_copy
        
    def _migrate_credentials(
        self,
        source_url: str,
        dest_path: str,
        file_owner: str,
        file_group: str
    ) -> None:
        """迁移凭证文件"""
        # 从URL提取原文件路�?        if "://file" not in source_url:
            Logger.warning("源凭证提供程序不是文件类型，跳过迁移")
            return
            
        source_path = source_url.split("://file", 1)[1]
        if not os.path.exists(source_path):
            Logger.info("原凭证文件不存在，创建新凭证存储")
            return
            
        # 复制文件并设置权�?        shutil.copy2(source_path, dest_path)
        os.chmod(dest_path, 0o640)
        os_utils.chown(dest_path, file_owner, file_group)
        Logger.info(f"凭证已成功迁�? {source_path} -> {dest_path}")
        
    def _create_credential_store(
        self,
        jceks_path: str,
        file_owner: str,
        file_group: str
    ) -> None:
        """创建新的凭证存储文件"""
        # 创建空JCEKS文件
        with open(jceks_path, 'wb') as f:
            f.write(b'JCEKS_FILE_HEADER')
            
        os.chmod(jceks_path, 0o640)
        os_utils.chown(jceks_path, file_owner, file_group)
        Logger.info(f"创建新凭证存�? {jceks_path}")

class ConfigValidator:
    """安全配置验证引擎"""
    
    def validate_security_config_properties(
        self,
        configs: Dict,
        validation_rules: Dict
    ) -> Dict[str, str]:
        """
        根据验证规则验证安全配置
        :param configs: 配置字典 {config_name: {key: value}}
        :param validation_rules: 验证规则字典 {config_file: {rule_type: rules}}
        :return: 问题字典 {config_file: 错误信息}
        """
        issues = defaultdict(str)
        
        try:
            # 预加载所有配�?            loaded_configs = {name: self._load_config_values(cfg) for name, cfg in configs.items()}
            
            # 遍历验证规则
            for config_file, rule_set in validation_rules.items():
                if config_file not in loaded_configs:
                    issues[config_file] = f"配置缺失: {config_file}"
                    continue
                    
                actual_values = loaded_configs[config_file]
                config_issues = self._validate_rule_set(
                    config_file, actual_values, rule_set)
                
                if config_issues:
                    issues[config_file] = "\n".join(config_issues)
                    
        except Exception as e:
            issues["global"] = f"配置验证失败: {str(e)}"
            
        return dict(issues)
        
    def _load_config_values(self, config: Union[dict, str]) -> Dict:
        """根据类型加载配置�?""
        if isinstance(config, dict):
            return config
            
        try:
            if config.startswith("{"):
                return rjson.loads(config)
            return self._parse_config(config)
        except Exception:
            return {}
        
    def _parse_config(self, content: str) -> Dict:
        """初步解析配置内容"""
        # 在实际实现中应使用更复杂的解�?        return {}
    
    def _validate_rule_set(
        self,
        config_file: str,
        config: Dict,
        rules: Dict
    ) -> List[str]:
        """验证单个规则�?""
        issues = []
        
        # 值检�?        value_rules = rules.get("value_checks", {})
        for prop, expected in value_rules.items():
            actual = self._get_nested_value(config, prop)
            if actual != expected:
                issues.append(f"值不匹配: {prop} (期望: {expected}, 实际: {actual})")
        
        # 非空检�?        for prop in rules.get("empty_checks", []):
            value = self._get_nested_value(config, prop)
            if not value:
                issues.append(f"属性不能为�? {prop}")
                
        # 可读文件检�?        for prop in rules.get("read_checks", []):
            file_path = self._get_nested_value(config, prop)
            if not file_path or not os.access(file_path, os.R_OK):
                issues.append(f"无法读取文件: {prop}={file_path}")
                
        # 模式检�?        pattern_rules = rules.get("pattern_checks", [])
        for entry in pattern_rules:
            prop = entry.get('property')
            pattern = entry.get('pattern')
            if not prop or not pattern:
                continue
                
            value = self._get_nested_value(config, prop)
            if value and not re.match(pattern, str(value)):
                issues.append(f"属性格式无�? {prop} (�? {value}, 期望模式: {pattern})")
                
        # 关系检�?        relation_rules = rules.get("relation_checks", {})
        for prop, required in relation_rules.items():
            prop_value = self._get_nested_value(config, prop)
            required_value = self._get_nested_value(config, required)
            if prop_value and not required_value:
                issues.append(f"当设�?{prop} �? {required} 是必需�?)
                
        return issues
        
    def _get_nested_value(self, config: Dict, path: str, default: Any = None) -> Any:
        """获取嵌套配置�?""
        keys = path.split('.')
        current = config
        try:
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current
        except TypeError:
            return default

class ConfigManager:
    """统一配置管理�?""
    
    def __init__(self, conf_dir: str):
        self.conf_dir = Path(conf_dir)
        
    def get_configurations(self, target_files: Dict[str, str]) -> Dict[str, Dict]:
        """
        从文件系统加载多种格式的配置
        :param target_files: 目标文件字典 {filename: config_type}
        :return: 配置字典 {config_name: 解析后的配置}
        """
        configs = {}
        
        for filename, config_type in target_files.items():
            config_path = self.conf_dir / filename
            if not config_path.exists():
                Logger.warning(f"配置文件未找�? {config_path}")
                continue
                
            try:
                if config_type == FILE_TYPE_XML:
                    configs[filename] = self._parse_xml_config(config_path)
                elif config_type == FILE_TYPE_PROPERTIES:
                    configs[filename] = self._parse_properties_config(config_path)
                elif config_type == FILE_TYPE_JSON:
                    configs[filename] = self._parse_json_config(config_path)
                elif config_type == FILE_TYPE_JAAS_CONF:
                    configs[filename] = self._parse_jaas_config(config_path)
                else:
                    Logger.warning(f"未知配置文件类型: {config_type} for {filename}")
                    configs[filename] = {}
            except Exception as e:
                Logger.error(f"解析配置失败 {filename}: {str(e)}")
                configs[filename] = {}
                
        return configs
        
    def _parse_xml_config(self, config_path: Path) -> Dict:
        """解析XML格式配置文件"""
        tree = ET.parse(config_path)
        root = tree.getroot()
        config_dict = {}
        
        for property_tag in root.findall('property'):
            name_tag = property_tag.find('name')
            value_tag = property_tag.find('value')
            if name_tag is not None and value_tag is not None:
                config_dict[name_tag.text] = value_tag.text
                
        return config_dict
        
    def _parse_properties_config(self, config_path: Path) -> Dict:
        """解析Java属性格式配置文�?""
        parser = configparser.ConfigParser()
        with open(config_path, 'r') as f:
            # 添加占位段来解析无段头的属性文�?            data = '[root]\n' + f.read()
            parser.read_string(re.sub(r'\\\s*\n', '\\\n ', data))
        return dict(parser['root'])
        
    def _parse_json_config(self, config_path: Path) -> Dict:
        """解析JSON格式配置文件"""
        with open(config_path, 'r') as f:
            return rjson.load(f)
            
    def _parse_jaas_config(self, config_path: Path) -> Dict:
        """解析JAAS配置文件"""
        jaas_conf = {}
        section_name = "default"
        section_header = re.compile(r"^(\w+)\s+\{\s*$")
        section_footer = re.compile(r"^\}\s*;?\s*$")
        property_line = re.compile(r'^\s*(\S+?)\s*=\s*"?([^";]+)"?;?\s*$')
        
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # 检查段开�?                sec_match = section_header.match(line)
                if sec_match:
                    section_name = sec_match.group(1)
                    jaas_conf[section_name] = {}
                    continue
                    
                # 检查段结束
                if section_footer.match(line):
                    section_name = "default"
                    continue
                    
                # 解析属�?                prop_match = property_line.match(line)
                if prop_match:
                    prop_name, prop_value = prop_match.groups()
                    if section_name in jaas_conf:
                        jaas_conf[section_name][prop_name] = prop_value
                    else:
                        Logger.warning(f"JAAS property without section: {prop_name}")
        return jaas_conf

class SecurityConfigUtils:
    """安全配置实用程序"""
    
    @staticmethod
    def get_value(config_data: Dict, path: str, default: Any = None) -> Any:
        """
        从嵌套结构中获取�?        :param config_data: 配置数据 (dict/list)
        :param path: 点分隔路�?(例如: 'top/sub/key')
        :param default: 找不到时的默认�?        """
        if not path or not config_data:
            return default
            
        keys = path.split('.') if isinstance(path, str) else path
        current = config_data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
                current = current[int(key)]
            else:
                return default
        return current
        
    @staticmethod
    def build_validation_rules(
        value_checks: Optional[Dict] = None,
        empty_checks: Optional[List] = None,
        read_checks: Optional[List] = None,
        pattern_checks: Optional[List] = None,
        relation_checks: Optional[Dict] = None
    ) -> Dict:
        """构建验证规则�?""
        return {
            "value_checks": value_checks or {},
            "empty_checks": empty_checks or [],
            "read_checks": read_checks or [],
            "pattern_checks": pattern_checks or [],
            "relation_checks": relation_checks or {}
        }

# 全局管理器实�?credential_manager = CredentialProviderManager()
config_validator = ConfigValidator()
kerberos_manager = KerberosTicketManager(
    kinit_path="/usr/bin/kinit",
    temp_dir=tempfile.gettempdir()
)

def update_credential_provider(config, config_type, dest_provider_path, 
                               file_owner, file_group, use_local_jceks=False):
    """
    (兼容接口) 更新凭证提供程序路径
    """
    provider_type = "localjceks" if use_local_jceks else "jceks"
    return credential_manager.update_credential_provider_path(
        config=config,
        credential_name=config_type,
        dest_provider_path=dest_provider_path,
        file_owner=file_owner,
        file_group=file_group,
        provider_type=provider_type
    )

def validate_security_config_properties(params, configuration_rules):
    """
    (兼容接口) 验证安全配置属�?    """
    issues = config_validator.validate_security_config_properties(
        configs=params,
        validation_rules=configuration_rules
    )
    return issues

def build_expectations(config_file, value_checks, empty_checks, read_checks):
    """
    (兼容接口) 构建验证规则
    """
    return {
        config_file: SecurityConfigUtils.build_validation_rules(
            value_checks=value_checks,
            empty_checks=empty_checks,
            read_checks=read_checks
        )
    }

def get_params_from_filesystem(conf_dir, config_files):
    """
    (兼容接口) 从文件系统获取配置参�?    """
    config_manager = ConfigManager(conf_dir)
    return config_manager.get_configurations(target_files=config_files)

def kinit_executor(kinit_path, exec_user, keytab_file, principal, hostname, temp_dir):
    """
    (兼容接口) Kerberos认证执行�?    """
    kerberos_manager.kinit(
        kinit_path=kinit_path,
        temp_dir=temp_dir,
        exec_user=exec_user,
        keytab_file=keytab_file,
        principal=principal,
        hostname=hostname
    )

def get_value(values, property_path, default_value):
    """
    (兼容接口) 获取嵌套配置�?    """
    return SecurityConfigUtils.get_value(
        config_data=values,
        path=property_path,
        default=default_value
    )
