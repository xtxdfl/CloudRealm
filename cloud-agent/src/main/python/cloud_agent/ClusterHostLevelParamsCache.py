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
import json
from typing import Any, Dict, Optional

from cloud_agent.ClusterCache import ClusterCache

logger = logging.getLogger(__name__)


class ClusterHostLevelParamsCache(ClusterCache):
    """
    Enterprise-grade host-level parameters caching system for distributed clusters
    
    Key Features:
        - Per-host parameter management with cluster-level organization
        - Host-specific parameter version control
        - Parameter validation and transformation
        - Operational metrics collection and reporting
        - Differential parameter change detection
    
    This cache stores parameters that:
        - Vary by host within the same cluster
        - Are used in execution and status commands
        - Require real-time access during operation
    """
    
    # Parameters that are required for all hosts in a cluster
    REQUIRE_HOST_PARAMS = ("host_name", "ip_address", "rack_id", "os_type")
    HOST_LEVEL_KEYS = REQUIRE_HOST_PARAMS + ("tags", "attributes")
    
    def __init__(self, cluster_cache_dir: str):
        """
        Initialize the host-level parameters caching system
        :param cluster_cache_dir: Directory for persistent parameter storage
        """
        super().__init__(cluster_cache_dir)
        logger.info(f"Initialized host-level params cache at {cluster_cache_dir}")
        
        # Performance metrics
        self.access_count = 0
        self.param_updates = 0

    def get_host_params(self, cluster_id: str, host_name: str) -> Dict[str, Any]:
        """
        Retrieve all parameters for a specific host in a cluster
        
        :param cluster_id: Target cluster identifier
        :param host_name: Name of the target host
        :return: Dictionary of host-level parameters
        """
        self.access_count += 1
        cluster_params = self.get(cluster_id, {})
        return cluster_params.get(host_name, {}).copy()

    def get_param_value(
        self, 
        cluster_id: str, 
        host_name: str, 
        param_name: str, 
        default: Any = None
    ) -> Any:
        """
        Retrieve a specific parameter value for a host in a cluster
        
        :param cluster_id: Target cluster identifier
        :param host_name: Name of the target host
        :param param_name: Name of parameter to retrieve
        :param default: Default value if parameter not found
        :return: Requested parameter value or default
        """
        host_params = self.get_host_params(cluster_id, host_name)
        return host_params.get(param_name, default)

    def validate_host_params(self, cluster_id: str) -> Dict[str, Dict[str, bool]]:
        """
        Validate host-level parameters for all hosts in a cluster
        
        :param cluster_id: Target cluster identifier
        :return: Dictionary of validation results per host
        """
        cluster_params = self.get(cluster_id, {})
        validation = {}
        
        for host_name, params in cluster_params.items():
            host_validation = {}
            
            for param in self.REQUIRE_HOST_PARAMS:
                present = param in params and bool(params[param])
                host_validation[param] = present
                
            validation[host_name] = host_validation
            
        return validation

    def diff_param_changes(
        self, 
        cluster_id: str, 
        new_params: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Dict]]:
        """
        Detect parameter changes between current and proposed state
        
        :param cluster_id: Target cluster identifier
        :param new_params: Proposed new parameters for hosts
        :return: Dictionary of changes per host
        """
        current_params = self.get(cluster_id, {})
        changes = {"added_hosts": {}, "removed_hosts": {}, "updated_hosts": {}}
        
        # Detect removed hosts
        removed = set(current_params.keys()) - set(new_params.keys())
        for host in removed:
            changes["removed_hosts"][host] = current_params[host]
        
        # Detect added hosts
        added = set(new_params.keys()) - set(current_params.keys())
        for host in added:
            changes["added_hosts"][host] = new_params[host]
        
        # Detect parameter changes for existing hosts
        for host in set(current_params.keys()) & set(new_params.keys()):
            host_changes = self._diff_host_params(
                current_params[host], 
                new_params[host]
            )
            if host_changes:
                changes["updated_hosts"][host] = host_changes
                
        return changes

    def _diff_host_params(
        self, 
        current: Dict[str, Any], 
        new: Dict[str, Any]
    ) -> Dict[str, Dict]:
        """
        Compare host-level parameters for a single host
        """
        changes = {"added": {}, "modified": {}, "removed": {}}
        
        # Check for removed parameters
        for key in set(current.keys()) - set(new.keys()):
            changes["removed"][key] = current[key]
        
        # Check for added or modified parameters
        for key in new:
            if key not in current:
                changes["added"][key] = new[key]
            elif current[key] != new[key]:
                changes["modified"][key] = {
                    "old": current[key],
                    "new": new[key]
                }
                
        return changes

    def rewrite_cluster_cache(self, cluster_id: str, cluster_params: Dict) -> None:
        """
        Specialized host-level parameter update with validation and change tracking
        
        :param cluster_id: Target cluster identifier
        :param cluster_params: New host-level parameters for the cluster
        """
        self.param_updates += 1
        
        # Perform validation before update
        validation = self.validate_host_params(cluster_id)
        
        # Log any missing required parameters
        for host, param_status in validation.items():
            missing = [k for k, v in param_status.items() if not v]
            if missing:
                logger.warning(
                    f"Host '{host}' in cluster '{cluster_id}' "
                    f"missing required params: {', '.join(missing)}"
                )
        
        # Apply update through super class
        super().rewrite_cluster_cache(cluster_id, cluster_params)
        
        # Log update summary
        hosts_count = len(cluster_params)
        params_count = sum(len(p) for p in cluster_params.values())
        logger.info(
            f"Updated host params for cluster '{cluster_id}': "
            f"{hosts_count} hosts, {params_count} parameters"
        )

    def get_host_metadata(self, cluster_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract essential host metadata from stored parameters
        
        :param cluster_id: Target cluster identifier
        :return: Dictionary of host metadata by hostname
        """
        cluster_params = self.get(cluster_id, {})
        metadata = {}
        
        for host, params in cluster_params.items():
            host_meta = {
                key: params.get(key, None)
                for key in self.HOST_LEVEL_KEYS
            }
            metadata[host] = host_meta
            
        return metadata

    def generate_inventory_report(self, cluster_id: str) -> Dict:
        """
        Generate cluster inventory report based on host-level parameters
        
        :param cluster_id: Target cluster identifier
        :return: Dictionary with host inventory information
        """
        report = {
            "host_count": 0,
            "os_distribution": {},
            "rack_distribution": {},
            "component_distribution": {},
            "host_names": []
        }
        
        cluster_params = self.get(cluster_id, {})
        report["host_count"] = len(cluster_params)
        
        for host, params in cluster_params.items():
            # Track host names
            report["host_names"].append(host)
            
            # Track OS types
            os_type = params.get("os_type", "UNKNOWN")
            report["os_distribution"][os_type] = report["os_distribution"].get(os_type, 0) + 1
            
            # Track rack locations
            rack_id = params.get("rack_id", "/UNKNOWN_RACK")
            report["rack_distribution"][rack_id] = report["rack_distribution"].get(rack_id, 0) + 1
            
            # Track components
            components = params.get("components", [])
            if isinstance(components, str):
                components = [components]
            for comp in components:
                report["component_distribution"][comp] = report["component_distribution"].get(comp, 0) + 1
                
        return report

    def get_cache_metrics(self) -> Dict:
        """
        Retrieve cache performance metrics
        """
        return {
            "clusters": len(self),
            "param_accesses": self.access_count,
            "param_updates": self.param_updates,
            "last_hash": self.hash
        }

    def get_cache_name(self) -> str:
        """Unique identifier for this cache type"""
        return "host_level_params"
