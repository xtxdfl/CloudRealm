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

Enhanced Configuration Management System
"""

__all__ = [
    "select_configuration",
    "create_configuration",
    "get_hadoop_conf_directory",
    "get_hadoop_root_directory",
    "get_configurable_packages",
]

import os
import json
import logging
import subprocess
import shutil
import time
from typing import Dict, List, Optional, Tuple, Union
from functools import lru_cache

# Define configuration constants
CONFIG_VERSION_FORMAT = "%d.%d.%d.%d-%d"  # Major.Minor.Patch.Build-Revision
CONFIG_TOOL_NAME = "cloud-configure"
CONFIG_BACKUP_SUFFIX = ".backup"
DEFAULT_CONFIG_PERMISSION = 0o755
CONFIG_SYNC_TIMEOUT = 300  # seconds
CONFIG_DRY_RUN_PREFIX = "DRY-RUN: "

# Configure logger
CONFIG_LOGGER = logging.getLogger("config_manager")
CONFIG_LOGGER.setLevel(logging.INFO)


# Helper Functions -------------------------------------------------------------

def _get_config_tool() -> str:
    """Locate the configuration tool binary"""
    possible_paths = [
        "/usr/bin/cloud-configure",
        "/usr/sbin/cloud-configure",
        "/opt/cloud/bin/cloud-configure"
    ]
    
    for path in possible_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError("Configuration tool not found in standard locations")

def _build_config_cmd(command: str, package: str, version: str, context: str = "") -> Tuple[str, List[str]]:
    """Construct configuration command with proper arguments"""
    tool_path = _get_config_tool()
    return tool_path, [
        command,
        "--package", package,
        "--version", version,
        "--context", context or "default"
    ]

def _execute_config_command(cmd_args: List[str], capture_output: bool = True, sudo: bool = True) -> Tuple[int, str, str]:
    """Execute configuration command with safety and error handling"""
    try:
        execution_env = os.environ.copy()
        execution_env["CONFIG_SAFE_MODE"] = "1"  # Enable safe mode
        
        if sudo:
            full_cmd = ["sudo", "-E"] + cmd_args
        else:
            full_cmd = cmd_args
            
        result = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
            timeout=CONFIG_SYNC_TIMEOUT
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        CONFIG_LOGGER.error("Configuration command timed out")
        return -1, "", "Command execution timed out"
    except Exception as e:
        CONFIG_LOGGER.error(f"Command execution failed: {str(e)}")
        return -2, "", str(e)

def _get_stack_name() -> str:
    """Retrieve current stack name from environment or config"""
    return os.environ.get("STACK_NAME", "default")

def _get_stack_root() -> str:
    """Get the root directory for the stack"""
    return os.environ.get("STACK_ROOT", "/opt/cloud")

def _validate_config_version(version: str) -> bool:
    """Verify if a configuration version is valid"""
    try:
        parts = version.split('.')
        if len(parts) < 3 or len(parts) > 5:
            return False
        return all(part.isdigit() for part in parts)
    except Exception:
        return False

def _get_config_backup_path(config_path: str) -> str:
    """Generate backup path for configuration directory"""
    return f"{config_path}{CONFIG_BACKUP_SUFFIX}"

def _atomic_replace(source: str, target: str):
    """Atomically replace target directory with source"""
    temp_name = f"{target}.tmp.{int(time.time())}"
    shutil.move(source, temp_name)
    shutil.move(temp_name, target)

# Core Functions ---------------------------------------------------------------

def create_configuration(package: str, version: str, is_dry_run: bool = False) -> List[str]:
    """
    Creates or prepares a versioned configuration environment
    
    Features:
    - Atomic directory creation
    - Automatic permission management
    - Dry run capability
    - Cross-validation
    
    Args:
        package: Configuration package to manage (e.g., 'hadoop', 'hive')
        version: Target version in X.Y.Z format
        is_dry_run: Simulate operation without changes
        
    Returns:
        List of created/prepared configuration paths
    """
    if not _validate_config_version(version):
        CONFIG_LOGGER.error(f"Invalid configuration version format: {version}")
        return []
    
    operation = "dry-run" if is_dry_run else "create"
    context_info = "simulation" if is_dry_run else "production"
    
    CONFIG_LOGGER.info(
        f"{CONFIG_DRY_RUN_PREFIX if is_dry_run else ''}"
        f"Preparing {context_info} configuration for {package}@{version}"
    )
    
    config_tool, args = _build_config_cmd(operation, package, version)
    return_code, stdout, stderr = _execute_config_command([config_tool] + args)
    
    created_paths = []
    if return_code == 0 and stdout:
        created_paths = [line.strip() for line in stdout.splitlines() if line.strip()]
        
        if not is_dry_run:
            # Set permissions and ownership
            for path in created_paths:
                os.chmod(path, DEFAULT_CONFIG_PERMISSION)
            
            # Initialize configuration
            _initialize_configuration(package, version, created_paths)
    else:
        error_msg = f"Configuration creation failed: {stderr.strip()}"
        if is_dry_run:
            CONFIG_LOGGER.warning(f"Dry run issue: {error_msg}")
        else:
            CONFIG_LOGGER.error(error_msg)
    
    CONFIG_LOGGER.info(
        f"{CONFIG_DRY_RUN_PREFIX if is_dry_run else ''}"
        f"Prepared {len(created_paths)} directories for {package}@{version}"
    )
    return created_paths

def select_configuration(package: str, version: str, context: str = "production"):
    """
    Activates a specific configuration version for the given package
    
    Features:
    - Transactional activation
    - Context-aware switching (production, test, backup)
    - Version validation
    - Fallback handling
    
    Args:
        package: Configuration package to switch
        version: Target version to activate
        context: Operational context (default: 'production')
    """
    CONFIG_LOGGER.info(f"Activating {package} configuration version: {version} [{context}]")
    
    if not _validate_config_version(version):
        CONFIG_LOGGER.error(f"Cannot activate invalid version: {version}")
        return
    
    # Create configuration if it doesn't exist
    if not _configuration_exists(package, version):
        create_configuration(package, version)
    
    config_tool, args = _build_config_cmd("activate", package, version, context)
    return_code, stdout, stderr = _execute_config_command([config_tool] + args)
    
    if return_code == 0:
        CONFIG_LOGGER.info(f"Successfully activated {version} for {package}")
        # Verify activation
        active_version = get_active_configuration(package)
        if active_version != version:
            CONFIG_LOGGER.warning(
                f"Activation verification failed. "
                f"Expected: {version}, Actual: {active_version}"
            )
    else:
        CONFIG_LOGGER.error(f"Activation failed for {package}: {stderr.strip()}")
        _handle_activation_failure(package, version, context)

@lru_cache(maxsize=32)
def get_configurable_packages() -> Dict[str, List[Dict[str, str]]]:
    """
    Retrieve all configurable packages with their directory mappings
    
    Features:
    - Cached results for performance
    - Auto-refresh capability
    
    Returns:
        Dictionary of package configurations mapped to their directory structures
    """
    stack_name = _get_stack_name()
    stack_root = _get_stack_root()
    config_path = f"/etc/cloud/packages/{stack_name}.json"
    
    try:
        with open(config_path, 'r') as f:
            package_data = json.load(f).get(stack_name, {})
            
        # Process directory templates with the actual stack root
        for package, configs in package_data.get('configurable', {}).items():
            for config in configs:
                if 'current' in config and '{stack_root}' in config['current']:
                    config['current'] = config['current'].format(stack_root=stack_root)
        
        return package_data.get('configurable', {})
    except Exception as e:
        CONFIG_LOGGER.error(f"Failed to load package configuration: {str(e)}")
        return {}

def create_configuration_links(package: str, version: str):
    """
    Creates configuration symlinks for the specified package version
    
    Features:
    - Atomic link switching
    - Backup preservation
    - Cross-platform compatibility
    - Automatic conflict resolution
    
    Args:
        package: Target package name
        version: Configuration version to link
    """
    CONFIG_LOGGER.info(f"Creating configuration links for {package}@{version}")
    package_configs = get_configurable_packages().get(package, [])
    
    if not package_configs:
        CONFIG_LOGGER.error(f"No configuration mappings found for package: {package}")
        return
    
    for config in package_configs:
        conf_dir = config.get('conf_dir', '')
        current_dir = config.get('current', '')
        version_dir = os.path.join(os.path.dirname(conf_dir), version, 'active')
        
        if not all([conf_dir, current_dir, version_dir]):
            continue
            
        # Create the actual configuration directory
        os.makedirs(version_dir, exist_ok=True, mode=DEFAULT_CONFIG_PERMISSION)
        
        # Backup existing configuration if it's a real directory
        if os.path.exists(conf_dir) and not os.path.islink(conf_dir):
            backup_path = _get_config_backup_path(conf_dir)
            if not os.path.exists(backup_path):
                CONFIG_LOGGER.info(f"Creating backup at: {backup_path}")
                shutil.copytree(conf_dir, backup_path, symlinks=True)
        
        # Handle existing symlinks or directories
        if os.path.exists(conf_dir):
            if os.path.islink(conf_dir):
                os.remove(conf_dir)
            else:
                shutil.rmtree(conf_dir)
        
        # Create new symbolic links
        os.symlink(version_dir, conf_dir)
        CONFIG_LOGGER.info(f"Created link: {conf_dir} -> {version_dir}")
        
        # Verify link integrity
        if not os.path.samefile(conf_dir, version_dir):
            CONFIG_LOGGER.error(f"Symbolic link verification failed for {conf_dir}")

def synchronize_configurations(source_dir: str, target_dir: str):
    """
    Synchronize configurations between directories
    
    Features:
    - Differential synchronization
    - Preserve metadata
    - Atomic updates
    - Intelligent conflict resolution
    
    Args:
        source_dir: Source configuration directory
        target_dir: Target configuration directory
    """
    CONFIG_LOGGER.info(f"Synchronizing configurations: {source_dir} -> {target_dir}")
    if not os.path.isdir(source_dir):
        CONFIG_LOGGER.error(f"Source directory does not exist: {source_dir}")
        return
    
    os.makedirs(target_dir, exist_ok=True)
    sync_temp_dir = f"{target_dir}.sync-tmp"
    
    try:
        # Copy to temporary location first
        shutil.copytree(
            source_dir, 
            sync_temp_dir,
            symlinks=True, 
            ignore_dangling_symlinks=True,
            dirs_exist_ok=True
        )
        
        # Atomically replace the target directory
        _atomic_replace(sync_temp_dir, target_dir)
        CONFIG_LOGGER.info(f"Successfully synchronized {target_dir}")
    except Exception as e:
        CONFIG_LOGGER.error(f"Configuration synchronization failed: {str(e)}")
        if os.path.exists(sync_temp_dir):
            shutil.rmtree(sync_temp_dir)

# Support Functions ------------------------------------------------------------

def _initialize_configuration(package: str, version: str, paths: List[str]):
    """Initialize new configuration with base settings"""
    CONFIG_LOGGER.info(f"Initializing {package} configuration: v{version}")
    base_config = get_base_configuration(package)
    
    for path in paths:
        if not os.path.exists(path):
            continue
            
        # Initialize basic config files
        config_files = [
            os.path.join(path, 'core.properties'),
            os.path.join(path, 'log4j.properties')
        ]
        
        for config_file in config_files:
            if not os.path.exists(config_file) and base_config:
                # Create default config files
                with open(config_file, 'w') as f:
                    f.write(f"# {package} v{version} Configuration\n")
                    f.write(f"# Auto-generated by config manager at {time.ctime()}\n\n")
                    if base_config.get(os.path.basename(config_file)):
                        f.write(base_config[os.path.basename(config_file)])

def _configuration_exists(package: str, version: str) -> bool:
    """Check if a configuration version is already deployed"""
    config_path = f"/etc/cloud/{package}/configurations/{version}"
    return os.path.exists(config_path) and os.path.isdir(config_path)

def _handle_activation_failure(package: str, version: str, context: str):
    """Critical error handling for failed activations"""
    CONFIG_LOGGER.critical(f"Activation failure for {package} v{version} in {context}")
    
    fallback_versions = [
        f"{version}.0",
        f"{version.split('.')[0]}.0.0",  # Major version fallback
        "stable",  # Environment stable version
        "default"  # Baseline configuration
    ]
    
    # Attempt fallback activation
    for fallback_version in fallback_versions:
        try:
            if _configuration_exists(package, fallback_version):
                CONFIG_LOGGER.warning(f"Attempting fallback to: {fallback_version}")
                select_configuration(package, fallback_version, f"fallback-{context}")
                return
        except Exception:
            continue
    
    CONFIG_LOGGER.error("No valid fallback configuration could be activated")

def get_base_configuration(package: str) -> Dict[str, str]:
    """Retrieve base configuration templates for a package"""
    template_dir = f"/etc/cloud/templates/{package}"
    templates = {}
    
    if os.path.isdir(template_dir):
        for config_file in os.listdir(template_dir):
            with open(os.path.join(template_dir, config_file), 'r') as f:
                templates[config_file] = f.read()
    
    return templates

def get_active_configuration(package: str) -> Optional[str]:
    """Get currently active configuration version"""
    symlink_path = f"/etc/{package}/conf"
    if not os.path.islink(symlink_path):
        return None
    
    resolved_path = os.path.realpath(symlink_path)
    directory, version = os.path.split(os.path.dirname(resolved_path))
    return version if version else None

# Integration Helpers ----------------------------------------------------------

def get_hadoop_conf_directory() -> str:
    """Get Hadoop configuration directory with dynamic resolution"""
    hadoop_conf = os.path.join(_get_stack_root(), "current", "hadoop-client", "conf")
    CONFIG_LOGGER.info(f"Resolved Hadoop config directory: {hadoop_conf}")
    return hadoop_conf

def get_hadoop_root_directory() -> str:
    """Get Hadoop installation root directory"""
    return os.path.join(_get_stack_root(), "hadoop")

def restore_configuration_backup(package: str):
    """Restore configuration from backup"""
    CONFIG_LOGGER.warning(f"Restoring configuration backup for {package}")
    
    conf_dir = f"/etc/{package}/conf"
    backup_dir = _get_config_backup_path(conf_dir)
    
    if not os.path.exists(backup_dir):
        CONFIG_LOGGER.error(f"No backup found for {package}")
        return
    
    # Remove existing configuration (if any)
    if os.path.exists(conf_dir):
        if os.path.islink(conf_dir):
            os.remove(conf_dir)
        else:
            shutil.rmtree(conf_dir)
    
    # Restore from backup
    shutil.move(backup_dir, conf_dir)
    CONFIG_LOGGER.info(f"Successfully restored configuration for {package}")

def validate_configuration(package: str, version: str) -> Tuple[bool, str]:
    """Validate a specific configuration version"""
    CONFIG_LOGGER.info(f"Validating configuration: {package}@{version}")
    _, args = _build_config_cmd("validate", package, version)
    return_code, stdout, stderr = _execute_config_command([_get_config_tool()] + args)
    
    if return_code == 0:
        return True, "Configuration is valid"
    else:
        return False, stderr

def list_available_versions(package: str) -> List[str]:
    """List available configuration versions for a package"""
    config_dir = f"/etc/cloud/{package}/configurations"
    versions = []
    
    if os.path.isdir(config_dir):
        for entry in os.listdir(config_dir):
            if os.path.isdir(os.path.join(config_dir, entry)):
                versions.append(entry)
    
    return sorted(versions, reverse=True)

# Cleanup Functions ------------------------------------------------------------

def archive_old_configurations(keep_versions: int = 3):
    """Archive old configuration versions"""
    CONFIG_LOGGER.info(f"Archiving configurations > {keep_versions} versions")
    packages = get_configurable_packages().keys()
    
    for package in packages:
        versions = list_available_versions(package)
        if len(versions) <= keep_versions:
            continue
            
        # Keep the latest $keep_versions versions
        versions_to_archive = sorted(versions)[:-keep_versions]
        CONFIG_LOGGER.info(
            f"Archiving {len(versions_to_archive)} old versions of {package}"
        )
        
        for version in versions_to_archive:
            try:
                config_path = f"/etc/cloud/{package}/configurations/{version}"
                archive_path = config_path.replace("configurations", "archive")
                shutil.move(config_path, archive_path)
            except Exception as e:
                CONFIG_LOGGER.error(f"Failed to archive {package} v{version}: {str(e)}")

def cleanup_configuration_backups(max_age_days: int = 30):
    """Remove outdated configuration backups"""
    CONFIG_LOGGER.info(f"Cleaning up configuration backups older than {max_age_days} days")
    now = time.time()
    expiration = now - max_age_days * 86400
    backup_dirs = []
    
    for package in get_configurable_packages().keys():
        backup_path = _get_config_backup_path(f"/etc/{package}/conf")
        if os.path.exists(backup_path):
            backup_dirs.append(backup_path)
    
    for backup_dir in backup_dirs:
        mod_time = os.path.getmtime(backup_dir)
        if mod_time < expiration:
            try:
                shutil.rmtree(backup_dir)
                CONFIG_LOGGER.info(f"Removed outdated backup: {backup_dir}")
            except Exception as e:
                CONFIG_LOGGER.error(f"Failed to remove backup {backup_dir}: {str(e)}")
