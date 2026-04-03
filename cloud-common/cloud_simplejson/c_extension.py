#!/usr/bin/env python3
"""Optimized C extension loader with platform detection and failover"""

import importlib
import os
import sys
import platform
import logging
import ctypes
from typing import Any, Dict, Optional, Tuple

__version__ = "1.3.0"
__all__ = ["get", "is_loaded", "get_extension_path"]

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/tmp/c_extension_loader.log"),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("c_extension_loader")

# Platform detection mapping
PLATFORM_EXT_MAP = {
    "linux": {
        "x86_64": "_speedups.linux_x64",
        "aarch64": "_speedups.linux_arm64",
        "i386": "_speedups.linux_i386",
        "universal": "_speedups.linux_universal"
    },
    "darwin": {
        "x86_64": "_speedups.macos_intel",
        "arm64": "_speedups.macos_m1",
        "universal": "_speedups.macos_universal"
    },
    "win32": {
        "AMD64": "_speedups.win_x64",
        "x86": "_speedups.win_x86",
        "ARM64": "_speedups.win_arm64"
    }
}

# Fallback paths (pre-defined absolute locations)
FALLBACK_PATHS = [
    "/usr/local/lib/c_extensions",
    os.path.expanduser("~/.local/c_extensions"),
    os.path.join(os.path.dirname(__file__), "c_build")
]

# Performance metrics cache
_LOAD_CACHE: Dict[str, Any] = {}
_LOAD_STATS = {"total_tries": 0, "success_count": 0}

def get() -> Any:
    """Dynamically load the best matching C extension module
    
    Returns:
        Loaded module or None if no compatible extensions found
    """
    global _LOAD_CACHE
    
    # Use cached result if available
    cache_key = f"{sys.platform}-{platform.machine()}"
    if cache_key in _LOAD_CACHE:
        return _LOAD_CACHE[cache_key]
    
    candidate = None
    
    # First try: Intelligent platform detection
    if sys.platform in PLATFORM_EXT_MAP:
        machine_map = PLATFORM_EXT_MAP[sys.platform]
        for arch in [platform.machine(), "universal"]:
            if arch in machine_map:
                candidate = machine_map[arch]
                logger.debug("Trying platform-specific extension: %s", candidate)
                ext_module = _try_load(candidate)
                if ext_module:
                    _update_stats(True)
                    _LOAD_CACHE[cache_key] = ext_module
                    return ext_module
    
    # Second try: Parent-package relative import
    parent_pkg = ".".join(__name__.split(".")[:-1] + ["_speedups"])
    logger.debug("Trying parent-package relative import: %s", parent_pkg)
    ext_module = _try_load(parent_pkg)
    if ext_module:
        _update_stats(True)
        _LOAD_CACHE[cache_key] = ext_module
        return ext_module
    
    # Third try: System library paths
    for lib_path in FALLBACK_PATHS:
        if os.path.exists(lib_path):
            logger.debug("Scanning fallback directory: %s", lib_path)
            ext_module = _scan_directory(lib_path)
            if ext_module:
                _update_stats(True)
                _LOAD_CACHE[cache_key] = ext_module
                return ext_module
    
    # Final fallback: Try common names (last resort)
    common_names = ["c_extension", "_c_extension", "_speedups", "json_speedups"]
    for name in common_names:
        logger.debug("Trying common extension: %s", name)
        ext_module = _try_load(name)
        if ext_module:
            _update_stats(True)
            _LOAD_CACHE[cache_key] = ext_module
            return ext_module
    
    _update_stats(False)
    _LOAD_CACHE[cache_key] = None
    return None

def is_loaded() -> bool:
    """Check if any C extension has been successfully loaded
    
    Returns:
        True if C extension is available, False otherwise
    """
    return get() is not None

def get_extension_path() -> Optional[str]:
    """Get the filesystem path of the loaded extension
    
    Returns:
        Absolute path to the loaded extension module or None
    """
    mod = get()
    return getattr(mod, "__file__", None) if mod else None

def get_load_stats() -> Tuple[int, int]:
    """Get loading statistics (success_count, total_tries)"""
    return _LOAD_STATS["success_count"], _LOAD_STATS["total_tries"]

def _try_load(module_name: str) -> Optional[Any]:
    """Safe module loader with error trapping"""
    global _LOAD_STATS
    _LOAD_STATS["total_tries"] += 1
    
    try:
        module = importlib.import_module(module_name)
        
        # Basic validation of C extension
        if hasattr(module, "is_valid_extension") and not module.is_valid_extension():
            logger.warning("Extension %s failed validation", module_name)
            return None
        
        return module
    except ImportError as e:
        logger.debug("Import failed for %s: %s", module_name, e)
    except OSError as e:
        # Handle library compatibility issues
        if "wrong ELF class" in str(e):
            logger.error("Architecture mismatch: %s", e)
        elif "undefined symbol" in str(e):
            logger.error("Symbol resolution failure: %s", e)
        else:
            logger.exception("OS error loading %s", module_name)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("Unexpected error loading %s", module_name)
    
    return None

def _scan_directory(directory: str) -> Optional[Any]:
    """Scan directory for compatible extensions"""
    valid_extensions = {
        ".so": "linux", 
        ".dylib": "darwin", 
        ".pyd": "win32", 
        ".dll": "win32"
    }
    
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1]
                if ext in valid_extensions and valid_extensions[ext] == sys.platform:
                    lib_path = entry.path
                    try:
                        logger.debug("Attempting to load: %s", lib_path)
                        ext_module = ctypes.CDLL(lib_path)
                        return _wrap_c_module(ext_module, lib_path)
                    except OSError as e:
                        logger.debug("CTYPES load failed for %s: %s", lib_path, e)
    except Exception:  # pylint: disable=broad-except
        logger.exception("Error scanning directory %s", directory)
    
    return None

def _wrap_c_module(cdll: ctypes.CDLL, path: str) -> Any:
    """Create mock module object for ctypes loaded libraries"""
    class CDLLWrapper:
        __file__ = path
        __loader__ = None
        
        def __getattr__(self, name):
            try:
                return getattr(cdll, name)
            except AttributeError:
                return None
    
    return CDLLWrapper()

def _update_stats(success: bool) -> None:
    """Update loading statistics"""
    if success:
        _LOAD_STATS["success_count"] += 1
        logger.info("C extension loaded successfully")
    else:
        logger.error("All C extension load attempts failed")

# Auto-check when imported in debug mode
if os.getenv("C_EXT_DEBUG"):
    logger.setLevel(logging.DEBUG)
    logger.debug("C extension loader initialized")
    logger.debug("Current platform: %s %s", sys.platform, platform.machine())
    
    loaded_mod = get()
    if loaded_mod:
        logger.info("Successfully loaded extension: %s", get_extension_path())
        suc, tries = get_load_stats()
        logger.debug("Load stats: %d/%d success rate", suc, tries)
    else:
        logger.warning("No compatible C extensions found")
