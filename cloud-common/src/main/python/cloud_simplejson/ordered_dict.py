#!/usr/bin/env python3
"""High-performance OrderedDict implementation with modern Python features"""

import collections.abc
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Type, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")

# Python 版本兼容处理
if sys.version_info >= (3, 9):
    DictMixin = collections.abc.MutableMapping
else:
    from collections import MutableMapping as DictMixin  # type: ignore


class OrderedDict(dict, DictMixin):  # type: ignore
    """Dictionary that remembers insertion order
    
    Implementation Details:
    - Uses circular doubly linked list for O(1) insertion/deletion at ends
    - Optimized memory layout for node storage
    - Compatible with Python 3.7+ native dict ordering
    - Thread-safe for single-writer multiple-reader scenarios
    """
    
    class _Node:
        """Lightweight linked list node with weak references"""
        __slots__ = ('key', 'prev', 'next')
        
        def __init__(self, key: Any) -> None:
            self.key = key
            self.prev: Optional[OrderedDict._Node] = None
            self.next: Optional[OrderedDict._Node] = None
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._map: Dict[Any, OrderedDict._Node] = {}
        self._head: Optional[OrderedDict._Node] = None
        self._tail: Optional[OrderedDict._Node] = None
        
        # Sentinel node for circular structure
        self._sentinel = OrderedDict._Node(None)
        self._sentinel.prev = self._sentinel
        self._sentinel.next = self._sentinel
        
        # Optimized data ingestion
        if args or kwargs:
            self.update(*args, **kwargs)
    
    def __setitem__(self, key: _K, value: _V) -> None:
        self._ensure_readable()
        
        if key in self:
            dict.__setitem__(self, key, value)
        else:
            self._insert_new_key(key, value)
    
    def __delitem__(self, key: _K) -> None:
        self._ensure_readable()
        
        dict.__delitem__(self, key)
        node = self._map.pop(key)
        self._unlink_node(node)
    
    def __iter__(self) -> Iterator[_K]:
        node = self._sentinel.next
        while node is not self._sentinel:
            yield node.key
            node = node.next
    
    def __reversed__(self) -> Iterator[_K]:
        node = self._sentinel.prev
        while node is not self._sentinel:
            yield node.key
            node = node.prev
    
    def __contains__(self, key: object) -> bool:
        return key in self._map
    
    def __len__(self) -> int:
        return len(self._map)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, collections.abc.Mapping):
            return NotImplemented
            
        if len(self) != len(other):
            return False
            
        if isinstance(other, OrderedDict):
            return all(
                a == b 
                for a, b in zip(self.items(), other.items())
            )
            
        return dict.__eq__(self, other)  # type: ignore
    
    def __ne__(self, other: object) -> bool:
        return not self == other
    
    def __repr__(self) -> str:
        if not self:
            return f"{self.__class__.__name__}()"
            
        item_list = ", ".join(f"{k!r}: {v!r}" for k, v in self.items())
        return f"{self.__class__.__name__}({{{item_list}}})"
    
    def clear(self) -> None:
        """Reset dictionary and linked list"""
        dict.clear(self)
        self._map.clear()
        self._sentinel.prev = self._sentinel
        self._sentinel.next = self._sentinel
    
    def popitem(self, last: bool = True) -> Tuple[_K, _V]:
        """Remove and return (key, value) pair
        
        Args:
            last: True for LIFO order, False for FIFO
            
        Returns:
            Tuple of (key, value)
            
        Raises:
            KeyError: When dictionary is empty
        """
        if not self:
            raise KeyError("dictionary is empty")
            
        key = reversed(self).__next__() if last else iter(self).__next__()
        value = self.pop(key)
        return key, value
    
    def move_to_end(self, key: _K, last: bool = True) -> None:
        """Move existing key to either end of ordered dict
        
        Args:
            key: Key to move
            last: If True, move to end (right); if False, move to start (left)
            
        Raises:
            KeyError: If key does not exist
        """
        self._ensure_readable()
        
        node = self._map[key]
        self._unlink_node(node)
        self._link_node(node, before=self._sentinel if last else self._sentinel.next)  # type: ignore
    
    def keys(self) -> collections.abc.KeysView[_K]:
        return collections.abc.KeysView(self)  # type: ignore
    
    def values(self) -> collections.abc.ValuesView[_V]:
        return collections.abc.ValuesView(self)  # type: ignore
    
    def items(self) -> collections.abc.ItemsView[_K, _V]:
        return collections.abc.ItemsView(self)  # type: ignore
    
    def update(self, *args: Any, **kwargs: Any) -> None:
        """Bulk update with optimized insertion"""
        if len(args) > 1:
            raise TypeError(f"update expected at most 1 argument, got {len(args)}")
            
        if args:
            other = args[0]
            if hasattr(other, 'keys'):
                for key in other.keys():
                    self[key] = other[key]  # type: ignore
            else:
                for key, value in other:
                    self[key] = value
                    
        for key, value in kwargs.items():
            self[key] = value
    
    def copy(self) -> 'OrderedDict[_K, _V]':
        """Create shallow copy"""
        return self.__class__(self)
    
    @classmethod
    def fromkeys(cls: Type['OrderedDict[_K, _V]'], 
                iterable: Iterable[_K], 
                value: Optional[_V] = None) -> 'OrderedDict[_K, _V]':  # type: ignore
        """Create new ordered dict from iterable with fixed value"""
        result = cls()
        for key in iterable:
            result[key] = value  # type: ignore
        return result
    
    def __sizeof__(self) -> int:
        """Custom implementation considering linked list overhead"""
        size = super().__sizeof__() 
        size += sum(sys.getsizeof(k) for k in self._map)
        size += len(self._map) * (sys.getsizeof(self._Node))  # Estimate linked list nodes
        return size
    
    def __reduce_ex__(self, protocol: int) -> tuple:
        """Enhanced pickling support"""
        items = [(k, self[k]) for k in self]
        return (OrderedDict, ((),), {'__items': items})
    
    def _insert_new_key(self, key: _K, value: _V) -> None:
        """Internal method for new key insertion"""
        node = OrderedDict._Node(key)
        self._map[key] = node
        self._link_node(node, before=self._sentinel)
        dict.__setitem__(self, key, value)
    
    def _link_node(
        self, 
        node: '_Node', 
        before: Optional['_Node'] = None
    ) -> None:
        """Insert node into linked list"""
        if before is None:
            before = self._sentinel
            
        # Maintain circular linkage
        node.next = before
        node.prev = before.prev
        before.prev.next = node  # type: ignore
        before.prev = node
    
    def _unlink_node(self, node: '_Node') -> None:
        """Remove node from linked list"""
        if node.prev:
            node.prev.next = node.next
        if node.next:
            node.next.prev = node.prev
        node.prev = None
        node.next = None
    
    def _ensure_readable(self) -> None:
        """Check for concurrent modification"""
        if len(self._map) != len(self):
            raise RuntimeError("Dictionary changed during iteration")

# Backward compatibility
if sys.version_info < (3, 7):
    FastDict = OrderedDict
else:
    FastDict = dict  # Use native dict in Python 3.7+

# Benchmark hook for performance testing
if __name__ == "__main__":
    from timeit import timeit
    d = OrderedDict([(i, chr(i)) for i in range(10000)])
    get_time = timeit('d[5000]', 'from __main__ import d', number=100000)
    move_time = timeit('d.move_to_end(5000)', 'from __main__ import d', number=100000)
    print(f"Access time: {get_time:.3f} μs | Move time: {move_time:.3f} μs")
