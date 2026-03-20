#!/usr/bin/env python3
"""Enhanced threaded WebSocket client with connection management and reliability features"""

import threading
import time
import logging
import queue
import uuid
from typing import Optional, List, Iterable, Dict, Any, Callable

from cloud_ws4py.client import WebSocketBaseClient
from cloud_ws4py.exc import ConnectionClosedException, HandshakeError

__all__ = ["WebSocketThreadedClient", "RetryPolicy", "MessageQueue"]

logger = logging.getLogger("ws4py.threaded_client")

DEFAULT_HEARTBEAT_INTERVAL = 30.0  # seconds
CONNECTION_TIMEOUT = 10.0  # seconds
MESSAGE_QUEUE_TIMEOUT = 1.0  # seconds

class RetryPolicy:
    """Configurable retry strategy for reconnections"""
    def __init__(
        self,
        max_attempts: int = 5,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.current_attempt = 0

    def should_retry(self) -> bool:
        """Check if another retry should be attempted"""
        return self.current_attempt < self.max_attempts

    def next_delay(self) -> float:
        """Get next retry delay with exponential backoff"""
        if not self.should_retry():
            return 0.0
            
        delay = min(
            self.initial_delay * (self.backoff_factor ** self.current_attempt),
            self.max_delay
        )
        self.current_attempt += 1
        return delay

    def reset(self) -> None:
        """Reset retry counter"""
        self.current_attempt = 0

class MessageQueue(queue.Queue):
    """Thread-safe message queue with priority support"""
    def __init__(self, maxsize: int = 1000):
        super().__init__(maxsize=maxsize)
        self._lock = threading.RLock()
        self._interrupted = False
    
    def safe_put(self, message: Any, block: bool = True, timeout: float = None) -> None:
        """Put message with error handling"""
        if self._interrupted:
            raise ConnectionClosedException("Queue terminated")
            
        try:
            self.put(message, block=block, timeout=timeout)
        except queue.Full:
            logger.warning("Message queue full, dropping message")
    
    def safe_get(self, block: bool = True, timeout: float = None) -> Any:
        """Get message with error handling"""
        if self._interrupted:
            raise ConnectionClosedException("Queue terminated")
            
        try:
            return self.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def terminate(self) -> None:
        """Mark queue as terminated and unblock waiting threads"""
        with self._lock:
            self._interrupted = True
        
        # Put a special marker to unblock get calls
        try:
            self.put(ConnectionClosedException("Queue terminated"), block=False)
        except queue.Full:
            pass

class WebSocketThreadedClient(WebSocketBaseClient):
    """
    Production-ready threaded WebSocket client with:
    - Automatic reconnection
    - Heartbeat monitoring
    - Thread-safe message queue
    - Graceful shutdown
    - Connection state tracking
    - Error handling integration
    """
    
    def __init__(
        self,
        url: str,
        protocols: Optional[List[str]] = None,
        extensions: Optional[List[str]] = None,
        heartbeat_freq: float = DEFAULT_HEARTBEAT_INTERVAL,
        ssl_options: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        exclude_headers: Optional[List[str]] = None,
        retry_policy: Optional[RetryPolicy] = None,
        on_error: Optional[Callable[[str, Exception], None]] = None,
        on_reconnect: Optional[Callable[[int], None]] = None
    ):
        """
        :param url: WebSocket server URL
        :param heartbeat_freq: Heartbeat interval in seconds
        :param retry_policy: Custom retry strategy
        :param on_error: Error callback (func(error_message, exception))
        :param on_reconnect: Reconnect callback (func(attempt_number))
        """
        WebSocketBaseClient.__init__(
            self,
            url,
            protocols,
            extensions,
            heartbeat_freq=heartbeat_freq,
            ssl_options=ssl_options,
            headers=headers,
            exclude_headers=exclude_headers,
        )
        
        # Configuration
        self.retry_policy = retry_policy or RetryPolicy()
        self.on_error = on_error
        self.on_reconnect = on_reconnect
        
        # Connection state
        self._connection_id = uuid.uuid4().hex
        self.connection_time = 0.0
        self.is_connecting = False
        self.is_connected = False
        self.is_closing = False
        
        # Threading
        self._worker_thread = threading.Thread(
            target=self._run_client,
            name=f"WebSocketThread-{self._connection_id}",
            daemon=False
        )
        self._shutdown_event = threading.Event()
        self._send_queue = MessageQueue()
        self._receive_queue = MessageQueue()
        
        # Monitoring
        self.stats = {
            'sent_count': 0,
            'received_count': 0,
            'connect_time': 0.0,
            'connect_attempts': 0,
            'reconnects': 0
        }
        
        logger.info(f"Client initialized for {url} (ID: {self._connection_id})")
    
    def connect(self) -> None:
        """Initiate connection and start thread"""
        if self.is_connected or self.is_connecting:
            logger.warning("Client already connecting or connected")
            return
            
        self.stats['connect_attempts'] += 1
        self.is_connecting = True
        self._shutdown_event.clear()
        self._worker_thread.start()
        logger.debug("Connection thread started")
    
    def handshake_ok(self) -> None:
        """Callback when handshake is successfully completed"""
        super().handshake_ok()
        self.is_connected = True
        self.is_connecting = False
        self.connection_time = time.time()
        logger.info("WebSocket connection established")
    
    def close(self, code: int = 1000, reason: str = "Normal closure") -> None:
        """Initiate graceful closure"""
        if self.is_closing or not self.is_connected:
            return
            
        self.is_closing = True
        logger.info(f"Initiating closure: {code} {reason}")
        super().close(code, reason)
        self._shutdown_event.set()
        self._worker_thread.join(timeout=5.0)
        self._cleanup()
        logger.info("Connection fully closed")
    
    def terminate(self) -> None:
        """Force immediate termination"""
        logger.warning("Forcing client termination")
        self._shutdown_event.set()
        if self.is_connected:
            self.close_connection()
        self._worker_thread.join(timeout=2.0)
        if self._worker_thread.is_alive():
            logger.error("Worker thread still alive after join, terminating")
            # Python doesn't provide true thread termination, so we rely on daemon mode
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Clean up resources"""
        self._send_queue.terminate()
        self._receive_queue.terminate()
        self.is_connected = False
        self.is_connecting = False
        self.is_closing = False
    
    def send(self, payload: Any) -> None:
        """Queue a message for sending (thread-safe)"""
        if not self.is_connected or self.is_closing:
            raise ConnectionClosedException("Connection not established or closed")
        
        if isinstance(payload, str):
            data = payload.encode('utf-8')
        elif isinstance(payload, bytes):
            data = payload
        elif callable(payload) or isinstance(payload, Iterable):
            # Support generators and callables
            data = payload
        else:
            raise ValueError("Unsupported payload type")
        
        self._send_queue.safe_put(data)
        logger.debug("Message queued for sending")
    
    def receive(self, block: bool = True, timeout: float = None) -> Any:
        """Receive a message from the queue (thread-safe)"""
        timeout = timeout if timeout is not None else MESSAGE_QUEUE_TIMEOUT
        return self._receive_queue.safe_get(block=block, timeout=timeout)
    
    def received_message(self, message) -> None:
        """Add received message to receive queue"""
        self.stats['received_count'] += 1
        self._receive_queue.safe_put(message, block=False)
        logger.debug(f"Received message (#{self.stats['received_count']})")
    
    def closed(self, code: int, reason: str = None) -> None:
        """Handle connection closure"""
        self.is_connected = False
        self._receive_queue.safe_put(ConnectionClosedException("Connection closed"))
        logger.info(f"Connection closed: {code} {reason or ''}")
        self._shutdown_event.set()
    
    def _run_client(self) -> None:
        """Main client processing thread"""
        logger.debug("Client thread started")
        
        connection_success = False
        reconnect_attempt = 0
        
        while not self._shutdown_event.is_set() and self.retry_policy.should_retry():
            try:
                # Attempt connection
                logger.debug("Starting connection attempt")
                super().connect()
                
                # Mark successful connection
                connection_success = True
                self.retry_policy.reset()
                
                # Start heartbeat and message processing
                self._run_event_loop()
                
            except HandshakeError as he:
                logger.error(f"Handshake failed: {str(he)}")
                self._notify_error("Handshake failed", he)
            except ConnectionRefusedError as cre:
                logger.error("Connection refused by server")
                self._notify_error("Connection refused", cre)
            except Exception as e:
                logger.error(f"Connection error: {str(e)}", exc_info=True)
                self._notify_error("Connection error", e)
            finally:
                if connection_success:
                    # Only need to reconnect if we were connected
                    self._schedule_reconnect(reconnect_attempt)
                    reconnect_attempt += 1
        
        if not connection_success:
            logger.error("All connection attempts failed")
            self._cleanup()
    
    def _run_event_loop(self) -> None:
        """Handle message sending and heartbeat in event loop"""
        last_heartbeat = time.time()
        
        while not self._shutdown_event.is_set() and self.is_connected:
            try:
                # Handle outgoing messages
                self._process_outgoing_queue()
                
                # Handle heartbeats
                current_time = time.time()
                if self.heartbeat_freq > 0 and current_time - last_heartbeat > self.heartbeat_freq:
                    self._send_heartbeat()
                    last_heartbeat = current_time
                
                # Prevent busy-waiting
                self._shutdown_event.wait(0.05)
                
            except ConnectionClosedException:
                logger.info("Connection closed during event loop")
                break
            except Exception as e:
                logger.error(f"Event loop error: {str(e)}", exc_info=True)
                self._notify_error("Processing error", e)
                self.close(code=1002, reason="Processing error")
    
    def _process_outgoing_queue(self) -> None:
        """Send messages from the queue"""
        timeout = self.heartbeat_freq if self.heartbeat_freq > 0 else MESSAGE_QUEUE_TIMEOUT
        
        # Process all available messages
        while not self._shutdown_event.is_set():
            payload = self._send_queue.safe_get(timeout=timeout)
            if payload is None:
                break
                
            if callable(payload):
                # Handle generator functions
                try:
                    for chunk in payload():
                        if self.is_closing:
                            return
                        super().send(chunk)
                except Exception as e:
                    logger.error(f"Generator error: {str(e)}")
                    self._notify_error("Generator failure", e)
            elif isinstance(payload, bytes):
                # Standard message
                super().send(payload)
                self.stats['sent_count'] += 1
                logger.debug(f"Message sent (#{self.stats['sent_count']})")
    
    def _send_heartbeat(self) -> None:
        """Send a heartbeat ping to server"""
        try:
            self.ping(b'heartbeat')
            logger.debug("Heartbeat sent")
        except Exception as e:
            logger.error(f"Heartbeat failed: {str(e)}")
            self.close(code=1002, reason="Heartbeat failure")
    
    def _schedule_reconnect(self, attempt: int) -> None:
        """Initiate reconnection attempt after delay"""
        if not self.retry_policy.should_retry():
            logger.error("Max reconnect attempts reached")
            return
            
        delay = self.retry_policy.next_delay()
        self.stats['reconnects'] += 1
        
        logger.info(f"Scheduling reconnect in {delay:.1f}s (attempt {self.retry_policy.current_attempt})")
        
        # Notify external handler
        if self.on_reconnect:
            try:
                self.on_reconnect(self.retry_policy.current_attempt)
            except Exception:
                logger.exception("Error in reconnect callback")
        
        # Wait before next attempt
        self._shutdown_event.wait(delay)
    
    def _notify_error(self, context: str, error: Exception) -> None:
        """Notify error via callback and log"""
        logger.error(f"{context}: {str(error)}")
        if self.on_error:
            try:
                self.on_error(context, error)
            except Exception:
                logger.exception("Error in error callback")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(threadName)s] %(levelname)s: %(message)s'
    )
    
    # Create retry policy with backoff
    retry = RetryPolicy(
        max_attempts=5,
        backoff_factor=1.8,
        initial_delay=2.0
    )
    
    class EchoClient(WebSocketThreadedClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, retry_policy=retry, **kwargs)
            self.received_messages = 0
            
        def opened(self):
            logger.info("Connection established, sending messages...")
            
            # Test generator-style messages
            def data_provider():
                data = ["Chunk1", "Chunk2", "EndSignal"]
                for chunk in data:
                    yield chunk
                    time.sleep(0.5)  # Simulate processing time
            self.send(data_provider)
            
            # Send regular messages
            for i in range(5):
                self.send(f"Message #{i+1}")
            
        def received_message(self, message):
            self.received_messages += 1
            print(f"Received: {message}")
            
            if self.received_messages >= 10:
                self.close()
        
        def closed(self, code, reason):
            logger.info(f"Connection closed: {code} - {reason}")
            # This triggers automatically
    
    # Create client
    client = EchoClient(
        "ws://echo.websocket.org",
        heartbeat_freq=15.0,
        headers=[("X-Client-Id", "TestClient/1.0")],
        on_error=lambda ctx, err: logger.error(f"Client error: {ctx} - {str(err)}")
    )
    
    # Start connection
    client.connect()
    
    try:
        # Monitor for messages from main thread
        while True:
            msg = client.receive()
            if isinstance(msg, Exception):
                if isinstance(msg, ConnectionClosedException):
                    logger.info("Connection closed message received")
                    break
                else:
                    logger.error(f"Unexpected exception: {str(msg)}")
            elif msg:
                print(f"Main thread received: {msg}")
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, closing client")
        client.terminate()
    
    logger.info(f"Client stats: {client.stats}")
    logger.info("Application finished")
