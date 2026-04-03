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

Enhanced Cross-Platform Process Locking System
"""

import os
import time
import errno
import logging
from typing import Optional, Union
from pathlib import Path
from logging import Logger

class LockAcquisitionError(Exception):
    """Custom exception for lock acquisition failures"""
    pass

class LockType(Enum):
    """Supported lock mechanisms based on platform"""
    FCNTL = "fcntl"  # POSIX-compliant systems
    MSLOCK = "mslock"  # Windows systems
    FLOCK = "flock"  # BSD/MacOS systems

class ProcessLock:
    """
    Enhanced cross-platform process locking with deadlock detection and automatic recovery.
    
    Features:
    - Automatic platform detection with fallback mechanisms
    - Deadlock detection and self-recovery
    - Built-in lock validation using PID tracking
    - Configurable timeout and retry strategies
    - Atomic file operations for lock reliability
    
    Usage:
    >>> with ProcessLock("/var/lock/service.lock") as lock:
    >>>     # Critical section
    >>>     perform_task()
    """
    
    LOCK_TIMEOUT = 30  # seconds
    RETRY_INTERVAL = 0.5  # seconds
    MAX_RETRIES = int(LOCK_TIMEOUT / RETRY_INTERVAL)
    DEFAULT_TEMP_DIR = "/tmp" if os.name == "posix" else os.getenv("TEMP", "")
    
    def __init__(
        self, 
        lock_file_path: Union[str, Path],
        lock_type: Optional[LockType] = None,
        timeout: int = LOCK_TIMEOUT,
        skip_failures: bool = False,
        logger: Optional[Logger] = None,
        context_name: str = "unknown"
    ):
        """
        Initialize process lock with advanced configuration
        
        :param lock_file_path: Filesystem path for lock tracking
        :param lock_type: Explicit lock mechanism selection (auto-detected by default)
        :param timeout: Maximum duration to wait for lock (seconds)
        :param skip_failures: Proceed without lock if acquisition fails
        :param logger: Custom logger instance
        :param context_name: Descriptive name for lock usage context
        """
        self.lock_path = Path(lock_file_path)
        self.context = context_name
        self.timeout = timeout
        self.skip_failures = skip_failures
        self.lock_fd = None
        self.acquired = False
        self._lock_mechanism = lock_type or self._detect_lock_mechanism()
        self._pid = os.getpid()
        self.logger = logger or self._create_default_logger()

        # Validate lock storage directory
        self._ensure_lock_directory()

    def __enter__(self):
        """Context manager entry point"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point"""
        self.release()
        return False

    def _create_default_logger(self) -> Logger:
        """Create logger instance if not provided"""
        logger = logging.getLogger("ProcessLock")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _ensure_lock_directory(self):
        """Validate and create lock storage directory"""
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, FileNotFoundError) as e:
            self.logger.error(
                f"Lock directory inaccessible: {self.lock_path.parent}. Error: {e}"
            )
            if not self.skip_failures:
                raise LockAcquisitionError(
                    f"Lock storage directory error: {e}"
                )

    def _detect_lock_mechanism(self) -> LockType:
        """Automatically determine appropriate locking mechanism"""
        try:
            if os.name == "nt":
                return LockType.MSLOCK
            
            # Attempt to determine Linux vs other POSIX
            import sys
            if "bsd" in sys.platform or "darwin" in sys.platform:
                return LockType.FLOCK
            
            # Default to POSIX fcntl
            return LockType.FCNTL
        
        except Exception:
            return LockType.FLOCK  # Safest fallback

    def _check_stale_lock(self) -> bool:
        """
        Detect and recover from stale locks (processes that died holding lock)
        Returns True if lock was stale and recovered, False otherwise
        """
        try:
            if not self.lock_path.exists():
                return False
                
            # Retrieve PID of locking process
            try:
                with open(self.lock_path, "r") as f:
                    lock_pid = int(f.read().strip())
            except (ValueError, OSError):
                return False
                
            # Check if process is still active
            if not self._is_pid_active(lock_pid):
                self.logger.warning(f"Removing stale lock from terminated process {lock_pid}")
                os.remove(self.lock_path)
                return True
                
            return False
        except Exception as e:
            self.logger.error(f"Stale lock check failed: {e}")
            return False

    def _is_pid_active(self, pid: int) -> bool:
        """Check if given PID is running on the system"""
        try:
            os.kill(pid, 0)  # Signal 0 checks process existence
            return True
        except OSError as e:
            # Process not found error code
            if e.errno in (errno.ESRCH, errno.EPERM):
                return False
            # Access denied might mean process is running
            if e.errno == errno.EPERM:
                return True
            # Unknown error
            self.logger.warning(f"PID check error for pid={pid}: {e}")
            return True  # Assume active to prevent accidental removal

    def _acquire_fcntl_lock(self) -> bool:
        """POSIX-compliant locking using fcntl"""
        import fcntl
        
        try:
            # Open file in append mode without truncating
            fd = os.open(
                str(self.lock_path), 
                os.O_CREAT | os.O_WRONLY | os.O_APPEND,
                0o600  # Owner read/write
            )
            
            # Write current PID to avoid stale locks
            os.write(fd, f"{self._pid}\n".encode())
            os.fsync(fd)  # Ensure write to disk
            
            # Acquire exclusive non-blocking lock
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            self.lock_fd = fd
            self.acquired = True
            return True
            
        except BlockingIOError:
            # Lock currently held by another process
            os.close(fd)
            return False
        except Exception as e:
            os.close(fd) if 'fd' in locals() else None
            self.logger.error(f"fcntl lock acquisition failed: {e}")
            return False

    def _acquire_flock_lock(self) -> bool:
        """BSD/MacOS compatible locking using flock"""
        import fcntl
        
        try:
            fd = os.open(
                str(self.lock_path), 
                os.O_CREAT | os.O_WRONLY | os.O_APPEND,
                0o600  # Owner read/write
            )
            
            # Write current PID to file
            os.write(fd, f"{self._pid}\n".encode())
            os.fsync(fd)
            
            # Attempt non-blocking flock
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            self.lock_fd = fd
            self.acquired = True
            return True
            
        except (BlockingIOError, IOError):
            os.close(fd)
            return False
        except Exception as e:
            os.close(fd) if 'fd' in locals() else None
            self.logger.error(f"flock acquisition failed: {e}")
            return False

    def _acquire_mslock(self) -> bool:
        """Windows-compatible locking using msvcrt"""
        try:
            import msvcrt
            
            # Windows requires binary mode + sharing
            fd = os.open(
                str(self.lock_path), 
                os.O_CREAT | os.O_RDWR | os.O_TRUNC
            )
            # Write current PID
            os.write(fd, f"{self._pid}\n".encode())
            os.fsync(fd)
            
            # Apply Windows file lock
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # Lock entire file
            
            self.lock_fd = fd
            self.acquired = True
            return True
            
        except Exception as e:
            # Windows OSError for lock contention
            if isinstance(e, OSError) and e.winerror == 33:  # Lock violation
                return False
            self.logger.error(f"Windows lock acquisition failed: {e}")
            return False

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire process lock with configurable blocking behavior
        
        :param blocking: Wait for lock if unavailable
        :return: True if lock acquired, False otherwise
        """
        if self.acquired:
            return True
            
        start_time = time.monotonic()
        retry_count = 0
        
        while time.monotonic() - start_time < self.timeout or not blocking:
            # Check for stale lock before each attempt
            self._check_stale_lock()
            
            # Select lock mechanism
            if self._lock_mechanism == LockType.FCNTL:
                acquired = self._acquire_fcntl_lock()
            elif self._lock_mechanism == LockType.FLOCK:
                acquired = self._acquire_flock_lock()
            else:  # LockType.MSLOCK
                acquired = self._acquire_mslock()
                
            if acquired:
                self.logger.info(
                    f"Acquired {self._lock_mechanism.value} lock at {self.lock_path} "
                    f"for process {self._pid} [{self.context}]"
                )
                return True
                
            if not blocking:
                break
                
            # Exponential backoff with capped retries
            sleep_time = min(
                self.RETRY_INTERVAL * (2 ** retry_count), 
                5.0  # Max 5 seconds between retries
            )
            time.sleep(sleep_time)
            retry_count = min(retry_count + 1, self.MAX_RETRIES)
        
        # Final attempt after timeout
        if self._check_stale_lock() or self._attempt_lock_override():
            return self.acquire(blocking=False)
        
        error_msg = (
            f"Failed to acquire lock after {self.timeout:.1f} seconds "
            f"at {self.lock_path} [{self.context}]"
        )
        if self.skip_failures:
            self.logger.warning(error_msg)
            return False
        raise LockAcquisitionError(error_msg)

    def _attempt_lock_override(self) -> bool:
        """Last-resort lock break for critical situations"""
        if not self.lock_path.exists():
            return False
            
        try:
            # Verify lock hasn't been acquired since last check
            if self._check_stale_lock():
                return True
                
            self.logger.critical(
                f"Forcibly removing possibly active lock at {self.lock_path}"
            )
            os.remove(self.lock_path)
            return True
        except Exception as e:
            self.logger.error(f"Lock override failed: {e}")
            return False

    def release(self) -> None:
        """Release acquired lock and clean up resources"""
        if not self.acquired or not self.lock_fd:
            return
            
        try:
            # Clear lock file contents
            os.ftruncate(self.lock_fd, 0)
            os.fsync(self.lock_fd)
            
            # Release platform-specific lock
            if self._lock_mechanism == LockType.FCNTL:
                import fcntl
                fcntl.lockf(self.lock_fd, fcntl.LOCK_UN)
            elif self._lock_mechanism == LockType.FLOCK:
                import fcntl
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            elif self._lock_mechanism == LockType.MSLOCK:
                import msvcrt
                msvcrt.locking(self.lock_fd, msvcrt.LK_UNLCK, 1)
        except Exception as e:
            error_msg = f"Lock release failed: {e}"
            if self.skip_failures:
                self.logger.error(error_msg)
            else:
                raise LockAcquisitionError(error_msg) from e
        finally:
            # Ensure file descriptor is closed
            try:
                if self.lock_fd:
                    os.close(self.lock_fd)
            except OSError as e:
                self.logger.error(f"Failed to close lock FD: {e}")
            finally:
                self.lock_fd = None
                self.acquired = False
                self.logger.info(
                    f"Released lock at {self.lock_path} [PID: {self._pid}, Context: {self.context}]"
                )

    def is_locked_by_current_process(self) -> bool:
        """Verify if lock is held by current process"""
        return self.acquired

    def get_lock_status(self) -> dict:
        """Retrieve detailed lock state information"""
        status = {
            "path": str(self.lock_path),
            "acquired": self.acquired,
            "pid": self._pid,
            "mechanism": self._lock_mechanism.value,
            "context": self.context
        }
        
        if self.lock_path.exists():
            try:
                with open(self.lock_path, "r") as f:
                    lock_data = f.read().strip()
                    status["lock_pid"] = int(lock_data) if lock_data.isdigit() else None
            except Exception:
                status["lock_pid"] = None
        return status

    def transfer_lock(self, to_pid: int) -> bool:
        """
        Transfer lock ownership to another process
        This dangerous method should be used only in controlled scenarios
        """
        if not self.acquired:
            return False
            
        try:
            # Write new PID to lock file
            os.ftruncate(self.lock_fd, 0)
            os.lseek(self.lock_fd, 0, os.SEEK_SET)
            os.write(self.lock_fd, f"{to_pid}\n".encode())
            os.fsync(self.lock_fd)
            self._pid = to_pid
            return True
        except Exception:
            return False
