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

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.

cloud Agent Configuration Fetcher

Optimized version for safe configuration retrieval
"""

from resource_management.core.logger import Logger

__all__ = ["get_config"]

def get_config(config_type, default=None):
    """
    Safely retrieves configuration of the specified type
    
    :param config_type:   Configuration type (e.g., 'hdfs-site', 'core-site')
    :param default:       Default value if config not found
    :return:              Configuration dict or default value
    """
    import params
    
    # Quick path for missing config registry
    if not params.config:
        Logger.warning("[ConfigError] No service configurations available. Using default for: %s" % config_type)
        return default
        
    # Get all configurations section
    all_configs = params.config.get("configurations")
    if not all_configs:
        Logger.warning("[ConfigError] No 'configurations' section found. Using default for: %s" % config_type)
        return default
    
    # Get requested configuration type
    config = all_configs.get(config_type)
    
    if config is None:
        Logger.warning(
            "[ConfigError] Configuration type '%s' not found. Available types: %s. Using default." % 
            (config_type, ", ".join(all_configs.keys()) if all_configs else "None")
        )
        return default
    
    # Enable debug logging if needed
    if Logger.is_debug_enabled():
        Logger.debug("[ConfigDebug] Retrieved configuration for %s: %d parameters" % 
                    (config_type, len(config)))
    
    return config
