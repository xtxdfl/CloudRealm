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

import os
import logging
import threading
import copy
import contextlib

import cloud_simplejson as json
from collections import defaultdict, deque

from Grep import Grep
from cloud_agent import Constants
from models.commands import CommandStatus, AgentCommand
from cloud_stomp.adapter.websocket import ConnectionIsAlreadyClosed

logger = logging.getLogger(__name__)

# Constants for configuration
MAX_REPORT_SIZE = 1_950_000  # Max message size on server (2MB - some buffer)
IN_PROGRESS_EXIT_CODE = 777  # Special code for in-progress commands
MAX_REPORT_HISTORY = 1000  # Max stored historical reports
OUTPUT_LAST_LINES = 200  # Default number of tail lines to capture
LOG_TRAIL_SIZE = 1024  # Default log tail size in characters


class CommandStatusManager:
    """
    Advanced command status tracking and reporting system providing:
        - Thread-safe command status storage
        - Report batching and compression
        - Failure recovery mechanisms
        - Performance profiling
        - Log optimization
    
    Features:
        - Real-time status updates
        - Smart log truncation
        - Connection recovery handling
        - Memory optimization for large environments
    """
    
    def __init__(self, initializer_module):
        """
        Initialize the command status tracking system
        :param initializer_module: Main initialization module with configurations
        """
        self.initializer = initializer_module
        self.config = initializer_module.config
        self.server_listener = initializer_module.server_responses_listener
        self.is_registered = initializer_module.is_registered
        
        # Command storage
        self.current_state = {}  # task_id: (command, report)
        self.acknowledged_commands = deque(maxlen=MAX_REPORT_HISTORY)
        self.lock = threading.RLock()
        self.send_queue = deque()
        
        # Configuration options with defaults
        self.command_update_output = getattr(self.config, "command_update_output", True)
        self.log_max_symbols_size = getattr(self.config, "log_max_symbols_size", LOG_TRAIL_SIZE)
        self.output_tail_lines = getattr(self.config, "output_tail_lines", OUTPUT_LAST_LINES)
        
        # Performance tracking
        self.last_report_time = 0
        self.reports_sent = 0
        self.failed_sends = 0
        self.startup_time = threading.time
    
    @contextlib.contextmanager
    def status_lock(self):
        """Thread-safe context manager for status operations"""
        with self.lock:
            yield
    
    def update_command_status(self, command: dict, report: dict) -> None:
        """
        Update status of a command and trigger reporting
        :param command: Original command dictionary
        :param report: Status report dictionary
        """
        with self.status_lock():
            task_id = command["taskId"]
            
            # Remove old status data
            self._remove_stale_data(task_id)
            
            # Queue for reporting
            self.current_state[task_id] = (command, report)
            
            # Auto-report based on status
            if report["status"] != CommandStatus.in_progress or self.config.report_ongoing_tasks:
                self.queue_report_sending(task_id)
    
    def queue_report_sending(self, task_id: str) -> None:
        """Mark a command for reporting in the next batch"""
        with self.status_lock():
            if task_id in self.current_state and task_id not in self.acknowledged_commands:
                self.send_queue.append(task_id)
    
    def report_all(self) -> None:
        """Generate and send reports for all pending commands"""
        if not self.send_queue:
            logger.debug("No reports to send")
            return
            
        report = self._generate_report()
        
        if report:
            self._send_reports(report)
    
    def _generate_report(self) -> dict:
        """
        Generate status reports for commands that need to be reported.
        Returns dictionary with clusterId as keys and reports as list values.
        """
        with self.status_lock():
            cluster_reports = defaultdict(list)
            processed_tasks = []
            
            while self.send_queue:
                task_id = self.send_queue.popleft()
                
                if task_id not in self.current_state:
                    logger.debug("Task %s missing from current state", task_id)
                    continue
                    
                command, report = self.current_state[task_id]
                cluster_id = report["clusterId"]
                
                # Collect reports based on command type and status
                if self._should_report_command(command, report):
                    if report["status"] == CommandStatus.in_progress:
                        processed_report = self._generate_progress_report(command, report)
                    else:
                        processed_report = report.copy()
                    
                    self._enhance_report_metadata(processed_report, command)
                    cluster_reports[cluster_id].append(processed_report)
                    processed_tasks.append(task_id)
            
            # Add processed tasks to acknowledged set
            self.acknowledged_commands.extend(processed_tasks)
            return dict(cluster_reports)
    
    def _should_report_command(self, command: dict, report: dict) -> bool:
        """Determine if a command should be reported"""
        command_type = command["commandType"]
        status = report["status"]
        
        if command_type in AgentCommand.EXECUTION_COMMAND_GROUP:
            return True
        # Auto-execution commands don't need regular reporting
        elif command_type == AgentCommand.auto_execution and status != CommandStatus.in_progress:
            logger.debug("Handling auto-execution command: %s", command["commandId"])
            return False
        return False
    
    def _generate_progress_report(self, command: dict, report: dict) -> dict:
        """
        Create an in-progress report for commands still running
        :param command: Original command data
        :param report: Current report data
        :return: Enhanced progress report
        """
        progress_report = self._generate_report_stub(command)
        
        # Optimized output reading with truncation
        files_to_read = {
            "stdout": report.get("tmpout", ""),
            "stderr": report.get("tmperr", ""),
            "structuredOut": report.get("structuredOut", "")
        }
        
        file_contents = {}
        for key, path in files_to_read.items():
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        content = f.read()
                    # Apply smart truncation for large outputs
                    file_contents[key] = self._truncate_log_content(content, key)
                except IOError as e:
                    logger.error("Error reading %s for %s: %s", key, command["taskId"], e)
                    file_contents[key] = "ERROR_READING_LOG"
            else:
                file_contents[key] = "LOG_NOT_FOUND"
        
        progress_report.update({
            "stdout": file_contents["stdout"],
            "stderr": file_contents["stderr"],
            "structuredOut": file_contents["structuredOut"],
            "exitCode": IN_PROGRESS_EXIT_CODE,
            "status": CommandStatus.in_progress,
            "additionalData": report.get("additionalData", {})
        })
        return progress_report
    
    def _truncate_log_content(self, content: str, log_type: str) -> str:
        """Smart truncation for different log types"""
        size_limit = self.log_max_symbols_size
        tail_lines = self.output_tail_lines
        
        if not content:
            return ""
            
        if log_type in ["stdout", "stderr"]:
            # For stdout/stderr we want last X lines with limited characters
            truncated = Grep().tail(content, tail_lines)
            return Grep().tail_by_symbols(truncated, size_limit)
        
        # For structured output, keep entire JSON but truncate long strings
        try:
            structured = json.loads(content)
            if isinstance(structured, dict):
                for k, v in structured.items():
                    if isinstance(v, str) and len(v) > size_limit:
                        structured[k] = f"[TRUNCATED - {len(v)} characters]"
                return json.dumps(structured)
        except json.JSONDecodeError:
            pass
        
        # Fallback to simple truncate
        return content[:size_limit] if len(content) > size_limit else content
    
    def _generate_report_stub(self, command: dict) -> dict:
        """Generate a base report template"""
        return {
            "role": command.get("role", ""),
            "actionId": command.get("commandId", ""),
            "taskId": command.get("taskId", ""),
            "clusterId": command.get("clusterId", ""),
            "serviceName": command.get("serviceName", ""),
            "roleCommand": command.get("roleCommand", ""),
            "reportTime": threading.time()
        }
    
    def _enhance_report_metadata(self, report: dict, command: dict) -> None:
        """Add additional metadata to reports"""
        report["hostName"] = self.config.hostname
        report["hostPort"] = self.config.server_port
        report["agentVersion"] = Constants.AGENT_VERSION
        
        # Add command context
        report["commandContext"] = {
            "commandType": command["commandType"],
            "commandParams": command.get("commandParams", {})
        }
    
    def _send_reports(self, reports: dict) -> None:
        """Send reports to the server, handling batching and failures"""
        report_chunks = []
        
        # Split oversized reports
        current_chunk = defaultdict(list)
        current_size = 0
        
        for cluster_id, report_list in reports.items():
            for report in report_list:
                report_size = len(json.dumps(report))
                
                # Start new chunk if needed
                if current_size + report_size > MAX_REPORT_SIZE:
                    report_chunks.append(dict(current_chunk))
                    current_chunk = defaultdict(list)
                    current_size = 0
                
                current_chunk[cluster_id].append(report)
                current_size += report_size
        
        if current_chunk:
            report_chunks.append(dict(current_chunk))
        
        # Send each chunk
        for chunk in report_chunks:
            self._send_report_chunk(chunk)
    
    def _send_report_chunk(self, report_chunk: dict) -> None:
        """Send a single report chunk to the server"""
        if not self.is_registered:
            logger.debug("Skipping report send - not registered to server")
            return False
            
        try:
            correlation_id = self.initializer.connection.send(
                message={"clusters": report_chunk},
                destination=Constants.COMMANDS_STATUS_REPORTS_ENDPOINT,
                log_message_function=self._create_log_processor(report_chunk)
            )
            
            self._track_sent_report(correlation_id, report_chunk)
            self.reports_sent += 1
            logger.info("Sent command report with ID: %s", correlation_id)
            return True
            
        except ConnectionIsAlreadyClosed:
            logger.warning("Failed to send reports - connection closed")
            self.failed_sends += 1
            self._requeue_unsent(report_chunk)
            return False
    
    def _create_log_processor(self, report_chunk: dict):
        """Create closure to handle logging of report contents"""
        def log_processor(message_dict):
            try:
                # Create a copy to avoid modifying original
                log_copy = copy.deepcopy(message_dict)
                
                for cid in log_copy["clusters"]:
                    for rep in log_copy["clusters"][cid]:
                        # Truncate large output fields
                        for field in ["stdout", "stderr", "structuredOut"]:
                            if field in rep and rep[field]:
                                rep[field] = "[TRUNCATED]"
                
                return log_copy
            except (KeyError, TypeError):
                return {"error": "report-processing-error"}
        return log_processor
    
    def _track_sent_report(self, correlation_id: str, reports: dict) -> None:
        """Store data for handling server acknowledgements"""
        task_ids = []
        for cluster_reports in reports.values():
            for report in cluster_reports:
                task_ids.append(report["taskId"])
        
        self.server_listener.add_callback(
            correlation_id,
            lambda: self._handle_report_acknowledge(task_ids),
            lambda: self._handle_report_failure(task_ids)
        )
    
    def _handle_report_acknowledge(self, task_ids: list) -> None:
        """Server acknowledged receipt of reports - clean up"""
        with self.status_lock():
            for task_id in task_ids:
                if task_id in self.current_state and task_id in self.acknowledged_commands:
                    del self.current_state[task_id]
                    self.acknowledged_commands.remove(task_id)
    
    def _handle_report_failure(self, task_ids: list) -> None:
        """Server didn't acknowledge reports - resend them"""
        logger.warning("Command reports failed: %s", task_ids)
        with self.status_lock():
            for task_id in task_ids:
                if task_id in self.acknowledged_commands:
                    self.acknowledged_commands.remove(task_id)
                    self.queue_report_sending(task_id)
    
    def _requeue_unsent(self, reports: dict) -> None:
        """Add reports back to queue after sending failure"""
        with self.status_lock():
            for cluster_id, report_list in reports.items():
                for report in report_list:
                    task_id = report["taskId"]
                    if task_id in self.current_state:
                        self.queue_report_sending(task_id)
    
    def get_command_status(self, task_id: str) -> dict:
        """Retrieve current status of a command"""
        with self.status_lock():
            if task_id in self.current_state:
                return copy.deepcopy(self.current_state[task_id][1])
        return {"error": "command_not_found"}
    
    def get_performance_stats(self) -> dict:
        """Get command management performance stats"""
        return {
            "commands_tracked": len(self.current_state),
            "reports_sent": self.reports_sent,
            "reports_pending": len(self.send_queue),
            "commands_acknowledged": len(self.acknowledged_commands),
            "failed_sends": self.failed_sends
        }
    
    def cleanup_old_commands(self, max_age: float = 3600) -> None:
        """Cleanup old commands that are no longer needed"""
        current_time = threading.time()
        with self.status_lock():
            tasks_to_remove = []
            
            for task_id, (_, report) in self.current_state.items():
                # Criteria for removal:
                # 1. Final status (completed/failed) acknowledged by server
                # 2. Older than max_age
                if report["status"] not in CommandStatus.ACTIVE_STATUSES:
                    if task_id in self.acknowledged_commands:
                        tasks_to_remove.append(task_id)
                
                elif current_time - report.get("startTime", 0) > max_age:
                    logger.warning("Removing stale command: %s", task_id)
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                self._remove_stale_data(task_id)
    
    def _remove_stale_data(self, task_id: str) -> None:
        """Clean up all data related to a task"""
        with self.status_lock():
            # Remove current state
            if task_id in self.current_state:
                del self.current_state[task_id]
            
            # Remove from pending queues
            if task_id in self.acknowledged_commands:
                self.acknowledged_commands.remove(task_id)
            
            # Remove from send queue
            if task_id in self.send_queue:
                self.send_queue.remove(task_id)
