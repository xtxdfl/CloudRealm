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

Enhanced Stack Version Detection Utility
"""

import os
import re
import logging
from typing import Optional, List, Tuple, Dict

# Configure logger
STACK_LOGGER = logging.getLogger("stack_version")
STACK_LOGGER.setLevel(logging.INFO)

# Stack version recognition constants
VERSION_FORMATS = [
    r"(\d+\.\d+\.\d+\.\d+-\d+)",      # Standard cloud format (1.2.3.4-567)
    r"(\d+\.\d+\.\d+-\d+)",            # Three-digit HDP format (3.1.4-123)
    r"(\d+\.\d+\.\d+\.\d+)",           # Four-digit without build 
    r"(\d+\-\d+\.\d+\.\d+\.\d+-\d+)"   # Amazon Linux format (7-1.2.3.4-567)
]
DEFAULT_PATTERN = r"(\d+\.\d+\.\d+(?:\.\d+)?-\d+)"  # Generic fallback pattern
CACHE_TTL = 300  # Version cache lifetime (seconds)

# Global cache for version results
_version_cache = {}  # {package_name: (timestamp, version)}

def clear_version_cache():
    """Clear stale entries from the version cache"""
    global _version_cache
    current_time = time.time()
    _version_cache = {
        pkg: (ts, ver) 
        for pkg, (ts, ver) in _version_cache.items()
        if current_time - ts < CACHE_TTL
    }

def extract_version(string: str) -> Optional[str]:
    """
    Identify stack version using prioritized pattern matching
    
    Args:
        string: Input string to search for version pattern
        
    Returns:
        Extracted version string or None if not found
    """
    # Try all known version formats in priority order
    for pattern in VERSION_FORMATS + [DEFAULT_PATTERN]:
        match = re.search(pattern, string)
        if match:
            return match.group(1)
    
    # Fallback: capture any digit-dot-dash sequence
    return re.search(r"([\d\.-]+)", string).group(1) if re.search(r"[\d\.-]{5,}", string) else None

@OsFamilyFuncImpl(OSConst.WINSRV_FAMILY)
def get_stack_version(package_name: str, force_refresh: bool = False) -> Optional[str]:
    """
    Retrieve stack version on Windows platforms
    
    Enhanced Features:
    - Multiple installation location checks
    - Registry lookup fallback
    - Service Manager query
    - Stale cache cleanup
    
    Args:
        package_name: Target component name (e.g., "HDFS")
        force_refresh: Bypass cache and recheck
        
    Returns:
        Detected stack version or None if unable to determine
    """
    # Check version cache first
    cached_version = _get_cached_version(package_name)
    if not force_refresh and cached_version:
        return cached_version
    
    # Search priority:
    search_methods = [
        _get_version_from_env_var,
        _get_version_from_registry,
        _get_version_from_uninstall_reg,
        _get_version_from_service_info
    ]
    
    for method in search_methods:
        version = method(package_name)
        if version:
            _cache_version(package_name, version)
            return version
    
    STACK_LOGGER.info(
        f"Failed to detect stack version for {package_name} on Windows"
    )
    return None

def _get_version_from_env_var(package_name: str) -> Optional[str]:
    """Check environment variable for home directory pattern"""
    try:
        home_path = os.environ[f"{package_name.upper()}_HOME"]
        return extract_version(home_path)
    except KeyError:
        pass
    return None

def _get_version_from_registry(package_name: str) -> Optional[str]:
    """Query Windows registry for installation info"""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            f"SOFTWARE\\Apache\\{package_name}\\Install"
        ) as key:
            install_dir = winreg.QueryValueEx(key, "INSTALLDIR")[0]
            return extract_version(install_dir)
    except OSError:
        pass
    return None

def _get_version_from_uninstall_reg(package_name: str) -> Optional[str]:
    """Check Windows uninstall registry entries"""
    pattern = re.compile(f"Apache {package_name} (\d+\.\d+\.\d+\.\d+-\d+)")
    
    try:
        import winreg
        base_key = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(base_key, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as uninstall:
            for idx in range(winreg.QueryInfoKey(uninstall)[0]):
                try:
                    subkey_name = winreg.EnumKey(uninstall, idx)
                    with winreg.OpenKey(uninstall, subkey_name) as subkey:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        match = pattern.search(display_name)
                        if match:
                            return match.group(1)
                except OSError:
                    continue
    except OSError:
        pass
    return None

def _get_version_from_service_info(package_name: str) -> Optional[str]:
    """Query service configuration for path info"""
    try:
        import win32serviceutil
        services = win32serviceutil.QueryServiceStatus(f"{package_name}Service", machine=".")
        bin_path = win32serviceutil.GetServiceConfig(f"{package_name}Service", machine=".")[6]
        return extract_version(bin_path)
    except:
        pass
    return None

@OsFamilyFuncImpl(OsFamilyImpl.DEFAULT)
def get_stack_version(package_name: str, force_refresh: bool = False) -> Optional[str]:
    """
    Retrieve stack version on Unix-like platforms
    
    Enhanced Features:
    - Multiple stack selector support
    - Service status fallback
    - Alternate executable search
    - Package manager queries
    - Config file analysis
    
    Args:
        package_name: Target component name (e.g., "HDFS")
        force_refresh: Bypass cache and recheck
        
    Returns:
        Detected stack version or None if unable to determine
    """
    # Check version cache first
    cached_version = _get_cached_version(package_name)
    if not force_refresh and cached_version:
        return cached_version
    
    # Search priority on Unix
    try:
        # 1. Stack selector primary method
        status_output = _query_stack_selector(package_name)
        version = _parse_selector_output(status_output, package_name)
        if version:
            _cache_version(package_name, version)
            return version
        
        # 2. Check symlinked directories
        version = _find_version_from_symlinks(package_name)
        if version:
            _cache_version(package_name, version)
            return version
        
        # 3. Query package manager
        version = _query_package_manager(package_name)
        if version:
            _cache_version(package_name, version)
            return version
    except Exception as e:
        STACK_LOGGER.error(f"Stack version detection error: {str(e)}")
    
    STACK_LOGGER.warning(f"Failed to find stack version for {package_name}")
    return None

def _query_stack_selector(package_name: str) -> Optional[str]:
    """Use stack selector tools to retrieve version"""
    tool_path = find_stack_tool()
    if not tool_path:
        STACK_LOGGER.debug("No stack selector tool found")
        return None
    
    try:
        # Try with sudo wrapper if necessary
        command = f"{tool_path} status {package_name}"
        result = execute_command(command, capture_output=True)
        if result and result.returncode == 0:
            return result.stdout
    except Exception as e:
        STACK_LOGGER.warning(f"Stack tool execution failed: {str(e)}")
    
    return None

def find_stack_tool() -> Optional[str]:
    """Locate stack selector binary in common locations"""
    tool_paths = [
        stack_tools.get_stack_tool_path(stack_tools.STACK_SELECTOR_NAME),
        "/usr/bin/cloud-select",
        "/usr/local/bin/cloud-select",
        "/usr/sbin/cloud-select",
        "/opt/cloud/bin/cloud-select"
    ]
    
    for path in tool_paths:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None

def _parse_selector_output(output: str, package_name: str) -> Optional[str]:
    """Extract version from tool response"""
    if not output:
        return None
    
    clean_output = output.strip()
    
    # Known selector output formats:
    patterns = [
        rf"{package_name}\s*-\s*([\d\.-]+)",  # HDFS - 3.1.4.0-123
        rf"{package_name}:\s*(.+)",           # HDFS: 3.1.4.0-123
        r"Current version:\s*(.+)",           # Current version: 3.1.4.0-123
        r"Version:\s*(.+)"                    # Version: 3.1.4.0-123
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_output)
        if match:
            candidate = match.group(1).strip()
            if re.match(r"\d", candidate):  # Must start with digit
                return candidate
    
    # Fallback: extract any version patterns
    return extract_version(clean_output)

def _find_version_from_symlinks(package_name: str) -> Optional[str]:
    """Check common symlink locations for version pattern"""
    symlink_paths = [
        f"/usr/{package_name.lower()}",
        f"/usr/hdp/{package_name.lower()}",
        f"/opt/{package_name.lower()}"
    ]
    
    for path in symlink_paths:
        if not os.path.islink(path):
            continue
        
        real_path = os.path.realpath(path)
        return extract_version(real_path)
    
    return None

def _query_package_manager(package_name: str) -> Optional[str]:
    """Get version from system package manager"""
    try:
        # Try RPM-based systems
        import rpm
        ts = rpm.TransactionSet()
        for hdr in ts.dbMatch("name", package_name.lower()):
            return hdr["version"] + "-" + hdr["release"]
    except:
        pass
    
    try:
        # Try DEB-based systems
        import apt
        cache = apt.Cache()
        pkg = cache.get(package_name.lower())
        if pkg and pkg.installed:
            return pkg.installed.version
    except:
        pass
    
    return None

# Cache helpers -------------------------------------

def _get_cached_version(package_name: str) -> Optional[str]:
    """Check cache for recent version result"""
    global _version_cache
    
    # Clear expired cache entries
    clear_version_cache()
    
    cached = _version_cache.get(package_name)
    if not cached:
        return None
        
    _, version = cached
    STACK_LOGGER.debug(f"Using cached version for {package_name}: {version}")
    return version

def _cache_version(package_name: str, version: str):
    """Cache a successful version lookup"""
    global _version_cache
    if version:
        _version_cache[package_name] = (time.time(), version)

# Compatibility layer -------------------------------

@OsFamilyFuncImpl(OSConst.WINSRV_FAMILY)
def legacy_get_stack_version(package_name: str) -> Optional[str]:
    """Original Windows implementation"""
    try:
        component_home_dir = os.environ[package_name.upper() + "_HOME"]
        paths = component_home_dir.split(os.sep)
        for path in reversed(paths):
            if path:
                version = extract_version(path)
                if version:
                    return version
    except KeyError:
        pass
    return None

@OsFamilyFuncImpl(OsFamilyImpl.DEFAULT)
def legacy_get_stack_version(package_name: str) -> Optional[str]:
    """Original Unix-like implementation"""
    try:
        stack_selector_path = stack_tools.get_stack_tool_path(
            stack_tools.STACK_SELECTOR_NAME
        )
        if not os.path.exists(stack_selector_path):
            return None
            
        command = f"cloud-python-wrap {stack_selector_path} status {package_name}"
        return_code, stack_output = shell.call(command, timeout=20)
        if return_code == 0:
            cleaned = stack_output.strip().replace(f"{package_name} - ", "")
            return extract_version(cleaned)
    except Exception:
        pass
    return None
