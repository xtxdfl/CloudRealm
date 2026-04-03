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

import logging
import threading
import time
import enum
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class ExecutionStatus(enum.Enum):
    """Represents the lifecycle states of background command execution"""
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    STOP_REQUESTED = "STOP_REQUESTED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class BackgroundCommandHandle:
    """
    Advanced background command execution handler with:
        - Lifecycle state management
        - Callback integration
        - Termination safety
        - Execution metrics
    
    Usage:
        handle = BackgroundCommandHandle(
            command="ls -l",
            command_id="cmd_123",
            on_execution_start=start_callback,
            on_execution_complete=complete_callback
        )
        
        # For thread execution
        handle.start()
    """

    MAX_EXECUTION_TIME = 3600  # 1 hour default timeout
    STATUS_TRANSITIONS = {
        ExecutionStatus.SCHEDULED: [ExecutionStatus.RUNNING],
        ExecutionStatus.RUNNING: [
            ExecutionStatus.COMPLETED, 
            ExecutionStatus.STOP_REQUESTED,
            ExecutionStatus.ERROR
        ],
        ExecutionStatus.STOP_REQUESTED: [ExecutionStatus.STOPPED, ExecutionStatus.ERROR],
        ExecutionStatus.STOPPED: [],
        ExecutionStatus.COMPLETED: [],
        ExecutionStatus.ERROR: [],
    }

    def __init__(
        self,
        command: str,
        command_id: str,
        on_execution_start: Optional[Callable[[Any], None]] = None,
        on_execution_complete: Optional[Callable[[int], None]] = None,
        timeout_sec: int = MAX_EXECUTION_TIME
    ):
        """
        Initialize command execution handler
        
        :param command: Shell command to execute
        :param command_id: Unique identifier for the command
        :param on_execution_start: Callback when execution begins (handle)
        :param on_execution_complete: Callback when execution finishes (exit_code)
        :param timeout_sec: Maximum allowed execution time
        """
        self.command = command
        self.command_id = command_id
        self.timeout_sec = timeout_sec
        
        # Execution lifecycle
        self._status = ExecutionStatus.SCHEDULED
        self._pid = 0
        self._exit_code = None
        self._start_time = None
        self._lock = threading.RLock()
        
        # Callback integration
        self.start_callback = on_execution_start or self._default_callback
        self.completion_callback = on_execution_complete or self._default_callback
        
        # Thread execution components
        self._execution_thread = None
        self._stop_event = threading.Event()
        self._termination_timeout = 10  # Seconds to wait for graceful termination

    @property
    def pid(self) -> int:
        """Process identifier of the executing command"""
        return self._pid

    @property
    def status(self) -> ExecutionStatus:
        """Current execution state"""
        return self._status

    @property
    def exit_code(self) -> Optional[int]:
        """Command exit status (available after completion)"""
        return self._exit_code

    @property
    def execution_time(self) -> float:
        """Elapsed/total execution time in seconds"""
        if self._status == ExecutionStatus.SCHEDULED:
            return 0.0
        if self._status in (ExecutionStatus.RUNNING, ExecutionStatus.STOP_REQUESTED):
            return time.time() - self._start_time
        return self._end_time - self._start_time

    def _transition_status(self, new_status: ExecutionStatus) -> bool:
        """Safely transition between execution states"""
        with self._lock:
            if new_status in self.STATUS_TRANSITIONS.get(self._status, []):
                logger.debug(
                    "Command %s status transition: %s → %s",
                    self.command_id,
                    self._status.value,
                    new_status.value
                )
                self._status = new_status
                return True
            logger.warning(
                "Invalid status transition: %s → %s",
                self._status.value,
                new_status.value
            )
            return False

    def start(self) -> bool:
        """Begin command execution thread"""
        if not self._transition_status(ExecutionStatus.RUNNING):
            return False

        self._execution_thread = threading.Thread(
            target=self._execute_command,
            name=f"CmdExec-{self.command_id}",
            daemon=True
        )
        self._start_time = time.time()
        self._execution_thread.start()
        logger.info(
            "Started background command: %s (ID: %s)",
            self.command, self.command_id
        )
        return True

    def stop(self, force=False) -> bool:
        """Request graceful termination of command execution"""
        if self._status in (ExecutionStatus.COMPLETED, ExecutionStatus.STOPPED, ExecutionStatus.ERROR):
            logger.debug(
                "Command %s already in terminal state: %s",
                self.command_id, self._status.value
            )
            return False
        
        if not self._transition_status(ExecutionStatus.STOP_REQUESTED):
            return False
        
        # Signal termination request
        self._stop_event.set()
        logger.info(
            "Requested termination of command %s", self.command_id
        )
        
        # Force termination logic
        if force:
            force_terminated = self._force_terminate()
            if force_terminated:
                return True
        
        # Wait for graceful termination
        if self._execution_thread:
            self._execution_thread.join(self._termination_timeout)
        
        return self._status == ExecutionStatus.STOPPED

    def _force_terminate(self) -> bool:
        """System-level command termination"""
        # Placeholder for actual process termination logic
        # This would actually send SIGTERM to the process
        logger.warning(
            "Force terminating command %s", self.command_id
        )
        return self._transition_status(ExecutionStatus.STOPPED)

    def _execute_command(self):
        """Execute the command with lifecycle management"""
        try:
            # Notify execution start
            self.start_callback(self)
            
            # Command execution simulation
            # In real implementation, this would use subprocess
            logger.info(
                "Executing command %s: %s",
                self.command_id, self.command
            )
            for i in range(self.timeout_sec):
                if self._stop_event.is_set():
                    logger.info("Command termination requested during execution")
                    break
                time.sleep(1)
            
            # Simulate successful execution
            result = 0
        except Exception as e:
            logger.error(
                "Command execution failed: %s", 
                str(e),
                exc_info=True
            )
            result = 1
        finally:
            self._complete_execution(result)

    def _complete_execution(self, exit_code: int):
        """Finalize command execution"""
        try:
            self._exit_code = exit_code
            self._end_time = time.time()
            
            # Update status based on exit code
            if self._status == ExecutionStatus.STOP_REQUESTED:
                final_status = ExecutionStatus.STOPPED
            elif exit_code == 0:
                final_status = ExecutionStatus.COMPLETED
            else:
                final_status = ExecutionStatus.ERROR
            
            self._transition_status(final_status)
            self.completion_callback(exit_code)
            
            logger.info(
                "Command %s completed with status %s (exit code: %d, time: %.1fs)",
                self.command_id,
                final_status.value,
                exit_code,
                self.execution_time
            )
        except Exception as e:
            logger.error(
                "Error completing command execution: %s",
                str(e),
                exc_info=True
            )

    def _default_callback(self, *args):
        """Default callback placeholder"""
        logger.debug("Callback triggered with %s", args)

    def wait_for_completion(self, timeout: float = None) -> bool:
        """Block until command execution completes or timeout"""
        return self._execution_thread.join(timeout) if self._execution_thread else True

    def __str__(self):
        return (
            f"[CommandHandle: id='{self.command_id}', "
            f"status='{self.status.value}', "
            f"pid={self.pid}, "
            f"exit_code={self.exit_code}, "
            f"time={self.execution_time:.1f}s]"
        )

    def __repr__(self):
        return (
            f"<BackgroundCommandHandle(command={self.command!r}, "
            f"command_id={self.command_id!r}, "
            f"status={self.status})>"
        )
