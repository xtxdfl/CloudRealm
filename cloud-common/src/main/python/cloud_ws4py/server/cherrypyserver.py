#!/usr/bin/env python3
"""Enhanced WebSocket integration for CherryPy with production-ready features"""

import base64
import hashlib
import logging
import os
import signal
import threading
import time
import json
import inspect
import uuid
import select
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import cherrypy
from cherrypy import Tool, process, HTTPError
from cherrypy.lib import httputil
from cheroot.server import HTTPConnection, HTTPRequest, KnownLengthRFile
from prometheus_client import start_http_server, Counter, Gauge, Histogram, REGISTRY

# Monkey-patch REGISTRY to avoid duplicate metrics
if "_is_patched" not in REGISTRY.__dict__:
    REGISTRY._is_patched = True
    import re
    for name in list(REGISTRY._collector_to_names.keys()):
        if not re.match(r'^process_', name):
            REGISTRY.unregister(name)
    del re

METRICS_PORT = int(os.environ.get('WS_METRICS_PORT', '9100'))
if METRICS_PORT and not os.path.exists('/.dockerenv'):
    start_http_server(METRICS_PORT)

# Metrics
WS_CONNECTIONS = Gauge('cherrypy_websocket_active_connections', 'Active WebSocket connections')
WS_MESSAGES_SENT = Counter('cherrypy_websocket_messages_sent_total', 'Total messages sent', ['type'])
WS_MESSAGES_RECEIVED = Counter('cherrypy_websocket_messages_received_total', 'Total messages received', ['type'])
WS_CONNECTION_DURATION = Histogram('cherrypy_websocket_connection_duration_seconds', 'Duration of WebSocket connections')
WS_HANDSHAKE_FAILURES = Counter('cherrypy_websocket_handshake_failures', 'Failed WebSocket handshakes')
SERVER_REQUEST_COUNT = Counter('cherrypy_http_requests_total', 'Total HTTP requests', ['method', 'status'])

# Constants
WS_VERSION = 13
WS_KEY = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_CONNECTIONS_PER_IP = 50
HEARTBEAT_TIMEOUT = 30  # seconds
GRACEFUL_SHUTDOWN_PERIOD = 15  # seconds

# Configure logging
logger = logging.getLogger("cloud_ws4py.cherrypy")

class ConnectionMetadata:
    """Metadata container for WebSocket connections"""
    __slots__ = (
        'created_at', 'last_activity', 'remote_addr', 'path', 
        'protocol', 'extensions', 'session_id'
    )
    
    def __init__(self, request: HTTPRequest):
        self.created_at = time.time()
        self.last_activity = time.time()
        self.remote_addr = request.remote.ip
        self.path = request.path_info
        self.protocol = ""
        self.extensions = []
        self.session_id = str(uuid.uuid4())
    
    def touch(self) -> None:
        self.last_activity = time.time()
    
    def set_handshake_details(self, protocol: str = "", extensions: List[str] = None) -> None:
        self.protocol = protocol
        self.extensions = extensions or []
    
    @property
    def duration(self) -> float:
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> float:
        return time.time() - self.last_activity

class WebSocketSecurityError(Exception):
    """Security-related WebSocket error"""
    code = 1008

class WebSocketTool(Tool):
    """Enhanced WebSocket upgrade tool with security and performance features"""
    
    def __init__(self):
        super().__init__("before_request_body", self.upgrade)
        self.connection_log = defaultdict(int)  # IP -> count
        self.blacklist = set()
    
    def _setup(self):
        conf = self._merged_args()
        hooks = cherrypy.serving.request.hooks
        p = conf.pop("priority", getattr(self.callable, "priority", self._priority))
        hooks.attach(self._point, self.callable, priority=p, **conf)
        hooks.attach("before_finalize", self.complete, priority=p)
        hooks.attach("on_end_request", self.start_handler, priority=70)
        hooks.attach("on_end_request", self.log_request, priority=100)
    
    def log_request(self) -> None:
        """Record HTTP request metrics"""
        request = cherrypy.serving.request
        method = request.method
        status = cherrypy.response.status.split(' ')[0]
        SERVER_REQUEST_COUNT.labels(method, status).inc()
    
    def upgrade(
        self, 
        protocols: Optional[List[str]] = None, 
        extensions: Optional[List[str]] = None, 
        version: int = WS_VERSION,
        handler_cls: Type = None,
        heartbeat_freq: float = None,
        max_payload_size: int = 10 * 1024 * 1024,
        require_origin: bool = True,
        allowed_origins: List[str] = None,
        subdomain_origin: bool = True
    ):
        """
        Performs WebSocket upgrade with enhanced security controls
        
        Parameters:
        - require_origin: Require valid Origin header
        - allowed_origins: List of permitted origin domains
        - subdomain_origin: Allow subdomains of allowed_origins
        - max_payload_size: Maximum data size (in bytes) for each message
        """
        self._validate_requirements(protocols, handler_cls)
        request = cherrypy.serving.request
        self._throttle_connections(request)
        self._validate_security_headers(request)
        
        response = cherrypy.serving.response
        response.stream = True
        response.headers["Content-Type"] = "text/plain"
        response.headers["Upgrade"] = "websocket"
        response.headers["Connection"] = "Upgrade"
        
        try:
            ws_location, ws_protocol, ws_extensions = self._process_handshake(
                request, protocols, extensions, version, require_origin, 
                allowed_origins, subdomain_origin
            )
            self._create_websocket_handler(
                request, response, ws_location, ws_protocol, ws_extensions, 
                handler_cls, heartbeat_freq, max_payload_size
            )
        except WebSocketSecurityError as e:
            response.status = "403 Forbidden"
            logger.warning(f"Security violation: {str(e)}")
            WS_HANDSHAKE_FAILURES.inc()
            raise HTTPError(403, str(e))
        except Exception as e:
            response.status = "400 Bad Request"
            logger.error(f"Handshake failed: {str(e)}")
            WS_HANDSHAKE_FAILURES.inc()
            raise HTTPError(400, str(e))
    
    def complete(self) -> None:
        """Prepare CherryPy internals for WebSocket integration"""
        request = cherrypy.serving.request
        if not hasattr(request, "ws_handler"):
            return
            
        # Set critical internal flags
        request.close_connection = True
        if hasattr(request, "conn") and request.conn:
            request.conn.linger = True
            
        # Skip response body processing
        cherrypy.response.body = [b'101 Switching Protocols']
    
    def start_handler(self) -> None:
        """Finalize WebSocket upgrade and initiate handler"""
        request = cherrypy.request
        if not hasattr(request, "ws_handler") or not request.ws_handler:
            return
            
        metadata = request.ws_metadata
        addr = (request.remote.ip, request.remote.port)
        
        # Register connection for management
        cherrypy.engine.publish("register-websocket", request.ws_handler)
        
        # Cleanup CherryPy references
        self._cleanup_request_resources(request)
        
        # Start metrics tracking
        WS_CONNECTIONS.inc()
        start_time = time.time()
        
        # Execute handler in managed thread
        cherrypy.engine.publish("handle-websocket", request.ws_handler, addr, metadata)
        
        # Update duration metrics
        WS_CONNECTION_DURATION.observe(time.time() - start_time)
        WS_CONNECTIONS.dec()
    
    def _validate_requirements(self, protocols: List[str], handler_cls: Type) -> None:
        """Ensure critical handshake parameters are available"""
        if not protocols or not handler_cls:
            raise ValueError("Missing required WebSocket configuration parameters")
    
    def _throttle_connections(self, request: HTTPRequest) -> None:
        """Enforce connection limits and IP-based throttling"""
        remote_ip = request.remote.ip
        
        # Check if IP is blacklisted
        if remote_ip in self.blacklist:
            raise WebSocketSecurityError(f"IP blocked: {remote_ip}")
            
        # Enforce connection limit
        current_connections = self.connection_log[remote_ip]
        if current_connections >= MAX_CONNECTIONS_PER_IP:
            raise WebSocketSecurityError(f"Connection limit reached for {remote_ip}")
            
        self.connection_log[remote_ip] += 1
    
    def _validate_security_headers(self, request: HTTPRequest) -> None:
        """Perform basic WebSocket handshake header validation"""
        if not any(h.lower() == "websocket" for h in request.headers.get('Upgrade', '').split(',')):
            raise HandshakeError("Missing or invalid Upgrade header")
            
        if "upgrade" not in request.headers.get('Connection', '').lower():
            raise HandshakeError("Missing or invalid Connection header")
    
    def _process_handshake(
        self,
        request: HTTPRequest,
        protocols: List[str],
        extensions: List[str],
        version: int,
        require_origin: bool,
        allowed_origins: List[str],
        subdomain_origin: bool
    ) -> Tuple[str, str, List[str]]:
        """Execute WebSocket handshake with security checks"""
        self._validate_origin(request, require_origin, allowed_origins, subdomain_origin)
        
        version_header = request.headers.get("Sec-WebSocket-Version")
        if not version_header or int(version_header) != version:
            raise HandshakeError(f"Unsupported WebSocket version: {version_header}")
        
        key = request.headers.get("Sec-WebSocket-Key")
        if not key:
            raise HandshakeError("Missing Sec-WebSocket-Key header")
        
        ws_protocol = self._select_protocol(request.headers.get("Sec-WebSocket-Protocol"), protocols)
        ws_extensions = self._select_extensions(request.headers.get("Sec-WebSocket-Extensions", ""), extensions)
        
        # Build WebSocket location URL
        ws_location = self._build_location_url(request)
        
        # Set required response headers
        cherrypy.response.headers["Sec-WebSocket-Accept"] = base64.b64encode(
            hashlib.sha1(key.encode('utf-8') + WS_KEY).digest()
        ).decode('utf-8')
        
        if ws_protocol:
            cherrypy.response.headers["Sec-WebSocket-Protocol"] = ws_protocol
        
        if ws_extensions:
            cherrypy.response.headers["Sec-WebSocket-Extensions"] = ", ".join(ws_extensions)
        
        return ws_location, ws_protocol, ws_extensions
    
    def _validate_origin(
        self,
        request: HTTPRequest,
        require_origin: bool,
        allowed_origins: List[str],
        allow_subdomains: bool
    ) -> None:
        """Implement strict origin validation"""
        origin = request.headers.get('Origin', '')
        
        if not origin and require_origin:
            raise WebSocketSecurityError("Origin header is required")
        
        if allowed_origins:
            origin_host = httputil.urlsplit(origin).netloc.split(':')[0]
            
            if allow_subdomains:
                if not any(origin_host.endswith('.' + domain) or origin_host == domain 
                          for domain in allowed_origins):
                    raise WebSocketSecurityError(f"Origin '{origin_host}' not allowed")
            elif origin_host not in allowed_origins:
                raise WebSocketSecurityError(f"Origin '{origin_host}' not permitted")
    
    def _select_protocol(self, client_protocol_str: str, server_protocols: List[str]) -> str:
        """Negotiate WebSocket subprotocol with client"""
        if not client_protocol_str:
            return ""
            
        client_protocols = [p.strip() for p in client_protocol_str.split(',')]
        for client_protocol in client_protocols:
            if client_protocol in server_protocols:
                return client_protocol
                
        raise HandshakeError("No matching subprotocol found")
    
    def _select_extensions(self, client_extensions: str, server_extensions: List[str]) -> List[str]:
        """Negotiate WebSocket extensions"""
        if not client_extensions or not server_extensions:
            return []
            
        return list(set(client_extensions.split(',')).intersection(server_extensions))
    
    def _build_location_url(self, request: HTTPRequest) -> str:
        """Construct WebSocket location URL"""
        scheme = 'wss' if request.scheme == 'https' else 'ws'
        port = f":{request.local.port}" if request.local.port != (443 if scheme == 'wss' else 80) else ""
        query = f"?{request.query_string}" if request.query_string else ""
        return f"{scheme}://{request.local.name}{port}{request.path_info}{query}"
    
    def _create_websocket_handler(
        self,
        request: HTTPRequest,
        response,
        location: str,
        protocol: str,
        extensions: List[str],
        handler_class: Type,
        heartbeat_freq: float,
        max_payload_size: int
    ) -> None:
        """Create WebSocket handler and attach to request"""
        request.ws_metadata = ConnectionMetadata(request)
        request.ws_metadata.set_handshake_details(protocol, extensions)
        
        rfile = request.rfile
        if hasattr(rfile, 'rfile') and isinstance(rfile.rfile, KnownLengthRFile):
            rfile = rfile.rfile
            
        try:
            # Transfer socket ownership to WebSocket handler
            ws_socket = self._extract_raw_socket(rfile)
            request.ws_handler = handler_class(
                sock=ws_socket,
                protocols=[protocol] if protocol else None,
                extensions=extensions,
                environ=request.wsgi_environ.copy(),
                heartbeat_freq=heartbeat_freq,
                max_payload_size=max_payload_size,
                connection_metadata=request.ws_metadata
            )
        except Exception as e:
            logger.exception("WebSocket handler creation failed")
            raise RuntimeError(f"Handler initialization error: {str(e)}")
    
    def _extract_raw_socket(self, rfile) -> Any:
        """Extract raw socket from CherryPy request object"""
        if hasattr(rfile, '_sock'):
            return rfile._sock
        elif hasattr(rfile, 'rfile') and hasattr(rfile.rfile, '_sock'):
            return rfile.rfile._sock
        elif hasattr(rfile, 'raw') and hasattr(rfile.raw, '_sock'):
            return rfile.raw._sock
        raise RuntimeError("Cannot extract socket from request stream")
    
    def _cleanup_request_resources(self, request) -> None:
        """Release CherryPy resources for WebSocket connections"""
        # Prevent CherryPy from closing the socket
        if hasattr(request, 'conn'):
            del request.conn
        if hasattr(request, 'rfile'):
            del request.rfile
        if hasattr(request, 'close'):
            request.close = lambda: None

class WebSocketManager:
    """Advanced connection manager with health monitoring and clustering support"""
    
    def __init__(self):
        self.connections = {}
        self.by_origin = defaultdict(list)
        self.by_path = defaultdict(list)
        self.by_session = {}
        self.running = False
        self.lock = threading.RLock()
        
        # Health monitoring
        self.heartbeat_thread = None
        self.broadcast_queue = Queue()
        self.cluster = None  # Placeholder for distributed messaging
        
        # Cluster configuration
        self.distributed = False
        self.broadcast_topic = "websocket_broadcast"
    
    def start(self) -> None:
        """Start monitoring services"""
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._monitor_connections)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        self.broadcast_thread = threading.Thread(target=self._process_broadcasts)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()
        
        if self.distributed:
            self._initialize_cluster()
    
    def stop(self) -> None:
        """Cleanly shut down manager"""
        self.running = False
        self.close_all()
        
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
            
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=5)
            
        if self.distributed:
            self._shutdown_cluster()
    
    def add(self, handler) -> None:
        """Register a new WebSocket handler"""
        if not handler.connection_metadata:
            logger.error("Connection metadata missing")
            return
            
        meta = handler.connection_metadata
        session_id = meta.session_id
        
        with self.lock:
            self.connections[handler] = meta
            self.by_origin[meta.remote_addr].append(handler)
            self.by_path[meta.path].append(handler)
            self.by_session[session_id] = handler
            
        logger.info(f"New connection: {meta.remote_addr} {meta.path} {session_id}")
    
    def remove(self, handler) -> None:
        """Unregister a closed connection"""
        if handler not in self.connections:
            return
            
        meta = self.connections[handler]
        session_id = meta.session_id
        
        with self.lock:
            if handler in self.connections:
                del self.connections[handler]
                
            self.by_origin[meta.remote_addr].remove(handler)
            if not self.by_origin[meta.remote_addr]:
                del self.by_origin[meta.remote_addr]
                
            self.by_path[meta.path].remove(handler)
            if not self.by_path[meta.path]:
                del self.by_path[meta.path]
                
            if session_id in self.by_session:
                del self.by_session[session_id]
        
        logger.info(f"Connection closed: {meta.remote_addr} {meta.path} {session_id}")
    
    def send_to_session(self, session_id: str, message: Any, binary: bool = False) -> bool:
        """Send message to a specific session"""
        with self.lock:
            handler = self.by_session.get(session_id)
            if not handler:
                return False
                
            if handler.terminated:
                return False
                
            try:
                if binary:
                    handler.send_binary(message)
                else:
                    handler.send(message)
                return True
            except Exception:
                return False
    
    def broadcast(self, message: Any, path: str = None, binary: bool = False) -> int:
        """Distribute message across connections"""
        if self.distributed:
            # Distribute broadcast to cluster
            self.cluster.publish(self.broadcast_topic, json.dumps({
                "message": message,
                "path": path,
                "binary": binary
            }))
            return
        
        # Local broadcast
        sent = 0
        with self.lock:
            targets = (
                self.connections.keys() 
                if not path 
                else [h for h in self.by_path.get(path, [])]
            )
            for handler in targets:
                if handler.terminated:
                    continue
                    
                try:
                    if binary:
                        handler.send_binary(message)
                    else:
                        handler.send(message)
                    sent += 1
                except Exception as e:
                    logger.warning(f"Broadcast error: {str(e)}")
                    continue
        
        return sent
    
    def close_session(self, session_id: str, code: int = 1000, reason: str = "") -> bool:
        """Close specific connection with status"""
        with self.lock:
            handler = self.by_session.get(session_id)
            if not handler:
                return False
                
            if handler.client_terminated:
                return False
                
            try:
                handler.close(code, reason)
                return True
            except Exception:
                return False
    
    def terminate_idle(self, max_idle: int = HEARTBEAT_TIMEOUT) -> int:
        """Close connections exceeding idle threshold"""
        terminated = 0
        current_time = time.time()
        
        with self.lock:
            for handler in list(self.connections.keys()):
                if handler.terminated:
                    continue
                    
                meta = self.connections[handler]
                if (current_time - meta.last_activity) > max_idle:
                    try:
                        handler.close(1000, "Idle timeout")
                        terminated += 1
                    except Exception:
                        pass
        
        return terminated
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Compile connection statistics"""
        stats = {
            "total": len(self.connections),
            "by_origin": defaultdict(int),
            "by_path": defaultdict(int),
            "sessions": list(self.by_session.keys())
        }
        
        with self.lock:
            for meta in self.connections.values():
                stats["by_origin"][meta.remote_addr] += 1
                stats["by_path"][meta.path] += 1
        
        return stats
    
    def _monitor_connections(self) -> None:
        """Background health monitoring service"""
        while self.running:
            try:
                # Terminate idle connections
                terminated = self.terminate_idle()
                if terminated:
                    logger.info(f"Terminated {terminated} idle connections")
                
                # Validate active connections
                self._validate_heartbeats()
                
                # Update cluster state
                if self.distributed:
                    self._sync_cluster_state()
            except Exception as e:
                logger.error(f"Monitor error: {str(e)}")
            finally:
                time.sleep(5)
    
    def _validate_heartbeats(self) -> None:
        """Ensure clients are responsive"""
        with self.lock:
            for handler in list(self.connections.keys()):
                if handler.terminated:
                    continue
                    
                try:
                    if hasattr(handler, "manager_heartbeat"):
                        handler.manager_heartbeat()
                except Exception as e:
                    logger.warning(f"Heartbeat failed for connection: {str(e)}")
    
    def _process_broadcasts(self) -> None:
        """Handle queued broadcast messages"""
        while self.running:
            try:
                messages = self.broadcast_queue.get(timeout=1.0)
                for path, message, binary in messages:
                    self.broadcast(message, path, binary)
            except Empty:
                pass
            except Exception as e:
                logger.error(f"Broadcast processor error: {str(e)}")
    
    def _initialize_cluster(self) -> None:
        """Connect to distributed messaging system (example)"""
        # Production implementation would use Redis PubSub, Kafka, etc.
        logger.info("Initializing cluster communication")
        self.cluster = ClusterAdapter()
        self.cluster.subscribe(self.broadcast_topic, self._cluster_broadcast)
    
    def _shutdown_cluster(self) -> None:
        logger.info("Shutting down cluster links")
        if self.cluster:
            self.cluster.unsubscribe(self.broadcast_topic)
    
    def _sync_cluster_state(self) -> None:
        """Synchronize state across cluster nodes"""
        pass  # Production implementation would broadcast state
    
    def _cluster_broadcast(self, message: Dict) -> None:
        """Handle broadcast received from cluster"""
        try:
            data = json.loads(message)
            self.broadcast_queue.put([
                (data.get("path"), data["message"], data.get("binary", False))
            ])
        except Exception as e:
            logger.error(f"Invalid cluster message: {str(e)}")

class WebSocketPlugin(process.plugins.SimplePlugin):
    """Production-grade WebSocket management plugin for CherryPy"""
    
    def __init__(self, bus, manager: Optional[WebSocketManager] = None):
        super().__init__(bus)
        self.manager = manager or WebSocketManager()
        self.signals_set = False
        self.app_shutdown = False
    
    def start(self) -> None:
        """Initialize plugin services"""
        self.bus.log("Starting WebSocket engine")
        self.bus.subscribe("register-websocket", self.add)
        self.bus.subscribe("handle-websocket", self.handle)
        self.bus.subscribe("stop", self.stop_all)
        self.manager.start()
        self._register_signals()
    
    def stop(self) -> None:
        """Cleanup plugin resources"""
        self.bus.log("Stopping WebSocket engine")
        self.bus.unsubscribe("register-websocket", self.add)
        self.bus.unsubscribe("handle-websocket", self.handle)
        self.bus.unsubscribe("stop", self.stop_all)
        self.manager.stop()
        self._deregister_signals()
    
    def add(self, handler) -> None:
        """Register new connection"""
        self.manager.add(handler)
    
    def handle(self, handler, addr, metadata) -> None:
        """Execute WebSocket handler with monitoring"""
        try:
            # Initiate connection lifetime
            start_time = time.time()
            WS_CONNECTION_DURATION.observe(time.time() - start_time)
            
            # Start metrics tracking thread
            monitor_thread = threading.Thread(
                target=self._monitor_connection,
                args=(handler,),
                daemon=True
            )
            monitor_thread.start()
            
            # Run main handler logic
            handler.run()
        finally:
            # Cleanup tracking
            self.manager.remove(handler)
            WS_CONNECTION_DURATION.observe(time.time() - start_time)
    
    def stop_all(self) -> None:
        """Initiates graceful shutdown procedure"""
        if self.app_shutdown:
            return
            
        self.app_shutdown = True
        self.bus.log("Graceful shutdown initiated")
        
        # Notify clients before termination
        self._broadcast_shutdown_notice()
        
        # Close connection tracker
        self.manager.stop()
        
        # Force terminate any remaining connections
        self.manager.close_all()
        self.bus.log("All connections terminated")
    
    def get_stats(self) -> Dict:
        """Retrieve connection statistics"""
        return self.manager.get_connection_stats()
    
    def _monitor_connection(self, handler) -> None:
        """Background monitoring for connection health"""
        while not self.app_shutdown and not handler.terminated:
            try:
                if hasattr(handler, "connection_metadata"):
                    handler.connection_metadata.touch()
                
                gevent.sleep(0.5)
                
                # Perform sanity check
                if handler and handler.sock and not isinstance(handler, WebSocket):
                    # Check if socket is still alive
                    r, _, _ = select.select([handler.sock], [], [], 0.1)
                    if not r:
                        # Socket looks dead - attempt to close cleanly
                        handler.close(1002, "Connection lost")
                        return
            except Exception as e:
                logger.debug(f"Monitor exception: {str(e)}")
                break
    
    def _broadcast_shutdown_notice(self) -> None:
        """Notify all clients about imminent shutdown"""
        self.manager.broadcast(json.dumps({
            "type": "system",
            "event": "shutdown",
            "reason": "Server maintenance",
            "timeout": GRACEFUL_SHUTDOWN_PERIOD
        }))
        
        # Wait for clients to disconnect voluntarily
        gevent.sleep(GRACEFUL_SHUTDOWN_PERIOD)
    
    def _register_signals(self) -> None:
        """Setup OS signal handlers for management"""
        if self.signals_set:
            return
            
        try:
            import signal
            signal.signal(signal.SIGUSR1, self._handle_stats_signal)
            signal.signal(signal.SIGUSR2, self._handle_maintenance_signal)
            self.signals_set = True
        except Exception:
            pass
    
    def _deregister_signals(self) -> None:
        """Clear signal handlers"""
        if not self.signals_set:
            return
            
        import signal
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)
        signal.signal(signal.SIGUSR2, signal.SIG_DFL)
        self.signals_set = False
    
    def _handle_stats_signal(self, signum, frame) -> None:
        """Output cluster statistics"""
        stats = self.manager.get_connection_stats()
        stats_output = [
            f"==== WebSocket Statistics ====",
            f"Active Connections: {stats['total']}",
            f"By Origin:",
        ] + [f"  {ip}: {count}" for ip, count in stats['by_origin'].items()] + [
            f"By Path:",
        ] + [f"  {path}: {count}" for path, count in stats['by_path'].items()] + [
            f"Session IDs: {len(stats['sessions'])}",
            f"============================="
        ]
        logger.info("\n".join(stats_output))
    
    def _handle_maintenance_signal(self, signum, frame) -> None:
        """Trigger maintenance routines"""
        logger.info("Running maintenance routines")
        # Termination logic would go here
        # Example: self.manager.terminate_idle(300)

class ClusterAdapter:
    """Basic mock cluster adapter for demonstration"""
    def subscribe(self, topic, callback):
        logger.info(f"Subscribing to cluster topic: {topic}")
    
    def unsubscribe(self, topic):
        logger.info(f"Unsubscribing from cluster topic: {topic}")
    
    def publish(self, topic, message):
        logger.debug(f"Publishing to cluster: {topic}")

class SmartEchoHandler(WebSocket):
    """Enhanced echo handler with rate limiting"""
    
    RATE_LIMIT = 10  # messages per second
    MAX_CONNECTION_DURATION = 300  # seconds
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_count = 0
        self.last_reset = time.time()
        self.stats = {
            "messages_received": 0,
            "bytes_received": 0,
            "start_time": time.time()
        }
    
    def received_message(self, message):
        """Handle incoming messages with rate limiting"""
        WS_MESSAGES_RECEIVED.labels('echo').inc()
        current_time = time.time()
        
        # Reset counter after 1 second
        if current_time - self.last_reset > 1:
            self.message_count = 0
            self.last_reset = current_time
        
        # Enforce rate limit
        self.message_count += 1
        if self.message_count > self.RATE_LIMIT:
            self.close(1008, "Rate limit exceeded")
            return
            
        # Update statistics
        self.stats["messages_received"] += 1
        self.stats["bytes_received"] += len(str(message))
        
        # Terminate if connection exceeds max duration
        elapsed = current_time - self.stats["start_time"]
        if elapsed > self.MAX_CONNECTION_DURATION:
            self.close(1000, "Connection duration limit reached")
            return
            
        # Echo message with timestamp
        response = f"[{current_time:.3f}] {message.data}"
        self.send(response)
        WS_MESSAGES_SENT.labels('echo').inc()

if __name__ == "__main__":
    import sys
    import atexit
    
    # Configuration
    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": 9000,
        "environment": "production",
        "log.access_file": "",
        "log.error_file": "server_errors.log"
    })
    
    # Setup enhanced WebSocket ecosystem
    manager = WebSocketManager()
    plugin = WebSocketPlugin(cherrypy.engine, manager)
    plugin.subscribe()
    
    cherrypy.tools.websocket = Tool("before_request_body", WebSocketTool().upgrade)
    
    # Graceful shutdown handler
    def graceful_shutdown():
        logger.critical("Shutdown signal received")
        plugin.stop_all()
    
    atexit.register(graceful_shutdown)
    signal.signal(signal.SIGTERM, lambda *_: graceful_shutdown())
    signal.signal(signal.SIGINT, lambda *_: graceful_shutdown())
    
    # WebSocket application
    class Root:
        @cherrypy.expose
        @cherrypy.tools.websocket(
            protocols=["chat", "echo"],
            extensions=["permessage-deflate"],
            handler_cls=SmartEchoHandler,
            require_origin=True,
            allowed_origins=["localhost"],
            max_payload_size=1000000
        )
        def ws(self):
            """WebSocket endpoint"""
            return "WebSocket endpoint"
    
    # Start service
    cherrypy.quickstart(Root())
    logger.info("Service terminated")
