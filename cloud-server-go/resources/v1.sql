-- Cloud Database Schema v1.sql
-- Generated from existing cloud database

SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS adminpermission;
CREATE TABLE `adminpermission` (
  `permission_id` bigint(20) NOT NULL,
  `permission_label` varchar(255) DEFAULT NULL,
  `permission_name` varchar(255) DEFAULT NULL,
  `principal_id` bigint(20) DEFAULT NULL,
  `resource_type_id` int(11) DEFAULT NULL,
  `sort_order` int(11) DEFAULT NULL,
  PRIMARY KEY (`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS adminprincipal;
CREATE TABLE `adminprincipal` (
  `principal_id` bigint(20) NOT NULL,
  `principal_type_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`principal_id`),
  KEY `FKr6i8i2ay4w55vcqd6xhscgecs` (`principal_type_id`),
  CONSTRAINT `FKr6i8i2ay4w55vcqd6xhscgecs` FOREIGN KEY (`principal_type_id`) REFERENCES `adminprincipaltype` (`principal_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS adminprincipaltype;
CREATE TABLE `adminprincipaltype` (
  `principal_type_id` int(11) NOT NULL,
  `principal_type_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`principal_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS adminresourcetype;
CREATE TABLE `adminresourcetype` (
  `resource_type_id` int(11) NOT NULL,
  `resource_type` varchar(255) DEFAULT NULL,
  `resource_type_label` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`resource_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS agent_version;
CREATE TABLE `agent_version` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `create_time` bigint(20) DEFAULT NULL,
  `description` text,
  `download_url` varchar(255) DEFAULT NULL,
  `file_hash` varchar(128) DEFAULT NULL,
  `file_size` bigint(20) DEFAULT NULL,
  `is_active` int(11) DEFAULT NULL,
  `is_latest` int(11) DEFAULT NULL,
  `package_path` varchar(255) NOT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  `version` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `UK_gdcf9r4tt350plfx1cyg42v4m` (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS cluster_service;
CREATE TABLE `cluster_service` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_id` bigint(20) NOT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `modified_time` bigint(20) DEFAULT NULL,
  `service_enabled` int(11) DEFAULT NULL,
  `service_name` varchar(255) NOT NULL,
  `service_type` varchar(255) NOT NULL,
  `service_version` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS clusters;
CREATE TABLE `clusters` (
  `cluster_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_info` varchar(255) NOT NULL,
  `cluster_name` varchar(100) NOT NULL,
  `desired_cluster_state` varchar(255) NOT NULL,
  `desired_stack_id` bigint(20) NOT NULL,
  `provisioning_state` varchar(255) NOT NULL,
  `resource_id` bigint(20) NOT NULL,
  `security_type` varchar(32) NOT NULL,
  `upgrade_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`cluster_id`),
  UNIQUE KEY `UK_egoyg2oiovhefj3q1nrem7y5` (`cluster_name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS config_history;
CREATE TABLE `config_history` (
  `id` binary(16) NOT NULL,
  `change_summary` varchar(255) DEFAULT NULL,
  `changed_fields` varchar(255) DEFAULT NULL,
  `config_file` varchar(255) NOT NULL,
  `content` varchar(255) DEFAULT NULL,
  `created_at` datetime(6) DEFAULT NULL,
  `is_current` bit(1) DEFAULT NULL,
  `operator` varchar(255) DEFAULT NULL,
  `service_name` varchar(255) NOT NULL,
  `version` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS config_template;
CREATE TABLE `config_template` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `config_content` text NOT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `description` text,
  `is_default` int(11) DEFAULT NULL,
  `service_name` varchar(255) NOT NULL,
  `template_name` varchar(255) NOT NULL,
  `template_type` varchar(255) NOT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  `version` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS data_asset_catalog;
CREATE TABLE `data_asset_catalog` (
  `asset_id` bigint(20) NOT NULL,
  `catalog_id` bigint(20) NOT NULL,
  `assigned_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`asset_id`,`catalog_id`),
  KEY `FKqceqx9dpujhffwfxw95by5vwg` (`catalog_id`),
  CONSTRAINT `FKdha6bxhjy2bnkuemhn2ls3d6a` FOREIGN KEY (`asset_id`) REFERENCES `data_assets` (`asset_id`),
  CONSTRAINT `FKqceqx9dpujhffwfxw95by5vwg` FOREIGN KEY (`catalog_id`) REFERENCES `data_catalogs` (`catalog_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS data_assets;
CREATE TABLE `data_assets` (
  `asset_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `asset_name` varchar(255) NOT NULL,
  `asset_type` varchar(255) NOT NULL,
  `column_name` varchar(255) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `data_format` varchar(255) DEFAULT NULL,
  `database_name` varchar(255) DEFAULT NULL,
  `description` text,
  `engine` varchar(255) DEFAULT NULL,
  `is_partitioned` bit(1) DEFAULT NULL,
  `last_access_time` bigint(20) DEFAULT NULL,
  `location` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `partition_columns` varchar(255) DEFAULT NULL,
  `quality_score` decimal(38,2) DEFAULT NULL,
  `record_count` bigint(20) DEFAULT NULL,
  `schema_name` varchar(255) DEFAULT NULL,
  `size_bytes` bigint(20) DEFAULT NULL,
  `storage_path` varchar(255) DEFAULT NULL,
  `table_name` varchar(255) DEFAULT NULL,
  `tags` varchar(255) DEFAULT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`asset_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS data_catalogs;
CREATE TABLE `data_catalogs` (
  `catalog_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `catalog_name` varchar(255) NOT NULL,
  `catalog_type` varchar(255) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `is_public` bit(1) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `parent_id` bigint(20) DEFAULT NULL,
  `sort_order` int(11) DEFAULT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`catalog_id`),
  UNIQUE KEY `UK_89672meagswl5ssbr7f5insj1` (`catalog_name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS data_lineage;
CREATE TABLE `data_lineage` (
  `lineage_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `created_time` bigint(20) DEFAULT NULL,
  `is_active` bit(1) DEFAULT NULL,
  `lineage_type` varchar(255) NOT NULL,
  `source_asset_id` bigint(20) NOT NULL,
  `target_asset_id` bigint(20) NOT NULL,
  `transform_expression` text,
  `transform_type` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`lineage_id`),
  KEY `FK86xullp71xcr5cwxu6aokr51m` (`source_asset_id`),
  KEY `FKmhm0e8svdg6e7wcd3acotew5w` (`target_asset_id`),
  CONSTRAINT `FK86xullp71xcr5cwxu6aokr51m` FOREIGN KEY (`source_asset_id`) REFERENCES `data_assets` (`asset_id`),
  CONSTRAINT `FKmhm0e8svdg6e7wcd3acotew5w` FOREIGN KEY (`target_asset_id`) REFERENCES `data_assets` (`asset_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS data_quality_results;
CREATE TABLE `data_quality_results` (
  `result_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `asset_id` bigint(20) NOT NULL,
  `check_status` varchar(255) NOT NULL,
  `check_time` bigint(20) NOT NULL,
  `duration_ms` int(11) DEFAULT NULL,
  `error_details` text,
  `executed_by` varchar(255) DEFAULT NULL,
  `invalid_records` bigint(20) DEFAULT NULL,
  `rule_id` bigint(20) NOT NULL,
  `total_records` bigint(20) DEFAULT NULL,
  `valid_percentage` decimal(38,2) DEFAULT NULL,
  `valid_records` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`result_id`),
  KEY `FKaq1qn5lf5rb03k2qqwx8blvxn` (`asset_id`),
  KEY `FKp5ctqm7spqb441qw4uyc9y2yc` (`rule_id`),
  CONSTRAINT `FKaq1qn5lf5rb03k2qqwx8blvxn` FOREIGN KEY (`asset_id`) REFERENCES `data_assets` (`asset_id`),
  CONSTRAINT `FKp5ctqm7spqb441qw4uyc9y2yc` FOREIGN KEY (`rule_id`) REFERENCES `data_quality_rules` (`rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS data_quality_rules;
CREATE TABLE `data_quality_rules` (
  `rule_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `created_by` varchar(255) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `is_enabled` bit(1) DEFAULT NULL,
  `last_run_status` varchar(255) DEFAULT NULL,
  `last_run_time` bigint(20) DEFAULT NULL,
  `rule_definition` text NOT NULL,
  `rule_name` varchar(255) NOT NULL,
  `rule_params` varchar(255) DEFAULT NULL,
  `rule_type` varchar(255) NOT NULL,
  `schedule_cron` varchar(255) DEFAULT NULL,
  `severity` varchar(255) DEFAULT NULL,
  `target_asset_id` bigint(20) NOT NULL,
  `target_column` varchar(255) DEFAULT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`rule_id`),
  KEY `FKrsgaxf4y09e3m7kxsn020ohao` (`target_asset_id`),
  CONSTRAINT `FKrsgaxf4y09e3m7kxsn020ohao` FOREIGN KEY (`target_asset_id`) REFERENCES `data_assets` (`asset_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS exporter_metadata;
CREATE TABLE `exporter_metadata` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `config_template` text,
  `create_time` bigint(20) DEFAULT NULL,
  `dependencies` text,
  `description` text,
  `download_url` varchar(255) DEFAULT NULL,
  `exporter_name` varchar(255) NOT NULL,
  `exporter_version` varchar(255) NOT NULL,
  `file_hash` varchar(128) DEFAULT NULL,
  `file_size` bigint(20) DEFAULT NULL,
  `is_active` int(11) DEFAULT NULL,
  `package_name` varchar(255) NOT NULL,
  `package_path` varchar(255) NOT NULL,
  `ports` varchar(100) DEFAULT NULL,
  `service_name` varchar(255) NOT NULL,
  `service_type` varchar(255) NOT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_metadata;
CREATE TABLE `host_metadata` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `agent_version` varchar(50) DEFAULT NULL,
  `cpu_cores` int(11) DEFAULT NULL,
  `cpu_count` int(11) DEFAULT NULL,
  `cpu_model` varchar(255) DEFAULT NULL,
  `cpu_usage` double DEFAULT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `disk_count` int(11) DEFAULT NULL,
  `disk_usage` double DEFAULT NULL,
  `free_disk` bigint(20) DEFAULT NULL,
  `free_memory` bigint(20) DEFAULT NULL,
  `host_id` bigint(20) NOT NULL,
  `host_name` varchar(255) DEFAULT NULL,
  `hostname` varchar(255) DEFAULT NULL,
  `java_version` varchar(50) DEFAULT NULL,
  `kernel_version` varchar(100) DEFAULT NULL,
  `last_heartbeat` bigint(20) DEFAULT NULL,
  `mac_address` varchar(100) DEFAULT NULL,
  `memory_usage` double DEFAULT NULL,
  `metadata_json` text,
  `network_interfaces` text,
  `network_traffic_in` bigint(20) DEFAULT NULL,
  `network_traffic_out` bigint(20) DEFAULT NULL,
  `os_arch` varchar(50) DEFAULT NULL,
  `os_type` varchar(50) DEFAULT NULL,
  `os_version` varchar(100) DEFAULT NULL,
  `private_ip` varchar(50) DEFAULT NULL,
  `public_ip` varchar(50) DEFAULT NULL,
  `total_disk` bigint(20) DEFAULT NULL,
  `total_memory` bigint(20) DEFAULT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  `uptime` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_operation_log;
CREATE TABLE `host_operation_log` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `created_time` bigint(20) NOT NULL,
  `duration_ms` bigint(20) DEFAULT NULL,
  `error_message` varchar(1000) DEFAULT NULL,
  `host_id` bigint(20) DEFAULT NULL,
  `host_ip` varchar(255) DEFAULT NULL,
  `host_name` varchar(255) DEFAULT NULL,
  `operation` varchar(50) NOT NULL,
  `operation_status` varchar(20) NOT NULL,
  `operation_time` bigint(20) NOT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `operator_ip` varchar(50) DEFAULT NULL,
  `request_params` text,
  `response_result` text,
  `status_after` varchar(20) DEFAULT NULL,
  `status_before` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_registration_log;
CREATE TABLE `host_registration_log` (
  `reg_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `error_message` varchar(1000) DEFAULT NULL,
  `host_id` bigint(20) DEFAULT NULL,
  `host_name` varchar(255) NOT NULL,
  `ipv4` varchar(255) DEFAULT NULL,
  `registered_time` bigint(20) DEFAULT NULL,
  `registration_type` varchar(255) NOT NULL,
  `source_ip` varchar(255) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`reg_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_role_command;
CREATE TABLE `host_role_command` (
  `task_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `attempt_count` int(11) DEFAULT NULL,
  `auto_skip_on_failure` int(11) DEFAULT NULL,
  `command_detail` varchar(255) DEFAULT NULL,
  `custom_command_name` varchar(255) DEFAULT NULL,
  `end_time` bigint(20) DEFAULT NULL,
  `error_log` varchar(255) DEFAULT NULL,
  `event` longtext,
  `exitcode` int(11) DEFAULT NULL,
  `host_id` bigint(20) DEFAULT NULL,
  `host_name` varchar(255) DEFAULT NULL,
  `is_background` int(11) DEFAULT NULL,
  `last_attempt_time` bigint(20) DEFAULT NULL,
  `ops_display_name` varchar(255) DEFAULT NULL,
  `original_start_time` bigint(20) DEFAULT NULL,
  `output_log` varchar(255) DEFAULT NULL,
  `request_id` bigint(20) NOT NULL,
  `retry_allowed` int(11) DEFAULT NULL,
  `role` varchar(255) DEFAULT NULL,
  `role_command` varchar(255) DEFAULT NULL,
  `stage_id` bigint(20) NOT NULL,
  `start_time` bigint(20) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  `std_error` longblob,
  `std_out` longblob,
  `structured_out` longblob,
  PRIMARY KEY (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_tag_categories;
CREATE TABLE `host_tag_categories` (
  `category_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `category_name` varchar(255) NOT NULL,
  `category_type` varchar(255) NOT NULL,
  `color` varchar(255) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `sort_order` int(11) DEFAULT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_tag_mapping;
CREATE TABLE `host_tag_mapping` (
  `host_id` bigint(20) NOT NULL,
  `tag_id` bigint(20) NOT NULL,
  `assigned_by` varchar(255) DEFAULT NULL,
  `assigned_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`host_id`,`tag_id`),
  KEY `FKsf9o5vcu7l386ipu28rdeuort` (`tag_id`),
  CONSTRAINT `FKk7nc8ps36vgie97jacqt9vrdj` FOREIGN KEY (`host_id`) REFERENCES `hosts` (`host_id`),
  CONSTRAINT `FKsf9o5vcu7l386ipu28rdeuort` FOREIGN KEY (`tag_id`) REFERENCES `host_tags` (`tag_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS host_tags;
CREATE TABLE `host_tags` (
  `tag_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `color` varchar(255) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `tag_name` varchar(255) NOT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  `category_id` bigint(20) NOT NULL,
  PRIMARY KEY (`tag_id`),
  KEY `FK97ay2hs1wrxlq7xxfnb32jljo` (`category_id`),
  CONSTRAINT `FK97ay2hs1wrxlq7xxfnb32jljo` FOREIGN KEY (`category_id`) REFERENCES `host_tag_categories` (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS hostcomponentdesiredstate;
CREATE TABLE `hostcomponentdesiredstate` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `admin_state` varchar(255) DEFAULT NULL,
  `blueprint_provisioning_state` varchar(255) DEFAULT NULL,
  `cluster_id` bigint(20) DEFAULT NULL,
  `component_name` varchar(255) DEFAULT NULL,
  `desired_state` varchar(255) DEFAULT NULL,
  `host_id` bigint(20) DEFAULT NULL,
  `maintenance_state` varchar(255) DEFAULT NULL,
  `restart_required` int(11) DEFAULT NULL,
  `service_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS hostcomponentstate;
CREATE TABLE `hostcomponentstate` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_id` bigint(20) DEFAULT NULL,
  `component_name` varchar(255) DEFAULT NULL,
  `current_state` varchar(255) DEFAULT NULL,
  `host_id` bigint(20) DEFAULT NULL,
  `last_live_state` varchar(255) DEFAULT NULL,
  `service_name` varchar(255) DEFAULT NULL,
  `upgrade_state` varchar(255) DEFAULT NULL,
  `version` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS hosts;
CREATE TABLE `hosts` (
  `host_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `agent_status` varchar(255) DEFAULT NULL,
  `agent_version` varchar(255) DEFAULT NULL,
  `cpu_count` int(11) NOT NULL,
  `cpu_info` varchar(255) NOT NULL,
  `cpu_usage` decimal(38,2) DEFAULT NULL,
  `discovery_status` varchar(2000) DEFAULT NULL,
  `disk_info` text,
  `disk_usage` decimal(38,2) DEFAULT NULL,
  `heartbeat_interval` int(11) DEFAULT NULL,
  `host_attributes` longtext,
  `host_name` varchar(255) NOT NULL,
  `ipv4` varchar(255) DEFAULT NULL,
  `ipv6` varchar(255) DEFAULT NULL,
  `last_heartbeat_time` bigint(20) DEFAULT NULL,
  `last_registration_time` bigint(20) DEFAULT NULL,
  `memory_usage` decimal(38,2) DEFAULT NULL,
  `network_info` text,
  `os_arch` varchar(255) NOT NULL,
  `os_info` varchar(1000) DEFAULT NULL,
  `os_type` varchar(255) NOT NULL,
  `public_host_name` varchar(255) DEFAULT NULL,
  `rack_info` varchar(255) DEFAULT NULL,
  `total_disk` bigint(20) DEFAULT NULL,
  `total_mem` bigint(20) NOT NULL,
  `used_disk` bigint(20) DEFAULT NULL,
  `used_mem` bigint(20) DEFAULT NULL,
  `available_mem` bigint(20) DEFAULT NULL,
  `available_disk` bigint(20) DEFAULT NULL,
  `last_operation_time` bigint(20) DEFAULT NULL,
  `storage_size` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`host_id`),
  UNIQUE KEY `UK_cldf40pyjm4150iwq12ixa26o` (`host_name`),
  UNIQUE KEY `UK_3ytqj7mi7dqk0cv894lp61iph` (`ipv4`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=latin1;

ALTER TABLE hosts ADD COLUMN IF NOT EXISTS available_mem bigint(20) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS available_disk bigint(20) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS storage_size bigint(20) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS memory_usage decimal(38,2) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS disk_usage decimal(38,2) DEFAULT NULL;

DROP TABLE IF EXISTS permission_roleauthorization;
CREATE TABLE `permission_roleauthorization` (
  `authorization_id` bigint(20) NOT NULL,
  `permission_id` bigint(20) NOT NULL,
  PRIMARY KEY (`authorization_id`,`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS policies;
CREATE TABLE `policies` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `active` bit(1) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS request;
CREATE TABLE `request` (
  `request_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_host_info` longblob,
  `cluster_id` bigint(20) DEFAULT NULL,
  `command_name` varchar(255) DEFAULT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `display_status` varchar(255) DEFAULT NULL,
  `end_time` bigint(20) DEFAULT NULL,
  `exclusive_execution` int(11) DEFAULT NULL,
  `inputs` longblob,
  `request_context` varchar(255) DEFAULT NULL,
  `request_schedule_id` bigint(20) DEFAULT NULL,
  `request_type` varchar(255) DEFAULT NULL,
  `start_time` bigint(20) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  `user_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS role_operation_log;
CREATE TABLE `role_operation_log` (
  `log_id` int(11) NOT NULL AUTO_INCREMENT,
  `create_time` bigint(20) DEFAULT NULL,
  `error_message` varchar(500) DEFAULT NULL,
  `ip_address` varchar(50) DEFAULT NULL,
  `new_value` varchar(1000) DEFAULT NULL,
  `old_value` varchar(1000) DEFAULT NULL,
  `operation_type` varchar(50) DEFAULT NULL,
  `result` varchar(20) DEFAULT NULL,
  `target_id` int(11) DEFAULT NULL,
  `target_name` varchar(255) DEFAULT NULL,
  `target_type` varchar(50) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `user_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`log_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS roleauthorization;
CREATE TABLE `roleauthorization` (
  `authorization_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `authorization_name` varchar(255) DEFAULT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `description` varchar(512) DEFAULT NULL,
  `is_system` int(11) DEFAULT NULL,
  `role_type` varchar(50) DEFAULT NULL,
  `scope` varchar(255) DEFAULT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`authorization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_config_repo;
CREATE TABLE `service_config_repo` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `branch` varchar(100) DEFAULT NULL,
  `config_path` varchar(255) NOT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `is_active` bit(1) DEFAULT NULL,
  `last_commit_id` varchar(100) DEFAULT NULL,
  `last_commit_time` bigint(20) DEFAULT NULL,
  `repo_name` varchar(100) NOT NULL,
  `repo_type` varchar(50) DEFAULT NULL,
  `repo_url` varchar(500) NOT NULL,
  `service_id` bigint(20) NOT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_dependencies;
CREATE TABLE `service_dependencies` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `created_time` bigint(20) DEFAULT NULL,
  `dependency_type` varchar(50) DEFAULT 'REQUIRED',
  `depends_on_service_id` bigint(20) NOT NULL,
  `depends_on_service_name` varchar(100) NOT NULL,
  `max_version` varchar(50) DEFAULT NULL,
  `min_version` varchar(50) DEFAULT NULL,
  `service_id` bigint(20) NOT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  `created_at` datetime(3) DEFAULT NULL,
  `updated_at` datetime(3) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_service_dependencies_service_id` (`service_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_desired_state;
CREATE TABLE `service_desired_state` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_id` bigint(20) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `desired_state` varchar(255) DEFAULT NULL,
  `service_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_host_mapping;
CREATE TABLE `service_host_mapping` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `create_time` bigint(20) DEFAULT NULL,
  `host_id` bigint(20) NOT NULL,
  `host_ip` varchar(50) DEFAULT NULL,
  `host_name` varchar(255) DEFAULT NULL,
  `role` varchar(50) DEFAULT NULL,
  `service_id` bigint(20) NOT NULL,
  `service_name` varchar(100) NOT NULL,
  `status` varchar(20) DEFAULT 'ACTIVE',
  `update_time` bigint(20) DEFAULT NULL,
  `created_at` datetime(3) DEFAULT NULL,
  `updated_at` datetime(3) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_service_host_mapping_service_id` (`service_id`),
  KEY `idx_service_host_mapping_host_id` (`host_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_metadata;
CREATE TABLE `service_metadata` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `created_time` bigint(20) DEFAULT NULL,
  `is_available` bit(1) DEFAULT NULL,
  `package_md5` varchar(64) DEFAULT NULL,
  `package_name` varchar(255) DEFAULT NULL,
  `package_path` varchar(500) DEFAULT NULL,
  `service_description` varchar(500) DEFAULT NULL,
  `service_name` varchar(100) NOT NULL,
  `service_type` varchar(50) DEFAULT NULL,
  `service_version` varchar(50) NOT NULL,
  `updated_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_operation_audit;
CREATE TABLE `service_operation_audit` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `created_time` bigint(20) DEFAULT NULL,
  `duration_ms` bigint(20) DEFAULT '0',
  `error_message` text,
  `operation` varchar(20) NOT NULL,
  `operation_status` varchar(20) NOT NULL,
  `operation_time` bigint(20) NOT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `service_name` varchar(100) NOT NULL,
  `status_after` varchar(20) DEFAULT NULL,
  `status_before` varchar(20) DEFAULT NULL,
  `created_at` datetime(3) DEFAULT NULL,
  `updated_at` datetime(3) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_service_operation_audit_service_name` (`service_name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS service_operations;
CREATE TABLE `service_operations` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `command_id` varchar(100) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `duration_ms` bigint(20) DEFAULT NULL,
  `end_time` bigint(20) DEFAULT NULL,
  `error_message` varchar(1000) DEFAULT NULL,
  `operation` varchar(50) NOT NULL,
  `operator` varchar(100) DEFAULT NULL,
  `output` text,
  `service_id` bigint(20) NOT NULL,
  `service_name` varchar(100) NOT NULL,
  `start_time` bigint(20) DEFAULT NULL,
  `status` varchar(50) NOT NULL,
  `target_hosts` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS servicecomponentdesiredstate;
CREATE TABLE `servicecomponentdesiredstate` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_id` bigint(20) DEFAULT NULL,
  `component_name` varchar(255) DEFAULT NULL,
  `desired_repo_version_id` bigint(20) DEFAULT NULL,
  `desired_state` varchar(255) DEFAULT NULL,
  `recovery_enabled` int(11) DEFAULT NULL,
  `repo_state` varchar(255) DEFAULT NULL,
  `service_name` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS services;
CREATE TABLE `services` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_id` bigint(20) DEFAULT NULL,
  `config_version` varchar(50) DEFAULT NULL,
  `created_time` bigint(20) DEFAULT NULL,
  `description` varchar(500) DEFAULT NULL,
  `is_deleted` tinyint(1) DEFAULT '0',
  `last_operation` varchar(20) DEFAULT NULL,
  `last_operation_time` bigint(20) DEFAULT NULL,
  `last_restart_time` bigint(20) DEFAULT NULL,
  `service_name` varchar(100) NOT NULL,
  `service_type` varchar(50) NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'STOPPED',
  `updated_time` bigint(20) DEFAULT NULL,
  `version` varchar(50) NOT NULL,
  `created_at` datetime(3) DEFAULT NULL,
  `updated_at` datetime(3) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `UK_38twoss73rtux07w58qp200r0` (`service_name`),
  UNIQUE KEY `idx_services_service_name` (`service_name`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS stage;
CREATE TABLE `stage` (
  `stage_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `cluster_id` bigint(20) DEFAULT NULL,
  `command_execution_type` varchar(255) DEFAULT NULL,
  `command_params` longblob,
  `display_status` varchar(255) DEFAULT NULL,
  `host_params` longblob,
  `log_info` varchar(255) DEFAULT NULL,
  `request_context` varchar(255) DEFAULT NULL,
  `request_id` bigint(20) NOT NULL,
  `skippable` int(11) DEFAULT NULL,
  `status` varchar(255) DEFAULT NULL,
  `supports_auto_skip_failure` int(11) DEFAULT NULL,
  PRIMARY KEY (`stage_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS tenant;
CREATE TABLE `tenant` (
  `tenant_id` int(11) NOT NULL AUTO_INCREMENT,
  `create_time` bigint(20) DEFAULT NULL,
  `creator` varchar(255) DEFAULT NULL,
  `description` varchar(512) DEFAULT NULL,
  `max_hosts` int(11) DEFAULT NULL,
  `max_users` int(11) DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `tenant_code` varchar(100) DEFAULT NULL,
  `tenant_name` varchar(255) NOT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`tenant_id`),
  UNIQUE KEY `UK_ng2jtiduv4m34nlcypgqdp29j` (`tenant_code`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS user_authentication;
CREATE TABLE `user_authentication` (
  `user_authentication_id` int(11) NOT NULL AUTO_INCREMENT,
  `authentication_key` varchar(255) DEFAULT NULL,
  `authentication_type` varchar(255) DEFAULT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `update_time` bigint(20) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`user_authentication_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS user_role;
CREATE TABLE `user_role` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `authorization_id` int(11) NOT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `creator` varchar(255) DEFAULT NULL,
  `expiry_time` bigint(20) DEFAULT NULL,
  `is_active` int(11) DEFAULT NULL,
  `tenant_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

DROP TABLE IF EXISTS users;
CREATE TABLE `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT,
  `active` int(11) DEFAULT NULL,
  `create_time` bigint(20) DEFAULT NULL,
  `display_name` varchar(255) DEFAULT NULL,
  `local_username` varchar(255) DEFAULT NULL,
  `principal_id` bigint(20) DEFAULT NULL,
  `user_name` varchar(255) DEFAULT NULL,
  `version` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `UK_k8d0f2n7n88w1a16yhua64onx` (`user_name`),
  KEY `FKf2q7vjfwrbsmopqgy84amk3ge` (`principal_id`),
  CONSTRAINT `FKf2q7vjfwrbsmopqgy84amk3ge` FOREIGN KEY (`principal_id`) REFERENCES `adminprincipal` (`principal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

SET FOREIGN_KEY_CHECKS=1;

