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

Enhanced Log Feeder Configuration Generator
"""

import os
import logging
from typing import Optional, Any
from resource_management.core.logger import StructuredLogger
from resource_management.core.resources import File, Directory
from resource_management.libraries.functions.security import apply_file_permissions

# 配置常量
LOGFEEDER_CONF_DIR = "/etc/logfeeder/conf"
DEFAULT_CONFIG_MODE = 0o644
DEFAULT_DIR_MODE = 0o755

# 初始化结构化日志记录器
logger = StructuredLogger(__name__)

def generate_logfeeder_config(
    service_type: str, 
    config_content: Any,
    config_dir: Optional[str] = LOGFEEDER_CONF_DIR,
    file_mode: Optional[int] = DEFAULT_CONFIG_MODE,
    dir_mode: Optional[int] = DEFAULT_DIR_MODE,
    validate_content: Optional[bool] = False,
    backup_existing: Optional[bool] = True
) -> None:
    """
    安全生成和部署 Log Feeder 配置文件
    
    此功能为指定的服务创建专门的 Log Feeder 配置：
    1. 确保配置目录存在且具有正确的权限
    2. 根据提供的参数生成配置文件
    3. 支持配置文件验证和备份
    
    :param service_type: 服务标识符 (如: hdfs, yarn, kafka)，用作文件名后缀
    :param config_content: 配置内容 (字符串、字典或模板对象)
    :param config_dir: 配置文件目录 (默认: /etc/logfeeder/conf)
    :param file_mode: 配置文件权限 (默认: 0o644 -> rw-r--r--)
    :param dir_mode: 目录权限 (默认: 0o755 -> rwxr-xr-x)
    :param validate_content: 是否在写入前验证配置内容 (默认: False)
    :param backup_existing: 是否备份已存在的配置文件 (默认: True)
    
    示例调用:
        generate_logfeeder_config("hdfs", json_config_template)
    """
    # 创建配置目录结构
    ensure_config_directory(config_dir, dir_mode)
    
    # 构建完整文件路径
    file_name = f"input.config-{service_type}.json"
    full_file_path = construct_file_path(config_dir, file_name)
    
    # 记录配置生成操作
    log_config_operation(service_type, full_file_path, config_content)
    
    # 准备配置内容
    processed_content = prepare_config_content(config_content)
    
    # 可选的内容验证
    if validate_content:
        validate_json_config(processed_content)
    
    # 备份现有配置
    if backup_existing and os.path.exists(full_file_path):
        create_config_backup(full_file_path)
    
    # 部署配置文件
    deploy_config_file(full_file_path, processed_content, file_mode)

def ensure_config_directory(
    config_dir: str, 
    mode: int = DEFAULT_DIR_MODE
) -> None:
    """
    确保配置目录存在且权限正确
    
    :param config_dir: 目标配置目录路径
    :param mode: 目录权限模式
    """
    try:
        # 创建目录并设置权限
        Directory(config_dir,
                  mode=mode,
                  cd_access="a",
                  create_parents=True,
                  owner="logfeeder",
                  group="hadoop",
                  action="create_on_missing")
        
        logger.info(f"验证配置目录 {config_dir} 准备就绪", 
                    permissions=oct(mode)[2:],
                    create_parents=True)
    except Exception as dir_exc:
        logger.error("配置目录创建失败", 
                     path=config_dir,
                     error=str(dir_exc))
        raise RuntimeError(f"无法准备Log Feeder配置目录: {str(dir_exc)}")

def construct_file_path(
    base_dir: str, 
    file_name: str
) -> str:
    """
    构建完整配置文件的规范路径
    
    :param base_dir: 基础目录路径
    :param file_name: 文件名
    :return: 拼接后的绝对路径
    """
    # 规范化路径，防止目录遍历攻击
    if file_name.startswith(".") or "/" in file_name:
        logger.warning("检测到可疑文件名", 
                       file_name=file_name,
                       base_dir=base_dir)
        file_name = sanitize_filename(file_name)
    
    full_path = os.path.join(base_dir, file_name)
    abs_path = os.path.abspath(full_path)
    
    # 路径安全检查
    if not abs_path.startswith(base_dir):
        error_msg = f"无效的文件路径: {abs_path} (超出基准目录)"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return abs_path

def sanitize_filename(
    unsafe_name: str
) -> str:
    """
    清理潜在不安全的文件名
    
    :param unsafe_name: 原始文件名
    :return: 安全文件名
    """
    # 删除路径组件
    clean_name = os.path.basename(unsafe_name)
    
    # 替换可疑字符
    clean_name = clean_name.replace("..", ".")
    clean_name = ''.join(c if c.isalnum() or c in '-_. ' else '_' 
                         for c in clean_name)
    return clean_name[:255]  # 限制文件名长度

def prepare_config_content(
    raw_content: Any
) -> str:
    """
    将各种配置内容类型转换为字符串
    
    :param raw_content: 原始配置内容 (字符串/字典/模板)
    :return: 字符串形式的配置内容
    """
    try:
        # 处理 JSON 字典
        if isinstance(raw_content, dict):
            import json
            return json.dumps(raw_content, indent=2)
        
        # 处理模板对象
        elif hasattr(raw_content, 'get_content'):
            return raw_content.get_content()
        
        # 直接返回字符串
        return str(raw_content)
    except Exception as conv_exc:
        logger.error("配置内容转换失败", 
                     content_type=type(raw_content).__name__,
                     error=str(conv_exc))
        raise ValueError("无效的配置内容格式") from conv_exc

def validate_json_config(
    json_content: str
) -> None:
    """
    验证 JSON 配置的语法正确性
    
    :param json_content: JSON字符串
    :raises ValueError: JSON无效时抛出
    """
    try:
        import json
        json.loads(json_content)
    except json.JSONDecodeError as json_err:
        logger.error("JSON配置验证失败", 
                     error=str(json_err),
                     context=json_content[:100] + "..." if len(json_content) > 100 else json_content)
        raise ValueError(f"无效的JSON配置: {str(json_err)}")

def create_config_backup(
    file_path: str
) -> None:
    """
    创建现有配置的备份
    
    :param file_path: 原始配置文件路径
    """
    import shutil
    import time
    
    backup_path = f"{file_path}.bak-{int(time.time())}"
    
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"配置文件已成功备份",
                    original=file_path,
                    backup=backup_path)
    except Exception as backup_exc:
        logger.warning("配置文件备份失败",
                       original=file_path,
                       error=str(backup_exc))

def deploy_config_file(
    full_path: str, 
    content: str, 
    mode: int
) -> File:
    """
    最终部署配置文件
    
    :param full_path: 完整文件路径
    :param content: 配置内容
    :param mode: 文件权限
    :return: File资源对象
    """
    try:
        # 创建配置文件
        config_file = File(full_path,
                          content=content,
                          mode=mode,
                          owner="logfeeder",
                          group="hadoop",
                          encoding="utf-8",
                          action="create")
        
        # 应用额外安全控制
        apply_file_permissions(full_path, mode=mode)
        
        logger.info(f"Log Feeder配置部署完成",
                    file_path=full_path,
                    size=f"{len(content)} 字节")
        
        return config_file
    except Exception as deploy_exc:
        logger.error("配置文件部署失败",
                     path=full_path,
                     error=str(deploy_exc))
        raise RuntimeError(f"配置文件 '{full_path}' 创建失败") from deploy_exc

def log_config_operation(
    service_type: str, 
    file_path: str, 
    content: Any
) -> None:
    """记录详细的配置生成操作"""
    context = {
        "service": service_type,
        "config_path": file_path,
        "content_type": type(content).__name__
    }
    
    # 添加内容摘要
    if isinstance(content, dict):
        context["structure"] = list(content.keys())[:3] + ["..."]
    elif hasattr(content, 'get_content'):
        sample = content.get_content()[:150] + "..." if content.get_content() else "<空模板>"
        context["content_sample"] = sample
    elif len(str(content)) > 300:
        context["content_sample"] = str(content)[:150] + "..." + str(content)[-150:]
    else:
        context["content_sample"] = str(content)
    
    logger.info(f"为服务 {service_type} 生成Log Feeder配置", **context)
    
# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 示例1: 基本配置生成
    hdfs_config = {
        "type": "hdfs_log",
        "paths": ["/var/log/hadoop/hdfs/*.log"],
        "fields": {"service": "hdfs", "component": "namenode"}
    }
    generate_logfeeder_config("hdfs", hdfs_config)
    
    # 示例2: 带验证和备份的复杂配置
    yarn_config = {
        "type": "yarn_log",
        "paths": [
            "/var/log/hadoop-yarn/yarn/yarn-*.log",
            "/var/log/hadoop-mapreduce/mapred/*.log"
        ],
        "multiline": {
            "pattern": "^\\d{4}-\\d{2}-\\d{2}",
            "negate": True,
            "match": "after"
        }
    }
    generate_logfeeder_config("yarn", yarn_config, 
                             validate_content=True, 
                             backup_existing=True)
    
    # 示例3: 从模板生成
    from resource_management.core.source import Template
    kafka_template = Template("""
    {
      "type": "kafka_log",
      "paths": ["/opt/kafka/logs/server.log", "/opt/kafka/logs/controller.log"],
      "fields": {
        "service": "kafka",
        "environment": "#{env_name}"
      }
    }
    """)
    generate_logfeeder_config("kafka", kafka_template)
