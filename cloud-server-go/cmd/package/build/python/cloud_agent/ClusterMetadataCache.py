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
from typing import Any, Dict

from cloud_agent.ClusterCache import ClusterCache

logger = logging.getLogger(__name__)


class ClusterMetadataCache(ClusterCache):
    """
    Advanced cluster metadata management system providing:
        - Centralized metadata storage for cluster configurations
        - Agent configuration synchronization
        - Cluster metadata version control
        - Selective cluster deletion with safety checks
        - Automated agent configuration updates
    
    This cache stores critical metadata objects:
        - Cluster topologies
        - Service configurations
        - Agent-level settings
        - Security descriptors
    """
    
    COMMON_CLUSTER_ID = "-1"  # Special ID for common cluster data
    
    def __init__(self, cluster_cache_dir: str, config: Any):
        """
        Initialize the metadata caching system with configuration integration
        :param cluster_cache_dir: Directory for persistent metadata storage
        :param config: Configuration object for agent settings
        """
        self.config = config
        super().__init__(cluster_cache_dir)
        logger.info(f"Initialized metadata cache at {cluster_cache_dir}")
        
        # Additional metadata handling initialization
        self._update_agent_config_on_init()

    def _update_agent_config_on_init(self):
        """Apply agent configuration from metadata if available"""
        try:
            agent_config = self.get_agent_configuration()
            if agent_config:
                self.config.update_configuration_from_metadata(agent_config)
                logger.info("Agent configuration updated from metadata cache")
        except Exception as e:
            logger.warning(f"Initial agent config update failed: {str(e)}")

    def on_cache_update(self) -> None:
        """Trigger point for metadata cache updates"""
        super().on_cache_update()
        
        try:
            # Always attempt to update agent config from common cluster data
            agent_config = self.get_agent_configuration()
            if agent_config:
                self.config.update_configuration_from_metadata(agent_config)
                logger.debug("Agent configuration updated from metadata")
        except KeyError:
            logger.warning("Agent config metadata not found in common cluster data")
        except Exception as e:
            logger.error(f"Agent config update failed: {str(e)}")

    def get_agent_configuration(self) -> Dict:
        """Retrieve agent-specific configuration from metadata"""
        try:
            return self[self.COMMON_CLUSTER_ID]["agentConfigs"]
        except KeyError:
            logger.debug("Agent configuration not found in metadata cache")
            return {}

    def get_cluster_metadata(self, cluster_id: str) -> Dict:
        """Retrieve comprehensive metadata for a specific cluster"""
        return self.get(cluster_id, {})
    
    def get_service_metadata(self, cluster_id: str, service_name: str) -> Dict:
        """Extract service-specific metadata from cluster data"""
        cluster_meta = self.get_cluster_metadata(cluster_id)
        
        # Iterate through services hierarchy
        services = cluster_meta.get("services", {})
        for service in services.values():
            if service.get("serviceName") == service_name:
                return service
        
        return {}
    
    def get_component_metadata(self, cluster_id: str, service_name: str, component_name: str) -> Dict:
        """Locate specific component metadata within service structure"""
        service_meta = self.get_service_metadata(cluster_id, service_name)
        
        # Search components hierarchy
        components = service_meta.get("components", {})
        for comp in components.values():
            if comp.get("componentName") == component_name:
                return comp
        
        return {}

    def cache_delete(self, clusters_to_delete: Dict, cache_hash: str) -> None:
        """
        Delete cluster metadata with safety checks
        
        :param clusters_to_delete: Dictionary of clusters to delete (empty dict per cluster for deletion)
        :param cache_hash: Version hash for the cache after deletion
        """
        mutable_dict = self._get_mutable_copy()
        
        # Prevent deleting the common cluster metadata
        if self.COMMON_CLUSTER_ID in clusters_to_delete:
            logger.error(f"Cannot delete common cluster metadata ({self.COMMON_CLUSTER_ID})")
            raise PermissionError("Common cluster metadata cannot be deleted")
        
        for cluster_id, deletion_data in clusters_to_delete.items():
            # Safety check: only empty deletion operations are allowed
            if deletion_data != {}:
                logger.error(f"Attempted partial delete on cluster {cluster_id}: {deletion_data}")
                raise ValueError("Partial cluster metadata deletion not supported")
            
            if cluster_id in mutable_dict:
                logger.info(f"Deleting metadata for cluster: {cluster_id}")
                del mutable_dict[cluster_id]
            else:
                logger.warning(f"Cluster {cluster_id} not found in metadata cache for deletion")
        
        # Apply changes and persist new state
        self.rewrite_cache(mutable_dict, cache_hash)
        logger.info(f"Deleted {len(clusters_to_delete)} cluster metadata sets")
    
    def get_metadata_version(self) -> str:
        """Retrieve the current metadata version hash"""
        return self.hash or "UNKNOWN"
    
    def get_cluster_list(self) -> list:
        """List all clusters currently in metadata cache"""
        return [cid for cid in self.keys() if cid != self.COMMON_CLUSTER_ID]
    
    def get_cache_health(self) -> dict:
        """Get metadata cache health report"""
        return {
            "clusters": len(self),
            "common_data": bool(self.get(self.COMMON_CLUSTER_ID, {})),
            "agent_config": bool(self.get_agent_configuration()),
            "current_hash": self.get_metadata_version()
        }

    def get_cache_name(self) -> str:
        """Cache identity for file persistence"""
        return "metadata"
    
    def get_critical_paths(self) -> list:
        """List critical metadata paths for validation"""
        common_agent_config = self.get_agent_configuration()
        return [
            f"/{self.COMMON_CLUSTER_ID}/agentConfigs",
            f"/{self.COMMON_CLUSTER_ID}/security/keys"
        ]

    def validate_cache(self) -> list:
        """Perform basic integrity validation of cached metadata"""
        issues = []
        
        # Check common cluster metadata
        if self.COMMON_CLUSTER_ID not in self:
            issues.append("Common cluster data missing")
        
        # Check agent config existence
        if not self.get_agent_configuration():
            issues.append("Agent configuration missing")
        
        return issues
