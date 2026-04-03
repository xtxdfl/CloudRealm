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

Enhanced Cluster Alert Behavior Simulator
"""

import logging
import random
import time
from datetime import datetime
from resource_management.core.exceptions import Fail
from typing import Dict, Tuple, List

# Configure logger
logger = logging.getLogger("cloud_alerts")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

# Alert result constants
RESULT_CODE_OK = "OK"
RESULT_CODE_CRITICAL = "CRITICAL"
RESULT_CODE_UNKNOWN = "UNKNOWN"

# Default message templates
MESSAGE_TEMPLATES = {
    RESULT_CODE_OK: "Ok: All systems are functioning normally",
    RESULT_CODE_CRITICAL: "Critical: Service disruption detected",
    RESULT_CODE_UNKNOWN: "Unknown: Unable to determine cluster status"
}

# Behavior key constants
BEHAVIOR_TYPE = "alert_behaviour_type"
PERCENTAGE_KEY = "alert_success_percentage"
TIMEOUT_RETURN = "alert_timeout_return_value"
TIMEOUT_DURATION = "alert_timeout_secs"
FLIP_INTERVAL = "alert_flip_interval_mins"

# Predefined behavior outputs
BEHAVIOR_RESULTS = {
    "true": (RESULT_CODE_OK, MESSAGE_TEMPLATES[RESULT_CODE_OK]),
    "false": (RESULT_CODE_CRITICAL, MESSAGE_TEMPLATES[RESULT_CODE_CRITICAL]),
    "none": (RESULT_CODE_UNKNOWN, MESSAGE_TEMPLATES[RESULT_CODE_UNKNOWN])
}


def simulate_perf_cluster_alert_behaviour(
        alert_behaviour_properties: Dict,
        configurations: Dict) -> Tuple[str, List[str]]:
    """
    Simulates various cluster alert behaviors for testing and performance evaluation.
    
    The function supports three simulation modes:
    1. Percentage-based behavior: Randomly returns success or failure based on configured percentage
    2. Timeout-based behavior: Sleeps for specified time before returning result
    3. Flip-flop behavior: Alternates between success and failure based on time intervals
    
    Args:
        alert_behaviour_properties: Dictionary containing behavior configuration keys
        configurations: Dictionary of current configuration settings
        
    Returns:
        Tuple containing the result code (OK/CRITICAL/UNKNOWN) and a list of result messages
    """
    # Extract behavior type from configurations
    behavior = configurations.get(
        alert_behaviour_properties.get(BEHAVIOR_TYPE, "")
    )
    
    # Default behavior if no specific type is configured
    if not behavior:
        logger.debug("No behavior specified, returning default OK state")
        return (RESULT_CODE_OK, [MESSAGE_TEMPLATES[RESULT_CODE_OK]])
    
    behavior = behavior.lower()
    logger.debug(f"Simulating '{behavior}' alert behavior")
    
    try:
        # Process percentage-based behavior
        if behavior == "percentage":
            return _handle_percentage_behavior(
                alert_behaviour_properties, configurations)
        
        # Process timeout-based behavior
        elif behavior == "timeout":
            return _handle_timeout_behavior(
                alert_behaviour_properties, configurations)
        
        # Process flip-flop behavior
        elif behavior == "flip":
            return _handle_flip_behavior(
                alert_behaviour_properties, configurations)
        
        # Handle unknown behavior types
        else:
            return _handle_unknown_behavior(behavior)
            
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Configuration error: {str(e)}")
        return (RESULT_CODE_UNKNOWN, [f"Configuration error: {str(e)}"])
    except Fail as f:
        logger.error(f"Behavior simulation failed: {str(f)}")
        return (RESULT_CODE_CRITICAL, [f"Behavior failure: {str(f)}"])
    except Exception as e:
        logger.exception("Unexpected error in alert simulation")
        return (RESULT_CODE_UNKNOWN, [f"Unexpected error: {str(e)}"])


def _handle_percentage_behavior(
        alert_behaviour_properties: Dict,
        configurations: Dict) -> Tuple[str, List[str]]:
    """
    Handles percentage-based alert behavior simulation.
    
    Returns OK/Critical based on configured success probability.
    """
    # Get percentage configuration with error checking
    percent_key = alert_behaviour_properties.get(PERCENTAGE_KEY, "")
    success_percent = configurations.get(percent_key)
    
    if success_percent is None or not success_percent.strip():
        raise Fail(f"Percentage behavior requires '{PERCENTAGE_KEY}' configuration")
    
    # Convert and validate percentage value
    try:
        success_percent = float(success_percent)
        if not 0 <= success_percent <= 100:
            raise ValueError("Percentage must be between 0-100")
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid percentage value: {success_percent} - {e}")
        return (RESULT_CODE_UNKNOWN, ["Invalid success percentage configuration"])
    
    # Generate random result based percentage
    rand_val = random.uniform(0, 100)
    if rand_val <= success_percent:
        result_code, message = BEHAVIOR_RESULTS["true"]
        logger.info(f"Success (chance: {success_percent}%) - {message}")
    else:
        result_code, message = BEHAVIOR_RESULTS["false"]
        logger.info(f"Failure (chance: {100-success_percent}%) - {message}")
    
    return result_code, [message]


def _handle_timeout_behavior(
        alert_behaviour_properties: Dict,
        configurations: Dict) -> Tuple[str, List[str]]:
    """
    Handles timeout-based alert behavior simulation.
    
    Sleeps for specified duration before returning result.
    """
    # Get timeout configuration with error checking
    return_key = alert_behaviour_properties.get(TIMEOUT_RETURN, "")
    duration_key = alert_behaviour_properties.get(TIMEOUT_DURATION, "")
    
    result_type = configurations.get(return_key)
    timeout_secs = configurations.get(duration_key)
    
    if not result_type or not timeout_secs:
        missing = []
        if not result_type: missing.append(TIMEOUT_RETURN)
        if not timeout_secs: missing.append(TIMEOUT_DURATION)
        raise Fail(f"Timeout behavior requires {', '.join(missing)} configuration")
    
    # Validate timeout value
    try:
        timeout_secs = int(timeout_secs)
        if timeout_secs <= 0:
            raise ValueError("Timeout must be a positive integer")
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid timeout value: {timeout_secs} - {e}")
        return (RESULT_CODE_UNKNOWN, ["Invalid timeout duration configuration"])
    
    # Execute timeout and return result
    try:
        result_type = result_type.lower()
        
        logger.info(f"Simulating timeout behavior: sleeping for {timeout_secs} seconds")
        start = time.perf_counter()
        time.sleep(timeout_secs)
        elapsed = time.perf_counter() - start
        
        if result_type in BEHAVIOR_RESULTS:
            result_code, message = BEHAVIOR_RESULTS[result_type]
            logger.info(f"Timeout completed ({elapsed:.2f}s): {message}")
            return result_code, [message]
        else:
            raise Fail(f"Invalid return type: {result_type}")
    except (InterruptedError, KeyboardInterrupt):
        logger.warning("Timeout behavior interrupted")
        return (RESULT_CODE_UNKNOWN, ["Alert simulation interrupted"])


def _handle_flip_behavior(
        alert_behaviour_properties: Dict,
        configurations: Dict) -> Tuple[str, List[str]]:
    """
    Handles flip-flop alert behavior simulation.
    
    Alternates between OK and Critical states based on time intervals.
    """
    # Get flip interval configuration with error checking
    interval_key = alert_behaviour_properties.get(FLIP_INTERVAL, "")
    interval_mins = configurations.get(interval_key)
    
    if not interval_mins:
        raise Fail(f"Flip behavior requires '{FLIP_INTERVAL}' configuration")
    
    # Convert and validate interval value
    try:
        interval_mins = int(interval_mins)
        if interval_mins <= 0:
            raise ValueError("Flip interval must be a positive integer")
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid flip interval: {interval_mins} - {e}")
        return (RESULT_CODE_UNKNOWN, ["Invalid flip interval configuration"])
    
    # Calculate flip state based on current time
    now = datetime.utcnow()
    flip_state = (now.minute // interval_mins) % 2 == 0
    state_str = "OK" if flip_state else "CRITICAL"
    
    logger.info(f"Flip state at {now.time()}: {state_str} "
                f"(changes every {interval_mins} min)")
    
    result_code, message = BEHAVIOR_RESULTS[str(flip_state).lower()]
    return result_code, [f"{message} | Flip state: {state_str}"]


def _handle_unknown_behavior(behavior_type: str) -> Tuple[str, List[str]]:
    """Handles unknown or unrecogized behavior types."""
    logger.warning(f"Unknown alert behavior type: '{behavior_type}'")
    return (RESULT_CODE_UNKNOWN, 
           [f"Unknown behavior type: '{behavior_type}'"])


if __name__ == "__main__":
    # Test configurations for simulated alert behavior
    test_properties = {
        "alert_behaviour_type": "alert.behavior.type",
        "alert_success_percentage": "alert.success.percent",
        "alert_timeout_return_value": "alert.timeout.return",
        "alert_timeout_secs": "alert.timeout.secs",
        "alert_flip_interval_mins": "alert.flip.interval"
    }
    
    # Test configuration set 1: Percentage-based behavior
    test_config1 = {
        "alert.behavior.type": "percentage",
        "alert.success.percent": "75"  # 75% success rate
    }
    
    # Test configuration set 2: Timeout-based behavior
    test_config2 = {
        "alert.behavior.type": "timeout",
        "alert.timeout.secs": "3",     # 3-second timeout
        "alert.timeout.return": "false" # Return "Critical" after timeout
    }
    
    # Test configuration set 3: Flip-flop behavior
    test_config3 = {
        "alert.behavior.type": "flip",
        "alert.flip.interval": "5"     # Flip state every 5 minutes
    }
    
    # Execute test scenarios
    print("\n=== Testing Percentage Behavior ===")
    for i in range(5):
        print(simulate_perf_cluster_alert_behaviour(
            test_properties, test_config1))
    
    print("\n=== Testing Timeout Behavior ===")
    print(simulate_perf_cluster_alert_behaviour(
        test_properties, test_config2))
    
    print("\n=== Testing Flip-Flop Behavior ===")
    print(simulate_perf_cluster_alert_behaviour(
        test_properties, test_config3))
