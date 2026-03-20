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

Enhanced Command Execution with Pattern Matching
"""

import re
import time
import logging
import subprocess
from typing import Optional, Pattern, Tuple, Dict, Any
from functools import wraps

# Configure logger
CMD_LOGGER = logging.getLogger("command_matcher")
CMD_LOGGER.setLevel(logging.DEBUG)

# Default retry settings
DEFAULT_RETRIES = 5
DEFAULT_BACKOFF = 2
MAX_BACKOFF = 60
STATUS_THRESHOLD = 1.5  # seconds for slow command logging

class CommandError(RuntimeError):
    """Custom exception for command execution failures"""
    def __init__(self, message, command, output, exit_code, pattern):
        super().__init__(message)
        self.command = command
        self.output = output
        self.exit_code = exit_code
        self.pattern = pattern

    def __str__(self):
        return (
            f"CommandError[cmd={self.command}, code={self.exit_code}, "
            f"pattern='{self.pattern}']: {super().__str__()}"
        )
        
def retry(
    retries: int = DEFAULT_RETRIES, 
    initial_backoff: int = DEFAULT_BACKOFF,
    max_backoff: int = MAX_BACKOFF,
    exponential: bool = True,
    retry_on: Optional[Tuple[Exception]] = None,
    logger: Optional[logging.Logger] = None
):
    """
    Enhanced retry decorator with exponential backoff and custom exception handling
    
    Params:
        retries: Maximum number of retry attempts
        initial_backoff: Initial wait time in seconds
        max_backoff: Maximum wait time between retries
        exponential: Use exponential backoff (True) or fixed backoff (False)
        retry_on: Tuple of exception types to retry (default: all exceptions)
        logger: Logger instance for logging retry attempts
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or CMD_LOGGER
            attempts = 0
            current_backoff = initial_backoff
            last_exc = None
            
            while attempts <= retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    # Check if we should retry this exception
                    if retry_on and not isinstance(e, retry_on):
                        raise
                    
                    attempts += 1
                    if attempts > retries:
                        log.error(
                            f"Operation failed after {retries} retries. Last error: {str(e)}"
                        )
                        raise
                    
                    # Calculate next wait time
                    wait_time = min(
                        initial_backoff * (2 ** (attempts - 1)) if exponential else initial_backoff, 
                        max_backoff
                    )
                    log.warning(
                        f"Attempt {attempts}/{retries} failed. Retrying in {wait_time:.1f}s. Error: {str(e)}"
                    )
                    
                    # Wait with backoff
                    time.sleep(wait_time)
                    
            # Should never reach here, just in case
            raise last_exc
        return wrapper
    return decorator

def call_and_match_output(
    command: str,
    pattern: str,
    error_message: str,
    timeout: int = 300,
    cwd: str = None,
    env: Dict[str, str] = None,
    retries: int = DEFAULT_RETRIES,
    case_insensitive: bool = True,
    timeout_error: bool = True,
    log_output: bool = True,
    **shell_args
) -> Tuple[bool, str]:
    """
    Execute a command and verify its output matches a regex pattern with enhanced capabilities
    
    Features:
    - Pattern compilation caching for performance
    - Detailed error diagnostics
    - Timeout protection
    - Environment customization
    - Output logging control
    - Customizable retry logic
    
    Args:
        command: Shell command to execute
        pattern: Regex pattern to match in command output
        error_message: Custom error message if pattern doesn't match
        timeout: Execution timeout in seconds
        cwd: Working directory for command
        env: Environment variables dictionary
        retries: Number of retry attempts
        case_insensitive: Perform case-insensitive matching
        timeout_error: Treat timeout as match failure (not execution error)
        log_output: Log command outputs for debugging
        **shell_args: Additional shell execution arguments
        
    Returns:
        Tuple (success (bool), output text)
    
    Raises:
        CommandError: When pattern doesn't match after all retries
        TimeoutExpired: When command times out
        CalledProcessError: When command returns non-zero exit status
    """
    # Validate parameters
    if not command:
        raise ValueError("Command cannot be empty")
    if not pattern:
        raise ValueError("Pattern cannot be empty")
    
    # Pre-compile regex with caching
    flags = re.IGNORECASE if case_insensitive else 0
    regex = re.compile(pattern, flags)
    
    # Setup execution context
    exec_info = {
        "command": command,
        "pattern": pattern,
        "error_message": error_message,
        "start_time": time.time()
    }
    
    # Run the command with retries
    return _retry_command(
        exec_info, 
        regex, 
        timeout, 
        cwd, 
        env, 
        retries, 
        timeout_error,
        log_output,
        **shell_args
    )

def _retry_command(
    exec_info: Dict[str, Any],
    regex: Pattern,
    timeout: int,
    cwd: str,
    env: Dict[str, str],
    max_retries: int,
    timeout_error: bool,
    log_output: bool,
    **shell_args
) -> Tuple[bool, str]:
    """Core command execution with retry logic"""
    attempts = 0
    output = ""
    
    # Get current environment with optional overrides
    full_env = env if env else os.environ.copy()
    
    # Run loop with retries
    while attempts <= max_retries:
        attempts += 1
        try:
            # Execute command with timeout
            output = _execute_command(
                exec_info["command"], 
                timeout, 
                cwd, 
                full_env, 
                log_output
            )
            
            # Check for pattern match
            if regex.search(output):
                exec_time = time.time() - exec_info["start_time"]
                CMD_LOGGER.info(
                    f"Pattern found in command output "
                    f"[{exec_info['command']}] in {exec_time:.2f}s"
                )
                return True, output
            
            # Pattern not found
            err_msg = (
                f"{exec_info['error_message']} "
                f"(pattern: '{exec_info['pattern']}')"
            )
            raise CommandError(
                message=err_msg,
                command=exec_info["command"],
                output=output,
                exit_code=0,
                pattern=exec_info["pattern"]
            )
        
        except CommandError:
            # Re-raise after last retry
            if attempts > max_retries:
                CMD_LOGGER.error(
                    f"Pattern not found after {max_retries} retries: "
                    f"{exec_info['pattern']}"
                )
                raise
                
            # Log retry warning
            CMD_LOGGER.warning(
                f"Retry {attempts}/{max_retries}: Pattern not found for "
                f"command: {exec_info['command']}"
            )
            
        except subprocess.TimeoutExpired as to:
            if not timeout_error or attempts > max_retries:
                raise
            
            CMD_LOGGER.warning(
                f"Command {exec_info['command']} timed out. "
                f"Retrying ({attempts}/{max_retries})..."
            )
            output = ""
            
        except Exception as e:
            if attempts > max_retries:
                raise
                
            CMD_LOGGER.warning(
                f"Command execution failed: {str(e)}. "
                f"Retrying ({attempts}/{max_retries})..."
            )
    
    # Should not reach here
    raise RuntimeError(
        f"Unexpected exit from retry loop for command: {exec_info['command']}"
    )

def _execute_command(
    command: str,
    timeout: int,
    cwd: str = None,
    env: Dict[str, str] = None,
    log_output: bool = True
) -> str:
    """
    Execute command with robust output capture and timeout handling
    
    Args:
        command: Command string to execute
        timeout: Execution timeout in seconds
        cwd: Working directory
        env: Environment variables
        log_output: Log command outputs
        
    Returns:
        Command output string with STDOUT/STDERR combined
        
    Raises:
        subprocess.TimeoutExpired: On execution timeout
        subprocess.CalledProcessError: On non-zero exit code
    """
    start_time = time.time()
    
    # Split command for shell=False execution
    if isinstance(command, str):
        command = [arg.strip() for arg in re.split(r'\s+', command) if arg.strip()]
    
    # Execute command
    CMD_LOGGER.debug(f"Executing: {' '.join(command)}")
    if log_output:
        CMD_LOGGER.debug(f"Command environment: {json.dumps(env, indent=2)}")
    
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            check=True
        )
        output = result.stdout
        
    except subprocess.CalledProcessError as cpe:
        # Capture non-zero exit output
        output = cpe.stdout or cpe.stderr or ""
        raise CommandError(
            message=f"Command failed with code {cpe.returncode}",
            command=command,
            output=output,
            exit_code=cpe.returncode,
            pattern=""
        ) from cpe
        
    # Log performance metrics
    exec_time = time.time() - start_time
    if exec_time > STATUS_THRESHOLD:
        CMD_LOGGER.info(
            f"Command completed in {exec_time:.2f}s: {' '.join(command)}"
        )
    
    if log_output:
        # Prevent logging huge outputs
        if len(output) > 1024:
            log_out = output[:512] + " ... [truncated] ... " + output[-512:]
        else:
            log_out = output
            
        CMD_LOGGER.debug(f"Command output:\n{log_out}")
        
    return output

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        # Successful pattern matching
        print("Testing successful command...")
        success, output = call_and_match_output(
            command="echo 'Hello World' && sleep 1",
            pattern=r"Hello\s+World",
            error_message="Greeting not found"
        )
        print(f"Success: {success}, Output: {output.strip()}")
        
        # Failed pattern matching
        print("\nTesting failed command...")
        try:
            success, output = call_and_match_output(
                command="echo 'Test Failure'",
                pattern=r"Success",
                error_message="Expected success message",
                retries=2
            )
        except CommandError as ce:
            print(f"Caught expected error: {str(ce)}")
        
        # Command timeout
        print("\nTesting timeout command...")
        try:
            success, output = call_and_match_output(
                command="echo 'Starting' && sleep 5",
                pattern=r"Starting",
                error_message="Start message missing",
                timeout=1
            )
        except CommandError as ce:
            print(f"Caught timeout: {str(ce)}")
            
        # Retry logic demo
        print("\nTesting retry with increasing sleep...")
        try:
            success, output = call_and_match_output(
                command="echo 'Attempt ${COUNT:-1}' && sleep ${SLEEP:-0}",
                pattern=r"Attempt\s+3",
                error_message="Never reached attempt 3",
                env={"COUNT": "1", "SLEEP": "1"},
                retries=5
            )
        except CommandError as ce:
            print(f"Failed: {str(ce)}")
    
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
