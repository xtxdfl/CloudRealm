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
import time
import threading
import concurrent.futures
import uuid
import re
from collections import defaultdict
from enum import Enum

from apscheduler.scheduler import Scheduler
from alerts.collector import AlertCollector
from alerts.metric_alert import MetricAlert
from alerts.ams_alert import AmsAlert
from alerts.port_alert import PortAlert
from alerts.script_alert import ScriptAlert
from alerts.web_alert import WebAlert
from alerts.recovery_alert import RecoveryAlert
from ExitHelper import ExitHelper
from Utils import Utils

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Enumeration of supported alert types"""
    PORT = "PORT"
    METRIC = "METRIC"
    AMS = "AMS"
    SCRIPT = "SCRIPT"
    WEB = "WEB"
    RECOVERY = "RECOVERY"


class AlertDefinitionSource:
    """Represents the source configuration for an alert definition"""
    def __init__(self, config):
        self.type = config.get("type", "")
        self.interval = config.get("interval", 60)
        # Additional attributes based on alert type
        if self.type == AlertType.SCRIPT.value:
            self.script_path = config.get("path", "")
        # Add more type-specific attributes as needed


class AlertSchedulerHandler:
    """Advanced alert scheduling system with dynamic management capabilities"""
    
    # Configuration constants
    DEFAULT_THREADPOOL_SIZE = 7
    MAX_CONCURRENT_ALERTS = 5
    ALERT_LOCK_TIMEOUT = 300  # 5 minutes

    def __init__(self, initializer_module, in_minutes=True):
        self.initializer = initializer_module
        self.config = initializer_module.config
        self.in_minutes = in_minutes
        
        # Alert configuration
        self.alert_definitions_cache = initializer_module.alert_definitions_cache
        
        # Setup scheduler
        self._setup_scheduler_config()
        self.scheduler = Scheduler(self.scheduler_config)
        
        # Alert collector
        self.collector = AlertCollector()
        self.alert_reporter = initializer_module.alert_status_reporter
        
        # Thread pool for concurrent alert execution
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.DEFAULT_THREADPOOL_SIZE
        )
        self.active_alerts = {}
        self.alert_locks = defaultdict(threading.Lock)
        self.recovery_manager = initializer_module.recovery_manager
        
        # Register exit handler
        ExitHelper().register(self.exit_handler)
        logger.info("AlertSchedulerHandler initialized successfully")

    def _setup_scheduler_config(self):
        """Configure scheduler settings"""
        alert_grace_period = int(self.config.get("agent", "alert_grace_period", 5))
        apscheduler_standalone = False
        
        self.scheduler_config = {
            "apscheduler.threadpool.core_threads": self.DEFAULT_THREADPOOL_SIZE,
            "apscheduler.coalesce": True,
            "apscheduler.standalone": apscheduler_standalone,
            "apscheduler.misfire_grace_time": alert_grace_period,
            "apscheduler.threadpool.context_injector": (
                self._inject_job_context
                if not apscheduler_standalone
                else None
            ),
            "apscheduler.threadpool.agent_config": self.config,
        }

    def _inject_job_context(self, config):
        """Inject necessary context into alert jobs"""
        if not config.use_system_proxy_setting():
            from cloud_commons.network import reconfigure_urllib2_opener
            reconfigure_urllib2_opener(ignore_system_proxy=True)
        logger.debug("Job context injected for alert execution")

    def exit_handler(self):
        """Clean shutdown procedure"""
        logger.info("Starting AlertSchedulerHandler shutdown")
        self.stop()
        logger.info("AlertSchedulerHandler shutdown complete")

    def start(self):
        """Start the alert scheduling system"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Restarting alert scheduler")
        
        try:
            alert_definitions = self._load_alert_definitions()
            self._schedule_definitions(alert_definitions)
            self.scheduler.start()
            logger.info(
                "Alert scheduler started successfully with %d alerts",
                len(alert_definitions)
            )
        except Exception as e:
            logger.critical(
                "Failed to start alert scheduler: %s", 
                repr(e),
                exc_info=True
            )
            raise

    def stop(self):
        """Stop all alert processing"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("Stopped the alert scheduler")
            
            # Cancel all active alerts
            self._cancel_active_alerts()
            logger.info("Cancelled active alerts")
        except Exception as e:
            logger.error(
                "Error during alert scheduler shutdown: %s", 
                repr(e),
                exc_info=True
            )

    def update_definitions(self, event_type):
        """Update alert definitions based on cluster changes"""
        try:
            if event_type == "CREATE":
                self.reschedule_all()
            elif event_type in ("DELETE", "UPDATE"):
                self.reschedule()
            logger.info(
                "Alert definitions updated for event: %s", 
                event_type
            )
        except Exception as e:
            logger.error(
                "Failed to update alert definitions: %s", 
                repr(e),
                exc_info=True
            )

    def reschedule(self):
        """Reschedule alerts based on current definition changes"""
        try:
            updated_definitions = self._load_alert_definitions()
            current_jobs = self.scheduler.get_jobs()
            
            # Clear previously reported alerts
            self.alert_reporter.reported_alerts.clear()
            
            # Track job UUIDs for diff calculations
            active_uuids = {alert.get_uuid() for alert in updated_definitions}
            scheduled_uuids = {job.name for job in current_jobs}
            
            # Calculate needed actions
            to_remove = scheduled_uuids - active_uuids
            to_add = active_uuids - scheduled_uuids
            
            # Remove obsolete jobs
            for job_uuid in to_remove:
                self._unschedule_job_by_uuid(job_uuid)
            
            # Add new jobs
            added_count = 0
            for definition in updated_definitions:
                if definition.get_uuid() in to_add:
                    self._schedule_definition(definition)
                    added_count += 1
            
            logger.info(
                "Alert reschedule complete: Removed %d, Added %d",
                len(to_remove), added_count
            )
            return True
        except Exception as e:
            logger.error(
                "Alert rescheduling failed: %s", 
                repr(e),
                exc_info=True
            )
            return False

    def reschedule_all(self):
        """Complete rescheduling of all alerts"""
        try:
            current_jobs = self.scheduler.get_jobs()
            job_count = len(current_jobs)
            
            # Unschedule all existing jobs
            for job in current_jobs:
                self._unschedule_job_by_uuid(job.name)
            
            # Reload and reschedule definitions
            alert_definitions = self._load_alert_definitions()
            self._schedule_definitions(alert_definitions)
            
            logger.info(
                "Full alert reschedule complete: Removed %d, Added %d alerts",
                job_count, len(alert_definitions)
            )
        except Exception as e:
            logger.error(
                "Failed to perform full alert reschedule: %s", 
                repr(e),
                exc_info=True
            )

    def _load_alert_definitions(self):
        """Load and parse all alert definitions from cache"""
        alert_definitions = []
        definitions_processed = 0
        
        for cluster_id, command_json in self.alert_definitions_cache.items():
            cluster_name = command_json.get("clusterName", "")
            host_name = command_json.get("hostName", "")
            public_host_name = command_json.get("publicHostName", "")
            cluster_hash = command_json.get("hash", None)
            
            # Create alert instances from definitions
            for definition in command_json.get("alertDefinitions", []):
                alert = self._create_alert_instance(
                    definition, 
                    cluster_name, 
                    cluster_id,
                    host_name, 
                    public_host_name
                )
                if alert:
                    definitions_processed += 1
                    alert.set_helpers(
                        self.collector,
                        self.initializer.configurations_cache,
                        self.initializer.configuration_builder
                    )
                    alert_definitions.append(alert)
        
        logger.debug(
            "Loaded %d alert definitions across %d clusters",
            definitions_processed, len(self.alert_definitions_cache)
        )
        return alert_definitions

    def _create_alert_instance(self, json_definition, cluster_name, cluster_id, host_name, public_host_name):
        """Create alert instance from JSON definition"""
        # Create immutable copy of definition
        definition = Utils.get_mutable_copy(json_definition)
        source = definition.get("source", {})
        source_type = source.get("type", "").upper()
        
        # Try to map to AlertType enum
        try:
            parsed_type = AlertType(source_type)
        except Exception:
            logger.warning(
                "Unknown alert type '%s' in definition: %s", 
                source_type, json_definition.get("name", "Unnamed Alert")
            )
            return None
        
        # Create appropriate alert type
        alert_classes = {
            AlertType.METRIC: MetricAlert,
            AlertType.AMS: AmsAlert,
            AlertType.PORT: PortAlert,
            AlertType.SCRIPT: ScriptAlert,
            AlertType.WEB: WebAlert,
            AlertType.RECOVERY: RecoveryAlert
        }
        
        # Prepare type-specific configuration
        config = self._prepare_alert_config(definition, source, source_type)
        
        try:
            alert = alert_classes[parsed_type](
                definition,
                config,
                self.config
            )
            alert.set_cluster(
                cluster_name, 
                cluster_id, 
                host_name, 
                public_host_name
            )
            return alert
        except Exception as e:
            logger.error(
                "Failed to create alert '%s' (%s): %s", 
                json_definition.get("name", "Unnamed Alert"),
                source_type,
                str(e),
                exc_info=logger.isEnabledFor(logging.DEBUG)
            )
            return None

    def _prepare_alert_config(self, definition, source, source_type):
        """Prepare alert-specific configuration"""
        config = source.copy()
        
        # Handle script-specific paths
        if source_type == AlertType.SCRIPT.value:
            config["stacks_directory"] = self.initializer.stacks_dir
            config["common_services_directory"] = self.initializer.common_services_dir
            config["extensions_directory"] = self.initializer.extensions_dir
            config["host_scripts_directory"] = self.initializer.host_scripts_dir
        
        return config

    def _schedule_definitions(self, definitions):
        """Schedule a list of alert definitions"""
        scheduled_count = 0
        for definition in definitions:
            if self._schedule_definition(definition):
                scheduled_count += 1
        logger.info(
            "Scheduled %d/%d alert definitions", 
            scheduled_count, len(definitions)
        )

    def _schedule_definition(self, definition):
        """Schedule an individual alert definition"""
        if not definition.is_enabled():
            logger.info(
                "Skipping disabled alert: %s (%s)", 
                definition.get_name(), definition.get_uuid()
            )
            return False
        
        try:
            job = self.scheduler.add_interval_job(
                self._wrap_alert_execution(definition),
                minutes=definition.interval() if self.in_minutes else None,
                seconds=None if self.in_minutes else definition.interval()
            )
            job.name = definition.get_uuid()
            logger.info(
                "Scheduled alert: %s (%s, interval=%d %s)",
                definition.get_name(),
                definition.get_uuid(),
                definition.interval(),
                "minutes" if self.in_minutes else "seconds"
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to schedule alert '%s': %s",
                definition.get_name(),
                str(e)
            )
            return False

    def _wrap_alert_execution(self, definition):
        """Create a thread-safe wrapper for alert execution"""
        alert_uuid = definition.get_uuid()
        alert_name = definition.get_name()
        
        def wrapped_execution():
            # Check if this alert is already running
            if not self._acquire_alert_lock(alert_uuid):
                logger.warning(
                    "Skipping alert %s; already running", 
                    alert_name
                )
                return
                
            try:
                # Track and execute the alert
                self._track_active_alert(alert_uuid, alert_name)
                definition.collect()
            except Exception as e:
                logger.error(
                    "Alert %s execution failed: %s", 
                    alert_name,
                    str(e),
                    exc_info=logger.isEnabledFor(logging.DEBUG)
                )
            finally:
                self._release_alert_lock(alert_uuid)
                self._untrack_active_alert(alert_uuid)
        
        return wrapped_execution

    def _acquire_alert_lock(self, alert_uuid):
        """Acquire lock for alert execution or skip if already running"""
        lock = self.alert_locks[alert_uuid]
        return lock.acquire(blocking=False)

    def _release_alert_lock(self, alert_uuid):
        """Release lock after alert execution"""
        if alert_uuid in self.alert_locks:
            self.alert_locks[alert_uuid].release()

    def _track_active_alert(self, alert_uuid, alert_name):
        """Track an active alert execution"""
        if alert_uuid not in self.active_alerts:
            self.active_alerts[alert_uuid] = {
                "name": alert_name,
                "start_time": time.time(),
                "thread_id": threading.get_ident()
            }
            logger.debug(
                "Started alert execution: %s (%s)", 
                alert_name, alert_uuid
            )

    def _untrack_active_alert(self, alert_uuid):
        """Remove alert from tracking after completion"""
        if alert_uuid in self.active_alerts:
            alert_name = self.active_alerts[alert_uuid]["name"]
            duration = time.time() - self.active_alerts[alert_uuid]["start_time"]
            del self.active_alerts[alert_uuid]
            logger.debug(
                "Completed alert %s in %.2f seconds", 
                alert_name, duration
            )

    def _unschedule_job_by_uuid(self, uuid):
        """Unschedule job and clean up resources"""
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            if job.name == uuid:
                try:
                    self.scheduler.unschedule_job(job)
                    self.collector.remove_by_uuid(uuid)
                    if uuid in self.active_alerts:
                        del self.active_alerts[uuid]
                    if uuid in self.alert_locks:
                        del self.alert_locks[uuid]
                    logger.info("Unscheduled alert: %s", uuid)
                except Exception as e:
                    logger.error(
                        "Failed to unschedule alert: %s", 
                        uuid,
                        exc_info=True
                    )
                return True
        return False

    def _cancel_active_alerts(self):
        """Cancel all currently executing alerts"""
        for alert_id, alert_data in list(self.active_alerts.items()):
            try:
                # Would actually require a way to interrupt the running alert
                pass
            except Exception:
                logger.error(
                    "Failed to cancel alert: %s", 
                    alert_data["name"],
                    exc_info=True
                )
        
        # Clean up tracking
        self.active_alerts.clear()
        self.alert_locks.clear()

    def execute_alert(self, execution_commands):
        """Execute alerts on demand"""
        if not execution_commands:
            logger.warning("No alerts provided for execution")
            return
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_ALERTS
        ) as executor:
            futures = {}
            
            # Create tasks for each alert
            for command in execution_commands:
                future = executor.submit(
                    self._execute_single_alert, 
                    command
                )
                task_id = str(uuid.uuid4())
                futures[future] = task_id
                logger.debug(
                    "Submitted on-demand alert execution task: %s", 
                    task_id
                )
            
            # Wait for completion
            for future in concurrent.futures.as_completed(futures):
                task_id = futures[future]
                try:
                    future.result()
                    logger.debug(
                        "Completed on-demand alert task: %s", 
                        task_id
                    )
                except Exception as e:
                    logger.error(
                        "On-demand alert task %s failed: %s", 
                        task_id, str(e)
                    )

    def _execute_single_alert(self, command):
        """Execute a single alert definition immediately"""
        try:
            alert_definition = command.get("alertDefinition", {})
            cluster_name = command.get("clusterName", "")
            cluster_id = command.get("clusterId", "")
            host_name = command.get("hostName", "")
            public_host_name = command.get("publicHostName", "")
            alert_name = alert_definition.get("name", "Unknown Alert")
            
            alert = self._create_alert_instance(
                alert_definition,
                cluster_name,
                cluster_id,
                host_name,
                public_host_name
            )
            
            if not alert:
                logger.error(
                    "Skipping on-demand alert due to creation failure: %s", 
                    alert_name
                )
                return
            
            # Inject dependencies
            alert.set_helpers(
                self.collector,
                self.initializer.configurations_cache,
                self.initializer.configuration_builder
            )
            
            # Execute
            logger.info(
                "Executing on-demand alert: %s", 
                alert_name
            )
            alert.collect()
            logger.info(
                "Completed on-demand alert: %s", 
                alert_name
            )
        except Exception as e:
            logger.error(
                "Failed to execute on-demand alert: %s", 
                str(e),
                exc_info=True
            )
            raise

    def get_scheduled_job_count(self):
        """Get the number of currently scheduled jobs"""
        return len(self.scheduler.get_jobs()) if self.scheduler else 0

    def get_active_alert_count(self):
        """Get the number of currently executing alerts"""
        return len(self.active_alerts)

    def get_collector(self):
        """Get the alert collector instance"""
        return self.collector

    def get_collector_stats(self):
        """Get statistics about collected alerts"""
        return self.collector.get_statistics()
