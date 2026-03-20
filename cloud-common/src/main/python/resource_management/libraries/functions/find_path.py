#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Enhanced File Path Locator Utility
"""

import os
from typing import Union, List, Optional, Tuple

def find_path(
    search_directories: Union[str, List[str]], 
    filename: str,
    follow_symlinks: bool = True
) -> Optional[str]:
    """
    Locates a file within specified directories using prioritized search.
    
    Advanced Features:
    - Flexible input types (comma-separated string or list)
    - Symbolic link resolution control
    - Normalized path handling
    - Empty directory filtering
    
    Args:
        search_directories: Paths to search (comma-separated string or list)
        filename: File to locate
        follow_symlinks: Resolve symbolic links to real paths (default: True)
        
    Returns:
        Absolute path to the found file or None if not found
        
    Examples:
        Basic:
            >>> find_path("/opt,/usr/bin", "java")
            /opt/java/bin/java
            
        Symlink handling:
            >>> find_path("/usr/bin", "python", follow_symlinks=False)
            /usr/bin/python3.9
            
        Multiple directories:
            >>> find_path(["/var/log", "/tmp"], "app.log")
            /var/log/app.log
    """
    normalized_dirs = _normalize_search_paths(search_directories)
    
    for directory in normalized_dirs:
        if not directory:  # Skip empty or None values
            continue
            
        candidate = _build_candidate_path(directory, filename)
        if candidate is None:  # Path construction failed
            continue
            
        # Check both direct path and resolved path modes
        verified_path = _verify_path_candidate(candidate, follow_symlinks)
        if verified_path:
            return verified_path
    
    return None  # No valid path found

def _normalize_search_paths(search_directories: Union[str, List[str]]) -> List[str]:
    """
    Convert and normalize search directory input into standardized list
    
    Args:
        search_directories: Input paths (string or list)
        
    Returns:
        List of unique, absolute directory paths with environmental expansion
    """
    # Handle input types and expand environment variables
    processed_paths = os.path.expandvars(
        search_directories if isinstance(search_directories, str)
        else os.pathsep.join(search_directories)
    )
    
    # Split, normalize, and deduplicate paths
    directories = []
    visited = set()
    for path in processed_paths.split(os.pathsep):
        if not path:  # Skip empty strings
            continue
            
        # Convert to absolute path and normalize
        absolute_path = os.path.abspath(os.path.expanduser(path))
        
        # Exclude duplicates and non-directories
        if absolute_path not in visited and os.path.isdir(absolute_path):
            directories.append(absolute_path)
            visited.add(absolute_path)
            
    return directories

def _build_candidate_path(directory: str, filename: str) -> Optional[str]:
    """
    Safely construct candidate file path
    
    Args:
        directory: Base directory path
        filename: Target filename
        
    Returns:
        Full candidate path or None if invalid
    """
    # Check for illegal path constructs
    if ("..%" in directory) or ("..%" in filename):
        return None
        
    try:
        return os.path.join(directory, filename)
    except (TypeError, ValueError):
        return None

def _verify_path_candidate(candidate: str, follow_symlinks: bool) -> Optional[str]:
    """
    Validate if candidate path is a valid file
    
    Args:
        candidate: Path to check
        follow_symlinks: Resolve symbolic links
        
    Returns:
        Verified path or None if invalid
    """
    try:
        # Handle symlink resolution based on parameter
        if follow_symlinks:
            if os.path.isfile(candidate):
                return os.path.realpath(candidate)
        else:
            # Check if candidate exists as file or valid symlink
            if os.path.isfile(candidate) or (
                os.path.islink(candidate) and 
                os.path.isfile(os.readlink(candidate))
            ):
                return candidate
    except OSError:  # Handle permission errors, broken links
        pass
    return None

