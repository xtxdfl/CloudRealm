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
from typing import Any, Dict, Optional, Union

from cloud_agent import hostname
from ExceptionHandler import ConfigValidationError, CacheExpiredError

logger = logging.getLogger(__name__)


class ConfigurationBuilder:
    """
    Advanced Configuration Management System
    ========================================
    
    This system provides a unified interface for building configuration 
    payloads needed for executing various commands. It consolidates data from:
    
    - Cluster-level configurations
    - Host-specific parameters
    - Service and component configurations
    - Topology metadata
    - Agent-level settings
    
    Key features:
    
    - Intelligent caching and validation
    - Dynamic configuration assembly
    - Version-aware payload construction
    - Multi-level configuration hierarchy
    - Detailed diagnostics via telemetry
    
    The configuration builder ensures:
    - Data consistency across layers
    - Timestamp validation for configuration freshness
    - Secure handling of sensitive parameters
    - Efficient resource utilization
    """
    
    AGENT_LEVEL_KEYS = {
        "public_hostname", 
        "agentCacheDir", 
        "agentConfigParams"
    }
    
    def __init__(self, initializer_module):
        """
        Initialize the configuration builder system
        :param initializer_module: Main application initializer
        """
        self.config = initializer_module.config
        self.metadata_cache = initializer_module.metadata_cache
        self.topology_cache = initializer_cache.topology_cache
        self.host_params_cache = initializer_module.host_level_params_cache
        self.config_cache = initializer_module.configurations_cache
        self.telemetry = {}  # Track configuration build metrics
        
        # Pre-compute frequently used values
        self.cache_dir = self.config.get("agent", "cache_dir")
        self.system_proxy_setting = self.config.use_system_proxy_setting()
        self.parallel_exec = self.config.get_parallel_exec_option()
        
        logger.info("Configuration builder initialized")
    
    def get_configuration(
        self, 
        cluster_id: Optional[str], 
        service_name: Optional[str] = None, 
        component_name: Optional[str] = None, 
        config_timestamp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build a comprehensive configuration payload
        
        The output configuration hierarchy:
        1. Global-level parameters
        2. Cluster-level parameters
        3. Service-level parameters
        4. Component-level parameters
        5. Host-specific parameters
        
        :param cluster_id: Target cluster identifier
        :param service_name: Service name for the configuration
        :param component_name: Component name for the configuration
        :param config_timestamp: Expected configuration freshness timestamp
        :return: Unified configuration dictionary
        :raises ConfigValidationError: For invalid input parameters
        :raises CacheExpiredError: If provided timestamp is newer than cache
        """
        # Start telemetry tracking
        self._reset_telemetry()
        
        try:
            # Validate input parameters
            self._validate_input(cluster_id, service_name, component_name)
            
            # Primary configuration container
            config_payload = {}
            self.telemetry["start_time"] = time.monotonic()
            
            # Build cluster-specific configuration if provided
            if cluster_id:
                logger.debug(f"Building config for cluster: {cluster_id}")
                self._handle_config_timestamp(config_timestamp)
                config_payload.update(self._build_cluster_config(cluster_id, service_name, component_name))
            else:
                logger.debug("Building agent-level configuration")
                config_payload["agentLevelParams"] = {}
            
            # Add global and agent-level settings
            self._add_global_parameters(config_payload)
            self._add_agent_parameters(config_payload)
            
            # Finalize security properties
            self._secure_sensitive_data(config_payload)
            
            # Return completed payload
            return config_payload
        except Exception as error:
            logger.exception("Configuration build failed")
            raise ConfigBuildError("Failed to create configuration") from error
        finally:
            # Finish telemetry collection
            self._complete_telemetry()
    
    def _validate_input(
        self,
        cluster_id: Optional[str],
        service_name: Optional[str],
        component_name: Optional[str]
    ) -> None:
        """Validate configuration input parameters"""
        self.telemetry["cluster_id"] = cluster_id
        self.telemetry["service"] = service_name
        self.telemetry["component"] = component_name
        
        # Validate component requires service
        if component_name and not service_name:
            logger.warning("Component specified without service")
            raise ConfigValidationError("Component requires service specification")
        
        # Validate cluster existence
        if cluster_id and cluster_id not in self.topology_cache.clusters:
            logger.error(f"Invalid cluster ID: {cluster_id}")
            raise ConfigValidationError(f"Cluster {cluster_id} not found")
    
    def _handle_config_timestamp(self, config_timestamp: Optional[int]) -> None:
        """Validate cache freshness against required timestamp"""
        if config_timestamp is not None:
            cache_timestamp = self.config_cache.global_timestamp
            
            # Check if cache is expired
            if cache_timestamp < config_timestamp:
                logger.error(
                    f"Config timestamp mismatch: cache={cache_timestamp}, required={config_timestamp}"
                )
                raise CacheExpiredError("Configuration cache is outdated")
            
            logger.debug(f"Config timestamp valid: {cache_timestamp}")
    
    def _build_cluster_config(
        self,
        cluster_id: str,
        service_name: Optional[str],
        component_name: Optional[str]
    ) -> Dict[str, Any]:
        """Build configuration layer for a specific cluster"""
        config = {}
        
        # Get cluster metadata
        metadata = self.metadata_cache[cluster_id]
        host_params = self.host_params_cache[cluster_id]
        configurations = self.config_cache[cluster_id]
        
        # Construct base cluster parameters
        config["clusterLevelParams"] = metadata.clusterLevelParams
        config["hostLevelParams"] = host_params
        config["clusterHostInfo"] = self.topology_cache.get_cluster_host_info(cluster_id)
        config["localComponents"] = self.topology_cache.get_cluster_local_components(cluster_id)
        config["componentVersionMap"] = self.topology_cache.get_cluster_component_version_map(cluster_id)
        
        # Add host information
        host_info = self.topology_cache.get_current_host_info(cluster_id)
        config.setdefault("agentLevelParams", {})["hostname"] = host_info.get("hostName")
        config["clusterName"] = metadata.clusterLevelParams.cluster_name
        
        # Add service-level parameters if applicable
        self._add_service_params(config, metadata, service_name)
        
        # Add component-level parameters if applicable
        self._add_component_params(config, cluster_id, service_name, component_name)
        
        # Add configuration snapshots
        config.update(configurations)
        
        return config
    
    def _add_service_params(
        self,
        config: Dict[str, Any],
        metadata: Any,
        service_name: Optional[str]
    ) -> None:
        """Add service-level parameters to configuration"""
        if service_name and service_name != "null":
            service_params = metadata.serviceLevelParams.get(service_name)
            if service_params:
                config["serviceLevelParams"] = service_params
                self.telemetry["serv_params"] = True
    
    def _add_component_params(
        self,
        config: Dict[str, Any],
        cluster_id: str,
        service_name: Optional[str],
        component_name: Optional[str]
    ) -> None:
        """Add component-level parameters to configuration"""
        if not component_name or not service_name:
            return
            
        component = self.topology_cache.get_component_info_by_key(cluster_id, service_name, component_name)
        if component is not None:
            config["componentLevelParams"] = component.componentLevelParams
            config["commandParams"] = component.commandParams
            self.telemetry["comp_params"] = True
    
    def _add_global_parameters(self, config: Dict[str, Any]) -> None:
        """Add global configuration parameters"""
        global_params = self.metadata_cache.get_cluster_indepedent_data().clusterLevelParams
        config["cloudLevelParams"] = global_params
        self.telemetry["global_params"] = True
    
    def _add_agent_parameters(self, config: Dict[str, Any]) -> None:
        """Add agent-level parameters to configuration"""
        agent_level = config.setdefault("agentLevelParams", {})
        
        # Network properties
        agent_level["public_hostname"] = self.public_fqdn
        
        # Directory paths
        agent_level["agentCacheDir"] = self.cache_dir
        
        # Execution settings
        agent_level.setdefault("agentConfigParams", {})
        agent_level["agentConfigParams"]["agent"] = {
            "parallel_execution": self.parallel_exec,
            "use_system_proxy_settings": self.system_proxy_setting
        }
    
    def _secure_sensitive_data(self, config: Dict[str, Any]) -> None:
        """Handle sensitive data in configuration"""
        # Implement your security protocols here
        # Example: redact passwords, encrypt secrets, etc.
        
        # Sample placeholder for data security
        if "password" in config:
            config["password"] = "******"
            self.telemetry["redacted"] = True
    
    @property
    def public_fqdn(self) -> str:
        """Get public FQDN for the current host"""
        return hostname.public_hostname(self.config)
    
    def _reset_telemetry(self) -> None:
        """Initialize performance tracking for this build"""
        self.telemetry = {
            "cluster_config": False,
            "global_params": False,
            "serv_params": False,
            "comp_params": False,
            "redacted": False,
            "start_time": 0,
            "duration": 0
        }
    
    def _complete_telemetry(self) -> None:
        """Finalize performance metrics collection"""
        if "start_time" in self.telemetry:
            self.telemetry["duration"] = time.monotonic() - self.telemetry["start_time"]
            logger.debug(f"Configuration build metrics: {self.telemetry}")
    
    def get_build_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for configuration builds"""
        return self.telemetry.copy()


# Exception hierarchy
class ConfigValidationError(Exception):
    """Raised when invalid input parameters are provided"""
    pass

class CacheExpiredError(Exception):
    """Raised when configuration cache is outdated"""
    pass

class ConfigBuildError(Exception):
    """Raised when configuration assembly fails"""
    pass


# Example usage
if __name__ == "__main__":
    import time
    import sys
    
    # Mock dependencies
    class MockConfig:
        def get(self, section, key):
            return "/var/lib/cloud"
        def use_system_proxy_setting(self):
            return True
        def get_parallel_exec_option(self):
            return True
            
    class MockCaches:
        def __init__(self):
            self.clusters = ["cluster1"]
            self.timestamp = int(time.time())
        def __getitem__(self, key):
            return MockCacheData()
            
    class MockCacheData:
        clusterLevelParams = {"cluster_name": "test_cluster"}
        serviceLevelParams = {"HDFS": {"service_param": "value"}}
            
    class MockTopology:
        clusters = ["cluster1"]
        def get_cluster_host_info(self, cluster):
            return {"hosts": ["node1"]}
        def get_cluster_local_components(self, cluster):
            return ["DATANODE"]
        def get_cluster_component_version_map(self, cluster):
            return {"DATANODE": "3.2.1"}
        def get_current_host_info(self, cluster):
            return {"hostName": "node1.example.com"}
        def get_component_info_by_key(self, cluster, service, component):
            return MockComponent() if component == "DATANODE" else None
    
    class MockComponent:
        componentLevelParams = {"heap_size": "1024m"}
        commandParams = {"restart_command": "sudo systemctl restart datanode"}
    
    class MockInitializer:
        config = MockConfig()
        metadata_cache = MockCaches()
        topology_cache = MockTopology()
        host_level_params_cache = MockCaches()
        configurations_cache = MockCaches()
        def get_cluster_indepedent_data(self):
            return MockCacheData()
    
    # Initialize and test builder
    builder = ConfigurationBuilder(MockInitializer())
    
    try:
        # Build configuration for HDFS DATANODE
        config = builder.get_configuration(
            cluster_id="cluster1",
            service_name="HDFS",
            component_name="DATANODE"
        )
        print("Configuration build successful")
        print(f"Agent hostname: {config['agentLevelParams']['hostname']}")
        print(f"Datanode heap: {config['componentLevelParams']['heap_size']}")
    except ConfigBuildError as e:
        print(f"Configuration failed: {str(e)}")
