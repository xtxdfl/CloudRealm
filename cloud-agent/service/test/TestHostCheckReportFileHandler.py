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
"""

from unittest import TestCase
import unittest
from mock.mock import patch
import os
import tempfile
from HostCheckReportFileHandler import HostCheckReportFileHandler
import logging
import configparser


class TestHostCheckReportFileHandler(TestCase):
    """Unit tests for HostCheckReportFileHandler functionality"""
    
    # Initialize logger
    logger = logging.getLogger()

    def test_write_host_check_report_really_empty(self):
        """Test writing completely empty host check report"""
        # Create temporary file for testing
        tmpfile = tempfile.mktemp()
        
        # Set up configuration
        config = configparser.RawConfigParser()
        config.add_section("agent")
        config.set("agent", "prefix", os.path.dirname(tmpfile))  # Set test directory path
        
        # Create handler instance
        handler = HostCheckReportFileHandler(config)
        
        # Write empty report
        handler.writeHostCheckFile({})
        
        # Validate written report
        configValidator = configparser.RawConfigParser()
        configPath = os.path.join(
            os.path.dirname(tmpfile), 
            HostCheckReportFileHandler.HOST_CHECK_FILE
        )
        configValidator.read(configPath)
        
        # Verify users section exists and is empty
        if configValidator.has_section("users"):
            users = configValidator.get("users", "usr_list")
            self.assertEqual(users, "")  # Should be empty

    @patch("os.path.exists")
    @patch("os.listdir")
    def test_write_host_check_report_empty(self, list_mock, exists_mock):
        """Test writing host check report with empty sections"""
        # Set up mock environment
        tmpfile = tempfile.mktemp()
        exists_mock.return_value = False  # Simulate no existing directories
        list_mock.return_value = []  # Simulate empty directories
        
        # Set up configuration
        config = configparser.RawConfigParser()
        config.add_section("agent")
        config.set("agent", "prefix", os.path.dirname(tmpfile))
        
        # Create handler instance
        handler = HostCheckReportFileHandler(config)
        
        # Prepare minimal test data with empty sections
        mydict = {
            "hostHealth": {"activeJavaProcs": []},
            "existingUsers": [],
            "alternatives": [],
            "stackFoldersAndFiles": [],
            "installedPackages": [],
            "existingRepos": []
        }
        
        # Write report
        handler.writeHostCheckFile(mydict)
        
        # Validate written report
        configValidator = configparser.RawConfigParser()
        configPath = os.path.join(
            os.path.dirname(tmpfile), 
            HostCheckReportFileHandler.HOST_CHECK_FILE
        )
        configValidator.read(configPath)
        
        # Verify users section
        users = configValidator.get("users", "usr_list")
        homedirs = configValidator.get("users", "usr_homedir_list")
        self.assertEqual(users, "")
        self.assertEqual(homedirs, "")
        
        # Verify alternatives section
        names = configValidator.get("alternatives", "symlink_list")
        targets = configValidator.get("alternatives", "target_list")
        self.assertEqual(names, "")
        self.assertEqual(targets, "")
        
        # Verify directories section
        paths = configValidator.get("directories", "dir_list")
        self.assertEqual(paths, "")
        
        # Verify processes section
        procs = configValidator.get("processes", "proc_list")
        self.assertEqual(procs, "")
        
        # Verify metadata section has creation time
        time_val = configValidator.get("metadata", "created")
        self.assertIsNotNone(time_val)

    @patch("os.path.exists")
    @patch("os.listdir")
    def test_write_host_check_report(self, list_mock, exists_mock):
        """Test writing host check report with sample data"""
        # Set up mock environment
        tmpfile = tempfile.mktemp()
        exists_mock.return_value = False
        list_mock.return_value = []
        
        # Set up configuration
        config = configparser.RawConfigParser()
        config.add_section("agent")
        config.set("agent", "prefix", os.path.dirname(tmpfile))
        
        # Create handler instance
        handler = HostCheckReportFileHandler(config)
        
        # Prepare sample report data
        mydict = {
            "hostHealth": {
                "activeJavaProcs": [
                    {"pid": 355, "hadoop": True, "command": "some command", "user": "root"},
                    {"pid": 455, "hadoop": True, "command": "some command", "user": "hdfs"}
                ]
            },
            "existingUsers": [{"name": "user1", "homeDir": "/var/log", "status": "Exists"}],
            "alternatives": [
                {"name": "/etc/alternatives/hadoop-conf", "target": "/etc/hadoop/conf.dist"},
                {"name": "/etc/alternatives/hbase-conf", "target": "/etc/hbase/conf.1"}
            ],
            "stackFoldersAndFiles": [
                {"name": "/a/b", "type": "directory"},
                {"name": "/a/b.txt", "type": "file"}
            ],
            "installed_packages": [  # Note corrected key
                {"name": "hadoop", "version": "3.2.3", "repoName": "HDP"},
                {"name": "hadoop-lib", "version": "3.2.3", "repoName": "HDP"}
            ],
            "existing_repos": ["HDP", "HDP-epel"]  # Note corrected key
        }
        
        # Write host check file
        handler.writeHostCheckFile(mydict)
        
        # Validate host check file
        configValidator = configparser.RawConfigParser()
        configPath = os.path.join(
            os.path.dirname(tmpfile), 
            HostCheckReportFileHandler.HOST_CHECK_FILE
        )
        configValidator.read(configPath)
        
        # Verify users section
        users = configValidator.get("users", "usr_list")
        homedirs = configValidator.get("users", "usr_homedir_list")
        self.assertEqual(users, "user1")
        self.assertEqual(homedirs, "/var/log")
        
        # Verify alternatives section
        names = configValidator.get("alternatives", "symlink_list")
        targets = configValidator.get("alternatives", "target_list")
        self.chkItemsEqual(
            names, 
            ["/etc/alternatives/hadoop-conf", "/etc/alternatives/hbase-conf"]
        )
        self.chkItemsEqual(
            targets, 
            ["/etc/hadoop/conf.dist", "/etc/hbase/conf.1"]
        )
        
        # Verify directories section
        paths = configValidator.get("directories", "dir_list")
        self.chkItemsEqual(paths, ["/a/b", "/a/b.txt"])
        
        # Verify processes section
        procs = configValidator.get("processes", "proc_list")
        self.chkItemsEqual(procs, ["455", "355"])
        
        # Write custom actions file
        handler.writeHostChecksCustomActionsFile(mydict)
        
        # Validate custom actions file
        configValidator = configparser.RawConfigParser()
        configPath_ca = os.path.join(
            os.path.dirname(tmpfile),
            HostCheckReportFileHandler.HOST_CHECK_CUSTOM_ACTIONS_FILE
        )
        configValidator.read(configPath_ca)
        
        # Verify packages section
        pkgs = configValidator.get("packages", "pkg_list")
        self.chkItemsEqual(pkgs, ["hadoop", "hadoop-lib"])
        
        # Verify repositories section
        repos = configValidator.get("repositories", "repo_list")
        self.chkItemsEqual(repos, ["HDP", "HDP-epel"])
        
        # Verify metadata section has creation time
        time_val = configValidator.get("metadata", "created")
        self.assertIsNotNone(time_val)

    @patch("os.path.exists")
    @patch("os.listdir")
    def test_write_host_stack_list(self, list_mock, exists_mock):
        """Test writing directories with stack list"""
        # Set up mock environment with existing HDP directories
        exists_mock.return_value = True
        list_mock.return_value = ["1.1.1.1-1234", "current", "test"]
        
        tmpfile = tempfile.mktemp()
        
        # Set up configuration
        config = configparser.RawConfigParser()
        config.add_section("agent")
        config.set("agent", "prefix", os.path.dirname(tmpfile))
        
        # Create handler instance
        handler = HostCheckReportFileHandler(config)
        
        # Prepare test data with directories
        mydict = {
            "hostHealth": {},
            "stackFoldersAndFiles": [
                {"name": "/a/b", "type": "directory"},
                {"name": "/a/b.txt", "type": "file"}
            ]
        }
        
        # Write report
        handler.writeHostCheckFile(mydict)
        
        # Validate written report
        configValidator = configparser.RawConfigParser()
        configPath = os.path.join(
            os.path.dirname(tmpfile), 
            HostCheckReportFileHandler.HOST_CHECK_FILE
        )
        configValidator.read(configPath)
        
        # Verify directories section includes auto-discovered HDP paths
        paths = configValidator.get("directories", "dir_list")
        self.chkItemsEqual(
            paths, 
            [
                "/a/b", 
                "/a/b.txt", 
                "/usr/hdp/1.1.1.1-1234", 
                "/usr/hdp/current"
            ]
        )

    def chkItemsEqual(self, commaDelimited, expectedItems):
        """
        Helper method to compare comma-delimited strings with expected item lists
        Normalizes order for comparison
        """
        # Convert comma-delimited string to sorted list
        items1 = sorted(commaDelimited.split(","))
        # Sort expected items
        items2 = sorted(expectedItems)
        # Join for display
        items1_str = ",".join(items1)
        items2_str = ",".join(items2)
        # Assert equality
        self.assertEqual(items2_str, items1_str)


if __name__ == "__main__":
    # Run tests with increased verbosity
    unittest.main(verbosity=2)
