#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one or more
contributor license agreements.  See the NOTICE file distributed with
this work for additional information regarding copyright ownership.
The ASF licenses this file to you under the Apache License, Version 2.0
(the "License"); you may not use this file except in compliance with
the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Enhanced Directory Archiving Utility
"""

import os
import sys
import zipfile
import logging
import time
import stat
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Tuple, List

# Configure logger
ARCHIVE_LOGGER = logging.getLogger("directory_archiver")
ARCHIVE_LOGGER.setLevel(logging.INFO)

# Compression options
DEFAULT_COMPRESSION = zipfile.ZIP_DEFLATED
DEFAULT_COMPRESSION_LEVEL = 6

# Performance constants
MAX_WORKERS = os.cpu_count() * 2
BLOCK_SIZE = 64 * 1024  # 64KB chunks for streaming reads

# File permission masks
EXECUTABLE_MASK = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

def create_archive(
    source_dir: str,
    output_file: str,
    compression: int = DEFAULT_COMPRESSION,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
    include_hidden: bool = False,
    preserve_permissions: bool = False,
    symlinks: bool = True,
    concurrency: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """
    Create a ZIP archive of a directory with enhanced features
    
    Key Features:
    - Multi-threaded compression for large directories
    - Preservation of Unix file permissions
    - Symbolic link handling
    - Progress tracking
    - Customizable compression levels
    - Hidden file filtering
    
    Args:
        source_dir: Directory to archive
        output_file: Path to output ZIP file
        compression: ZIP compression method (ZIP_STORED, ZIP_DEFLATED, ZIP_LZMA)
        compression_level: Compression level (0-9 for DEFLATED, 0 for store)
        include_hidden: Include hidden files/dotfiles
        preserve_permissions: Preserve Unix file permissions
        symlinks: Handle symbolic links (store links as symlinks)
        concurrency: Number of worker threads (default: CPU * 2)
        progress_callback: Callback function (processed_files, total_files)
        
    Returns:
        True if successful, False otherwise
    """
    source_dir = os.path.abspath(source_dir)
    output_file = os.path.abspath(output_file)
    
    if not os.path.isdir(source_dir):
        ARCHIVE_LOGGER.error(f"Source directory does not exist: {source_dir}")
        return False
        
    # Prepare file list and calculate total size
    file_list = []
    def collect_files(path, root=source_dir):
        for entry in os.scandir(path):
            # Skip hidden files/directories if not included
            if not include_hidden and entry.name.startswith('.'):
                continue
                
            entry_path = entry.path
            rel_path = os.path.relpath(entry_path, root)
            
            if entry.is_symlink() and symlinks:
                file_list.append((entry_path, rel_path, 'symlink'))
            elif entry.is_file(follow_symlinks=False):
                file_list.append((entry_path, rel_path, 'file'))
            elif entry.is_dir(follow_symlinks=False):
                file_list.append((entry_path, rel_path, 'dir'))
                collect_files(entry_path, root)
    
    collect_files(source_dir)
    total_files = len(file_list)
    ARCHIVE_LOGGER.info(f"Found {total_files} files to archive from {source_dir}")
    
    # Configure workers
    workers = concurrency or min(max(1, MAX_WORKERS), 32)
    
    # Create parent directory if needed
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Create the archive
    processed_files = 0
    start_time = time.time()
    
    try:
        with zipfile.ZipFile(
            output_file, 
            'w', 
            compression=compression,
            compresslevel=compression_level
        ) as zipf:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                tasks = [
                    executor.submit(add_to_archive, zipf, *file_info)
                    for file_info in file_list
                ]
                
                for idx, future in enumerate(tasks):
                    success = future.result()
                    processed_files += 1
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(processed_files, total_files)
                        
                    # Periodically log progress
                    if processed_files % 100 == 0 or processed_files == total_files:
                        ARCHIVE_LOGGER.debug(
                            f"Processed {processed_files}/{total_files} files "
                            f"({processed_files/total_files:.1%})"
                        )
    except Exception as e:
        ARCHIVE_LOGGER.error(f"Archive creation failed: {str(e)}")
        # Cleanup partial output
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass
        return False
    
    # Final status
    total_time = time.time() - start_time
    archive_size = os.path.getsize(output_file) / (1024 * 1024)
    ARCHIVE_LOGGER.info(
        f"Created archive: {output_file} "
        f"({archive_size:.2f} MB) in {total_time:.1f} seconds "
        f"at {total_files/total_time:.1f} files/s"
    )
    return True

def add_to_archive(
    zipf: zipfile.ZipFile,
    full_path: str,
    rel_path: str,
    entry_type: str
) -> bool:
    """
    Add a single entry to the ZIP archive with proper handling
    """
    try:
        if entry_type == 'file':
            return _add_file(zipf, full_path, rel_path)
        elif entry_type == 'dir':
            return _add_directory(zipf, full_path, rel_path)
        elif entry_type == 'symlink':
            return _add_symlink(zipf, full_path, rel_path)
        else:
            ARCHIVE_LOGGER.warning(f"Unknown entry type: {entry_type} for {full_path}")
            return False
    except Exception as e:
        ARCHIVE_LOGGER.warning(f"Failed to add {full_path}: {str(e)}")
        return False

def _add_file(
    zipf: zipfile.ZipFile,
    file_path: str,
    zip_path: str
) -> bool:
    """
    Add a regular file to the archive with proper compression
    """
    # Get file stats
    stat_info = os.stat(file_path)
    
    # Create ZipInfo with file metadata
    zip_info = zipfile.ZipInfo.from_file(file_path, zip_path)
    zip_info.external_attr = (stat_info.st_mode & 0xFFFF) << 16
    
    # Calculate file hash (optional for verification)
    file_hash = hashlib.md5()
    
    # Add file contents with streaming to save memory
    with open(file_path, 'rb') as src_file:
        with zipf._lock:  # Thread-safe write
            with zipf.open(zip_info, 'w') as dest_file:
                while True:
                    chunk = src_file.read(BLOCK_SIZE)
                    if not chunk:
                        break
                    dest_file.write(chunk)
                    file_hash.update(chunk)
    
    # Logging
    ARCHIVE_LOGGER.debug(f"Added file: {zip_path} ({stat_info.st_size} bytes)")
    return True

def _add_directory(
    zipf: zipfile.ZipFile,
    dir_path: str,
    zip_path: str
) -> bool:
    """
    Add an empty directory to the archive (important for structure)
    """
    # Ensure directory path ends with separator
    if not zip_path.endswith('/'):
        zip_path += '/'
    
    # Create directory entry
    stat_info = os.stat(dir_path)
    zip_info = zipfile.ZipInfo(zip_path)
    zip_info.external_attr = (stat_info.st_mode & 0xFFFF) << 16
    zip_info.compress_type = zipfile.ZIP_STORED
    
    with zipf._lock:
        zipf.writestr(zip_info, b'')
    
    ARCHIVE_LOGGER.debug(f"Added directory: {zip_path}")
    return True

def _add_symlink(
    zipf: zipfile.ZipFile,
    link_path: str,
    zip_path: str
) -> bool:
    """
    Preserve symbolic links in the archive
    """
    target = os.readlink(link_path)
    
    # Create special entry for symlink
    zip_info = zipfile.ZipInfo(zip_path)
    zip_info.external_attr = (0o777 | stat.S_IFLNK) << 16
    zip_info.compress_type = zipfile.ZIP_STORED
    
    # Store link target using UTF-8 encoding
    link_data = target.encode('utf-8')
    
    with zipf._lock:
        zipf.writestr(zip_info, link_data)
    
    ARCHIVE_LOGGER.debug(f"Added symlink: {zip_path} -> {target}")
    return True

def extract_archive(
    zip_file: str,
    target_dir: str,
    overwrite_existing: bool = False,
    preserve_permissions: bool = True
) -> bool:
    """
    Extract a ZIP archive with proper metadata preservation
    
    Args:
        zip_file: Path to ZIP archive
        target_dir: Directory to extract files
        overwrite_existing: Overwrite existing files
        preserve_permissions: Restore Unix file permissions
        
    Returns:
        True if successful, False otherwise
    """
    if not os.path.isfile(zip_file):
        ARCHIVE_LOGGER.error(f"ZIP file not found: {zip_file}")
        return False
    
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    extracted_count = 0
    
    try:
        with zipfile.ZipFile(zip_file, 'r') as zipf:
            file_list = zipf.infolist()
            total_files = len(file_list)
            ARCHIVE_LOGGER.info(f"Extracting {total_files} files to {target_dir}")
            
            for zip_info in file_list:
                # Normalize path for security
                dest_path = os.path.join(target_dir, zip_info.filename)
                dest_path = os.path.abspath(dest_path)
                
                # Validate extraction safety
                if not dest_path.startswith(os.path.abspath(target_dir)):
                    ARCHIVE_LOGGER.error(f"Security violation: {dest_path} outside target dir")
                    return False
                
                # Create directory structure if needed
                if zip_info.is_dir():
                    Path(dest_path).mkdir(parents=True, exist_ok=True)
                    ARCHIVE_LOGGER.debug(f"Created directory: {dest_path}")
                    continue
                
                # Skip if file exists unless overwriting
                if os.path.exists(dest_path) and not overwrite_existing:
                    ARCHIVE_LOGGER.debug(f"Skipped existing file: {dest_path}")
                    continue
                
                # Extract file contents
                with zipf.open(zip_info) as src_file:
                    with open(dest_path, 'wb') as dest_file:
                        while True:
                            chunk = src_file.read(BLOCK_SIZE)
                            if not chunk:
                                break
                            dest_file.write(chunk)
                
                # Special handling for symlinks
                if preserve_permissions:
                    # Only available in Python 3.6+
                    if hasattr(zip_info, 'is_symlink') and zip_info.is_symlink():
                        target = zipf.read(zip_info).decode('utf8')
                        os.symlink(target, dest_path)
                    else:
                        # Restore file permissions
                        unix_attr = (zip_info.external_attr >> 16) & 0o777
                        os.chmod(dest_path, unix_attr)
                        
                        # Check if executable (based on any executable bit)
                        executable = bool(unix_attr & EXECUTABLE_MASK)
                        if executable:
                            ARCHIVE_LOGGER.debug(f"Set executable permission: {dest_path}")
                
                extracted_count += 1
                ARCHIVE_LOGGER.debug(f"Extracted: {dest_path}")
                
    except Exception as e:
        ARCHIVE_LOGGER.error(f"Extraction failed: {str(e)}")
        return False
    
    ARCHIVE_LOGGER.info(f"Extracted {extracted_count} files successfully")
    return True

def archive_dir(
    source_dir: str,
    output_file: str,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL
) -> None:
    """
    Simplified compatibility wrapper for the original archive_dir functionality
    
    Args:
        source_dir: Directory to compress
        output_file: Output ZIP file path
        compression_level: Compression level (1-9)
    """
    create_archive(
        source_dir=source_dir,
        output_file=output_file,
        compression_level=compression_level
    )

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    def progress_callback(current, total):
        sys.stdout.write(f"\rProcessing: {current}/{total} files")
        sys.stdout.flush()
    
    # Test creating an archive
    create_archive(
        source_dir="test_files",
        output_file="output.zip",
        progress_callback=progress_callback
    )
    
    # Test extracting
    extract_archive(
        zip_file="output.zip",
        target_dir="extracted_files"
    )
    
    print("\nArchive test completed")

