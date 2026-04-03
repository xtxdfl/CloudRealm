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

Enhanced Template-Based Configuration Provider
"""

import os
import logging
from resource_management.core import Environment
from resource_management.core.resources import File
from resource_management.core.providers import Provider
from resource_management.core.source import Template
from resource_management.libraries.functions.format import format

# Create logger
LOG = logging.getLogger(__name__)

class TemplateConfigProvider(Provider):
    """
    Enhanced template-based configuration file provider.
    
    Features:
    - Intelligently resolves template sources
    - Validates all required parameters
    - Detailed logging of operations
    - Flexible template naming conventions
    - Atomic updates with temporary files
    """
    
    def action_create(self):
        """Render and deploy configuration file from template."""
        try:
            # Validate and preprocess inputs
            file_path, template_name = self._prepare_template_rendering()
            
            LOG.info(f"Generating config file from template: {template_name} → {file_path}")
            
            # Create configuration file from template
            File(
                file_path,
                owner=self.resource.owner or self._get_default_owner(),
                group=self.resource.group or self._get_default_group(),
                mode=self.resource.mode or 0o644,  # Default to rw-r--r--
                content=Template(
                    template_name, 
                    extra_imports=self.resource.extra_imports,
                    delimiters=self.resource.delimiters
                ),
                encoding=self.resource.encoding or 'utf-8',
                backup=self.resource.backup or True,
                atomic_update=True
            )
            
            LOG.info(f"Successfully deployed config file: {file_path}")
            
        except Exception as e:
            LOG.error(f"Failed to generate config file: {str(e)}")
            # Consider wrapping in a custom ConfigurationError
            raise

    def action_remove(self):
        """Remove configuration file if exists."""
        file_path = self.resource.name
        if os.path.exists(file_path):
            LOG.info(f"Removing config file: {file_path}")
            File(file_path, action="delete")
        else:
            LOG.debug(f"Config file not found, nothing to remove: {file_path}")

    def _prepare_template_rendering(self):
        """Validate inputs and determine template source."""
        # Validate required parameters
        if not hasattr(self.resource, 'name') or not self.resource.name:
            raise ValueError("Configuration file path is required (resource.name)")
        
        file_path = os.path.abspath(self.resource.name)
        file_base = os.path.basename(file_path)
        
        # Determine template source
        if hasattr(self.resource, 'template_tag') and self.resource.template_tag:
            template_name = format("{file_base}-{template_tag}.j2", 
                                  file_base=file_base,
                                  template_tag=self.resource.template_tag)
        elif hasattr(self.resource, 'template_name') and self.resource.template_name:
            template_name = self.resource.template_name
            if not template_name.endswith('.j2'):
                template_name += '.j2'
        else:
            template_name = format("{file_base}.j2", file_base=file_base)
        
        # Ensure template has .j2 extension
        if not template_name.endswith('.j2'):
            template_name += '.j2'
            
        return file_path, template_name

    def _get_default_owner(self):
        """Get default file owner based on execution context."""
        # In a real implementation, integrate with your security model
        return "root" if os.name != 'nt' else "Administrator"

    def _get_default_group(self):
        """Get default group based on execution context."""
        # In a real implementation, integrate with your security model
        return "root" if os.name != 'nt' else "Administrators"
