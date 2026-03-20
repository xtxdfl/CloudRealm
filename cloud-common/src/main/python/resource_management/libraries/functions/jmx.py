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

Enhanced JMX Metrics Collector Utility
"""

import time
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from functools import wraps
from typing import Any, Dict, Optional, Tuple, Callable

# Configure logger
JMX_LOGGER = logging.getLogger("jmx_collector")
JMX_LOGGER.setLevel(logging.DEBUG)

# Default settings
DEFAULT_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2
SECURITY_OPTIONS = ["--negotiate", "-u", ":"]
BASIC_CURL_OPTIONS = ["-s", "-K", "-"]

def jmx_retry(retries=MAX_RETRIES, delay=RETRY_DELAY, logger=JMX_LOGGER):
    """
    Decorator for retrying JMX operations with exponential backoff
    
    Args:
        retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        logger: Logger instance for logging retries
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < retries:
                        sleep_time = delay * (2 ** (attempt - 1))
                        logger.warning(
                            f"Attempt {attempt}/{retries} failed for JMX query. "
                            f"Retrying in {sleep_time:.1f}s. Error: {str(e)}"
                        )
                        time.sleep(sleep_time)
            
            logger.error(
                f"Failed after {retries} attempts. Last error: {str(last_exception)}"
            )
            raise last_exception
        return wrapper
    return decorator

@jmx_retry()
def get_jmx_property(
    jmx_url: str,
    property_path: str,
    security_enabled: bool = False,
    run_user: Optional[str] = None,
    is_https_enabled: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    parse_json: bool = True
) -> Any:
    """
    Retrieve a specific property value from JMX endpoint with robust error handling
    
    Enhanced Features:
    - Smart retry mechanism with backoff
    - Multiple connection backends (curl and urllib)
    - JMX bean navigation using dot notation
    - Secure transport handling
    - User impersonation
    - Timeout protection
    - Detailed diagnostics
    
    Args:
        jmx_url: Complete URL to JMX endpoint
        property_path: Dot-separated path to JMX property (e.g., "beans.0.CapacityUsed")
        security_enabled: Enable Kerberos security
        run_user: User to impersonate when using curl
        is_https_enabled: Allow insecure HTTPS when True
        timeout: Operation timeout in seconds
        parse_json: Return parsed JSON when False (for complex handling)
        
    Returns:
        Requested JMX property value or None on failure
    """
    # Validate input parameters
    if not jmx_url:
        raise ValueError("JMX URL cannot be empty")
    
    if not property_path:
        raise ValueError("Property path cannot be empty")
    
    # Select connection method based on security and user context
    if security_enabled or run_user:
        response_data = _call_using_curl(
            jmx_url, 
            security_enabled,
            run_user,
            is_https_enabled,
            timeout
        )
    else:
        response_data = _call_using_urllib(
            jmx_url,
            security_enabled,
            is_https_enabled,
            timeout
        )
    
    # Handle empty response
    if not response_data:
        return None
    
    # Parse response if required
    if not parse_json:
        return response_data
    
    try:
        jmx_data = json.loads(response_data)
        return _extract_property(jmx_data, property_path)
    
    except Exception as e:
        JMX_LOGGER.error(
            f"Failed to parse JMX response or extract property: {str(e)}"
        )
        return None

def _call_using_curl(
    jmx_url: str,
    security_enabled: bool,
    run_user: Optional[str],
    is_https_enabled: bool,
    timeout: int
) -> Optional[str]:
    """
    Execute JMX call using curl backend (required for Kerberos security)
    """
    from resource_management.libraries.functions.get_user_call_output import (
      get_user_call_output,
    )
    
    try:
        # Construct curl command with security options
        cmd_base = ["curl", *BASIC_CURL_OPTIONS]
        curl_config = []
        
        if security_enabled:
            cmd_base.extend(SECURITY_OPTIONS)
        
        if is_https_enabled:
            curl_config.append("--insecure")
        
        curl_config.extend([
            f"--max-time {timeout}",
            f"--url {jmx_url}"
        ])
        
        # Execute curl command
        _, data, _ = get_user_call_output(
            cmd_base,
            user=run_user,
            quiet=True,
            input='\n'.join(curl_config),
            timeout=timeout + 5
        )
        
        # Log connection metrics
        JMX_LOGGER.debug(f"Curl backend successfully retrieved JMX data from {jmx_url}")
        return data
    
    except Exception as e:
        JMX_LOGGER.error(
            f"Curl connection to JMX endpoint failed: {str(e)}",
            exc_info=True
        )
        return None

def _call_using_urllib(
    jmx_url: str,
    security_enabled: bool,
    is_https_enabled: bool,
    timeout: int
) -> Optional[str]:
    """
    Execute JMX call using urllib backend (lighter weight, no Kerberos)
    """
    # Warn if security was requested but not using curl
    if security_enabled:
        JMX_LOGGER.warning(
            "Security enabled but falling back to urllib without Kerberos support"
        )
    
    try:
        # Create custom opener with timeout support
        opener = urllib.request.build_opener()
        
        # Disable SSL verification if needed
        if is_https_enabled:
            import ssl
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=context)
            )
        
        # Execute HTTP request
        with opener.open(jmx_url, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            JMX_LOGGER.debug(f"urllib backend retrieved JMX data from {jmx_url}")
            return data
    
    except urllib.error.URLError as ue:
        JMX_LOGGER.error(f"URL error connecting to JMX endpoint: {str(ue.reason)}")
    except Exception as e:
        JMX_LOGGER.error(
            f"Failed to connect to JMX endpoint via urllib: {str(e)}",
            exc_info=True
        )
    
    return None

def _extract_property(data: Dict, property_path: str) -> Any:
    """
    Navigate JMX structure using dot-separated path and strict key checks
    
    Args:
        data: Parsed JMX JSON structure
        property_path: Dot-separated path to property
        
    Returns:
        Requested property value or None if not found
    """
    # Handle simple path (no dots)
    if '.' not in property_path:
        if property_path in data:
            return data[property_path]
        raise KeyError(f"Property '{property_path}' not found in JMX response")
    
    # Split path into components
    path_parts = property_path.split('.')
    current_value = data
    
    try:
        for part in path_parts:
            # Handle array indices
            if part.isdigit():
                index = int(part)
                if not isinstance(current_value, list) or index >= len(current_value):
                    raise IndexError(
                        f"Invalid array index '{part}' in '{property_path}'"
                    )
                current_value = current_value[index]
            # Handle dictionary keys
            else:
                if part not in current_value:
                    raise KeyError(
                        f"Property '{part}' not found at path '{property_path}'"
                    )
                current_value = current_value[part]
    
    except (KeyError, IndexError, TypeError) as e:
        JMX_LOGGER.debug(
            f"Property path navigation failed: {str(e)}. "
            f"Available keys: {list(current_value.keys()) if isinstance(current_value, dict) else ''}"
        )
        return None
    
    return current_value

def get_value_from_jmx(
    qry: str,
    property: str,
    security_enabled: bool,
    run_user: Optional[str] = None,
    is_https_enabled: bool = False,
    **kwargs
) -> Optional[Any]:
    """
    Original interface wrapper for backward compatibility
    """
    return get_jmx_property(
        jmx_url=qry,
        property_path=property,
        security_enabled=security_enabled,
        run_user=run_user,
        is_https_enabled=is_https_enabled,
        **kwargs
    )

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Test JMX retrieval with security disabled
    print("Testing insecure HTTP connection...")
    value = get_jmx_property(
        jmx_url="http://localhost:50070/jmx?qry=Hadoop:service=NameNode,name=NameNodeInfo",
        property_path="beans.0.CapacityUsed",
        security_enabled=False
    )
    print(f"CapacityUsed: {value}")
    
    # Test with property path navigation
    print("\nTesting complex property path...")
    value = get_jmx_property(
        jmx_url="http://localhost:50070/jmx",
        property_path="beans.3.StorageInfo.clusterID",
        security_enabled=False
    )
    print(f"Cluster ID: {value}")
    
    # Simulate secure connection
    print("\nTesting Kerberos secured connection...")
    try:
        value = get_jmx_property(
            jmx_url="https://secure-nn.example.com:50470/jmx",
            property_path="beans.0.TotalFiles",
            security_enabled=True,
            run_user="hdfs",
            is_https_enabled=True
        )
        print(f"Total Files: {value}")
    except Exception as e:
        print(f"Secure test exception: {str(e)}")
