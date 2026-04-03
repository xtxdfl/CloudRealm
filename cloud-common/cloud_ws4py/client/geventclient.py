#!/usr/bin/env python3
"""Advanced WebSocket client with auto-reconnect, message throttling, and enhanced observability"""

import copy
import time
import logging
import traceback
import signal
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import gevent
from gevent import Greenlet, queue, lock
from gevent.queue import Queue, PriorityQueue
from cryptography.fernet import Fernet
from prometheus_client import Counter, Gauge, Histogram
from websocket import WebSocketConnectionClosedException

from cloud_ws4py.client import WebSocketBaseClient
from cloud_ws4py.compat import py3k
from cloud_ws4py.exc import HandshakeError

__all__ = ["WebSocketClient", "SecureWebSocketClient", "MessagePriority", "ClientStatus"]

# Configure logging
logger = logging.getLogger("ws4py.client")
client_logger = logging.getLogger("ws4py.client.detail")

# Metrics
CLIENT_CONNECTIONS = Counter('websocket_client_connections', 'Client connection attempts', ['status'])
MESSAGES_SENT = Counter('websocket_client_messages_sent', 'Messages sent', ['type', 'status'])
MESSAGES_RECEIVED = Counter('websocket_client_messages_received', 'Messages received', ['type'])
RECONNECTS = Counter('websocket_client_reconnects', 'Reconnection attempts')
LATENCY_HISTOGRAM = Histogram(
    'websocket_client_latency', 
    'Message round-trip latency in seconds',
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, float('inf'))
)
QUEUE_DEPTH = Gauge('websocket_client_queue_depth', 'Pending messages in queue')
HEARTBEATS = Counter('websocket_client_heartbeats', 'Heartbeat events')

class MessagePriority:
    """Message priorities for priority queue"""
    CRITICAL = 0    # Highest priority: critical system messages
    HIGH = 1        # Time-sensitive data
    NORMAL = 2      # Regular messages
    LOW = 3         # Background/non-critical data

class ClientStatus:
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    SHUTDOWN = "shutdown"
    ERROR = "error"

class WebSocketClient(WebSocketBaseClient):
    """
    Enhanced WebSocket client with enterprise-grade features:
    - Automatic reconnection
    - Priority message queue
    - Payload encryption
    - Message acknowledgment
    - Performance metrics
    - Graceful shutdown
    - Connection health monitoring
    """
    
    DEFAULT_RECONNECT_DELAYS = (0.1, 0.5, 1, 5, 10, 30, 60)  # Exponential backoff
    
    def __init__(
        self,
        url: str,
        protocols: Optional[List[str]] = None,
        extensions: Optional[List[str]] = None,
        heartbeat_freq: Optional[float] = None,
        ssl_options: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        exclude_headers: Optional[List[str]] = None,
        max_retries: int = 8,
        priority_queue: bool = True,
        encryption_key: Optional[bytes] = None,
        auto_reconnect: bool = True,
        acknowledgment_timeout: float = 5.0,
    ):
        """
        :param url: WebSocket server URL (ws:// or wss://)
        :param protocols: Supported subprotocols
        :param heartbeat_freq: Heartbeat interval in seconds
        :param max_retries: Maximum connection attempts (0=infinite)
        :param priority_queue: Use priority queue for messages
        :param encryption_key: Encryption key for sensitive messages
        :param auto_reconnect: Automatically reconnect on failure
        :param acknowledgment_timeout: Await ACK timeout (seconds)
        """
        super().__init__(
            url,
            protocols=protocols,
            extensions=extensions,
            heartbeat_freq=heartbeat_freq,
            ssl_options=ssl_options,
            headers=headers,
            exclude_headers=exclude_headers
        )
        
        # Connection management
        self.status = ClientStatus.DISCONNECTED
        self.stats = {
            'connects': 0,
            'reconnects': 0,
            'sent': 0,
            'received': 0,
            'sent_bytes': 0,
            'received_bytes': 0,
        }
        
        # Message queue
        self.priority_queue = priority_queue
        if priority_queue:
            self.message_queue = PriorityQueue(maxsize=1000)
        else:
            self.message_queue = Queue(maxsize=1000)
            
        self.output_lock = lock.BoundedSemaphore()
        
        # Reconnection settings
        self.max_retries = max_retries
        self.auto_reconnect = auto_reconnect
        self.reconnect_delays = self.DEFAULT_RECONNECT_DELAYS
        self.curr_retry = 0
        
        # Security
        self.encryption_key = encryption_key
        if self.encryption_key:
            self.cipher = Fernet(self.encryption_key)
        
        # Message tracking
        self.pending_acks = {}
        self.ack_lock = lock.Semaphore()
        self.ack_timeout = acknowledgment_timeout
        
        # Threading/runtime
        self.run_thread = Greenlet(self._managed_run)
        self.sender_thread = Greenlet(self._process_queue)
        self.monitor_thread = Greenlet(self._monitor_health)
        self.shutdown_signal = False
        
        # Register OS signal handlers
        signal.signal(signal.SIGINT, self.handle_sigint)
        signal.signal(signal.SIGTERM, self.handle_sigterm)
    
    def connect(self, timeout: float = 10.0) -> None:
        """Initiate connection with timeout support"""
        self.stats['connects'] += 1
        self.status = ClientStatus.CONNECTING
        CLIENT_CONNECTIONS.labels(self.status).inc()
        
        try:
            # Make DNS resolution greenlet-friendly
            gevent.with_timeout(
                timeout, 
                super().connect, 
                timeout=timeout
            )
        except gevent.Timeout:
            self._handle_connection_error("Connection timed out")
            CLIENT_CONNECTIONS.labels("timeout").inc()
        except Exception as e:
            self._handle_connection_error(f"Connection error: {str(e)}")
            CLIENT_CONNECTIONS.labels("error").inc()
    
    def _managed_run(self) -> None:
        """Robust connection lifecycle management"""
        while not self.shutdown_signal:
            try:
                # Connection sequence
                self.connect()
                
                if self.terminated:
                    self._execute_reconnect()
                    continue
                    
                # Start worker threads
                self._start_dependent_threads()
                
                # Execute standard run loop
                super().run()
                
            except WebSocketConnectionClosedException:
                self.log("Connection closed by server", level=logging.INFO)
                self.status = ClientStatus.DISCONNECTED
                self._execute_reconnect()
            except Exception as e:
                self.log(f"Critical error: {str(e)}", exc_info=True, level=logging.ERROR)
                self.status = ClientStatus.ERROR
                CLIENT_CONNECTIONS.labels("critical_error").inc()
                self._execute_reconnect()
        
        # Final cleanup
        self._terminate_dependent_threads()
        self.log("Client shutdown complete", level=logging.INFO)
    
    def _start_dependent_threads(self) -> None:
        """Launch sender and monitor threads"""
        if not self.sender_thread.started or self.sender_thread.ready():
            self.sender_thread = Greenlet(self._process_queue)
        self.sender_thread.start()
        
        if not self.monitor_thread.started or self.monitor_thread.ready():
            self.monitor_thread = Greenlet(self._monitor_health)
        self.monitor_thread.start()
    
    def _terminate_dependent_threads(self) -> None:
        """Cleanly terminate background threads"""
        for thread in [self.sender_thread, self.monitor_thread]:
            if thread.started and not thread.ready():
                thread.kill(block=True, timeout=2.0)
    
    def _execute_reconnect(self) -> None:
        """Handle reconnection logic"""
        if self.shutdown_signal or not self.auto_reconnect:
            return
            
        if self.max_retries > 0 and self.curr_retry >= self.max_retries:
            self.log("Max reconnection attempts reached")
            self.shutdown()
            return
            
        self.status = ClientStatus.RECONNECTING
        self.terminated = False  # Reset state for reconnect
        
        # Exponential backoff with jitter
        delay_idx = min(self.curr_retry, len(self.reconnect_delays) - 1)
        base_delay = self.reconnect_delays[delay_idx]
        jitter = base_delay * 0.2  # ±20% jitter
        actual_delay = base_delay + (2 * jitter * random.random()) - jitter
        
        self.log(f"Reconnecting in {actual_delay:.1f}s (attempt {self.curr_retry+1})")
        RECONNECTS.inc()
        gevent.sleep(actual_delay)
        
        self.curr_retry += 1
        self.stats['reconnects'] += 1
    
    def _monitor_health(self) -> None:
        """Background connection health monitoring"""
        self.log("Starting health monitor")
        
        while self.status == ClientStatus.CONNECTED and not self.terminated:
            try:
                # Track latency via heartbeat echo
                sent_time = time.time()
                self.ping(b"heartbeat")
                
                # Expect pong within 1 second
                gevent.with_timeout(1.0, self._await_heartbeat_response, sent_time)
                HEARTBEATS.inc()
            except gevent.Timeout:
                self.log("Heartbeat timeout, reconnecting...", level=logging.WARNING)
                self.terminate(1001, "Heartbeat missed")
            except Exception as e:
                self.log(f"Heartbeat error: {str(e)}", level=logging.ERROR)
            finally:
                gevent.sleep(self.heartbeat_freq or 30)
        
        self.log("Health monitor exiting")
    
    def _await_heartbeat_response(self, sent_time: float) -> None:
        """Validate heartbeat response"""
        response = self.receive(block=True, timeout=1.0)
        if not response:
            raise RuntimeError("No heartbeat response")
            
        if response.data != b"heartbeat":
            raise RuntimeError("Invalid heartbeat payload")
            
        # Record message round-trip latency
        latency = time.time() - sent_time
        LATENCY_HISTOGRAM.observe(latency)
    
    def run(self) -> None:
        """Start client asynchronously (recommended for production)"""
        if not self.run_thread.started or self.run_thread.ready():
            self.run_thread = Greenlet(self._managed_run)
        self.run_thread.start()
    
    def handshake_ok(self) -> None:
        """Handle successful connection establishment"""
        super().handshake_ok()
        self.status = ClientStatus.CONNECTED
        CLIENT_CONNECTIONS.labels(self.status).inc()
        self.log(f"Connected to {self.url}")
        self.curr_retry = 0  # Reset retry counter on success
    
    def close(self, code: int = 1000, reason: str = "Client close") -> None:
        """Initiate graceful closure of the connection"""
        if self.status == ClientStatus.CONNECTED:
            self.status = ClientStatus.DISCONNECTED
            super().close(code, reason)
    
    def send(
        self,
        payload: Union[str, bytes],
        priority: int = MessagePriority.NORMAL,
        require_ack: bool = False,
        ack_timeout: Optional[float] = None
    ) -> Optional[uuid.UUID]:
        """
        Send a message with optional priority and acknowledgment
        
        :param payload: Message content
        :param priority: Message priority level
        :param require_ack: Whether to await acknowledgment
        :param ack_timeout: Custom ACK timeout
        :return: Message ID if awaiting ACK
        """
        # Generate unique message ID for tracking
        message_id = str(uuid.uuid4()) if require_ack else None
        
        # Prepare message object
        message = {
            'id': message_id,
            'sent_time': time.time(),
            'payload': payload,
            'priority': priority,
            'require_ack': require_ack,
            'attempts': 0
        }
        
        # Queue the message with appropriate method
        if self.priority_queue:
            self.message_queue.put((priority, message))
        else:
            self.message_queue.put(message)
        
        QUEUE_DEPTH.set(self.message_queue.qsize())
        
        # If ACK required, register and wait
        if require_ack:
            return self._await_acknowledgment(message_id, ack_timeout or self.ack_timeout)
        return None
    
    def send_control(
        self,
        opcode: int,
        body: bytes = b'',
        priority: int = MessagePriority.CRITICAL
    ) -> None:
        """Send control frames with critical priority"""
        try:
            # Use the standard method but bypass queueing
            self._write(self.stream.build(opcode, body, mask=self.stream.always_mask))
            self.log(f"Sent control frame ({opcode})", level=logging.DEBUG)
        except Exception as e:
            self.log(f"Control frame error: {str(e)}", level=logging.ERROR)
    
    def received_message(self, message) -> None:
        """Process incoming messages with acknowledgment support"""
        super().received_message(message)
        self.message_queue.put(copy.deepcopy(message))
        self.stats['received'] += 1
        self.stats['received_bytes'] += len(message.data)
        MESSAGES_RECEIVED.labels(type=type(message).__name__).inc()
        
        # Handle acknowledgment protocol
        self._handle_ack_protocol(message)
    
    def _handle_ack_protocol(self, message) -> None:
        """Process message acknowledgment messages"""
        try:
            # Protocol message format: {"type": "ack", "id": "message-id"}
            if not isinstance(message.data, bytes):
                return
                
            data = message.data.decode('utf-8', errors='ignore')
            if not data.startswith('{"type":'):
                return
                
            msg_obj = json.loads(data)
            if msg_obj.get('type') == 'ack':
                ack_id = msg_obj.get('id')
                if ack_id:
                    with self.ack_lock:
                        if ack_id in self.pending_acks:
                            event = self.pending_acks.pop(ack_id)
                            event.set()
        except Exception:
            # Safely ignore JSON errors
            pass
    
    def _await_acknowledgment(self, message_id: str, timeout: float) -> Optional[bool]:
        """Wait for message acknowledgment from server"""
        event = gevent.event.AsyncResult()
        
        with self.ack_lock:
            self.pending_acks[message_id] = event
        
        try:
            return event.get(timeout=timeout)
        except gevent.Timeout:
            self.log(f"ACK timeout for message {message_id}", level=logging.WARNING)
            return False
        finally:
            with self.ack_lock:
                if message_id in self.pending_acks:
                    del self.pending_acks[message_id]
    
    def secure_send(
        self,
        payload: Union[str, bytes, dict],
        priority: int = MessagePriority.HIGH,
        require_ack: bool = True
    ) -> Optional[uuid.UUID]:
        """Send payload with encryption and ACK requirement"""
        if not self.encryption_key:
            raise RuntimeError("Encryption not configured")
            
        if isinstance(payload, dict):
            payload = json.dumps(payload).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        
        encrypted = self.cipher.encrypt(payload)
        return self.send(encrypted, priority, require_ack)
    
    def _process_queue(self):
        """Process outgoing message queue with error handling"""
        self.log("Starting sender thread")
        
        while self.status == ClientStatus.CONNECTED and not self.terminated:
            try:
                # Queue processing
                if self.priority_queue:
                    priority, msg = self.message_queue.get(timeout=1.0)
                else:
                    msg = self.message_queue.get(timeout=1.0)
                
                self._send_queued_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"Queue processing error: {str(e)}", level=logging.ERROR)
        
        self.log("Sender thread exiting")
    
    def _send_queued_message(self, msg_dict: dict) -> None:
        """Send a message from the queue with retry logic"""
        self.log(f"Sending message: {msg_dict.get('id')}", level=logging.DEBUG)
        
        # Track send attempts
        msg_dict['attempts'] += 1
        success = False
        
        try:
            # Acquire write lock to prevent interleaving
            with self.output_lock:
                if isinstance(msg_dict['payload'], str):
                    self.send(msg_dict['payload'])
                else:
                    self.send(msg_dict['payload'], binary=True)
            
            success = True
            self.stats['sent'] += 1
            self.stats['sent_bytes'] += len(msg_dict['payload'])
            MESSAGES_SENT.labels(
                type='binary' if isinstance(msg_dict['payload'], bytes) else 'text',
                status='success'
            ).inc()
            
            # If ACK handled externally, skip waiting
            if not msg_dict.get('require_ack'):
                return
        except Exception as e:
            delay = min(0.5 * (2 ** msg_dict['attempts']), 30)
            self.log(f"Send failed (retry {msg_dict['attempts']} in {delay}s): {str(e)}")
            gevent.sleep(delay)
            MESSAGES_SENT.labels(
                type='binary' if isinstance(msg_dict['payload'], bytes) else 'text',
                status='retry'
            ).inc()
        
        # Requeue if failed and requires guarantee
        if not success and self.auto_reconnect and not self.shutdown_signal:
            if self.priority_queue:
                self.message_queue.put((msg_dict['priority'], msg_dict))
            else:
                self.message_queue.put(msg_dict)
            
            QUEUE_DEPTH.set(self.message_queue.qsize())
    
    def is_secure(self) -> bool:
        """Check if connection uses encryption"""
        return self.url.startswith('wss') or self.url.startswith('https')
    
    def get_stats(self) -> dict:
        """Get client connection statistics"""
        return copy.deepcopy(self.stats)
    
    def log(self, message: str, level: int = logging.INFO, exc_info: bool = False) -> None:
        """Standardized logging with client context"""
        log_message = f"[{self.status.upper()}] {message}"
        logger.log(level, log_message, exc_info=exc_info)
    
    def shutdown(self, timeout: float = 5.0) -> None:
        """Terminate client with graceful shutdown"""
        self.log("Initiating shutdown")
        self.status = ClientStatus.SHUTDOWN
        self.shutdown_signal = True
        
        # Close connection if needed
        try:
            self.close(code=1000, reason="Client shutdown")
        except:
            pass
            
        # Terminate threads
        threads = [self.run_thread, self.sender_thread, self.monitor_thread]
        gevent.joinall(
            threads,
            timeout=timeout,
            raise_error=False
        )
    
    def handle_sigint(self, signum, frame) -> None:
        """Handle SIGINT (Ctrl+C)"""
        self.log("SIGINT received, initiating shutdown")
        self.shutdown()
    
    def handle_sigterm(self, signum, frame) -> None:
        """Handle SIGTERM"""
        self.log("SIGTERM received, terminating")
        self.shutdown(timeout=1.0)
        sys.exit(1)

class SecureWebSocketClient(WebSocketClient):
    """Preconfigured secure client with encryption support"""
    
    def __init__(
        self,
        url: str,
        encryption_key: bytes,
        **kwargs
    ):
        # Force secure URLs
        if not self._validate_secure_url(url):
            raise ValueError("URL must be wss:// or https://")
        
        # Configure headers for secure handshake
        secure_headers = kwargs.pop('headers', {})
        secure_headers.update({
            'X-TLS-Version': '1.3',
            'X-Encryption': 'enabled',
        })
        
        super().__init__(
            url,
            encryption_key=encryption_key,
            ssl_options={
                'cert_reqs': ssl.CERT_REQUIRED,
                'check_hostname': True,
                'ssl_version': ssl.PROTOCOL_TLS_CLIENT
            },
            headers=secure_headers,
            **kwargs
        )
        
        self.log("Secure client initialized")
    
    @staticmethod
    def _validate_secure_url(url: str) -> bool:
        return url.startswith('wss://') or url.startswith('https://')
    
    def handshake_ok(self):
        super().handshake_ok()
        self.log("Secure connection established")

if __name__ == "__main__":
    # Example usage
    import os
    import logging
    from cloud_ws4py import configure_logger
    
    configure_logger(level=logging.DEBUG)
    
    # Create secure client with encryption
    encryption_key = Fernet.generate_key()
    client = SecureWebSocketClient(
        url="wss://echo.websocket.org",
        encryption_key=encryption_key,
        auto_reconnect=True,
        max_retries=5,
        acknowledgment_timeout=2.0
    )
    client.run()
    
    # Send secure message with ACK requirement
    msg_id = client.secure_send(
        {"sensitive": "financial data"},
        priority=MessagePriority.HIGH,
        require_ack=True
    )
    
    # Handle ACK
    if not client._await_acknowledgment(msg_id, 3.0):
        print("Acknowledgment timeout!")
    
    # Graceful shutdown
    while True:
        try:
            msg = client.message_queue.get()
            if msg.data == "shutdown":
                break
            print(f"Received: {msg}")
        except KeyboardInterrupt:
            client.shutdown()
            break
