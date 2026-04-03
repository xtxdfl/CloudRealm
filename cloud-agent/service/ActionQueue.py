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

import queue
import os
import time
import signal
import re
import logging
import threading
import pprint
import cloud_simplejson as json
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

from .AgentException import AgentException
from BackgroundCommandExecutionHandle import (
    BackgroundCommandExecutionHandle,
)
from models.commands import AgentCommand, CommandStatus
from cloud_commons.str_utils import split_on_chunks


logger = logging.getLogger()
installScriptHash = -1

MAX_SYMBOLS_PER_LOG_MESSAGE = 7900
MAX_CONCURRENT_ACTIONS = 5  # 最大并行执行任务数
TEMP_FILE_CLEANUP_AGE = 86400  # 24小时(?

PASSWORD_REPLACEMENT = "[PROTECTED]"
PASSWORD_PATTERN = re.compile(r"('\S*password':\s*u?')(\S+)(')")


def hide_passwords(text):
    """Replaces the matching passwords with **** in the given text"""
    if text is None:
        return None
    return PASSWORD_PATTERN.sub(r"\1{}\3".format(PASSWORD_REPLACEMENT), text)


class ActionQueue(threading.Thread):
    """Action Queue for the agent. We pick one command at a time from the queue
    and execute it.
    
    Note: Action and command terms are used interchangeably in this context.
    """

    EXECUTION_COMMAND_WAIT_TIME = 2

    class CommandCancelled(Exception):
        """Exception raised when a command is cancelled during execution."""

    def __init__(self, initializer_module):
        super().__init__()
        self.commandQueue = queue.PriorityQueue()
        self.backgroundCommandQueue = queue.Queue()
        self.commandStatuses = initializer_module.commandStatuses
        self.config = initializer_module.config
        self.recovery_manager = initializer_module.recovery_manager
        self.configTags = {}
        self.stop_event = initializer_module.stop_event
        self.tmpdir = self.config.get("agent", "prefix")
        self.customServiceOrchestrator = initializer_module.customServiceOrchestrator
        self.parallel_execution = self.config.get_parallel_exec_option()
        self.taskIdsToCancel = set()
        self.cancelEvent = threading.Event()
        self.component_status_executor = initializer_module.component_status_executor
        self.lock = threading.Lock()
        self.thread_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ACTIONS)
        self.active_futures = set()
        self.command_file_times = {}

        if self.parallel_execution == 1:
            logger.info(
                "Parallel execution is enabled, will execute agent commands using thread pool"
            )

    def put(self, commands):
        """Add commands to the appropriate queue based on their type."""
        for command in commands:
            command.setdefault("serviceName", "null")
            command.setdefault("clusterId", "null")

            priority = self._get_command_priority(command)
            logger.info(
                f"Adding {command['commandType']} for role {command['role']} "
                f"for service {command['serviceName']} of cluster_id {command['clusterId']} "
                f"with priority {priority} to the queue"
            )

            if command["commandType"] == AgentCommand.background_execution:
                self.backgroundCommandQueue.put(self.create_command_handle(command))
            else:
                self.commandQueue.put((priority, command))

    def _get_command_priority(self, command):
        """Determine command priority based on type and parameters."""
        priority = 10  # Default priority
        command_type = command.get("commandType", "")
        params = command.get("commandParams", {})
        
        if command_type in (AgentCommand.auto_execution, AgentCommand.status_command):
            priority = 1  # High priority for auto-execution and status commands
        elif params.get("priority"):
            try:
                priority = int(params["priority"])
            except ValueError:
                pass
        
        return priority

    def interrupt(self):
        """Interrupt the queue processing by adding a None sentinel."""
        self.commandQueue.put((0, None))

    def cancel(self, commands):
        """Cancel commands in progress or in the queue."""
        for command in commands:
            task_id = command["target_task_id"]
            reason = command["reason"]
            logger.info(f"Canceling command with taskId = {task_id}")
            
            # Add to cancellation set
            self.taskIdsToCancel.add(task_id)
            
            # Cancel if in progress
            self.customServiceOrchestrator.cancel_command(task_id, reason)
            
            # Signal any waiting threads
            self.cancelEvent.set()

    def run(self):
        """Main processing loop for the action queue."""
        while not self.stop_event.is_set():
            try:
                self._process_background_queue()
                self.fill_recovery_commands()
                self._process_command_queue()
                self._clean_old_temp_files()
            except Exception:
                logger.exception("ActionQueue thread failed with exception. Re-running it")
        
        # Wait for active futures to complete before shutting down
        wait(self.active_futures, return_when=ALL_COMPLETED, timeout=30)
        self.thread_pool.shutdown(wait=False)
        logger.info("ActionQueue thread has successfully finished")

    def _process_background_queue(self):
        """Process background commands in the queue."""
        while not self.backgroundCommandQueue.empty():
            try:
                command = self.backgroundCommandQueue.get(False)
                if "__handle" in command and command["__handle"].status is None:
                    self.process_command(command)
            except queue.Empty:
                break

    def _process_command_queue(self):
        """Process commands in the main queue based on execution mode."""
        try:
            if self.parallel_execution == 0:  # Serial execution
                priority, command = self.commandQueue.get(
                    True, self.EXECUTION_COMMAND_WAIT_TIME
                )
                if command is None:
                    return
                self.process_command(command)
            else:  # Parallel execution
                while not self.stop_event.is_set() and not self.commandQueue.empty():
                    priority, command = self.commandQueue.get_nowait()
                    if command is None:
                        continue
                    
                    retry_able = self._is_retryable_command(command)
                    
                    if retry_able and len(self.active_futures) < MAX_CONCURRENT_ACTIONS:
                        future = self.thread_pool.submit(self.process_command, command)
                        self.active_futures.add(future)
                        future.add_done_callback(lambda f: self.active_futures.remove(f))
                        logger.debug(
                            f"Submitted command {command['commandId']} to thread pool"
                        )
                    else:
                        self.process_command(command)
                        break
        except queue.Empty:
            pass
        except TypeError:
            # Handle case where queue returns None
            pass

    def _is_retryable_command(self, command):
        """Determine if a command is retryable based on its parameters."""
        command_type = command.get("commandType")
        params = command.get("commandParams", {})
        
        if command_type == AgentCommand.auto_execution:
            return False
        
        return params.get("command_retry_enabled", "false") == "true"

    def create_command_handle(self, command):
        """Create a handle for background command execution."""
        if "__handle" in command:
            raise AgentException("Command already has __handle")
        
        command["__handle"] = BackgroundCommandExecutionHandle(
            command, command["commandId"], None, self.on_background_command_complete_callback
        )
        return command

    def process_command(self, command):
        """Process a single command based on its type."""
        command_type = command["commandType"]
        try:
            if command_type in AgentCommand.AUTO_EXECUTION_COMMAND_GROUP:
                try:
                    if self.recovery_manager.enabled():
                        self.recovery_manager.on_execution_command_start()
                        self.recovery_manager.process_execution_command(command)
                    
                    self.execute_command(command)
                finally:
                    if self.recovery_manager.enabled():
                        self.recovery_manager.on_execution_command_finish()
            else:
                logger.error("Unrecognized command %s", pprint.pformat(command))
        except self.CommandCancelled:
            logger.info(f"Command {command['taskId']} was cancelled during execution")
        except Exception:
            logger.exception(f"Exception while processing {command_type} command")

    def execute_command(self, command):
        """
        Executes commands from the EXECUTION_COMMAND_GROUP.
        Implements retry logic with exponential backoff and cancellation checks.
        """
        taskId = command["taskId"]
        command_type = command["commandType"]
        
        logger.info(
            f"Executing command with id={command['commandId']}, taskId={taskId} "
            f"for role={command['role']} of cluster_id={command['clusterId']}"
        )
        
        # Prepare in-progress status report
        in_progress_status = self._prepare_in_progress_status(command, taskId)
        self.commandStatuses.put_command_status(command, in_progress_status)
        
        # Extract command parameters
        cmd_params = command.get("commandParams", {})
        retry_duration = int(cmd_params.get("max_duration_for_retries", 0))
        retry_able = (
            cmd_params.get("command_retry_enabled", "false") == "true"
            and command_type != AgentCommand.auto_execution
        )
        log_command_output = cmd_params.get("log_output", "true") != "false"
        
        logger.debug(
            f"Command execution metadata - taskId={taskId}, retry_enabled={retry_able}, "
            f"max_retry_duration={retry_duration}, log_output={log_command_output}"
        )
        
        # Execute with retry logic
        self.cancelEvent.clear()
        self.taskIdsToCancel.discard(taskId)
        
        try:
            command_result, num_attempts = self._execute_with_retry(
                command, in_progress_status, retry_able, retry_duration
            )
        except self.CommandCancelled:
            logger.info(f"Command {taskId} was cancelled")
            return
        except Exception as e:
            logger.error(f"Unexpected error executing command {taskId}: {str(e)}")
            command_result = {
                "exitcode": 1,
                "stdout": "",
                "stderr": f"Unexpected error: {str(e)}",
                "structuredOut": {}
            }
            num_attempts = 1
        
        # Process command result
        status = self._determine_command_status(command_result, command_type)
        role_result = self._prepare_final_report(command, command_result, status, num_attempts)
        
        # Handle logs
        if self._should_log_command(log_command_output):
            self._log_command_output(role_result, command)
            
        # Report final status
        self._report_final_status(command, role_result, status, in_progress_status)

    def _prepare_in_progress_status(self, command, taskId):
        """Prepare the in-progress status report for a command."""
        status_template = self.commandStatuses.generate_report_template(command)
        prefix = "auto_" if command["commandType"] == AgentCommand.auto_execution else ""
        
        status_template.update({
            "tmpout": os.path.join(self.tmpdir, f"{prefix}output-{taskId}.txt"),
            "tmperr": os.path.join(self.tmpdir, f"{prefix}errors-{taskId}.txt"),
            "structuredOut": os.path.join(self.tmpdir, f"{prefix}structured-out-{taskId}.json"),
            "status": CommandStatus.in_progress,
        })
        
        # Record temp file creation time
        self.command_file_times[taskId] = time.time()
        return status_template

    def _execute_with_retry(self, command, in_progress_status, retry_able, max_retry_duration):
        """Executes a command with retry logic."""
        taskId = command["taskId"]
        num_attempts = 0
        delay = 1
        command_result = {}
        
        # Track if we need to clear files after first attempt
        clear_files = True
        
        # We'll allow up to 10 retries even if duration allows for more
        max_attempts = 10
        start_time = time.monotonic()
        
        for attempt in range(1, max_attempts + 1):
            if self.stop_event.is_set() or taskId in self.taskIdsToCancel:
                self.taskIdsToCancel.discard(taskId)
                raise self.CommandCancelled()
            
            num_attempts += 1
            retry = num_attempts > 1
            
            # Exit if we've used up our retry time
            elapsed = time.monotonic() - start_time
            if retry and elapsed > max_retry_duration:
                logger.debug(f"Retry duration exceeded for {taskId}")
                break
            
            try:
                # Execute command
                command_result = self.customServiceOrchestrator.runCommand(
                    command,
                    in_progress_status["tmpout"],
                    in_progress_status["tmperr"],
                    override_output_files=clear_files,
                    retry=retry,
                )
                
                # Clear files only once if we're going to retry
                clear_files = False
                
                # Check if we have a result
                if not command_result:
                    logger.error(f"Empty result for command {taskId}")
                    if not retry_able or attempt >= max_attempts:
                        break
                    continue
                
                # Handle background commands (no retry)
                if command["commandType"] == AgentCommand.background_execution:
                    logger.info(
                        f"Background command {taskId} started with exit code {command_result.get('exitcode', -1)}"
                    )
                    return command_result, num_attempts
                
                # Check exit code
                if command_result.get("exitcode") == 0:
                    logger.debug(f"Command {taskId} succeeded on attempt {attempt}")
                    return command_result, num_attempts
                
                # Check for cancellation signals
                exitcode = command_result.get("exitcode", -1)
                if exitcode in (-signal.SIGTERM, -signal.SIGKILL):
                    logger.info(f"Command {taskId} was cancelled during execution")
                    self.taskIdsToCancel.discard(taskId)
                    raise self.CommandCancelled()
                
                # If not retryable or last attempt, break
                if not retry_able or attempt == max_attempts:
                    break
                
            except Exception as e:
                logger.exception(f"Unexpected error during command execution {taskId}")
                if not retry_able or attempt == max_attempts:
                    command_result = {
                        "exitcode": 1,
                        "stdout": "",
                        "stderr": f"Execution error: {str(e)}",
                        "structuredOut": {}
                    }
                    break
            
            # Prepare for next retry
            logger.info(f"Retrying command {taskId} after delay {delay}")
            command_result["stderr"] += "\n\nCommand failed. Retrying command execution ...\n\n"
            
            if "agentLevelParams" not in command:
                command["agentLevelParams"] = {}
            command["agentLevelParams"]["commandBeingRetried"] = "true"
            
            # Wait with cancellation check
            end_time = time.monotonic() + delay
            while time.monotonic() < end_time:
                if self.stop_event.is_set() or taskId in self.taskIdsToCancel:
                    self.taskIdsToCancel.discard(taskId)
                    raise self.CommandCancelled()
                time.sleep(0.5)  # Smaller intervals for more responsive cancellation
            
            # Exponential backoff
            delay = min(delay * 2, 1800)  # Cap at 30 minutes
        
        return command_result, num_attempts

    def _determine_command_status(self, command_result, command_type):
        """Determine the final status of a command."""
        if command_type == AgentCommand.background_execution:
            return CommandStatus.in_progress
        
        if command_result.get("exitcode") == 0:
            return CommandStatus.completed
        
        # Check for cancellation signals
        exitcode = command_result.get("exitcode", -1)
        if exitcode in (-signal.SIGTERM, -signal.SIGKILL):
            return CommandStatus.cancelled
        
        return CommandStatus.failed

    def _prepare_final_report(self, command, command_result, status, num_attempts):
        """Prepare the final status report for a command."""
        role_result = self.commandStatuses.generate_report_template(command)
        taskId = command["taskId"]
        
        # Prepare result messages
        if status == CommandStatus.completed:
            success_msg = f"\n\nCommand ({taskId}) completed successfully!\n"
            command_result["stdout"] += success_msg
            result_message = f"Command {taskId} completed successfully"
        else:
            error_msg = f"\n\nCommand ({taskId}) failed after {num_attempts} attempts ({status})\n"
            command_result["stdout"] += error_msg
            result_message = f"Command {taskId} failed after {num_attempts} attempts"
        
        logger.info(result_message)
        
        # Populate base result
        role_result.update({
            "stdout": command_result.get("stdout", ""),
            "stderr": command_result.get("stderr", ""),
            "exitCode": command_result.get("exitcode", -1),
            "status": status,
        })
        
        # Add structured output if available
        if "structuredOut" in command_result:
            role_result["structuredOut"] = json.dumps(command_result["structuredOut"])
        else:
            role_result["structuredOut"] = ""
        
        # Handle custom command metadata
        params = command.get("commandParams", {})
        if "custom_command" in params:
            role_result["customCommand"] = params["custom_command"]
        
        # Ensure non-empty strings
        role_result["stdout"] = role_result["stdout"] or "None"
        role_result["stderr"] = role_result["stderr"] or "None"
        
        return role_result

    def _should_log_command(self, log_command_output):
        """Determine if command output should be logged."""
        config_logging_flag = self.config.has_option("logging", "log_command_executes")
        config_logging_value = self.config.get("logging", "log_command_executes") if config_logging_flag else "0"
        return int(config_logging_value) == 1 and log_command_output

    def _log_command_output(self, role_result, command):
        """Log command output, splitting into chunks if necessary."""
        taskId = command["taskId"]
        command_type = command["commandType"]
        role_command = command.get("roleCommand", "unknown")
        
        logger.info(
            f"Begin {command_type} output log for command={taskId}, "
            f"role={command['role']}, command={role_command}"
        )
        self._log_output_chunks(hide_passwords(role_result["stdout"]), taskId, "stdout")
        logger.info(f"End output log for command={taskId}")
        
        if role_result["stderr"] and role_result["stderr"] != "None":
            logger.info(
                f"Begin {command_type} stderr log for command={taskId}, "
                f"role={command['role']}, command={role_command}"
            )
            self._log_output_chunks(hide_passwords(role_result["stderr"]), taskId, "stderr")
            logger.info(f"End stderr log for command={taskId}")

    def _log_output_chunks(self, text, taskId, log_type):
        """Log output in chunks with a correlation ID."""
        if not text:
            return
            
        log_id = f"{taskId}-{time.strftime('%Y%m%d%H%M%S')}"
        chunks = split_on_chunks(text, MAX_SYMBOLS_PER_LOG_MESSAGE)
        total = len(chunks)
        
        logger.info(f"Log {log_type} ID={log_id} | {total} chunks | Start")
        
        for i, chunk in enumerate(chunks, 1):
            log = f"Log {log_type} ID={log_id} | Chunk {i}/{total}\n{chunk}"
            logger.info(log)
        
        logger.info(f"Log {log_type} ID={log_id} | Completed")

    def _report_final_status(self, command, role_result, status, in_progress_status):
        """Report the final command status and perform cleanup."""
        self.recovery_manager.process_execution_command_result(command, status)
        self.commandStatuses.put_command_status(command, role_result)
        
        # Update component status
        self._update_component_status(command)
        
        # Clean up temporary files
        self._clean_temp_files(in_progress_status)
        
        # Remove file time tracking
        taskId = command.get("taskId")
        if taskId in self.command_file_times:
            del self.command_file_times[taskId]

    def _clean_temp_files(self, in_progress_status):
        """Clean up temporary files created during command execution."""
        file_keys = ["tmpout", "tmperr", "structuredOut"]
        for key in file_keys:
            file_path = in_progress_status.get(key)
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temp file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {file_path}: {str(e)}")

    def _clean_old_temp_files(self):
        """Clean up temporary files that are older than the specified age."""
        if not hasattr(self, "command_file_times") or not self.command_file_times:
            return
            
        now = time.time()
        threshold = now - TEMP_FILE_CLEANUP_AGE
        keys_to_remove = []
        
        for taskId, file_time in self.command_file_times.items():
            if file_time < threshold:
                keys_to_remove.append(taskId)
                
                # Build file paths using naming convention
                base_path = os.path.join(self.tmpdir, f"output-{taskId}.txt")
                try:
                    os.remove(base_path)
                    os.remove(base_path.replace("output", "errors"))
                    os.remove(base_path.replace("output", "structured-out"))
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logger.warning(f"Error cleaning temp files for {taskId}: {str(e)}")
        
        # Remove tracked entries
        for key in keys_to_remove:
            if key in self.command_file_times:
                del self.command_file_times[key]

    def _update_component_status(self, command):
        """Update component status after command execution."""
        cluster_id = command["clusterId"]
        if cluster_id in ("-1", "null"):
            return
            
        service_name = command["serviceName"]
        if service_name == "null":
            return
            
        component_name = command["role"]
        self.component_status_executor.check_component_status(
            cluster_id, service_name, component_name, "STATUS", report=True
        )

    def tasks_in_progress_or_pending(self):
        """Check if there are tasks in progress or pending."""
        has_queue_tasks = not self.commandQueue.empty() or not self.backgroundCommandQueue.empty()
        has_active_futures = len(self.active_futures) > 0
        has_recovery_tasks = self.recovery_manager.has_active_command()
        
        return has_queue_tasks or has_active_futures or has_recovery_tasks

    def fill_recovery_commands(self):
        """Add recovery commands to the queue if conditions are met."""
        if self.recovery_manager.enabled() and not self.tasks_in_progress_or_pending():
            recovery_commands = self.recovery_manager.get_recovery_commands()
            if recovery_commands:
                logger.debug(f"Adding {len(recovery_commands)} recovery commands to queue")
                self.put(recovery_commands)

    def on_background_command_complete_callback(self, process_condensed_result, handle):
        """Callback for when a background command completes execution."""
        logger.debug("Processing background command completion: %s", handle.command["taskId"])
        
        status = CommandStatus.completed if handle.exitCode == 0 else CommandStatus.failed
        aborted_postfix = ""
        
        if self.customServiceOrchestrator.command_canceled_reason(handle.command["taskId"]):
            status = CommandStatus.failed
            aborted_postfix = self.customServiceOrchestrator.command_canceled_reason(handle.command["taskId"])
            logger.debug("Background command was aborted: %s", aborted_postfix)
        
        role_result = self.commandStatuses.generate_report_template(handle.command)
        structured_out = process_condensed_result.get("structuredOut", {})
        
        role_result.update({
            "stdout": (process_condensed_result.get("stdout", "") or "") + aborted_postfix,
            "stderr": (process_condensed_result.get("stderr", "") or "") + aborted_postfix,
            "exitCode": process_condensed_result.get("exitcode", -1),
            "structuredOut": json.dumps(structured_out) if structured_out else "",
            "status": status,
        })
        
        self.commandStatuses.put_command_status(handle.command, role_result)
        
        # For background commands, update component status
        self._update_component_status(handle.command)

    def reset(self):
        """Resets command queue."""
        with self.commandQueue.mutex:
            self.commandQueue.queue.clear()
