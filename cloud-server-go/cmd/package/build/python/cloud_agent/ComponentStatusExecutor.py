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
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, List, Tuple, Optional

from cloud_agent import Constants
from cloud_agent.LiveStatus import LiveStatus
from cloud_agent.Utils import Utils
from cloud_agent.models.commands import AgentCommand
from cloud_stomp.adapter.websocket import ConnectionIsAlreadyClosed

logger = logging.getLogger(__name__)

class ComponentStatusExecutor(threading.Thread):
    """
    Advanced component health monitoring system providing:
        - Distributed component status tracking
        - Failure detection and recovery orchestration
        - Performance optimized reporting
        - Cluster-aware health monitoring
    
    Key features:
        - Adaptive component health checks
        - Status change detection and propagation
        - Stale report filtering system
        - Self-healing cluster awareness
    """
    
    def __init__(self, initializer_module):
        """
        Initialize the component status executor
        :param initializer_module: Main application initializer with configurations
        """
        super().__init__(name="ComponentStatusExecutor")
        self.initializer = initializer_module
        self.config = initializer_module.config
        self.metadata_cache = initializer_module.metadata_cache
        self.topology_cache = initializer_module.topology_cache
        self.service_orchestrator = initializer_module.customServiceOrchestrator
        self.stop_event = initializer_module.stop_event
        self.recovery_manager = initializer_module.recovery_manager
        self.server_listener = initializer_module.server_responses_listener
        
        # Core status storage
        self._reported_status = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))
        self._pending_updates = []  # Reports to be discarded
        self._last_refresh_time = 0
        
        # Thread controls
        self.check_interval = self.config.status_commands_run_interval
        self.min_interval = 15  # Minimum health check interval (seconds)
        self.max_interval = 600  # Maximum health check interval
        self.daemon = True  # Thread exits with main process
        
        # Performance tracking
        self.checks_performed = 0
        self.status_changes = 0
        self.last_complete_sweep = 0
        
        self._init_locks()
        logger.info(f"Component status executor initialized with {self.check_interval}s interval")
    
    def _init_locks(self):
        """Initialize all thread synchronization primitives"""
        self._update_lock = threading.RLock()
        self._pending_lock = threading.RLock()
        self._execution_lock = threading.Lock()
    
    @contextmanager
    def _status_lock(self):
        """Context manager for status data access"""
        with self._update_lock:
            yield
    
    @contextmanager
    def _pending_lock(self):
        """Context manager for pending updates list"""
        with self._pending_lock:
            yield
    
    def run(self):
        """Main monitoring lifecycle - executes until shutdown signal received"""
        if self.check_interval <= 0:
            self._handle_disabled_executor()
            return
            
        logger.info("Component status monitoring started")
        
        while not self.stop_event.is_set():
            cycle_start = time.monotonic()
            
            try:
                self._execute_monitoring_cycle()
            except Exception as err:
                self._handle_cycle_exception(err)
            
            # Calculate adaptive sleep interval
            sleep_time = self._calculate_next_cycle_delay(cycle_start)
            self.stop_event.wait(sleep_time)
        
        logger.info("Component status monitoring stopped")
    
    def _execute_monitoring_cycle(self):
        """Full component status evaluation and reporting cycle"""
        with self._execution_lock:
            # Purge data for removed clusters
            self._clean_stale_clusters()
            
            # Prepare reports collection
            cluster_reports = defaultdict(list)
            
            # Cycle through all configured clusters
            for cluster_id in self.topology_cache.get_cluster_ids():
                cluster_report = self._process_cluster(cluster_id)
                if cluster_report:
                    cluster_reports[cluster_id] = cluster_report
            
            # Filter outdated reports
            filtered_reports = self._filter_stale_reports(cluster_reports)
            
            # Send updates if available
            if filtered_reports:
                self._send_status_reports(filtered_reports)
            
            # Update metrics
            self.last_complete_sweep = time.monotonic()
            logger.debug(f"Monitoring cycle completed for {len(cluster_reports)} clusters")
    
    def _process_cluster(self, cluster_id: str) -> List[dict]:
        """Evaluate status for all components in a cluster"""
        try:
            topology = self.topology_cache[cluster_id]
            metadata = self.metadata_cache[cluster_id]
        except KeyError:
            logger.debug(f"Cluster {cluster_id} metadata unavailable - skipping")
            return []
        
        # Check if we should process this cluster
        if "status_commands_to_run" not in metadata or "components" not in topology:
            return []
        
        current_host_id = self.topology_cache.get_current_host_id(cluster_id)
        if not current_host_id:
            logger.warning(f"Host ID missing for cluster {cluster_id}")
            return []
        
        # Collect relevant status commands
        status_commands = metadata.status_commands_to_run
        cluster_report = []
        
        # Evaluate all components on current host
        for component in topology.components:
            # Skip processing if shutdown requested
            if self.stop_event.is_set():
                break
                
            # Skip components on other hosts
            if current_host_id not in component.hostIds:
                continue
                
            # Process each status command for this component
            for command_name in status_commands:
                component_report = self._evaluate_component(
                    cluster_id, 
                    component.serviceName, 
                    component.componentName, 
                    command_name
                )
                if component_report:
                    cluster_report.append(component_report)
        
        return cluster_report
    
    def _evaluate_component(
        self, 
        cluster_id: str, 
        service_name: str, 
        component_name: str, 
        command_name: str
    ) -> Optional[dict]:
        """
        Evaluate component status and detect changes
        Returns status report if changed, None otherwise
        """
        # Skip if commands are running for this component
        if self.service_orchestrator.commandsRunningForComponent(cluster_id, component_name):
            logger.debug(f"Skipping status check for {component_name} - operation in progress")
            return None
        
        # Get component status
        status_result = self.service_orchestrator.requestComponentStatus({
            "serviceName": service_name,
            "role": component_name,
            "clusterId": cluster_id,
            "commandType": AgentCommand.status
        })
        
        # Determine live status
        new_status = LiveStatus.LIVE_STATUS if status_result["exitcode"] == 0 else LiveStatus.DEAD_STATUS
        self.checks_performed += 1
        
        # Log status failures (excluding expected non-running states)
        if new_status == LiveStatus.DEAD_STATUS:
            self._log_component_failure(status_result, service_name, component_name)
        
        # Check for status changes
        current_status = self._get_reported_status(cluster_id, service_name, component_name, command_name)
        if new_status == current_status:
            return None  # Status unchanged
        
        # Prepare status report
        report = {
            "serviceName": service_name,
            "componentName": component_name,
            "command": command_name,
            "status": new_status,
            "clusterId": cluster_id
        }
        
        # Handle status change events
        self._handle_status_change(cluster_id, service_name, component_name, command_name, 
                                  current_status, new_status, report)
        
        return report
    
    def _log_component_failure(self, status_result: dict, service: str, component: str) -> None:
        """Log meaningful component failure messages"""
        stderr = status_result.get("stderr", "")
        if not ("ComponentIsNotRunning" in stderr or "ClientComponentHasNoStatus" in stderr):
            logger.warning(f"Status check failed for {service}/{component}:\n{stderr}")
    
    def _handle_status_change(
        self,
        cluster_id: str,
        service: str,
        component: str,
        command: str,
        old_status: str,
        new_status: str,
        report: dict
    ) -> None:
        """Process component status transitions"""
        logger.info(f"Status changed for {service}/{component}: {old_status} -> {new_status}")
        
        # Update stored status
        self._update_reported_status(cluster_id, service, component, command, new_status)
        
        # Trigger recovery actions
        self.recovery_manager.handle_status_change(component, new_status)
        self.status_changes += 1
        
        # Mark report for potential discard
        with self._pending_lock():
            self._pending_updates.append(report)
    
    def _clean_stale_clusters(self) -> None:
        """Purge status data for removed clusters"""
        with self._status_lock():
            active_clusters = set(self.topology_cache.get_cluster_ids())
            stored_clusters = list(self._reported_status.keys())
            
            for cluster_id in stored_clusters:
                if cluster_id not in active_clusters:
                    logger.info(f"Cleaning status data for removed cluster: {cluster_id}")
                    del self._reported_status[cluster_id]
    
    def _filter_stale_reports(self, reports: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
        """Remove outdated reports from the pending set"""
        if not self._pending_updates:
            return reports
            
        with self._pending_lock():
            pending_updates = self._pending_updates.copy()
            self._pending_updates.clear()
        
        if not pending_updates:
            return reports
            
        filtered_reports = defaultdict(list)
        for cluster_id, cluster_reports in reports.items():
            for report in cluster_reports:
                if not self._is_report_stale(report, pending_updates):
                    filtered_reports[cluster_id].append(report)
        
        return filtered_reports
    
    def _is_report_stale(self, report: dict, stale_set: List[dict]) -> bool:
        """Check if a report is outdated by comparing with pending changes"""
        return any(
            Utils.are_dicts_equal(report, stale_report, keys_to_skip=["status"])
            for stale_report in stale_set
        )
    
    def _send_status_reports(self, reports: Dict[str, List[dict]]) -> None:
        """Transmit status reports to the server"""
        if not self.initializer.is_registered:
            logger.debug("Skipping report send - agent not registered")
            return
        
        try:
            correlation_id = self.initializer.connection.send(
                message={"clusters": reports},
                destination=Constants.COMPONENT_STATUS_REPORTS_ENDPOINT
            )
            
            # Register success callback
            self.server_listener.add_callback(
                correlation_id,
                success_func=lambda: self._handle_report_success(reports),
                failure_func=lambda: self._handle_report_failure(reports)
            )
        except ConnectionIsAlreadyClosed:
            logger.warning("Failed to send reports - connection closed")
    
    def _handle_report_success(self, reports: Dict[str, List[dict]]) -> None:
        """Process successfully delivered reports"""
        with self._status_lock():
            for cluster_id, report_list in reports.items():
                for report in report_list:
                    service = report["serviceName"]
                    component = report["componentName"]
                    command = report["command"]
                    status = report["status"]
                    
                    self._update_reported_status(cluster_id, service, component, command, status)
    
    def _handle_report_failure(self, reports: Dict[str, List[dict]]) -> None:
        """Handle failed report delivery - retry later"""
        logger.warning("Component status reports delivery failed")
        with self._pending_lock():
            for cluster_reports in reports.values():
                for report in cluster_reports:
                    self._pending_updates.append(report)
    
    def _update_reported_status(
        self,
        cluster_id: str,
        service: str,
        component: str,
        command: str,
        status: str
    ) -> None:
        """Update the stored reported status for a component"""
        with self._status_lock():
            component_key = f"{service}/{component}"
            self._reported_status[cluster_id][component_key][command] = status
    
    def _get_reported_status(
        self,
        cluster_id: str,
        service: str,
        component: str,
        command: str
    ) -> Optional[str]:
        """Retrieve stored status for a component"""
        with self._status_lock():
            component_key = f"{service}/{component}"
            return self._reported_status[cluster_id][component_key].get(command)
    
    def _calculate_next_cycle_delay(self, cycle_start: float) -> float:
        """Dynamically determine sleep interval between cycles"""
        # Ensure minimum interval is respected
        base_interval = max(self.check_interval, self.min_interval)
        
        # Reduce frequency during off hours (customizable)
        current_hour = time.localtime().tm_hour
        if 0 <= current_hour < 6:  # Midnight to 6AM
            return min(base_interval * 2, self.max_interval)
        
        return base_interval
    
    def _handle_disabled_executor(self) -> None:
        """Special handling when executor is disabled"""
        logger.warning("Component status monitoring is disabled - critical functionality may be affected")
        # While disabled, prevent resource consumption
        self.stop_event.wait(3600)  # Check hourly if still disabled
    
    def _handle_cycle_exception(self, error: Exception) -> None:
        """Handle exceptions during monitoring cycle"""
        logger.exception(f"Monitoring cycle failed: {error}")
        # Add custom recovery for specific exceptions if needed
    
    def force_refresh(self) -> None:
        """Trigger immediate status refresh for all components"""
        logger.info("Forcing full component status refresh")
        with self._execution_lock:
            # Clear pending updates
            with self._pending_lock():
                self._pending_updates.clear()
            
            # Resend all cached statuses
            self.force_send_component_statuses()
    
    def force_send_component_statuses(self) -> None:
        """Generate and send complete component status snapshot"""
        cluster_reports = defaultdict(list)
        
        with self._status_lock():
            for cluster_id, components in self._reported_status.items():
                for comp_path, commands in components.items():
                    service, component = comp_path.split("/", 1)
                    for command_name, status in commands.items():
                        report = {
                            "serviceName": service,
                            "componentName": component,
                            "command": command_name,
                            "status": status,
                            "clusterId": cluster_id
                        }
                        cluster_reports[cluster_id].append(report)
        
        if cluster_reports:
            self._send_status_reports(cluster_reports)
    
    def get_status_summary(self) -> dict:
        """Retrieve executor performance metrics"""
        return {
            "active": self.is_alive(),
            "interval": self.check_interval,
            "last_run": self.last_complete_sweep,
            "components_tracked": sum(len(c) for c in self._reported_status.values()),
            "status_checks": self.checks_performed,
            "status_changes": self.status_changes
        }
    
    def shutdown(self) -> None:
        """Gracefully terminate the executor"""
        if not self.is_alive():
            return
            
        logger.info("Stopping component status monitoring")
        self.stop_event.set()
        
        # Send final status report
        self.force_send_component_statuses()
        
        # Wait for thread to complete
        self.join(timeout=30)
        if self.is_alive():
            logger.warning("Component status executor failed to stop cleanly")


# Example usage
if __name__ == "__main__":
    import sys
    from collections import namedtuple
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock initializer setup
    class MockInitializer:
        def __init__(self):
            self.config = namedtuple('Config', ['status_commands_run_interval'])(30)
            self.metadata_cache = {}
            self.topology_cache = {}
            self.customServiceOrchestrator = namedtuple('Orc', ['requestComponentStatus'])(lambda x: {"exitcode": 0})
            self.stop_event = threading.Event()
            self.recovery_manager = namedtuple('Recovery', ['handle_status_change'])(lambda: None)
            self.server_responses_listener = namedtuple('Listener', ['add_callback'])(lambda: None)
            self.connection = namedtuple('Conn', ['send'])(lambda x,y: "corr123")
            self.is_registered = True
    
    # Create and start executor
    executor = ComponentStatusExecutor(MockInitializer())
    executor.start()
    
    logger.info("Running component status executor for 60 seconds")
    time.sleep(60)
    
    # Graceful shutdown
    logger.info("Requesting shutdown")
    executor.shutdown()
    logger.info("Execution complete")
