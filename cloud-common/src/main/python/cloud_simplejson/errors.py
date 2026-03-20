#!/usr/bin/env python3
"""Enhanced JSON decoding error handling system with source mapping"""

__all__ = [
    "JSONDecodeError", 
    "error_context", 
    "syntax_highlight"
]

import sys
import re
from collections import namedtuple
from dataclasses import dataclass, field
from typing import NamedTuple, Optional, Callable, Iterator, Tuple

# Type aliases
SourceSpan = NamedTuple('SourceSpan', [
    ('start_line', int),
    ('start_col', int),
    ('end_line', int),
    ('end_col', int),
    ('doc_position', Tuple[int, int])
])

# Line cache for large documents
_CACHE = {}
_CACHE_SIZE = 20  # Number of documents to cache

def clear_cache():
    """Clear the line position cache"""
    global _CACHE
    _CACHE = {}

def linecol(doc: str, pos: int, cache_enabled: bool = True) -> Tuple[int, int]:
    """
    Calculate precise line and column from document position.
    
    Implements dual-mode lookup with performance cache for large documents.
    
    Args:
        doc: JSON source document
        pos: Character offset in document
        cache_enabled: Disable for security-sensitive environments
    
    Returns:
        (line_number, column_number) tuple
    
    >>> linecol('{"key":\\n"value"}', 10)
    (2, 3)
    """
    if not 0 <= pos < len(doc):
        raise IndexError(f"Position {pos} out of range [0, {len(doc)})")

    # Fast path for short documents
    if len(doc) < 1000 or not cache_enabled:
        return _simple_linecol(doc, pos)
    
    # Cache-based approach for large documents
    return _cached_linecol(doc, pos)

def _simple_linecol(doc: str, pos: int) -> Tuple[int, int]:
    """Non-cached implementation for small documents"""
    # Last newline before position
    last_nl = doc.rfind('\n', 0, pos)
    
    # If no newlines before position
    if last_nl == -1:
        return 1, pos + 1
    
    # Calculate line and column
    current_line = doc.count('\n', 0, pos) + 1
    column = pos - last_nl
    return current_line, column

def _cached_linecol(doc: str, pos: int) -> Tuple[int, int]:
    """Cached implementation with line position map"""
    global _CACHE
    
    # Generate document signature
    doc_hash = hash(doc)
    
    # Retrieve or build line index
    if doc_hash in _CACHE:
        line_starts = _CACHE[doc_hash]
    else:
        # Build list of line start positions
        line_starts = [0] + [m.end() for m in re.finditer(r'\n', doc)]
        
        # Update cache with FIFO strategy
        if len(_CACHE) >= _CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[doc_hash] = line_starts
    
    # Find the last line start <= position
    for line_num, line_start in enumerate(line_starts, 1):
        if line_start <= pos < (line_starts[line_num] if line_num < len(line_starts) else len(doc)):
            return line_num, pos - line_start + 1
    
    # Fallback on error (should never happen)
    return _simple_linecol(doc, pos)

def error_span(doc: str, start: int, end: Optional[int] = None) -> SourceSpan:
    """
    Compute a complete source span with start and end positions
    
    Args:
        doc: JSON source document
        start: Start character offset
        end: End character offset (defaults to start)
    
    Returns:
        Named tuple with:
        - start_line/start_col: Beginning line/column
        - end_line/end_col: Ending line/column
        - doc_position: (start, end) positions
    
    >>> span = error_span('{"key":"value"}', 8, 10)
    >>> (span.start_line, span.start_col, span.end_col)
    (1, 9, 11)
    """
    end = end or start
    start_line, start_col = linecol(doc, start)
    end_line, end_col = linecol(doc, end)
    
    return SourceSpan(
        start_line, start_col,
        end_line, end_col,
        (start, end)
    )

def errmsg(
    msg: str,
    doc: str,
    pos: int,
    context_lines: int = 2,
    syntax_highlighter: Optional[Callable] = None,
    end: Optional[int] = None
) -> str:
    """
    Format rich error message with contextual code display
    
    Args:
        msg: Error description
        doc: JSON source document
        pos: Error start position
        context_lines: Context lines to display
        syntax_highlighter: Function for source code coloring
        end: Optional end position for multi-character errors
    
    Returns:
        Detailed error message with source preview
    
    >>> errmsg("Unexpected token", '{"key":7}', 7)
    "Unexpected token: line 1 column 8 (char 7)\\n> | {..."
    """
    # Calculate absolute bounds and context
    span = error_span(doc, pos, end)
    context_start = max(0, pos - 80)
    context_end = min(len(doc), end if end else pos + 80)
    code_snippet, _ = source_context(doc, span, context_lines, context_start, context_end)
    
    # Highlight source syntax
    if syntax_highlighter:
        code_snippet = syntax_highlighter(code_snippet)
    
    # Compose final message
    marker = _create_position_marker(span.start_col, span.end_col, len(code_snippet))
    
    base_msg = f"{msg}: line {span.start_line} column {span.start_col}"
    if span.end_line != span.start_line or span.start_col != span.end_col:
        base_msg += f" → line {span.end_line} column {span.end_col}"
    base_msg += f" (char {span.doc_position[0]}"
    if end:
        base_msg += f"-{span.doc_position[1]}"
    base_msg += ")\n\n"
    
    return f"{base_msg}{code_snippet}\n{marker}"

def source_context(
    doc: str,
    span: SourceSpan,
    context_lines: int,
    context_start: int,
    context_end: int
) -> Tuple[str, Tuple[int, int]]:
    """Extract source context around error position"""
    lines = doc.split('\n')
    
    # Get relevant lines around the error
    start_idx = max(0, span.start_line - context_lines - 1)
    end_idx = min(len(lines), span.end_line + context_lines)
    
    snippet_lines = []
    line_number_width = len(str(end_idx))
    
    # Create context blocks
    if start_idx > 0:
        snippet_lines.append(f"... [showing {span.start_line - context_lines} lines] ...")
    
    for i in range(start_idx, end_idx):
        line = lines[i]
        line_text = line[context_start:context_end] if i == start_idx and context_start else line
        prefix = f"{i + 1:>{line_number_width}} | "
        snippet_lines.append(f"{prefix}{line_text}")
    
    if end_idx < len(lines):
        snippet_lines.append(f"... [omitting {len(lines) - end_idx} lines] ...")
    
    snippet = '\n'.join(snippet_lines)
    
    # Calculate visual position marker
    marker_base = (span.start_line - start_idx) * (len(prefix) - 1) + span.start_col
    marker_end = marker_base + (span.end_col - span.start_col) if span.end_line == span.start_line else None
    
    return snippet, (marker_base, marker_end)

def _create_position_marker(start_col: int, end_col: int, line_len: int) -> str:
    """Generate visual indicator pointing to error position"""
    # Single character marker
    if start_col == end_col:
        return " " * (start_col - 1) + "^" + " " * (line_len - start_col)
    
    # Multi-character highlight
    marker = [' '] * max(line_len, end_col)
    for i in range(start_col - 1, end_col):
        marker[i] = '~'
    marker[start_col - 1] = '^'  # Start indicator
    return ''.join(marker)

def syntax_highlight(source: str) -> str:
    """Simple JSON syntax highlighter for error displays"""
    patterns = [
        (r'(\btrue\b|\bfalse\b|\bnull\b)', '\x1b[35m\\1\x1b[0m'),  # Keywords (purple)
        (r'-?\b\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b', '\x1b[36m\\1\x1b[0m'),  # Numbers (cyan)
        (r'".*?(?<!\\)"', '\x1b[32m\\1\x1b[0m'),  # Strings (green)
        (r'[{}[\]:,]', '\x1b[33m\\1\x1b[0m'),  # Syntax (yellow)
    ]
    
    for pattern, replacement in patterns:
        source = re.sub(pattern, replacement, source)
    
    return source

def error_context(doc: str, pos: Tuple[int, int], error_type: str = "decoding") -> Iterator[str]:
    """Generate context-aware diagnostic messages"""
    start, end = pos
    error_identifier = {
        "decoding": ("Syntax", "near"),
        "schema": ("Validation", "within"),
        "semantic": ("Evaluation", "while processing")
    }.get(error_type, ("Error", "during"))
    
    yield f"{error_identifier[0]} error {error_identifier[1]}:"
    
    # Extract relevant context
    if start > 0:
        yield f"  Preceding: {doc[max(0, start - 40):start]}"
    
    if end < len(doc):
        yield f"  Current: {doc[start:end]}"
        yield f"  Following: {doc[end:min(len(doc), end + 40)]}"
    
    # Suggest possible solutions
    current_token = doc[pos[0]:pos[1]]
    for suggestion in _get_suggestions(current_token, error_type):
        yield f"  Consider: {suggestion}"

def _get_suggestions(token: str, error_type: str) -> Iterator[str]:
    """Generate auto-suggestions based on token type"""
    # Mapping of common mistakes to solutions
    suggestions = {
        "decoding": [
            ("ture", "true", "Maybe you meant 'true'?"),
            ("flase", "false", "Possible typo, use 'false'"),
            ("nul", "null", "The null keyword is spelled 'null'"),
            ("{,}", "}", "Unmatched braces, check nesting"),
            ("[,]", "]", "Unmatched brackets, check nesting"),
            ("Infinity", "1e1000", "Use large exponent for infinity"),
            ("NaN", "null", "NaN not valid in JSON, use null"),
            ("undefined", "null", "Use 'null' for JSON undefined")
        ],
        "schema": [
            ("string", "number", "Check expected data type"),
            ("missing", "required", "Required property missing"),
            ("extra", "allow", "Unexpected property found")
        ],
        "semantic": [
            ("div by zero", "check", "Divide by zero protection"),
            ("overflow", "limit", "Numeric value too large"),
            ("circular", "resolve", "Circular reference detected"),
            ("reference", "copy", "Unresolved reference")
        ]
    }
    
    token_lower = token.lower()
    for pattern, solution, suggestion in suggestions.get(error_type, []):
        if pattern in token_lower:
            yield suggestion + f" → use {solution}"
  
@dataclass
class JSONDecodeError(ValueError):
    """Enhanced JSON decoding error container with source mapping
    
    Attributes:
        msg: Original error message
        doc: JSON document being parsed
        pos: Start position in document
        end: End position of error span (optional)
        span: Computed source position metadata
        diagnostics: Optional diagnostic suggestions
    
    Methods:
        rich_message(): Format detailed context-rich error
        to_dict(): Convert to serializable structure
        print(): Write formatted error to stderr
    
    Example:
        try:
            json.loads(invalid_json)
        except JSONDecodeError as e:
            e.print()
    """
    
    msg: str
    doc: str
    pos: int
    end: Optional[int] = None
    span: SourceSpan = field(init=False)
    diagnostics: list = field(default_factory=list)
    
    def __post_init__(self):
        # Calculate error span
        self.span = error_span(self.doc, self.pos, self.end)
        if not self.diagnostics:
            self.diagnostics = list(error_context(self.doc, (self.pos, self.end or self.pos)))
        
        # Format base exception message
        base_msg = errmsg(self.msg, self.doc, self.pos, self.end)
        ValueError.__init__(self, base_msg)
    
    def __str__(self):
        """Default string representation"""
        return "\n".join([
            f"{self.msg} [line {self.span.start_line}, column {self.span.start_col}]",
            *self.diagnostics[:3]  # Show top diagnostics
        ])
    
    def rich_message(self, width: int = 80, highlight: bool = True) -> str:
        """Generate detailed contextual error view
        
        Args:
            width: Display width constraint
            highlight: Enable syntax coloring
        
        Returns:
            Formatted multi-line error presentation
        """
        return errmsg(
            self.msg,
            self.doc,
            self.pos,
            context_lines=3,
            syntax_highlighter=syntax_highlight if highlight else None,
            end=self.end
        )
    
    def to_dict(self) -> dict:
        """Convert error to structured data format"""
        return {
            "error": self.msg,
            "position": {
                "char": self.span.doc_position[0],
                "end_char": self.span.doc_position[1],
                "line": self.span.start_line,
                "column": self.span.start_col,
                "end_line": self.span.end_line,
                "end_column": self.span.end_col
            },
            "document_preview": self.doc[max(0, self.pos-20):min(len(self.doc), self.pos+20)],
            "diagnostics": self.diagnostics
        }
    
    def print(self, file=sys.stderr, width: int = 120):
        """Pretty-print error to output stream
        
        Args:
            file: Output stream (default=stderr)
            width: Display width
        """
        print("\n" + "="*width, file=file)
        print(f"JSON DECODING ERROR: {self.msg}", file=file)
        print("-"*width, file=file)
        
        # Display source context
        snippet, (marker_start, marker_end) = source_context(
            self.doc, 
            self.span,
            3,
            max(0, self.span.doc_position[0] - 40),
            min(len(self.doc), self.span.doc_position[1] + 40)
        )
        
        print(syntax_highlight(snippet), file=file)
        
        # Create visual marker
        marker_base = marker_start
        if marker_end:
            marker = '~' * (marker_end - marker_base)
        else:
            marker = '^'
        
        print(
            " " * marker_base + 
            "\x1b[31m" + marker + " <─ ERROR HERE\x1b[0m",
            file=file
        )
        
        # Key diagnostic messages
        if self.diagnostics:
            print("\nDIAGNOSTICS:", file=file)
            for d in self.diagnostics[:3]:
                print(f" • {d}", file=file)
        
        print("="*width + "\n", file=file)
    
    def __reduce__(self):
        return self.__class__, (
            self.msg, 
            self.doc, 
            self.pos, 
            self.end,
            self.diagnostics
        )

# API compatibility layer (for speedups extension)
if __name__ == "__main__":
    default_error = JSONDecodeError(
        msg="Expecting value",
        doc='{"key": invalid}',
        pos=8
    )
    default_error.print(width=80)
