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

from urllib.parse import urlparse
import logging
import http.client
import ssl
from ssl import SSLError
from typing import Tuple, Optional
import time
import os

from cloud_agent.CloudConfig import CloudConfig
from cloud_commons.inet_utils import ensure_ssl_using_protocol

# Configure logging
logger = logging.getLogger(__name__)


class NetworkError(Exception):
    """Base class for network-related errors"""
    pass

class ConnectionError(NetworkError):
    """Server connection failure"""
    pass

class SSLConfigurationError(NetworkError):
    """Invalid SSL configuration"""
    pass

class ServerUnavailableError(NetworkError):
    """Server not responding"""
    pass


class NetUtil:
    DEFAULT_CONNECT_TIMEOUT = 10
    DEFAULT_REQUEST_TIMEOUT = 30
    DEFAULT_CONNECT_RETRY_DELAY = 10  # seconds
    MIN_CONNECT_RETRY_DELAY = 1
    MAX_CONNECT_RETRY_DELAY = 300
    BACKOFF_FACTOR = 1.5
    DEFAULT_HEARTBEAT_INTERVAL_MIN = 1
    DEFAULT_HEARTBEAT_INTERVAL_MAX = 10
    MINIMUM_HEARTBEAT_INTERVAL = 0.1
    
    # Server status endpoint
    SERVER_STATUS_PATH = "/ca"
    
    def __init__(self, config: CloudConfig, stop_event=None):
        """
        Initialize network utility with configuration
        
        :param config: Cloud configuration object
        :param stop_event: Event to signal when to stop network operations
        """
        self.config = config
        self.stop_event = stop_event
        
        # Load SSL configuration
        self._initialize_ssl()
        
        # Configure timeouts
        self.connect_timeout = config.get_int("network", "connect_timeout", self.DEFAULT_CONNECT_TIMEOUT)
        self.request_timeout = config.get_int("network", "request_timeout", self.DEFAULT_REQUEST_TIMEOUT)
        
        # Configure retry parameters
        self.connect_retry_delay = config.get_int(
            "server", "connect_retry_delay", self.DEFAULT_CONNECT_RETRY_DELAY
        )
        self.max_connect_attempts = config.get_int("server", "max_connect_attempts", 3)
        self.enable_exponential_backoff = config.get_bool("server", "enable_backoff", True)
        
        # Initialize status tracking
        self.last_successful_connection = 0
        self.connection_failures = 0
        self.current_retry_delay = self.connect_retry_delay

    def _initialize_ssl(self):
        """Initialize SSL configuration based on agent settings"""
        try:
            if self.config.force_https_protocol:
                ensure_ssl_using_protocol(
                    self.config.force_https_protocol,
                    self.config.ca_cert_file_path
                )
                
            self.ssl_verify = self.config.get_bool("security", "ssl_verify_cert", True)
            
            # Create SSL context
            self.ssl_context = self._create_ssl_context() if self.ssl_verify else ssl._create_unverified_context()
            
        except ssl.SSLError as e:
            logger.critical("SSL initialization failed: %s", str(e))
            raise SSLConfigurationError(f"SSL configuration error: {str(e)}") from e

    def _create_ssl_context(self):
        """Create SSL context with verification"""
        ctx = ssl.create_default_context()
        
        # Load CA certificate bundle if provided
        if self.config.ca_cert_file_path and os.path.exists(self.config.ca_cert_file_path):
            ctx.load_verify_locations(self.config.ca_cert_file_path)
        
        # Set protocol if forced
        if self.config.force_https_protocol:
            ctx.options |= {
                "TLSv1": ssl.OP_NO_TLSv1,
                "TLSv1.1": ssl.OP_NO_TLSv1_1,
                "TLSv1.2": ssl.OP_NO_TLSv1_2,
                "TLSv1.3": ssl.OP_NO_TLSv1_3
            }.get(self.config.force_https_protocol, 0)
            
        return ctx

    def build_server_url(self, base_url: str) -> str:
        """
        Build complete server status check URL
        
        :param base_url: Server base URL
        :return: Complete status URL
        """
        return f"{base_url.rstrip('/')}{self.SERVER_STATUS_PATH}"

    def check_url(self, url: str) -> Tuple[bool, str]:
        """
        Check if a URL is reachable and returns HTTP 200
        
        :param url: URL to check
        :return: Tuple (is_reachable, response_body)
        """
        logger.debug("Checking URL: %s", url)
        response_body = ""
        
        try:
            parsed_url = urlparse(url)
            
            # Create secure connection
            if parsed_url.scheme == "https":
                conn = http.client.HTTPSConnection(
                    parsed_url.netloc,
                    timeout=self.connect_timeout,
                    context=self.ssl_context
                )
            else:
                conn = http.client.HTTPConnection(
                    parsed_url.netloc,
                    timeout=self.connect_timeout
                )
            
            # Make request with timeout
            conn.request("GET", parsed_url.path, timeout=self.request_timeout)
            response = conn.getresponse()
            status = response.status
            
            response_body = response.read().decode('utf-8', 'ignore')
            logger.debug("Response from %s: %d %s", 
                         url, status, response.reason)
            
            if status == 200:
                logger.info("Successfully connected to %s", url)
                self._record_success()
                return True, response_body
            
            logger.warning("Server returned status %d for %s", status, url)
            return False, response_body
            
        except SSLError as e:
            logger.error("SSL error connecting to %s: %s", url, str(e))
            self._record_failure()
            return False, response_body
        
        except (TimeoutError, socket.timeout):
            logger.warning("Connection to %s timed out", url)
            self._record_failure()
            return False, response_body
        
        except (ConnectionRefusedError, socket.gaierror, OSError) as e:
            logger.warning("Connection to %s failed: %s", url, str(e))
            self._record_failure()
            return False, response_body
        
        except Exception as e:
            logger.error("Unexpected error checking %s: %s", url, str(e))
            self._record_failure()
            return False, response_body

    def _record_success(self):
        """Record successful connection"""
        self.last_successful_connection = time.time()
        self.connection_failures = 0
        self.current_retry_delay = self.connect_retry_delay
        
    def _record_failure(self):
        """Record connection failure and adjust retry delay"""
        self.connection_failures += 1
        
        # Calculate next retry delay
        if self.enable_exponential_backoff:
            self.current_retry_delay = min(
                self.connect_retry_delay * (self.BACKOFF_FACTOR ** self.connection_failures),
                self.MAX_CONNECT_RETRY_DELAY
            )
        
        # Never decrease below minimum
        self.current_retry_delay = max(self.current_retry_delay, self.MIN_CONNECT_RETRY_DELAY)
        
        logger.debug("Connection failure %d, next delay: %ss", 
                     self.connection_failures, self.current_retry_delay)

    def calculate_retry_delay(self) -> float:
        """Calculate delay before next retry attempt"""
        return self.current_retry_delay

    def try_to_connect(self, server_url: str, max_retries: Optional[int] = None) -> int:
        """
        Attempt to connect to a server with automatic retries
        
        :param server_url: Server base URL to connect to
        :param max_retries: Max connection attempts (None for unlimited)
        :return: Number of retries performed
        """
        if max_retries is None:
            max_retries = self.max_connect_attempts
        
        target_url = self.build_server_url(server_url)
        logger.info("Attempting connection to %s (max attempts: %s)",
                     server_url, str(max_retries) if max_retries != -1 else "unlimited")
        
        retries = 0
        connected = False
        
        while (max_retries == -1 or retries < max_retries) and not self._should_stop():
            try:
                # Perform connection check
                reachable, _ = self.check_url(target_url)
                
                if reachable:
                    connected = True
                    logger.info("Successfully connected to server after %d attempts", retries)
                    break
                
                # Calculate retry delay
                delay = self.calculate_retry_delay()
                logger.info("Connection attempt %d failed. Retrying in %0.1f seconds...",
                             (retries + 1), delay)
                
                retries += 1
                
                # Wait before next retry
                if self.stop_event:
                    self.stop_event.wait(delay)
                else:
                    time.sleep(delay)
                
            except KeyboardInterrupt:
                logger.info("Connection attempt interrupted by user")
                break
            except Exception as e:
                logger.error("Error during connection attempt: %s", str(e))
                retries += 1
                time.sleep(1)
        
        if not connected:
            logger.error("Failed to connect to server after %d attempts", retries)
            raise ServerUnavailableError(f"Could not connect to {server_url} after {retries} attempts")
        
        return retries

    def _should_stop(self) -> bool:
        """Check if we should stop connection attempts"""
        return self.stop_event and self.stop_event.is_set()

    @classmethod
    def get_agent_heartbeat_idle_interval(
        cls, 
        cluster_size: int, 
        min_interval: Optional[float] = None, 
        max_interval: Optional[float] = None
    ) -> float:
        """
        Calculate optimal heartbeat interval based on cluster size
        
        :param cluster_size: Number of hosts in the cluster
        :param min_interval: Minimum allowed heartbeat interval (seconds)
        :param max_interval: Maximum allowed heartbeat interval (seconds)
        :return: Calculated heartbeat interval
        """
        # Set default min/max values if not provided
        min_val = min_interval or cls.DEFAULT_HEARTBEAT_INTERVAL_MIN
        max_val = max_interval or cls.DEFAULT_HEARTBEAT_INTERVAL_MAX
        
        # Calculate base interval (cluster_size scaled logarithmically)
        # Avoid division by zero for cluster_size = 0
        adjusted_size = max(1, cluster_size)
        interval = max_val - (adjusted_size ** 0.5) / 10
        
        # Apply constraints
        interval = max(min_val, min(interval, max_val))
        interval = max(cls.MINIMUM_HEARTBEAT_INTERVAL, interval)
        
        logger.debug("Calculated heartbeat interval: %.2fs for cluster size %d", 
                      interval, cluster_size)
        
        return interval
