#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
import concurrent.futures
import time
from collections import defaultdict
from cloud_stomp.adapter.websocket import ConnectionIsAlreadyClosed
from cloud_agent import Constants

logger = logging.getLogger(__name__)
ERROR_THRESHOLD = 5  # Number of consecutive errors before backoff
BACKOFF_FACTOR = 2   # Multiplier for backoff time

class AlertStatusReporter(threading.Thread):
    """
    Thread-safe alert status reporter that manages cluster alerts with optimized:
        - Change detection and processing
        - Reduced bandwidth usage
        - Error handling and recovery
        - Resource management
    
    Key features:
        1. Efficient change detection with field-based diffing
        2. Rate-limiting with repeat tolerance
        3. Stale cluster cleanup
        4. Connection failure resilience
        5. Detailed instrumentation
    """
    
    # Fields that trigger resend when changed
    RESEND_FIELDS = ["text", "state"]
    
    def __init__(self, initializer_module):
        threading.Thread.__init__(self, name="AlertStatusReporter")
        self.daemon = True
        self.initializer = initializer_module
        self.config = initializer_module.config
        self.stop_event = initializer_module.stop_event
        self.alert_interval = self.config.alert_reports_interval
        self.send_changes_only = self.config.send_alert_changes_only
        
        # Dependencies
        self.collector = initializer_module.alert_scheduler_handler.collector()
        self.connection = initializer_module.connection
        self.server_responses = initializer_module.server_responses_listener
        self.definitions_cache = initializer_module.alert_definitions_cache
        self.stale_monitor = initializer_module.stale_alerts_monitor

        # State tracking
        self.reported_alerts = defaultdict(dict)  # cluster_id -> {alert_name: {field: value}}
        self.alert_counters = defaultdict(lambda: defaultdict(int))  # cluster_id -> alert_name -> repeat_count
        self.connection_errors = 0
        self.last_success = time.time()
        
        logger.info("AlertStatusReporter initialized with interval=%ds", self.alert_interval)

    def run(self):
        """Main reporting loop with enhanced error handling and backoff"""
        if self.alert_interval <= 0:
            logger.warning("Alert reporting is disabled. Interval=%d", self.alert_interval)
            return

        consecutive_errors = 0
        current_interval = self.alert_interval
        
        while not self.stop_event.is_set():
            start_time = time.time()
            
            try:
                if self.initializer.is_registered:
                    self._clean_inactive_clusters()
                    alerts = self._collect_alerts()
                    
                    if alerts:
                        to_send = (
                            self._filter_changed_alerts(alerts)
                            if self.send_changes_only
                            else alerts
                        )
                        
                        if to_send:
                            self._send_alerts(to_send)
                        
                    # Metrics
                    duration = time.time() - start_time
                    logger.debug(
                        "Processed alerts: total=%d, sent=%d, time=%.2fs",
                        len(alerts), len(to_send), duration
                    )
                
                consecutive_errors = 0
                current_interval = self.alert_interval
                
            except ConnectionIsAlreadyClosed as e:
                logger.warning("Connection closed during send: %s", str(e))
            except Exception as e:
                consecutive_errors += 1
                logger.exception("Alert reporting error %d/%d: %s", 
                                consecutive_errors, ERROR_THRESHOLD, str(e))
                
                # Exponential backoff on repeated errors
                if consecutive_errors >= ERROR_THRESHOLD:
                    current_interval = min(
                        current_interval * BACKOFF_FACTOR,
                        self.alert_interval * 8
                    )
                    logger.warning("Entering backoff: interval=%ds", current_interval)
            
            # Adaptive sleep with termination check
            sleep_until = start_time + current_interval
            while time.time() < sleep_until and not self.stop_event.is_set():
                time.sleep(0.5)
        
        logger.info("Alert reporter stopped gracefully")

    def _collect_alerts(self):
        """Collect and preprocess alerts from collector"""
        alerts = self.collector.alerts()
        self.stale_monitor.save_executed_alerts(alerts)
        return alerts

    def _filter_changed_alerts(self, alerts):
        """Filter alerts based on change detection and repeat tolerance"""
        changed_alerts = []
        cluster_configs = {}
        
        for alert in alerts:
            cluster_id = alert["clusterId"]
            alert_name = alert["name"]
            
            # Get cluster configuration only once per cluster
            if cluster_id not in cluster_configs:
                cluster_configs[cluster_id] = self._get_repeat_tolerance(cluster_id)
            
            repeat_tolerance = cluster_configs[cluster_id]
            report_changed = self._should_report_alert(alert, repeat_tolerance)
            
            if report_changed:
                changed_alerts.append(alert)
        
        return changed_alerts

    def _get_repeat_tolerance(self, cluster_id):
        """Get repeat tolerance setting for a cluster with caching"""
        # Check if tolerance is defined in cache
        cluster_alerts = self.definitions_cache.get(cluster_id)
        if not cluster_alerts:
            return self.config.default_alert_tolerance
        
        alert_definitions = cluster_alerts.get("alertDefinitions", [])
        if not alert_definitions:
            return self.config.default_alert_tolerance
            
        # Return definition tolerance or fallback to cluster default
        return next((
            int(alert.get("repeat_tolerance", self.config.default_alert_tolerance))
            for alert in alert_definitions
            if alert.get("repeat_tolerance_enabled", True)
        ), self.config.default_alert_tolerance)

    def _should_report_alert(self, alert, repeat_tolerance):
        """Determine if an alert should be reported based on changes and counters"""
        cluster_id = alert["clusterId"]
        alert_name = alert["name"]
        alert_state = alert["state"]
        
        # Track current values for RESEND_FIELDS
        current_values = {}
        prev_values = self.reported_alerts.get(cluster_id, {}).get(alert_name, {})
        
        # Compare current and previous field values
        changed = False
        for field in self.RESEND_FIELDS:
            current_val = alert.get(field, "")
            current_values[field] = current_val
            
            if field not in prev_values or prev_values[field] != current_val:
                changed = True
        
        # State-based reporting logic
        try:
            if changed:
                self.alert_counters[cluster_id][alert_name] = 0
                should_report = True
            elif alert_state != "OK" and self.alert_counters[cluster_id][alert_name] < repeat_tolerance:
                should_report = True
                self.alert_counters[cluster_id][alert_name] += 1
            else:
                should_report = False
            
            # Update state only after successful report
            if should_report:
                self.reported_alerts[cluster_id][alert_name] = current_values
        except KeyError:
            logger.warning("State tracking issue for %s:%s", cluster_id, alert_name)
            should_report = True  # Safely report if state corrupted
        
        return should_report

    def _send_alerts(self, alerts):
        """Send alerts to server with error handling and confirmation"""
        try:
            log_msg = f"Sending {len(alerts)} alert reports"
            logger.info(log_msg)
            
            correlation_id = self.connection.send(
                message=alerts,
                destination=Constants.ALERTS_STATUS_REPORTS_ENDPOINT,
                log_message_function=self._log_alert_batch
            )
            
            # Register success callback
            self.server_responses.register_success_handler(
                correlation_id, 
                lambda h, m: self._handle_send_success(m)
            )
            
        except ConnectionIsAlreadyClosed:
            logger.warning("Server connection closed before sending alerts")
            raise
        except Exception as e:
            logger.error("Failed to send alerts: %s", str(e))
            raise

    def _handle_send_success(self, message):
        """Update internal state on successful send"""
        self.last_success = time.time()
        logger.debug("Successfully reported %d alerts", len(message))

    def _clean_inactive_clusters(self):
        """Clean up state for clusters that no longer exist"""
        active_clusters = set(self.definitions_cache.get_cluster_ids())
        
        # Clean reported_alerts
        for cluster_id in list(self.reported_alerts.keys()):
            if cluster_id not in active_clusters:
                del self.reported_alerts[cluster_id]
        
        # Clean alert counters
        for cluster_id in list(self.alert_counters.keys()):
            if cluster_id not in active_clusters:
                del self.alert_counters[cluster_id]
        
        logger.debug("Cleaned state for %d inactive clusters", 
                    len(self.reported_alerts) - len(active_clusters))

    def _log_alert_batch(self, alert_batch):
        """Generate safe log output for alert batches"""
        if not isinstance(alert_batch, list):
            return "(invalid alert format)"
            
        summary = {
            "count": len(alert_batch),
            "clusters": {},
            "states": defaultdict(int)
        }
        
        for alert in alert_batch:
            cluster_id = alert.get("clusterId", "unknown")
            alert_state = alert.get("state", "UNKNOWN")
            alert_name = alert.get("name", "unnamed")
            
            summary["clusters"].setdefault(cluster_id, []).append(alert_name)
            summary["states"][alert_state] += 1
            
        # Trim state text for logging
        if "text" in alert:
            alert["text"] = (alert["text"][:50] + '..') if len(alert["text"]) > 52 else alert["text"]
        
        return f"Alerts[count={summary['count']}, states={dict(summary['states'])}]"

    def get_report_stats(self):
        """Get current reporting statistics for monitoring"""
        counts = defaultdict(int)
        for cluster_data in self.reported_alerts.values():
            counts['alerts'] += len(cluster_data)
            
        return {
            "tracked_clusters": len(self.reported_alerts),
            "tracked_alerts": counts['alerts'],
            "last_success": self.last_success,
            "report_interval": self.alert_interval
        }

    def stop(self):
        """Trigger graceful shutdown"""
        self.stop_event.set()
        logger.info("Stopping alert reporter")
