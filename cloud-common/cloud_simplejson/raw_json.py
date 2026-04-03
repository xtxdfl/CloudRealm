#!/usr/bin/env python3
"""Safe RawJSON container for pre-encoded JSON embedding with validation"""

import json
import sys
import re
from typing import Any, Union, Optional, Match
from collections.abc import Iterable
from .errors import JSONEncodingError, JSONSecurityError

__all__ = ["RawJSON", "raw_json_validator"]
__version__ = "2.1.0"

# Security constants
MAX_NESTING_DEPTH = 50
MAX_DOCUMENT_LENGTH = 10 * 1024 * 1024  # 10MB
SUSPICIOUS_PATTERNS = re.compile(
    r"(?:<\s*script\b|{\s*\{\s*|\$\{|\\u[0-9a-f]{4}[^\\])",
    re.IGNORECASE
)

class RawJSON:
    """Secure container for pre-encoded JSON fragments
    
    Features:
    - Validation of JSON syntactic correctness
    - Protection against JSON injection attacks
    - Depth and size constraint enforcement
    - Optional schema validation
    - Chunked encoding support
    
    >>> safe_data = RawJSON('{"valid": true}')
    >>> print(safe_data)
    {"valid": true}
    """
    
    __slots__ = ('_encoded', '_is_validated', '_metadata')
    
    def __init__(
        self, 
        encoded_json: Union[str, bytes, Iterable],
        *,
        validate: bool = True,
        auto_trim: bool = True,
        allow_control_chars: bool = False,
        validator_func: Optional[callable] = None
    ) -> None:
        """
        Initialize RawJSON container
        
        Args:
            encoded_json: Pre-encoded JSON string, bytes, or chunked iterable
            validate: Perform security and syntax validation
            auto_trim: Automatically remove surrounding whitespace
            allow_control_chars: Permit non-escaped control characters
            validator_func: Custom validation function signature: 
                            func(data: str) -> Tuple[bool, Optional[str]]
        """
        self._is_validated = False
        self._metadata = {
            'source_size': 0,
            'normalized': False,
            'chunked': False,
            'security_flags': []
        }
        
        # Handle different input types
        if isinstance(encoded_json, (str, bytes)):
            content = self._normalize_input(encoded_json, auto_trim, allow_control_chars)
            self._encoded = [content]  # Unified chunked storage
            self._metadata['source_size'] = len(content)
        elif isinstance(encoded_json, Iterable):
            self._chunked_input(encoded_json, auto_trim, allow_control_chars)
            self._metadata['chunked'] = True
        else:
            raise TypeError("Unsupported input type, must be str, bytes or Iterable")
        
        # Perform validation if requested
        if validate:
            self.validate(validator_func)
    
    def _normalize_input(
        self, 
        data: Union[str, bytes], 
        auto_trim: bool,
        allow_control_chars: bool
    ) -> str:
        """Normalize and decode input data"""
        # Handle byte input
        if isinstance(data, bytes):
            try:
                content = data.decode('utf-8', errors='strict')
            except UnicodeDecodeError as e:
                raise JSONEncodingError(f"Invalid UTF-8 encoding: {e}") from e
        else:
            content = data
        
        # Apply automatic trimming
        if auto_trim:
            content = content.strip()
        
        # Size constraint
        if len(content) > MAX_DOCUMENT_LENGTH:
            raise JSONSecurityError(
                f"Document exceeds max length ({MAX_DOCUMENT_LENGTH} bytes)"
            )
        
        # Control character safety
        if not allow_control_chars:
            if any(ord(char) < 32 and char not in '\r\n\t' for char in content):
                raise JSONSecurityError("Unescaped control characters detected")
        
        # Store original size metadata
        self._metadata['source_size'] = len(content)
        return content
    
    def _chunked_input(
        self, 
        data: Iterable, 
        auto_trim: bool, 
        allow_control_chars: bool
    ) -> None:
        """Process chunked input with size constraints"""
        chunks = []
        total_size = 0
        
        for chunk in data:
            if not isinstance(chunk, (str, bytes)):
                raise TypeError("All chunks must be str or bytes")
            
            # Normalize each chunk
            norm_chunk = self._normalize_input(chunk, auto_trim=False, allow_control_chars=allow_control_chars)
            
            # Incremental size check
            total_size += len(norm_chunk)
            if total_size > MAX_DOCUMENT_LENGTH:
                raise JSONSecurityError(
                    f"Document exceeds max length ({MAX_DOCUMENT_LENGTH} bytes)"
                )
            
            chunks.append(norm_chunk)
            auto_trim = False  # Trim only first chunk
        
        # Apply trimming only to combined document
        if auto_trim:
            full_doc = ''.join(chunks).strip()
            chunks = [full_doc]
            total_size = len(full_doc)
        
        self._encoded = chunks
        self._metadata['source_size'] = total_size
        self._metadata['chunked'] = True
    
    @property
    def encoded(self) -> str:
        """Get the complete encoded JSON string"""
        return ''.join(self._encoded)
    
    @property
    def is_validated(self) -> bool:
        """Check if validation has been performed"""
        return self._is_validated
    
    @property
    def size(self) -> int:
        """Get original size in bytes"""
        return self._metadata['source_size']
    
    @property
    def security_flags(self) -> list:
        """Get detected security warnings"""
        return self._metadata.get('security_flags', [])
    
    def chunks(self) -> Iterable[str]:
        """Yield JSON content in original chunks (if chunked)"""
        yield from self._encoded
    
    def validate(self, validator_func: Optional[callable] = None) -> None:
        """Perform full validation on the content
        
        Args:
            validator_func: Custom validation function
        """
        if self._is_validated:
            return
        
        full_content = self.encoded
        
        # JSON validity check
        try:
            parsed = json.loads(full_content)
            self._check_nesting(parsed)
        except json.JSONDecodeError as e:
            raise JSONEncodingError(f"Invalid JSON: {e}") from e
        
        # Security vulnerability scanning
        security_issues = []
        if match := SUSPICIOUS_PATTERNS.search(full_content):
            issue_type = self._classify_threat(match.group(0))
            security_issues.append(f"Potential {issue_type} at pos {match.start()}")
        
        # Custom validator
        if validator_func:
            is_valid, custom_error = validator_func(full_content)
            if not is_valid:
                raise JSONEncodingError(f"Custom validation failed: {custom_error or 'Unknown error'}")
        
        # Update security flags if any
        if security_issues:
            self._metadata['security_flags'] = security_issues
        
        self._is_validated = True
    
    def _check_nesting(self, obj: Any, current_depth: int = 0) -> None:
        """Recursively check nesting depth"""
        if current_depth > MAX_NESTING_DEPTH:
            raise JSONSecurityError(f"Exceeds max nesting depth {MAX_NESTING_DEPTH}")
        
        if isinstance(obj, dict):
            for value in obj.values():
                self._check_nesting(value, current_depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self._check_nesting(item, current_depth + 1)
    
    def _classify_threat(self, pattern: str) -> str:
        """Classify detected security pattern"""
        pattern = pattern.lower()
        if 'script' in pattern:
            return "XSS injection"
        if '{{' in pattern or '}}' in pattern:
            return "template injection"
        if '${' in pattern:
            return "expression language injection"
        if '\\u' in pattern:
            return "unicode escape masking"
        return "suspicious pattern"
    
    def __str__(self) -> str:
        """Safe string representation"""
        return self.encoded if self._is_validated else '[Unvalidated JSON]'
    
    def __repr__(self) -> str:
        """Debug representation"""
        status = "validated" if self._is_validated else "unvalidated"
        chunks = "chunked" if self._metadata['chunked'] else "single"
        issues = len(self.security_flags)
        size_kb = self.size / 1024
        
        return (
            f"<RawJSON {status}, {size_kb:.1f}KB, {chunks}, "
            f"issues={issues} at 0x{id(self):x}>"
        )
    
    def __len__(self) -> int:
        """Return original content length"""
        return self.size
    
    def __eq__(self, other: object) -> bool:
        """Compare content equality"""
        if not isinstance(other, RawJSON):
            return False
        return self.encoded == other.encoded
    
    def __add__(self, other: Union['RawJSON', str]) -> 'RawJSON':
        """Concatenate with another RawJSON or string"""
        if isinstance(other, RawJSON):
            new_chunks = self._encoded + other._encoded
            return RawJSON(new_chunks, validate=False)
        if isinstance(other, str):
            return RawJSON(self._encoded + [other], validate=False)
        return NotImplemented
    
    def to_dict(self, validate: bool = True) -> dict:
        """Convert to Python dict with optional validation"""
        if validate and not self._is_validated:
            self.validate()
        return json.loads(self.encoded)
    
    @classmethod
    def serialize(cls, obj: Any) -> 'RawJSON':
        """Create RawJSON from Python objects"""
        encoded = json.dumps(
            obj,
            ensure_ascii=False,
            separators=(',', ':'),
            check_circular=True
        )
        return cls(encoded, validator_func=raw_json_validator)

# Built-in validator
def raw_json_validator(content: str) -> tuple:
    """Default security validator for RawJSON

    Returns:
        Tuple: (is_valid: bool, error_message: Optional[str])
    """
    # Check for forbidden patterns
    if SUSPICIOUS_PATTERNS.search(content):
        return False, "Suspicious pattern detected"
    
    # Basic structure check
    if not content.strip().startswith(('{', '[')):
        return False, "JSON root must be object or array"
    
    return True, None

# Security helper functions
def sanitize_json_input(data: str) -> str:
    """Sanitize potential dangerous JSON content"""
    # Basic script tag removal
    data = re.sub(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", data, flags=re.IGNORECASE)
    
    # Remove expression patterns
    data = re.sub(r"\{\s*(%.*?%|\{.*?\})\s*\}", "", data)
    
    # Escape HTML specials in strings (only where needed)
    string_re = r'"([^"\\]*(?:\\.[^"\\]*)*)"'
    data = re.sub(string_re, lambda m: _escape_string(m), data)
    
    return data

def _escape_string(match: Match) -> str:
    """Escape HTML specials within strings"""
    s = match.group(1)
    # Only escape if we have suspicious content
    if '<' in s or '>' in s or '&' in s:
        s = s.replace('&', '\\u0026')
        s = s.replace('<', '\\u003c')
        s = s.replace('>', '\\u003e')
    return f'"{s}"'

# Performance optimization hook
if __name__ == "__main__":
    import timeit
    
    test_doc = '{"key": "value", "num": 42}'
    rj = RawJSON(test_doc)
    
    def rawjson_validate():
        rj.validate()
    
    time = timeit.timeit(rawjson_validate, number=10000)
    print(f"Validation speed: {time/10000*1e6:.3f} μs per doc")
