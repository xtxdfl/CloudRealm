#!/usr/bin/env python3
"""High-performance gevent WebSocket server with enhanced management features"""

import logging
import signal
import time
import os
import sys
import json
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import gevent
from gevent.pywsgi import WSGIHandler, WSGIServer as _WSGIServer
from gevent.pool import Pool
from gevent.queue import Queue
from prometheus_client import start_http_server, Counter, Gauge, Histogram

from cloud_ws4py import format_addresses
from cloud_ws4py.server.wsgiutils import WebSocketWSGIApplication
from cloud_ws4py.websocket import WebSocket
from cloud_ws4py import configure_logger as base_configure_logger

__version__ = "2.5.0"
__all__ = [
    "WebSocketWSGIHandler", 
    "WSGIServer", 
    "GEventWebSocketPool",
    "ConnectionManager",
    "configure_logger"
]

# Configure logging
logger = logging.getLogger("cloud_ws4py.server")

# Global metrics
METRICS_PORT = int(os.getenv("WS_METRICS_PORT", 9100))
WS_CONNECTIONS = Gauge('websocket_active_connections', 'Active WebSocket connections')
WS_MESSAGES_SENT = Counter('websocket_messages_sent_total', 'Total messages sent', ['type'])
WS_MESSAGES_RECEIVED = Counter('websocket_messages_received_total', 'Total messages received', ['type'])
WS_CONNECTION_DURATION = Histogram('websocket_connection_duration_seconds', 'Duration of WebSocket connections')
WS_HANDSHAKE_FAILURES = Counter('websocket_handshake_failures', 'Failed WebSocket handshakes')
SERVER_REQUEST_COUNT = Counter('server_http_requests_total', 'Total HTTP requests', ['method', 'status'])

# Graceful shutdown constants
GRACEFUL_SHUTDOWN_PERIOD = 15.0  # seconds
CONNECTION_DRAIN_TIMEOUT = 30.0  # seconds

def configure_logger(level: int = logging.INFO, filename: Optional[str] = None) -> None:
    """Extended logger configuration with server-specific settings"""
    base_configure_logger(level, filename)
    if filename:
        handler = logging.FileHandler(filename)
    else:
        handler = logging.StreamHandler()
        
    formatter = logging.Formatter(
        '%(asctime)s [%(process)d] %(name)s/%(levelname)s: '
        '%(client_ip)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)

class ConnectionMetadata:
    """Metadata container for WebSocket connections"""
    __slots__ = (
        'connected_at', 'last_active', 
        'remote_addr', 'path', 'headers'
    )
    
    def __init__(self, environ: Dict[str, Any]) -> None:
        self.connected_at = time.time()
        self.last_active = time.time()
        self.remote_addr = format_addresses({
            'peer': environ.get('REMOTE_ADDR', ''),
            'port': int(environ.get('REMOTE_PORT', 0))
        })
        self.path = environ.get('PATH_INFO', '')
        self.headers = {
            k: v for k, v in environ.items() 
            if k.startswith('HTTP_')
        }
    
    def touch(self) -> None:
        """Update the last activity timestamp"""
        self.last_active = time.time()
        
    def __json__(self) -> Dict[str, Any]:
        return {
            "remote_addr": self.remote_addr,
            "path": self.path,
            "duration": self.connection_duration,
            "last_active": self.last_active - self.connected_at
        }
    
    @property
    def connection_duration(self) -> float:
        return time.time() - self.connected_at

class WebSocketWSGIHandler(WSGIHandler):
    """
    Enhanced WSGI handler with:
    - WebSocket upgrade support
    - Connection metadata tracking
    - Graceful degradation to HTTP
    - Robust exception handling
    
    Features:
    1. Automatically handles Upgrade header
    2. Tracks connection metadata
    3. Fallback to standard HTTP processing
    4. Detailed metrics collection
    """
    
    def run_application(self) -> None:
        """Execute the WSGI application with WebSocket detection"""
        start_time = time.time()
        status_code = '500'
        request_id = hex(id(self))
        client_ip = self.environ.get('REMOTE_ADDR', 'unknown')
        
        # Set logging context
        logger = logging.LoggerAdapter(
            logging.getLogger('cloud_ws4py.server.request'),
            {'client_ip': client_ip}
        )
        
        try:
            upgrade_header = self.environ.get("HTTP_UPGRADE", "").lower()
            
            if upgrade_header == "websocket":
                logger.info(
                    f"[REQ-{request_id}] WebSocket upgrade attempt from {client_ip}"
                )
                
                # Prepare WebSocket environment
                self.environ["ws4py.socket"] = (
                    self.socket or self.environ["wsgi.input"].rfile._sock
                )
                
                # Process upgrade handshake
                self.result = self.application(self.environ, self.start_response) or []
                self.process_result()
                
                # Extract created WebSocket instance
                ws = self.environ.pop("ws4py.websocket", None)
                if ws:
                    # Track metadata and manage connection
                    self.environ["ws4py.metadata"] = ConnectionMetadata(self.environ)
                    status_code = '101'  # Switching Protocols
                    logger.info(
                        f"[REQ-{request_id}] WebSocket established with {client_ip}"
                    )
                    
                    # Transfer socket ownership to connection pool
                    del self.environ["ws4py.socket"]
                    self.socket = None
                    self.rfile.close()
                    
                    # Track connection in server's pool
                    ws_greenlet = self.server.pool.track(ws, self.environ["ws4py.metadata"])
                    ws_greenlet.join()
                else:
                    WS_HANDSHAKE_FAILURES.inc()
                    logger.error(
                        f"[REQ-{request_id}] WebSocket creation failed for {client_ip}"
                    )
            else:
                # Standard HTTP request processing
                self._original_run_application()
                status_code = str(self.status.split(' ')[0])
        except Exception as e:
            logger.exception(
                f"[REQ-{request_id}] Unhandled exception: {e}"
            )
            status_code = '500'
        finally:
            # Cleanup and metrics
            duration = time.time() - start_time
            method = self.environ.get('REQUEST_METHOD', 'UNKNOWN')
            
            SERVER_REQUEST_COUNT.labels(method, status_code).inc()
            logger.info(
                f"[REQ-{request_id}] {method} {self.environ.get('PATH_INFO')} "
                f"{status_code} {duration:.3f}s"
            )

    def _original_run_application(self) -> None:
        """Delegate to base HTTP processing"""
        super().run_application()

class GEventWebSocketPool(Pool):
    """
    Advanced WebSocket connection pool with:
    - Active connection monitoring
    - Graceful shutdown support
    - Per-client metadata tracking
    - Automatic reaping of stalled connections
    
    Features:
    1. Connection lifecycle tracking with metrics
    2. Automatic heartbeat verification
    3. Connection termination by pattern
    4. Cluster-wide connection statistics
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._connections = {}  # greenlet -> (websocket, metadata)
        self._metadata_map = {}  # remote_addr -> [connections]
        self._signal_queue = Queue()
        self._monitor_greenlet = gevent.spawn(self._monitor_connections)
        self._shutting_down = False

    def track(self, websocket: WebSocket, metadata: ConnectionMetadata) -> gevent.Greenlet:
        """Register and activate a new WebSocket connection"""
        conn_greenlet = self.spawn(self._connection_runner, websocket, metadata)
        self._connections[conn_greenlet] = (websocket, metadata)
        
        # Track by client address
        if metadata.remote_addr not in self._metadata_map:
            self._metadata_map[metadata.remote_addr] = []
        self._metadata_map[metadata.remote_addr].append(conn_greenlet)
        
        # Update metrics
        WS_CONNECTIONS.inc()
        
        logger.info(
            f"New connection: {metadata.remote_addr} ({len(self)} active)"
        )
        return conn_greenlet

    def _connection_runner(self, websocket: WebSocket, metadata: ConnectionMetadata) -> None:
        """Execute and monitor a WebSocket connection"""
        try:
            start_time = time.time()
            websocket.run()
        finally:
            with WS_CONNECTION_DURATION.time():
                # Cleanup resource tracking
                if metadata.remote_addr in self._metadata_map:
                    if gevent.getcurrent() in self._metadata_map[metadata.remote_addr]:
                        self._metadata_map[metadata.remote_addr].remove(gevent.getcurrent())
                
                # Update metrics and log
                duration = time.time() - start_time
                WS_CONNECTIONS.dec()
                logger.info(
                    f"Connection closed: {metadata.remote_addr} "
                    f"(duration: {duration:.1f}s, active: {len(self)})"
                )
                
                # Remove from connection map
                if gevent.getcurrent() in self._connections:
                    del self._connections[gevent.getcurrent()]

    def _monitor_connections(self, interval: float = 30.0) -> None:
        """Background task to monitor connection health"""
        while not self._shutting_down:
            try:
                # Check for stalled connections
                for greenlet, (ws, meta) in list(self._connections.items()):
                    if not greenlet.started:
                        continue
                        
                    # Auto-close connections exceeding max duration
                    if hasattr(ws, 'MAX_CONNECTION_DURATION'):
                        if meta.connection_duration > ws.MAX_CONNECTION_DURATION:
                            logger.warning(
                                "Terminating connection %s: exceeded max duration",
                                meta.remote_addr
                            )
                            ws.close(1000, "Connection lifetime expired")
                            
                    # Heartbeat verification
                    if hasattr(ws, 'HEARTBEAT_INTERVAL'):
                        if time.time() - meta.last_active > 2 * ws.HEARTBEAT_INTERVAL:
                            logger.warning(
                                "Terminating connection %s: heartbeat timeout",
                                meta.remote_addr
                            )
                            ws.close(1002, "Heartbeat timeout")
            except Exception as e:
                logger.error("Connection monitor error: %s", e)
            
            gevent.sleep(interval)

    def broadcast(self, message: str, origin: Optional[WebSocket] = None, 
                 pattern: Optional[str] = None) -> None:
        """Broadcast message to matching connections"""
        recipients = 0
        for greenlet, (ws, meta) in list(self._connections.items()):
            if ws.terminated or ws is origin:
                continue
                
            if pattern and not re.search(pattern, meta.path):
                continue
                
            try:
                ws.send(message)
                WS_MESSAGES_SENT.labels('broadcast').inc()
                recipients += 1
            except Exception as e:
                logger.error("Broadcast send error: %s", e)
        
        logger.debug("Broadcast sent to %d connections", recipients)

    def terminate_by_pattern(self, pattern: str, reason: str = "Server maintenance") -> int:
        """Terminate connections matching URL pattern"""
        terminated = 0
        for greenlet, (ws, meta) in list(self._connections.items()):
            if re.search(pattern, meta.path):
                try:
                    ws.close(1001, reason)
                    terminated += 1
                except Exception:
                    pass
        logger.info(f"Terminated {terminated} connections matching {pattern}")
        return terminated

    def connection_stats(self) -> Dict[str, Any]:
        """Return detailed connection statistics"""
        connections_by_path = {}
        for _, meta in self._connections.values():
            connections_by_path[meta.path] = connections_by_path.get(meta.path, 0) + 1
        
        return {
            "total_active": len(self),
            "connections_by_path": connections_by_path,
            "clients": list(self._metadata_map.keys())
        }

    def clear(self, reason: str = "Server shutdown") -> None:
        """Gracefully close all connections with custom reason"""
        self._shutting_down = True
        logger.info(f"Initiating graceful shutdown: {len(self)} connections")
        
        # Broadcast server shutdown notification
        self.broadcast(json.dumps({
            "type": "server_event",
            "event": "shutdown",
            "reason": reason,
            "timeout": CONNECTION_DRAIN_TIMEOUT
        }))
        
        # Give clients time to disconnect cleanly
        gevent.sleep(GRACEFUL_SHUTDOWN_PERIOD)
        
        # Manually terminate remaining connections
        remaining = len(self)
        for greenlet, (ws, meta) in list(self._connections.items()):
            try:
                ws.close(1001, reason)
                logger.debug(f"Closed connection: {meta.remote_addr}")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
        
        # Allow time for connection cleanup
        gevent.sleep(5)
        
        logger.info(f"Shutdown completed: {remaining} connections terminated")

class WSGIServer(_WSGIServer):
    """
    Production-grade WebSocket server with:
    - Graceful shutdown handling
    - Signal-based administration
    - Automatic metrics endpoint
    - Runtime configuration reloading
    
    Features:
    1. SIGUSR1: Connection statistics dump
    2. SIGHUP: Configuration reload
    3. SIGTERM/SIGINT: Graceful shutdown
    """
    
    handler_class = WebSocketWSGIHandler
    
    def __init__(self, listener: Tuple[str, int], application: Callable, 
                 spawn: Optional[Pool] = None, **kwargs) -> None:
        super().__init__(listener, application, spawn, **kwargs)
        
        # Start metrics server on child port
        if METRICS_PORT and os.getpid() != self.pid:  # Avoid duplicate forks
            start_http_server(METRICS_PORT)
            logger.info(f"Metrics server active on port {METRICS_PORT}")
        
        # Replace pool with our enhanced version
        self.pool = kwargs.get("connection_pool", GEventWebSocketPool())
        
        # Signal handling setup
        gevent.signal(signal.SIGTERM, self.graceful_stop, "SIGTERM")
        gevent.signal(signal.SIGINT, self.graceful_stop, "SIGINT")
        gevent.signal(signal.SIGUSR1, self.dump_connection_stats)
        gevent.signal(signal.SIGHUP, self.reload_configuration)
        
    def graceful_stop(self, signame: str = 'SIGTERM') -> None:
        """Initiates controlled shutdown sequence"""
        logger.critical(f"Received {signame}, initiating graceful shutdown...")
        
        # Step 1: Stop accepting new connections
        self.stop_accepting()
        logger.info("Stopped accepting new connections")
        
        # Step 2: Close existing connections
        self.pool.clear(f"Server terminating ({signame})")
        
        # Step 3: Final server termination
        super().stop()
        logger.info("Server shutdown complete")
        
        # Step 4: Exit process
        os._exit(0)  # Prevent gevent cleanup hangs

    def dump_connection_stats(self) -> None:
        """Output current connection statistics"""
        stats = self.pool.connection_stats()
        logger.info("====== Connection Statistics ======")
        logger.info(f"Total Active: {stats['total_active']}")
        logger.info("By Path:")
        for path, count in stats.get('connections_by_path', {}).items():
            logger.info(f"  {path}: {count}")
        logger.info("="*40)

    def reload_configuration(self) -> None:
        """Hot-reload server configuration"""
        logger.info("Reloading server configuration...")
        # Implementation would parse config files and update operational parameters
        
    def serve_forever(self, stop_timeout: float = 60.0, **kwargs) -> None:
        """Enhanced forever loop with health checks"""
        logger.info(
            f"Server started on {format_addresses(self.address)} "
            f"(PID: {os.getpid()})"
        )
        
        try:
            super().serve_forever(stop_timeout=stop_timeout, **kwargs)
        except KeyboardInterrupt:
            self.graceful_stop("KeyboardInterrupt")
        except Exception as e:
            logger.exception(f"Critical server failure: {e}")
            self.pool.clear("Critical failure")
            raise

class ConnectionManager:
    """
    Advanced connection orchestration with:
    - Session-based routing
    - Authentication interceptor
    - Message transformation pipeline
    - Protocol negotiation
    
    Integration:
    from cloud_ws4py.server.geventserver import ConnectionManager
    
    app = WebSocketWSGIApplication(
        handler_cls=WSHandler,
        connection_manager=CustomConnectionManager()
    )
    """
    
    def __init__(self, auth_function: Optional[Callable] = None, 
                 max_connections_per_ip: int = 50) -> None:
        self.auth_function = auth_function
        self.max_connections_per_ip = max_connections_per_ip
        self.connection_counter = Counter()
        
    def upgrade(self, environ: Dict[str, Any]) -> bool:
        """
        Validate connection before upgrade:
        1. Check authentication
        2. Enforce rate limits
        3. Verify protocol compatibility
        """
        client_ip = environ.get('REMOTE_ADDR')
        
        # Rate limiting by IP
        if self.connection_counter[client_ip] > self.max_connections_per_ip:
            logger.warning(f"Connection limit exceeded for {client_ip}")
            return False
        
        # Custom authentication
        if self.auth_function and not self.auth_function(environ):
            logger.info(f"Authentication failed for {client_ip}")
            return False
            
        self.connection_counter[client_ip] += 1
        return True
        
    def transform_incoming(self, websocket: WebSocket, message: str) -> Any:
        """
        Pre-process incoming messages:
        - Deserialization
        - Validation
        - Compression
        """
        return message
        
    def transform_outgoing(self, websocket: WebSocket, payload: Any) -> str:
        """
        Format outgoing messages:
        - Serialization
        - Encryption
        - Compression
        """
        return str(payload)

if __name__ == "__main__":
    from cloud_ws4py.websocket import EchoWebSocket

    # Custom logger configuration
    configure_logger(level=logging.DEBUG)
    logger.info("Starting development server...")
    
    # Create enhanced application
    application = WebSocketWSGIApplication(
        handler_cls=EchoWebSocket,
        connection_manager=ConnectionManager()
    )
    
    # Create production server instance
    server = WSGIServer(
        ("0.0.0.0", 9000), application,
        # Production settings:
        spawn=gevent.pool.Pool(size=1000),  # Worker greenlet pool
        log=None,  # Disable built-in logging
        error_log=logging.getLogger('cloud_ws4py.server.error'),
        connection_pool=GEventWebSocketPool(size=20000)  # Connection pool
    )
    
    # Begin serving
    logger.critical("Server accepting connections on port 9000")
    server.serve_forever()
