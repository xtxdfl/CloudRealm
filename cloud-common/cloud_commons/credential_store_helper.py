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
import re
import logging
import secrets
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from enum import Enum
from contextlib import contextmanager
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)

CREDENTIAL_UTIL_CMD = "org.apache.cloud.server.credentialapi.CredentialUtil"
CREDENTIAL_UTIL_JAR = "CredentialUtil.jar"
LOG_LINE_REGEX = re.compile(r"^(([0-1][0-9])|([2][0-3])):([0-5][0-9])(:[0-5][0-9])[,]\d{1,3}")

class CredentialOperation(Enum):
    GET = "get"
    LIST = "list"
    CREATE = "create"
    DELETE = "delete"

@dataclass(frozen=True)
class CredentialConfig:
    java_home: str
    jdk_location: str
    cs_lib_path: str
    provider_path: str

    @property
    def java_bin(self) -> str:
        return f"{self.java_home}/bin/java"
    
    @property
    def credential_util_dir(self) -> str:
        """Extracts directory from classpath"""
        paths = self.cs_lib_path.split("*")
        if len(paths) > 1:
            path = paths[0].split(":")[-1]
            return path.replace("${JAVA_HOME}", self.java_home)
        return "."

    @property
    def credential_util_path(self) -> str:
        return os.path.join(self.credential_util_dir, CREDENTIAL_UTIL_JAR)
    
    @property
    def credential_util_url(self) -> str:
        return f"{self.jdk_location}/{CREDENTIAL_UTIL_JAR}"

def normalize_output(lines: List[str]) -> List[str]:
    """Filter out log lines from credential utility output"""
    return [line for line in lines if not LOG_LINE_REGEX.match(line)]

def download_credential_util(config: CredentialConfig) -> None:
    """Ensure credential utility exists, download if missing"""
    if os.path.exists(config.credential_util_path):
        return
    
    Path(config.credential_util_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        if not config.jdk_location.startswith(("http://", "https://", "file://")):
            raise RuntimeError(f"Unsupported download protocol: {config.jdk_location}")
        
        logger.info(f"Downloading credential utility: {config.credential_util_url}")
        with NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Use safer external download method with progress/timeout
        download_command = [
            "/usr/bin/curl", 
            "-L",
            "-sS",           # Silent but show errors
            "-o", temp_path, 
            config.credential_util_url
        ]
        
        result = subprocess.run(
            download_command, 
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            timeout=60,
            check=True
        )
        
        os.chmod(temp_path, 0o755)
        os.rename(temp_path, config.credential_util_path)
        
    except Exception as e:
        logger.error(f"Failed to download credential utility: {str(e)}")
        raise
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

@contextmanager
def secure_password_file(password: str) -> str:
    """Securely handle password using temp file with automatic cleanup"""
    try:
        # Create temporary file with restricted permissions
        with NamedTemporaryFile("w", delete=False) as f:
            f.write(password)
            tmp_path = f.name
        
        # Set strict permissions
        os.chmod(tmp_path, 0o600)
        yield tmp_path
        
    finally:
        if tmp_path and os.path.exists(tmp_path):
            # Securely erase file contents before deletion
            with open(tmp_path, "wb") as f:
                f.write(os.urandom(os.path.getsize(tmp_path)))
            os.unlink(tmp_path)

def execute_credential_cmd(
    config: CredentialConfig, 
    operation: CredentialOperation, 
    alias: Optional[str] = None, 
    password: Optional[str] = None,
    force: bool = False
) -> List[str]:
    """Execute CredentialUtil command with proper error handling"""
    download_credential_util(config)
    
    cmd_args = [
        config.java_bin,
        "-cp", 
        config.cs_lib_path,
        CREDENTIAL_UTIL_CMD,
        operation.value
    ]
    
    if alias:
        cmd_args.append(alias)
    
    if operation in (CredentialOperation.GET, CredentialOperation.LIST):
        # Suppress interactive prompts for automated operations
        cmd_args.append("-noninteractive")
    
    if operation in (CredentialOperation.CREATE, CredentialOperation.DELETE):
        # Ensure operations are forced for scripted environments
        cmd_args.append("-f")
    
    if operation == CredentialOperation.CREATE and password:
        # Handle password securely via temp file
        with secure_password_file(password) as password_file:
            cmd_args.extend(["-infile", password_file])
            
            # Execute with secure environment
            result = subprocess.run(
                cmd_args,
                check=True,
                text=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                start_new_session=True  # Isolate in new process group
            )
    
    else:
        # Provider argument for all operations
        cmd_args.extend(["-provider", config.provider_path])
        
        # Execute without password handling
        result = subprocess.run(
            cmd_args,
            check=True,
            text=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
    
    # Handle command output
    if result.returncode != 0:
        error_msg = f"Command failed ({' '.join(cmd_args)}): {result.stderr}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Clean and return output lines
    output_lines = result.stdout.splitlines()
    return normalize_output(output_lines)

def get_password_from_credential_store(
    alias: str, 
    config: CredentialConfig
) -> str:
    """Retrieve password securely from credential store""" 
    output = execute_credential_cmd(
        config, 
        CredentialOperation.GET,
        alias=alias
    )
    return output[-1] if output else ""

def list_aliases_from_credential_store(
    config: CredentialConfig
) -> List[str]:
    """List all aliases in credential store"""
    output = execute_credential_cmd(
        config, 
        CredentialOperation.LIST
    )
    # Skip first line (table header)
    return output[1:] if len(output) > 1 else []

def delete_alias_from_credential_store(
    alias: str, 
    config: CredentialConfig
) -> None:
    """Remove alias from credential store"""
    execute_credential_cmd(
        config,
        CredentialOperation.DELETE,
        alias=alias
    )

def create_password_in_credential_store(
    alias: str, 
    config: CredentialConfig,
    password: str
) -> None:
    """Securely store new credential with rotation option"""
    # Generate 128-bit salt
    new_password = f"{password}-{secrets.token_hex(16)}"
    
    execute_credential_cmd(
        config,
        CredentialOperation.CREATE,
        alias=alias,
        password=new_password
    )
