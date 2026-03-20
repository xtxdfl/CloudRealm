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

import cloud_simplejson as json
import logging
import os
import tempfile
import time
import filelock  # 需要安装：pip install filelock

logger = logging.getLogger()
DEFAULT_RUN_DIR = "/var/run/cloud-agent"
TEMP_FILE_PREFIX = "cloud_agent_config_"

class ActualConfigHandler:
    """安全可靠的配置处理器，用于管理组件级配置文件"""
    
    # 常量配置
    CONFIG_NAME = "config.json"
    FILE_LOCK_TIMEOUT = 30  # 文件锁超时时间（秒）
    
    def __init__(self, config, config_tags):
        """
        初始化配置处理器
        :param config: 应用程序配置对象
        :param config_tags: 配置标签字典（组�?>标签�?        """
        self.config = config
        self.config_tags = config_tags
        self._run_dir = self._determine_run_dir()
        self._lock_dir = os.path.join(self._run_dir, ".locks")
        
        # 创建锁目�?        if not os.path.exists(self._lock_dir):
            os.makedirs(self._lock_dir, exist_ok=True)
            logger.debug("Created lock directory: %s", self._lock_dir)

    def _determine_run_dir(self):
        """确定并创建运行目�?""
        run_dir = self.config.get("agent", "prefix") if self.config.has_option("agent", "prefix") else DEFAULT_RUN_DIR
        
        # 如果目录不存在，尝试创建
        if not os.path.exists(run_dir):
            try:
                logger.info("Creating missing run directory: %s", run_dir)
                os.makedirs(run_dir, 0o755, exist_ok=True)
            except Exception as e:
                logger.error("Failed to create run directory %s: %s. Using /tmp", run_dir, str(e))
                run_dir = "/tmp"
                os.makedirs(run_dir, 0o755, exist_ok=True)
                
        return os.path.abspath(run_dir)

    def _atomic_write(self, file_path, data):
        """以原子方式安全写入文�?""
        file_name = os.path.basename(file_path)
        lock_path = os.path.join(self._lock_dir, f"{file_name}.lock")
        temp_file = None
        
        try:
            # 创建文件�?            with filelock.FileLock(lock_path, timeout=self.FILE_LOCK_TIMEOUT):
                # 创建临时文件
                with tempfile.NamedTemporaryFile(
                    prefix=TEMP_FILE_PREFIX,
                    dir=self._run_dir,
                    suffix=".tmp",
                    mode="w",
                    delete=False
                ) as tmp_file:
                    temp_file = tmp_file.name
                    json.dump(data, tmp_file, indent=2)
                
                # 原子替换文件
                os.replace(temp_file, file_path)
                logger.debug("Safely wrote file %s", file_path)
        except filelock.Timeout:
            logger.error("Failed to acquire lock for %s", file_path)
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            raise
        except Exception as e:
            logger.error("Error writing file %s: %s", file_path, str(e))
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            raise

    def write_actual(self, tags):
        """写入主要配置文件"""
        self._atomic_write(self._get_file_path(self.CONFIG_NAME), tags)
        
    def write_actual_component(self, component, tags):
        """写入组件配置"""
        if self.config_tags.get(component) != tags:
            logger.info("Updating component config: %s", component)
            self.config_tags[component] = tags
            filename = f"{component}_{self.CONFIG_NAME}"
            self._atomic_write(self._get_file_path(filename), tags)

    def write_client_components(self, service_name, tags, components):
        """
        为指定服务写入客户端组件配置
        :param service_name: 服务名称
        :param tags: 标签数据
        :param components: 要更新的组件列表
        """
        from LiveStatus import LiveStatus  # 延迟导入避免循环依赖
        
        # 优化查找逻辑
        service_components = []
        for comp in LiveStatus.CLIENT_COMPONENTS:
            if comp["serviceName"] == service_name:
                component_name = comp["componentName"]
                if (components == ["*"] or component_name in components):
                    service_components.append(component_name)
        
        # 批量更新组件
        logger.info("Updating %d components for service %s", len(service_components), service_name)
        for comp_name in service_components:
            self.write_actual_component(comp_name, tags)

    def _get_file_path(self, filename):
        """获取完整的文件路�?""
        return os.path.join(self._run_dir, filename)

    def _safe_load_json(self, path):
        """安全加载JSON文件，带错误处理"""
        try:
            if not os.path.exists(path):
                logger.debug("File does not exist: %s", path)
                return None
                
            # 检查文件是否被篡改或损�?            if os.path.getsize(path) == 0:
                logger.warning("Skipping empty file: %s", path)
                return None
                
            with open(path, "r") as file:
                # 添加时间戳监�?                start_time = time.time()
                data = json.load(file)
                elapsed = (time.time() - start_time) * 1000
                
                if elapsed > 100:
                    logger.warning("Slow JSON parse of %s: %.2f ms", path, elapsed)
                
                return data
        except json.JSONDecodeError as e:
            logger.error("JSON parse error in file %s: %s", path, str(e))
        except Exception as e:
            logger.error("Error reading file %s: %s", path, str(e))
        
        return None

    def read_actual(self):
        """读取主要配置文件"""
        return self._safe_load_json(self._get_file_path(self.CONFIG_NAME))

    def read_actual_component(self, component_name):
        """读取组件配置，带缓存机制"""
        # 检查内存缓�?        if component_name in self.config_tags and self.config_tags[component_name]:
            return self.config_tags[component_name]
        
        # 检查并缓存文件内容
        filename = f"{component_name}_{self.CONFIG_NAME}"
        file_path = self._get_file_path(filename)
        data = self._safe_load_json(file_path)
        
        if data:
            self.config_tags[component_name] = data
            logger.debug("Cached config for %s from file", component_name)
        
        return data

    def update_component_tag(self, component_name, tag, value):
        """更新组件的指定标�?""
        # 获取当前配置
        current_config = self.read_actual_component(component_name)
        
        if not current_config:
            current_config = {}
        
        # 检查标签变�?        if tag in current_config and current_config[tag] == value:
            logger.debug("Tag %s unchanged for %s", tag, component_name)
            return
            
        # 更新标签�?        current_config[tag] = value
        logger.info("Updating tag %s for component %s", tag, component_name)
        
        # 写回文件
        filename = f"{component_name}_{self.CONFIG_NAME}"
        self._atomic_write(self._get_file_path(filename), current_config)
