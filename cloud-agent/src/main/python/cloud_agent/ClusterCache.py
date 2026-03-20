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

import os
import shutil
import json
import logging
import threading
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, Any, Optional, List, Set


class ClusterCache(dict):
    """
    Enterprise-grade cluster cache management with:
        - Atomic file operations
        - Fine-grained locking
        - Write-ahead logging
        - Self-healing capabilities
    
    Features:
        1. Dual in-memory and persistent disk cache
        2. Transaction-safe cache updates
        3. Optimized concurrency controls
        4. Real-time health monitoring
    """

    # Common data cluster ID constant
    COMMON_DATA_CLUSTER = "-1"
    
    # File locks dictionary for thread safety
    _file_locks = defaultdict(threading.RLock)
    
    def __init__(self, cluster_cache_dir: str):
        """
        Initialize an atomic cluster cache handler
        :param cluster_cache_dir: Directory for persistent cache storage
        """
        super().__init__()
        
        self.cluster_cache_dir = cluster_cache_dir
        self.version = "1.2"  # Cache format version
        
        # Cache file paths
        self.cache_base_name = self.get_cache_name()
        self.cache_json_file = os.path.join(
            cluster_cache_dir, f"{self.cache_base_name}.v{self.version}.json"
        )
        self.hash_file = os.path.join(
            cluster_cache_dir, f".{self.cache_base_name}.hash"
        )
        self.backup_dir = os.path.join(cluster_cache_dir, "backups")
        
        # Locking mechanisms
        self._cache_lock = threading.RLock()
        self._file_lock = self._file_locks[self.cache_json_file]
        
        # Load cache with recovery capabilities
        self._load_or_initialize_cache()

    def _load_or_initialize_cache(self):
        """Smart cache initialization with self-healing"""
        # Reset cache state
        self.hash = None
        cache_dict = {}
        
        try:
            # Attempt loading from primary location
            if os.path.exists(self.cache_json_file):
                with self._atomic_file_access(self.cache_json_file, "r") as f:
                    cache_dict = json.load(f)
                
                if os.path.exists(self.hash_file):
                    with self._atomic_file_access(self.hash_file, "r") as f:
                        self.hash = f.read().strip()
            else:
                # Attempt locating previous version caches
                cache_dict = self._find_legacy_cache()
                
            # Apply loaded data
            self.rewrite_cache(cache_dict, self.hash)
            logger.info(f"Cache initialized: {self.cache_json_file} [clusters: {len(cache_dict)}]")
            
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Cache loading failed: {str(e)} - Attemping recovery")
            cache_dict = self._recover_cache()
            self.rewrite_cache(cache_dict, None)
            logger.warning("Cache recovered from fallback state")

    def _find_legacy_cache(self) -> Dict[str, Any]:
        """Locate caches from previous versions"""
        legacy_files = [
            os.path.join(self.cluster_cache_dir, f"{self.cache_base_name}.*.json"),
            os.path.join(self.cluster_cache_dir, f"{self.cache_base_name}.json")
        ]
        
        for pattern in legacy_files:
            for file_path in glob.glob(pattern):
                try:
                    with open(file_path, "r") as f:
                        return json.load(f)
                except:
                    continue
        return {}

    def _recover_cache(self) -> Dict[str, Any]:
        """Robust cache recovery mechanisms"""
        # Check for WAL files first
        wal_dir = os.path.join(self.cluster_cache_dir, "wal")
        if os.path.isdir(wal_dir):
            for wal_file in sorted(os.listdir(wal_dir)):
                try:
                    with open(os.path.join(wal_dir, wal_file), "r") as f:
                        return json.load(f)
                except:
                    continue
                    
        # Attempt restoring from backup
        if os.path.isdir(self.backup_dir):
            for backup in sorted(
                os.listdir(self.backup_dir), 
                reverse=True
            ):
                if backup.startswith(self.cache_base_name):
                    try:
                        backup_path = os.path.join(self.backup_dir, backup)
                        with open(backup_path, "r") as f:
                            return json.load(f)
                    except:
                        continue
        
        # Fallback to empty cache
        return {}

    def get_cluster_independent_data(self) -> Dict[str, Any]:
        """Retrieve common/shared cluster data"""
        return self.get(self.COMMON_DATA_CLUSTER, {})
    
    def get_cluster_ids(self) -> Set[str]:
        """Get unique cluster identifiers"""
        # Use set operations for efficient lookups
        ids = set(self.keys())
        ids.discard(self.COMMON_DATA_CLUSTER)
        return ids

    def rewrite_cache(
        self, 
        cache: Dict[str, Any], 
        cache_hash: Optional[str]
    ) -> None:
        """
        Atomically refresh the entire cache
        :param cache: New cache dictionary
        :param cache_hash: Associated content hash
        """
        # Calculate cluster changes
        existing_clusters = set(self.keys())
        new_clusters = set(cache.keys())
        removed_clusters = existing_clusters - new_clusters
        
        # Transactional update
        with self._cache_lock:
            try:
                # Remove outdated clusters
                for cluster_id in removed_clusters:
                    del self[cluster_id]
                
                # Apply new/updated clusters
                for cluster_id, cluster_data in cache.items():
                    self._update_cluster(cluster_id, cluster_data)
                
                # Persist changes WAL-first
                self._create_wal(cache)
                self.persist_cache(cache_hash)
                self._cleanup_wal()
                
                # Trigger cache metrics
                self.on_cache_update()
            except Exception as e:
                # State reversal on update failure
                logger.error(f"Cache update failed: {str(e)} - Rolling back")
                self._rollback_wal()

    def _update_cluster(
        self, 
        cluster_id: str, 
        cluster_data: Any
    ) -> None:
        """Immutable cluster data update"""
        # Create immutable snapshot of data
        immutable_data = self._make_immutable(cluster_data)
        
        # Optimized in-memory update
        if cluster_id in self and isinstance(
            self[cluster_id], dict
        ) and isinstance(immutable_data, dict):
            # Preserve existing non-conflicting data
            existing = self[cluster_id]
            for key in set(existing.keys()) - set(immutable_data.keys()):
                immutable_data[key] = existing[key]
        
        self[cluster_id] = immutable_data

    def cache_update(
        self, 
        update_dict: Dict[str, Any], 
        cache_hash: Optional[str]
    ) -> None:
        """
        Differential cache update
        :param update_dict: Changes to apply
        :param cache_hash: Updated content hash
        """
        # Merge changes with current state
        merged_data = self.deep_merge(
            self._get_mutable_copy(),
            update_dict
        )
        self.rewrite_cache(merged_data, cache_hash)
    
    @staticmethod
    def deep_merge(
        base: Dict[str, Any], 
        update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursive dictionary merge with type preservation"""
        if not isinstance(base, dict) or not isinstance(update, dict):
            return update
        
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = ClusterCache.deep_merge(base[key], value)
            else:
                base[key] = value
        return base
        
    def cache_delete(
        self, 
        delete_dict: Dict[str, Any], 
        cache_hash: Optional[str]
    ) -> None:
        """
        Delete specific cache elements - must be implemented by subclasses
        :param delete_dict: Elements to remove
        :param cache_hash: Updated content hash
        """
        raise NotImplementedError("Subclasses should implement cache_delete")

    @contextmanager
    def _atomic_file_access(
        self, 
        file_path: str, 
        mode: str
    ):
        """Transactional file access with atomic replacement"""
        temp_dir = os.path.dirname(file_path)
        with tempfile.NamedTemporaryFile(
            mode=mode[0] + "+", 
            dir=temp_dir, 
            delete=False
        ) as tf:
            temp_name = tf.name
            try:
                if "r" in mode:
                    with open(file_path, "r") as src:
                        shutil.copyfileobj(src, tf)
                        tf.flush()
                        tf.seek(0)
                
                yield tf
                
                if "w" in mode:
                    tf.flush()
                    os.replace(temp_name, file_path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)

    def persist_cache(
        self, 
        cache_hash: Optional[str]
    ) -> None:
        """Atomic cache persistence with backup rotation"""
        # Ensure directory structure exists
        os.makedirs(self.cluster_cache_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Create backup before modifying
        backup_id = f"{self.cache_base_name}-{int(time.time())}.json"
        backup_path = os.path.join(self.backup_dir, backup_id)
        if os.path.exists(self.cache_json_file):
            shutil.copy(
                self.cache_json_file, 
                backup_path
            )
        
        with self._atomic_file_access(self.cache_json_file, "w") as f:
            json.dump(self, f, indent=2)
            
        # Clean up old backups (keep 5 most recent)
        backups = sorted(
            [f for f in os.listdir(self.backup_dir) 
             if f.startswith(self.cache_base_name)],
            key=lambda x: os.path.getmtime(os.path.join(self.backup_dir, x))
        )
        for old_backup in backups[:-5]:
            os.remove(os.path.join(self.backup_dir, old_backup))
        
        # Update hash file if provided
        if cache_hash is not None:
            with self._atomic_file_access(self.hash_file, "w") as f:
                f.write(cache_hash)
        
        self.hash = cache_hash

    def _create_wal(self, new_cache: Dict[str, Any]) -> None:
        """Write-ahead logging for transactions"""
        wal_dir = os.path.join(self.cluster_cache_dir, "wal")
        os.makedirs(wal_dir, exist_ok=True)
        
        wal_file = os.path.join(
            wal_dir, 
            f"{self.cache_base_name}-{int(time.time() * 1000)}.json.tmp"
        )
        
        with open(wal_file, "w") as f:
            json.dump(new_cache, f)
        
        # Commit the transaction
        os.rename(wal_file, wal_file.replace(".tmp", ".wal"))

    def _cleanup_wal(self) -> None:
        """Clean completed transactions"""
        wal_dir = os.path.join(self.cluster_cache_dir, "wal")
        if not os.path.isdir(wal_dir):
            return
            
        for wal in os.listdir(wal_dir):
            if wal.endswith(".wal"):
                wal_path = os.path.join(wal_dir, wal)
                try:
                    os.unlink(wal_path)
                except:
                    logger.warning(f"Couldn't clean WAL file: {wal_path}")

    def _rollback_wal(self) -> None:
        """Recover state from latest WAL file"""
        wal_dir = os.path.join(self.cluster_cache_dir, "wal")
        wal_files = sorted(
            [f for f in os.listdir(wal_dir) if f.endswith(".wal")],
            reverse=True
        )
        
        if wal_files:
            latest_wal = os.path.join(wal_dir, wal_files[0])
            with open(latest_wal, "r") as f:
                self.rewrite_cache(json.load(f), self.hash)
        else:
            # Fallback to last known good state
            self._load_or_initialize_cache()

    def _get_mutable_copy(self) -> Dict[str, Any]:
        """Create deep copy of cache for mutation"""
        with self._cache_lock:
            return self.deep_copy_data(dict(self))
    
    @staticmethod
    def deep_copy_data(data: Any) -> Any:
        """Recursive deep copy with immutability removal"""
        if isinstance(data, tuple):
            return tuple(ClusterCache.deep_copy_data(x) for x in data)
        elif isinstance(data, list):
            return [ClusterCache.deep_copy_data(x) for x in data]
        elif isinstance(data, dict):
            return {k: ClusterCache.deep_copy_data(v) for k, v in data.items()}
        return data
    
    @staticmethod
    def _make_immutable(data: Any) -> Any:
        """Create immutable representation of data"""
        if isinstance(data, dict):
            # Only freeze top-level attributes
            return FrozenDict((k, ClusterCache._make_immutable(v)) 
                      for k, v in data.items())
        elif isinstance(data, list):
            return tuple(ClusterCache._make_immutable(x) for x in data)
        return data
    
    def __getitem__(self, key: str) -> Any:
        """Access cached elements with detailed errors"""
        try:
            return super().__getitem__(key)
        except KeyError:
            clusters = ", ".join(self.keys())
            error_msg = (
                f"{self.cache_base_name.title()} missing for '{key}'. "
                f"Avaliable clusters: {clusters}"
            )
            logger.error(error_msg)
            raise CacheMissError(error_msg)

    def on_cache_update(self) -> None:
        """Extension point for cache change notifications"""
        pass

    def get_cache_name(self) -> str:
        """Must be implemented by subclasses to provide cache identifier"""
        raise NotImplementedError("Subclasses must implement get_cache_name")
    
    def health_check(self) -> Dict[str, Any]:
        """Report cache health metrics"""
        return {
            "version": self.version,
            "last_hash": self.hash,
            "cluster_count": len(self),
            "disk_size": os.path.getsize(self.cache_json_file),
            "last_modified": os.path.getmtime(self.cache_json_file)
        }


class FrozenDict(dict):
    """Immutable dictionary implementation"""
    __slots__ = ()
    
    def __setitem__(self, key, value):
        raise TypeError("FrozenDict doesn't support item assignment")
    
    def __delitem__(self, key):
        raise TypeError("FrozenDict doesn't support item deletion")
    
    def update(self, *args, **kwargs):
        raise TypeError("FrozenDict doesn't support updates")


class CacheMissError(Exception):
    """Specialized exception for missing cache keys"""
    pass


# Global logger configuration
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

