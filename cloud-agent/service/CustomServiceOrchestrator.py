#!/usr/bin/env python3

# -*- coding: utf-8 -*-


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

import sys

import uuid

import logging

import threading

import cloud_simplejson as json

import subprocess

from collections import defaultdict

from configparser import NoOptionError

from typing import Dict, Any, Optional, Tuple, List



from cloud_commons import shell

from cloud_commons.constants import AGENT_TMP_DIR

from resource_management.libraries.functions.log_process_information import log_process_information

from resource_management.core.utils import PasswordString

from resource_management.core.encryption import ensure_decrypted

from resource_management.core import shell as rmf_shell



from models.commands import AgentCommand

from Utils import Utils

from AgentException import AgentException

from PythonExecutor import PythonExecutor





logger = logging.getLogger(__name__)





class CustomServiceOrchestrator:

    """

    Advanced Service Orchestration System

    =====================================

    

    This system provides comprehensive management of service component execution, 

    including credential handling, configuration assembly, and command lifecycle 

    management. Key features:

    

    - Credential store encryption management

    - Automated JCEKS file generation

    - Component status monitoring

    - Parallel command execution safety

    - Smart command cancellation

    - Background task management

    """

    

    # Execution constants

    SCRIPT_TYPE_PYTHON = "PYTHON"

    COMMAND_NAME_STATUS = "STATUS"

    CUSTOM_ACTION_COMMAND = "ACTIONEXECUTE"

    CUSTOM_COMMAND_COMMAND = "CUSTOM_COMMAND"

    FREQUENT_COMMANDS = [COMMAND_NAME_STATUS, "HEARTBEAT"]

    DONT_DEBUG_FAILURES_FOR_COMMANDS = FREQUENT_COMMANDS

    DONT_BACKUP_LOGS_FOR_COMMANDS = FREQUENT_COMMANDS

    

    # Credential store configuration

    DEFAULT_CREDENTIAL_SHELL_LIB_PATH = "/var/lib/cloud-agent/cred/lib"

    DEFAULT_CREDENTIAL_CONF_DIR = "/var/lib/cloud-agent/cred/conf"

    DEFAULT_CREDENTIAL_SHELL_CMD = "org.apache.hadoop.security.alias.CredentialShell"

    CREDENTIAL_PROVIDER_PROPERTY_NAME = "hadoop.security.credential.provider.path"

    CREDENTIAL_STORE_CLASS_PATH_NAME = "credentialStoreClassPath"

    

    # Topic constants

    HOSTS_LIST_KEY = "all_hosts"

    PING_PORTS_KEY = "all_ping_ports"

    RACKS_KEY = "all_racks"

    IPV4_ADDRESSES_KEY = "all_ipv4_ips"

    cloud_SERVER_HOST = "cloud_server_host"

    cloud_SERVER_PORT = "cloud_server_port"

    cloud_SERVER_USE_SSL = "cloud_server_use_ssl"

    

    def __init__(self, initializer_module):

        """Initialize the orchestrator with application context"""

        self.initializer = initializer_module

        self.configuration_builder = initializer_module.configuration_builder

        self.host_params_cache = initializer_module.host_level_params_cache

        self.config = initializer_module.config

        self.hooks_orchestrator = initializer_module.hooks_orchestrator

        self.file_cache = initializer_module.file_cache

        

        # Path configurations

        self.tmp_dir = self.config.get("agent", "prefix")

        self.exec_tmp_dir = AGENT_TMP_DIR

        self.encryption_key = None

        

        # Status command file patterns

        self.status_commands_stdout = os.path.join(self.tmp_dir, "status_command_stdout_{0}.txt")

        self.status_commands_stderr = os.path.join(self.tmp_dir, "status_command_stderr_{0}.txt")

        self.status_structured_out = os.path.join(self.tmp_dir, "status_structured-out-{0}.json")

        

        # Security configurations

        self.force_https_protocol = self.config.get_force_https_protocol_name()

        self.ca_cert_file_path = self.config.get_ca_cert_file_path()

        self.credential_shell_lib_path = self._get_credential_path(

            "security", "credential_lib_dir", self.DEFAULT_CREDENTIAL_SHELL_LIB_PATH

        )

        self.credential_conf_dir = self._get_credential_path(

            "security", "credential_conf_dir", self.DEFAULT_CREDENTIAL_CONF_DIR

        )

        self.credential_shell_cmd = self.config.get(

            "security", "credential_shell_cmd", self.DEFAULT_CREDENTIAL_SHELL_CMD

        )

        

        # Command tracking

        self.commands_in_progress_lock = threading.RLock()

        self.commands_in_progress = {}

        self.commands_for_component = defaultdict(lambda: defaultdict(int))

        logger.info("Service orchestrator initialized")



    # ==================== Command Lifecycle Management ====================

    

    def map_task_to_process(self, task_id: str, process_id: int) -> None:

        """Map a task ID to its process ID for cancellation tracking"""

        with self.commands_in_progress_lock:

            logger.debug("Mapping task %s to PID %s", task_id, process_id)

            self.commands_in_progress[task_id] = process_id

    

    def cancel_command(self, task_id: str, reason: str) -> None:

        """Cancel an in-progress command and associated processes"""

        with self.commands_in_progress_lock:

            if task_id in self.commands_in_progress:

                pid = self.commands_in_progress[task_id]

                logger.info(

                    "Canceling command %s (PID %s): %s", 

                    task_id, pid, reason

                )

                log_process_information(logger)

                

                # Mark as canceled before killing the process

                self.commands_in_progress[task_id] = reason

                shell.kill_process_with_children(pid)

            else:

                logger.warning("No process found for task %s", task_id)

    

    def commandsRunningForComponent(self, clusterId: str, componentName: str) -> bool:

        """Check if commands are running for a specific component"""

        return self.commands_for_component[clusterId][componentName] > 0

    

    # ==================== Credential Management ====================

    

    def _get_credential_path(self, section: str, option: str, default: str) -> str:

        """Get a credential path with default handling"""

        path = self.config.get(section, option, fallback=default)

        if option == "credential_lib_dir":

            return os.path.join(path, "*")  # Wildcard for JAR files

        return path

    

    def getProviderDirectory(self, service_name: str) -> str:

        """Get the service-specific credential directory"""

        return os.path.join(self.credential_conf_dir, service_name.lower())

    

    def _generate_jceks(self, command_json: Dict[str, Any]) -> Dict[str, Any]:

        """

        Generate JCEKS files for credential store support

        Returns updated command JSON with sensitive data removed

        """

        configtype_credentials = {}

        cred_info = command_json["serviceLevelParams"].get("configuration_credentials", {})

        

        if not cred_info:

            logger.info("No credentials found for encryption")

            return command_json

        

        for config_type, password_props in cred_info.items():

            if config_type not in command_json["configurations"]:

                continue

                

            config = command_json["configurations"][config_type]

            credentials = self._extract_credentials(password_props, config)

            

            if credentials:

                configtype_credentials[config_type] = credentials

                self._remove_plaintext_passwords(password_props, config)

        

        if configtype_credentials:

            self._process_config_credentials(configtype_credentials, command_json)

        

        return command_json

    

    def _extract_credentials(

        self, password_props: Dict[str, str], config: Dict[str, str]

    ) -> Dict[str, str]:

        """Extract credentials from configuration"""

        credentials = {}

        for key_name, value_name in password_props.items():

            if key_name == value_name:

                if value_name in config:

                    credentials[key_name] = config[value_name]

            else:

                keyname_parts = key_name.split(":")

                alias_key = keyname_parts[0]

                config_ref = config if len(keyname_parts) < 2 else self._get_config_ref(config, keyname_parts[1])

                

                if alias_key in config_ref and value_name in config:

                    alias = config_ref[alias_key]

                    credentials[alias] = config[value_name]

        return credentials

    

    def _get_config_ref(self, config, config_type):

        """Get configuration reference by type"""

        # Implement logic to get cross-configuration reference if needed

        return config  # Placeholder - implementation dependent on system architecture

    

    def _remove_plaintext_passwords(

        self, password_props: Dict[str, str], config: Dict[str, str]

    ) -> None:

        """Remove plaintext passwords from configuration"""

        for value_name in set(password_props.values()):

            config.pop(value_name, None)

    

    def _process_config_credentials(self, credentials, command_json):

        """Process extracted credentials and update configuration"""

        java_bin = f"{command_json['cloudLevelParams']['java_home']}/bin/java"

        serviceName = command_json["serviceName"]

        command_json["credentialStoreEnabled"] = "true"

        

        for config_type, creds in credentials.items():

            provider_path = self._create_jceks_file(

                config_type, creds, command_json, java_bin, serviceName

            )

            

            # Update configuration with JCEKS provider path

            config = command_json["configurations"][config_type]

            config[self.CREDENTIAL_PROVIDER_PROPERTY_NAME] = provider_path

            config[self.CREDENTIAL_STORE_CLASS_PATH_NAME] = self.credential_shell_lib_path

    

    def _create_jceks_file(

        self, config_type: str, credentials: Dict[str, str], 

        command_json: Dict[str, Any], java_bin: str, service_name: str

    ) -> str:

        """Create a JCEKS file for given credentials"""

        if "role" in command_json:

            provider_dir = os.path.join(self.getProviderDirectory(command_json["role"]), f"{config_type}.jceks")

        else:

            provider_dir = os.path.join(self.getProviderDirectory(service_name), f"{config_type}.jceks")

        

        # Remove existing JCEKS file

        if os.path.exists(provider_dir):

            os.remove(provider_dir)

        

        provider_path = f"jceks://file{provider_dir}"

        self._populate_jceks_file(provider_path, credentials, java_bin)

        os.chmod(provider_dir, 0o644)  # Set appropriate permissions

        

        return provider_path

    

    def _populate_jceks_file(

        self, provider_path: str, credentials: Dict[str, str], java_bin: str

    ) -> None:

        """Populate JCEKS file with credentials"""

        for alias, password in credentials.items():

            decrypted_pwd = ensure_decrypted(password, self.encryption_key)

            protected_pwd = PasswordString(decrypted_pwd)

            

            cmd = [

                java_bin,

                "-cp",

                self.credential_shell_lib_path,

                self.credential_shell_cmd,

                "create",

                alias,

                "-value",

                protected_pwd,

                "-provider",

                provider_path

            ]

            logger.debug("Executing credential command: %s", " ".join(cmd))

            

            # Execute and handle command result

            try:

                result = subprocess.run(cmd, check=True, text=True, 

                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                logger.debug("Credential creation succeeded:\n%s", result.stdout)

            except subprocess.CalledProcessError as e:

                logger.error(

                    "Credential creation failed (exit %d):\n%s\n%s", 

                    e.returncode, e.stdout, e.stderr

                )

                raise AgentException("JCEKS file creation failed") from e

    

    # ==================== Command Execution ====================

    

    def runCommand(

        self,

        command_header: Dict[str, Any],

        tmpoutfile: str,

        tmperrfile: str,

        forced_command_name: Optional[str] = None,

        override_output_files: bool = True,

        retry: bool = False,

        is_status_command: bool = False,

        tmpstrucoutfile: Optional[str] = None

    ) -> Dict[str, Any]:

        """

        Execute a service command with comprehensive management

        

        :param command_header: Command execution context

        :param tmpoutfile: Path for stdout capture

        :param tmperrfile: Path for stderr capture

        :param forced_command_name: Override command name

        :param override_output_files: Overwrite existing output files

        :param retry: Flag indicating command retry

        :param is_status_command: Status check special handling

        :param tmpstrucoutfile: Structured output path

        :return: Execution result dictionary

        """

        # Initialize execution context

        execution_context = {

            "incremented_component": False,

            "command": None,

            "cluster_id": None,

            "json_path": None,

            "result": None

        }

        

        try:

            # Prepare command execution

            self._prepare_execution(

                command_header, forced_command_name, 

                is_status_command, execution_context

            )

            

            # Setup structured output

            tmpstrucoutfile = self._get_structured_out_path(

                execution_context["task_id"], tmpstrucoutfile, is_status_command

            )

            

            # Handle credential encryption

            if self._needs_credential_generation(execution_context["command"], retry):

                self._generate_command_credentials(execution_context["command"])

            

            # Dump command to JSON file

            execution_context["json_path"] = self._dump_command_to_json(

                execution_context["command"], retry, is_status_command

            )

            

            # Get hooks and script sequence

            script_sequence = self._resolve_execution_script_sequence(

                execution_context["command"], execution_context["forced_command_name"]

            )

            

            # Execute the script sequence

            execution_context["result"] = self._execute_scripts(

                script_sequence,

                execution_context["json_path"],

                execution_context["command"],

                execution_context["task_id"],

                tmpoutfile,

                tmperrfile,

                tmpstrucoutfile,

                override_output_files,

                is_status_command

            )

            

            # Handle command cancellation

            if not execution_context["command"].get("__handle"):

                self._check_command_cancellation(

                    execution_context["task_id"],

                    execution_context["result"]

                )

            

            return execution_context["result"]

            

        except AgentException as ae:

            logger.exception("Service command execution failed")

            return {

                "stdout": str(ae),

                "stderr": str(ae),

                "structuredOut": "{}",

                "exitcode": 1

            }

        

        except Exception as e:

            logger.exception("Unexpected error during command execution")

            return {

                "stdout": f"System error: {str(e)}",

                "stderr": f"System error: {str(e)}",

                "structuredOut": "{}",

                "exitcode": 2

            }

        

        finally:

            # Cleanup resources

            self._cleanup_execution(execution_context)

    

    def _prepare_execution(

        self, command_header: Dict[str, Any], forced_command_name: Optional[str], 

        is_status_command: bool, context: Dict[str, Any]

    ) -> None:

        """Prepare command execution context"""

        context["command"] = self.generate_command(command_header)

        context["cluster_id"] = str(context["command"]["clusterId"])

        context["forced_command_name"] = forced_command_name

        context["task_id"] = context["command"].get("taskId", "status")

        

        # Track component-level commands

        if context["cluster_id"] not in {"-1", "null"} and not is_status_command:

            component = context["command"]["role"]

            self.commands_for_component[context["cluster_id"]][component] += 1

            context["incremented_component"] = True

            

            # Reset status for re-reporting after command completion

            if "serviceName" in context["command"]:

                service_component_name = f"{context['command']['serviceName']}/{component}"

                self.initializer.component_status_executor.reported_component_status[

                    context["cluster_id"]

                ][service_component_name]["STATUS"] = None

    

    def _get_structured_out_path(

        self, task_id: str, tmpstrucoutfile: Optional[str], is_status_command: bool

    ) -> str:

        """Determine structured output file path"""

        return (

            tmpstrucoutfile or 

            os.path.join(self.tmp_dir, f"status-structured-out-{task_id}.json") 

            if is_status_command

            else os.path.join(self.tmp_dir, f"structured-out-{task_id}.json")

        )

    

    def _needs_credential_generation(self, command: Dict[str, Any], retry: bool) -> bool:

        """Determine if credential generation is needed"""

        cred_enabled = command.get("serviceLevelParams", {}).get("credentialStoreEnabled")

        command_name = command.get("roleCommand")

        return (

            cred_enabled and

            command_name != self.COMMAND_NAME_STATUS and

            (not retry or command.get("agentLevelParams", {}).get("commandBeingRetried") != "true")

        )

    

    def _generate_command_credentials(self, command: Dict[str, Any]) -> None:

        """Generate credentials for command"""

        logger.info("Generating credentials for command %s", command.get("taskId", "unknown"))

        self._generate_jceks(command)

    

    def _resolve_execution_script_sequence(

        self, command: Dict[str, Any], forced_command_name: Optional[str]

    ) -> List[Tuple[str, str]]:

        """Resolve script execution sequence with hooks"""

        script_type = command["commandParams"]["script_type"].upper()

        if script_type != self.SCRIPT_TYPE_PYTHON:

            raise AgentException(f"Unsupported script type: {script_type}")

        

        # Determine script type and path

        command_name = forced_command_name or command.get("roleCommand", self.COMMAND_NAME_STATUS)

        script = command["commandParams"]["script"]

        

        if command_name == self.CUSTOM_ACTION_COMMAND:

            base_dir = self.file_cache.get_custom_actions_base_dir(command)

            scripts = [(os.path.join(base_dir, "scripts", script), base_dir)]

        else:

            base_dir = self.file_cache.get_service_base_dir(command)

            script_path = os.path.join(base_dir, script)

            if not os.path.exists(script_path):

                raise AgentException(f"Script not found: {script_path}")

            scripts = [(script_path, base_dir)]

        

        # Add hooks

        hooks = self.hooks_orchestrator.resolve_hooks(command, command_name)

        if hooks:

            scripts = hooks.pre_hooks + scripts + hooks.post_hooks

            

        # Filter out None values

        return [s for s in scripts if s]

    

    def _execute_scripts(

        self,

        script_sequence: List[Tuple[str, str]],

        json_path: str,

        command: Dict[str, Any],

        task_id: str,

        tmpoutfile: str,

        tmperrfile: str,

        tmpstrucoutfile: str,

        override_files: bool,

        is_status: bool

    ) -> Dict[str, Any]:

        """Execute a sequence of scripts"""

        command_name = command.get("roleCommand")

        backup_logs = command_name not in self.DONT_BACKUP_LOGS_FOR_COMMANDS

        log_failure = command_name not in self.DONT_DEBUG_FAILURES_FOR_COMMANDS

        handle = command.pop("__handle", None)

        

        # Set environment for encryption if needed

        if self.encryption_key:

            os.environ["AGENT_ENCRYPTION_KEY"] = self.encryption_key

        

        python_executor = PythonExecutor(self.tmp_dir, self.config)

        result = None

        

        for py_file, base_dir in script_sequence:

            exec_result = python_executor.run_file(

                script=py_file,

                args=[

                    command_name or self.COMMAND_NAME_STATUS,

                    json_path,

                    base_dir,

                    tmpstrucoutfile,

                    logging.getLevelName(logger.level),

                    self.exec_tmp_dir,

                    self.force_https_protocol,

                    self.ca_cert_file_path

                ],

                tmpout=tmpoutfile,

                tmperr=tmperrfile,

                timeout=int(command["commandParams"]["command_timeout"]),

                tmpstructuredout=tmpstrucoutfile,

                taskid=task_id,

                override_output_files=override_files,

                backup_log_files=backup_logs,

                log_info_on_failure=log_failure,

                handle=handle

            )

            

            # After first execution, always append to existing files

            override_files = False

            

            # Break on failure unless we have handle

            if exec_result["exitcode"] != 0 and not handle:

                result = exec_result

                break

        return result or {"exitcode": 0, "stdout": "", "stderr": "", "structuredOut": "{}"}

    

    def _check_command_cancellation(self, task_id: str, result: Dict[str, Any]) -> None:

        """Check if command was canceled and update results"""

        with self.commands_in_progress_lock:

            if task_id in self.commands_in_progress:

                reason = self.commands_in_progress.pop(task_id)

                cancel_msg = f"\nCommand aborted: {reason}\n"

                

                # Append cancellation message to outputs

                result["stdout"] += cancel_msg

                result["stderr"] += cancel_msg

                

                # Update output files

                self._append_to_file(tmpoutfile, cancel_msg)

                self._append_to_file(tmperrfile, cancel_msg)

    

    def _append_to_file(self, filepath: str, content: str) -> None:

        """Append content to a file"""

        try:

            with open(filepath, "a") as f:

                f.write(content)

        except OSError as e:

            logger.error("Failed to write to %s: %s", filepath, str(e))

    

    def _cleanup_execution(self, context: Dict[str, Any]) -> None:

        """Cleanup execution resources"""

        # Release component tracking

        if context["incremented_component"]:

            component = context["command"]["role"]

            self.commands_for_component[context["cluster_id"]][component] -= 1

        

        # Cleanup JSON command file

        if context["json_path"]:

            self._conditionally_remove_command_file(

                context["json_path"], 

                context["result"],

                context.get("is_status_command", False)

            )

        

        # Cleanup status command files

        if context.get("is_status_command"):

            self._cleanup_status_files(

                context["stdout_file"],

                context["stderr_file"],

                context["structured_out_file"]

            )

    

    def _cleanup_status_files(self, *files: str) -> None:

        """Cleanup temporary status files"""

        for file_path in files:

            try:

                if file_path and os.path.exists(file_path):

                    os.unlink(file_path)

            except OSError:

                logger.debug("Failed to delete status file %s", file_path)

    

    # ==================== Command Utilities ====================

    

    def requestComponentStatus(self, command_header: Dict[str, Any], command_name: str = "STATUS") -> Dict[str, Any]:

        """

        Request component status with automated output handling

        

        :param command_header: Component status context

        :param command_name: Name of status command

        :return: Status result dictionary

        """

        # Create unique temporary files

        stdout_file = self.status_commands_stdout.format(uuid.uuid4())

        stderr_file = self.status_commands_stderr.format(uuid.uuid4())

        structured_out = self.status_structured_out.format(uuid.uuid4())

        

        try:

            return self.runCommand(

                command_header=command_header,

                tmpoutfile=stdout_file,

                tmperrfile=stderr_file,

                forced_command_name=command_name,

                override_output_files=logger.level != logging.DEBUG,

                is_status_command=True,

                tmpstrucoutfile=structured_out

            )

        finally:

            self._cleanup_status_files(stdout_file, stderr_file, structured_out)

    

    def generate_command(self, command_header: Dict[str, Any]) -> Dict[str, Any]:

        """

        Generate full command configuration from header and context

        

        :param command_header: Command metadata

        :return: Complete command configuration

        """

        cluster_id = str(command_header.get("clusterId", "-1"))

        

        if cluster_id in {"-1", "null"}:

            cluster_id = None

            service_name = component_name = None

        else:

            service_name = command_header.get("serviceName")

            component_name = command_header.get("role")

        

        # Get base configuration

        command_dict = self.configuration_builder.get_configuration(

            cluster_id, service_name, component_name,

            command_header.get("requiredConfigTimestamp")

        )

        

        # Merge headers without override

        if "clusterHostInfo" in command_header:

            command_dict.pop("clusterHostInfo", None)

        

        # Merge configurations

        command = Utils.update_nested(Utils.get_mutable_copy(command_dict), command_header)

        

        # Handle compressed cluster info

        if "clusterHostInfo" in command_header and command_header["clusterHostInfo"]:

            command["clusterHostInfo"] = self._decompress_cluster_host_info(

                command["clusterHostInfo"]

            )

        

        return command

    

    def _decompress_cluster_host_info(self, compressed_info: Dict[str, Any]) -> Dict[str, Any]:

        """Decompress cluster host information"""

        # Extract basic info

        info = compressed_info.copy()

        hosts = info.pop(self.HOSTS_LIST_KEY, [])

        ports = info.pop(self.PING_PORTS_KEY, [])

        racks = info.pop(self.RACKS_KEY, [])

        ips = info.pop(self.IPV4_ADDRESSES_KEY, [])

        

        # Extract server info

        server_host = info.pop(self.cloud_SERVER_HOST, "")

        server_port = info.pop(self.cloud_SERVER_PORT, "")

        server_ssl = info.pop(self.cloud_SERVER_USE_SSL, "false")

        

        # Decompress mapped values

        decompressed = {}

        for key, ranges in info.items():

            decompressed[key] = self._convert_smart_range_to_list(ranges, hosts)

        

        # Decompress other mappings

        decompressed[self.PING_PORTS_KEY] = self._convert_mapped_range_to_list(ports)

        decompressed[self.RACKS_KEY] = self._convert_mapped_range_to_list(racks)

        decompressed[self.IPV4_ADDRESSES_KEY] = self._convert_mapped_range_to_list(ips)

        decompressed[self.HOSTS_LIST_KEY] = hosts

        

        # Add server info

        decompressed[self.cloud_SERVER_HOST] = server_host

        decompressed[self.cloud_SERVER_PORT] = server_port

        decompressed[self.cloud_SERVER_USE_SSL] = server_ssl

        

        return decompressed

    

    def _convert_smart_range_to_list(self, ranges: List[str], host_list: List[str]) -> List[str]:

        """Convert smart range to host list"""

        indexes = []

        for r in ranges:

            parts = r.split(",")

            for part in parts:

                if "-" in part:

                    start, end = map(int, part.split("-"))

                    indexes.extend(range(start, end + 1))

                else:

                    indexes.append(int(part))

        return [host_list[i] for i in set(indexes)] if host_list else []

    

    def _convert_mapped_range_to_list(self, mappings: List[str]) -> List[str]:

        """Convert mapped range to flat value list"""

        result_map = {}

        for mapping in mappings:

            if ":" not in mapping:

                result_map[len(result_map)] = mapping

                continue

                

            val, range_expr = mapping.split(":", 1)

            for part in range_expr.split(","):

                if "-" in part:

                    start, end = map(int, part.split("-"))

                    for idx in range(start, end + 1):

                        result_map[idx] = val

                else:

                    result_map[int(part)] = val

                    

        return [result_map[i] for i in sorted(result_map)]

    

    def _dump_command_to_json(

        self, command: Dict[str, Any], retry: bool, is_status_command: bool

    ) -> str:

        """Dump command to temporary JSON file"""

        filename = (

            f"status_command_{uuid.uuid4()}.json" if is_status_command

            else f"command-{command['taskId']}.json"

        )

        file_path = os.path.join(self.tmp_dir, filename)

        

        # Create secure JSON file

        try:

            if os.path.exists(file_path):

                os.unlink(file_path)

                

            with os.fdopen(os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:

                json.dump(command, f, sort_keys=False, indent=4)

        except OSError as e:

            raise AgentException(f"Failed to create command file: {str(e)}")

        

        return file_path

    

    def _conditionally_remove_command_file(

        self, json_path: str, command_result: Dict[str, Any], is_status: bool

    ) -> bool:

        """Conditionally remove command file based on retention policy"""

        if is_status or not os.path.exists(json_path):

            return False

            

        policy = self.config.command_file_retention_policy

        policy_map = {

            self.config.COMMAND_FILE_RETENTION_POLICY_REMOVE: True,

            self.config.COMMAND_FILE_RETENTION_POLICY_REMOVE_ON_SUCCESS: 

                command_result.get("exitcode", 1) == 0

        }

        

        remove_file = policy_map.get(policy, False)

        if remove_file:

            try:

                os.unlink(json_path)

                logger.info("Removed command file per policy: %s", policy)

                return True

            except OSError as e:

                logger.error("Failed to remove command file: %s", str(e))

        return False

