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

Enhanced URL Port Extractor Utility
"""

import re
from typing import Union, Any
from enum import Enum

class SpecialValues(Enum):
    """Standardized values for unknown/special configurations"""
    UNDEFINED = "UnknownConfiguration"
    UNAVAILABLE = "Unavailable"
    ANY = "ANY"

class PortType(Enum):
    """Validation categories for port ranges"""
    SYSTEM = (0, 1023)
    USER = (1024, 49151)
    DYNAMIC = (49152, 65535)
    
    @property
    def min(self):
        return self.value[0]
    
    @property
    def max(self):
        return self.value[1]

PORT_REGEX = re.compile(
    r"""
    # Match hostname or IPv4/IPv6 with port
    (?:^|[\s\[\]'\"])                     # Start of string or boundary
    (?:                                    # Optional protocol
        (?:https?|tcp|udp|ssl|ftps?)://   # Supported protocols
    )?
    (?:                                    # Host groups
        \[([0-9a-fA-F:]+)\]               # IPv6 in brackets
        |                                  # OR
        ([^:/\s]+?)                        # Hostname or IPv4
    )
    :                                      # Port separator
    (\d{1,5})                             # Port number (1-5 digits)
    """, 
    re.VERBOSE
)

def extract_port_from_url(
    address: Union[str, int, Any], 
    default_port: Union[str, int] = SpecialValues.UNDEFINED.value
) -> str:
    """
    Extracts port number from various URL and address formats with enhanced validation.
    
    Features:
    - Supports IPv4, IPv6, and hostname formats
    - Validates port ranges
    - Handles special configuration markers
    - Provides descriptive error messages
    
    Args:
        address: Input URL, host:port string, or port number
        default_port: Return value when no port found (default: 'UnknownConfiguration')
        
    Returns:
        Extracted port number as string, or default value if not found
        
    Raises:
        ValueError: For invalid port numbers
        RuntimeError: For malformed URLs
        
    Examples:
        >>> extract_port_from_url("example.com:8080")
        '8080'
        >>> extract_port_from_url("[fe80::1]:443")
        '443'
        >>> extract_port_from_url(8080)
        '8080'
        >>> extract_port_from_url("badurl", default_port="UNKNOWN")
        'UNKNOWN'
    """
    # 1. Handle special cases and edge conditions
    if address is None or not address:
        return ""
        
    if address == SpecialValues.UNDEFINED.value:
        return address
        
    # 2. Process numeric ports directly
    if isinstance(address, int):
        _validate_port_number(address)
        return str(address)
        
    # 3. Handle string representations of ports
    if isinstance(address, str):
        # Check for special values first
        if address in {SpecialValues.UNDEFINED.value, SpecialValues.UNAVAILABLE.value}:
            return address
            
        # Return pure digit strings after validation
        if address.isdigit():
            port_num = int(address)
            _validate_port_number(port_num)
            return address
            
        # 4. Advanced pattern matching for complex URLs
        match = PORT_REGEX.search(address)
        if match:
            port_num = match.group(3)
            if port_num:  # Group 3 is the port number
                return port_num
                
        # 5. Fallback for simple host:port format without protocol
        parts = address.rsplit(":", 1)
        if len(parts) > 1 and parts[1].isdigit():
            port_num = int(parts[1])
            _validate_port_number(port_num)
            return parts[1]
            
    # 6. Handle failed extraction
    if default_port == SpecialValues.UNDEFINED.value:
        raise RuntimeError(f"Could not extract port from malformed URL: '{address}'")
    return str(default_port)

def _validate_port_number(port: int):
    """Validates port number range with detailed error messages"""
    MIN_PORT = 0
    MAX_PORT = 65535
    
    if not MIN_PORT <= port <= MAX_PORT:
        range_type = next(
            (t.name for t in PortType if t.min <= port <= t.max),
            "out of range"
        )
        raise ValueError(
            f"Invalid port {port}: Must be between {MIN_PORT} and {MAX_PORT}. "
            f"Specified port is {range_type}."
        )

def is_valid_port(port: Union[str, int]) -> bool:
    """Safe port validation without exceptions"""
    try:
        port_num = int(port) if isinstance(port, str) and port.isdigit() else int(port)
        _validate_port_number(port_num)
        return True
    except (ValueError, TypeError):
        return False

def normalize_port_specification(spec: str) -> tuple:
    """
    Extracts protocol, host and port from complex specifications
    
    Examples:
        "tcp://example.com:443" -> ("tcp", "example.com", "443")
        "[::1]:8080"            -> (None, "::1", "8080")
        "9090"                  -> (None, None, "9090")
    """
    match = PORT_REGEX.search(spec)
    if not match:
        return (None, None, spec if spec.isdigit() else None)
    
    protocol = None
    if "://" in spec[:match.start()]:
        protocol = spec.split("://", 1)[0]
    
    host = match.group(1) or match.group(2)
    port = match.group(3)
    return (protocol, host, port)

def get_port_type(port: int) -> PortType:
    """Classify port based on IANA ranges"""
    return next(
        (pt for pt in PortType if pt.min <= port <= pt.max),
        PortType.DYNAMIC
    )

def resolve_service_port(service_name: str, default: int) -> str:
    """Resolve well-known port numbers for common services"""
    service_ports = {
        "http": "80",
        "https": "443",
        "ssh": "22",
        "ftp": "21",
        "smtp": "25",
        "dns": "53",
        "kerberos": "88",
        "ldap": "389",
        "ldaps": "636",
        "zookeeper": "2181",
        "kafka": "9092",
        "hdfs": "8020",
        "yarn": "8032",
    }
    return service_ports.get(service_name.lower(), str(int(default)))

