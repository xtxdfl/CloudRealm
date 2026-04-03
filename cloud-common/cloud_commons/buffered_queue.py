#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apache Licensed Thread-Safe Buffered Queue

A high-performance producer-consumer queue with backpressure support,
thread-safe synchronization, and graceful termination handling.
"""

from collections import deque
from threading import RLock, Condition
import time
from typing import Any, Optional, Union

class BufferedQueue:
    """
    Thread-safe buffered queue for efficient producer-consumer communication.
    
    Features:
    - Blocking/non-blocking get with timeout
    - Auto-clearance of wait signals when queue becomes empty
    - Graceful termination notification
    - Thread-safe queue reset
    - Backpressure awareness for producers
    """
    
    def __init__(self, max_size: int = 0):
        """
        Initialize the buffered queue.
        
        :param max_size: Maximum queue size (0 for unlimited)
        """
        self._queue = deque()
        # Used for coordinating consumers and producers
        self._condition = Condition(RLock())  # RLock supports recursive locking
        self._producer_complete = False  # Producer termination flag
        self._max_size = max_size  # Backpressure control
        self._closing = False  # Queue shutdown flag

    def put(self, item: Any, timeout: Optional[float] = None) -> bool:
        """
        Add an item to the queue with optional backpressure handling.
        
        :param item: Item to add to the queue
        :param timeout: Maximum wait time if queue is full (None blocks indefinitely)
        :return: True if item was added, False if timed out or queue closing
        :raises ValueError: If queue is being closed
        """
        with self._condition:
            if self._closing:
                raise ValueError("Queue is closing, cannot add items")
            
            # Handle backpressure if max_size is set
            if self._max_size > 0:
                end_time = time.monotonic() + timeout if timeout else None
                while len(self._queue) >= self._max_size:
                    if not self._condition.wait_for(
                        lambda: len(self._queue) < self._max_size or self._closing,
                        timeout=end_time - time.monotonic() if end_time else None
                    ):
                        return False  # Timeout expired
                    if self._closing:
                        raise ValueError("Queue closed while waiting")
            
            # Add item to queue and notify consumers
            self._queue.append(item)
            self._condition.notify_all()
            return True

    def get(self, timeout: Optional[float] = None) -> Any:
        """
        Retrieve an item from the queue.
        
        :param timeout: Maximum wait time for an item (None blocks indefinitely)
        :return: Item from queue or None if timed out/completed
        """
        with self._condition:
            # Wait conditions: either data available or producer has finished
            if not self._queue and not self._producer_complete:
                # Wait for data or termination signal
                if not self._condition.wait_for(
                    lambda: self._queue or self._producer_complete,
                    timeout=timeout
                ):
                    return None  # Timeout without data
                
            # Return item if available
            if self._queue:
                item = self._queue.popleft()
                # Notify producers that space is available
                if self._max_size > 0:
                    self._condition.notify_all()
                return item
            return None  # No items and producer finished

    def notify_completion(self):
        """Signal that no more items will be produced."""
        with self._condition:
            self._producer_complete = True
            self._condition.notify_all()

    def close(self):
        """Gracefully shut down the queue, rejecting new puts and clearing data."""
        with self._condition:
            self._closing = True
            self._queue.clear()
            self._condition.notify_all()

    def reset(self):
        """Reset the queue to initial state (not closed, empty, not completed)."""
        with self._condition:
            self._queue.clear()
            self._producer_complete = False
            self._closing = False
            self._condition.notify_all()

    def batch_get(self, max_items: int = 0, timeout: Optional[float] = None) -> list:
        """
        Retrieve multiple items in a batch.
        
        :param max_items: Maximum items to retrieve (0 for all available)
        :param timeout: Maximum wait time for first item
        :return: List of retrieved items
        """
        with self._condition:
            if not self._queue and not self._producer_complete:
                if not self._condition.wait_for(
                    lambda: self._queue or self._producer_complete,
                    timeout=timeout
                ):
                    return []
                    
            result = []
            while self._queue and (not max_items or len(result) < max_items):
                result.append(self._queue.popleft())
                
            # Notify producers that space is available
            if result and self._max_size > 0:
                self._condition.notify_all()
            return result

    @property
    def empty(self) -> bool:
        """Check if queue is empty and no more items will come."""
        with self._condition:
            return self._producer_complete and not self._queue

    @property
    def size(self) -> int:
        """Current number of items in the queue."""
        with self._condition:
            return len(self._queue)

    @property
    def pending(self) -> bool:
        """Check if queue has items or expects more (not empty and not finished)."""
        with self._condition:
            return not self._producer_complete or self._queue

    @property
    def capacity(self) -> float:
        """Current queue utilization as fraction (0-1)."""
        if self._max_size <= 0:
            return 0
        with self._condition:
            return len(self._queue) / self._max_size

    def __len__(self) -> int:
        """Current number of items in the queue."""
        return self.size
