#!/usr/bin/env python3
"""Optimized JSON token scanner with enhanced performance and error handling"""

import re
from typing import Tuple, Callable, Any, Dict, Optional
from .errors import JSONDecodeError, JSONScannerError, JSONMaxDepthError

# Speedup mechanism with better error handling
def _import_c_make_scanner():
    try:
        from . import c_extension
        _speedups = c_extensions.get()
        return getattr(_speedups, "make_scanner", None)
    except (ImportError, AttributeError) as e:
        # Explicitly log fallback for troubleshooting
        import logging
        logging.debug("C extension scanner not available: %s", str(e))
        return None

# Compile regexes only once at module level
NUMBER_RE = re.compile(
    r"""
    -?           # Optional minus sign
    (?:0|[1-9]\d*)          # Integer part
    (?:\.\d+)?             # Optional fractional part
    (?:[eE][-+]?\d+)?      # Optional exponent
    """,
    re.VERBOSE | re.X
)
KEYWORD_TOKENS = {
    "null": None,
    "true": True,
    "false": False,
    "NaN": lambda c: c.parse_constant("NaN"),
    "Infinity": lambda c: c.parse_constant("Infinity"),
    "-Infinity": lambda c: c.parse_constant("-Infinity")
}
MAX_TOKEN_LEN = max(len(k) for k in KEYWORD_TOKENS)

__all__ = ["make_scanner", "JSONDecodeError", "JSONScannerError"]

def py_make_scanner(context: Any) -> Callable[[str, int], Tuple[Any, int]]:
    """
    Create a JSON token scanner function optimized for performance
    
    Args:
        context: Parser context containing parse methods and config
    
    Returns:
        Function that takes (string, index) and returns (parsed_value, new_index)
    """
    parse_object = context.parse_object
    parse_array = context.parse_array
    parse_string = context.parse_string
    parse_float = context.parse_float
    parse_int = context.parse_int
    parse_constant = context.parse_constant
    strict = context.strict
    memo = context.memo
    max_scan_depth = getattr(context, "max_scan_depth", 1000)
    
    # Stack depth counter to prevent Stack Overflow on deep structures
    scan_depth = [0]
    
    def _scan_once(string: str, idx: int) -> Tuple[Any, int]:
        """Scan next JSON token starting at given index"""
        if scan_depth[0] > max_scan_depth:
            raise JSONMaxDepthError(f"Maximum scan depth ({max_scan_depth}) exceeded", 
                                    string, idx)
                                    
        scan_depth[0] += 1
        try:
            try:
                nextchar = string[idx]
            except IndexError:
                raise JSONDecodeError("Unexpected end of input", string, idx)

            # 1. String parsing (most common after object keys)
            if nextchar == '"':
                return parse_string(string, idx + 1, strict=strict)
            
            # 2. Object parsing
            elif nextchar == '{':
                return parse_object(
                    (string, idx + 1),
                    _scan_once,
                    memo=memo
                )
            
            # 3. Array parsing
            elif nextchar == '[':
                return parse_array((string, idx + 1), _scan_once)
            
            # 4. Keyword tokens via direct slice comparison
            start_slice = string[idx:idx + MAX_TOKEN_LEN]
            for token_str, token_val in KEYWORD_TOKENS.items():
                if start_slice.startswith(token_str):
                    if token_str in ("NaN", "Infinity", "-Infinity"):
                        return token_val(context), idx + len(token_str)
                    return token_val, idx + len(token_str)
            
            # 5. Number parsing (second most common)
            if match := NUMBER_RE.match(string, idx):
                num_str = match.group(0)
                # Efficiently handle integer/float distinction
                if '.' in num_str or 'e' in num_str.lower():
                    return parse_float(num_str), match.end()
                return parse_int(num_str), match.end()
                
            # 6. Unexpected character
            raise JSONDecodeError(
                f"Invalid token starting with '{nextchar}' (0x{ord(nextchar):x})", 
                string, idx
            )
            
        finally:
            scan_depth[0] -= 1

    def scan_once(string: str, idx: int) -> Tuple[Any, int]:
        """Public scan interface with memo cleanup and index validation"""
        if idx < 0:
            raise JSONScannerError(f"Invalid scan index {idx}", string, idx)
            
        try:
            return _scan_once(string, idx)
        except JSONDecodeError as e:
            # Add more context about current position
            e.set_context(position=idx, current_char=string[idx] if idx < len(string) else None)
            raise
        finally:
            # Clear memo only if parse_object was not called (handles nested objects)
            if idx == 0:  # Only clear on top-level scan
                memo.clear()

    return scan_once

# Fallback to Python scanner if C extension unavailable
c_scanner = _import_c_make_scanner()
make_scanner = c_scanner if c_scanner else py_make_scanner
