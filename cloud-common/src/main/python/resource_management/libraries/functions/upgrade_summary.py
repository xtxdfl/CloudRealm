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

Enhanced Cluster Upgrade Management Utilities
"""

from collections import namedtuple
from typing import Dict, Optional, List
from resource_management.libraries.script.script import Script
from resource_management.libraries.functions.constants import Direction


class ServiceVersionInfo:
    """Encapsulates version information for a service during upgrades"""
    __slots__ = ('service_name', 'source_stack', 'source_version', 'target_stack', 'target_version')
    
    def __init__(self, service_name: str, source_stack: str, source_version: str, 
                 target_stack: str, target_version: str):
        self.service_name = service_name
        self.source_stack = source_stack
        self.source_version = source_version
        self.target_stack = target_stack
        self.target_version = target_version
        
    def __repr__(self) -> str:
        return (f"ServiceVersionInfo(service={self.service_name}, "
                f"from={self.source_stack}@{self.source_version}, "
                f"to={self.target_stack}@{self.target_version})")


class UpgradeSummary:
    """Comprehensive summary of cluster upgrade process"""
    __slots__ = (
        'upgrade_type', 'direction', 'orchestration', 'is_revert',
        'services', 'is_downgrade_allowed', 'is_switch_bits',
        'associated_stack', 'associated_version', 'start_time',
        'progress_ratio', 'completed_services'
    )
    
    def __init__(self, upgrade_type: str, direction: str, orchestration: str, 
                 is_revert: bool, services: Dict[str, ServiceVersionInfo],
                 is_downgrade_allowed: bool, is_switch_bits: bool,
                 associated_stack: str, associated_version: str,
                 start_time: Optional[float] = None,
                 progress_ratio: float = 0.0,
                 completed_services: List[str] = None):
        self.upgrade_type = upgrade_type
        self.direction = direction
        self.orchestration = orchestration
        self.is_revert = is_revert
        self.services = services
        self.is_downgrade_allowed = is_downgrade_allowed
        self.is_switch_bits = is_switch_bits
        self.associated_stack = associated_stack
        self.associated_version = associated_version
        self.start_time = start_time  # Timestamp when upgrade started
        self.progress_ratio = progress_ratio  # 0.0 to 1.0 indicating progress
        self.completed_services = completed_services or []
        
    @property
    def is_downgrade(self) -> bool:
        """Check if this is a downgrade operation"""
        return self.direction.lower() == Direction.DOWNGRADE.lower()
        
    def get_service(self, service_name: str) -> Optional[ServiceVersionInfo]:
        """Retrieve version info for a specific service"""
        return self.services.get(service_name)
        
    def mark_service_completed(self, service_name: str):
        """Mark a service as completed during upgrade process"""
        if service_name in self.services and service_name not in self.completed_services:
            self.completed_services.append(service_name)
            self.progress_ratio = len(self.completed_services) / len(self.services)
            
    @property
    def services_remaining(self) -> List[str]:
        """Get list of services not yet completed"""
        return [svc for svc in self.services if svc not in self.completed_services]
        
    def __repr__(self) -> str:
        progress = f"{self.progress_ratio:.0%}" if self.start_time else "unknown"
        return (f"UpgradeSummary(type={self.upgrade_type}, "
                f"direction={self.direction}, "
                f"services={len(self.services)}, "
                f"progress={progress})")


class UpgradeManager:
    """Centralized upgrade state management and operations"""
    
    _upgrade_summary = None
    
    @classmethod
    def get_upgrade_summary(cls) -> Optional[UpgradeSummary]:
        """
        Retrieves the current cluster upgrade summary from cloud configuration
        
        Returns:
            UpgradeSummary object if upgrade is in progress, else None
        """
        # Return cached version if available
        if cls._upgrade_summary:
            return cls._upgrade_summary
            
        config = Script.get_config()
        
        # Check upgrade summary exists and has valid format
        if "upgradeSummary" not in config or not isinstance(config["upgradeSummary"], dict):
            return None
            
        upgrade_data = config["upgradeSummary"]
        
        # Validate critical upgrade parameters
        required_keys = {"type", "direction", "services", "associatedStackId", "associatedVersion"}
        if not required_keys.issubset(upgrade_data.keys()):
            raise ValueError("Invalid upgrade summary format in configuration")
            
        # Process services version information
        service_versions = {}
        for service_name, service_data in upgrade_data["services"].items():
            # Validate service data format
            if not all(key in service_data for key in ["sourceStackId", "sourceVersion", 
                                                      "targetStackId", "targetVersion"]):
                raise ValueError(f"Missing version info for service: {service_name}")
                
            service_version = ServiceVersionInfo(
                service_name=service_name,
                source_stack=service_data["sourceStackId"],
                source_version=service_data["sourceVersion"],
                target_stack=service_data["targetStackId"],
                target_version=service_data["targetVersion"]
            )
            service_versions[service_name] = service_version
            
        # Create comprehensive upgrade summary
        summary = UpgradeSummary(
            upgrade_type=upgrade_data["type"],
            direction=upgrade_data["direction"],
            orchestration=upgrade_data.get("orchestration", "STANDARD"),
            is_revert=upgrade_data.get("isRevert", False),
            services=service_versions,
            is_downgrade_allowed=upgrade_data.get("isDowngradeAllowed", False),
            is_switch_bits=upgrade_data.get("isSwitchBits", False),
            associated_stack=upgrade_data["associatedStackId"],
            associated_version=upgrade_data["associatedVersion"]
        )
        
        # Cache and return the summary
        cls._upgrade_summary = summary
        return summary
        
    @classmethod
    def get_service_version_info(cls, service_name: str = None) -> Optional[ServiceVersionInfo]:
        """
        Retrieves version information for a specific service
        
        Args:
            service_name: Service to retrieve (default: current service in context)
            
        Returns:
            ServiceVersionInfo if available, else None
        """
        # Get current service name if not specified
        if service_name is None:
            config = Script.get_config()
            service_name = config.get("serviceName")
            if not service_name:
                raise ValueError("Service name not provided and could not be determined from context")
                
        summary = cls.get_upgrade_summary()
        if not summary:
            return None
            
        return summary.get_service(service_name)
        
    @classmethod
    def get_source_version(cls, service_name: str = None, default: str = None) -> Optional[str]:
        """
        Retrieve source version for a service during upgrade
        
        Args:
            service_name: Target service (default: current service)
            default: Default value if version cannot be determined
            
        Returns:
            Source version string or default value
        """
        service_info = cls.get_service_version_info(service_name)
        return service_info.source_version if service_info else default
        
    @classmethod
    def get_target_version(cls, service_name: str = None, default: str = None) -> Optional[str]:
        """
        Retrieve target version for a service during upgrade
        
        Args:
            service_name: Target service (default: current service)
            default: Default value if version cannot be determined
            
        Returns:
            Target version string or default value
        """
        service_info = cls.get_service_version_info(service_name)
        return service_info.target_version if service_info else default
        
    @classmethod
    def get_downgrade_source_version(cls, service_name: str = None) -> Optional[str]:
        """
        Retrieve source version specifically for downgrade operations
        
        Args:
            service_name: Target service (default: current service)
            
        Returns:
            Source version string or None if not downgrade
        """
        summary = cls.get_upgrade_summary()
        if not summary or not summary.is_downgrade:
            return None
            
        service_info = summary.get_service(service_name)
        return service_info.source_version if service_info else None
        
    @classmethod
    def mark_service_completed(cls, service_name: str) -> bool:
        """
        Mark a service as successfully upgraded in the system context
        
        Args:
            service_name: Service name to mark as completed
            
        Returns:
            True if marked successfully, False otherwise
        """
        summary = cls.get_upgrade_summary()
        if not summary:
            return False
            
        summary.mark_service_completed(service_name)
        # Here we would persist this state back to cloud server
        # Implementation placeholder for actual persistence
        return True

    @classmethod
    def is_upgrade_in_progress(cls) -> bool:
        """Check if any upgrade operation is currently active"""
        return cls.get_upgrade_summary() is not None

    @classmethod
    def get_remaining_services(cls) -> List[str]:
        """Get services pending upgrade completion"""
        summary = cls.get_upgrade_summary()
        return summary.services_remaining if summary else []
        
    @classmethod
    def get_upgrade_progress(cls) -> float:
        """Get current upgrade progress ratio (0.0 to 1.0)"""
        summary = cls.get_upgrade_summary()
        return summary.progress_ratio if summary else 0.0


# Legacy API Functions (for backward compatibility)
def get_source_stack(service_name=None) -> Optional[str]:
    """Legacy: See get_source_version"""
    service_info = UpgradeManager.get_service_version_info(service_name)
    return service_info.source_stack if service_info else None

def get_source_version(service_name=None, default_version=None) -> Optional[str]:
    """Legacy: Wrapper for UpgradeManager.get_source_version"""
    return UpgradeManager.get_source_version(service_name, default_version)

def get_target_version(service_name=None, default_version=None) -> Optional[str]:
    """Legacy: Wrapper for UpgradeManager.get_target_version"""
    return UpgradeManager.get_target_version(service_name, default_version)

def get_downgrade_from_version(service_name=None) -> Optional[str]:
    """Legacy: Wrapper for UpgradeManager.get_downgrade_source_version"""
    return UpgradeManager.get_downgrade_source_version(service_name)

def get_upgrade_summary() -> Optional[UpgradeSummary]:
    """Legacy: Wrapper for UpgradeManager.get_upgrade_summary"""
    return UpgradeManager.get_upgrade_summary()
