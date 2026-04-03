#!/usr/bin/env python3
"""High-performance WSGI WebSocket handler with enhanced security and flexibility"""

import base64
import logging
import sys
import os
import re
import json
import hashlib
import random
import uuid
from functools import lru_cache
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Set

import cryptography.fernet
from prometheus_client import Counter, Gauge, Histogram
from werkzeug.datastructures import Headers
from werkzeug.security import safe_str_cmp

logger = logging.getLogger("cloud_ws4py.wsgi")
debug_logger = logging.getLogger("cloud_ws4py.detail")

__all__ = [
    "WebSocketWSGIApplication",
    "ProtocolValidator",
    "ExtensionNegotiator",
    "SecurityPolicy",
    "ConnectionRegistry",
    "MetricsMiddleware",
    "encrypt_payload",
    "decrypt_payload"
]

# Constants
WS_VERSION = 13
WS_KEY = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
MAX_HEADER_SIZE = 8192  # 8KB
DEFAULT_MAX_PAYLOAD = 10 * 1024 * 1024  # 10MB

# Metrics
WS_HANDSHAKES = Counter('wsgi_websocket_handshakes', 'Completed WebSocket handshakes', ['origin', 'status'])
WS_HANDSHAKE_FAILURES = Counter('wsgi_websocket_handshake_failures', 'Failed WebSocket handshakes', ['reason'])
WS_CONNECTIONS_ACTIVE = Gauge('wsgi_websocket_active_connections', 'Current active WebSocket connections')
WS_MSG_RECEIVED = Counter('wsgi_websocket_messages_received', 'Messages received', ['type', 'path'])
WS_MSG_SENT = Counter('wsgi_websocket_messages_sent', 'Messages sent', ['type', 'path'])
WS_CONNECTION_DURATION = Histogram(
    'wsgi_websocket_connection_duration', 
    'Connection lifespan in seconds',
    buckets=(0.1, 0.5, 1, 5, 15, 60, 300, 1800, 3600, '+Inf')
)
WS_CLIENT_VERSIONS = Counter('wsgi_websocket_client_versions', 'Client protocol versions', ['version'])

@lru_cache(maxsize=128)
def generate_accept_header(key: str) -> str:
    """Optimized computation of Sec-WebSocket-Accept header"""
    digest = hashlib.sha1(key.encode('utf-8') + WS_KEY).digest()
    return base64.b64encode(digest).decode('utf-8')

def encrypt_payload(data: bytes, secret: bytes) -> bytes:
    """Encrypt WebSocket payload using Fernet symmetric encryption"""
    return cryptography.fernet.Fernet(secret).encrypt(data)

def decrypt_payload(data: bytes, secret: bytes) -> bytes:
    """Decrypt WebSocket payload"""
    return cryptography.fernet.Fernet(secret).decrypt(data)

def origin_matches(allowed_origin: str, request_origin: str) -> bool:
    """Validate origin with wildcard pattern support"""
    if allowed_origin == "*":
        return True
        
    if allowed_origin.startswith("*."):
        domain_suffix = allowed_origin[2:]
        return request_origin.endswith(domain_suffix) or request_origin == domain_suffix
        
    return safe_str_cmp(allowed_origin, request_origin)

def extract_cidr_ip(remote_addr: str) -> str:
    """Extract client IP from potentially proxied address"""
    # Handle X-Forwarded-For format: client, proxy1, proxy2
    if ',' in remote_addr:
        return remote_addr.split(',')[0].strip()
    return remote_addr

def is_compression_extension(ext: str) -> bool:
    """Identify common WebSocket compression extension patterns"""
    return any(
        ext.startswith(prefix) 
        for prefix in ('permessage-deflate', 'x-webkit-deflate-frame')
    )

class SecurityPolicy:
    """Configurable security policy for WebSocket connections"""
    
    def __init__(
        self, 
        allowed_origins: List[str] = None, 
        rate_limit: int = 100, 
        require_origin: bool = True,
        csrf_protection: bool = True
    ):
        self.allowed_origins = allowed_origins or []
        self.rate_limit = rate_limit  # Connections per minute per IP
        self.require_origin = require_origin
        self.csrf_protection = csrf_protection
        
        # Connection tracking for rate limiting
        self.connection_counter = defaultdict(int)
        self.lock = threading.Lock()
    
    def validate_origin(self, request_origin: Optional[str]) -> bool:
        """Ensure request origin matches allowed patterns"""
        # Allow CORS requests
        if not request_origin and not self.require_origin:
            return True
            
        if not request_origin and self.require_origin:
            debug_logger.debug("Origin required but missing")
            return False
            
        # Match against any allowed origin pattern
        for allowed_origin in self.allowed_origins:
            if origin_matches(allowed_origin, request_origin):
                return True
                
        debug_logger.debug(f"Origin mismatch: {request_origin}")
        return False
    
    def track_connection(self, client_ip: str) -> bool:
        """Enforce connection rate limiting"""
        ip = extract_cidr_ip(client_ip)
        
        with self.lock:
            current_count = self.connection_counter[ip]
            if current_count >= self.rate_limit:
                return False
                
            self.connection_counter[ip] = current_count + 1
            return True
    
    def decay_counters(self):
        """Periodically reset rate limiting counters"""
        with self.lock:
            for ip in list(self.connection_counter.keys()):
                self.connection_counter[ip] = max(0, self.connection_counter[ip] - self.rate_limit // 2)
                if self.connection_counter[ip] == 0:
                    del self.connection_counter[ip]
    
    def validate_csrf(self, environ: dict) -> bool:
        """Check CSRF tokens for POST-originated WebSocket connections"""
        if not self.csrf_protection:
            return True
            
        # Verify Origin header matches host
        if 'HTTP_ORIGIN' in environ:
            return origin_matches(environ['HTTP_HOST'], environ['HTTP_ORIGIN'])
            
        # Verify Referer header if Origin is missing
        if 'HTTP_REFERER' in environ:
            referer_host = environ['HTTP_REFERER'].split('/')[2]
            return safe_str_cmp(referer_host, environ['HTTP_HOST'])
            
        return False

class ProtocolValidator:
    """Advanced protocol negotiation with priority support"""
    
    def __init__(self, server_protocols: List[str], client_priority=False):
        self.server_protocols = server_protocols
        self.client_priority = client_priority
    
    def negotiate(self, client_protocols: str) -> str:
        """Select mutually supported protocol with priority consideration"""
        if not client_protocols or not self.server_protocols:
            return ""
            
        client_list = [p.strip() for p in client_protocols.split(',')]
        selected_protocol = ""
        
        # Client priority: prefer client's order
        if self.client_priority:
            for protocol in client_list:
                if protocol in self.server_protocols:
                    selected_protocol = protocol
                    break
        # Server priority: select first match in server's order
        else:
            for protocol in self.server_protocols:
                if protocol in client_list:
                    selected_protocol = protocol
                    break
        
        return selected_protocol

class ExtensionNegotiator:
    """Comprehensive WebSocket extension negotiation"""
    
    def __init__(self, server_extensions: List[str], prefer_compression=False):
        self.server_extensions = server_extensions
        self.prefer_compression = prefer_compression
    
    def negotiate(self, client_extensions: str) -> List[str]:
        """Select extensions based on available options and priorities"""
        if not client_extensions or not self.server_extensions:
            return []
            
        client_list = [e.strip() for e in client_extensions.split(',')]
        matched = []
        
        # Handle compression extensions separately
        compression_exts = [ext for ext in self.server_extensions if is_compression_extension(ext)]
        other_exts = [ext for ext in self.server_extensions if not is_compression_extension(ext)]
        
        # Negotiate compression first if preferred
        if self.prefer_compression:
            for ext in compression_exts:
                if ext in client_list:
                    matched.append(ext)
                    break
        
        # Always include other supported extensions
        for ext in other_exts:
            if ext in client_list:
                matched.append(ext)
        
        # Fallback to compression if not yet selected
        if self.prefer_compression and not any(is_compression_extension(ext) for ext in matched):
            for ext in compression_exts:
                if ext in client_list:
                    matched.append(ext)
                    break
        
        # Include parameters from client's request
        final_with_params = []
        for ext in matched:
            # Find matching extension in client list with parameters
            for client_ext in client_list:
                if client_ext.startswith(ext) and '=' in client_ext:
                    final_with_params.append(client_ext)
                    break
            else:
                final_with_params.append(ext)
                
        return final_with_params

class ConnectionRegistry:
    """Global connection tracking with distributed support"""
    
    connections = defaultdict(set)
    lock = threading.Lock()
    
    @classmethod
    def add_connection(cls, websocket) -> str:
        """Register connection with unique ID"""
        conn_id = cls._generate_id()
        path = websocket.environ.get('PATH_INFO', 'global')
        
        with cls.lock:
            cls.connections[path].add(websocket)
        
        return conn_id
    
    @classmethod
    def remove_connection(cls, websocket) -> None:
        """Unregister connection"""
        path = websocket.environ.get('PATH_INFO', 'global')
        with cls.lock:
            if path in cls.connections:
                try:
                    cls.connections[path].remove(websocket)
                except KeyError:
                    pass
                if not cls.connections[path]:
                    del cls.connections[path]
    
    @classmethod
    def broadcast(cls, message: Any, path: str = None, binary: bool = False) -> int:
        """Efficient message broadcasting to connection groups"""
        sent = 0
        targets = cls._select_targets(path)
        
        for websocket in targets:
            if websocket.terminated:
                continue
                
            try:
                if binary:
                    websocket.send_binary(message)
                else:
                    websocket.send(message)
                sent += 1
            except Exception as e:
                debug_logger.error(f"Broadcast error: {str(e)}")
        
        return sent
    
    @classmethod
    def get_stats(cls) -> dict:
        """Compile global connection statistics"""
        with cls.lock:
            return {
                "total_connections": sum(len(grp) for grp in cls.connections.values()),
                "by_path": {path: len(connections) for path, connections in cls.connections.items()}
            }
    
    @classmethod
    def _select_targets(cls, path: str = None) -> List:
        """Select connections based on path pattern"""
        if not path:
            # Return all active connections
            targets = []
            for group in cls.connections.values():
                targets.extend(group)
            return targets
            
        # Path matching with wildcard support
        if path.endswith('*'):
            path_prefix = path.rstrip('*')
            targets = []
            for p in list(cls.connections.keys()):
                if p.startswith(path_prefix):
                    targets.extend(cls.connections[p])
            return targets
            
        # Exact path match
        return list(cls.connections.get(path, []))
    
    @staticmethod
    def _generate_id() -> str:
        """Create efficient connection ID"""
        return f"conn-{uuid.uuid4().hex[:8]}"

class MetricsMiddleware:
    """Monitoring middleware for WSGI applications"""
    
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        # Pre-request metrics
        start_time = time.time()
        method = environ['REQUEST_METHOD']
        path = environ['PATH_INFO']
        
        def custom_start_response(status, headers, exc_info=None):
            # Track status metrics
            status_code = status.split(' ')[0]
            SERVER_REQUEST_COUNT.labels(method, status_code).inc()
            
            # Execute original start_response
            return start_response(status, headers, exc_info)
        
        # Process request
        response = self.app(environ, custom_start_response)
        
        # Post-request metrics
        duration = time.time() - start_time
        REQUEST_DURATION.labels(method, path).observe(duration)
        
        return response

class WebSocketWSGIApplication:
    """
    Advanced WSGI application for WebSocket handling with features:
    - Fine-grained security policies
    - Protocol and extension negotiation
    - Connection tracking and metrics
    - Payload encryption support
    """
    
    def __init__(
        self, 
        handler_cls: Type[WebSocket],
        origin_policy: SecurityPolicy = None,
        protocol_validator: ProtocolValidator = None,
        extension_negotiator: ExtensionNegotiator = None,
        max_payload_size: int = DEFAULT_MAX_PAYLOAD,
        encryption_key: bytes = None
    ):
        """
        Initialize WebSocket application with:
        
        :param handler_cls: WebSocket handler implementation
        :param origin_policy: Defines origin validation rules
        :param protocol_validator: Manages subprotocol negotiation
        :param extension_negotiator: Handles extensions
        :param max_payload_size: Maximum allowed message size (bytes)
        :param encryption_key: Optional payload encryption key
        """
        self.handler_cls = handler_cls
        self.origin_policy = origin_policy or SecurityPolicy()
        self.protocol_validator = protocol_validator
        self.extension_negotiator = extension_negotiator
        self.max_payload_size = max_payload_size
        
        # Set up payload encryption if configured
        self.encryption_key = encryption_key
        if self.encryption_key is None:
            secret = os.getenv('WS_PAYLOAD_SECRET')
            self.encryption_key = secret.encode() if secret else None
        
        # Initialize statistics reporting thread
        self.stats_thread = threading.Thread(
            target=self._report_stats, 
            daemon=True
        )
        self.stats_thread.start()
        
        debug_logger.info("WebSocket application initialized")
    
    def __call__(self, environ: dict, start_response: Callable) -> List[bytes]:
        """Process WSGI request with comprehensive WebSocket upgrade logic"""
        try:
            self._pre_handshake_check(environ)
            return self._handle_websocket(environ, start_response)
        except HandshakeError as e:
            debug_logger.warning(f"Handshake failed: {str(e)}")
            WS_HANDSHAKE_FAILURES.labels(reason=str(e)).inc()
            start_response('400 Bad Request', [('Content-Type', 'text/plain')])
            return [b"WebSocket handshake failed"]
        except Exception as e:
            logger.exception("Unexpected error during handshake")
            start_response('500 Internal Server Error', [])
            return [b"Internal Server Error"]
    
    def _handle_websocket(self, environ: dict, start_response: Callable) -> List[bytes]:
        """Execute WebSocket upgrade process"""
        # Extract request headers
        headers = self._extract_headers(environ)
        
        # Step 1: Validate core handshake requirements
        self._validate_method(environ)
        
        # Step 2: Enforce security policies
        origin = environ.get('HTTP_ORIGIN', '')
        if not self.origin_policy.validate_origin(origin):
            raise HandshakeError("Origin not allowed")
            
        remote_addr = environ.get('REMOTE_ADDR', 'unknown')
        if not self.origin_policy.track_connection(remote_addr):
            raise HandshakeError("Rate limit exceeded")
        
        # Step 3: Negotiate protocol version
        version = self._negotiate_version(headers)
        if not version:
            raise HandshakeError("Version negotiation failed")
            
        # Step 4: Generate accept key
        accept_value = generate_accept_header(headers['Sec-WebSocket-Key'])
        
        # Step 5: Negotiate protocols & extensions
        protocols_header = self._negotiate_protocols(headers)
        extensions_header = self._negotiate_extensions(headers)
        
        # Step 6: Build WebSocket handler
        websocket = self._create_handler(
            environ, 
            protocols=protocols_header.split(',') if protocols_header else [],
            extensions=extensions_header.split(',') if extensions_header else [],
        )
        
        WS_HANDSHAKES.labels(origin=origin, status='success').inc()
        WS_CLIENT_VERSIONS.labels(version=version).inc()
        
        # Step 7: Send upgrade response
        response_headers = [
            ('Upgrade', 'websocket'),
            ('Connection', 'Upgrade'),
            ('Sec-WebSocket-Version', str(version)),
        ]
        
        if accept_value:
            response_headers.append(('Sec-WebSocket-Accept', accept_value))
        if protocols_header:
            response_headers.append(('Sec-WebSocket-Protocol', protocols_header))
        if extensions_header:
            response_headers.append(('Sec-WebSocket-Extensions', extensions_header))
        
        # Add security headers
        response_headers.extend(self._security_headers(origin))
        
        start_response('101 Switching Protocols', response_headers)
        
        # Track connection lifetime
        self._register_connection(websocket)
        
        debug_logger.info(f"Handshake completed for {remote_addr}")
        return []
    
    def _pre_handshake_check(self, environ: dict) -> None:
        """Preliminary environment checks"""
        # Ensure we have the raw socket
        if "ws4py.socket" not in environ:
            raise RuntimeError("Missing raw socket in WSGI environment")
            
        # Check header size to prevent DoS attacks
        content_length = environ.get('CONTENT_LENGTH')
        if content_length and int(content_length) > MAX_HEADER_SIZE:
            raise HandshakeError("Headers exceed maximum size")
    
    def _extract_headers(self, environ: dict) -> Headers:
        """Convert WSGI environ into structured HTTP headers"""
        headers = Headers()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                headers.add(header_name, value)
        
        # WS-specific non-prefixed headers
        special_headers = [
            'Sec-WebSocket-Key',
            'Sec-WebSocket-Version',
            'Sec-WebSocket-Protocol',
            'Sec-WebSocket-Extensions'
        ]
        for sh in special_headers:
            if sh in environ:
                headers.add(sh, environ[sh])
        
        return headers
    
    def _validate_method(self, environ: dict) -> None:
        """Validate HTTP method"""
        if environ.get("REQUEST_METHOD") != "GET":
            raise HandshakeError("HTTP method must be GET")
    
    def _negotiate_version(self, headers: Headers) -> int:
        """Version negotiation with fallback"""
        # Parse version from client with compatibility
        version = headers.get('Sec-WebSocket-Version', '')
        if not version:
            return WS_VERSION  # Default to latest supported
            
        try:
            version = int(version)
        except ValueError:
            raise HandshakeError("Invalid websocket version format")
            
        # Current version support matrix
        SUPPORTED_VERSIONS = [8, 13]  # Hixie76 and RFC6455
        return version if version in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[-1]
    
    def _negotiate_protocols(self, headers: Headers) -> str:
        """Handle protocol negotiation if configured"""
        if not self.protocol_validator:
            return ''
        
        return self.protocol_validator.negotiate(
            headers.get('Sec-WebSocket-Protocol', '')
        )
    
    def _negotiate_extensions(self, headers: Headers) -> str:
        """Handle extension negotiation if configured"""
        if not self.extension_negotiator:
            return ''
            
        return ', '.join(
            self.extension_negotiator.negotiate(
                headers.get('Sec-WebSocket-Extensions', '')
            )
        )
    
    def _create_handler(
        self,
        environ: dict,
        protocols: List[str],
        extensions: List[str]
    ) -> WebSocket:
        """Instantiate and configure WebSocket handler"""
        # Setup environment for handler
        environ['ws4py.max_payload_size'] = self.max_payload_size
        if self.encryption_key:
            environ['ws4py.encryption_key'] = self.encryption_key
        
        # Create handler instance
        websocket = self.handler_cls(
            sock=environ["ws4py.socket"],
            protocols=protocols,
            extensions=extensions,
            environ=environ.copy(),
        )
        
        environ["ws4py.websocket"] = websocket
        return websocket
    
    def _register_connection(self, websocket: WebSocket) -> None:
        """Register connection for metrics and management"""
        conn_id = ConnectionRegistry.add_connection(websocket)
        websocket.environ['ws4py.connection_id'] = conn_id
        WS_CONNECTIONS_ACTIVE.inc()
        
        # Record connection metadata
        remote_addr = websocket.environ.get('REMOTE_ADDR', 'unknown')
        path = websocket.environ.get('PATH_INFO', '/')
        start_time = time.time()
        
        # Register cleanup callback
        orig_terminate = websocket.terminate
        
        def tracked_terminate(*args, **kwargs):
            # Call original termination
            orig_terminate(*args, **kwargs)
            
            # Update metrics
            duration = time.time() - start_time
            WS_CONNECTION_DURATION.observe(duration)
            WS_CONNECTIONS_ACTIVE.dec()
            
            # Remove from registry
            ConnectionRegistry.remove_connection(websocket)
            
            debug_logger.info(
                f"Connection terminated: {remote_addr} {path} "
                f"{duration:.2f}s"
            )
            
        websocket.terminate = tracked_terminate
    
    def _security_headers(self, origin: str) -> List[Tuple[str, str]]:
        """Add security-related headers to response"""
        return [
            ('X-Frame-Options', 'DENY'),
            ('Content-Security-Policy', f"default-src 'self'; connect-src {origin}"),
            ('Strict-Transport-Security', 'max-age=31536000; includeSubDomains'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Referrer-Policy', 'same-origin'),
            ('Feature-Policy', "geolocation 'none'; microphone 'none'; camera 'none'"),
        ]
    
    def _report_stats(self) -> None:
        """Periodically report connection statistics"""
        while True:
            stats = ConnectionRegistry.get_stats()
            logger.info(
                f"WebSocket Stats: {stats['total_connections']} connections, "
                f"{len(stats['by_path'])} paths"
            )
            for path, count in stats['by_path'].items():
                debug_logger.debug(f"  {path}: {count}")
            
            # Decay security counters
            self.origin_policy.decay_counters()
            
            time.sleep(30)

# Standalone metrics for WSGI
SERVER_REQUEST_COUNT = Counter(
    'websocket_http_requests',
    'Total HTTP requests handled',
    ['method', 'status']
)
REQUEST_DURATION = Histogram(
    'websocket_http_request_duration',
    'HTTP request processing duration',
    ['method', 'path']
)

# Example usage middleware
if __name__ == "__main__":
    from cloud_ws4py.websocket import EchoWebSocket
    
    # Security configuration
    security = SecurityPolicy(
        allowed_origins=["https://example.com", "*.example.net"],
        rate_limit=200
    )
    
    # Protocol support
    protocols = ProtocolValidator(
        server_protocols=["chat-v1", "file-transfer", "echo"],
        client_priority=True
    )
    
    # Compression support
    extensions = ExtensionNegotiator(
        server_extensions=[
            "permessage-deflate",
            "message-mask"  # Example custom extension
        ],
        prefer_compression=True
    )
    
    # Create application instance
    app = WebSocketWSGIApplication(
        handler_cls=EchoWebSocket,
        origin_policy=security,
        protocol_validator=protocols,
        extension_negotiator=extensions,
        max_payload_size=5 * 1024 * 1024,  # 5MB
    )
    
    # Wrap with metrics middleware
    metrics_app = MetricsMiddleware(app)
    
    # Simulate WSGI call
    class MockEnviron:
        def __init__(self):
            self._data = {
                'REQUEST_METHOD': 'GET',
                'PATH_INFO': '/chat',
                'SERVER_NAME': 'localhost',
                'SERVER_PORT': '8000',
                'ws4py.socket': MockSocket(),
                'HTTP_UPGRADE': 'websocket',
                'HTTP_CONNECTION': 'upgrade',
                'HTTP_SEC_WEBSOCKET_KEY': 'dGhlIHNhbXBsZSBub25jZQ==',
                'HTTP_SEC_WEBSOCKET_VERSION': '13',
                'HTTP_SEC_WEBSOCKET_PROTOCOL': 'chat-v1,not-supported',
                'HTTP_SEC_WEBSOCKET_EXTENSIONS': 'permessage-deflate',
                'HTTP_ORIGIN': 'https://app.example.com',
                'REMOTE_ADDR': '192.168.1.100'
            }
        
        def get(self, key, default=None):
            return self._data.get(key, default)
    
    # Mock WSGI call
    def start_response(status, headers):
        print(f"Status: {status}")
        for header, value in headers:
            print(f"{header}: {value}")
    
    response = metrics_app(MockEnviron(), start_response)
    print(f"Response: {response}")
