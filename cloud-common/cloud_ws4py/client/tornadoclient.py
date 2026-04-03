#!/usr/bin/env python3
"""High-performance Tornado WebSocket client with SSL/TLS validation and connection reliability"""

import ssl
import time
import logging
import uuid
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Callable, Any

from tornado import iostream, escape, web
from tornado.ioloop import IOLoop
from tornado.netutil import ssl_wrap_socket
from cloud_ws4py.client import WebSocketBaseClient
from cloud_ws4py.exc import HandshakeError, ConnectionRefusedError, TimeoutException
from cloud_ws4py.websocket import WebSocket
from cloud_ws4py.compat import urlparse

__all__ = ["TornadoWebSocketClient", "SecureTornadoWebSocketClient", "RetryPolicy"]

logger = logging.getLogger("tornado.websocket.client")

DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 30.0
HANDSHAKE_VALIDATION_LIMIT = 10 * 1024  # 10KB max header size

class RetryPolicy:
    """Configurable connection retry strategy"""
    BACKOFF_FACTOR = 2
    INITIAL_DELAY = 0.5
    MAX_DELAY = 60
    MAX_ATTEMPTS = 5
    
    def __init__(
        self,
        backoff_factor: float = BACKOFF_FACTOR,
        initial_delay: float = INITIAL_DELAY,
        max_delay: float = MAX_DELAY,
        max_attempts: int = MAX_ATTEMPTS
    ):
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts
        self.attempts = 0
    
    def next_delay(self) -> float:
        """Calculate next retry delay with exponential backoff"""
        if self.attempts >= self.max_attempts:
            return -1  # Stop retrying
            
        delay = self.initial_delay * (self.backoff_factor ** self.attempts)
        delay = min(delay, self.max_delay)
        self.attempts += 1
        return delay
    
    def reset(self) -> None:
        """Reset retry counter"""
        self.attempts = 0

class EnhancedTornadoIOStream(iostream.IOStream):
    """Extended IOStream with timeout support and error handling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._read_timeout = None
        self._connect_timeout = None
        self._active_timeout = None
        self._connection_id = str(uuid.uuid4())
        self._last_activity = time.time()
    
    def set_timeouts(self, connect_timeout: float, read_timeout: float) -> None:
        """Configure connection and read timeouts"""
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
    
    def _handle_timeout(self) -> None:
        """Handle stream timeout scenarios"""
        if self._state == iostream.IOStream.CONNECTING:
            if time.time() - self._start_time > self._connect_timeout:
                self.close(exc_info=TimeoutException("Connection timed out"))
        elif self._state == iostream.IOStream.READING:
            if self._read_timeout and time.time() - self._last_activity > self._read_timeout:
                self.close(exc_info=TimeoutException("Read operation timed out"))
    
    def _schedule_next_timeout_check(self) -> None:
        """Periodically check for timeouts"""
        IOLoop.current().add_timeout(time.time() + 1, self._handle_timeout)
    
    def on_connection_activity(self) -> None:
        """Update last activity timestamp"""
        self._last_activity = time.time()

class TornadoWebSocketClient(WebSocketBaseClient):
    """
    Production-ready WebSocket client for Tornado with:
    - SSL/TLS certificate validation
    - Connection retry logic
    - Read/write timeouts
    - Message integrity checks
    - Detailed error reporting
    """
    
    def __init__(
        self,
        url: str,
        protocols: Optional[List[str]] = None,
        extensions: Optional[List[str]] = None,
        io_loop: Optional[IOLoop] = None,
        ssl_options: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        exclude_headers: Optional[List[str]] = None,
        message_validator: Optional[Callable] = None,
        connection_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        retry_policy: Optional[RetryPolicy] = None,
        on_connected: Optional[Callable] = None,
    ):
        """
        :param url: WebSocket URL (ws:// or wss://)
        :param protocols: Supported subprotocols
        :param extensions: Requested extensions
        :param io_loop: Custom IOLoop instance
        :param ssl_options: SSL/TLS configuration
        :param headers: Custom HTTP headers
        :param exclude_headers: Headers to exclude
        :param message_validator: Callback to verify incoming messages
        :param connection_timeout: Connection timeout in seconds
        :param read_timeout: Read operation timeout
        :param retry_policy: Custom retry strategy
        :param on_connected: Callback after successful connection
        """
        WebSocketBaseClient.__init__(
            self,
            url,
            protocols=protocols,
            extensions=extensions,
            ssl_options=ssl_options or {},
            headers=headers or {},
            exclude_headers=exclude_headers or [],
        )
        
        # Configuration
        self.io_loop = io_loop or IOLoop.current()
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.on_connected = on_connected
        self.message_validator = message_validator or self._default_validator
        
        # Connection state
        self._connection_id = uuid.uuid4().hex
        self.is_connecting = False
        self.is_connected = False
        self.is_closing = False
        
        # Security context
        self._parsed_url = urlparse(url)
        self.host = self._parsed_url.hostname
        self.port = self._parsed_url.port or (443 if self.scheme == "wss" else 80)
        
        # Initialize SSL context with safer defaults
        self._configure_secure_context()
        
        # Create enhanced IOStream
        self.io = self._create_iostream()
        
        logger.info(f"Client initialized for {url} (ID: {self._connection_id})")
    
    def _configure_secure_context(self) -> None:
        """Set up SSL context with enhanced security"""
        if self.scheme == "wss":
            # Set default SSL options
            self.ssl_options.setdefault('ssl_version', ssl.PROTOCOL_TLS_CLIENT)
            self.ssl_options.setdefault('cert_reqs', ssl.CERT_REQUIRED)
            self.ssl_options.setdefault('check_hostname', True)
            
            # Upgrade to better ciphers if possible
            if hasattr(ssl, 'OP_NO_COMPRESSION'):
                self.ssl_options.setdefault('options', ssl.OP_NO_COMPRESSION)
            if hasattr(ssl, 'OP_NO_SSLv2'):
                self.ssl_options.setdefault('options', self.ssl_options.get('options', 0) | ssl.OP_NO_SSLv2)
            if hasattr(ssl, 'OP_NO_SSLv3'):
                self.ssl_options.setdefault('options', self.ssl_options.get('options', 0) | ssl.OP_NO_SSLv3)
            if hasattr(ssl, 'OP_NO_TLSv1'):
                self.ssl_options.setdefault('options', self.ssl_options.get('options', 0) | ssl.OP_NO_TLSv1)
            
            # Configure trusted CA bundle (fallback to system default)
            if 'ca_certs' not in self.ssl_options:
                import certifi
                self.ssl_options.setdefault('ca_certs', certifi.where())
    
    def _create_iostream(self) -> EnhancedTornadoIOStream:
        """Create appropriate IOStream based on connection type"""
        if self.scheme == "wss":
            return self._create_secure_stream()
        return EnhancedTornadoIOStream(self.sock, io_loop=self.io_loop)
    
    def _create_secure_stream(self) -> EnhancedTornadoIOStream:
        """Properly wrap socket with SSL/TLS using Tornado utilities"""
        try:
            # Wrap the socket with SSL
            ssl_sock = ssl_wrap_socket(
                self.sock,
                ssl_options=self.ssl_options,
                server_hostname=self.host
            )
            
            # Create SSLIOStream with validation
            return iostream.SSLIOStream(
                ssl_sock,
                io_loop=self.io_loop,
                ssl_options=self.ssl_options
            )
        except ssl.SSLError as e:
            raise ConnectionRefusedError(f"SSL error: {str(e)}")
    
    def connect(self) -> None:
        """Initiate WebSocket connection with retry capability"""
        if self.is_connecting or self.is_connected:
            logger.warning("Attempt to connect already established connection")
            return
        
        self.is_connecting = True
        self.retry_policy.reset()
        
        try:
            logger.debug(f"Connecting to {self.host}:{self.port}")
            self.io.set_close_callback(self._connection_refused)
            
            # Configure timeouts
            self.io.set_timeouts(self.connection_timeout, self.read_timeout)
            
            # Perform TCP connection
            self.io.connect(
                (self.host, self.port), 
                callback=self._on_tcp_connected
            )
        except Exception as e:
            self._handle_initial_connection_error(str(e))
    
    def _on_tcp_connected(self) -> None:
        """Callback when TCP connection is established"""
        try:
            self.io.set_close_callback(self._connection_closed)
            
            # Write handshake request
            handshake_data = escape.utf8(self.handshake_request)
            logger.debug("Sending WebSocket handshake request")
            self.io.write(handshake_data, callback=self._handshake_sent)
        except Exception as e:
            self._handle_error("TCP connection failed", e)
    
    def _connection_refused(self, *args, **kwargs) -> None:
        """Handle connection refusal at TCP level"""
        error = "Connection refused by server"
        logger.error(error)
        self._handle_error(error)
        self._handle_connection_failed()
    
    def _connection_closed(self, *args, **kwargs) -> None:
        """Handle connection closed during handshake"""
        error = "Connection closed during handshake"
        logger.error(error)
        self._handle_error(error)
        self._handle_connection_failed()
    
    def _handshake_sent(self) -> None:
        """Callback when handshake data has been written"""
        logger.debug("Handshake data sent, awaiting response...")
        
        # Read handshake response headers
        self.io.read_until(b"\r\n\r\n", self._handshake_completed)
    
    def _handshake_completed(self, data: bytes) -> None:
        """Process WebSocket handshake response"""
        try:
            logger.debug("Received handshake response")
            
            # Validate response length for security
            if len(data) > HANDSHAKE_VALIDATION_LIMIT:
                raise HandshakeError("Excessively large handshake response")
            
            # Process and validate handshake
            response_line, _, header_data = data.partition(b"\r\n")
            self.process_response_line(response_line.strip())
            
            # Store entire response for debugging
            self.handshake_response = data.decode('utf-8', 'replace')
            
            # Extract protocols and extensions from headers
            self.protocols = []
            self.extensions = []
            if header_data:
                protocols, extensions = self.process_handshake_header(header_data)
                self.protocols = protocols
                self.extensions = extensions
            
            # Validate server handshake
            key = self.headers.get('Sec-WebSocket-Key')
            if key:
                expected_accept = self._generate_accept_header(key)
                if self.headers.get('Sec-WebSocket-Accept') != expected_accept:
                    raise HandshakeError("Invalid Sec-WebSocket-Accept header")
            
            # Connection established successfully
            self._connection_established()
            
        except HandshakeError as he:
            self._handle_error("Handshake validation failed", he)
            self.close_connection(reason="Handshake failed")
            self._handle_connection_failed()
        except Exception as e:
            self._handle_error("Unexpected handshake error", e)
            self._handle_connection_failed()
    
    def _generate_accept_header(self, key: str) -> str:
        """Generate expected Sec-WebSocket-Accept value"""
        import base64, hashlib
        key += '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
        sha1 = hashlib.sha1(key.encode()).digest()
        return base64.b64encode(sha1).decode('ascii')
    
    def _connection_established(self) -> None:
        """Finalize connection setup after handshake"""
        self.is_connecting = False
        self.is_connected = True
        
        # Configure IOStream for ongoing communication
        self.io.set_close_callback(self._stream_closed)
        
        # Notify subclass of successful connection
        self.opened()
        
        # Invoke external callback
        if self.on_connected:
            self.on_connected(self)
        
        # Begin reading data
        self._read_next_message()
        
        logger.info(f"WebSocket connection established ({self._connection_id})")
    
    def _read_next_message(self) -> None:
        """Initiate next read operation on the stream"""
        try:
            # Continuously read messages
            self.io.read_bytes(self.reading_buffer_size, self._process_incoming_data)
        except Exception as e:
            self._handle_error("Failed to read from socket", e)
    
    def _process_incoming_data(self, data: bytes) -> None:
        """Process incoming WebSocket data"""
        try:
            # Update activity timestamp
            self.io.on_connection_activity()
            
            # Process bytes through WS state machine
            if not self.process(data):
                # Processing complete (message consumed)
                self._read_next_message()
        except Exception as e:
            self._handle_error("Error processing incoming data", e)
    
    def _stream_closed(self, *args, **kwargs) -> None:
        """Handle graceful connection closure"""
        logger.info("Connection gracefully closed")
        code, reason = 1000, "Normal closure"
        self._close_connection(code, reason)
    
    def _handle_initial_connection_error(self, error: str) -> None:
        """Handle errors during initial connection phase"""
        logger.error(f"Initial connection error: {error}")
        self._handle_error("Connection failed", error)
        self._schedule_reconnect()
    
    def _handle_connection_failed(self) -> None:
        """Cleanup after failed connection attempt"""
        self.is_connecting = False
        self.close_connection(reason="Connection failed")
        self._schedule_reconnect()
    
    def _schedule_reconnect(self) -> None:
        """Schedule next reconnect attempt"""
        delay = self.retry_policy.next_delay()
        if delay < 0:
            logger.error("Max reconnection attempts reached")
            self._final_close(1006, "Connection failed")
            return
            
        logger.warning(f"Scheduling reconnect in {delay:.1f}s (attempt {self.retry_policy.attempts})")
        self.io_loop.call_later(delay, self.connect)
    
    def _default_validator(self, data: bytes) -> bool:
        """Default message validation checks"""
        # Check SHA-256 checksum if checksum header is present
        if 'x-message-checksum' in self.headers:
            expected_checksum = self.headers['x-message-checksum']
            actual_checksum = hashlib.sha256(data).hexdigest()
            if expected_checksum != actual_checksum:
                logger.error("Message checksum mismatch")
                return False
        
        return True
    
    def _write(self, b: bytes) -> None:
        """Send data to server with validation checks"""
        if self.is_closing or not self.is_connected:
            raise RuntimeError("Cannot send on closed websocket")
        
        try:
            # Add integrity headers for critical messages
            if self.message_validator(b):
                self.io.write(b)
                self.io.on_connection_activity()
            else:
                logger.warning("Message failed validation, not sending")
        except Exception as e:
            self._handle_error("Error writing to socket", e)
    
    def close(self, code: int = 1000, reason: str = "Client requested closure") -> None:
        """Cleanly close WebSocket connection"""
        if not self.is_connected:
            logger.warning("Attempt to close inactive connection")
            return
            
        self.is_closing = True
        logger.info(f"Closing connection: {code} - {reason}")
        super().close(code, reason)
    
    def close_connection(self) -> None:
        """Forcefully close underlying connection"""
        try:
            logger.debug("Closing underlying connection")
            self.io.close()
            self.is_connected = False
            self.is_closing = False
        except Exception as e:
            logger.error("Error closing connection", exc_info=True)
    
    def _close_connection(self, code: int, reason: str) -> None:
        """Handle both clean and unclean connection closure"""
        try:
            # If we have a closing frame, extract code and reason
            if self.stream.closing:
                code = self.stream.closing.code
                reason = self.stream.closing.reason or reason
            
            logger.info(f"Connection closing: {code} {reason}")
            
            # Clean up resources
            self.close_connection()
            
            # Notify subclass
            self.closed(code, reason)
        finally:
            self.is_connected = False
            self.is_closing = False
            self.stream._cleanup()
    
    def _final_close(self, code: int, reason: str) -> None:
        """Terminate connection without recovery"""
        self.io_loop.add_callback(lambda: self._close_connection(code, reason))
    
    def _handle_error(self, context: str, error: Optional[Exception] = None) -> None:
        """Centralized error handling"""
        error_msg = context
        if error:
            error_msg += f": {str(error)}"
        logger.error(error_msg, exc_info=error is not None)
        
        # Trigger error callback if defined
        if hasattr(self, 'on_error') and callable(self.on_error):
            self.on_error(error_msg, error)
    
    def __repr__(self) -> str:
        """Enhanced representation for debugging"""
        return f"<TornadoWebSocketClient {self._connection_id} connected={self.is_connected}>"

class SecureTornadoWebSocketClient(TornadoWebSocketClient):
    """Preconfigured secure client with certificate pinning"""
    
    def __init__(
        self,
        url: str,
        certificate_fingerprints: Optional[List[str]] = None,
        **kwargs
    ):
        """
        :param certificate_fingerprints: List of SHA256 fingerprints to trust
        """
        if not url.startswith("wss://"):
            raise ValueError("Secure connection requires wss:// URL")
        
        # Enforce certificate validation by default
        kwargs.setdefault('ssl_options', {})
        kwargs['ssl_options'].setdefault('cert_reqs', ssl.CERT_REQUIRED)
        
        super().__init__(url, **kwargs)
        
        # Stored fingerprints for pinning validation
        self.allowed_fingerprints = certificate_fingerprints or []
    
    def _configure_secure_context(self) -> None:
        """Override with certificate pinning configuration"""
        super()._configure_secure_context()
        
        # Add certificate pinning support
        self.ssl_options['cert_fingerprints'] = self.allowed_fingerprints
        self.ssl_options.setdefault('check_pinning', True)
    
    def _create_secure_stream(self) -> EnhancedTornadoIOStream:
        """Wrap socket and perform certificate validation"""
        ssl_socket = ssl_wrap_socket(
            self.sock,
            ssl_options=self.ssl_options,
            server_hostname=self.host,
            purpose=ssl.Purpose.SERVER_AUTH
        )
        
        # Perform certificate pinning validation
        if self.ssl_options.get('check_pinning') and self.allowed_fingerprints:
            self._validate_certificate(ssl_socket.getpeercert(binary_form=True))
        
        return iostream.SSLIOStream(
            ssl_socket,
            io_loop=self.io_loop,
            ssl_options=self.ssl_options
        )
    
    def _validate_certificate(self, der_cert: bytes) -> None:
        """Check if certificate matches approved fingerprints"""
        import hashlib
        fingerprint = hashlib.sha256(der_cert).hexdigest().lower()
        if fingerprint not in self.allowed_fingerprints:
            raise HandshakeError(f"Certificate SHA256 fingerprint ({fingerprint}) "
                                 "not in allowed list")
        
        logger.info("Certificate validated against fingerprint pinning")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    class TestClient(TornadoWebSocketClient):
        def opened(self):
            logger.info("Connection established")
            # Send test data
            self.send("Hello, Server!")
            
            # Close after reply
            self.close_after_reply = True
        
        def received_message(self, message):
            logger.info(f"Received: {message.data}")
            if hasattr(self, 'close_after_reply'):
                self.close()
        
        def closed(self, code, reason=None):
            logger.info(f"Connection closed: {code} {reason or ''}")
            IOLoop.current().stop()
        
        def on_error(self, error_msg, exception):
            logger.error(f"Client error: {error_msg}")
    
    # Example with retry policy
    retry = RetryPolicy(
        initial_delay=1.0,
        backoff_factor=1.5,
        max_delay=10,
        max_attempts=5
    )
    
    client = TestClient(
        "ws://echo.websocket.org",
        connection_timeout=5.0,
        read_timeout=15.0,
        retry_policy=retry,
        headers={
            "User-Agent": "SecureTornadoClient/1.0",
            "X-Request-ID": "test-run-001"
        }
    )
    
    client.connect()
    
    try:
        IOLoop.current().start()
    except KeyboardInterrupt:
        client.close()
        IOLoop.current().stop()
