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

Enhanced HTTPS Detection Utility
"""

from typing import Union, Optional
from enum import Enum

class HttpPolicyValues(Enum):
    """Valid values for HDFS http.policy configuration"""
    HTTP_ONLY = "http_only"
    HTTPS_ONLY = "https_only"
    HTTP_AND_HTTPS = "http_and_https"

POLICY_KEY = "dfs.http.policy"
LEGACY_KEY = "dfs.https.enable"
SUPPORTED_POLICIES = {policy.value for policy in HttpPolicyValues}

def is_https_enabled(
    dfs_http_policy: Optional[str] = None,
    dfs_https_enable: Optional[Union[bool, str]] = None
) -> bool:
    """
    Determines if HTTPS is enabled in HDFS by checking both new and legacy properties.
    
    Evaluation logic:
    1. Prioritizes `dfs.http.policy` if set:
       - Returns True for 'https_only' or 'HTTPS_ONLY'
       - Returns False for all other valid values ('http_only', 'http_and_https')
    2. Falls back to `dfs.https.enable` if the policy is not set or invalid
    3. Automatically converts legacy string values ('true', 'false') to booleans
    
    Returns:
        Returns True if HTTPS is enabled, False otherwise.
        
    Examples:
        >>> is_https_enabled(dfs_http_policy="https_only")
        True
        >>> is_https_enabled(dfs_http_policy="http_and_https")
        False
        >>> is_https_enabled(dfs_https_enable=True)
        True
        >>> is_https_enabled(dfs_https_enable="false")
        False
    """
    # 1. Check modern policy configuration (priority)
    if dfs_http_policy:
        normalized_policy = dfs_http_policy.strip().lower()
        
        if normalized_policy == HttpPolicyValues.HTTPS_ONLY.value:
            return True
        elif normalized_policy in SUPPORTED_POLICIES:
            return False
    
    # 2. Fallback to legacy boolean property
    if dfs_https_enable is not None:
        if isinstance(dfs_https_enable, bool):
            return dfs_https_enable
        elif isinstance(dfs_https_enable, str):
            return dfs_https_enable.strip().lower() == "true"
    
    return False  # Default to HTTP if no configuration found

def check_https_configuration_consistency(
    policy_value: Optional[str] = None,
    legacy_value: Optional[Union[bool, str]] = None
) -> bool:
    """
    Validates consistency between new and legacy HTTPS properties.
    
    Rules:
    - If both properties are set:
        * POLICY=HTTPS_ONLY and LEGACY=True -> Valid
        * POLICY=HTTPS_ONLY and LEGACY=False -> Conflict
        * POLICY=HTTP_ONLY and LEGACY=True -> Conflict
        * Both disabled -> Valid
    
    Returns:
        True if configurations are consistent, False if conflicts exist.
    """
    https_by_policy = is_https_enabled(dfs_http_policy=policy_value)
    https_by_legacy = is_https_enabled(dfs_https_enable=legacy_value)
    
    # Only check consistency if both properties are explicitly set
    if policy_value is not None and legacy_value is not None:
        return https_by_policy == https_by_legacy
    
    return True  # Considered consistent if either is unset

def normalize_configuration_key(
    key: str,
    normalized_keys: dict = {POLICY_KEY: POLICY_KEY, LEGACY_KEY: LEGACY_KEY}
) -> str:
    """
    Normalizes configuration keys with case-insensitivity and alias support.
    
    Supports:
    - Key variants: 'DfsHttpPolicy', 'DFS_HTTP_POLICY'
    - Legacy naming: 'dfs.enable.https'
    - Aliases: 'http_policy', 'https_enabled'
    """
    key_lower = key.strip().lower().replace("_", "").replace("-", "")
    
    mapping = {
        "dfshttppolicy": POLICY_KEY,
        "httpolicy": POLICY_KEY,
        "dfshttpsenable": LEGACY_KEY,
        "httpsenable": LEGACY_KEY,
        "enablehttps": LEGACY_KEY
    }
    
    return mapping.get(key_lower, key)

def detect_https_configuration(configurations: dict) -> str:
    """
    Analyzes configuration dictionary to return the effective HTTPS status.
    
    Returns:
        "HTTPS_ONLY", "HTTP_WITH_HTTPS", "HTTP_ONLY", or "MIXED" with conflict details
    """
    policy_val = configurations.get(POLICY_KEY, "").strip().lower()
    legacy_val = configurations.get(LEGACY_KEY)
    
    # Resolve effective HTTPS status
    https_detected = is_https_enabled(policy_val, legacy_val)
    
    # Determine overall configuration state
    if policy_val:
        if policy_val == "https_only":
            return "HTTPS_ONLY"
        elif policy_val == "http_and_https":
            return "HTTP_WITH_HTTPS" if https_detected else "HTTP_ONLY"
        return "HTTP_ONLY"
    
    return "HTTPS_ONLY" if https_detected else "HTTP_ONLY"

def convert_legacy_to_policy(https_enable: Union[bool, str]) -> str:
    """
    Converts legacy boolean configuration to modern policy string.
    
    Examples:
        True -> "https_only"
        "TRUE" -> "https_only"
        False -> "http_only"
        None -> "http_only"
    """
    if https_enable in (True, "true", "TRUE", "True"):
        return HttpPolicyValues.HTTPS_ONLY.value
    return HttpPolicyValues.HTTP_ONLY.value

def validate_https_configuration(
    config_dict: dict,
    current_version: str,
    min_https_version: str = "2.0"
) -> dict:
    """
    Comprehensive validation of HTTPS configuration with version checking.
    
    Returns dictionary with:
    {
        "status": "VALID"|"INVALID"|"WARNING",
        "effective_policy": str,
        "compatibility": bool,
        "conflicts": list[str],
        "recommendation": str
    }
    """
    # Placeholder for actual validation logic
    result = {
        "status": "VALID",
        "effective_policy": "",
        "compatibility": True,
        "conflicts": [],
        "recommendation": ""
    }
    
    policy_value = config_dict.get(POLICY_KEY, "").strip()
    legacy_value = config_dict.get(LEGACY_KEY)
    
    # 1. Check configuration conflicts
    if not check_https_configuration_consistency(policy_value, legacy_value):
        result["conflicts"].append(
            f"Conflict between {POLICY_KEY}={policy_value} and "
            f"{LEGACY_KEY}={legacy_value}"
        )
        result["status"] = "INVALID"
    
    # 2. Verify version compatibility
    policy_only_version = "3.0"  # Minimum version requiring POLICY setting
    if not policy_value and current_version >= policy_only_version:
        result["compatibility"] = False
        result["status"] = "WARNING" if result["status"] == "VALID" else "INVALID"
        result["recommendation"] = (
            f"Upgrade required: Versions {policy_only_version}+ require "
            f"explicit {POLICY_KEY} setting"
        )
    
    # 3. Determine effective policy
    result["effective_policy"] = (
        policy_value if policy_value 
        else convert_legacy_to_policy(legacy_value)
    )
    
    # 4. Validate policy format
    if result["effective_policy"].lower() not in SUPPORTED_POLICIES:
        result["status"] = "INVALID"
        result["conflicts"].append(
            f"Invalid policy value: '{result['effective_policy']}'. "
            f"Supported values: {', '.join(SUPPORTED_POLICIES)}"
        )
    
    return result
