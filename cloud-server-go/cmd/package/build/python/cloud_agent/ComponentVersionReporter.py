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
from collections import defaultdict
from typing import Dict, List, Optional

from cloud_agent import Constants
from cloud_agent.models.commands import AgentCommand

logger = logging.getLogger(__name__)


class ComponentVersionReporter(threading.Thread):
    """
    Component Version Reporting System
    ==================================
    
    This system provides comprehensive version tracking for all components
    across multiple cluster environments. Key features include:
    
    - Distributed component version discovery
    - Error-resilient version collection
    - Intelligent caching mechanisms
    - Configurable version detection strategies
    
    The system operates as follows:
    1. Discovers all installed components on the current host
    2. Executes version detection commands for each component
    3. Processes and validates version information
    4. Aggregates and reports versions to the central server
    """
    
    def __init__(self, initializer_module):
        """
        Initialize the version reporting subsystem
        :param initializer_module: Main application initializer
        """
        super().__init__(name="ComponentVersionReporter")
        self.initializer = initializer_module
        self.topology_cache = initializer_module.topology_cache
        self.service_orchestrator = initializer_module.customServiceOrchestrator
        self.connection = initializer_module.connection
        self.server_listener = initializer_module.server_responses_listener
        self.stop_event = initializer_module.stop_event
        self.execution_count = 0
        
        # Configuration
        self.max_retry_count = 3  # Max attempts to get component version
        self.retry_delay = 5  # Seconds between retries
        self.daemon = True  # Thread exits with main process
        
        logger.info("Component version reporter initialized")

    def run(self):
        """
        Main execution loop for version collection and reporting
        """
        logger.info("Component version reporting started")
        
        # Execute version reporting with retries
        success = False
        for attempt in range(self.max_retry_count + 1):
            if self.stop_event.is_set():
                logger.info("Reporting aborted - shutdown requested")
                return
                
            try:
                self._execute_version_reporting()
                success = True
                break
            except Exception as err:
                logger.error(f"Version reporting attempt {attempt+1} failed: {str(err)}")
                self.execution_count += 1
                self.stop_event.wait(self.retry_delay)
        
        if success:
            logger.info("Component version reporting completed successfully")
        else:
            logger.error("Component version reporting failed after %d attempts", self.max_retry_count)

    def _execute_version_reporting(self) -> None:
        """
        Core version collection and reporting process
        """
        # Prepare cluster report containers
        version_reports = defaultdict(list)
        failed_components = []
        success_count = 0
        
        # Process all clusters
        for cluster_id in self.topology_cache.get_cluster_ids():
            if self.stop_event.is_set():
                return
                
            cluster_report = self._process_cluster(cluster_id)
            if not cluster_report:
                continue
                
            for report in cluster_report:
                if report.get("version") is not None:
                    version_reports[cluster_id].append(report)
                    success_count += 1
                else:
                    failed_components.append(
                        f"{report['serviceName']}/{report['componentName']}"
                    )
        
        # Check if any versions were collected
        if not any(version_reports.values()):
            logger.warning("No component versions collected for reporting")
            raise Exception("No versions collected")
        
        # Report collected versions
        self._send_version_reports(version_reports)
        
        # Log summary
        logger.info(
            "Version collection summary: %d components succeeded, %d failed",
            success_count, len(failed_components)
        )
        if failed_components:
            logger.debug("Failed components: %s", ", ".join(failed_components))

    def _process_cluster(self, cluster_id: str) -> Optional[List[dict]]:
        """
        Collect version information for components in a specific cluster
        :param cluster_id: Identifier of the target cluster
        :return: List of version reports for this cluster
        """
        try:
            topology = self.topology_cache[cluster_id]
        except KeyError:
            logger.warning("Cluster %s not found in topology cache", cluster_id)
            return None
            
        if "components" not in topology:
            logger.debug("No components defined for cluster %s", cluster_id)
            return None
            
        current_host_id = self.topology_cache.get_current_host_id(cluster_id)
        if not current_host_id:
            logger.warning("No host ID found for cluster %s", cluster_id)
            return None
            
        cluster_reports = []
        for component in topology.components:
            if self.stop_event.is_set():
                break
                
            if current_host_id not in component.hostIds:
                continue  # Component not on this host
                
            version_report = self._get_component_version(
                cluster_id, component.serviceName, component.componentName
            )
            if version_report:
                cluster_reports.append(version_report)
        
        return cluster_reports

    def _get_component_version(
        self, cluster_id: str, service_name: str, component_name: str
    ) -> Optional[dict]:
        """
        Retrieve version for a specific component
        :param cluster_id: Cluster identifier
        :param service_name: Name of the service
        :param component_name: Name of the component
        :return: Version report dictionary or None if failed
        """
        for attempt in range(1, self.max_retry_count + 1):
            try:
                result = self.service_orchestrator.requestComponentStatus(
                    command_dict={
                        "serviceName": service_name,
                        "role": component_name,
                        "clusterId": cluster_id,
                        "commandType": AgentCommand.get_version
                    },
                    command_name=AgentCommand.get_version
                )
                
                return self._process_version_result(
                    result, cluster_id, service_name, component_name
                )
            except Exception as version_error:
                logger.warning(
                    "Attempt %d/%d failed for %s/%s: %s",
                    attempt, self.max_retry_count,
                    service_name, component_name, str(version_error)
                )
                if attempt < self.max_retry_count:
                    self.stop_event.wait(self.retry_delay)
        return None

    def _process_version_result(
        self, result: dict, cluster_id: str, service_name: str, component_name: str
    ) -> dict:
        """
        Process and validate the raw version detection result
        :return: Clean version report dictionary
        """
        # Handle command execution failures
        if result["exitcode"] != 0:
            logger.error(
                "Version command failed for %s/%s: %s",
                service_name, component_name, result.get("stderr", "Unknown error")
            )
            return {
                "serviceName": service_name,
                "componentName": component_name,
                "clusterId": cluster_id,
                "error": result.get("stderr", "Command failed"),
                "exitcode": result["exitcode"]
            }
        
        # Handle missing structured output
        structured_out = result.get("structuredOut", {})
        if not structured_out or not isinstance(structured_out, dict):
            logger.error(
                "Invalid structured output for %s/%s: %s",
                service_name, component_name, str(structured_out)
            )
            return {
                "serviceName": service_name,
                "componentName": component_name,
                "clusterId": cluster_id,
                "error": "Missing or invalid structured output"
            }
        
        # Extract version
        version = structured_out.get("version")
        if not version:
            logger.error(
                "Version not found in output for %s/%s",
                service_name, component_name
            )
            return {
                "serviceName": service_name,
                "componentName": component_name,
                "clusterId": cluster_id,
                "error": "Version key missing in output"
            }
        
        # Success case
        logger.debug(
            "Found version '%s' for %s/%s",
            version, service_name, component_name
        )
        return {
            "serviceName": service_name,
            "componentName": component_name,
            "version": version,
            "clusterId": cluster_id
        }

    def _send_version_reports(self, cluster_reports: Dict[str, List[dict]]) -> None:
        """
        Transmit version reports to the central server
        :param cluster_reports: Collected version reports by cluster
        """
        if not cluster_reports:
            logger.warning("No version reports to send")
            return
            
        if not self.initializer.is_registered:
            logger.error("Cannot send reports - agent not registered")
            return
            
        try:
            # Serialize reports in batches
            report_packages = self._package_reports_for_transport(cluster_reports)
            for package in report_packages:
                self.connection.send(
                    message={"clusters": package},
                    destination=Constants.COMPONENT_VERSION_REPORTS_ENDPOINT
                )
                logger.debug("Sent version report package with %d components", 
                           sum(len(c) for c in package.values()))
        except Exception as send_error:
            logger.exception("Failed to send version reports: %s", str(send_error))

    def _package_reports_for_transport(self, reports: Dict[str, List[dict]]) -> List[Dict[str, List[dict]]]:
        """
        Package large reports into transmission-friendly chunks
        :return: List of report chunks suitable for network transmission
        """
        max_payload_size = 1_000_000  # 1MB max payload
        packages = []
        current_pkg = defaultdict(list)
        current_size = 0
        
        for cluster_id, cluster_reports in reports.items():
            for report in cluster_reports:
                report_size = len(str(report))
                
                # Start new package if needed
                if current_size + report_size > max_payload_size:
                    packages.append(dict(current_pkg))
                    current_pkg = defaultdict(list)
                    current_size = 0
                
                current_pkg[cluster_id].append(report)
                current_size += report_size
        
        if current_pkg:
            packages.append(dict(current_pkg))
            
        return packages

    def run_on_demand(self) -> None:
        """
        Execute version reporting immediately as a manual request
        """
        if self.is_alive():
            logger.warning("Version reporter already running")
        else:
            logger.info("Executing manual version report")
            self.start()


# Example usage
if __name__ == "__main__":
    import time
    import sys
    import logging.handlers
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        stream=sys.stdout
    )
    
    # Mock initializer class
    class MockInitializer:
        def __init__(self):
            self.config = type('Config', (), {})()
            self.topology_cache = type('Cache', (), {
                'get_cluster_ids': lambda: ['cluster1', 'cluster2'],
                '__getitem__': lambda self, key: {'components': [
                    type('Component', (), {
                        'serviceName': 'HDFS',
                        'componentName': 'DATANODE',
                        'hostIds': ['host1']
                    })(),
                    type('Component', (), {
                        'serviceName': 'YARN',
                        'componentName': 'NODEMANAGER',
                        'hostIds': ['host2']
                    })()
                ]},
                'get_current_host_id': lambda _, cluster: 'host1'
            })()
            self.customServiceOrchestrator = type('Orchestrator', (), {
                'requestComponentStatus': lambda self, **kwargs: {
                    "exitcode": 0,
                    "structuredOut": {"version": "3.2.1"}
                }
            })()
            self.connection = type('Connection', (), {
                'send': lambda self, **kwargs: None
            })()
            self.stop_event = threading.Event()
    
    # Create and run reporter
    reporter = ComponentVersionReporter(MockInitializer())
    print("Starting version reporter...")
    reporter.start()
    
    # Wait for completion
    reporter.join()
    print("Version reporting completed")
