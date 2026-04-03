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

import subprocess
import logging
import abc
from typing import Tuple, Optional
from cloud_commons import OSCheck, OSConst
from cloud_commons.logging_utils import get_logger
from cloud_commons.os_family import OsFamilyImpl
from resource_management.core import shell

# Initialize logger
logger = get_logger(__name__)

class FirewallCheckResult:
    """Structured result of firewall status check"""
    def __init__(
        self, 
        is_active: bool, 
        firewall_name: str,
        enabled_profiles: list = None,
        details: str = None
    ):
        self.is_active = is_active
        self.firewall_name = firewall_name
        self.enabled_profiles = enabled_profiles or []
        self.details = details or ""
        
    def __bool__(self):
        return self.is_active
    
    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        profiles = f" [{', '.join(self.enabled_profiles)}]" if self.enabled_profiles else ""
        return f"{self.firewall_name}: {status}{profiles}"


class FirewallChecker(metaclass=abc.ABCMeta):
    """Abstract base class for firewall status checkers"""
    FIREWALL_NAME = "Generic Firewall"
    TIMEOUT = 15  # Command execution timeout in seconds
    
    @abc.abstractmethod
    def get_check_command(self) -> list:
        """Return firewall status check command as tokenized list"""
        pass
    
    @abc.abstractmethod
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        """Parse command output into FirewallCheckResult"""
        pass
    
    def execute_command(self) -> Tuple[int, str, str]:
        """Execute firewall check command with safe wrapper"""
        command = self.get_check_command()
        try:
            # Use tokenized command for better security
            return shell.call(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=self.TIMEOUT, 
                quiet=False
            )
        except Exception as e:
            logger.warning(f"Firewall command failed: {e}")
            return 1, "", str(e)
    
    def check_firewall(self) -> FirewallCheckResult:
        """Perform firewall status check and return structured result"""
        if not self.get_check_command():
            return FirewallCheckResult(False, self.FIREWALL_NAME, 
                                      details="No check command defined")
            
        retcode, stdout, stderr = self.execute_command()
        logger.debug(f"Firewall check completed: {retcode}\nOUT: {stdout}\nERR: {stderr}")
        return self.parse_result(retcode, stdout, stderr)


@OsFamilyImpl(os_family=OSConst.WINSRV_FAMILY)
class WindowsFirewallChecker(FirewallChecker):
    """Firewall status checker for Windows systems"""
    FIREWALL_NAME = "Windows Defender Firewall"
    
    def get_check_command(self) -> list:
        return [
            "powershell.exe", 
            "-ExecutionPolicy", "Bypass",
            "-Command", 
            "Get-NetFirewallProfile | Where-Object { $_.Enabled } | "
            "Select-Object -ExpandProperty Name"
        ]
    
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        if returncode != 0:
            logger.warning(f"Failed to check firewall: {stderr}")
            return FirewallCheckResult(
                True,  # Assume firewall is active on failure
                self.FIREWALL_NAME,
                details=f"Check failed: {stderr}"
            )
            
        active_profiles = [line.strip() for line in stdout.splitlines() if line.strip()]
        return FirewallCheckResult(
            bool(active_profiles),
            self.FIREWALL_NAME,
            enabled_profiles=active_profiles
        )


@OsFamilyImpl(os_family=OsFamilyImpl.DEFAULT)
class LinuxFirewallChecker(FirewallChecker):
    """Base class for Linux firewall checkers"""
    FIREWALL_NAME = "iptables"
    
    def get_base_command(self, tool_name: str) -> list:
        """Standardize base command format for Linux tools"""
        return ["/usr/bin/env", tool_name]
    
    def is_available(self, command: list) -> bool:
        """Check if firewall tool is installed"""
        try:
            subprocess.run(
                [command[0], "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return True
        except (OSError, subprocess.CalledProcessError):
            return False


class UbuntuFirewallChecker(LinuxFirewallChecker):
    """Firewall status checker for Ubuntu-based systems"""
    FIREWALL_NAME = "ufw"
    
    def get_check_command(self) -> list:
        cmd = self.get_base_command("ufw") + ["status"]
        return cmd if self.is_available(cmd) else []
    
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        if returncode != 0:
            logger.debug(f"Non-zero exit code: {returncode} for ufw status")
            return FirewallCheckResult(False, self.FIREWALL_NAME)
            
        is_active = any("Status: active" in line for line in stdout.splitlines())
        return FirewallCheckResult(is_active, self.FIREWALL_NAME)


class FedoraFirewallChecker(LinuxFirewallChecker):
    """Firewall status checker for modern Fedora systems"""
    FIREWALL_NAME = "firewalld"
    
    def get_check_command(self) -> list:
        cmd = self.get_base_command("firewall-cmd") + ["--state"]
        return cmd if self.is_available(cmd) else []
    
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        is_active = stdout.strip().lower() == "running"
        return FirewallCheckResult(is_active, self.FIREWALL_NAME)


class RedHatFirewallChecker(LinuxFirewallChecker):
    """Firewall status checker for RedHat/CentOS systems"""
    FIREWALL_NAME = "iptables"
    
    def get_check_command(self) -> list:
        # Check possible firewall services: firewalld 鈫?iptables
        services = [
            ("firewalld", "--is-active"), 
            ("iptables", "status")
        ]
        
        for service, arg in services:
            cmd = self.get_base_command("systemctl") + ["is-active", service]
            if self.is_available(cmd[:1]):
                cmd.append(arg) if arg else None
                return cmd
        return []
    
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        is_active = returncode == 0 and "active" in stdout
        return FirewallCheckResult(is_active, self.FIREWALL_NAME or "iptables")


class SuseFirewallChecker(LinuxFirewallChecker):
    """Firewall status checker for SUSE systems"""
    FIREWALL_NAME = "SuSEfirewall2"
    
    def get_check_command(self) -> list:
        cmd = self.get_base_command("SuSEfirewall2") + ["status"]
        return cmd if self.is_available(cmd) else []
    
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        if returncode != 0:
            return FirewallCheckResult(False, self.FIREWALL_NAME)
            
        # Parse both classic and new YaST firewall
        running = any(
            "is not running" not in line and "running" in line 
            for line in stdout.splitlines()
        )
        return FirewallCheckResult(running, self.FIREWALL_NAME)


class UniversalLinuxChecker(LinuxFirewallChecker):
    """Fallback firewall checker for Linux systems"""
    FIREWALL_NAME = "iptables"
    
    def get_check_command(self) -> list:
        # Try both legacy and modern tools
        tools = ["systemctl", "service", "chkconfig"]
        for tool in tools:
            cmd = self.get_base_command(tool)
            if tool == "service":
                cmd += ["iptables", "status"]
            else:
                cmd += ["status", "iptables"]
            
            if self.is_available(cmd[:1]):
                return cmd
        return []
    
    def parse_result(self, returncode: int, stdout: str, stderr: str) -> FirewallCheckResult:
        if returncode == 3 or "unused" in stdout:
            return FirewallCheckResult(False, self.FIREWALL_NAME)
        return FirewallCheckResult("running" in stdout or "active" in stdout, self.FIREWALL_NAME)


# =======================
# Factory Implementation
# =======================
class FirewallManager:
    """Centralized firewall status management"""
    def __init__(self):
        self.os_family = OSCheck.get_os_family()
        self.os_type = OSCheck.get_os_type()
        self.os_version = OSCheck.get_os_major_version()
        
    def get_checker(self) -> FirewallChecker:
        """Factory method to get appropriate firewall checker"""
        if self.os_family == OSConst.WINSRV_FAMILY:
            return WindowsFirewallChecker()
            
        if OSCheck.is_ubuntu_family():
            return UbuntuFirewallChecker()
            
        if OSCheck.is_redhat_family():
            if self.os_type == OSConst.OS_FEDORA and int(self.os_version) >= 18:
                return FedoraFirewallChecker()
            return RedHatFirewallChecker()
            
        if OSCheck.is_suse_family():
            return SuseFirewallChecker()
            
        return UniversalLinuxChecker()
    
    def check_firewall(self) -> FirewallCheckResult:
        """Perform firewall status check with automatic configuration"""
        checker = self.get_checker()
        logger.info(f"Checking firewall status ({checker.FIREWALL_NAME})...")
        return checker.check_firewall()
    
    def recommend_firewall_cmd(self) -> str:
        """Recommend best firewall management command"""
        os_id = OSCheck().get_os_type()
        if os_id in [OSConst.UBUNTU_OS_TYPE]:
            return "sudo ufw"
        if os_id in [OSConst.CENTOS_OS_TYPE, OSConst.REDHAT_OS_TYPE]:
            return "sudo firewall-cmd"
        if os_id == OSConst.SUSE_OS_TYPE:
            return "sudo yast firewall"
        return "sudo iptables"


# =========================
# Public API for Consumers
# =========================
def firewall_status() -> FirewallCheckResult:
    """Public method to get firewall status"""
    return FirewallManager().check_firewall()
