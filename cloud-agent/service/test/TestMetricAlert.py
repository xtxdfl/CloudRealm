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

from unittest import TestCase
from alerts.metric_alert import MetricAlert
from mock.mock import Mock, MagicMock, patch
from cloudConfig import cloudConfig


class TestMetricAlert(TestCase):
    """Unit tests for MetricAlert class"""

    def setUp(self):
        """Initial test setup"""
        # Create cloudConfig instance for testing
        self.config = cloudConfig()

    @patch("urllib.request.urlopen")
    def test_collect_ok_state(self, mock_urlopen):
        """
        Test collecting metrics in OK state
        - Validates JMX collection and reporting
        - Checks alert data is correctly populated
        - Verifies result text formatting
        """
        # Define alert metadata
        alert_meta = {
            "name": "alert1",
            "label": "label1",
            "serviceName": "service1",
            "componentName": "component1",
            "uuid": "123",
            "enabled": "true",
        }
        
        # Define alert source configuration
        alert_source_meta = {
            "jmx": {"property_list": ["x/y"]},
            "uri": {
                "http": "192.168.0.10:8080",
                "https_property": "{{hdfs-site/dfs.http.policy}}",
                "https_property_value": "HTTPS_ONLY",
            },
            "reporting": {
                "ok": {"text": "OK: {0}"},
                "warning": {"text": "Warn: {0}", "value": 2},
                "critical": {"text": "Crit: {0}", "value": 5},
            },
        }
        
        # Test parameters
        cluster = "c1"
        host = "host1"
        expected_text = "OK: 1"  # Expected outcome text
        
        # Collector validation function
        def collector_side_effect(clus, data):
            """Verify collected alert data matches expectations"""
            # Assert various fields in the collected data
            self.assertEqual(data["name"], alert_meta["name"])
            self.assertEqual(data["label"], alert_meta["label"])
            self.assertEqual(data["text"], expected_text)
            self.assertEqual(data["service"], alert_meta["serviceName"])
            self.assertEqual(data["component"], alert_meta["componentName"])
            self.assertEqual(data["uuid"], alert_meta["uuid"])
            self.assertEqual(data["enabled"], alert_meta["enabled"])
            self.assertEqual(data["cluster"], cluster)
            self.assertEqual(clus, cluster)

        # Setup mock HTTP response
        response = Mock()
        mock_urlopen.return_value = response
        # Simulate JMX response with value 1 (OK state)
        response.read.return_value = b'{"beans": [{"y": 1}]}'
        
        # Mock collector and its put method
        mock_collector = MagicMock()
        mock_collector.put.side_effect = collector_side_effect
        
        # Create alert instance and set helpers
        alert = MetricAlert(alert_meta, alert_source_meta, self.config)
        alert.set_helpers(
            mock_collector, 
            {"foo-site/bar": 12, "foo-site/baz": "asd"}  # Mocked configurations
        )
        alert.set_cluster(cluster, host)
        
        # Execute collection
        alert.collect()
        
        # Verify interactions
        self.assertTrue(mock_urlopen.called)
        self.assertTrue(mock_collector.put.called)

    @patch("urllib.request.urlopen")
    def test_collect_warning_state(self, mock_urlopen):
        """
        Test collecting metrics in WARNING state
        - Validates state transition logic
        - Checks boundary value behavior
        """
        # Test metadata similar to OK state
        alert_meta = {
            "name": "alert1",
            "label": "label1",
            "serviceName": "service1",
            "componentName": "component1",
            "uuid": "123",
            "enabled": "true",
        }
        
        # Alert source configuration with values
        alert_source_meta = {
            "jmx": {"property_list": ["x/y"]},
            "uri": {
                "http": "192.168.0.10:8080",
                "https_property": "{{hdfs-site/dfs.http.policy}}",
                "https_property_value": "HTTPS_ONLY",
            },
            "reporting": {
                "ok": {"text": "OK: {0}"},
                "warning": {"text": "Warn: {0}", "value": 2},
                "critical": {"text": "Crit: {0}", "value": 5},
            },
        }
        
        # Test parameters (WARNING state)
        cluster = "c1"
        host = "host1"
        expected_text = "Warn: 4"  # WARNING threshold text
        
        # Collector validation function
        def collector_side_effect(clus, data):
            """Verify warning state data"""
            self.assertEqual(data["text"], expected_text)
            self.assertEqual(data["state"], "WARNING")

        # Setup mock response (value 4 = WARNING)
        response = Mock()
        mock_urlopen.return_value = response
        response.read.return_value = b'{"beans": [{"y": 4}]}'
        
        # Configure mock collector
        mock_collector = MagicMock()
        mock_collector.put.side_effect = collector_side_effect
        
        # Create and configure alert
        alert = MetricAlert(alert_meta, alert_source_meta, self.config)
        alert.set_helpers(
            mock_collector, 
            {"foo-site/bar": 12, "foo-site/baz": "asd"}
        )
        alert.set_cluster(cluster, host)
        
        # Execute collection
        alert.collect()
        
        # Verify interactions
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertEqual(mock_collector.put.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_collect_critical_state_with_cluster_id(self, mock_urlopen):
        """
        Test collecting metrics in CRITICAL state
        - Validates additional metadata (clusterId)
        - Tests higher threshold behavior
        """
        # Test metadata with additional clusterId
        alert_meta = {
            "definitionId": 1,  # Added definitionId
            "name": "alert1",
            "label": "label1",
            "serviceName": "service1",
            "componentName": "component1",
            "uuid": "123",
            "enabled": "true",
        }
        
        # Alert source configuration
        alert_source_meta = {
            "jmx": {"property_list": ["x/y"]},
            "uri": {
                "http": "192.168.0.10:8080",
                "https_property": "{{hdfs-site/dfs.http.policy}}",
                "https_property_value": "HTTPS_ONLY",
            },
            "reporting": {
                "ok": {"text": "OK: {0}"},
                "warning": {"text": "Warn: {0}", "value": 2},
                "critical": {"text": "Crit: {0}", "value": 5},
            },
        }
        
        # Test parameters with cluster ID
        cluster = "c1"
        cluster_id = "0"
        host = "host1"
        expected_text = "Crit: 12"  # CRITICAL state text
        
        # Collector validation function
        def collector_side_effect(clus, data):
            """Verify critical state and clusterId inclusion"""
            self.assertEqual(data["name"], alert_meta["name"])
            self.assertEqual(data["clusterId"], cluster_id)
            self.assertEqual(data["state"], "CRITICAL")
            self.assertEqual(clus, cluster)

        # Setup mock response (value 12 = CRITICAL)
        response = Mock()
        mock_urlopen.return_value = response
        response.read.return_value = b'{"beans": [{"y": 12}]}'
        
        # Configure mock collector
        mock_collector = MagicMock()
        mock_collector.put.side_effect = collector_side_effect
        
        # Create and configure alert
        alert = MetricAlert(alert_meta, alert_source_meta, self.config)
        alert.set_helpers(mock_collector, MagicMock(), MagicMock())
        alert.set_cluster(cluster, cluster_id, host)
        
        # Execute collection
        alert.collect()
        
        # Verify interactions
        self.assertTrue(mock_urlopen.called)
        self.assertTrue(mock_collector.put.called)

if __name__ == "__main__":
    # Run the tests when executed directly
    unittest.main()
