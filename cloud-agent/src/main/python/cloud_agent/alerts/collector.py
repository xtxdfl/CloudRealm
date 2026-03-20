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
import threading
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AlertStorage:
    """
    线程安全的告警存储结构
    采用两层嵌套结构: cluster -> name -> alert
    """
    def __init__(self):
        self._storage = defaultdict(dict)  # 类型: Dict[str, Dict[str, dict]]
        self._lock = threading.RLock()
        self._size = 0
        self._clusters = set()
    
    def __len__(self) -> int:
        """返回存储的告警总数"""
        with self._lock:
            return self._size
    
    def __contains__(self, key: Tuple[str, Optional[str]]) -> bool:
        """检查集群或特定告警是否存在"""
        cluster, alert_name = key
        if alert_name is None:
            with self._lock:
                return cluster in self._storage
        else:
            with self._lock:
                return cluster in self._storage and alert_name in self._storage[cluster]
    
    @property
    def cluster_count(self) -> int:
        """返回集群数量"""
        with self._lock:
            return len(self._storage)
    
    @property
    def clusters(self) -> List[str]:
        """返回所有集群列表"""
        with self._lock:
            return list(self._clusters)
    
    def put(self, cluster: str, alert: dict) -> bool:
        """
        添加或更新告警到存储
        返回是否为新告警添加
        """
        alert_name = alert.get("name")
        if not alert_name:
            logger.error(f"无效告警数据: 缺少'name'字段 - {alert}")
            return False
        
        with self._lock:
            # 检查是否为新告警
            is_new = cluster not in self._storage or alert_name not in self._storage[cluster]
            
            # 更新存储
            self._storage[cluster][alert_name] = alert
            self._clusters.add(cluster)
            
            if is_new:
                self._size += 1
                logger.debug(f"添加新告警: [集群: {cluster}] [{alert_name}]")
            else:
                logger.debug(f"更新已有告警: [集群: {cluster}] [{alert_name}]")
            
            return is_new
    
    def remove(self, cluster: str, alert_name: str) -> bool:
        """
        从指定集群中移除指定名称的告警
        返回是否实际移除了告警
        """
        with self._lock:
            if cluster in self._storage and alert_name in self._storage[cluster]:
                del self._storage[cluster][alert_name]
                self._size -= 1
                logger.info(f"移除告警: [集群: {cluster}] [{alert_name}]")
                
                # 如果集群中已无告警，移除集群
                if not self._storage[cluster]:
                    del self._storage[cluster]
                    self._clusters.discard(cluster)
                
                return True
            return False
    
    def remove_by_uuid(self, alert_uuid: str) -> int:
        """
        根据UUID移除告警
        返回实际移除的告警数量
        """
        removed_count = 0
        clusters_to_check = []
        
        # 首先收集需要检查的集群
        with self._lock:
            clusters_to_check = list(self._storage.keys())
        
        # 遍历所有集群中的告警
        for cluster in clusters_to_check:
            # 需要重新获取告警名称列表的副本，因为字典可能在迭代时改变
            with self._lock:
                alert_names = list(self._storage.get(cluster, {}).keys())
            
            for alert_name in alert_names:
                with self._lock:
                    alert = self._storage[cluster].get(alert_name)
                    
                if not alert:
                    continue
                
                uuid_value = alert.get("uuid")
                if uuid_value == alert_uuid:
                    success = self.remove(cluster, alert_name)
                    if success:
                        removed_count += 1
        
        return removed_count
    
    def get(self, cluster: str, alert_name: str) -> Optional[dict]:
        """获取指定集群和名称的告警"""
        with self._lock:
            if cluster in self._storage and alert_name in self._storage[cluster]:
                return self._storage[cluster][alert_name]
            return None
    
    def get_by_uuid(self, alert_uuid: str) -> List[dict]:
        """根据UUID查找所有匹配的告警"""
        results = []
        with self._lock:
            for cluster, alerts in self._storage.items():
                for alert in alerts.values():
                    if "uuid" not in alert:
                        logger.debug(f"告警缺少uuid字段: {alert.get('name')}")
                        continue
                    
                    if alert["uuid"] == alert_uuid:
                        results.append(alert)
        return results
    
    def clear_cluster(self, cluster: str) -> int:
        """清除指定集群的所有告警，返回被清除的告警数量"""
        removed_count = 0
        with self._lock:
            if cluster in self._storage:
                removed_count = len(self._storage[cluster])
                self._size -= removed_count
                del self._storage[cluster]
                self._clusters.discard(cluster)
                logger.info(f"清除集群 '{cluster}' 的所有告警: {removed_count} 条")
        return removed_count
    
    def clear_all(self) -> int:
        """清除所有告警，返回被清除的告警总数"""
        removed_count = 0
        with self._lock:
            removed_count = self._size
            self._storage.clear()
            self._clusters.clear()
            self._size = 0
            logger.info(f"清除所有告警: {removed_count} 条")
        return removed_count
    
    def pop_alerts(self) -> List[dict]:
        """
        获取并清除所有告警
        返回所有告警的列表
        """
        with self._lock:
            # 收集所有告警
            alerts = []
            for cluster, alert_dict in self._storage.items():
                alerts.extend(alert_dict.values())
            
            # 清空存储
            self._storage.clear()
            self._clusters.clear()
            self._size = 0
            
            logger.info(f"弹出 {len(alerts)} 条告警以供处理")
            return alerts
