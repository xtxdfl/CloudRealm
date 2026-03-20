#!/usr/bin/env python
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

import os
import sys
import signal
import time
import logging
import threading
import weakref
import traceback
import atexit
from typing import Callable, Tuple, Any, List, Optional

# Configure logging
logger = logging.getLogger("ResourceCleaner")

class ExitManager:
    """Advanced Resource Cleanup and Teardown Manager
    
    Provides a robust, thread-safe mechanism for managing resource cleanup
    during application shutdown. Key features:
    
    - Guaranteed execution of cleanup routines
    - Prioritized and ordered cleanup
    - Thread-safe operation
    - Detailed progress logging
    - Recovery mechanisms for hung processes
    - Resource tracking and monitoring
    """
    
    # Priority levels for cleanup functions
    PRIORITY_CRITICAL = 0
    PRIORITY_HIGH = 1
    PRIORITY_NORMAL = 2
    PRIORITY_LOW = 3
    
    # Exit status codes
    CLEAN_EXIT = 0
    ERROR_IN_CLEANUP = 3
    
    # Default timeout for critical operations (seconds)
    CRITICAL_TIMEOUT = 10
    
    def __init__(self):
        """Initialize the resource manager"""
        self.cleanup_registry = {}
        self.resources = weakref.WeakValueDictionary()
        self.exit_lock = threading.RLock()
        self.exit_code = self.CLEAN_EXIT
        self.cleaning_started = False
        self.timeout_thread = None
        self.log_level = logging.INFO
        
        # Set up automatic cleanup
        atexit.register(self.execute_cleanup)
        
        # Capture process signals
        self.register_signal_handlers()
        
        logger.info("Resource manager initialized. Registered for graceful termination")
    
    def configure_logging(self, level=logging.INFO):
        """Configure logging verbosity for cleanup process"""
        self.log_level = level
        logging.getLogger().setLevel(level)
    
    def register_signal_handlers(self):
        """Register handlers for process termination signals"""
        signals = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, 'SIGHUP'):
            signals.append(signal.SIGHUP)
        
        for sig in signals:
            try:
                signal.signal(sig, self.signal_handler)
                logger.debug("Registered handler for signal %d", sig)
            except (ValueError, OSError):
                logger.warning("Cannot register handler for signal %d", sig)
    
    def signal_handler(self, signum, frame):
        """Handle termination signals gracefully"""
        logger.warning("Received termination signal %d. Initiating cleanup...", signum)
        self.execute_cleanup()
        logger.info("Cleanup completed. Exiting process")
        sys.exit(self.exit_code)
    
    def register(
        self,
        func: Callable,
        *args,
        priority: int = PRIORITY_NORMAL,
        name: str = None,
        critical: bool = False,
        timeout: int = None,
        **kwargs
    ) -> None:
        """Register a function for cleanup
        
        :param func: Function to call during cleanup
        :param priority: Execution priority (lower numbers first)
        :param name: Descriptive name for this resource
        :param critical: If True, failure will cause non-zero exit
        :param timeout: Max execution time (seconds) for critical operations
        :param args: Positional arguments to pass to func
        :param kwargs: Keyword arguments to pass to func
        """
        if self.cleaning_started:
            logger.error("Cannot register resource %s during cleanup phase", name or "unnamed")
            return
        
        with self.exit_lock:
            # Name defaults to function name
            name = name or func.__name__
            
            # Generate unique identifier even for same-named resources
            uid = f"{name}_{time.time_ns()}"
            
            if critical and timeout is None:
                timeout = self.CRITICAL_TIMEOUT
            
            self.cleanup_registry[uid] = {
                'func': func,
                'args': args,
                'kwargs': kwargs,
                'priority': priority,
                'name': name,
                'critical': critical,
                'timeout': timeout
            }
            
            logger.info("Registered resource %s with priority %d", name, priority)
    
    def register_resource(
        self,
        resource: object,
        teardown: Callable,
        name: str = None,
        priority: int = PRIORITY_NORMAL,
        **kwargs
    ) -> None:
        """Register a resource object for teardown
        
        :param resource: Resource object to track
        :param teardown: Function for deallocating the resource
        :param name: Descriptive name for the resource
        :param priority: Cleanup priority
        """
        name = name or type(resource).__name__
        uid = f"{name}_{id(resource)}"
        self.resources[uid] = resource
        self.register(teardown, priority=priority, name=f"{name}_teardown", **kwargs)
    
    def monitor_resource(self, resource: Any, name: Optional[str] = None) -> None:
        """Lightweight resource monitoring without cleanup registration"""
        if name is None:
            name = getattr(type(resource), '__name__', 'resource')
        uid = f"{name}_{id(resource)}"
        self.resources[uid] = resource
        logger.debug("Tracking resource: %s", uid)
    
    def report_resources(self) -> List[str]:
        """Get list of currently tracked resources"""
        return list(self.resources.keys())
    
    def set_exit_code(self, code: int) -> None:
        """Set exit code to be returned after cleanup"""
        if code != self.CLEAN_EXIT:
            self.exit_code = code
    
    def execute_cleanup(self, max_attempts: int = 2) -> None:
        """Execute all registered cleanup functions in priority order"""
        if self.cleaning_started:
            logger.debug("Cleanup already in progress. Ignoring duplicate call")
            return
        
        # Mark cleanup as started
        self.cleaning_started = True
        logger.log(
            self.log_level,
            "Starting resource cleanup. Processing %d registered tasks",
            len(self.cleanup_registry)
        )
        
        with self.exit_lock:
            # Organize by priority
            priorities = {}
            for uid, task_info in self.cleanup_registry.items():
                prio = task_info['priority']
                if prio not in priorities:
                    priorities[prio] = []
                priorities[prio].append(task_info)
            
            # Sort and flatten
            sorted_tasks = []
            for prio in sorted(priorities.keys()):
                sorted_tasks.extend(priorities[prio])
            
            cleanup_stats = {
                'total': len(sorted_tasks),
                'completed': 0,
                'succeeded': 0,
                'failed': 0
            }
            
            # Process tasks in priority order
            for task in sorted_tasks:
                success = self._execute_task(task, max_attempts)
                cleanup_stats['completed'] += 1
                if success:
                    cleanup_stats['succeeded'] += 1
                else:
                    cleanup_stats['failed'] += 1
                    logger.warning("Failed to clean resource: %s", task['name'])
            
            # Log overall status
            logger.log(
                self.log_level,
                "Cleanup completed: %d/%d succeeded. Final exit code: %d",
                cleanup_stats['succeeded'], cleanup_stats['total'], self.exit_code
            )
    
    def _execute_task(self, task: dict, max_attempts: int) -> bool:
        """Execute a single cleanup task with timeout handling"""
        attempts = 0
        task_name = task['name']
        
        logger.debug("Cleaning resource: %s", task_name)
        
        # Set up timeout mechanism
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Resource cleanup timed out: {task_name}")
        
        old_handler = None
        
        # Setup signal handler if timeout is specified
        if task['timeout']:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(task['timeout'])
        
        try:
            while attempts < max_attempts:
                attempts += 1
                try:
                    task['func'](*task['args'], **task['kwargs'])
                    logger.debug("Successfully cleaned %s", task_name)
                    return True
                except Exception as e:
                    logger.error(
                        "Attempt %d/%d failed for %s: %s\n%s",
                        attempts, max_attempts, task_name, str(e), traceback.format_exc()
                    )
        except TimeoutError as te:
            logger.error("Cleanup timed out for %s: %s", task_name, str(te))
            if task['critical']:
                self.exit_code = self.ERROR_IN_CLEANUP
        finally:
            # Restore original signal handler
            if old_handler is not None:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        # Task failed
        if task['critical']:
            self.exit_code = self.ERROR_IN_CLEANUP
            logger.critical("Critical resource cleanup failed: %s", task_name)
        return False
    
    def exit(self, code: int = CLEAN_EXIT):
        """Execute cleanup and terminate the process"""
        self.set_exit_code(code)
        self.execute_cleanup()
        logger.info("Process exiting with code %d", self.exit_code)
        os._exit(self.exit_code)
    
    def __del__(self):
        """Ensure cleanup if destructor is called"""
        if not self.cleaning_started:
            logger.warning("Resource manager deallocated before cleanup")
            self.execute_cleanup()

# Create singleton instance
GlobalExitManager = ExitManager()

# Usage example
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Create some dummy resources
    class DBConnection:
        def __init__(self, name):
            self.name = name
            GlobalExitManager.monitor_resource(self, f"DBConnection_{name}")
        
        def close(self):
            logger.debug(f"Closing DB connection {self.name}")
    
    class FileHandle:
        def __init__(self, filename):
            self.filename = filename
            self.name = f"File:{filename}"
            self.fh = open(filename, 'w')  # In real code, handle open properly
            GlobalExitManager.register(self.close, name=self.name)
        
        def close(self):
            logger.debug(f"Closing file {self.filename}")
            self.fh.close()
    
    # Register resources
    db1 = DBConnection("primary")
    db2 = DBConnection("replica")
    file1 = FileHandle("log.txt")
    
    GlobalExitManager.register(
        lambda: print("Resource cleanup complete"),
        priority=ExitManager.PRIORITY_LOW,
        name="final_callback"
    )
    
    # Forced exit handler
    def admin_shutdown():
        GlobalExitManager.monitor_resource("AdminShutdownHook")
        logger.info("Admin shutdown requested")
        GlobalExitManager.exit(128 + signal.SIGTERM)
    
    GlobalExitManager.register(
        admin_shutdown,
        priority=ExitManager.PRIORITY_CRITICAL,
        name="admin_shutdown",
        critical=True
    )
    
    # Simulate critical application failure
    try:
        raise RuntimeError("Simulated critical error")
    except Exception as e:
        logger.error("Application fault: %s", str(e))
        GlobalExitManager.exit(1)
