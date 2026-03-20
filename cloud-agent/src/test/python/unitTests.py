#!/usr/bin/env python3
"""
Enhanced Unit Test Runner for cloud Python Components
======================================================

A robust test runner that provides:
- Flexible test selection patterns
- Environment setup for cloud components
- Detailed test execution logs
- Multiple output options (console and file)
- Test discovery with custom filtering
- Special debug mode with selective test execution

Original License:
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
"""

import os
import sys
import re
import logging
import fnmatch
import argparse
import time
import unittest
from os.path import abspath, isdir, join, dirname, basename, exists
from resource_management.core.logger import Logger
from only_for_platform import get_platform, PLATFORM_WINDOWS

# Constants
SELECTED_PREFIX = "_"  # Files with this prefix are run in debug mode
PY_EXT = ".py"
LOG_FILE_NAME = "tests.log"
TEST_FILE_PATTERN = r"^_?[Tt]est.*\.py$"

class CustomFormatter(logging.Formatter):
    """Custom formatter with colored output for different log levels"""
    COLORS = {
        logging.DEBUG: "\033[37m",    # White
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[1;35m"  # Bold Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        message = super().format(record)
        if color:
            message = f"{color}{message}{self.RESET}"
        return message

def setup_python_paths():
    """Configure Python paths for cloud project"""
    current_dir = os.getcwd()
    script_dir = dirname(abspath(__file__))
    # Calculate project root based on script location
    # Assuming script is at: cloud-agent/src/test/python/unitTests.py
    cloud_agent_dir = dirname(dirname(dirname(dirname(script_dir))))
    src_dir = dirname(cloud_agent_dir)  # Parent of agent directory is source root
    cloud_common_dir = join(src_dir, "cloud-common")
    
    # Critical Python paths
    paths = [
        join(cloud_agent_dir, "src", "main", "python"),
        join(cloud_agent_dir, "src", "main", "python", "cloud_agent"),
        join(cloud_common_dir, "src", "main", "python"),
        join(cloud_common_dir, "src", "main", "python", "cloud_jinja2"),
        join(cloud_common_dir, "src", "test", "python"),
        join(cloud_common_dir, "src", "test", "python", "cloud_jinja2"),
        join(src_dir, "cloud-server", "src", "main", "resources", "common-services", 
             "HDFS", "2.1.0.2.0", "package", "files"),
        join(src_dir, "cloud-server", "src", "test", "python"),
        join(cloud_agent_dir, "src", "test", "python", "resource_management"),
        current_dir  # Add current directory last
    ]
    
    # Add to sys.path if they exist
    for path in paths:
        if exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            logging.debug(f"Added to PYTHONPATH: {path}")
    
    return paths

def configure_logging(log_path, verbosity=0):
    """Setup logging with console and file handlers
    
    verbosity levels:
    0 = WARNING (default)
    1 = INFO
    ‚â? = DEBUG
    """
    logger = logging.getLogger()
    
    # Set log level based on verbosity
    log_level = logging.WARNING
    if verbosity == 1:
        log_level = logging.INFO
    elif verbosity >= 2:
        log_level = logging.DEBUG
    logger.setLevel(log_level)
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create file handler
    os.makedirs(dirname(log_path), exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode='w')
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Create console handler with color
    console_handler = logging.StreamHandler()
    console_formatter = CustomFormatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Initialize resource_management logger
    Logger.initialize_logger(logging_level=logging.WARNING)
    
    return logger

def find_test_files(search_dir, pattern=None, recursive=True):
    """Discover test files matching criteria
    
    Args:
        search_dir: Directory to search
        pattern: Filename pattern (e.g. "Test*" or "test_file")
        recursive: Search subdirectories if True
        
    Returns:
        List of absolute paths to test files
    """
    test_files = []
    
    # Ensure search_dir exists
    if not exists(search_dir):
        logging.error(f"Search directory not found: {search_dir}")
        return []
    
    # Compile test file regex
    test_pattern = re.compile(TEST_FILE_PATTERN)
    
    # Handle recursive vs non-recursive search
    if recursive:
        for root, _, files in os.walk(search_dir):
            for file in files:
                if test_pattern.match(file) and (not pattern or fnmatch.fnmatch(file, pattern + '*')):
                    test_files.append(abspath(join(root, file)))
    else:
        for file in os.listdir(search_dir):
            if test_pattern.match(file) and (not pattern or fnmatch.fnmatch(file, pattern + '*')):
                test_files.append(abspath(join(search_dir, file)))
    
    return test_files

def load_tests(test_files):
    """Load tests from files
    
    Args:
        test_files: List of absolute paths to test files
        
    Returns:
        unittest.TestSuite containing all tests
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for file_path in test_files:
        # Make relative to current directory
        rel_path = os.path.relpath(file_path, os.getcwd())
        # Convert to module path (replace separators and remove .py)
        module_path = rel_path.replace(os.sep, '.')[:-3]
        
        try:
            logging.info(f"Loading tests from: {module_path}")
            module_tests = loader.loadTestsFromName(module_path)
            suite.addTest(module_tests)
        except Exception as e:
            logging.error(f"Failed to load tests from {file_path}: {e}")
    
    return suite

def run_tests(suite, verbosity=1):
    """Run test suite and return results
    
    Args:
        suite: unittest.TestSuite to execute
        verbosity: 0=quiet, 1=normal, 2=verbose
        
    Returns:
        Test result object
    """
    logging.info("\n" + "=" * 70)
    logging.info(f"RUNNING TESTS ({suite.countTestCases()} test cases)")
    logging.info("=" * 70 + "\n")
    
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        stream=sys.stdout,
        descriptions=True
    )
    
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time
    
    # Print summary
    logging.info("\n" + "=" * 70)
    if result.wasSuccessful():
        logging.info("‚ú?PASSED: All tests completed successfully")
    else:
        logging.error(f"‚ù?FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    
    logging.info(f"Tests: {suite.countTestCases()}")
    logging.info(f"Time:  {duration:.2f} seconds")
    logging.info("=" * 70)
    
    return result

def main():
    """Main entry point for test runner"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="cloud Agent Unit Test Runner",
        epilog="Example usage: python unitTests.py -v TestAgent"
    )
    parser.add_argument(
        "pattern", 
        nargs="?", 
        default=None,
        help="Test file pattern (e.g. 'TestFile' or 'TestClass')"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="count", 
        default=0,
        help="Verbosity level (use -v for info, -vv for debug)"
    )
    parser.add_argument(
        "-o", "--output", 
        default=None,
        help=f"Custom log file path (default: target/{LOG_FILE_NAME})"
    )
    parser.add_argument(
        "--no-recursion", 
        action="store_true",
        help="Disable recursive test discovery"
    )
    args = parser.parse_args()
    
    # Configure environment paths
    paths = setup_python_paths()
    
    # Calculate log file path
    current_dir = os.getcwd()
    # Find project's target directory (3 levels up from script)
    target_dir = join(current_dir, "..", "..", "..", "..", "target")
    log_path = args.output or join(target_dir, LOG_FILE_NAME)
    
    # Configure logging
    logger = configure_logging(log_path, args.verbose)
    
    # Log system info
    logger.info("=" * 70)
    logger.info("SHURDP AGENT UNIT TEST RUNNER")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Directory: {current_dir}")
    logger.info(f"Log file: {log_path}")
    logger.info("=" * 70)
    
    # Log configured paths
    logger.info("\nCONFIGURED PYTHON PATHS:")
    for path in paths:
        if exists(path):
            logger.info(f"  - {path}")
        else:
            logger.warning(f"  - {path} (MISSING)")
    
    # Test Discovery Settings
    logger.info("\nTEST DISCOVERY SETTINGS:")
    logger.info(f"Pattern:       {args.pattern or 'All tests'}")
    logger.info(f"Recursion:     {not args.no_recursion}")
    logger.info(f"Verbosity:     {args.verbose}")
    
    # 1. First look for SELECTED_PREFIX tests (debug mode)
    debug_tests = find_test_files(
        current_dir,
        pattern=f"{SELECTED_PREFIX}*",
        recursive=not args.no_recursion
    )
    
    if debug_tests:
        logger.info("\nDEBUG MODE: Running selected tests:")
        for test in debug_tests:
            logger.info(f"  - {basename(test)}")
        test_files = debug_tests
    elif args.pattern:
        # 2. Run tests matching the pattern
        logger.info(f"\nRunning tests matching pattern: '{args.pattern}'")
        test_files = find_test_files(
            current_dir,
            pattern=f"*{args.pattern}*",
            recursive=not args.no_recursion
        )
        
        if not test_files:
            logger.error("‚ù?ERROR: No matching tests found!")
            return 1
    else:
        # 3. Run all tests
        logger.info("\nRunning all discovered tests")
        test_files = find_test_files(
            current_dir, 
            recursive=not args.no_recursion
        )
        
        if not test_files:
            logger.error("‚ù?ERROR: No tests found!")
            return 1
    
    # Load and run tests
    suite = load_tests(test_files)
    result = run_tests(suite, verbosity=args.verbose + 1)  # +1 to match unittest's verbosity
    
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    # Set start time for total execution time
    start_time = time.time()
    
    # Run main and capture exit code
    exit_code = main()
    
    # Calculate and log total execution time
    duration = time.time() - start_time
    logging.info(f"Total execution time: {duration:.2f} seconds")
    
    # Exit with the appropriate status code
    if exit_code == 0:
        logging.info("=" * 70)
        logging.info("‚ú?TEST RUN COMPLETED SUCCESSFULLY")
        logging.info("=" * 70)
    else:
        logging.error("=" * 70)
        logging.error("‚ù?TEST RUN COMPLETED WITH ERRORS")
        logging.error("=" * 70)
    
    # Use platform-appropriate exit method
    if get_platform() == PLATFORM_WINDOWS:
        os._exit(exit_code)
    else:
        sys.exit(exit_code)
