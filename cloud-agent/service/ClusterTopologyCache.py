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
from collections import defaultdict
from typing import Any, Dict, List, Optional

from cloud_agent import hostname
from ClusterCache import ClusterCache
from Utils import ImmutableDictionary, synchronized

logger = logging.getLogger(__name__)
topology_update_lock = threading.RLock()


class ClusterTopologyCache(ClusterCache):
    """
    Advanced cluster topology caching system providing:
        - Distributed topology management
        - Host and component discovery services
        - Service mapping and resolution
        - Realtime topology change handling
        - Optimized pathfinding for cluster operations
    
    This cache stores critical infrastructure data:
        - Host definitions and metadata
        - Component assignments and configurations
        - Service-host mappings
        - Component version tracking
    """
    
    def __init__(self, cluster_cache_dir: str, config: Any):
        """
        Initialize the topology caching system
        :param cluster_cache_dir: Directory for persistent topology storage
        :param config: Configuration object for agent settings
        """
        # Initialization should always call super first
        super().__init__(cluster_cache_dir)
        
        # Core topology structures
        self.hostname = hostname.hostname(config)
        self.hosts_by_id = ImmutableDictionary({})
        self.components_by_key = ImmutableDictionary({})
        
        # Runtime state tracking
        self.current_host_ids = {}
        self.local_components = {}
        self.component_versions = {}
        self.cluster_host_info_cache = {}   # Separate per-cluster cache
        
        logger.info(f"Topology cache initialized for host: {self.hostname}")

    def get_cache_name(self) -> str:
        """Cache identity for file persistence"""
        return "topology"

    @synchronized(topology_update_lock)
    def on_cache_update(self) -> None:
        """Rebuild internal structures after topology updates"""
        # Reset runtime caches
        self.cluster_host_info_cache = {}
        
        # Initialize data structures
        hosts_index = defaultdict(lambda: {})
        components_index = defaultdict(lambda: {})
        local_components = defaultdict(list)
        component_versions = defaultdict(lambda: defaultdict(lambda: ""))
        current_host_ids = {}
        
        # Process all clusters
        for cluster_id, cluster_topology in self.items():
            # Build hosts index by ID
            if "hosts" in cluster_topology:
                for host in cluster_topology.hosts:
                    hosts_index[cluster_id][host.hostId] = host
                    
                    # Identify current host in cluster
                    if host.hostName == self.hostname:
                        current_host_ids[cluster_id] = host.hostId
            
            # Build components index
            if "components" in cluster_topology:
                for comp in cluster_topology.components:
                    service_comp_key = f"{comp.serviceName}/{comp.componentName}"
                    components_index[cluster_id][service_comp_key] = comp
                    
                    # Track component versions
                    if "version" in comp.commandParams:
                        comp_version = comp.commandParams.version
                        comp_id = f"{comp.serviceName}.{comp.componentName}"
                        component_versions[cluster_id][comp_id] = comp_version
            
            # Find components on current host
            if cluster_id in current_host_ids:
                current_host_id = current_host_ids[cluster_id]
                cluster_components = cluster_topology.get("components", [])
                
                for comp in cluster_components:
                    if "hostIds" in comp and current_host_id in comp.hostIds:
                        local_components[cluster_id].append(comp.componentName)
        
        # Update thread-safe structures
        self.hosts_by_id = ImmutableDictionary(hosts_index)
        self.components_by_key = ImmutableDictionary(components_index)
        self.local_components = local_components
        self.component_versions = component_versions
        self.current_host_ids = current_host_ids
        
        logger.debug("Topology indices rebuilt")

    def _build_cluster_host_info(self, cluster_id: str) -> dict:
        """Construct clusterHostInfo structure for a specific cluster"""
        cluster_host_info = defaultdict(list)
        
        # Build component-based host lists
        components = self.get(cluster_id, {}).get("components", [])
        for comp in components:
            comp_name = comp.componentName.lower() + "_hosts"
            for host_id in comp.get("hostIds", []):
                if host := self.hosts_by_id[cluster_id].get(host_id):
                    cluster_host_info[comp_name].append(host.hostName)
        
        # Build aggregate host information
        all_hosts = []
        all_racks = []
        all_ips = []
        
        for host in self.get(cluster_id, {}).get("hosts", []):
            all_hosts.append(host.hostName)
            all_racks.append(host.rackName)
            all_ips.append(host.ipv4)
        
        cluster_host_info["all_hosts"] = all_hosts
        cluster_host_info["all_racks"] = all_racks
        cluster_host_info["all_ipv4_ips"] = all_ips
        
        return cluster_host_info

    @synchronized(topology_update_lock)
    def get_cluster_host_info(self, cluster_id: str) -> dict:
        """
        Get dictionary used in commands as clusterHostInfo
        :param cluster_id: Target cluster identifier
        :return: Structured host information dictionary
        """
        # Use cached version if available
        if cluster_id in self.cluster_host_info_cache:
            return self.cluster_host_info_cache[cluster_id]
        
        # Build and cache the structure
        cluster_info = self._build_cluster_host_info(cluster_id)
        self.cluster_host_info_cache[cluster_id] = cluster_info
        return cluster_info

    @synchronized(topology_update_lock)
    def get_component_info(self, cluster_id: str, service_name: str, component_name: str) -> Optional[dict]:
        """
        Retrieve component information by service and name
        :param cluster_id: Target cluster identifier
        :param service_name: Service name
        :param component_name: Component name
        :return: Component dictionary or None if not found
        """
        key = f"{service_name}/{component_name}"
        return self.components_by_key[cluster_id].get(key)

    @synchronized(topology_update_lock)
    def get_local_components(self, cluster_id: str) -> List[str]:
        """
        Get components running on this host in a cluster
        :param cluster_id: Target cluster identifier
        :return: List of component names
        """
        return self.local_components.get(cluster_id, [])

    @synchronized(topology_update_lock)
    def get_component_versions(self, cluster_id: str) -> dict:
        """
        Get component version map for a cluster
        :param cluster_id: Target cluster identifier
        :return: Dictionary of component version strings
        """
        return self.component_versions.get(cluster_id, {}).copy()

    @synchronized(topology_update_lock)
    def get_host_by_id(self, cluster_id: str, host_id: str) -> Optional[dict]:
        """
        Retrieve host information by ID
        :param cluster_id: Target cluster identifier
        :param host_id: Host identifier
        :return: Host dictionary or None if not found
        """
        return self.hosts_by_id[cluster_id].get(host_id)

    @synchronized(topology_update_lock)
    def get_current_host(self, cluster_id: str) -> Optional[dict]:
        """
        Get current host information in a cluster
        :param cluster_id: Target cluster identifier
        :return: Host dictionary or None if not part of cluster
        """
        if host_id := self.current_host_ids.get(cluster_id):
            return self.get_host_by_id(cluster_id, host_id)
        return None

    @synchronized(topology_update_lock)
    def get_cluster_ids_with_host(self) -> List[str]:
        """Get list of cluster IDs where this host participates"""
        return [cid for cid, hid in self.current_host_ids.items() if hid is not None]

    # ================== UPDATE OPERATIONS ================== #

    @staticmethod
    def _find_host_by_id(hosts: list, host_id: str) -> Optional[dict]:
        """Locate host by ID in host list"""
        return next((h for h in hosts if h.get("hostId") == host_id), None)

    @staticmethod
    def _find_component(components: list, service: str, comp_name: str) -> Optional[dict]:
        """Locate component by service and component name"""
        return next(
            (c for c in components 
             if c.get("serviceName") == service and c.get("componentName") == comp_name),
            None
        )

    @synchronized(topology_update_lock)
    def cache_update(self, updates: Dict[str, Dict], cache_hash: str) -> None:
        """
        Apply topology updates with advanced conflict resolution
        :param updates: Dictionary of topology changes by cluster ID
        :param cache_hash: New version hash for validation
        """
        mutable_dict = self._get_mutable_copy()
        
        # Process updates per cluster
        for cluster_id, cluster_updates in updates.items():
            # Create new cluster if needed
            if cluster_id not in mutable_dict:
                mutable_dict[cluster_id] = cluster_updates
                logger.info(f"Added new cluster topology: {cluster_id}")
                continue
            
            # Apply host updates
            if "hosts" in cluster_updates:
                cluster_hosts = mutable_dict[cluster_id].setdefault("hosts", [])
                
                for host_update in cluster_updates["hosts"]:
                    host_id = host_update["hostId"]
                    existing_host = self._find_host_by_id(cluster_hosts, host_id)
                    
                    if existing_host:
                        # Merge updates with existing host entry
                        existing_host.update(host_update)
                        logger.debug(f"Updated host: {host_id} in cluster: {cluster_id}")
                    else:
                        # Add new host entry
                        cluster_hosts.append(host_update)
                        logger.info(f"Added new host: {host_id} to cluster: {cluster_id}")
            
            # Apply component updates
            if "components" in cluster_updates:
                cluster_comps = mutable_dict[cluster_id].setdefault("components", [])
                
                for comp_update in cluster_updates["components"]:
                    service_name = comp_update["serviceName"]
                    comp_name = comp_update["componentName"]
                    
                    # Find existing component
                    existing_comp = self._find_component(
                        cluster_comps, service_name, comp_name
                    )
                    
                    if existing_comp:
                        # Handle host ID updates specially
                        if "hostIds" in comp_update:
                            current_ids = set(existing_comp.get("hostIds", []))
                            new_ids = set(comp_update["hostIds"])
                            
                            # Merge host assignments
                            comp_update["hostIds"] = list(current_ids | new_ids)
                        
                        # Update component properties
                        existing_comp.update(comp_update)
                        logger.debug(f"Updated component: {service_name}/{comp_name} in {cluster_id}")
                    else:
                        # Add new component
                        cluster_comps.append(comp_update)
                        logger.info(f"Added new component: {service_name}/{comp_name} to {cluster_id}")
        
        # Persist updated topology
        self.rewrite_cache(mutable_dict, cache_hash)
        logger.info(f"Topology updated with hash: {cache_hash[:8]}")

    # ================== DELETE OPERATIONS ================== #

    @synchronized(topology_update_lock)
    def cache_delete(self, deletions: Dict[str, Dict], cache_hash: str) -> int:
        """
        Process topological deletions with atomic operation sequencing
        :param deletions: Dictionary of delete operations by cluster
        :param cache_hash: New version hash after deletion
        :return: Number of elements deleted
        """
        mutable_dict = self._get_mutable_copy()
        cluster_deletions = []
        delete_count = 0
        
        for cluster_id, cluster_dels in deletions.items():
            # Check cluster exists
            if cluster_id not in mutable_dict:
                logger.warning(f"Delete operation: Cluster {cluster_id} not found")
                continue
            
            current_cluster = mutable_dict[cluster_id]
            
            # Full cluster deletion
            if not cluster_dels:
                del mutable_dict[cluster_id]
                cluster_deletions.append(cluster_id)
                logger.info(f"Scheduled cluster deletion: {cluster_id}")
                delete_count += 1
                continue
            
            # Process host deletions
            if "hosts" in cluster_dels:
                cluster_hosts = current_cluster.get("hosts", [])
                
                for host_del in cluster_dels["hosts"]:
                    host_id = host_del["hostId"]
                    host_ref = self._find_host_by_id(cluster_hosts, host_id)
                    
                    if host_ref:
                        # Remove host from cluster
                        cluster_hosts[:] = [h for h in cluster_hosts if h != host_ref]
                        delete_count += 1
                        logger.info(f"Deleted host: {host_id} from {cluster_id}")
                    else:
                        logger.warning(f"Host not found: {host_id} in {cluster_id}")
            
            # Process component hosts
            if "components" in cluster_dels:
                cluster_comps = current_cluster.get("components", [])
                
                for comp_del in cluster_dels["components"]:
                    service_name = comp_del["serviceName"]
                    comp_name = comp_del["componentName"]
                    comp_ref = self._find_component(cluster_comps, service_name, comp_name)
                    
                    if comp_ref:
                        # Process host removals from component
                        if "hostIds" in comp_del:
                            host_ids = comp_ref.get("hostIds", [])
                            removal_ids = set(comp_del["hostIds"])
                            
                            # Update host assignments
                            comp_ref["hostIds"] = [id for id in host_ids if id not in removal_ids]
                            delete_count += len(removal_ids)
                            logger.info(f"Removed {len(removal_ids)} hosts from {service_name}/{comp_name}")
                        
                        # Remove component if empty
                        if not comp_ref.get("hostIds", []):
                            cluster_comps[:] = [c for c in cluster_comps if c != comp_ref]
                            delete_count += 1
                            logger.info(f"Deleted component: {service_name}/{comp_name}")
                    else:
                        logger.warning(f"Component not found: {service_name}/{comp_name}")
        
        # Apply cluster-level deletions
        for cluster_id in cluster_deletions:
            if cluster_id in mutable_dict:
                del mutable_dict[cluster_id]
        
        # Persist updated topology
        self.rewrite_cache(mutable_dict, cache_hash)
        logger.info(f"Topology deleted {delete_count} elements, new hash: {cache_hash[:8]}")
        return delete_count

    # ================== DIAGNOSTIC UTILITIES ================== #

    def get_topology_summary(self, cluster_id: str) -> dict:
        """Generate summary report for cluster topology"""
        hosts = self.get(cluster_id, {}).get("hosts", [])
        components = self.get(cluster_id, {}).get("components", [])
        
        host_count = len(hosts)
        comp_count = len(components)
        
        unique_racks = len({h.get("rackName") for h in hosts})
        service_dist = defaultdict(int)
        for comp in components:
            service_dist[comp.get("serviceName")] += 1
        
        return {
            "hosts": host_count,
            "components": comp_count,
            "racks": unique_racks,
            "services": dict(service_dist),
            "versions": self.get_component_versions(cluster_id),
            "local_components": self.get_local_components(cluster_id)
        }
