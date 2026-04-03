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
import platform
import socket
import subprocess
import sys
import threading
import time
import psutil  # Requires psutil library

logger = logging.getLogger(__name__)

class PortOccupiedError(Exception):
    """Exception raised when a port is occupied by another process"""
    def __init__(self, port, process_info):
        super().__init__(f"Port {port} occupied by: {process_info}")
        self.port = port
        self.process_info = process_info

class PingPortListener(threading.Thread):
    """Listener for ping requests that responds with 'OK'"""

    def __init__(self, config, stop_event=None):
        """
        Initialize a ping port listener
        
        Args:
            config (CloudConfig): Configuration object
            stop_event (threading.Event): Event to stop the listener
        """
        super().__init__()
        self.daemon = True
        self.config = config
        self.stop_event = stop_event or threading.Event()
        self.host = "0.0.0.0"
        self.port = config.get_int("agent", "ping_port", default=0)
        self.socket = None
        self.listen_port = None
        self.max_errors = 5
        self.error_count = 0
        
        logger.info(f"Initializing PingPortListener on port {self.port}")

        # Validate port availability
        self._validate_port()
        
        # Create TCP socket
        logger.debug("Creating TCP socket for ping responses")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to the specified port
        logger.debug(f"Binding to port {self.port}")
        try:
            self.socket.bind((self.host, self.port))
            self.listen_port = self.socket.getsockname()[1]
        except OSError as e:
            if e.errno == 98:  # Address already in use
                process_info = self.get_process_using_port(self.port)
                logger.error(f"Port {self.port} already in use: {str(e)}")
                logger.debug(f"Occupying process: {process_info}")
                raise PortOccupiedError(self.port, process_info) from e
            else:
                logger.error(f"Socket bind error: {str(e)}")
                raise
        except Exception as e:
            logger.exception("Unexpected error during binding")
            raise RuntimeError(f"Binding failed: {str(e)}") from e
        
        # Start listening
        self.socket.listen(5)
        logger.info(f"PingPortListener active on port: {self.listen_port}")
        config.set("agent", "current_ping_port", str(self.listen_port))

    @staticmethod
    def get_process_using_port(port):
        """
        Get information about the process using a specific port,
        using cross-platform methods.
        
        Args:
            port (int): Port number to check
            
        Returns:
            str: Process information or error message
        """
        try:
            # First try with psutil for cross-platform support
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    if conn.pid:
                        proc = psutil.Process(conn.pid)
                        return f"{proc.name()} (PID: {proc.pid}, CMD: {' '.join(proc.cmdline())})"
            return "Unknown process (can't determine using psutil)"
        except Exception:
            # Fall back to system commands if psutil fails
            
            # Determine OS for appropriate command
            system = platform.system().lower()
            
            try:
                if system in ["linux", "darwin"]:  # Linux/Unix/macOS
                    # Try both lsof and fuser
                    commands = [
                        f"lsof -i :{port} | awk '/LISTEN/ {{print $1, $2}}'",
                        f"fuser {port}/tcp 2>/dev/null | awk '{{print $0}}'"
                    ]
                elif system == "windows":
                    commands = [
                        f'netstat -ano | findstr ":{port}.*LISTENING"'
                    ]
                else:
                    return "Unknown OS - can't determine process"
                
                # Execute commands until one returns valid output
                for cmd in commands:
                    result = subprocess.run(
                        cmd, 
                        shell=True, 
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    if result.stdout.strip():
                        return result.stdout.strip()
                
                return "No process information found"
                
            except Exception as e:
                return f"Error retrieving process: {str(e)}"

    def _validate_port(self):
        """Validate port number range"""
        if not (0 <= self.port <= 65535):
            logger.warning(f"Port number {self.port} is invalid, using random port")
            self.port = 0
    
    def run(self):
        """Main listening loop"""
        logger.info("PingPortListener started")
        
        try:
            while not self.stop_event.is_set():
                # Set a timeout to periodically check the stop event
                self.socket.settimeout(0.5)  # Timeout every 0.5 seconds to check termination
                
                try:
                    logger.debug("Waiting for connections...")
                    conn, addr = self.socket.accept()
                    logger.debug(f"Connection from {addr}")
                    
                    # Process the connection
                    with conn:
                        try:
                            # Respond to ping request
                            conn.sendall(b"OK")
                            self.error_count = 0  # Reset error count on success
                        except Exception as e:
                            logger.error(f"Failed to reply to ping: {str(e)}")
                            self._handle_error(e)
                except socket.timeout:
                    # This is expected - we're using non-blocking with timeout
                    continue
                except OSError as e:
                    if e.errno == 9:  # Bad file descriptor (socket closed)
                        logger.info("Socket closed, stopping listener")
                        break
                    logger.error(f"Socket error: {str(e)}")
                    self._handle_error(e)
                except Exception as e:
                    logger.error(f"Unexpected connection error: {str(e)}")
                    self._handle_error(e)
        
        except Exception as e:
            logger.exception("Critical failure in PingPortListener")
        finally:
            logger.info("PingPortListener terminated")
            self.close()

    def _handle_error(self, error):
        """Handle operational errors with resilience strategies"""
        self.error_count += 1
        logger.debug(f"Error count: {self.error_count}/{self.max_errors}")
        
        # Backoff after consecutive errors
        if self.error_count > 3:
            time.sleep(0.1 * self.error_count)
            
        if self.error_count >= self.max_errors:
            logger.error(f"Max error limit reached ({self.max_errors}), terminating listener")
            self.close()
            if not self.stop_event.is_set():
                self.stop_event.set()
            raise RuntimeError("Critical failure in ping port listener")

    def stop(self):
        """Gracefully stop the listener"""
        logger.info("Stopping PingPortListener")
        if self.socket:
            try:
                # Create a temporary connection to unblock accept()
                temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_sock.connect(("127.0.0.1", self.listen_port))
                temp_sock.close()
            except Exception:
                pass
            
            # Set stop event and close socket
            self.stop_event.set()
            self.close()

    def close(self):
        """Close network resources"""
        if self.socket:
            try:
                self.socket.close()
                logger.debug("Socket closed")
            except Exception as e:
                logger.error(f"Error closing socket: {str(e)}")
            finally:
                self.socket = None

    def __del__(self):
        """Destructor for resource cleanup"""
        if self.socket:
            self.close()
        logger.debug("PingPortListener destroyed")

    @staticmethod
    def create_safe(config, stop_event=None):
        """
        Create PingPortListener with safety mechanisms
        
        Args:
            config (CloudConfig): Configuration object
            stop_event (threading.Event): Event to stop the listener
            
        Returns:
            PingPortListener instance or None on failure
        """
        try:
            return PingPortListener(config, stop_event)
        except PortOccupiedError as e:
            logger.error(f"PingPortListener cannot start: {str(e)}")
            return None
        except Exception as e:
            logger.exception("Failed to initialize PingPortListener")
            return None
