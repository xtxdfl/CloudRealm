#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optimized statistical computation utilities

Functions for calculating critical statistical metrics with
improved performance and better numerical stability.
"""

import math
from math import sqrt
from typing import List, Union

def mean(values: List[Union[int, float]]) -> float:
    """
    Efficient calculation of arithmetic mean
    
    Args:
        values: List of numerical values
    
    Returns:
        Mean of the values. Returns 0 for empty lists.
    """
    if not values:
        return 0.0
    
    total = 0.0
    count = 0
    for v in values:
        total += v
        count += 1
    return total / count

def sample_standard_deviation(values: List[Union[int, float]]) -> float:
    """
    Calculates sample standard deviation (unbiased estimator)
    
    Args:
        values: List of numerical values
    
    Returns:
        Standard deviation. Returns 0 for insufficient data points (n < 2).
    """
    n = len(values)
    if n < 2:
        return 0.0
    
    # Calculate mean only once
    mean_val = mean(values)
    
    # Compute sum of squared differences using running calculation
    sum_squares = 0.0
    for v in values:
        diff = v - mean_val
        sum_squares += diff * diff
    
    # Calculate and return sample standard deviation
    return sqrt(sum_squares / (n - 1))

def sample_standard_deviation_percentage(values: List[Union[int, float]]) -> float:
    """
    Calculates coefficient of variation (CV)
    
    Args:
        values: List of numerical values
    
    Returns:
        CV value as percentage. Returns 0 for invalid cases.
    """
    if not values:
        return 0.0
    
    stdev = sample_standard_deviation(values)
    mean_val = mean(values)
    
    # Handle division by zero safely
    if abs(mean_val) < 1e-9:
        return 0.0
    return (stdev / abs(mean_val)) * 100.0

def count(values: List) -> int:
    """
    Returns the number of data points
    """
    return len(values)
