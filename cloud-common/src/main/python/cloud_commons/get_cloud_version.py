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

import os
import re
import logging
import configparser
from functools import lru_cache
from typing import Optional, Tuple, Dict
from packaging.version import parse as parse_version, Version

# 配置日志系统
logger = logging.getLogger("cloud_version")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# 环境变量常量
cloud_AGENT_CONF_ENV = "cloud_AGENT_CONF"
cloud_VERSION_FILE_ENV = "cloud_VERSION_PATH"
AGENT_PREFIX_KEY = "agent.prefix"

# 默认路径配置
PATHS = {
    "DEFAULT_CONF": "/etc/cloud-agent/conf/cloud-agent.ini",
    "ALTERNATIVE_CONF": "/opt/cloud-agent/conf/cloud-agent.ini",
    "DOCKER_VERSION_PATH": "/app/version",
    "DEFAULT_VERSION_FILE": "version",
    "ALTERNATIVE_VERSION_FILE": "current/version",
}

class cloudVersionError(Exception):
    """Custom exception for version detection issues"""
    def __init__(self, message, path=""):
        super().__init__(message)
        self.path = path
        logger.error(f"{message} [Path: {path}]")

def _parse_version_content(version_data: str) -> Tuple[Version, Dict[str, str]]:
    """
    解析版本文件的详细信息，支持多种格式
    
    格式示例:
        "2.7.6.0-2102" (简单格�?
        "version=2.8.1, build=6542, release=prod-2023" (键值对格式)
    """
    if not version_data:
        raise cloudVersionError("Empty version data")
    
    # 尝试解析键值对格式
    if '=' in version_data:
        components = {}
        # 安全地分割键值对
        for part in re.split(r',\s*|\s+', version_data.strip()):
            if '=' in part:
                key, val = part.split('=', 1)
                components[key.strip().lower()] = val.strip()
        
        if 'version' in components:
            base_version = components.get("build", components["version"])
            return parse_version(base_version), components
    
    # 处理简单版本格�?    clean_version = re.sub(r'[^0-9a-zA-Z\.\-]', '', version_data.split('\n')[0])
    if not clean_version:
        raise cloudVersionError("No valid version string found")
    
    return parse_version(clean_version), {"version": clean_version}

@lru_cache(maxsize=1)
def get_cloud_version_agent() -> Optional[Version]:
    """获取Agent安装的Cloud版本�?(带有缓存)"""
    version_info = get_detailed_version()
    return version_info[0] if version_info else None

def get_detailed_version() -> Optional[Tuple[Version, dict]]:
    """获取详细的版本信息，包括元数�?""
    try:
        # 1. 确定配置文件路径
        conf_path = _resolve_config_path()
        if not conf_path:
            logger.error("Cannot locate cloud-agent configuration file")
            return None
        
        # 2. 获取数据目录
        data_dir = _get_data_directory(conf_path)
        if not data_dir:
            logger.warning(f"Data directory not found in config: {conf_path}")
            return None
        
        # 3. 定位版本文件
        version_file = _find_version_file(data_dir)
        if not version_file:
            logger.error(f"Version file not found in data directory: {data_dir}")
            return None
        
        # 4. 读取并解析版本信�?        return _read_and_parse_version(version_file)
    
    except cloudVersionError as e:
        logger.exception("Version detection failed")
        return None
    except Exception as e:
        logger.exception("Unexpected error in version detection")
        return None

def _resolve_config_path() -> Optional[str]:
    """根据环境变量和默认值确定配置文件路�?""
    # 环境变量优先级最�?    if env_path := os.getenv(cloud_AGENT_CONF_ENV):
        if os.path.isfile(env_path):
            return env_path
        logger.warning(f"Configuration file from env not found: {env_path}")
    
    # 检查默认路�?    for path in [PATHS["DEFAULT_CONF"], PATHS["ALTERNATIVE_CONF"]]:
        if os.path.isfile(path):
            return path
    
    return None

def _get_data_directory(config_path: str) -> Optional[str]:
    """从配置文件中解析数据目录路径"""
    config = configparser.ConfigParser()
    
    try:
        with open(config_path, "r") as config_file:
            config.read_string("[DEFAULT]\n" + config_file.read())
        
        # 支持直接路径和相对路径解�?        if AGENT_PREFIX_KEY in config["DEFAULT"]:
            raw_path = config["DEFAULT"][AGENT_PREFIX_KEY]
            return _resolve_relative_path(raw_path, config_path)
        
        logger.warning(f"'{AGENT_PREFIX_KEY}' not found in config: {config_path}")
        return None
    
    except configparser.Error as e:
        raise cloudVersionError(f"Config parsing error: {str(e)}", config_path)

def _resolve_relative_path(raw_path: str, base_path: str) -> str:
    """处理配置中的相对路径"""
    if os.path.isabs(raw_path):
        return raw_path
    
    # 相对于配置文件目录解�?    base_dir = os.path.dirname(base_path)
    resolved = os.path.join(base_dir, raw_path)
    
    # 尝试规范化路�?    for _ in range(2):  # 最多尝试两次标准化
        norm_path = os.path.normpath(resolved)
        if norm_path == resolved:
            break
        resolved = norm_path
    
    return resolved

def _find_version_file(data_dir: str) -> Optional[str]:
    """在数据目录中定位版本文件"""
    # 1. 检查环境变量指定的版本文件
    if env_file := os.getenv(cloud_VERSION_FILE_ENV):
        if os.path.isfile(env_file):
            return env_file
        logger.warning(f"Version file from env not found: {env_file}")
    
    # 2. 检查容器化环境的特殊路�?    if os.path.isfile(PATHS["DOCKER_VERSION_PATH"]):
        return PATHS["DOCKER_VERSION_PATH"]
    
    # 3. 在数据目录中查找可能的版本文件位�?    for rel_path in [PATHS["DEFAULT_VERSION_FILE"], PATHS["ALTERNATIVE_VERSION_FILE"]]:
        candidate = os.path.join(data_dir, rel_path)
        if os.path.isfile(candidate):
            return candidate
    
    logger.error(f"No version file found in: {data_dir}")
    return None

def _read_and_parse_version(version_path: str) -> Tuple[Version, dict]:
    """安全读取和解析版本文�?""
    try:
        with open(version_path, "r") as f:
            content = f.read().strip()
        
        version_obj, metadata = _parse_version_content(content)
        logger.info(f"Detected cloud version: {version_obj} from {version_path}")
        return version_obj, metadata
    
    except IOError as e:
        raise cloudVersionError(f"File access error: {str(e)}", version_path)
    except ValueError as e:
        raise cloudVersionError(f"Version parsing error: {str(e)}", version_path)
    except Exception as e:
        raise cloudVersionError(f"Unexpected error: {str(e)}", version_path)

# ===============
# API 兼容�?# ===============
if __name__ == "__main__":
    """命令行直接调用时的行�?""
    try:
        version = get_cloud_version_agent()
        if version:
            print(f"cloud Agent Version: {version}")
            exit(0)
        else:
            print("Version not detected")
            exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(2)
