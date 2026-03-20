#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one or more
contributor license agreements.  See the NOTICE file distributed with
this work for additional information regarding copyright ownership.
The ASF licenses this file to you under the Apache License, Version 2.0
(the "License"); you may not use this file except in compliance with
the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Enhanced Mounted Directory Management System
"""

__all__ = ["manage_mounted_directories", "identify_duplicate_mount_directories"]

import os
import re
import csv
import errno
import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple

from resource_management.libraries.functions.file_system import (
    get_mount_point_for_dir,
    update_mount_points_cache,
)
from resource_management.core.logger import Logger
from resource_management.core.resources.system import Directory
from resource_management.core.exceptions import Fail
from resource_management.libraries.functions.config import get_config_value

# Logger configuration
MOUNT_LOGGER = logging.getLogger("mount_manager")
MOUNT_LOGGER.setLevel(logging.INFO)

# Constants
DIR_MOUNT_HISTORY_HEADER = """# Directory Mount History File
# 
# Tracks the mount points of service data directories to detect disk failures
#
# WARNING: Deletion may cause directory recreation on root partition if drives fail
# 
# Format: directory_path,mount_point
# 
# Example: /data/hdfs/data,/data
--------------------------------
"""

MOUNT_POINT_CHANGE_WARNING = """
*************************************** WARNING **************************************
{message}
The mount point for directory '{directory}' has changed from '{old_mount}' to '{new_mount}'.

This typically indicates:
  - A disk failure
  - Unintentional directory recreation on root partition
  - Intentional storage configuration change

Immediate Actions Required:
  1. Check health of storage devices: `df -h`, `smartctl -a <device>`
  2. Verify directory mount points: `mount | grep '{new_mount}'`
  3. If intentional change, update the history file at: {history_file}
  4. If disk failure, replace the failed drive
  5. Contact your storage administrator if unsure

To ignore this warning temporarily, set cluster-env/ignore_mount_changes=true
**************************************************************************************
"""

CONFIG_KEYS = {
    "ignore_mount_changes": "cluster-env/ignore_mount_changes",
    "manage_root_dirs": "cluster-env/manage_dirs_on_root",
    "one_dir_per_partition": "cluster-env/one_dir_per_partition",
}


class MountHistoryManager:
    """Manages the history of directory mount points"""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.history_dir = history_file.parent
        self.directory_map = self.load_history()
        
    def load_history(self) -> Dict[str, str]:
        """Load directory -> mount point mapping from history file"""
        mount_map = {}
        
        if self.history_file.exists():
            try:
                with self.history_file.open("r") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        # Skip comment and header lines
                        if not row or row[0].startswith("#") or len(row) < 2:
                            continue
                        mount_map[row[0]] = row[1]
                MOUNT_LOGGER.info(f"Loaded mount history for {len(mount_map)} directories")
            except Exception as e:
                MOUNT_LOGGER.error(
                    f"Error reading mount history from {self.history_file}: {str(e)}", 
                    exc_info=True
                )
        else:
            MOUNT_LOGGER.info(
                f"Mount history file not found: {self.history_file}. Creating new file."
            )
            self.ensure_history_directory()
        
        return mount_map
    
    def ensure_history_directory(self):
        """Ensure the history directory exists with proper permissions"""
        try:
            if not self.history_dir.exists():
                Directory(str(self.history_dir), create_parents=True, mode=0o755)
                MOUNT_LOGGER.info(f"Created mount history directory: {self.history_dir}")
        except Exception as e:
            MOUNT_LOGGER.error(f"Failed to create history directory: {str(e)}")
            raise Fail(f"History directory creation failed: {str(e)}")
    
    def update_history(self, directory: str, mount_point: str):
        """Update mount history for a directory"""
        self.directory_map[directory] = mount_point
    
    def save_history(self):
        """Save mount history to file"""
        try:
            self.ensure_history_directory()
            with self.history_file.open("w") as f:
                f.write(DIR_MOUNT_HISTORY_HEADER)
                for directory, mount in self.directory_map.items():
                    f.write(f"{directory},{mount}\n")
            MOUNT_LOGGER.info(f"Updated mount history at {self.history_file}")
        except OSError as e:
            MOUNT_LOGGER.error(
                f"Failed to write mount history ({e.errno}): {e.strerror}"
            )
        except Exception as e:
            MOUNT_LOGGER.error(f"Unexpected error saving mount history: {str(e)}")


def parse_directory_list(dirs_string: str) -> List[Path]:
    """Parse and validate a comma-separated directory list"""
    normalized_dirs = []
    
    for raw_dir in dirs_string.split(","):
        # Clean and normalize directory paths
        clean_dir = raw_dir.strip().replace("file:///", "/")
        clean_dir = re.sub(r"^\[.+\]", "", clean_dir)
        
        if not clean_dir:
            continue
        
        try:
            dir_path = Path(clean_dir)
            normalized_dirs.append(dir_path)
        except Exception as e:
            MOUNT_LOGGER.warning(f"Skipping invalid directory path '{clean_dir}': {e}")
    
    return normalized_dirs


def should_manage_directory(
    directory: Path,
    history_mount: str,
    current_mount: str,
    manage_root_dirs: bool,
) -> Tuple[bool, str]:
    """
    Determine if a directory should be managed based on mount point history
    
    Returns:
        (should_manage, change_message)
    """
    # First time seeing this directory
    if history_mount is None:
        if current_mount == "/":
            if not manage_root_dirs:
                message = (f"New directory on root mount: {directory}. "
                           "Management disabled by configuration.")
                return False, message
            return True, ""
        return True, ""
    
    # Mount point unchanged
    if history_mount == current_mount:
        if current_mount == "/" and not manage_root_dirs:
            message = (f"Root-mounted directory ignored: {directory}. "
                       "Management disabled by configuration.")
            return False, message
        return True, ""
    
    # Mount point changed - potential disk failure!
    message = (f"Mount point changed for {directory}: "
               f"was '{history_mount}', now '{current_mount}'. "
               "Possible disk failure or configuration change.")
    return False, message


def manage_mounted_directories(
    process_dir: Callable[[str], None],
    dirs_string: str,
    history_filename: str,
    update_cache: bool = True,
) -> str:
    """
    Intelligently manage directories across multiple mount points
    
    Core Features:
    1. Detect disk failures by tracking mount point changes
    2. Prevent accidental directory recreation on root partition
    3. Respect storage configuration constraints
    4. Handle multiple directories per mount point
    
    Args:
        process_dir: Function to process each managed directory
        dirs_string: Comma-separated list of directories to manage
        history_filename: File to track mount point history
        update_cache: Refresh mount point cache after processing
    """
    # Setup mount history manager
    history_path = Path(history_filename)
    history_manager = MountHistoryManager(history_path)
    
    # Parse and validate directory list
    directories = parse_directory_list(dirs_string)
    if not directories:
        MOUNT_LOGGER.warning("No valid directories to manage")
        return ""
    
    # Check configuration flags
    ignore_changes = get_config_value(CONFIG_KEYS["ignore_mount_changes"], False)
    manage_root_dirs = get_config_value(CONFIG_KEYS["manage_root_dirs"], True)
    one_dir_per_partition = get_config_value(CONFIG_KEYS["one_dir_per_partition"], False)
    
    # Collect information about existing directories
    existing_dirs = [d for d in directories if d.exists()]
    mount_usage = defaultdict(set)
    mount_points = {}
    
    for directory in existing_dirs:
        mount = get_mount_point_for_dir(str(directory))
        mount_usage[mount].add(str(directory))
        mount_points[str(directory)] = mount
    
    # Track status during processing
    mount_warnings = []
    used_mounts = set()
    managed_dirs = []
    
    for directory in directories:
        str_dir = str(directory)
        log_prefix = f"[{directory}] "
        
        # Retrieve current and historical mount points
        current_mount = mount_points.get(str_dir) or get_mount_point_for_dir(str_dir)
        historical_mount = history_manager.directory_map.get(str_dir)
        
        # Decision logic for directory management
        manage, message = should_manage_directory(
            directory,
            historical_mount,
            current_mount,
            manage_root_dirs
        )
        
        # Skip management if mount change detected (unless configured to ignore)
        if message and not ignore_changes:
            mount_warnings.append(
                MOUNT_POINT_CHANGE_WARNING.format(
                    message=message,
                    directory=str_dir,
                    old_mount=historical_mount or "<unknown>",
                    new_mount=current_mount or "<unknown>",
                    history_file=history_filename
                )
            )
            MOUNT_LOGGER.warning(log_prefix + message)
            manage = False
        
        # Check mount point usage constraints
        if manage and not directory.exists():
            if one_dir_per_partition and current_mount in used_mounts:
                MOUNT_LOGGER.warning(
                    log_prefix + f"Skipping - mount {current_mount} already used "
                    "(cluster-env/one_dir_per_partition=true)"
                )
                manage = False
            else:
                used_mounts.add(current_mount)
        
        # Process directory if all checks pass
        if manage:
            if not directory.exists():
                try:
                    MOUNT_LOGGER.info(log_prefix + "Creating directory")
                    process_dir(str_dir)
                    managed_dirs.append(str_dir)
                except Exception as e:
                    MOUNT_LOGGER.error(log_prefix + f"Creation failed: {str(e)}")
            else:
                MOUNT_LOGGER.debug(log_prefix + "Directory already exists")
            
            # Always update mount history for existing directories
            if directory.exists():
                history_manager.update_history(str_dir, current_mount or "unknown")
    
    # Handle mount point warnings
    if mount_warnings:
        MOUNT_LOGGER.error("\n" + "\n".join(mount_warnings))
    
    # Update mount point cache if requested
    if update_cache:
        MOUNT_LOGGER.debug("Refreshing mount point cache")
        update_mount_points_cache(refresh=True)
    
    # Save updated history
    history_manager.save_history()
    
    # Return final report
    report = (
        f"Managed {len(managed_dirs)} of {len(directories)} directories\n"
        f"{len(mount_warnings)} mount point changes detected\n"
        f"History updated at {history_filename}"
    )
    return report


def identify_duplicate_mount_directories(
    mount_points: Dict[str, str], 
    dirs_string: str
) -> List[Tuple[str, List[str]]]:
    """
    Identify directories sharing the same mount point
    
    This is particularly useful for:
    - Ensuring optimal performance configuration
    - Validating storage architecture
    - Identifying potential single points of failure
    
    Args:
        mount_points: Precomputed mount points (from get_mount_points())
        dirs_string: Comma-separated list of directories
        
    Returns:
        List of (mount_point, [directories]) tuples with duplicates
    """
    dirs = parse_directory_list(dirs_string)
    mount_groups = defaultdict(list)
    
    for directory in dirs:
        dir_str = str(directory)
        mount_point = mount_points.get(
            dir_str, get_mount_point_for_dir(dir_str)
        )
        mount_groups[mount_point].append(dir_str)
    
    return [
        (mount, dirs) 
        for mount, dirs in mount_groups.items() 
        if len(dirs) > 1
    ]


# Example usage
if __name__ == "__main__":
    # Sample configuration for testing
    logging.basicConfig(level=logging.INFO)
    
    def create_directory(dir_path: str):
        """Directory creation function example"""
        MOUNT_LOGGER.info(f"Creating directory: {dir_path}")
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Test data
    test_dirs = "/data/disk1,/data/disk2,/data/disk3,/opt/data,/"
    history_file = "/var/lib/cloud/mount_history.csv"
    
    # Run the test
    result_report = manage_mounted_directories(
        process_dir=create_directory,
        dirs_string=test_dirs,
        history_filename=history_file
    )
    
    MOUNT_LOGGER.info("\nTest Results:\n" + result_report)
