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
"""

"""
Enhanced Python Process Debugger
================================

This tool provides an interactive debugging environment for running Python 
processes. Key features:

- Secure interrupt mechanism for live processes
- Named pipe communication channel
- Interactive debugging session
- PID validation and process existence checks
- Graceful fallbacks and error reporting
"""

import os
import sys
import signal
import logging
import argparse
import traceback
from typing import Optional
from enum import Enum

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("PyDebugger")

class DebuggerMode(Enum):
    """Operation modes for the debugger"""
    ATTACH = "attach"
    EMERGENCY_INTERRUPT = "interrupt"
    INFO = "info"
    MONITOR = "monitor"

class PIDError(ValueError):
    """Custom exception for PID-related errors"""
    pass

class NamedPipe:
    """
    Secure Named Pipe Wrapper
    ========================
    
    Provides safe and reliable named pipe communication with 
    automatic cleanup and error handling.
    """
    def __init__(self, pipe_name: str, timeout: int = 10):
        self.pipe_name = pipe_name
        self.timeout = timeout
        self.pipe_fd = None

    def __enter__(self):
        """Context manager entry point"""
        logger.debug("Opening pipe: %s", self.pipe_name)
        try:
            self.pipe_fd = os.open(self.pipe_name, os.O_RDWR)
            return self
        except OSError as e:
            logger.error("Pipe open failed: %s", str(e))
            raise ConnectionError(f"Cannot open pipe {self.pipe_name}") from e

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit point - ensure pipe is closed"""
        if self.pipe_fd:
            os.close(self.pipe_fd)
            logger.debug("Closed pipe: %s", self.pipe_name)
        # Exception suppression
        return exc_type is None

    def put(self, message: str) -> bool:
        """Write a message to the pipe"""
        if not self.pipe_fd:
            return False
            
        try:
            os.write(self.pipe_fd, message.encode("utf-8"))
            return True
        except OSError as e:
            logger.error("Pipe write failed: %s", str(e))
            return False

    def get(self, buffer_size: int = 4096) -> Optional[str]:
        """Read a message from the pipe"""
        if not self.pipe_fd:
            return None
            
        try:
            result = os.read(self.pipe_fd, buffer_size)
            return result.decode("utf-8").strip()
        except OSError as e:
            logger.error("Pipe read failed: %s", str(e))
            return None
        except UnicodeDecodeError:
            logger.error("Invalid data received from pipe")
            return None

def pipename(pid: int) -> str:
    """Generate name for debug pipe based on PID"""
    return f"/tmp/debug_{pid}.pipe"

def validate_pid(pid: int) -> bool:
    """Check if a process with given PID exists"""
    try:
        # Signal 0 checks process existence without affecting it
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        logger.error("Process with PID %d does not exist", pid)
        return False
    except PermissionError:
        logger.error("Insufficient permissions to interact with PID %d", pid)
        return False
    except Exception as e:
        logger.error("PID validation error: %s", str(e))
        return False

def create_debug_pipe(pid: int) -> bool:
    """Create named pipe for debugging session"""
    pipe_name = pipename(pid)
    
    try:
        # Create FIFO if not exists
        if not os.path.exists(pipe_name):
            os.mkfifo(pipe_name, 0o600)  # Secure permissions
        
        # Ensure correct ownership
        if os.stat(pipe_name).st_uid != os.getuid():
            os.chown(pipe_name, os.getuid(), os.getgid())
        
        logger.info("Debug pipe created: %s", pipe_name)
        return True
    except OSError as e:
        logger.error("Failed to create pipe: %s", str(e))
        return False

def get_default_pid_path(default_path: str = "/var/run/cloud-agent/cloud-agent.pid") -> Optional[int]:
    """Get PID from default path with verification"""
    try:
        if not os.path.exists(default_path):
            logger.error("PID file not found at %s", default_path)
            return None
        
        with open(default_path, "r") as pid_file:
            pid_str = pid_file.read().strip()
            return int(pid_str)
    except FileNotFoundError:
        logger.error("PID file not found at %s", default_path)
    except ValueError:
        logger.error("Invalid PID in %s: '%s'", default_path, pid_str)
    except Exception as e:
        logger.error("Failed to read PID file: %s", str(e))
    
    return None

def debug_process(pid: int, mode: DebuggerMode = DebuggerMode.ATTACH):
    """
    Interrupt and debug a running process
    """
    # Verify process existence
    if not validate_pid(pid):
        raise PIDError(f"Invalid PID: {pid}")
    
    # Create communication pipe if needed
    if mode in [DebuggerMode.ATTACH, DebuggerMode.MONITOR]:
        if not create_debug_pipe(pid):
            raise ConnectionError("Failed to create debug pipe")
    
    # Send signal to target process
    logger.info("Sending debug signal to PID %d...", pid)
    try:
        os.kill(pid, signal.SIGUSR2)  # Request debug interrupt
    except (PermissionError, ProcessLookupError) as e:
        logger.critical("Signal failed: %s", str(e))
        sys.exit(1)
    
    # Interactive debug session
    if mode == DebuggerMode.ATTACH:
        logger.info("Entering interactive debug session. Press Ctrl+D to exit.")
        with NamedPipe(pipename(pid)) as pipe:
            try:
                while True:
                    # Display prompt
                    try:
                        output = pipe.get()
                        if output:
                            sys.stdout.write(output)
                        sys.stdout.write("(debug) ")
                        sys.stdout.flush()
                    except BrokenPipeError:
                        logger.info("Debug session closed by target process")
                        break
                    
                    # Get user input
                    try:
                        user_input = sys.stdin.readline()
                        if not user_input:  # EOF (Ctrl+D)
                            logger.info("Session terminated by user")
                            break
                        pipe.put(user_input.rstrip('\n') + '\n')
                    except BrokenPipeError:
                        logger.info("Debug session closed by target process")
                        break
            except Exception as e:
                logger.error("Debug session error: %s", str(e))
    
    # Monitor-only mode
    elif mode == DebuggerMode.MONITOR:
        logger.info("Entering read-only monitoring mode (press Ctrl+C to exit)")
        with NamedPipe(pipename(pid)) as pipe:
            try:
                while True:
                    output = pipe.get()
                    if output:
                        print("\n>>", output)
            except KeyboardInterrupt:
                logger.info("Monitoring session terminated")
            except Exception as e:
                logger.error("Monitoring error: %s", str(e))
    
    # Emergency interrupt without debug shell
    elif mode == DebuggerMode.EMERGENCY_INTERRUPT:
        logger.warning("Emergency interrupt complete. Process may be in unstable state.")
    else:
        # Info mode: just sent signal but didn't open channel
        logger.info("Debug signal sent. Attach a debugger to inspect process state.")


if __name__ == "__main__":
    # Command-line arguments
    parser = argparse.ArgumentParser(
        description="Python Process Debugger",
        epilog="Use with caution on production systems"
    )
    parser.add_argument(
        "-p", "--pid", 
        type=int,
        help="Target Process ID to debug"
    )
    parser.add_argument(
        "-m", "--mode", 
        default="attach",
        choices=["attach", "interrupt", "info", "monitor"],
        help="Debug mode: attach (interactive), interrupt (emergency), info (signal only), monitor (read-only)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--pid-file",
        default="/var/run/cloud-agent/cloud-agent.pid",
        help="Path to PID file containing target process ID"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Resolve target PID
        target_pid = None
        if args.pid:
            target_pid = args.pid
            logger.debug("Using PID from command line: %d", target_pid)
        else:
            logger.debug("Using default PID file: %s", args.pid_file)
            target_pid = get_default_pid_path(args.pid_file)
            
        if not target_pid:
            parser.error("Unable to determine target PID")
        
        # Set debug mode
        mode = DebuggerMode(args.mode)
        logger.info("Initiating %s mode for PID %d", mode.value.upper(), target_pid)
        
        # Start debugging session
        debug_process(target_pid, mode)
        
    except PIDError as pe:
        logger.critical("PID Error: %s", str(pe))
        sys.exit(1)
    except ConnectionError as ce:
        logger.critical("Connection Error: %s", str(ce))
        sys.exit(2)
    except BrokenPipeError:
        logger.info("Connection closed by target process")
    except KeyboardInterrupt:
        logger.info("Debug session terminated by user")
    except Exception as e:
        logger.critical("Critical Error: %s", str(e))
        logger.debug("Traceback:\n%s", traceback.format_exc())
        sys.exit(3)
    
    logger.info("Debugger exited successfully")

