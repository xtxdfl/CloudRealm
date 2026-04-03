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

Enhanced Configuration Checker Utility
"""

from typing import Any
from resource_management.libraries.script.config_dictionary import UnknownConfiguration

def is_empty(config_value: Any) -> bool:
    """
    Determine if a configuration value is considered "empty" in the context of cloud configuration management.
    
    This function specializes in identifying:
    1. Values explicitly marked as 'UnknownConfiguration' (sentinel value from the server)
    2. Python False-equivalent values (None, empty sequences, etc.)
    
    Args:
        config_value: Any configuration value from the cloud server
        
    Returns:
        True if the value is semantically empty in the configuration context, False otherwise
    """
    # First priority: Check for UnknownConfiguration marker
    if isinstance(config_value, UnknownConfiguration):
        return True
        
    # Second: Check for NoneType value
    if config_value is None:
        return True
    
    # Third: Check for false-equivalents (empty strings, zero-length collections)
    try:
        # Empty string or bytestring?
        if not config_value:
            return True
    except (TypeError, ValueError):
        # Non-iterable/non-bool types will raise - not empty
        pass
        
    return False

# Compatibility layer for legacy use cases
def is_unknown_config(value: Any) -> bool:
    """Legacy alias for is_empty (preserving backward compatibility)"""
    return isinstance(value, UnknownConfiguration)

# Example Usage
if __name__ == "__main__":
    class MockUnknownConfig:
        """Simulate UnknownConfiguration for testing"""
        pass
    
    test_cases = [
        (UnknownConfiguration, True, "UnknownConfiguration marker"),
        (None, True, "Explicit None value"),
        ("", True, "Empty string"),
        ([], True, "Empty list"),
        ({}, True, "Empty dictionary"),
        (0, False, "Zero value"),
        (False, True, "False boolean"),
        (True, False, "True boolean"),
        ("value", False, "Non-empty string"),
        (["item"], False, "Non-empty list"),
        ({"key": "value"}, False, "Non-empty dict"),
        (MockUnknownConfig(), True, "UnknownConfig subclass")
    ]
    
    print("Configuration Value Check Results:")
    for value, expected, desc in test_cases:
        result = is_empty(value)
        check = "PASS" if result == expected else "FAIL"
        print(f"{check} - {desc} ({value}): {result}")

