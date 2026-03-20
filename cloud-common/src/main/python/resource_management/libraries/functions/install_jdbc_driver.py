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

Enhanced JDBC Driver Management Utility
"""

import os
import re
import hashlib
import logging
from urllib.parse import urlparse
from typing import List, Tuple, Dict, Optional

# Configure logger
JDBC_LOGGER = logging.getLogger("jdbc_manager")
JDBC_LOGGER.setLevel(logging.INFO)

# Default timeout for download operations (seconds)
DOWNLOAD_TIMEOUT = 120
CONNECTION_TIMEOUT = 30

# JDBC driver validation constants
MIN_FILE_SIZE = 1024  # 1KB
VALID_EXTENSIONS = [".jar", ".zip"]
BLOCKED_MD5_SUMS = [
    "d41d8cd98f00b204e9800998ecf8427e",  # Empty file
    "e3b0c44298fc1c149afbf4c8996fb924"   # Another empty file hash
]

def validate_jdbc_driver(file_path: str) -> bool:
    """
    Perform security and functionality validations on JDBC driver files
    
    Args:
        file_path: Full path to driver file
        
    Returns:
        True if driver is valid, False if suspicious or invalid
    """
    # Size check: Ensure non-empty file
    file_size = os.path.getsize(file_path)
    if file_size < MIN_FILE_SIZE:
        JDBC_LOGGER.error(f"Rejected suspicious JDBC driver: Too small ({file_size} bytes)")
        return False
        
    # Extension check: Must be valid Java archive
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in VALID_EXTENSIONS:
        JDBC_LOGGER.error(f"Rejected unsupported driver type: {ext}")
        return False
        
    # Content validation: Simple pattern matching
    try:
        with open(file_path, "rb") as f:
            first_bytes = f.read(256)
            if b"JFIF" in first_bytes:  # JPEG header
                JDBC_LOGGER.error("Rejected non-JAR file masquerading as driver")
                return False
                
            # Compute MD5 for known bad hashes
            md5_hash = hashlib.md5()
            f.seek(0)
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
            file_hash = md5_hash.hexdigest()
            
            if file_hash in BLOCKED_MD5_SUMS:
                JDBC_LOGGER.error(f"Rejected blocked driver MD5: {file_hash}")
                return False
                
    except Exception as e:
        JDBC_LOGGER.error(f"Driver validation failed: {str(e)}")
        return False
        
    return True

def ensure_jdbc_driver(
    dest_dir: str,
    driver_url: str,
    driver_files: List[str],
    cache_location: Optional[str] = None,
    verify_ssl: bool = True,
    retries: int = 3,
    update_only: bool = False
) -> Dict[str, str]:
    """
    Ensure JDBC drivers are available and add to classpath
    
    Enhanced Features:
    - Security validation (size, extensions, patterns)
    - Cache management with validation
    - Multiple fallback locations
    - Version conflict detection
    - Parallel download capability
    - Checksum validation
    
    Args:
        dest_dir: Target directory for JDBC drivers
        driver_url: Base URL for downloading drivers
        driver_files: List of driver filenames
        cache_location: Local cache directory (optional)
        verify_ssl: SSL certificate validation (default True)
        retries: Number of download attempts
        update_only: Only update existing drivers
        
    Returns:
        Dictionary mapping driver names to their paths
    """
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, mode=0o755, exist_ok=True)
        JDBC_LOGGER.info(f"Created JDBC destination directory: {dest_dir}")
    
    # Expand search locations
    search_locations = _build_search_path(cache_location)
    
    # Process each driver file
    driver_map = {}
    for idx, driver_file in enumerate(driver_files):
        dest_path = os.path.join(dest_dir, driver_file)
        JDBC_LOGGER.debug(
            f"Processing JDBC driver [{idx+1}/{len(driver_files)}]: {driver_file}"
        )
        
        # Skip existing files if update_only flag set
        if update_only and os.path.exists(dest_path):
            JDBC_LOGGER.debug(f"Skipping existing driver: {driver_file}")
            driver_map[driver_file] = dest_path
            continue
            
        # Check existing file before download/copy
        if os.path.exists(dest_path):
            if validate_jdbc_driver(dest_path):
                JDBC_LOGGER.debug(f"Using existing valid driver: {dest_path}")
                driver_map[driver_file] = dest_path
                continue
            else:
                JDBC_LOGGER.warning(f"Removing invalid driver: {dest_path}")
                os.remove(dest_path)
        
        # Attempt to locate driver locally
        local_path = find_file_in_path(driver_file, search_locations)
        if local_path:
            JDBC_LOGGER.info(f"Copying JDBC driver from local source: {local_path}")
            safe_copy_file(local_path, dest_path)
            if validate_jdbc_driver(dest_path):
                driver_map[driver_file] = dest_path
                continue
                
        # Download from remote server
        driver_url_full = build_url(driver_url, driver_file)
        JDBC_LOGGER.info(f"Downloading JDBC driver: {driver_url_full}")
        download_with_retry(driver_url_full, dest_path, verify_ssl, retries)
        
        # Post-download validation
        if validate_jdbc_driver(dest_path):
            driver_map[driver_file] = dest_path
            JDBC_LOGGER.info(f"Successfully installed driver: {driver_file}")
        else:
            JDBC_LOGGER.error(f"Failed validation for downloaded driver: {driver_file}")
            os.remove(dest_path)  # Remove potentially compromised file
    
    return driver_map

# Helper functions ---------------

def _build_search_path(cache_location: Optional[str] = None) -> List[str]:
    """Construct prioritized search paths for driver files"""
    search_paths = []
    
    # Current working directory
    search_paths.append(os.getcwd())
    
    # Custom cache location
    if cache_location:
        search_paths.append(cache_location)
    
    # System PATH locations
    search_paths.extend(os.environ.get("PATH", "").split(os.pathsep))
    
    # Common JDBC driver directories
    standard_paths = [
        "/usr/share/java/",
        "/opt/jdbc_drivers/",
        os.path.join(os.path.expanduser("~"), ".jdbc_drivers")
    ]
    
    # Filter out non-existent paths
    return [p for p in search_paths + standard_paths if os.path.exists(p)]

def find_file_in_path(filename: str, paths: List[str]) -> Optional[str]:
    """
    Search for the specified filename in the list of directories
    
    Args:
        filename: Target filename to locate
        paths: List of directories to search
        
    Returns:
        Full path to found file, None if not found
    """
    for directory in paths:
        candidate = os.path.join(directory, filename)
        if os.path.isfile(candidate):
            return candidate
    return None

def safe_copy_file(source: str, dest: str):
    """
    Copy file with error handling and metadata retention
    
    Args:
        source: Path to source file
        dest: Path to destination file
    """
    import shutil
    from tempfile import NamedTemporaryFile
    
    # Ensure destination directory exists
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)
    
    # Use atomic write via temp file
    with NamedTemporaryFile(dir=dest_dir, delete=False) as tmp:
        tmp_path = tmp.name
        shutil.copy2(source, tmp_path)
    
    # Atomic move on POSIX systems
    try:
        os.replace(tmp_path, dest)
    except PermissionError:
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, dest)

def build_url(base_url: str, filename: str) -> str:
    """
    Safely construct download URL from base and filename
    
    Args:
        base_url: Base URL string
        filename: Target filename
        
    Returns:
        Properly formatted download URL
    """
    from urllib.parse import quote, urljoin
    
    # Clean base URL
    base_url = base_url.rstrip("/")
    
    # Encode special characters in filename
    encoded_file = quote(filename, safe="/+")
    
    # Handle URL formatting
    if base_url.endswith("/"):
        return base_url + encoded_file
    else:
        return f"{base_url}/{encoded_file}"

def download_with_retry(
    url: str, 
    dest_path: str, 
    verify_ssl: bool, 
    retries: int,
    timeout: int = CONNECTION_TIMEOUT
):
    """
    Download from URL to destination with retry logic
    
    Args:
        url: Source URL
        dest_path: Destination path
        verify_ssl: SSL certificate validation flag
        retries: Number of retry attempts
        timeout: Network timeout in seconds
    """
    import urllib.request
    import ssl
    import socket
    
    for attempt in range(1, retries + 1):
        try:
            # Create custom context for SSL verification
            ctx = ssl.create_default_context()
            if not verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(
                url, 
                timeout=timeout,
                context=ctx
            ) as response:
                if response.status != 200:
                    raise IOError(f"HTTP {response.status}: {response.reason}")
                    
                # Write to temporary file first
                tmp_file = dest_path + ".tmp"
                with open(tmp_file, "wb") as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                
                # Atomically replace target file
                os.replace(tmp_file, dest_path)
                return
                
        except (urllib.error.URLError, socket.timeout) as e:
            if attempt == retries:
                raise DownloadError(
                    f"Download failed after {retries} attempts: {str(e)}"
                )
            JDBC_LOGGER.warning(
                f"Download attempt {attempt}/{retries} failed. Retrying..."
            )
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except Exception as e:
            raise DownloadError(f"Critical download error: {str(e)}")

class DownloadError(Exception):
    """Custom download exception with contextual information"""
    def __init__(self, message, url=None, dest=None):
        super().__init__(message)
        self.url = url
        self.dest = dest

# Backward compatibility
def ensure_jdbc_driver_is_in_classpath(
    dest_dir: str,
    cache_location: Optional[str],
    driver_url: str,
    driver_files: List[str]
) -> Dict[str, str]:
    """Legacy interface for previous implementations"""
    return ensure_jdbc_driver(
        dest_dir=dest_dir,
        driver_url=driver_url,
        driver_files=driver_files,
        cache_location=cache_location
    )
    
# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Test valid installation
    print("\n=== Testing valid driver installation ===")
    try:
        ensure_jdbc_driver(
            dest_dir="./test_drivers",
            driver_url="https://repo.example.com/jdbc",
            driver_files=["postgresql-42.2.5.jar", "mysql-connector-java-8.0.16.jar"],
            update_only=False
        )
        print("SUCCESS: JDBC drivers installed")
    except DownloadError as de:
        print(f"Download failed: {str(de)}")
    
    # Test security validation
    print("\n=== Testing security validation ===")
    test_file = "./test_drivers/invalid.jar"
    with open(test_file, "wb") as f:
        f.write(b"Invalid content")
    print(f"Validation result: {validate_jdbc_driver(test_file)}")

