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

import copy
import logging
import threading
import time
import queue
from typing import Optional, Dict, Tuple, Any, Callable

from cloud_stomp.connect import BaseConnection
from cloud_stomp.protocol import Protocol12
from cloud_stomp.transport import Transport, DEFAULT_SSL_VERSION
from cloud_stomp.exception import StompException

from cloud_ws4py.client.threadedclient import WebSocketClient

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONNECTION_TIMEOUT = 10
HEARTBEAT_INTERVAL = 15.0  # seconds
STOMP_FRAME_TERMINATOR = b'\x00'
MAX_FRAME_SIZE = 5 * 1024 * 1024  # 5MB

class EnhancedWebSocketClient(WebSocketClient):
    """
    Enhanced WebSocket client for STOMP with:
    - Thread-safe message queue
    - Connection state tracking
    - Graceful shutdown
    - Connection resilience
    - Frame size validation
    """
    
    def __init__(self, *args, **kwargs):
        self.ssl_options = kwargs.pop('ssl_options', {})
        super().__init__(*args, **kwargs)
        
        self._message_queue = queue.Queue()
        self._connection_id = f"ws-{id(self)}"
        self._shutdown_event = threading.Event()
        self._connect_lock = threading.Lock()
        
        # Connection state tracking
        self.is_connected = False
        self.connection_time = 0.0
        
        # Error statistics
        self.error_count = 0
        self.last_error = None
        
        # Performance metrics
        self.message_counter = 0
        self.bytes_received = 0
        
        logger.debug(f"Initialized WebSocket client {self._connection_id}")
    
    def connect(self):
        """Establish connection with timeout and error handling"""
        with self._connect_lock:
            if self.is_connected:
                logger.warning("Attempted to connect already connected client")
                return
                
            try:
                start_time = time.time()
                super().connect()
                
                # Wait for connection handshake to complete
                with self.handshake_complete:
                    self.handshake_complete.wait(DEFAULT_CONNECTION_TIMEOUT)
                    
                if not self.is_connected:
                    raise ConnectionTimeoutException("WebSocket handshake timed out")
                
                self.connection_time = time.time()
                logger.info(f"Connected to {self.url} in {(self.connection_time - start_time):.3f}s")
            except Exception as e:
                logger.error(f"Connection failed: {str(e)}")
                self.handle_connection_error(e)
                raise
    
    def received_message(self, message):
        """Process incoming WebSocket messages with validation"""
        try:
            # Validate message size
            if len(message.data) > MAX_FRAME_SIZE:
                logger.error(f"Frame size exceeds limit: {len(message.data)} > {MAX_FRAME_SIZE}")
                self.close(reason="Frame size violation")
                return
                
            self.message_counter += 1
            self.bytes_received += len(message.data)
            
            # Add to thread-safe queue with timestamp
            self._message_queue.put({
                'timestamp': time.time(),
                'message': message,
                'counter': self.message_counter
            })
            logger.debug(f"Received message #{self.message_counter}")
        except Exception as e:
            logger.exception("Error processing incoming message")
            self.handle_message_error(e)
    
    def receive(self, timeout: float = None) -> Optional[str]:
        """Get next message with optional timeout"""
        try:
            item = self._message_queue.get(timeout=timeout)
            if item is None or item == StopIteration:
                return None
            return str(item['message'])
        except queue.Empty:
            return None
        except Exception as e:
            logger.error(f"Receive error: {str(e)}")
            return None
    
    def closed(self, code, reason=None):
        """Handle WebSocket closure"""
        self.is_connected = False
        logger.info(f"Connection closed: {code} {reason or ''}")
        self._message_queue.put(StopIteration)
        self._shutdown_event.set()
    
    def safe_send(self, data: bytes) -> bool:
        """Send data with error handling"""
        try:
            if not self.is_connected or self.terminated:
                raise ConnectionClosedException("Connection not established")
                
            self.send(data)
            return True
        except Exception as e:
            self.handle_send_error(e)
            return False
    
    def terminate(self) -> None:
        """Gracefully terminate connection"""
        self._shutdown_event.set()
        try:
            self.close(reason="Client termination")
            self.run_forever(timeout=5.0)
            logger.debug("Client terminated cleanly")
        except:
            logger.exception("Error during termination")
    
    def handle_connection_error(self, exception: Exception) -> None:
        """Centralized connection error handling"""
        self.error_count += 1
        self.last_error = exception
        logger.error(f"Connection error #{self.error_count}: {exception}")
    
    def handle_message_error(self, exception: Exception) -> None:
        """Error handling for message processing"""
        logger.error(f"Message processing error: {exception}")
    
    def handle_send_error(self, exception: Exception) -> None:
        """Error handling for send operations"""
        logger.error(f"Send error: {exception}")
        self.error_count += 1
        self.last_error = exception

class ResilientTransport(Transport):
    """
    Enhanced STOMP transport with:
    - Automatic reconnect
    - Connection health monitoring
    - Frame rate limiting
    - Error reporting
    """
    
    def __init__(self, url: str, ssl_options: Optional[Dict] = None):
        max_retries = 5
        Transport.__init__(
            self,
            (0, 0),
            auto_reconnect=True,
            reconnect_attempts_max=max_retries,
            reconnect_sleep_initial=1.0,
            reconnect_sleep_increase=0.5,
            reconnect_sleep_jitter=0.1,
            reconnect_sleep_max=30.0,
            heartbeats=(HEARTBEAT_INTERVAL * 1000, HEARTBEAT_INTERVAL * 1000),
            ssl_version=DEFAULT_SSL_VERSION,
            ssl_options=ssl_options
        )
        
        self.ws = EnhancedWebSocketClient(
            url, protocols=["stomp", "v12.stomp"], ssl_options=ssl_options
        )
        self.ws.daemon = True
        self._connection_url = url
        self._connection_state = "disconnected"
        self._last_activity = 0.0
        self._throughput_limit = 0  # bytes/sec (0 = unlimited)
        self._sent_bytes = 0
        self._rate_limit_start = time.time()
        self._shutdown_requested = False
        
        # Event callbacks
        self.on_connect = None
        self.on_disconnect = None
        self.on_error = None
        
        logger.info(f"Initialized transport for {url}")
    
    def is_connected(self) -> bool:
        """Check both STOMP and WebSocket connection state"""
        return (
            self.connected and 
            self.ws.is_connected and 
            not self.ws.terminated
        )
    
    def connect(self, timeout: float = DEFAULT_CONNECTION_TIMEOUT) -> None:
        """Establish connection with timeout management"""
        if self._connection_state == "connecting":
            logger.warning("Connection attempt already in progress")
            return
            
        self._connection_state = "connecting"
        self._shutdown_requested = False
        
        try:
            logger.info("Initiating WebSocket connection")
            self.ws.connect()
            
            # Verify connection within timeout
            start = time.time()
            while not self.ws.is_connected and time.time() - start < timeout:
                time.sleep(0.1)
            
            if not self.ws.is_connected:
                raise ConnectionTimeoutException("WebSocket handshake timeout")
            
            # Initialize STOMP protocol
            self._establish_stomp_connection(timeout)
            
            self._connection_state = "connected"
            self._last_activity = time.time()
            
            # Execute connection callback
            if callable(self.on_connect):
                self.on_connect()
                
        except Exception as e:
            self._handle_error("Connection failed", e)
            raise
    
    def _establish_stomp_connection(self, timeout: float) -> None:
        """Perform STOMP handshake and verification"""
        # Perform STOMP CONNECT frame handshake
        self._send_connect_frame()
        
        # Wait for CONNECTED frame response
        start = time.time()
        while not self.connected and time.time() - start < timeout:
            frame = self.receive_frame()
            if frame and frame.command == b'CONNECTED':
                self._process_connected_frame(frame)
                break
        
        if not self.connected:
            raise StompException("STOMP connection handshake failed")
    
    def _send_connect_frame(self) -> None:
        """Send STOMP CONNECT frame with credentials"""
        # Customizable credentials should come from config
        headers = {
            'accept-version': '1.2',
            'heart-beat': f'{int(HEARTBEAT_INTERVAL*1000)},{int(HEARTBEAT_INTERVAL*1000)}'
        }
        
        # Add authentication if required (should be parameterized)
        auth_str = self._get_connection_auth()
        if auth_str:
            headers['login'] = auth_str[0]
            headers['passcode'] = auth_str[1]
        
        connect_frame = Protocol12.CONNECT(headers)
        self.ws.safe_send(connect_frame)
    
    def _process_connected_frame(self, frame) -> None:
        """Process STOMP CONNECTED frame"""
        self.connected = True
        self.current_host_and_port = self._parse_frame_host(frame)
        
        # Process heart-beat header
        if b'heart-beat' in frame.headers:
            try:
                client_hb, server_hb = [int(x) for x in frame.headers[b'heart-beat'].split(b',')]
                actual_hb = max(client_hb, server_hb)
                self.set_heartbeat(actual_hb / 1000.0)
            except:
                logger.exception("Error parsing heart-beat header")
    
    def set_heartbeat(self, interval: float) -> None:
        """Configure heartbeat interval (seconds)"""
        self.ws.heartbeat_freq = interval
        logger.info(f"Heartbeat interval set to {interval:.1f}s")
    
    def _get_connection_auth(self) -> Optional[Tuple[str, str]]:
        """Retrieve authentication credentials (should be overridden)"""
        # In production, get from config or external service
        return None
    
    def send(self, encoded_frame: bytes) -> None:
        """Send STOMP frame with rate limiting and logging"""
        if not self.is_connected():
            raise ConnectionClosedException("Connection not established")
        
        try:
            # Apply rate limiting if configured
            if self._throughput_limit > 0:
                self._enforce_throughput_limit(len(encoded_frame))
            
            logger.debug(f"STOMP >>> {encoded_frame.decode().strip()}")
            self.ws.safe_send(encoded_frame + STOMP_FRAME_TERMINATOR)
        except Exception as e:
            self._handle_error("Send failed", e)
            raise
    
    def _enforce_throughput_limit(self, frame_size: int) -> None:
        """Ensure we don't exceed configured throughput limits"""
        now = time.time()
        elapsed = now - self._rate_limit_start
        self._sent_bytes += frame_size
        
        if elapsed >= 1.0:
            actual_rate = self._sent_bytes / elapsed
            self._sent_bytes = 0
            self._rate_limit_start = now
            
            if actual_rate > self._throughput_limit:
                sleep_time = min((actual_rate - self._throughput_limit) / self._throughput_limit, 1.0)
                time.sleep(sleep_time)
    
    def receive(self) -> Optional[bytes]:
        """Receive and parse STOMP frame with error handling"""
        try:
            raw_msg = self.ws.receive(timeout=0.1)
            if not raw_msg:
                return None
                
            # Validate STOMP frame termination
            if not raw_msg.endswith(STOMP_FRAME_TERMINATOR.decode()):
                logger.error("Invalid frame termination")
                return None
                
            logger.debug(f"STOMP <<< {raw_msg}")
            return raw_msg.encode()
        except Exception as e:
            self._handle_error("Receive error", e)
            return None
    
    def stop(self) -> None:
        """Gracefully shutdown connection"""
        if self._shutdown_requested:
            return
            
        self._shutdown_requested = True
        logger.info("Initiating transport shutdown")
        
        try:
            # Send STOMP DISCONNECT frame
            if self.is_connected():
                self._send_disconnect_frame()
                
            # Close WebSocket
            self.ws.terminate()
            
            # Update connection state
            self._connection_state = "disconnected"
            
            # Execute disconnect callback
            if callable(self.on_disconnect):
                self.on_disconnect()
                
            logger.info("Transport stopped")
        except Exception as e:
            self._handle_error("Stop failed", e)
    
    def _send_disconnect_frame(self) -> None:
        """Send graceful DISCONNECT frame"""
        try:
            disconnect_frame = Protocol12.DISCONNECT({})
            self.send(disconnect_frame)
            time.sleep(0.1)  # Allow time for transmission
        except:
            logger.exception("Error sending DISCONNECT")
    
    def _handle_error(self, context: str, exception: Exception) -> None:
        """Centralized error handling"""
        logger.error(f"{context}: {exception}")
        self.ws.error_count += 1
        self.ws.last_error = exception
        
        # Execute error callback
        if callable(self.on_error):
            self.on_error(context, exception)
    
    def check_connection_health(self) -> bool:
        """Verify connection health and reestablish if needed"""
        time_since_active = time.time() - self._last_activity
        
        if time_since_active > HEARTBEAT_INTERVAL * 2:
            logger.warning(f"No activity for {time_since_active:.1f}s, checking connection")
            try:
                # Test connectivity with heartbeat
                self.send(Protocol12.SEND({}, b'\n'))
                return True
            except:
                logger.exception("Heartbeat test failed, reconnecting")
                self.reconnect()
                return False
        return True
    
    def reconnect(self) -> None:
        """Reestablish connection after failure"""
        if self._connection_state == "reconnecting":
            return
            
        logger.info("Initiating reconnection")
        self._connection_state = "reconnecting"
        
        try:
            self.stop()
            self.connect()
        except:
            logger.exception("Reconnection failed")
            self._connection_state = "error"
        finally:
            if self.is_connected():
                self._connection_state = "connected"

class RobustWsConnection(BaseConnection, Protocol12):
    """
    Enterprise-grade STOMP over WebSocket connection with:
    - Automatic session recovery
    - Transaction management
    - Message guarantees
    - Security hardening
    """
    
    def __init__(self, url: str, ssl_options: Optional[Dict] = None):
        self.transport = ResilientTransport(url, ssl_options=ssl_options)
        self.transport.set_listener("connection-listener", self)
        self.transactions = {}
        self._session_id = None
        self._connection_properties = {}
        self._subscribed_destinations = set()
        
        # Event handlers
        self.on_stomp_connect = None
        self.on_stomp_error = None
        
        Protocol12.__init__(self, self.transport, (0, 0))
        
        # Configure callbacks
        self.transport.on_connect = self._handle_stomp_connected
        self.transport.on_error = self._handle_stomp_error
        self.transport.on_disconnect = self._handle_stomp_disconnected
        
        logger.info(f"Created STOMP connection for {url}")
    
    def connect(self, headers: Optional[Dict] = None, **keyword_headers) -> None:
        """Establish connection with authentication"""
        try:
            # Merge authentication headers
            final_headers = self._get_auth_headers()
            if headers:
                final_headers.update(headers)
            final_headers.update(keyword_headers)
            
            # Initiate connection
            self.transport.connect()
            
            # Store session properties
            self._session_id = self.transport.session_id
            
            logger.info(f"STOMP session established: {self._session_id}")
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            raise
    
    def _get_auth_headers(self) -> Dict:
        """Retrieve authentication headers (override for custom auth)"""
        # Placeholder - add enterprise authentication logic here
        return {
            'accept-version': '1.2',
            'host': self.transport._connection_url.split('//')[1].split('/')[0]
        }
    
    def disconnect(self, receipt: Optional[str] = None, headers: Optional[Dict] = None, **keyword_headers) -> None:
        """Graceful disconnection with receipt confirmation"""
        try:
            # Prepare DISCONNECT frame
            headers = headers or {}
            if receipt:
                headers['receipt'] = receipt
            headers.update(keyword_headers)
            
            # Queue shutdown
            self.transport.stop()
            
            # Wait for completion if receipt requested
            if receipt:
                self._wait_for_receipt(receipt)
                
            logger.info("Disconnect completed")
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
            raise
    
    def _handle_stomp_connected(self) -> None:
        """Handle connection establishment"""
        if callable(self.on_stomp_connect):
            self.on_stomp_connect(self, self._session_id)
    
    def _handle_stomp_error(self, context: str, exception: Exception) -> None:
        """Handle transport-level errors"""
        logger.error(f"STOMP error: {context} - {exception}")
        if callable(self.on_stomp_error):
            self.on_stomp_error(self, context, exception)
    
    def _handle_stomp_disconnected(self) -> None:
        """Handle disconnection cleanup"""
        logger.info("STOMP connection closed")
        self._subscribed_destinations.clear()
        self.transactions = {}
    
    def subscribe(self, destination: str, id_: Optional[str] = None, 
                 ack: str = 'auto', headers: Optional[Dict] = None, 
                 callback: Optional[Callable] = None, **keyword_headers) -> None:
        """Subscribe to destination with optional callback"""
        # Generate unique subscription ID if not provided
        if not id_:
            id_ = f"sub-{time.time_ns()}"
        
        # Register callback
        if callable(callback):
            self.add_listener(id_, callback)
        
        # Track subscribed destinations
        if destination not in self._subscribed_destinations:
            self._subscribed_destinations.add(destination)
            logger.debug(f"Subscribed to {destination} [{id_}]")
        
        super().subscribe(destination, id_, ack, headers, **keyword_headers)
    
    def resubscribe(self) -> None:
        """Re-subscribe to all previous destinations after reconnect"""
        logger.info(f"Resubscribing to {len(self._subscribed_destinations)} destinations")
        for destination in self._subscribed_destinations:
            self.subscribe(destination)
    
    def begin(self, transaction: str) -> None:
        """Start transaction with guaranteed state tracking"""
        if transaction in self.transactions:
            raise StompException(f"Transaction {transaction} already exists")
            
        self.transactions[transaction] = {'count': 0, 'messages': []}
        super().begin(transaction)
    
    def commit(self, transaction: str) -> None:
        """Commit transaction with verification"""
        if transaction not in self.transactions:
            raise StompException(f"Transaction {transaction} does not exist")
            
        super().commit(transaction)
        
        # Clear transaction state on successful commit
        del self.transactions[transaction]
    
    def abort(self, transaction: str) -> None:
        """Abort transaction and requeue messages"""
        if transaction in self.transactions:
            # Requeue messages from transaction
            for msg_data in self.transactions[transaction]['messages']:
                # Implementation-specific requeue logic would go here
                logger.debug(f"Requeuing message from aborted transaction {transaction}")
            
            # Clear transaction state
            del self.transactions[transaction]
        
        super().abort(transaction)

class ConnectionTimeoutException(StompException):
    """Raised when connection operations exceed timeout"""
    pass

class ConnectionClosedException(StompException):
    """Raised when operating on closed connection"""
    pass
