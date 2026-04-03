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

Enhanced JVM Memory Parameter Formatter
"""

import logging
import re
from typing import Union, Optional

from resource_management.libraries.script.config_dictionary import UnknownConfiguration
from resource_management.core.logger import Logger
from resource_management.libraries.functions.default import default

# Configure logger
JVM_OPTION_LOGGER = logging.getLogger("jvm_option_parser")
JVM_OPTION_LOGGER.setLevel(logging.INFO)

# Regular expression to validate and parse JVM memory values
JVM_MEMORY_REGEX = re.compile(
    r"^(?P<value>\d+)(?P<unit>[kmgtp]?b?)?$", 
    re.IGNORECASE
)

def format_jvm_option(
    name: str, 
    default_value: str = "1024m"
) -> str:
    """
    Format JVM memory parameters for consistent use in Java applications
    
    This function ensures consistent formatting of JVM memory parameters:
    1. Converts numeric values to megabyte strings (2048 => "2048m")
    2. Standardizes unit suffixes (1g => "1024m", 500 => "500m")
    3. Validates inputs and returns safe defaults for invalid formats
    
    Supported input formats:
    - Raw integers    (ex: 2048)
    - Memory strings  (ex: "2g", "512m", "1024")
    - Unit suffixes: k (kilo), m (mega), g (giga), t (tera), p (peta)
    
    Examples:
    >>> format_jvm_option("xmx", 2048)    # Returns "2048m"
    >>> format_jvm_option("xms", "2g")    # Returns "2048m"
    >>> format_jvm_option("xmn", "512")   # Returns "512m"
    >>> format_jvm_option("xx", "invalid") # Returns default_value
    
    Args:
        name: Name of the JVM parameter (e.g., "xmx", "xms")
        default_value: Fallback value if parsing fails
        
    Returns:
        Standardized JVM memory string with 'm' suffix
    """
    try:
        # Retrieve configuration value or use default
        option_value = _get_option_value(name, default_value)
        
        # Handle empty or whitespace-only values
        if not option_value or isinstance(option_value, str) and not option_value.strip():
            JVM_OPTION_LOGGER.warning(
                f"Empty JVM option: {name}. Using default: {default_value}"
            )
            return default_value
        
        # Convert integer values to memory strings
        if isinstance(option_value, int):
            return f"{option_value}m"
        
        # Process string values
        if isinstance(option_value, str):
            return _parse_jvm_memory_string(option_value.strip(), default_value)
        
        # Handle unknown types
        JVM_OPTION_LOGGER.warning(
            f"Unexpected type for JVM option {name}: {type(option_value)}. "
            f"Using default: {default_value}"
        )
        return default_value
        
    except Exception as e:
        JVM_OPTION_LOGGER.error(
            f"Failed to format JVM option {name}: {str(e)}. Using default: {default_value}",
            exc_info=True
        )
        return default_value


def _get_option_value(name: str, default_value: str) -> Union[int, str]:
    """Retrieve configuration value with safe handling of unknowns"""
    try:
        value = default(name, default_value)
        return value
    except UnknownConfiguration:
        JVM_OPTION_LOGGER.debug(
            f"Configuration missing for {name}. Using default: {default_value}"
        )
        return default_value
    except Exception as e:
        JVM_OPTION_LOGGER.warning(
            f"Error retrieving {name}: {str(e)}. Using default: {default_value}"
        )
        return default_value


def _parse_jvm_memory_string(value_str: str, default_value: str) -> str:
    """
    Parse and standardize JVM memory string to megabyte format
    
    Returns standardized string in format: <digits>m
    """
    # Optimization: Skip processing if already correctly formatted
    if value_str.endswith("m") and value_str[:-1].isdigit():
        return value_str
        
    # Check for explicit unit suffix
    match = JVM_MEMORY_REGEX.match(value_str)
    if not match:
        JVM_OPTION_LOGGER.warning(
            f"Invalid JVM memory format: '{value_str}'. "
            f"Using default: {default_value}"
        )
        return default_value
    
    # Extract numeric value and unit
    num_value = int(match.group("value"))
    unit = (match.group("unit") or "m").lower().replace("b", "")
    
    # Handle unitless values (assume megabytes)
    if not unit:
        return f"{num_value}m"
    
    # Convert all units to megabyte equivalent
    unit_conversion = {
        'k': 0.001,     # kilobytes
        'm': 1,         # megabytes (base unit)
        'g': 1024,      # gigabytes
        't': 1024**2,   # terabytes
        'p': 1024**3,   # petabytes
    }
    
    # Calculate megabyte value
    if unit in unit_conversion:
        # Preserve integers when possible
        megabyte_value = num_value * unit_conversion[unit]
        if megabyte_value.is_integer():
            return f"{int(megabyte_value)}m"
        # Use float with one decimal place precision
        return f"{megabyte_value:.1f}m".replace(".0m", "m")
    
    # Unrecognized unit - use as-is but log warning
    JVM_OPTION_LOGGER.warning(
        f"Unrecognized memory unit '{unit}' in {value_str}. Interpreting as MB"
    )
    return f"{num_value}m"


# Test cases to validate functionality
if __name__ == "__main__":
    TEST_CASES = [
        # Valid formats
        ("simple_number", "1024", "1024m"),
        ("explicit_mb", "1024m", "1024m"),
        ("uppercase_m", "2048M", "2048m"),
        ("gigabytes", "2g", "2048m"),
        ("float_gb", "2.5g", "2560m"),
        ("kilobytes", "4096k", "4m"),
        ("terabytes", "1t", "1048576m"),
        
        # Edge cases
        ("zero_value", "0m", "0m"),
        ("large_value", 16384, "16384m"),
        ("whitespace", " 512 ", "512m"),
        
        # Unit variations
        ("gb_unit", "4gb", "4096m"),
        ("mb_unit", "4mb", "4m"),
        ("kb_unit", "4096kb", "4m"),
        
        # Invalid formats
        ("empty", "", "1024m"),  # falls back to default
        ("invalid_str", "invalid", "1024m"),
        ("unit_only", "gb", "1024m"),
        ("negative", "-512m", "1024m"),
    ]
    
    print("JVM Option Formatter Test Results")
    print("=" * 60)
    
    for test_name, input_val, expected in TEST_CASES:
        result = format_jvm_option(test_name, default_value="1024m", input_val=input_val)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status}: {test_name!r}: {input_val} -> {result} (Expected: {expected})")
    
    print("=" * 60)
