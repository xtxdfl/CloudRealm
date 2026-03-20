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

Enhanced HDFS Command Execution Provider
"""

from resource_management.core.providers import Provider
from resource_management.core import shell
from resource_management.core.resources import Execute
from resource_management.libraries.functions.format import format
import logging

class ExecuteHDFSProvider(Provider):
    """
    Provides enhanced execution of HDFS commands with:
    - Automatic command formatting
    - Secure argument handling
    - Configurable execution environment
    - Robust error handling and retry mechanisms
    """
    
    def action_run(self):
        """
        Execute the HDFS command with proper configuration and environment setup.
        
        Handles both string and list/tuple command formats securely.
        """
        # Validate and initialize essential parameters
        self._validate_resource_parameters()
        
        # Format the HDFS command with configuration
        hdfs_command = self._build_hdfs_command()
        
        # Prepare execution environment
        execution_env = self._prepare_execution_environment()
        
        # Execute with retry mechanism
        self._execute_with_retry(hdfs_command, execution_env)
    
    def _validate_resource_parameters(self):
        """Ensure all required resource parameters are properly set."""
        if not hasattr(self.resource, 'conf_dir') or not self.resource.conf_dir:
            raise ValueError("HDFS configuration directory (conf_dir) is required")
            
        if not hasattr(self.resource, 'command') or not self.resource.command:
            raise ValueError("HDFS command to execute is required")
    
    def _build_hdfs_command(self):
        """Construct the fully formatted HDFS command with configuration context."""
        command = self.resource.command
        
        # Handle different command types securely
        if isinstance(command, (list, tuple)):
            # Prepend HDFS command with configuration context
            return f"hdfs --config {self.resource.conf_dir} {' '.join(self._quote_arguments(command))}"
        else:
            # Handle string command safely
            return f"hdfs --config {self.resource.conf_dir} {command}"
    
    def _quote_arguments(self, args):
        """
        Securely quote command arguments to prevent injection vulnerabilities.
        
        Args:
            args (list/tuple): Command arguments to be quoted
            
        Returns:
            list: Safely quoted command arguments
        """
        return [shell.quote_bash_args(arg) for arg in args]
    
    def _prepare_execution_environment(self):
        """Prepare the environment configuration for command execution."""
        return {
            'user': getattr(self.resource, 'user', None),
            'path': getattr(self.resource, 'bin_dir', None),
            'environment': getattr(self.resource, 'environment', None)
        }
    
    def _execute_with_retry(self, command, env_config):
        """
        Execute the command with configurable retry mechanisms.
        
        Args:
            command (str): The full command to execute
            env_config (dict): Environment configuration for execution
        """
        try:
            Execute(
                command,
                user=env_config['user'],
                tries=getattr(self.resource, 'tries', 1),
                try_sleep=getattr(self.resource, 'try_sleep', 0),
                logoutput=getattr(self.resource, 'logoutput', True),
                path=env_config['path'],
                environment=env_config['environment'],
            )
        except Exception as e:
            logging.error(f"HDFS command execution failed: {e}")
            raise
