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

import logging
import time
import traceback
import json
import os
import hashlib
import threading
from datetime import datetime
from typing import Dict, Optional, Any

# 高级日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] [%(module)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LiveStatus")
logger.setLevel(logging.INFO)

class EnhancedConfigHandler:
    """增强型配置处理系统"""
    CONFIG_CACHE_PREFIX = "status_config_"
    CONFIG_TTL = 3600  # 1小时缓存时间
    CONFIG_SIGNATURE_MAP = {}
    
    def __init__(self, config: Dict, config_tags: Dict):
        self.config = config or {}
        self.config_tags = config_tags or {}
        self.cache_dir = "/var/cache/cloud/status_config"
        self.last_config_error = None
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_config_signature(self) -> str:
        """生成配置唯一标识"""
        config_data = json.dumps(self.config, sort_keys=True).encode('utf-8')
        return hashlib.sha256(config_data).hexdigest()
    
    def _cache_file_path(self, component_name: str) -> str:
        """获取缓存文件路径"""
        safe_name = component_name.replace('/', '_').replace(':', '_')
        return os.path.join(self.cache_dir, f"{self.CONFIG_CACHE_PREFIX}{safe_name}.json")
    
    def _should_use_cached_config(self, component_name: str, current_signature: str) -> bool:
        """检查是否可以使用缓存配置"""
        cache_path = self._cache_file_path(component_name)
        
        # 如果文件不存在需要创建
        if not os.path.exists(cache_path):
            return False
            
        # 检查缓存签名
        cached_signature = self.CONFIG_SIGNATURE_MAP.get(component_name)
        if cached_signature and cached_signature == current_signature:
            # 检查文件修改时间
            file_age = time.time() - os.path.getmtime(cache_path)
            return file_age < self.CONFIG_TTL
        
        return False
    
    def _save_config_to_cache(self, component_name: str, config_data: Dict, signature: str):
        """保存配置到缓存"""
        cache_path = self._cache_file_path(component_name)
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    "timestamp": datetime.utcnow().isoformat(),
                    "component": component_name,
                    "signature": signature,
                    "data": config_data
                }, f, indent=2)
                
            self.CONFIG_SIGNATURE_MAP[component_name] = signature
            return True
        except Exception as e:
            logger.error(f"配置缓存失败 ({component_name}): {str(e)}")
            return False
    
    def _load_cached_config(self, component_name: str) -> Optional[Dict]:
        """从缓存加载配置"""
        cache_path = self._cache_file_path(component_name)
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            return data.get('data')
        except:
            return None
    
    def read_actual_component_config(self, component_name: str) -> Optional[Dict]:
        """获取组件的实际配置"""
        current_signature = self._get_config_signature()
        
        # 尝试使用缓存配置
        if self._should_use_cached_config(component_name, current_signature):
            logger.debug(f"使用缓存配置: {component_name}")
            return self._load_cached_config(component_name)
            
        logger.info(f"加载活动配置: {component_name}")
        config_data = None
        
        try:
            # 模拟配置加载 - 在实际应用中连接配置系统
            config_data = {
                "tags": self.config_tags,
                "settings": self.config.get(component_name, {}),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # 成功获取后保存到缓存
            self._save_config_to_cache(component_name, config_data, current_signature)
            return config_data
            
        except Exception as e:
            self.last_config_error = str(e)
            logger.error(f"配置加载失败: {str(e)}")
            
            # 尝试使用最后一次成功的缓存
            cached_data = self._load_cached_config(component_name)
            if cached_data:
                logger.warning(f"使用最后一次成功的缓存配置: {component_name}")
                return cached_data
                
            return self._create_fallback_config(component_name)
    
    def _create_fallback_config(self, component_name: str) -> Dict:
        """创建回退配置"""
        return {
            "component": component_name,
            "status": "fallback_config_used",
            "message": f"无法加载配置: {self.last_config_error or '未知错误'}",
            "timestamp": datetime.utcnow().isoformat()
        }

class ComponentStatus:
    """组件状态追踪器"""
    STATUS_CODES = {
        "HEALTHY": 0,
        "DEGRADED": 1,
        "STOPPED": 2,
        "FAILED": 3,
        "RECOVERING": 4,
        "UNKNOWN": 5
    }
    
    def __init__(self):
        self.status_history = []
        self.current_status = "UNKNOWN"
        self.last_change = time.time()
        
    def update_status(self, new_status: str):
        """更新组件状态并记录历史"""
        if new_status not in self.STATUS_CODES:
            logger.warning(f"尝试设置无效状态: {new_status}")
            return
            
        if new_status != self.current_status:
            transition = {
                "from": self.current_status,
                "to": new_status,
                "timestamp": time.time()
            }
            self.status_history.append(transition)
            self.current_status = new_status
            self.last_change = time.time()
            
            # 限制历史记录大小
            if len(self.status_history) > 100:
                self.status_history.pop(0)

class LiveStatusReporter:
    """实时状态报告系统"""
    
    def __init__(
        self,
        cluster: str,
        service: str,
        config_handler: EnhancedConfigHandler,
        status_monitor: Optional[ComponentStatus] = None
    ):
        self.cluster = cluster
        self.service = service
        self.config_handler = config_handler
        self.status_monitor = status_monitor or ComponentStatus()
        self._uptime_timestamp = time.time()
        self.report_lock = threading.Lock()
        
    def build_component_status(self, component_name: str, status_code: int) -> Dict[str, Any]:
        """构建组件状态报告"""
        status_name = self._status_code_to_name(status_code)
        self.status_monitor.update_status(status_name)
        
        # 获取组件配置
        config_data = self.config_handler.read_actual_component_config(component_name)
        
        # 创建状态报告
        with self.report_lock:
            report = {
                "componentName": component_name,
                "serviceName": self.service,
                "clusterName": self.cluster,
                "status": {
                    "code": status_code,
                    "name": status_name,
                    "lastChange": datetime.fromtimestamp(self.status_monitor.last_change).isoformat(),
                    "uptime": self._calculate_uptime()
                },
                "configuration": config_data,
                "metadata": {
                    "reportTimestamp": datetime.utcnow().isoformat(),
                    "monitorUptime": self._calculate_uptime(),
                    "statusTransitions": len(self.status_monitor.status_history)
                }
            }
            
            # 生成分析指标
            report["analytics"] = self._generate_status_analytics(status_name)
            logger.info(f"生成的组件状态报告: {component_name} ({status_name})")
            
        # 如果需要，可以添加历史记录
        if len(self.status_monitor.status_history) > 0:
            report["recentTransitions"] = self.status_monitor.status_history[-5:]
            
        return report
    
    def _status_code_to_name(self, code: int) -> str:
        """将状态代码转换为名称"""
        for name, value in self.status_monitor.STATUS_CODES.items():
            if value == code:
                return name
        return "UNKNOWN"
    
    def _calculate_uptime(self) -> str:
        """计算运行时间"""
        seconds = time.time() - self._uptime_timestamp
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
    
    def _generate_status_analytics(self, current_status: str) -> Dict[str, float]:
        """生成状态分析统计数据"""
        if not self.status_monitor.status_history:
            return {
                "stability": 100.0,
                "health_score": 100.0,
                "downtime_ratio": 0.0
            }
            
        # 计算健康/不健康状态的比例
        healthy_count = sum(1 for s in self.status_monitor.status_history 
                         if s['to'] in ["HEALTHY", "RECOVERING"])
        unhealthy_count = len(self.status_monitor.status_history) - healthy_count
        health_ratio = healthy_count / (len(self.status_monitor.status_history) or 1) * 100
        
        # 计算稳定性指标
        downtime_events = sum(1 for s in self.status_monitor.status_history 
                            if s['to'] in ["STOPPED", "FAILED"])
        downtime_ratio = downtime_events / max(1, len(self.status_monitor.status_history))
        
        # 计算健康状况
        if current_status in ["HEALTHY", "RECOVERING"]:
            health_score = (100 - downtime_ratio*50)
        else:
            health_score = (20 - downtime_ratio*10)
            
        return {
            "stability": health_ratio,
            "health_score": max(10, min(100, health_score)),
            "downtime_ratio": downtime_ratio,
            "mean_time_to_recover": self._calculate_mean_recovery_time()
        }
    
    def _calculate_mean_recovery_time(self) -> float:
        """计算平均恢复时间（秒）"""
        recovery_times = []
        start_event = None
        
        for event in self.status_monitor.status_history:
            if event['to'] in ['STOPPED', 'FAILED'] and event['from'] not in ['STOPPED', 'FAILED']:
                start_event = event
            elif event['to'] in ['HEALTHY', 'RECOVERING'] and start_event:
                recovery_time = event['timestamp'] - start_event['timestamp']
                recovery_times.append(recovery_time)
                start_event = None
                
        if not recovery_times:
            return 0.0
            
        return sum(recovery_times) / len(recovery_times)
