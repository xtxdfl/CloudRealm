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
from typing import Dict, List, Optional, Tuple, Union

from ClusterCache import ClusterCache

logger = logging.getLogger(__name__)


class AlertDefinitionIndex:
    """Efficient index for alert definitions using dictionary lookup"""
    def __init__(self, cluster_id: str):
        self.cluster_id = cluster_id
        self.id_to_index: Dict[str, int] = {}
        self.last_update = 0

    def update(self, definitions: List[dict]) -> None:
        """Rebuild index for current definitions"""
        self.id_to_index.clear()
        for idx, definition in enumerate(definitions):
            self.id_to_index[definition["definitionId"]] = idx
        self.last_update += 1

    def get_index(self, alert_id: str) -> Optional[int]:
        """Get index for alert ID with O(1) lookup"""
        return self.id_to_index.get(alert_id, None)


class ClusterAlertDefinitionsCache(ClusterCache):
    """
    Advanced cluster alert definition cache with:
        - Indexed O(1) access to definitions
        - Atomic update operations
        - Type-safe operations

    This cache maintains both memory and disk copies of cluster alert definitions
    for quick access to topology properties and alert configurations.
    """

    def __init__(self, cluster_cache_dir: str):
        """
        Initialize the alert definition cache
        :param cluster_cache_dir: Directory to store cache files
        """
        super().__init__(cluster_cache_dir)
        self.indexes: Dict[str, AlertDefinitionIndex] = {}
        self._initialize_indexes()

    def _initialize_indexes(self) -> None:
        """Create indexes from loaded cache"""
        cache = self._get_mutable_copy()
        for cluster_id, cluster_data in cache.items():
            self._create_index(cluster_id, cluster_data.get("alertDefinitions", []))

    def _create_index(self, cluster_id: str, definitions: List[dict]) -> None:
        """Create or update index for a cluster"""
        if cluster_id not in self.indexes:
            self.indexes[cluster_id] = AlertDefinitionIndex(cluster_id)
        self.indexes[cluster_id].update(definitions)

    def get_alert_index(self, cluster_id: str, alert_id: str) -> Optional[int]:
        """Get index of alert definition with O(1) complexity"""
        if cluster_id in self.indexes:
            return self.indexes[cluster_id].get_index(alert_id)
        return None

    def get_cluster_alert_definitions(self, cluster_id: str) -> List[dict]:
        """Get alert definitions for a specific cluster"""
        cache = self._clone_cache()
        return cache.get(cluster_id, {}).get("alertDefinitions", []).copy()

    def cache_update(self, updates: Dict[str, dict], cache_hash: str) -> Tuple[int, int]:
        """
        Update cache with new alert definitions
        Returns: (number of added items, number of updated items)
        """
        cache = self._get_mutable_copy()
        added, updated = 0, 0

        for cluster_id, cluster_data in updates.items():
            # New cluster initialization
            if cluster_id not in cache:
                cache[cluster_id] = cluster_data
                self._create_index(cluster_id, cluster_data.get("alertDefinitions", []))
                added += len(cluster_data.get("alertDefinitions", []))
                continue

            # Existing cluster update
            cluster_cache = cache[cluster_id]
            index = self.indexes.get(cluster_id)
            
            # Non-definition properties update
            for key, value in cluster_data.items():
                if key != "alertDefinitions":
                    cluster_cache[key] = value
            
            # Alert definitions processing
            if "alertDefinitions" in cluster_data:
                existing_defs = cluster_cache.setdefault("alertDefinitions", [])
                
                for alert_def in cluster_data["alertDefinitions"]:
                    alert_id = alert_def["definitionId"]
                    idx = index.get_index(alert_id) if index else None
                    
                    if idx is None:  # New alert
                        existing_defs.append(alert_def)
                        added += 1
                    else:  # Existing alert update
                        existing_defs[idx] = alert_def
                        updated += 1
                
                # Rebuild index after updates
                self._create_index(cluster_id, existing_defs)

        # Persist changes
        self.rewrite_cache(cache, cache_hash)
        logger.info(
            f"Cache updated: {added} alerts added, {updated} alerts updated"
        )
        return added, updated

    def cache_delete(self, deletions: Dict[str, dict], cache_hash: str) -> int:
        """
        Remove definitions from cache
        Returns: Number of items deleted
        """
        cache = self._get_mutable_copy()
        deleted_count = 0
        clusters_to_remove = []

        for cluster_id, cluster_data in deletions.items():
            # Skip non-existent clusters
            if cluster_id not in cache:
                logger.warning(
                    f"Cannot delete definitions for non-existent cluster: {cluster_id}"
                )
                continue

            cluster_entry = cache[cluster_id]
            
            # Full cluster deletion requested
            if not cluster_data or cluster_data.get("__delete_cluster", False):
                del cache[cluster_id]
                if cluster_id in self.indexes:
                    del self.indexes[cluster_id]
                clusters_to_remove.append(cluster_id)
                deleted_count += 1  # Count cluster as one deletion
                continue

            # Alert definitions deletion
            if "alertDefinitions" in cluster_data and "alertDefinitions" in cluster_entry:
                alerts_to_delete = cluster_data["alertDefinitions"]
                existing_alerts = cluster_entry["alertDefinitions"]
                index = self.indexes.get(cluster_id, AlertDefinitionIndex(cluster_id))
                
                # Collect indices of alerts to delete (reverse order)
                indices_to_delete = sorted([
                    idx for alert in alerts_to_delete
                    if (idx := index.get_index(alert["definitionId"])) is not None
                ], reverse=True)
                
                # Remove from end to beginning to keep indices valid
                for idx in indices_to_delete:
                    del existing_alerts[idx]
                    deleted_count += 1
                
                # Update index after deletions
                self._create_index(cluster_id, existing_alerts)

        # Persist changes
        self.rewrite_cache(cache, cache_hash)
        logger.info(
            f"Cache deletion completed: "
            f"{deleted_count} items deleted, {len(clusters_to_remove)} clusters removed"
        )
        return deleted_count

    def get_cache_name(self) -> str:
        return "alert_definitions"

    def get_cache_stats(self) -> dict:
        """Get statistics about current cache state"""
        counts = []
        alert_totals = 0
        
        for cluster_id, cluster_data in self.cache.items():
            cluster_count = len(cluster_data.get("alertDefinitions", []))
            alert_totals += cluster_count
            counts.append((cluster_id, cluster_count))
        
        return {
            "cluster_count": len(self.cache),
            "total_alerts": alert_totals,
            "clusters": counts
        }
