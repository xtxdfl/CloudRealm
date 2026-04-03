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
import atexit
from typing import Optional

logger = logging.getLogger(__name__)

# Reporting status constants
REPORTING_ACTIVE = 1
REPORTING_PAUSED = 2
REPORTING_SHUTDOWN = 3


class CommandStatusReporter(threading.Thread):
    """
    High-performance command status reporting service providing:
        - Adaptive scheduling mechanisms
        - Failure resilience and recovery
        - Telemetry monitoring
        - Graceful shutdown
    
    Key capabilities:
        - Automatic status propagation
        - Connection-aware reporting
        - Performance optimization
        - System diagnostics
    """
    
    def __init__(self, initializer_module):
        """
        Initialize the reporting service
        :param initializer_module: Main application initializer with configurations
        """
        super().__init__(name="CommandStatusReporter")
        self.initializer = initializer_module
        self.status_manager = initializer_module.commandStatuses
        self.stop_event = threading.Event()
        self.status = REPORTING_PAUSED  # Start in paused state until configuration loaded
        
        # Configuration parameters with fallback defaults
        self.reporting_interval = getattr(
            initializer_module.config, "command_reports_interval", 30
        )
        self.min_interval = 5  # Minimum reporting interval in seconds
        self.max_interval = 300  # Maximum reporting interval in seconds
        
        # Telemetry tracking
        self.start_time = time.monotonic()
        self.reports_sent = 0
        self.last_report_time = 0
        self.consecutive_failures = 0
        self.active_cycle = False
        
        # Thread management
        self.daemon = True  # Allow main process to exit if thread stuck
        atexit.register(self.shutdown)  # Register cleanup
        
        logger.info("Command reporting service initialized with interval %ss", 
                   self.reporting_interval)
    
    def run(self):
        """
        Command reporting lifecycle manager
        - Continuously send reports until shutdown
        - Dynamically adjust timing based on network conditions
        - Provide detailed operational telemetry
        """
        logger.info("Command reporting service started")
        self.status = REPORTING_ACTIVE
        
        while not self.stop_event.is_set():
            try:
                self._reporting_cycle()
            except Exception as err:
                self._handle_run_exception(err)
            
            # Calculate next wakeup using adaptive timing
            sleep_duration = self._calculate_next_cycle_delay()
            self.stop_event.wait(sleep_duration)
        
        logger.info("Command reporting service completed")
    
    def _reporting_cycle(self):
        """Execute a complete reporting cycle with performance tracking"""
        self.active_cycle = True
        cycle_start = time.monotonic()
        
        try:
            # Check if reporting should occur
            if not self._should_report():
                return
            
            # Execute the core report generation
            self.status_manager.report()
            self.reports_sent += 1
            self._track_success()
        except Exception as cycle_error:
            self._handle_cycle_exception(cycle_error)
        finally:
            # Record cycle performance metrics
            self.active_cycle = False
            self.last_report_time = time.monotonic()
            cycle_duration = self.last_report_time - cycle_start
            logger.debug("Reporting cycle completed in %.3fs", cycle_duration)
    
    def _should_report(self) -> bool:
        """Determine if reporting should occur in this cycle"""
        # Critical: Ensure agent is registered with server
        if not self.initializer.is_registered:
            logger.debug("Skipping report - not registered to cluster")
            return False
        
        # Report not needed if reporting is explicitly disabled
        if self.reporting_interval <= 0:
            return False
        
        # Skip report if pending commands count is low (performance optimization)
        if self.status_manager.get_pending_commands_count() < 1:
            logger.debug("No pending commands - skipping reporting cycle")
            return False
            
        return True
    
    def _calculate_next_cycle_delay(self) -> float:
        """Dynamically calculate delay until next reporting cycle"""
        base_interval = self.reporting_interval
        
        # Apply exponential backoff for network issues
        if self.consecutive_failures > 0:
            backoff_factor = 2 ** min(self.consecutive_failures, 5)  # Max 32x backoff
            adjusted_interval = min(base_interval * backoff_factor, self.max_interval)
            logger.warning("Applying reporting backoff: %.1fs (failures=%d)",
                          adjusted_interval, self.consecutive_failures)
            return adjusted_interval
        
        # Return base interval under normal conditions
        return max(base_interval, self.min_interval)
    
    def _track_success(self):
        """Reset failure tracking on successful report cycle"""
        if self.consecutive_failures > 0:
            logger.info("Reporting recovered after %d failures", 
                       self.consecutive_failures)
        self.consecutive_failures = 0
    
    def _handle_cycle_exception(self, error):
        """Handle errors encountered during a reporting cycle"""
        logger.error("Reporting cycle failure: %s", error)
        self.consecutive_failures += 1
        
        # Handle critical errors that require shutdown
        if isinstance(error, MemoryError):
            logger.critical("Memory exhaustion - halting reporting service")
            self.shutdown()
    
    def _handle_run_exception(self, error):
        """Handle unexpected errors in the main run loop"""
        logger.exception("Critical error in reporting service: %s", error)
        
        # Attempt service restart
        self.consecutive_failures += 5  # Aggressively backoff
        logger.warning("Restart attempt in next cycle")
    
    def reconfigure(self, new_interval: int):
        """Dynamically change reporting frequency"""
        # Apply boundaries to new interval
        self.reporting_interval = max(
            self.min_interval, min(new_interval, self.max_interval)
        )
        logger.info("Reporting interval reconfigured: %d seconds", 
                   self.reporting_interval)
        
        # Interrupt current sleep if interval changed
        self.stop_event.set()
        self.stop_event.clear()
    
    def get_telemetry(self) -> dict:
        """Retrieve performance and operational data"""
        return {
            "status": self._status_description(self.status),
            "uptime": time.monotonic() - self.start_time,
            "reports_sent": self.reports_sent,
            "current_failures": self.consecutive_failures,
            "last_report": self.last_report_time,
            "active_cycle": self.active_cycle,
            "pending_report_count": self.status_manager.get_pending_commands_count(),
            "reporting_interval": self.reporting_interval
        }
    
    def shutdown(self):
        """Gracefully terminate the reporting service"""
        if self.status == REPORTING_SHUTDOWN:
            return  # Already shutting down
            
        logger.info("Initiating reporting service shutdown")
        self.status = REPORTING_SHUTDOWN
        self.stop_event.set()
        
        # Attempt final report before exit
        if self.initializer.is_registered:
            logger.info("Sending final report before shutdown")
            try:
                self.status_manager.report(force_full=True)
            except Exception as final_err:
                logger.error("Final report failed: %s", final_err)
        
        # Join the thread with timeout to prevent deadlocks
        if self.is_alive():
            self.join(timeout=15)  # Maximum 15s for graceful shutdown
            if self.is_alive():
                logger.warning("Reporting service failed to terminate cleanly")
    
    def pause(self):
        """Temporarily suspend reporting"""
        if self.status == REPORTING_ACTIVE:
            logger.info("Pausing command reporting service")
            self.status = REPORTING_PAUSED
        self.stop_event.set()
    
    def resume(self):
        """Resume reporting after pause"""
        if self.status == REPORTING_PAUSED:
            logger.info("Resuming command reporting service")
            self.status = REPORTING_ACTIVE
            self.stop_event.clear()
    
    def _status_description(self, status_code) -> str:
        """Convert status code to human-readable description"""
        status_map = {
            REPORTING_ACTIVE: "Active",
            REPORTING_PAUSED: "Paused",
            REPORTING_SHUTDOWN: "Shutting down"
        }
        return status_map.get(status_code, f"Unknown ({status_code})")


# Example usage
if __name__ == "__main__":
    # Setup basic configuration for demonstration
    class MockInitializer:
        def __init__(self):
            self.is_registered = True
            self.config = type('Config', (), {'command_reports_interval': 10})()
            self.commandStatuses = type('StatusManager', (), {
                'report': lambda: logger.info("Mock report generated"),
                'get_pending_commands_count': lambda: 5
            })()
            self.stop_event = threading.Event()
    
    logging.basicConfig(level=logging.DEBUG)
    reporter = CommandStatusReporter(MockInitializer())
    reporter.start()
    
    try:
        logger.info("Running reporter for 30 seconds")
        time.sleep(30)
    finally:
        reporter.shutdown()
        reporter.join()
