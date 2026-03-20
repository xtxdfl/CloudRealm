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

Enhanced Windows MSI Package Management Provider
"""

import os
import logging
import urllib.parse
from resource_management import Script, Execute, File
from cloud_commons.inet_utils import download_file
from resource_management.core.providers import Provider
from resource_management.core.exceptions import Fail, ComponentIsNotRunning

LOG = logging.getLogger(__name__)

class WindowsMsiProvider(Provider):
    """
    Enhanced MSI package management provider for Windows systems.
    
    Features:
    - Secure remote and local MSI installation
    - Detailed logging of installation process
    - Idempotent operation with marker tracking
    - Clean temporary resource management
    """
    
    # Command templates
    INSTALL_TEMPLATE = (
        'cmd /C start /wait msiexec /qn /i "{msi_path}" '
        '/lv "{log_path}"{params}{flags}'
    )
    
    UNINSTALL_TEMPLATE = (
        'cmd /C start /wait msiexec /qn /x "{msi_path}" '
        '/lv "{log_path}"'
    )

    def action_install(self):
        """Install an MSI package with logging and error handling."""
        # Validate and set up installation paths
        package, source, work_dir = self._validate_and_setup()
        
        # Create installation markers
        marker_file, log_file = self._create_install_markers(package, work_dir)
        
        # If already installed, skip
        if self._check_already_installed(marker_file, package):
            return
            
        # Handle MSI source (download if needed)
        msi_path = self._get_msi_path(package, source, work_dir)
        
        # Build installation command
        install_cmd = self._build_install_command(
            msi_path, 
            log_file,
            self.resource.dict_args,
            self.resource.list_args
        )
        
        # Execute installation
        self._execute_installation(install_cmd, package, log_file)
        
        # Create success marker
        self._create_success_marker(marker_file, package)
        
        # Clean up temporary files
        self._cleanup_temp_files(msi_path, source)

    def action_uninstall(self):
        """Uninstall an MSI package with logging and error handling."""
        package, source, work_dir = self._validate_and_setup()
        marker_file, log_file = self._create_uninstall_markers(package, work_dir)
        msi_path = self._get_msi_path(package, source, work_dir)
        
        # Don't uninstall if not installed
        if not os.path.exists(marker_file):
            LOG.info(f"{package} is not installed, skipping uninstall")
            return
            
        # Build uninstall command
        uninstall_cmd = self.UNINSTALL_TEMPLATE.format(
            msi_path=msi_path,
            log_path=log_file
        )
        
        # Execute uninstall
        try:
            Execute(uninstall_cmd, logoutput=True, timeout=300)
            File(marker_file, action="delete")
            LOG.info(f"Successfully uninstalled {package}")
        except Exception as e:
            LOG.error(f"Uninstall failed for {package}: {e}")
            raise Fail(f"Uninstallation of {package} failed") from e

    def _validate_and_setup(self):
        """Validate input parameters and setup environment."""
        if not hasattr(self.resource, 'msi_name') or not self.resource.msi_name:
            raise Fail("MSI package name is required")
        
        package = self.resource.msi_name.strip()
        source = getattr(self.resource, 'http_source', None)
        work_dir = os.path.abspath(
            Script.get_config()["agentLevelParams"]["agentCacheDir"]
        )
        
        # Ensure work directory exists
        if not os.path.exists(work_dir):
            os.makedirs(work_dir, exist_ok=True)
            LOG.info(f"Created working directory: {work_dir}")
        
        return package, source, work_dir

    def _create_install_markers(self, package, work_dir):
        """Create file markers for installation tracking."""
        prefix = package.replace(' ', '_').replace('.', '_').lower()
        marker_file = os.path.join(work_dir, f"{prefix}.installed")
        log_file = os.path.join(work_dir, f"{prefix}_install.log")
        return marker_file, log_file

    def _create_uninstall_markers(self, package, work_dir):
        """Create file markers for uninstallation tracking."""
        prefix = package.replace(' ', '_').replace('.', '_').lower()
        marker_file = os.path.join(work_dir, f"{prefix}.installed")
        log_file = os.path.join(work_dir, f"{prefix}_uninstall.log")
        return marker_file, log_file

    def _check_already_installed(self, marker_file, package):
        """Check if package is already installed."""
        if os.path.exists(marker_file):
            LOG.info(f"{package} is already installed (marker exists: {marker_file})")
            return True
        return False

    def _get_msi_path(self, package, source, work_dir):
        """Get the full path to the MSI file, downloading if necessary."""
        # If source is provided, download the file
        if source:
            dl_url = urllib.parse.urljoin(source, package)
            local_path = os.path.join(work_dir, os.path.basename(package))
            
            LOG.info(f"Downloading {dl_url} to {local_path}")
            try:
                download_file(dl_url, local_path, timeout=300)
                return local_path
            except Exception as e:
                LOG.error(f"Failed to download {dl_url}: {e}")
                raise Fail("MSI download failed") from e
        
        # If no source, assume local path
        if os.path.exists(package):
            return os.path.abspath(package)
        
        raise Fail(f"MSI file not found at: {package}")

    def _build_install_command(self, msi_path, log_path, params, flags):
        """Build the MSI installation command string."""
        # Initialize empty components
        params_str = ""
        flags_str = ""
        
        # Add parameters (key=value pairs)
        if isinstance(params, dict):
            params_str = " ALLUSERS='1'"
            for k, v in params.items():
                params_str += f" {str(k)}='{str(v)}'"
        
        # Add flags
        if isinstance(flags, list):
            flags_str = " " + " ".join(f"/{str(f)}" for f in flags)
        
        # Format final command
        return self.INSTALL_TEMPLATE.format(
            msi_path=msi_path,
            log_path=log_path,
            params=params_str,
            flags=flags_str
        )

    def _execute_installation(self, command, package, log_path):
        """Execute the installation command with error handling."""
        LOG.info(f"Installing {package} with command: {command}")
        try:
            Execute(command, logoutput=True, timeout=600)
            LOG.info(f"Successfully installed {package}")
        except Exception as e:
            log_content = ""
            try:
                with open(log_path, 'r') as log_file:
                    log_content = log_file.read()
            except Exception as log_err:
                log_content = f"Failed to read log: {log_err}"
            
            LOG.error(f"Installation failed for {package}. Log contents:\n{log_content}")
            raise Fail(f"{package} installation failed with error: {e}") from e

    def _create_success_marker(self, marker_file, package):
        """Create installation success marker file."""
        try:
            with open(marker_file, 'w') as marker:
                marker.write(package)
            LOG.info(f"Created installation marker: {marker_file}")
        except Exception as e:
            LOG.warning(f"Failed to create marker file for {package}: {e}")

    def _cleanup_temp_files(self, msi_path, source):
        """Clean up downloaded temporary files after installation."""
        if not source:
            return
            
        try:
            if os.path.exists(msi_path):
                File(msi_path, action="delete")
                LOG.info(f"Cleaned up downloaded file: {msi_path}")
        except Exception as e:
            LOG.warning(f"Failed to clean up temp file {msi_path}: {e}")

    def _check_install_status(self, marker_file):
        """Check if package is installed based on marker file."""
        return os.path.exists(marker_file)
