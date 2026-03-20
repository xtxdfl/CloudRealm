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

cloud Agent - Enhanced HDFS Resource Management
"""

import cloud_simplejson as json
import grp
import os
import pwd
import re
import time
import logging
from urllib.parse import urlparse
from resource_management.core import shell, sudo
from resource_management.core.base import Fail
from resource_management.core.environment import Environment
from resource_management.core.logger import Logger
from resource_management.core.providers import Provider
from resource_management.core.resources.system import Execute, File
from resource_management.libraries.functions.is_empty import is_empty
from resource_management.libraries.functions import format, namenode_ha_utils
from resource_management.libraries.functions.get_user_call_output import get_user_call_output
from resource_management.libraries.functions.hdfs_utils import is_https_enabled_in_hdfs

# Constants
JSON_PATH = "/var/lib/cloud-agent/tmp/hdfs_resources_{timestamp}.json"
JAR_PATH = "/var/lib/cloud-agent/lib/fast-hdfs-resource.jar"

RESOURCE_TO_JSON_FIELDS = {
    "target": "target",
    "type": "type",
    "action": "action",
    "source": "source",
    "owner": "owner",
    "group": "group",
    "mode": "mode",
    "recursive_chown": "recursiveChown",
    "recursive_chmod": "recursiveChmod",
    "change_permissions_for_parents": "changePermissionforParents",
    "manage_if_exists": "manageIfExists",
    "dfs_type": "dfs_type",
}

EXCEPTIONS_TO_RETRY = {
    "FileNotFoundException": (" does not have any open files", 6, 30),
    "LeaseExpiredException": ("", 20, 6),
    "RetriableException": ("", 20, 6),
}

DFS_WHICH_SUPPORT_WEBHDFS = ["hdfs"]

class HdfsResourceJar:
    """Manages HDFS resources using a custom JAR implementation."""
    
    def action_delayed(self, action_name, main_resource):
        """Queue resource operations for batch processing."""
        dfs_type = main_resource.resource.dfs_type
        
        if main_resource.resource.nameservices is None and main_resource.has_core_configs:
            nameservices = namenode_ha_utils.get_nameservices(main_resource.resource.hdfs_site)
        else:
            nameservices = main_resource.resource.nameservices

        # Handle federated clusters
        if not nameservices or len(nameservices) < 2:
            self._delayed_action_for_nameservice(None, action_name, main_resource)
        else:
            for ns in nameservices:
                try:
                    nameservice = f"{main_resource.default_protocol}://{ns}"
                    self._delayed_action_for_nameservice(nameservice, action_name, main_resource)
                except namenode_ha_utils.NoActiveNamenodeException:
                    if len(nameservices) > 1:
                        Logger.exception(f"Skipping nameservice {ns}: No active namenode")
                    else:
                        raise

    def _delayed_action_for_nameservice(self, nameservice, action_name, main_resource):
        """Prepare resource JSON for specific nameservice."""
        env = Environment.get_instance()
        env_key = "hdfs_files_sudo" if main_resource.create_as_root else "hdfs_files"

        if env_key not in env.config:
            env.config[env_key] = []

        resource = self._build_resource_dict(action_name, main_resource, nameservice)
        env.config[env_key].append(resource)
        
    def _build_resource_dict(self, action_name, main_resource, nameservice):
        """Construct resource dictionary for JSON serialization."""
        resource = {}
        for field, json_field in RESOURCE_TO_JSON_FIELDS.items():
            if field == "action":
                resource[json_field] = action_name
            elif field == "mode" and main_resource.resource.mode:
                resource[json_field] = oct(main_resource.resource.mode)[2:]
            elif field == "manage_if_exists":
                resource[json_field] = main_resource.manage_if_exists
            else:
                value = getattr(main_resource.resource, field, None)
                if value:
                    resource[json_field] = value
        
        resource["nameservice"] = nameservice
        return resource

    def action_execute(self, main_resource, sudo_flag=False):
        """Execute batched resource operations using JAR implementation."""
        env = Environment.get_instance()
        env_key = "hdfs_files_sudo" if sudo_flag else "hdfs_files"

        if not self._has_resources_to_process(env, env_key):
            return

        user = self._get_execution_user(main_resource, sudo_flag)
        self._perform_kinit_if_needed(main_resource)
        
        json_path = self._create_resource_json(env, env_key, user)
        self._execute_jar(main_resource, json_path, user, sudo_flag)
        self._cleanup_resources(env, env_key)

    def _has_resources_to_process(self, env, env_key):
        """Check if there are resources to process."""
        return bool(env.config.get(env_key))

    def _get_execution_user(self, main_resource, sudo_flag):
        """Determine user for execution based on context."""
        if sudo_flag:
            return None
        main_resource.assert_parameter_is_set("user")
        return main_resource.resource.user

    def _perform_kinit_if_needed(self, main_resource):
        """Perform Kerberos authentication if required."""
        if main_resource.resource.security_enabled:
            self._enhanced_kinit(main_resource)

    def _enhanced_kinit(self, main_resource):
        """Enhanced Kerberos initialization with error checking."""
        keytab = main_resource.resource.keytab
        kinit_path = main_resource.resource.kinit_path_local
        principal = main_resource.resource.principal_name
        user = main_resource.resource.user

        # Validate keytab file
        if not os.path.isfile(keytab):
            raise Fail(f"Keytab file not found: {keytab}")
        
        # Validate kinit executable
        if not os.path.exists(kinit_path):
            raise Fail(f"kinit not found at: {kinit_path}")
        
        cmd = format("{kinit_path} -kt {keytab} {principal}")
        Logger.info(f"Performing kinit for principal: {principal}")
        Execute(cmd, user=user, logoutput=True)

    def _create_resource_json(self, env, env_key, user):
        """Create JSON file with resource definitions."""
        timestamp = str(time.time()).replace('.', '')
        json_path = JSON_PATH.format(timestamp=timestamp)
        File(json_path, 
             owner=user, 
             content=json.dumps(env.config[env_key],
             encoding='utf-8'))
        return json_path

    def _execute_jar(self, main_resource, json_path, user, sudo_flag):
        """Execute resource management JAR."""
        Execute(
            ("hadoop", "--config", main_resource.resource.hadoop_conf_dir, "jar", JAR_PATH, json_path),
            user=user,
            path=[main_resource.resource.hadoop_bin_dir],
            logoutput=main_resource.resource.logoutput,
            sudo=sudo_flag,
        )

    def _cleanup_resources(self, env, env_key):
        """Cleanup processed resources."""
        env.config[env_key] = []

class WebHDFSCallException(Fail):
    """Custom exception for WebHDFS operations."""
    
    def __init__(self, message, result_message):
        self.result_message = result_message
        super().__init__(message)

    def get_exception_name(self):
        """Extract exception name from response."""
        rem_ex = self.result_message.get('RemoteException', {})
        return rem_ex.get('exception') if 'exception' in rem_ex else None

    def get_exception_text(self):
        """Extract exception message from response."""
        rem_ex = self.result_message.get('RemoteException', {})
        return rem_ex.get('message') if 'message' in rem_ex else None

class WebHDFSUtil:
    """Utility class for WebHDFS operations."""
    
    VALID_STATUS_CODES = ["200", "201"]
    
    def __init__(self, hdfs_site, nameservice, run_user, security_enabled, logoutput=None):
        self.is_https_enabled = is_https_enabled_in_hdfs(
            hdfs_site.get("dfs.http.policy", "HTTP_ONLY"),
            hdfs_site.get("dfs.https.enable", "false")
        )
        
        prop = "dfs.namenode.https-address" if self.is_https_enabled else "dfs.namenode.http-address"
        address = namenode_ha_utils.get_property_for_active_namenode(
            hdfs_site, nameservice, prop, security_enabled, run_user
        )
        
        protocol = "https" if self.is_https_enabled else "http"
        self.address = f"{protocol}://{address}"
        self.run_user = run_user
        self.security_enabled = security_enabled
        self.logoutput = logoutput

    @staticmethod
    def get_default_protocol(default_fs, dfs_type):
        """Detect the applicable protocol based on filesystem configuration."""
        fs_protocol = urlparse(default_fs).scheme.lower()
        return dfs_type.lower() if fs_protocol == "viewfs" else fs_protocol

    @staticmethod
    def is_webhdfs_available(is_webhdfs_enabled, default_protocol):
        """Check if WebHDFS is enabled and supported."""
        return is_webhdfs_enabled and default_protocol in DFS_WHICH_SUPPORT_WEBHDFS

    def run_command(self, target, operation, method="POST", **kwargs):
        """Execute WebHDFS command with retry mechanism."""
        retry_count = 0
        max_retries = 3
        delay_factor = 1
        
        while retry_count < max_retries:
            try:
                return self._execute_webhdfs(target, operation, method, **kwargs)
            except WebHDFSCallException as ex:
                exception_name = ex.get_exception_name()
                exception_text = ex.get_exception_text()

                # Check if exception is retriable
                if exception_name in EXCEPTIONS_TO_RETRY:
                    if retry_count == max_retries - 1:
                        raise
                    
                    _, count, delay = EXCEPTIONS_TO_RETRY[exception_name]
                    Logger.info(f"Retryable error ({exception_name}): Retrying in {delay} seconds")
                    time.sleep(delay)
                    retry_count += 1
                else:
                    raise

    def _execute_webhdfs(self, target, operation, method, **kwargs):
        """Direct execution of WebHDFS commands."""
        target = HdfsResourceProvider.parse_path(target)
        if not target:
            raise Fail("Target cannot be empty")

        url = f"{self.address}/webhdfs/v1{target}?op={operation}"
        
        # Add parameters
        if 'params' in kwargs:
            for k, v in kwargs['params'].items():
                url += f"&{k}={v}"
        
        curl_cmd = self._build_curl_command(method, url, kwargs.get('file'))
        status, out, err = self._call_webhdfs(curl_cmd, kwargs.get('ignore_status_codes', []))
        
        try:
            response = json.loads(out)
        except ValueError:
            response = out

        if self._is_failed(status, response, kwargs.get('assertable_result', True)):
            self._handle_failure(curl_cmd, status, response, err)
            
        return response

    def _build_curl_command(self, method, url, file_path=None):
        """Construct CURL command for WebHDFS request."""
        cmd = ["curl", "-sS", "-L", "-w", "%{http_code}", "-X", method]
        
        if method == "PUT" and file_path:
            cmd.extend([
                "--data-binary", f"@{file_path}",
                "-H", "Content-Type: application/octet-stream"
            ])
        else:
            cmd.extend(["-d", "", "-H", "Content-Length: 0"])
        
        cmd.extend(self._get_authentication_flags())
        cmd.append(url)
        return cmd

    def _get_authentication_flags(self):
        """Return security flags based on authentication configuration."""
        flags = []
        if self.security_enabled:
            flags.extend(["--negotiate", "-u", ":"])
        if self.is_https_enabled:
            flags.append("-k")
        return flags

    def _call_webhdfs(self, cmd, ignore_codes):
        """Execute CURL command and process response."""
        _, out, err = get_user_call_output(
            cmd,
            user=self.run_user,
            logoutput=self.logoutput,
            quiet=False
        )
        status = out[-3:]
        response = out[:-3]  # Remove status code
        return status, response, err

    def _is_failed(self, status, response, assertable):
        """Check if request failed."""
        if status not in self.VALID_STATUS_CODES:
            return True
        if assertable and isinstance(response, dict) and response.get("boolean") is False:
            return True
        return False

    def _handle_failure(self, cmd, status, response, err):
        """Process failed WebHDFS request."""
        err_msg = f"WebHDFS Command Failed (Code: {status}): {cmd}\n"
        if isinstance(response, dict):
            err_msg += json.dumps(response, indent=2)
        else:
            err_msg += response
            
        err_msg += f"\n\nError Output:\n{err}"
        raise WebHDFSCallException(err_msg, response)

class HdfsResourceWebHDFS:
    """Implement HDFS resource management using WebHDFS API."""
    
    MAX_FILES_RECURSIVE = 1000
    MAX_DIRS_RECURSIVE = 250

    def action_delayed(self, action_name, main_resource):
        """Prepare resource operation for execution."""
        main_resource.assert_parameter_is_set("user")
        
        if main_resource.resource.security_enabled:
            HdfsResourceJar()._enhanced_kinit(main_resource)
            
        nameservices = (
            namenode_ha_utils.get_nameservices(main_resource.resource.hdfs_site)
            if main_resource.resource.nameservices is None
            else main_resource.resource.nameservices
        )
        
        if not nameservices:
            self._process_resource(None, action_name, main_resource)
        else:
            for ns in nameservices:
                try:
                    self._process_resource(ns, action_name, main_resource)
                except namenode_ha_utils.NoActiveNamenodeException:
                    if len(nameservices) > 1:
                        Logger.exception(f"Skipping nameservice {ns}: No active namenode")
                    else:
                        raise

    def _process_resource(self, nameservice, action_name, main_resource):
        """Process resource for specific nameservice."""
        self.util = WebHDFSUtil(
            main_resource.resource.hdfs_site,
            nameservice,
            main_resource.resource.user,
            main_resource.resource.security_enabled,
            main_resource.resource.logoutput,
        )
        
        self.mode = oct(main_resource.resource.mode)[2:] if main_resource.resource.mode else None
        self.main_resource = main_resource
        
        self.target_status = self._get_file_status(main_resource.resource.target)
        
        if not self._should_process_resource():
            return
            
        try:
            # Execute resource operation
            if action_name == "create":
                self._create_resource()
                self._apply_permissions()
            elif action_name == "download":
                self._download_resource()
            else:
                self._delete_resource()
        except Exception as e:
            Logger.error(f"Failed to process resource: {e}")
            raise

    def _should_process_resource(self):
        """Determine if resource should be processed."""
        if self.main_resource.manage_if_exists == False and self.target_status:
            Logger.info(f"Skipping unmanaged resource: {self.main_resource.resource.target}")
            return False
        
        parsed = HdfsResourceProvider.parse_path(self.main_resource.resource.target)
        if parsed in self.main_resource.ignored_resources_list:
            Logger.info(f"Skipping ignored resource: {parsed}")
            return False
            
        return True

    # (其他方法省略以保持简洁，但会包含完整的下载和权限操作实现)

class HdfsResourceProvider(Provider):
    """Provider for HDFS resource management operations."""
    
    def __init__(self, resource):
        super().__init__(resource)
        
        # Initialize core configurations
        self.has_core_configs = not is_empty(getattr(resource, "default_fs"))
        self.ignored_resources_list = self._get_ignore_list(
            self.resource.hdfs_resource_ignore_file
        )
        
        # Determine execution mode
        self.create_as_root = False
        self.webhdfs_enabled = False
        self.can_use_webhdfs = False
        
        if self.has_core_configs:
            self._configure_for_core()

    def _get_ignore_list(self, ignore_file):
        """Load list of resources to ignore."""
        if not ignore_file or not os.path.exists(ignore_file):
            return []
            
        with open(ignore_file) as f:
            return [
                self.parse_path(line.strip())
                for line in f
                if line.strip()
            ]

    def _configure_for_core(self):
        """Configure provider based on core HDFS settings."""
        self.assert_parameter_is_set("dfs_type")
        self.fsType = getattr(self.resource, "dfs_type").lower()
        
        self.default_protocol = WebHDFSUtil.get_default_protocol(
            self.resource.default_fs, 
            self.fsType
        )
        
        self.can_use_webhdfs = True
        
        # Check protocol compatibility
        path_protocol = urlparse(self.resource.target).scheme.lower()
        self.create_as_root = (
            path_protocol == "file" or 
            (self.default_protocol == "file" and not path_protocol)
        )
        
        if path_protocol and path_protocol != self.default_protocol:
            self.can_use_webhdfs = False
            Logger.info(
                f"Using JAR method - Protocol mismatch: "
                f"Path={path_protocol}, Default={self.default_protocol}"
            )
        
        # Enable WebHDFS if supported
        if self.fsType == "hdfs":
            self.webhdfs_enabled = self.resource.hdfs_site.get("dfs.webhdfs.enabled", False)

    @staticmethod
    def parse_path(path):
        """Normalize HDFS path by removing protocol and cleaning format."""
        match = re.match(r"[a-zA-Z]+://(?:[^/]+)?(/.+)", path) or re.match(r"[a-zA-Z]+://(/.+)", path)
        return re.sub(r"[/]+", "/", (match.group(1) if match else path).replace(" ", "%20"))

    def action_delayed(self, action_name):
        """Initiate resource operation preparation."""
        self.assert_parameter_is_set("type")
        executor = self._select_executor()
        executor.action_delayed(action_name, self)

    def _select_executor(self):
        """Select appropriate resource executor (WebHDFS or JAR)."""
        if self.can_use_webhdfs and WebHDFSUtil.is_webhdfs_available(
            self.webhdfs_enabled, 
            self.default_protocol
        ):
            return HdfsResourceWebHDFS()
        return HdfsResourceJar()

    # (Action methods and other helpers omitted for brevity)
    
    def assert_parameter_is_set(self, param):
        """Validate required resource parameter is set."""
        if not getattr(self.resource, param):
            raise Fail(f"Missing required parameter: {param}")
        return True
