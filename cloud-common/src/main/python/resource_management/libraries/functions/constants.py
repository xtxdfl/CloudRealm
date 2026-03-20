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

from enum import Enum, unique
from typing import Dict, Set

__all__ = ["Direction", "SafeMode", "StackFeature"]


class Direction(Enum):
    """
    Stack Upgrade direction constants
    """
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class SafeMode(Enum):
    """
    Namenode Safe Mode states
    """
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"


@unique
class StackFeature(Enum):
    """
    Enumerates all supported stack features with component categories
    for improved discoverability and maintenance.
    
    Features are grouped by components they affect:
      COMPRESSION - Data compression formats
      SECURITY - Security-related features
      UPGRADE - Stack upgrade capabilities
      COMPONENT - Component-specific functionalities
      INTEGRATION - Cross-component integrations
      CONFIG - Configuration management features
      OPTIMIZATION - Performance optimizations
      OPERATIONS - Operational capabilities
    
    Each feature maps to its implementation version in the stack.
    """
    # ========== COMPRESSION Features ========== 
    SNAPPY = ("snappy", "COMPRESSION")
    LZO = ("lzo", "COMPRESSION")
    
    # ========== UPGRADE Features ========== 
    EXPRESS_UPGRADE = ("express_upgrade", "UPGRADE")
    ROLLING_UPGRADE = ("rolling_upgrade", "UPGRADE")
    CONFIG_VERSIONING = ("config_versioning", "UPGRADE")
    COPY_TARBALL_TO_HDFS = ("copy_tarball_to_hdfs", "UPGRADE")
    
    # ========== SECURITY Features ========== 
    SECURE_ZOOKEEPER = ("secure_zookeeper", "SECURITY")
    DATANODE_NON_ROOT = ("datanode_non_root", "SECURITY")
    RANGER = ("ranger", "SECURITY")
    RANGER_TAGSYNC_COMPONENT = ("ranger_tagsync_component", "SECURITY")
    STORM_KERBEROS = ("storm_kerberos", "SECURITY")
    KAFKA_KERBEROS = ("kafka_kerberos", "SECURITY")
    RANGER_USERSYNC_NON_ROOT = ("ranger_usersync_non_root", "SECURITY")
    RANGER_AUDIT_DB_SUPPORT = ("ranger_audit_db_support", "SECURITY")
    ACCUMULO_KERBEROS_USER_AUTH = ("accumulo_kerberos_user_auth", "SECURITY")
    KNOX_SSO_TOPOLOGY = ("knox_sso_topology", "SECURITY")
    OOZIE_HOST_KERBEROS = ("oozie_host_kerberos", "SECURITY")
    HIVE_SERVER2_KERBERIZED_ENV = ("hive_server2_kerberized_env", "SECURITY")
    RANGER_KERBEROS_SUPPORT = ("ranger_kerberos_support", "SECURITY")
    SECURE_RANGER_SSL_PASSWORD = ("secure_ranger_ssl_password", "SECURITY")
    RANGER_KMS_SSL = ("ranger_kms_ssl", "SECURITY")
    KAFKA_EXTENDED_SASL_SUPPORT = ("kafka_extended_sasl_support", "SECURITY")
    
    # ========== COMPONENT Features ========== 
    FALCON_EXTENSIONS = ("falcon_extensions", "COMPONENT")
    HADOOP_CUSTOM_EXTENSIONS = ("hadoop_custom_extensions", "COMPONENT")
    PHOENIX = ("phoenix", "COMPONENT")
    NFS = ("nfs", "COMPONENT")
    TIMELINE_STATE_STORE = ("timeline_state_store", "COMPONENT")
    SPARK_16PLUS = ("spark_16plus", "COMPONENT")
    SPARK_THRIFTSERVER = ("spark_thriftserver", "COMPONENT")
    SPARK_LIVY = ("spark_livy", "COMPONENT")
    SPARK_LIVY2 = ("spark_livy2", "COMPONENT")
    STORM_AMS = ("storm_ams", "COMPONENT")
    OOZIE_ADMIN_USER = ("oozie_admin_user", "COMPONENT")
    HIVE_METASTORE_UPGRADE_SCHEMA = ("hive_metastore_upgrade_schema", "COMPONENT")
    HIVE_SERVER_INTERACTIVE = ("hive_server_interactive", "COMPONENT")
    HIVE_WEBHCAT_SPECIFIC_CONFIGS = ("hive_webhcat_specific_configs", "COMPONENT")
    HIVE_PURGE_TABLE = ("hive_purge_table", "COMPONENT")
    HIVE_ENV_HEAPSIZE = ("hive_env_heapsize", "COMPONENT")
    RANGER_KMS_HSM_SUPPORT = ("ranger_kms_hsm_support", "COMPONENT")
    RANGER_LOG4J_SUPPORT = ("ranger_log4j_support", "COMPONENT")
    RANGER_PID_SUPPORT = ("ranger_pid_support", "COMPONENT")
    RANGER_KMS_PID_SUPPORT = ("ranger_kms_pid_support", "COMPONENT")
    RANGER_ADMIN_PASSWD_CHANGE = ("ranger_admin_password_change", "COMPONENT")
    RANGER_SETUP_DB_ON_START = ("ranger_setup_db_on_start", "COMPONENT")
    SPARK_JAVA_OPTS_SUPPORT = ("spark_java_opts_support", "COMPONENT")
    KNOX_VERSIONED_DATA_DIR = ("knox_versioned_data_dir", "COMPONENT")
    RANGER_HIVE_PLUGIN_JDBC_URL = ("ranger_hive_plugin_jdbc_url", "COMPONENT")
    RANGER_TAGSYNC_SSL_XML_SUPPORT = ("ranger_tagsync_ssl_xml_support", "COMPONENT")
    OOZIE_EXTJS_INCLUDED = ("oozie_extjs_included", "COMPONENT")
    
    # ========== INTEGRATION Features ========== 
    PIG_ON_TEZ = ("pig_on_tez", "INTEGRATION")
    TEZ_FOR_SPARK = ("tez_for_spark", "INTEGRATION")
    HIVE_METASTORE_SITE_SUPPORT = ("hive_metastore_site_support", "INTEGRATION")
    HBASE_HOME_DIRECTORY = ("hbase_home_directory", "INTEGRATION")
    ATLAS_RANGER_PLUGIN_SUPPORT = ("atlas_ranger_plugin_support", "INTEGRATION")
    ATLAS_HOOK_SUPPORT = ("atlas_hook_support", "INTEGRATION")
    FALCON_ATLAS_SUPPORT_2_3 = ("falcon_atlas_support_2_3", "INTEGRATION")
    FALCON_ATLAS_SUPPORT = ("falcon_atlas_support", "INTEGRATION")
    STORM_METRICS_APACHE_CLASSES = ("storm_metrics_apache_classes", "INTEGRATION")
    ATLAS_HBASE_SETUP = ("atlas_hbase_setup", "INTEGRATION")
    KAFKA_RANGER_PLUGIN_SUPPORT = ("kafka_ranger_plugin_support", "INTEGRATION")
    YARN_RANGER_PLUGIN_SUPPORT = ("yarn_ranger_plugin_support", "INTEGRATION")
    HIVE_INTERACTIVE_ATLAS_HOOK_REQUIRED = ("hive_interactive_atlas_hook_required", "INTEGRATION")
    ATLAS_INSTALL_HOOK_PACKAGE_SUPPORT = ("atlas_install_hook_package_support", "INTEGRATION")
    ATLAS_CORE_SITE_SUPPORT = ("atlas_core_site_support", "INTEGRATION")
    AMS_LEGACY_HADOOP_SINK = ("ams_legacy_hadoop_sink", "INTEGRATION")
    
    # ========== CONFIG Features ========== 
    REMOVE_RANGER_HDFS_PLUGIN_ENV = ("remove_ranger_hdfs_plugin_env", "CONFIG")
    KAFKA_LISTENERS = ("kafka_listeners", "CONFIG")
    RANGER_USERSYNC_PASSWORD_JCEKS = ("ranger_usersync_password_jceks", "CONFIG")
    RANGER_INSTALL_INFRA_CLIENT = ("ranger_install_infra_client", "CONFIG")
    ATLAS_UPGRADE_SUPPORT = ("atlas_upgrade_support", "CONFIG")
    ATLAS_CONF_DIR_IN_PATH = ("atlas_conf_dir_in_path", "CONFIG")
    OOZIE_CREATE_HIVE_TEZ_CONFIGS = ("oozie_create_hive_tez_configs", "CONFIG")
    OOZIE_SETUP_SHARED_LIB = ("oozie_setup_shared_lib", "CONFIG")
    ZKFC_VERSION_ADVERTISED = ("zkfc_version_advertised", "CONFIG")
    PHOENIX_CORE_HDFS_SITE_REQUIRED = ("phoenix_core_hdfs_site_required", "CONFIG")
    RANGER_XML_CONFIGURATION = ("ranger_xml_configuration", "CONFIG")
    RANGER_SOLR_CONFIG_SUPPORT = ("ranger_solr_config_support", "CONFIG")
    CORE_SITE_FOR_RANGER_PLUGINS_SUPPORT = ("core_site_for_ranger_plugins", "CONFIG")
    ATLAS_HDFS_SITE_ON_NAMENODE_HA = ("atlas_hdfs_site_on_namenode_ha", "CONFIG")
    KAFKA_ENV_INCLUDE_RANGER_SCRIPT = ("kafka_env_include_ranger_script", "CONFIG")
    MULTIPLE_ENV_SH_FILES_SUPPORT = ("multiple_env_sh_files_support", "CONFIG")
    
    # ========== OPTIMIZATION Features ========== 
    KAFKA_ACL_MIGRATION_SUPPORT = ("kafka_acl_migration_support", "OPTIMIZATION")
    HIVE_INTERACTIVE_GA_SUPPORT = ("hive_interactive_ga", "OPTIMIZATION")
    
    # ========== OPERATIONS Features ========== 
    RANGER_SUPPORT_SECURITY_ZONE_FEATURE = ("ranger_support_security_zone_feature", "OPERATIONS")
    RANGER_ALL_ADMIN_CHANGE_DEFAULT_PASSWORD = ("ranger_all_admin_change_default_password", "OPERATIONS")

    def __init__(self, feature_name: str, category: str):
        """
        Initialize a stack feature with its metadata
        
        :param feature_name: Unique identifier for the feature
        :param category: Functional category for grouping
        """
        self._feature_name = feature_name
        self._category = category

    @property
    def feature_name(self) -> str:
        """Get the unique feature identifier"""
        return self._feature_name

    @property
    def category(self) -> str:
        """Get the functional category of the feature"""
        return self._category

    def __str__(self):
        """String representation of the feature"""
        return self.feature_name

    @classmethod
    def get_all_features(cls) -> Dict[str, 'StackFeature']:
        """Get all features as a name-to-object mapping"""
        return {feature.name: feature for feature in cls}

    @classmethod
    def get_features_by_category(cls, category: str) -> Set['StackFeature']:
        """Get all features belonging to a specific category"""
        return {feature for feature in cls if feature.category == category}

    @classmethod
    def is_supported(cls, feature_name: str) -> bool:
        """Check if a specific feature is supported"""
        return feature_name in cls._member_map_


# Feature Category Constants for Simplified Access
CATEGORIES = {
    "COMPRESSION": StackFeature.get_features_by_category("COMPRESSION"),
    "SECURITY": StackFeature.get_features_by_category("SECURITY"),
    "UPGRADE": StackFeature.get_features_by_category("UPGRADE"),
    "COMPONENT": StackFeature.get_features_by_category("COMPONENT"),
    "INTEGRATION": StackFeature.get_features_by_category("INTEGRATION"),
    "CONFIG": StackFeature.get_features_by_category("CONFIG"),
    "OPTIMIZATION": StackFeature.get_features_by_category("OPTIMIZATION"),
    "OPERATIONS": StackFeature.get_features_by_category("OPERATIONS"),
}

# Compatibility Layer for Existing Code (if needed)
__legacy_mapping = {feature.name: feature.feature_name for feature in StackFeature}

