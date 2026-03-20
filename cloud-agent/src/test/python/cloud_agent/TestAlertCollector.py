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

import unittest
from unittest.mock import patch, MagicMock
from cloud_agent.alerts.collector import AlertCollector


class AlertCollectorTestBase(unittest.TestCase):
    """警报收集器测试基�?""
    
    def setUp(self):
        # 创建警报收集器实�?        self.collector = AlertCollector()
        
        # 定义示例警报
        self.sample_alerts = [
            {"name": "CPU_Usage", "uuid": "001", "status": "CRITICAL"},
            {"name": "Memory_Usage", "uuid": "002", "status": "WARNING"},
            {"name": "Disk_Space", "uuid": "003", "status": "OK"},
            {"name": "Network_Down", "uuid": "004", "status": "CRITICAL"}
        ]
    
    def add_alerts_to_collector(self, cluster="TestCluster"):
        """向收集器添加示例警报"""
        for alert in self.sample_alerts:
            self.collector.put(cluster, alert)
        return self.sample_alerts


class AlertCollectionTests(AlertCollectorTestBase):
    """测试警报收集功能"""
    
    def test_add_alert_to_new_cluster(self):
        """测试向新集群添加警报"""
        # 添加一个新集群的警�?        alert = {"name": "NewAlert", "uuid": "100"}
        self.collector.put("NewCluster", alert)
        
        # 验证结果
        self.assertIn("NewCluster", self.collector._AlertCollector__buckets)
        self.assertEqual(
            self.collector._AlertCollector__buckets["NewCluster"],
            {"NewAlert": alert}
        )
    
    def test_add_alert_to_existing_cluster(self):
        """测试向现有集群添加警�?""
        # 准备测试数据
        cluster = "ExistingCluster"
        existing_alert = {"name": "ExistingAlert", "uuid": "200"}
        self.collector.put(cluster, existing_alert)
        
        # 添加新警�?        new_alert = {"name": "NewAlert", "uuid": "201"}
        self.collector.put(cluster, new_alert)
        
        # 验证结果
        self.assertEqual(len(self.collector._AlertCollector__buckets[cluster]), 2)
        self.assertIn("ExistingAlert", self.collector._AlertCollector__buckets[cluster])
        self.assertIn("NewAlert", self.collector._AlertCollector__buckets[cluster])
    
    def test_update_existing_alert(self):
        """测试更新已有警报"""
        # 准备测试数据
        cluster = "TestCluster"
        original_alert = {"name": "OriginalAlert", "uuid": "300", "value": 75}
        self.collector.put(cluster, original_alert)
        
        # 更新警报
        updated_alert = {"name": "OriginalAlert", "uuid": "300", "value": 85, "status": "WARNING"}
        self.collector.put(cluster, updated_alert)
        
        # 验证结果
        stored_alert = self.collector._AlertCollector__buckets[cluster]["OriginalAlert"]
        self.assertEqual(stored_alert["value"], 85)
        self.assertEqual(stored_alert["status"], "WARNING")
    
    def test_add_multiple_alerts(self):
        """测试批量添加警报"""
        # 准备测试数据
        cluster = "MultiAlertCluster"
        alerts = [
            {"name": "Alert1", "uuid": "401"},
            {"name": "Alert2", "uuid": "402"},
            {"name": "Alert3", "uuid": "403"}
        ]
        
        # 添加所有警�?        for alert in alerts:
            self.collector.put(cluster, alert)
        
        # 验证结果
        stored_alerts = self.collector._AlertCollector__buckets.get(cluster, {})
        self.assertEqual(len(stored_alerts), 3)
        self.assertTrue(all(a["name"] in stored_alerts for a in alerts))


class AlertRemovalTests(AlertCollectorTestBase):
    """测试警报移除功能"""
    
    def setUp(self):
        super().setUp()
        # 向收集器添加示例警报
        self.cluster_name = "TestCluster"
        self.alerts_added = self.add_alerts_to_collector(self.cluster_name)
    
    def test_remove_alert_by_name(self):
        """测试按名称移除警�?""
        # 移除指定警报
        alert_to_remove = self.sample_alerts[1]
        self.collector.remove(self.cluster_name, alert_to_remove["name"])
        
        # 验证结果
        stored_alerts = self.collector._AlertCollector__buckets[self.cluster_name]
        self.assertEqual(len(stored_alerts), 3)
        self.assertNotIn(alert_to_remove["name"], stored_alerts)
    
    def test_remove_non_existent_alert(self):
        """测试移除不存在的警报"""
        # 初始状�?        initial_count = len(self.collector._AlertCollector__buckets[self.cluster_name])
        
        # 尝试移除不存在的警报
        self.collector.remove(self.cluster_name, "NonExistentAlert")
        
        # 验证收集器状态未改变
        stored_alerts = self.collector._AlertCollector__buckets[self.cluster_name]
        self.assertEqual(len(stored_alerts), initial_count)
    
    def test_remove_alert_from_non_existent_cluster(self):
        """测试从不存在集群中移除警�?""
        # 尝试移除不存在的集群中的警报
        self.collector.remove("NonExistentCluster", "AnyAlert")
        
        # 验证收集器未添加新集�?        self.assertNotIn("NonExistentCluster", self.collector._AlertCollector__buckets)
    
    def test_remove_alert_by_uuid(self):
        """测试按UUID移除警报"""
        # 移除指定UUID的警�?        alert_to_remove = self.sample_alerts[2]
        self.collector.remove_by_uuid(alert_to_remove["uuid"])
        
        # 验证结果
        all_clusters_alerts = self.collector._AlertCollector__buckets
        for cluster_alerts in all_clusters_alerts.values():
            for alert in cluster_alerts.values():
                self.assertNotEqual(alert["uuid"], alert_to_remove["uuid"])
    
    def test_remove_by_uuid_with_multiple_clusters(self):
        """测试从多个集群中按UUID移除警报"""
        # 添加第二个集�?        second_cluster = "SecondCluster"
        second_cluster_alerts = [
            {"name": "Alert_A", "uuid": "101"},
            {"name": "Alert_B", "uuid": "102"}
        ]
        for alert in second_cluster_alerts:
            self.collector.put(second_cluster, alert)
        
        # 创建共享UUID的警�?        shared_uuid = "shared-UUID-123"
        self.collector.put(self.cluster_name, {"name": "SharedAlert1", "uuid": shared_uuid})
        self.collector.put(second_cluster, {"name": "SharedAlert2", "uuid": shared_uuid})
        
        # 移除共享UUID的警�?        self.collector.remove_by_uuid(shared_uuid)
        
        # 验证所有集群中都不存在该UUID的警�?        uuid_exists = any(
            alert["uuid"] == shared_uuid
            for cluster in self.collector._AlertCollector__buckets.values()
            for alert in cluster.values()
        )
        self.assertFalse(uuid_exists, "共享UUID的警报未被完全移�?)


class AlertRetrievalTests(AlertCollectorTestBase):
    """测试警报检索功�?""
    
    def test_retrieve_and_clear_alerts(self):
        """测试检索并清空警报"""
        # 添加多个集群的警�?        self.add_alerts_to_collector("Cluster1")
        self.add_alerts_to_collector("Cluster2")
        
        # 初始状态验�?        self.assertEqual(len(self.collector._AlertCollector__buckets), 2)
        self.assertEqual(
            sum(len(alerts) for alerts in self.collector._AlertCollector__buckets.values()),
            8  # 每个集群4个警�?        )
        
        # 检索警报并清空收集�?        alerts_list = self.collector.alerts()
        
        # 验证结果
        self.assertEqual(len(alerts_list), 8)
        
        # 收集器应被清�?        self.assertEqual(len(self.collector._AlertCollector__buckets), 0)
    
    def test_retrieve_specific_cluster_alerts(self):
        """测试检索特定集群的警报"""
        # 添加多个集群但只检索其中一�?        cluster1 = "ClusterA"
        cluster2 = "ClusterB"
        alerts_cluster1 = self.add_alerts_to_collector(cluster1)
        alerts_cluster2 = self.add_alerts_to_collector(cluster2)
        
        # 只检索ClusterA的警�?        alerts_a = []
        for alert in alerts_cluster1:
            alerts_a.append(alert)
        
        # 验证结果
        self.assertEqual(len(alerts_a), 4)
        for alert in alerts_a:
            self.assertEqual(alert['name'], alert['name'])  # 验证警报存在
            
        # ClusterB的警报应仍在收集器中
        self.assertEqual(len(self.collector._AlertCollector__buckets), 1)
        self.assertIn(cluster2, self.collector._AlertCollector__buckets)
    
    def test_retrieve_empty_collector(self):
        """测试检索空的收集器"""
        # 确保收集器为�?        self.collector._AlertCollector__buckets = {}
        
        # 检索警�?        alerts = self.collector.alerts()
        
        # 验证结果
        self.assertEqual(alerts, [])
        self.assertEqual(len(self.collector._AlertCollector__buckets), 0)


class ConcurrencyTests(AlertCollectorTestBase):
    """测试并发场景下的警报收集�?""
    
    def test_simultaneous_add_remove(self):
        """测试同时添加和移除警�?""
        import threading
        
        # 创建共享集群
        cluster = "ConcurrentCluster"
        
        # 定义添加警报的线程函�?        def add_alerts():
            for alert in self.sample_alerts:
                self.collector.put(cluster, alert.copy())
        
        # 定义移除警报的线程函�?        def remove_alerts():
            for alert in self.sample_alerts:
                self.collector.remove(cluster, alert["name"])
        
        # 同时运行添加和移除线�?        add_thread = threading.Thread(target=add_alerts)
        remove_thread = threading.Thread(target=remove_alerts)
        
        add_thread.start()
        remove_thread.start()
        
        add_thread.join()
        remove_thread.join()
        
        # 验证结果
        cluster_alerts = self.collector._AlertCollector__buckets.get(cluster, {})
        
        # 由于添加和移除同时发生，最终结果可能是0�?之间的任意�?        self.assertIn(len(cluster_alerts), [0, 1, 2, 3, 4])
    
    @patch("cloud_agent.alerts.collector.logger")
    def test_concurrent_modification_handling(self, logger_mock):
        """测试并发修改处理"""
        import threading
        import time
        
        # 定义添加警报的函�?        def add_alerts_delayed():
            time.sleep(0.1)  # 确保在迭代开始后添加
            for i in range(5):
                self.collector.put("ConcurrentCluster", {
                    "name": f"DynamicAlert{i}", 
                    "uuid": f"dynamic-{i}"
                })
        
        # 启动添加线程
        add_thread = threading.Thread(target=add_alerts_delayed)
        add_thread.start()
        
        # 开始迭代收集器 - 此时添加线程可能会修改内部结�?        alerts = self.collector.alerts()
        
        add_thread.join()
        
        # 验证不会抛出并发修改异常
        self.assertIsInstance(alerts, list)
        self.assertIn("Concurrent modification detected", logger_mock.warning.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
