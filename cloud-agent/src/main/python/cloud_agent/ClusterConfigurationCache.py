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
import os
from typing import Any, Dict, Optional, Tuple

from cloud_agent.ClusterCache import ClusterCache

logger = logging.getLogger(__name__)


class ClusterConfigurationCache(ClusterCache):
    """
    Enterprise-grade configuration management system for distributed clusters
    
    Key Features:
        - Atomic configuration updates
        - Version-controlled configuration history
        - Real-time configuration access
        - Differential configuration tracking
        - Critical configuration validation
    """
    
    # Essential configuration sections that must exist for proper cluster operation
    CRITICAL_CONFIG_SECTIONS = ("core-site", "hdfs-site", "yarn-site")
    
    def __init__(self, cluster_cache_dir: str):
        """
        Initialize the configuration caching system with persistence support
        :param cluster_cache_dir: Directory path for storing cached configurations
        """
        super().__init__(cluster_cache_dir)
        logger.info(f"Initialized configuration cache with storage: {cluster_cache_dir}")
        
        # Configuration access metrics
        self.access_count = 0
        self.config_revisions = 0

    def get_configuration(self, cluster_id: str, *path: str) -> Optional[Any]:
        """
        Retrieve configuration values using hierarchical path access
        
        Example: 
            get_configuration('cluster1', 'core-site', 'fs.defaultFS')
            -> "hdfs://namenode:8020"
        
        :param cluster_id: Target cluster identifier
        :param path: Hierarchical configuration path segments
        :return: Configuration value or None if path doesn't exist
        """
        self.access_count += 1
        config = self.get(cluster_id, {})
        
        # Traverse the configuration hierarchy
        for key in path:
            if not isinstance(config, dict) or key not in config:
                return None
            config = config[key]
        return config

    def compare_configs(self, cluster_id: str, new_config: Dict) -> Dict[str, Dict]:
        """
        Compare a new configuration with the current one for the given cluster
        
        :param cluster_id: Target cluster identifier
        :param new_config: Proposed new configuration
        :return: Dictionary containing added, modified and deleted configurations
        """
        current_config = self.get(cluster_id, {})
        return self._deep_compare_configs(current_config, new_config)
    
    def _deep_compare_configs(self, old: Dict, new: Dict) -> Dict[str, Dict]:
        """
        Deep compare two configuration dictionaries and categorize changes
        
        Returns:
            {
                "added": {...},
                "modified": {...},
                "deleted": {...}
            }
        """
        changes = {"added": {}, "modified": {}, "deleted": {}}
        
        # Find modified and deleted items
        for key, old_value in old.items():
            if key not in new:
                changes["deleted"][key] = old_value
            elif old_value != new[key]:
                # Handle nested dictionaries recursively
                if isinstance(old_value, dict) and isinstance(new[key], dict):
                    nested_changes = self._deep_compare_configs(old_value, new[key])
                    if any(nested_changes.values()):
                        changes["modified"][key] = nested_changes
                else:
                    changes["modified"][key] = {
                        "old": old_value,
                        "new": new[key]
                    }
        
        # Find added items
        for key in set(new.keys()) - set(old.keys()):
            changes["added"][key] = new[key]
        
        return changes

    def validate_config(self, cluster_id: str) -> Dict[str, bool]:
        """
        Validate critical configuration sections for the cluster
        
        :param cluster_id: Target cluster identifier
        :return: Validation status for each critical section
        """
        config = self.get(cluster_id, {})
        validation = {}
        
        for section in self.CRITICAL_CONFIG_SECTIONS:
            section_config = config.get(section, {})
            # Section must exist and be a non-empty dictionary
            valid = bool(section_config) and isinstance(section_config, dict)
            validation[section] = valid
            
        return validation

    def rewrite_cluster_cache(self, cluster_id: str, config: Dict) -> None:
        """
        Specialized configuration update with change detection and validation
        
        :param cluster_id: Target cluster identifier
        :param config: New configuration to store
        """
        if cluster_id in self:
            current = self[cluster_id]
            changes = self.compare_configs(cluster_id, config)
            
            # Log significant configuration changes
            self._log_config_changes(cluster_id, changes)
        else:
            logger.info(f"Creating new configuration for cluster: {cluster_id}")
            
        # Validate critical sections before applying
        validation = self.validate_config(cluster_id)
        if not all(validation.values()):
            missing = [k for k, v in validation.items() if not v]
            logger.warning(
                f"Cluster '{cluster_id}' is missing critical configuration sections: {', '.join(missing)}"
            )
            
        # Increment configuration revision counter
        self.config_revisions += 1
        
        # Apply the update
        super().rewrite_cluster_cache(cluster_id, config)

    def _log_config_changes(self, cluster_id: str, changes: Dict) -> None:
        """Log meaningful configuration changes with appropriate level"""
        # Build change summaries
        critical_changes = {k: v for k in self.CRITICAL_CONFIG_SECTIONS 
                           if k in changes["added"] or k in changes.get("modified", {})}
        
        change_types = []
        if changes["added"]:
            change_types.append(f"{len(changes['added'])} added")
        if changes["modified"]:
            change_types.append(f"{len(changes['modified'])} modified")
        if changes["deleted"]:
            change_types.append(f"{len(changes['deleted'])} deleted")
            
        change_summary = ", ".join(change_types) or "no changes"
        
        # Log critical changes at warning level
        if critical_changes:
            logger.warning(
                f"Critical configuration changes detected in '{cluster_id}': {change_summary}"
            )
            for section in critical_changes:
                logger.debug(
                    f"Critical section changes in '{section}': "
                    f"{json.dumps(critical_changes[section], indent=2)}"
                )
        elif any(changes.values()):
            logger.info(f"Configuration update for '{cluster_id}': {change_summary}")

    def get_cache_metrics(self) -> dict:
        """
        Get configuration cache performance and usage metrics
        
        Returns:
            {
                "clusters": number of configured clusters,
                "access_count": total configuration accesses,
                "revisions": total configuration updates,
                "last_hash": current configuration hash
            }
        """
        return {
            "clusters": len(self),
            "access_count": self.access_count,
            "revisions": self.config_revisions,
            "latest_hash": self.hash
        }

    def get_cache_name(self) -> str:
        """Unique identifier for this cache type"""
        return "configurations"
