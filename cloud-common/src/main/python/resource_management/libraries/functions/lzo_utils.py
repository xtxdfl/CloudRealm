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

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.

cloud Agent - LZO Compression Management
"""

__all__ = ["should_install_lzo", "get_lzo_packages", "install_lzo_if_needed"]

from cloud_commons.os_check import OSCheck
from resource_management.libraries.functions.stack_features import check_stack_feature
from resource_management.libraries.functions.default import default
from resource_management.libraries.functions import StackFeature, stack_features
from resource_management.libraries.script.script import Script
from resource_management.core.logger import Logger
from resource_management.libraries.functions.expect import expect
from resource_management.core.resources.packaging import Package

# Constants
LZO_WARNING_GPL_NOT_ACCEPTED = (
    "Cannot install LZO. The GPL license must be explicitly enabled using "
    "'cloud-server setup' on the cloud host, then restart the server and try again."
)
SKIP_LZO_SYS_PREPPED = (
    "Skipping LZO package installation as host is system prepared and "
    "sysprep_skip_lzo_package_operations is enabled"
)

def get_lzo_packages():
    """
    Get the list of LZO packages required for the current OS and stack version.
    
    Returns:
        list: Package names required for LZO support
    """
    base_packages = []
    
    # OS-specific base packages
    if OSCheck.is_suse_family():
        if int(OSCheck.get_os_major_version()) >= 12:
            base_packages.append("liblzo2-2")
        else:
            base_packages.append("lzo")
    elif OSCheck.is_redhat_family():
        base_packages.append("lzo")
    elif OSCheck.is_ubuntu_family():
        base_packages.append("liblzo2-2")
    
    # Stack-specific packages for rolling upgrade support
    stack_version = stack_features.get_stack_feature_version(Script.get_config())
    script = Script.get_instance()
    
    if stack_version and check_stack_feature(StackFeature.ROLLING_UPGRADE, stack_version):
        hadoop_pkg = "hadooplzo-${stack_version}"
        native_pkg = f"{hadoop_pkg}-native"
        
        # Ubuntu package naming convention uses hyphens instead of underscores
        if OSCheck.is_ubuntu_family():
            base_packages.extend([
                script.format_package_name(hadoop_pkg),
                script.format_package_name(native_pkg)
            ])
        else:
            # Replace hyphens with underscores for non-Ubuntu systems
            hadoop_pkg = hadoop_pkg.replace('-', '_')
            native_pkg = native_pkg.replace('-', '_')
            base_packages.extend([
                script.format_package_name(hadoop_pkg),
                script.format_package_name(native_pkg)
            ])
    
    return base_packages

def is_gpl_license_accepted():
    """Check if GPL license has been accepted for LZO installation"""
    return default("/cloudLevelParams/gpl_license_accepted", False)

def should_install_lzo():
    """
    Determine if LZO should be installed based on configuration and GPL acceptance.
    
    Returns:
        bool: True if LZO should be installed, False otherwise
    """
    config = Script.get_config()
    
    # Check if LZO compression is enabled in core-site.xml
    io_compression_codecs = default("/configurations/core-site/io.compression.codecs", "").lower()
    lzo_enabled = "com.hadoop.compression.lzo" in io_compression_codecs
    
    if not lzo_enabled:
        Logger.info("LZO not enabled in core-site.io.compression.codecs")
        return False
    
    # Check GPL license acceptance
    if not is_gpl_license_accepted():
        Logger.warning(LZO_WARNING_GPL_NOT_ACCEPTED)
        return False
    
    return True

def should_skip_package_operations():
    """Determine if package operations should be skipped based on sysprep configuration"""
    return (
        default("/cloudLevelParams/host_sys_prepped", False) and 
        default("/configurations/cluster-env/sysprep_skip_lzo_package_operations", False)
    )

def install_lzo_if_needed():
    """
    Install LZO packages if required based on configuration.
    Handles system preparation and GPL license checks.
    """
    if not should_install_lzo():
        Logger.info("LZO installation not required. Skipping.")
        return
    
    if should_skip_package_operations():
        Logger.info(SKIP_LZO_SYS_PREPPED)
        return
    
    # Ensure repositories are updated for new GPL acceptance
    Script.repository_util.create_repo_files()
    
    # Get package names and install parameters
    lzo_packages = get_lzo_packages()
    config = Script.get_config()
    
    retry_on_unavailability = config["cloudLevelParams"].get("agent_stack_retry_on_unavailability", False)
    retry_count = expect("/cloudLevelParams/agent_stack_retry_count", int)
    
    # Log installation details
    Logger.info(f"Installing LZO packages: {', '.join(lzo_packages)}")
    Logger.debug(f"Installation parameters - retry: {retry_on_unavailability}, attempts: {retry_count}")
    
    # Execute package installation
    Package(
        lzo_packages,
        retry_on_repo_unavailability=retry_on_unavailability,
        retry_count=retry_count
    )
    
    Logger.info("LZO package installation completed")
