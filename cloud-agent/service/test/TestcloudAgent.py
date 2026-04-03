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

import unittest
import subprocess
import os
import sys
import cloudConfig
from mock.mock import MagicMock, patch, ANY

# Mock distro.linux_distribution to control OS detection
with patch("distro.linux_distribution", return_value=("Suse", "11", "Final")):
    # Import cloud_agent after patching distro
    from cloud_agent import cloudAgent


class TestcloudAgent(unittest.TestCase):
    """
    Unit tests for cloudAgent functionality including:
    - Main execution flow
    - Log file configuration
    - Output file configuration
    """

    @patch.object(subprocess, "Popen")
    @patch("os.path.isfile")
    @patch("os.remove")
    def test_main(self, os_remove_mock, os_path_isfile_mock, subprocess_popen_mock):
        """
        Test the main execution flow of cloudAgent
        - Simulates subprocess execution
        - Verifies file presence checks and cleanup
        - Validates environment variable handling
        """
        
        # Setup mock objects
        facter1 = MagicMock()
        facter2 = MagicMock()
        
        # Configure mock behaviors
        subprocess_popen_mock.side_effect = [facter1, facter2]
        facter1.returncode = 77
        facter2.returncode = 55
        os_path_isfile_mock.return_value = True
        
        # Set environment variable for test
        if "PYTHON" not in os.environ:
            os.environ["PYTHON"] = "test/python/path"
        
        # Set command line argument
        sys.argv[0] = "test/data"
        
        # Execute method under test
        cloudAgent.main()
        
        # Verify subprocess calls
        self.assertTrue(subprocess_popen_mock.called)
        self.assertEqual(subprocess_popen_mock.call_count, 2)
        
        # Verify process communication
        self.assertTrue(facter1.communicate.called)
        self.assertTrue(facter2.communicate.called)
        
        # Verify file existence checks
        self.assertTrue(os_path_isfile_mock.called)
        self.assertEqual(os_path_isfile_mock.call_count, 2)
        
        # Verify cleanup operations
        self.assertTrue(os_remove_mock.called)

    def test_logfile_location(self):
        """
        Test cloudConfig.getLogFile() for cloud-agent
        - Validates both default and custom log locations
        - Tests environment variable override
        """
        # Default log configuration
        log_folder = "/var/log/cloud-agent"
        log_file = "cloud-agent.log"
        
        # Test without custom log dir (default behavior)
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                os.path.join(log_folder, log_file), 
                cloudConfig.cloudConfig.getLogFile()
            )
        
        # Test with custom log dir environment variable
        custom_log_folder = "/myloglocation/log"
        with patch.dict("os.environ", {"cloud_AGENT_LOG_DIR": custom_log_folder}):
            self.assertEqual(
                os.path.join(custom_log_folder, log_file), 
                cloudConfig.cloudConfig.getLogFile()
            )

    def test_outfile_location(self):
        """
        Test cloudConfig.getOutFile() for cloud-agent
        - Validates both default and custom output locations
        - Tests environment variable override
        """
        # Default output configuration
        out_folder = "/var/log/cloud-agent"
        out_file = "cloud-agent.out"
        
        # Test without custom output location (default behavior)
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                os.path.join(out_folder, out_file), 
                cloudConfig.cloudConfig.getOutFile()
            )
        
        # Test with custom output directory
        # NOTE: Using cloud_AGENT_LOG_DIR for cloud_AGENT_OUT_DIR here seems like an error
        custom_out_folder = "/myoutlocation/out"
        with patch.dict("os.environ", {"cloud_AGENT_LOG_DIR": custom_out_folder}):
            self.assertEqual(
                os.path.join(custom_out_folder, out_file), 
                cloudConfig.cloudConfig.getOutFile()
            )
            
        # Additional test with properly named environment variable
        # (Added as an improvement suggestion)
        with patch.dict("os.environ", {"cloud_AGENT_OUT_DIR": custom_out_folder}):
            self.assertEqual(
                os.path.join(custom_out_folder, out_file), 
                cloudConfig.cloudConfig.getOutFile()
            )

if __name__ == "__main__":
    unittest.main()
