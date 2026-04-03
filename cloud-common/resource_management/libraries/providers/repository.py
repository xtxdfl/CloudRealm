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

Enhanced Repository Management Provider
"""

import os
import filecmp
import tempfile
import re
import logging
from collections import defaultdict
from cloud_commons import os_utils
from resource_management.core import sudo
from resource_management.core.providers import Provider
from resource_management.core.resources import Execute, File
from resource_management.core.source import InlineTemplate, StaticFile
from resource_management.core.environment import Environment
from resource_management.core.logger import Logger
from resource_management.core.exceptions import ExecutionFailed
from resource_management.core.shell import checked_call, call
from resource_management.libraries.functions.format import format

# Constants
REPO_TEMPLATE_FOLDER = "data"
REPO_MANAGERS_BY_OS = {
    "redhat": "RHEL",
    "centos": "RHEL",
    "amazon": "RHEL",
    "suse": "SUSE",
    "ubuntu": "UBUNTU",
    "debian": "UBUNTU",
}
LOG = Logger(__name__)

class RepositoryManager:
    """Central repository management with caching mechanism."""
    repo_catalog = defaultdict(lambda: "")
    
    @classmethod
    def add_repo_content(cls, repo_file_path, content):
        """Add repository content to the catalog."""
        cls.repo_catalog[repo_file_path] += content.strip() + "\n"
    
    @classmethod
    def clear_catalog(cls):
        """Clear the repository catalog."""
        cls.repo_catalog.clear()
    
    @classmethod
    def apply_changes(cls):
        """Apply all repository changes from the catalog."""
        if not cls.repo_catalog:
            return
            
        for repo_file_path, content in cls.repo_catalog.items():
            cls._apply_repository(repo_file_path, content)
        
        cls.clear_catalog()
    
    @staticmethod
    def _apply_repository(repo_path, new_content):
        """Apply repository content to the system."""
        with tempfile.NamedTemporaryFile("w") as tmp_file:
            # Write new content to temp file
            tmp_file.write(new_content)
            tmp_file.flush()
            
            if RepositoryManager._should_write(repo_path, tmp_file.name):
                LOG.info(f"Updating repository configuration at {repo_path}")
                File(
                    repo_path,
                    content=StaticFile(tmp_file.name),
                    owner=os_utils.current_user(),
                )
                
                try:
                    RepositoryManager._run_post_update(repo_path)
                except ExecutionFailed as e:
                    LOG.error(f"Repository update failed: {e}")
                    File(repo_path, action="delete")
                    raise
    
    @staticmethod
    def _should_write(repo_path, tmp_path):
        """Determine if the repository file needs to be updated."""
        if os.path.isfile(repo_path):
            if filecmp.cmp(repo_path, tmp_path):
                LOG.debug(f"Repository configuration unchanged: {repo_path}")
                return False
            return True
        return True
    
    @staticmethod
    def _run_post_update(repo_path):
        """Run distro-specific post-update tasks."""
        # Default implementation, overridden in OS-specific providers
        pass


class BaseRepositoryProvider(Provider):
    """Base class for OS-specific repository providers."""
    repo_config_dir = None
    repo_file_extension = ""
    
    def action_create(self):
        """Prepare repository content without applying changes."""
        self._validate_params()
        config_content = self._build_config_content()
        repo_path = self._get_repo_path()
        
        RepositoryManager.add_repo_content(repo_path, config_content)
    
    def action_remove(self):
        """Remove repository configuration."""
        repo_path = self._get_repo_path()
        if not os.path.isfile(repo_path):
            LOG.info(f"Repository file does not exist: {repo_path}")
            return
            
        self._remove_config_file(repo_path)
    
    def action_post_apply(self):
        """Apply all pending repository changes."""
        RepositoryManager.apply_changes()
    
    def _get_repo_path(self):
        """Get full path to the repository file."""
        name = self.resource.repo_file_name
        return f"{self.repo_config_dir}/{name}{self.repo_file_extension}"
    
    def _validate_params(self):
        """Validate required resource parameters."""
        required = ["repo_file_name", "repo_id", "base_url"]
        missing = [param for param in required if not getattr(self.resource, param, None)]
        
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
    
    def _build_config_content(self):
        """Build repository configuration content."""
        template = self.resource.repo_template or self._get_default_template()
        context = {
            "repo_id": self.resource.repo_id,
            "base_url": self.resource.base_url,
            "mirror_list": getattr(self.resource, "mirror_list", ""),
            "components": getattr(self.resource, "components", []),
        }
        
        return InlineTemplate(template, **context).get_content()
    
    def _get_default_template(self):
        """Get OS-specific default template."""
        raise NotImplementedError(
            "Default template not implemented for this provider"
        )
    
    def _remove_config_file(self, repo_path):
        """Remove the repository file."""
        File(repo_path, action="delete")
        self._run_post_removal()


class RHELRepositoryProvider(BaseRepositoryProvider):
    """Repository provider for RHEL-based systems (CentOS, Amazon Linux, etc.)"""
    repo_config_dir = "/etc/yum.repos.d"
    repo_file_extension = ".repo"
    
    @staticmethod
    def _get_default_template():
        return (
            "[{{ repo_id }}]\n"
            "name={{ repo_id }} repository\n"
            "baseurl={{ base_url }}\n"
            "{% if mirror_list %}mirrorlist={{ mirror_list }}{% endif %}\n"
            "enabled=1\n"
            "gpgcheck=0\n"
        )
    
    def _run_post_removal(self):
        """RHEL-based systems usually don't need post-removal action."""
        pass


class SUSERepositoryProvider(RHELRepositoryProvider):
    """Repository provider for SUSE-based systems."""
    repo_config_dir = "/etc/zypp/repos.d"
    CLEAN_CMD = ["zypper", "clean", "--all"]
    
    def _run_post_removal(self):
        """Clean SUSE repository cache."""
        LOG.info("Cleaning zypper package cache")
        checked_call(self.CLEAN_CMD, sudo=True)
    
    @classmethod
    def _run_post_update(cls, repo_path):
        """Run post-update for SUSE repositories."""
        cls._run_post_removal()


class UbuntuRepositoryProvider(BaseRepositoryProvider):
    """Repository provider for Ubuntu/Debian systems."""
    repo_config_dir = "/etc/apt/sources.list.d"
    repo_file_extension = ".list"
    UPDATE_CMD = [
        "apt-get", "update", "-qq",
        "-o", "Dir::Etc::sourcelist=sources.list.d/{repo_file}",
        "-o", "Dir::Etc::sourceparts=-",
        "-o", "APT::Get::List-Cleanup=0"
    ]
    KEY_TOOLS = ("apt-key", "adv", "--recv-keys", "--keyserver", "keyserver.ubuntu.com")
    MISSING_KEY_REGEX = r"The following signatures couldn't be verified because the public key is not available: NO_PUBKEY ([A-Z0-9]+)"
    
    def _get_default_template(self):
        return "deb {{ base_url }} {{ ' '.join(components) }}"
    
    def _run_post_removal(self):
        """Run distro-specific actions after repository removal."""
        self._update_package_index(remove=True)
    
    def _update_package_index(self, remove=False):
        """Update package index."""
        if remove:
            cmd = ["apt-get", "update", "-qq"]
            Execute(cmd, sudo=True)
            return
            
        file_name = os.path.basename(self._get_repo_path())
        cmd = [
            part.format(repo_file=file_name)
            if "{repo_file}" in part else part
            for part in self.UPDATE_CMD
        ]
        
        try:
            ret, out = call(cmd, sudo=True, quiet=False)
            self._handle_missing_keys(out)
        except ExecutionFailed as e:
            self._handle_missing_keys(e.out)
            raise
    
    def _handle_missing_keys(self, output):
        """Handle missing GPG keys."""
        missing_keys = set(re.findall(self.MISSING_KEY_REGEX, output))
        
        for key in missing_keys:
            LOG.warning(f"Adding missing public key: {key}")
            Execute(
                self.KEY_TOOLS + (key,),
                timeout=15,
                ignore_failures=True,
                sudo=True,
            )
    
    @classmethod
    def _run_post_update(cls, repo_path):
        """Run distro-specific actions after repository update."""
        # Create provider instance to reuse update logic
        provider = cls(resource=None)  # Pseudo-instance for static access
        provider._update_package_index()


def get_repository_provider(os_family=None):
    """Factory function to get the appropriate repository provider."""
    os_family = os_family or OS_CURRENT_FAMILY
    os_type = REPO_MANAGERS_BY_OS.get(os_family.lower())
    
    providers = {
        "RHEL": RHELRepositoryProvider,
        "SUSE": SUSERepositoryProvider,
        "UBUNTU": UbuntuRepositoryProvider,
    }
    
    provider_class = providers.get(os_type)
    if not provider_class:
        raise RuntimeError(f"Unsupported OS family: {os_family}")
    
    return provider_class

