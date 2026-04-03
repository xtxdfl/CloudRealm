#!/usr/bin/env python3
"""Production-ready WSGI server with enhanced WebSocket support for Python"""

import sys
import os
import time
import threading
import logging
import json
import signal
import uuid
import select
from collections import defaultdict
from itertools import chain
from wsgiref.handlers import SimpleHandler
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer as _WSGIServer
from wsgiref import util
from typing import Callable, Dict, List, Optional, Set, Tuple, Type, Any
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Patch hop-by-hop headers to allow WebSocket upgrade
util._hoppish = lambda x: False  # Allow all hop-by-hop headers for WebSocket

# Configure logging
logger = logging.getLogger("cloud_ws4py.server")
access_logger = logging.getLogger("cloud_ws4py.access")

# Metrics
METRICS_PORT = int(os.environ.get('WSGIREF_METRICS_PORT', '9100'))
SERVER_REQUESTS = Counter('wsgiref_http_requests', 'Total HTTP requests', ['method', 'status'])
WEBSOCKET_CONNECTIONS = Counter('wsgiref_websocket_handshakes', 'WebSocket handshakes', ['status'])
ACTIVE_CONNECTIONS = Gauge('wsgiref_active_connections', 'Current active WebSocket connections')
CONNECTION_DURATION = Histogram(
    'wsgiref_connection_duration', 
    'WebSocket connection duration',
    buckets=(0.1, 0.5, 1, 5, 15, 60, 300, 1800, 3600, '+Inf')
)
MESSAGE_TRAFFIC = Counter(
    'wsgiref_message_traffic',
    'Message traffic',
    ['direction', 'type']
)

class EnhancedSimpleHandler(SimpleHandler):
    """
    Advanced WSGI handler with:
    - Connection metadata tracking
    - Real socket extraction
    - Robust error handling
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_id = None
        self.start_time = time.time()
        self.status_code = None
    
    def get_connection_socket(self) -> Any:
        """Extract the raw socket from WSGI input stream"""
        # Multiple fallback strategies
        try:
            return self.environ['ws4py.socket'] = get_connection(self.environ["wsgi.input"])
        except Exception as e:
            # Try alternative access patterns
            if hasattr(self.rfile, '_sock'):
                return self.rfile._sock
            elif hasattr(self.rfile, 'raw') and hasattr(self.rfile.raw, '_sock'):
                return self.rfile.raw._sock
            elif hasattr(self, 'connection') and hasattr(self.connection, 'sock'):
                return self.connection.sock
            raise RuntimeError(f"Could not extract socket: {str(e)}")
    
    def setup_environ(self):
        """Configure environment with enhanced metadata"""
        # First call base implementation
        super().setup_environ()
        
        # Generate unique connection ID
        self.connection_id = f"conn-{self.environ['REMOTE_ADDR']}-{uuid.uuid4().hex[:8]}"
        self.environ['wsgi.connection_id'] = self.connection_id
        
        # Extract and track socket
        self.environ['ws4py.socket'] = self.get_connection_socket()
        
        # Extract HTTP version
        self.http_version = self.environ["SERVER_PROTOCOL"].rsplit("/")[-1]
        
        # Request metadata
        self.environ['wsgi.request_start'] = self.start_time
        self.environ['wsgi.request_path'] = self.environ['PATH_INFO']
    
    def log_request(self, status: str, size: int) -> None:
        """Enhanced request logging with metrics"""
        method = self.environ.get('REQUEST_METHOD', '')
        path = self.environ['wsgi.request_path']
        duration = time.time() - self.start_time
        status_code = int(status.split(' ')[0])
        
        # Record access log
        client_ip = self.environ.get('REMOTE_ADDR', 'unknown')
        access_logger.info(
            f"{method} {path} {status_code} {duration:.4f}s - {client_ip}"
        )
        
        # Record metrics
        SERVER_REQUESTS.labels(method, str(status_code)).inc()
        
        super().log_request(status, size)
    
    def finish_response(self):
        """Finalize response with WebSocket connection handling"""
        try:
            # Force evaluation of WSGI application result
            content, self.result = self.collect_result()
            
            # Handle WebSocket upgrade
            ws = self.handle_websocket_upgrade()
            
            # Log connection
            if ws:
                self.log_websocket_creation(ws)
                
            # Standard HTTP response
            return super().finish_response()
        except Exception as e:
            logger.exception("Response handling failed")
            if ws:
                ws.close(1011, reason="Internal server error")
            raise
        finally:
            # Cleanup environment
            self.environ.pop("ws4py.socket", None)
            self.environ.pop("ws4py.websocket", None)
    
    def collect_result(self) -> Tuple[List, Any]:
        """Collect initial content chunks"""
        rest = iter(self.result)
        first = list(rest)
        return first, chain(first, rest)
    
    def handle_websocket_upgrade(self) -> Any:
        """Process WebSocket connection and link to server"""
        ws = self.environ.pop("ws4py.websocket", None)
        if ws:
            # Attach metadata
            ws.environ = self.environ.copy()
            ws.connection_id = self.connection_id
            
            # Register connection lifetime metrics
            ACTIVE_CONNECTIONS.inc()
            ws.created_at = self.start_time
            
            # Link to server manager
            try:
                self.request_handler.server.link_websocket_to_server(ws)
            except AttributeError:
                logger.error("WebSocket server not initialized")
                ws.close(1011, reason="Server configuration error")
                return None
            
            # Track connection metrics
            websocket_status = "upgraded"
            WEBSOCKET_CONNECTIONS.labels(websocket_status).inc()
        return ws
    
    def log_websocket_creation(self, ws) -> None:
        """Log successful WebSocket upgrade"""
        path = self.environ['wsgi.request_path']
        client_ip = self.environ['REMOTE_ADDR']
        logger.info(
            f"WS Handshake: {client_ip} {path} ({self.connection_id})"
        )

class WebSocketWSGIRequestHandler(WSGIRequestHandler):
    """Production-grade WebSocket request handler with security features"""
    
    # Custom protocol handler class
    ProtocolHandler = EnhancedSimpleHandler
    
    # Connection security settings
    MAX_REQUEST_LINE = 8192  # 8KB
    MAX_HEADERS = 100
    TIMEOUT = 30  # seconds
    
    def handle(self):
        """Handle request with timeout and size protections"""
        # Protect against slowloris attacks
        self.connection.settimeout(self.TIMEOUT)
        
        try:
            self.raw_requestline = self.rfile.readline(self.MAX_REQUEST_LINE)
            if not self.raw_requestline:
                return
                
            if not self.parse_request():
                return
                
            self.process_request()
        except socket.timeout:
            logger.warning(f"Timeout from {self.client_address}")
            self.close_connection = True
        except Exception as e:
            logger.exception(f"Request handling error: {str(e)}")
            self.send_error(500)
        finally:
            if not self.close_connection:
                try:
                    self.wfile.flush()
                except (socket.error, ConnectionResetError):
                    self.close_connection = True
    
    def process_request(self):
        """Execute request processing with custom handler"""
        handler = self.ProtocolHandler(
            self.rfile,
            self.wfile,
            self.get_stderr(),
            self.get_environ()
        )
        
        # Configure handler
        handler.request_handler = self
        handler.server = self.server
        handler.connection = self.connection
        
        # Run application logic
        handler.run(self.server.get_app())
    
    def get_environ(self) -> Dict:
        """Build WSGI environment with additional security headers"""
        environ = super().get_environ()
        
        # Add security headers to environment
        security_headers = {
            'HTTP_X_Frame_Options': 'DENY',
            'HTTP_X_Content_Type_Options': 'nosniff',
            'HTTP_Strict_Transport_Security': 'max-age=31536000; includeSubDomains',
            'HTTP_Content_Security_Policy': "default-src 'self'",
            'HTTP_Referrer_Policy': 'same-origin',
        }
        environ.update(security_headers)
        
        return environ
        
    def handle_timeout(self) -> None:
        """Custom timeout handling"""
        logger.warning(f"Timeout from {self.client_address}")
        self.close_connection = True

class WebSocketManager(threading.Thread):
    """Advanced WebSocket connection management with monitoring"""
    
    def __init__(self):
        super().__init__(daemon=True)
        self.connections = {}  # id -> websocket
        self.active = threading.Event()
        self.active.set()
        self.lock = threading.RLock()
        self.heartbeat_interval = 5  # seconds
        self.max_idle_time = 300  # seconds
        
        # Statistics
        self.added = 0
        self.removed = 0
        
    def run(self) -> None:
        """Background process for connection maintenance"""
        logger.info("WebSocket manager started")
        while self.active.is_set():
            try:
                self.perform_maintenance()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.exception(f"Manager error: {str(e)}")
    
    def add(self, websocket) -> None:
        """Register a new WebSocket connection"""
        with self.lock:
            self.connections[websocket.connection_id] = websocket
            self.added += 1
            ACTIVE_CONNECTIONS.inc()
            logger.debug(f"Added connection: {websocket.connection_id}")
    
    def remove(self, connection_id) -> None:
        """Unregister a closed connection"""
        with self.lock:
            if connection_id in self.connections:
                conn = self.connections.pop(connection_id)
                self.record_connection_stats(conn)
                self.removed += 1
                ACTIVE_CONNECTIONS.dec()
                logger.debug(f"Removed connection: {connection_id}")
    
    def record_connection_stats(self, websocket) -> None:
        """Track performance metrics for closed connection"""
        duration = time.time() - websocket.created_at
        CONNECTION_DURATION.observe(duration)
        
        if hasattr(websocket, 'stats'):
            MESSAGE_TRAFFIC.labels('in', 'binary').inc(websocket.stats.get('bytes_in', 0))
            MESSAGE_TRAFFIC.labels('out', 'binary').inc(websocket.stats.get('bytes_out', 0))
    
    def perform_maintenance(self) -> None:
        """Execute periodic maintenance tasks"""
        current_time = time.time()
        idle_connections = []
        
        with self.lock:
            # Identify idle connections
            for conn_id, websocket in list(self.connections.items()):
                if websocket.terminated:
                    self.remove(conn_id)
                    continue
                
                idle_time = current_time - websocket.last_active
                if idle_time > self.max_idle_time:
                    idle_connections.append(conn_id)
        
            # Cleanup
            for conn_id in idle_connections:
                if conn_id in self.connections:
                    websocket = self.connections[conn_id]
                    websocket.close(1001, "Idle timeout")
                    self.remove(conn_id)
        
        if idle_connections:
            logger.info(f"Closed {len(idle_connections)} idle connections")
    
    def close_all(self, code=1001, reason="Server shutdown") -> None:
        """Initiate graceful shutdown of all connections"""
        with self.lock:
            logger.warning(f"Initiating shutdown of {len(self.connections)} connections")
            
            # First send shutdown notification
            for websocket in self.connections.values():
                try:
                    if not websocket.terminated:
                        websocket.send(json.dumps({
                            "type": "server",
                            "event": "shutdown",
                            "reason": reason,
                            "timeout": 15
                        }))
                except Exception:
                    pass
            
            # Allow graceful client disconnection
            time.sleep(5)
            
            # Then force close remaining connections
            for websocket in self.connections.values():
                if not websocket.terminated:
                    websocket.close(code, reason)
    
    def statistics(self) -> Dict:
        """Retrieve management statistics"""
        return {
            "active": len(self.connections),
            "added": self.added,
            "removed": self.removed
        }
    
    def stop(self) -> None:
        """Stop management thread"""
        self.active.clear()
        self.close_all()
        self.join(timeout=10)
        logger.info("WebSocket manager stopped")

class WSGIServer(_WSGIServer):
    """
    Production WebSocket server with:
    - Graceful shutdown support
    - Enhanced connection management
    - Security features
    - Server metadata
    """
    
    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        app=None,
        bind_and_activate=True,
        worker_threads=4
    ):
        super().__init__(server_address, RequestHandlerClass, app, bind_and_activate)
        self.manager = None
        self.worker_threads = worker_threads
        self._active_requests = 0
        self._max_requests = 10000
        self._max_connections = 5000
        self._shutting_down = False
        
        # Configure server socket options
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, 'TCP_KEEPIDLE'):
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        if hasattr(socket, 'TCP_KEEPINTVL'):
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
        if hasattr(socket, 'TCP_KEEPCNT'):
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    
    def initialize_websockets_manager(self) -> None:
        """Start WebSocket management subsystem"""
        if self.manager:
            if self.manager.is_alive():
                return
                
        self.manager = WebSocketManager()
        self.manager.start()
        
        # Start metrics server if enabled
        if METRICS_PORT:
            threading.Thread(
                target=start_http_server,
                args=(METRICS_PORT,),
                daemon=True
            ).start()
            logger.info(f"Metrics server started on port {METRICS_PORT}")
    
    def link_websocket_to_server(self, websocket) -> None:
        """Integrate WebSocket connection with server management"""
        # Check if server is shutting down
        if self._shutting_down:
            websocket.close(1001, "Server shutting down")
            return
            
        # Apply connection limits
        with self.lock:
            if len(self.manager.connections) >= self._max_connections:
                websocket.close(1008, "Server connection limit reached")
                return
                
        # Link to manager
        self.manager.add(websocket)
    
    def serve_forever(self, poll_interval=0.5) -> None:
        """Enhanced serve_forever with graceful exit"""
        # Setup signal handlers for graceful shutdown
        self.install_signals()
        
        # Initialize manager
        self.initialize_websockets_manager()
        
        logger.info(
            f"WebSocket API active at {self.server_address[0]}:{self.server_address[1]}"
        )
        
        try:
            while not self._shutting_down:
                # Check thread health
                if not self.manager.is_alive():
                    logger.error("WebSocket manager died, restarting")
                    self.initialize_websockets_manager()
                
                # Continue serving
                super().serve_forever(poll_interval)
                
        except KeyboardInterrupt:
            logger.warning("Keyboard interrupt received")
        finally:
            self._shutting_down = True
            self.graceful_shutdown()
    
    def install_signals(self) -> None:
        """Register OS signal handlers"""
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGHUP, self.handle_reload_signal)
        signal.signal(signal.SIGUSR1, self.handle_dump_stats)
        
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT, self.handle_shutdown_signal)
    
    def handle_shutdown_signal(self, signum, frame) -> None:
        """Initiate graceful shutdown"""
        signame = signal.Signals(signum).name
        logger.critical(f"Received {signame}, initiating shutdown")
        self._shutting_down = True
        # Will break out of serve_forever loop
    
    def handle_reload_signal(self, signum, frame) -> None:
        """Reload application configuration"""
        logger.info("SIGHUP received, reloading config")
        # Implementation would reload application settings
    
    def handle_dump_stats(self, signum, frame) -> None:
        """Output server statistics"""
        stats = self.get_server_stats()
        stats_output = [
            "==== Server Statistics ====",
            f"Requests: {stats['requests']}",
            f"Active connections: {stats['active_connections']}",
            f"WebSocket handshakes: {stats['ws_handshakes']}",
            f"Total added: {stats['manager_added']}",
            f"Total removed: {stats['manager_removed']}",
            "========================"
        ]
        logger.info("\n".join(stats_output))
    
    def get_server_stats(self) -> Dict:
        """Compile server statistics"""
        mgr_stats = self.manager.statistics() if self.manager else {}
        return {
            "requests": SERVER_REQUESTS._value.get(),
            "active_connections": ACTIVE_CONNECTIONS._value.get(),
            "ws_handshakes": WEBSOCKET_CONNECTIONS._value.get(),
            "manager_added": mgr_stats.get("added", 0),
            "manager_removed": mgr_stats.get("removed", 0),
        }
    
    def graceful_shutdown(self) -> None:
        """Execute controlled shutdown sequence"""
        # Step 1: Stop accepting new connections
        self.server_close()
        
        # Step 2: Graceful shutdown of WebSocket manager
        if self.manager:
            self.manager.stop()
            logger.info("WebSocket manager stopped")
        
        # Step 3: Close all open connections
        logger.info("Shutdown complete")
    
    def process_request(self, request, client_address) -> None:
        """Track requests and enforce limits"""
        with self.lock:
            self._active_requests += 1
            if self._active_requests > self._max_requests:
                logger.debug(f"Max requests reached ({self._active_requests})")
        
        try:
            super().process_request(request, client_address)
        finally:
            with self.lock:
                self._active_requests -= 1
                if self._active_requests > self._max_requests * 0.9:
                    logger.warning(
                        f"High request concurrency: {self._active_requests}/{self._max_requests}"
                    )

def make_websocket_server(
    host: str = '',
    port: int = 8000,
    app: Callable = None,
    threaded: bool = True,
    worker_threads: int = 4,
    max_connections: int = 5000
) -> WSGIServer:
    """
    Factory function to create production-grade WSGI server
    
    :param host: Server host binding
    :param port: Server port
    :param app: WSGI application
    :param threaded: Use multi-threaded processing
    :param worker_threads: Number of request handler threads
    :param max_connections: Maximum WebSocket connections
    """
    # Configure server implementation
    server_class = WSGIServer
    handler_class = WebSocketWSGIRequestHandler
    
    # Create server instance
    server = server_class(
        (host, port),
        handler_class,
        app=app,
        worker_threads=worker_threads,
    )
    
    # Configure connection limits
    server._max_connections = max_connections
    
    # Enable threading if requested
    if threaded:
        import socketserver
        server = socketserver.ThreadingMixIn(server, num_threads=worker_threads)
    
    return server

if __name__ == "__main__":
    from cloud_ws4py import configure_logger
    from cloud_ws4py.websocket import EchoWebSocket
    from cloud_ws4py.server.wsgiutils import WebSocketWSGIApplication

    # Configure logging
    configure_logger(level=logging.INFO, filename='server.log')
    logger.info("Starting WebSocket test server")

    # Create application
    app = WebSocketWSGIApplication(handler_cls=EchoWebSocket)
    
    # Create production server
    server = make_websocket_server(
        host='0.0.0.0',
        port=9000,
        app=app,
        threaded=True,
        worker_threads=10,
        max_connections=10000
    )
    
    # Serve forever
    try:
        server.serve_forever()
    except (SystemExit, KeyboardInterrupt):
        logger.info("Server stopped by administrator")
    except Exception as e:
        logger.exception("Critical server failure")
    finally:
        try:
            server.graceful_shutdown()
        except:
            pass
    logger.info("Server shutdown complete")

