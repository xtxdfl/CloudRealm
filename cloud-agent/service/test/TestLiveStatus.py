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
from LiveStatus import LiveStatus
from cloudConfig import cloudConfig
import os
import sys
import io
from cloud_agent import ActualConfigHandler
from mock.mock import patch, MagicMock
import pprint
from cloud_commons import OSCheck
from only_for_platform import os_distro_value  # 假定有这个模?

class TestLiveStatus(TestCase):
    """Unit tests for LiveStatus class functionality"""

    def setUp(self):
        """Initial test setup"""
        # Disable stdout during tests to avoid clutter
        out = io.StringIO()
        sys.stdout = out

    def tearDown(self):
        """Cleanup after tests complete"""
        # Restore standard stdout
        sys.stdout = sys.__stdout__

    @patch.object(OSCheck, "os_distribution", new=MagicMock(return_value=os_distro_value))
    @patch.object(ActualConfigHandler.ActualConfigHandler, "read_actual_component")
    def test_build_predefined(self, read_actual_component_mock):
        """
        Test building LiveStatus with predefined parameters (without status checks)
        - Verifies configuration handling
        - Tests status structure population
        - Checks component tag retrieval
        """
        # Setup mock return values
        read_actual_component_mock.return_value = "actual_component"
        
        # Create configuration object
        config = cloudConfig().getConfig()
        # Set the agent prefix to a dummy directory
        config.set("agent", "prefix", os.path.join("cloud_agent", "dummy_files"))
        
        # Create LiveStatus instance
        livestatus = LiveStatus(
            "", 
            "SOME_UNKNOWN_SERVICE", 
            "SOME_UNKNOWN_COMPONENT", 
            {}, 
            config, 
            {}
        )
        
        # Build the status structure with predefined "STARTED" status
        result = livestatus.build(component_status="STARTED")
        # Format result for comparison
        result_str = pprint.pformat(result)
        
        # Validate the constructed status information
        expected_result = (
            "{'clusterName': '',\n "
            "'componentName': 'SOME_UNKNOWN_COMPONENT',\n "
            "'configurationTags': 'actual_component',\n "
            "'msg': '',\n 'serviceName': 'SOME_UNKNOWN_SERVICE',\n "
            "'stackVersion': '',\n 'status': 'STARTED'}"
        )
        
        self.assertEqual(result_str, expected_result)


if __name__ == "__main__":
    # Execute all tests when run directly
    unittest.main()
