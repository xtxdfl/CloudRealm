#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import enum
from typing import Final


# =====================
# Paths and Binaries
# =====================
SUDO_BINARY: Final[str] = "cloud-sudo.sh"
"""Path to the Sudo wrapper script for privilege escalation"""

AGENT_TEMP_DIR: Final[str] = "/var/lib/cloud-agent/tmp"
"""Temporary directory for cloud-agent operations"""

LOGFEEDER_CONF_DIR: Final[str] = "/usr/lib/cloud-logsearch-logfeeder/conf"
"""Directory path for Logfeeder configuration files"""


# =====================
# Upgrade Types
# =====================
class UpgradeType(enum.Enum):
    """Supported cluster upgrade strategies"""
    ROLLING = "rolling"
    NON_ROLLING = "nonrolling"
    HOST_ORDERED = "host_ordered"

    @classmethod
    def all_types(cls):
        """Get all valid upgrade types as a tuple"""
        return tuple(m.value for m in cls)


# =====================
# Service Definitions
# =====================
class Service(enum.Enum):
    """Core cloud service identifiers"""
    ATLAS = "ATLAS"
    FALCON = "FALCON"
    FLUME = "FLUME"
    HAWQ = "HAWQ"
    HDFS = "HDFS"
    HIVE = "HIVE"
    KAFKA = "KAFKA"
    KNOX = "KNOX"
    MAHOUT = "MAHOUT"
    OOZIE = "OOZIE"
    PIG = "PIG"
    PXF = "PXF"
    RANGER = "RANGER"
    SLIDER = "SLIDER"
    SPARK = "SPARK"
    SQOOP = "SQOOP"
    STORM = "STORM"
    TEZ = "TEZ"
    YARN = "YARN"
    ZEPPELIN = "ZEPPELIN"
    ZOOKEEPER = "ZOOKEEPER"
    HBASE = "HBASE"
    
    @property
    def config_dir(self) -> str:
        """Default configuration directory for the service"""
        return f"/etc/{self.value.lower()}/conf"
        
    @property
    def log_dir(self) -> str:
        """Default log directory for the service"""
        return f"/var/log/{self.value.lower()}"


# ====================
# Metadata Constants
# ====================
__version_info__ = (1, 3, 0)
__version__ = ".".join(map(str, __version_info__))
__author__ = "Apache cloud Team"
__license__ = "Apache License 2.0"
