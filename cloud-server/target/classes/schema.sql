DROP TABLE IF EXISTS `registries`;
CREATE TABLE `registries` (
  `id` BIGINT NOT NULL  COMMENT '唯一标识符',
  `registy_name` VARCHAR(255) NOT NULL  COMMENT '注册中心名称（可能为 registry\_name 拼写错误）',
  `registry_type` VARCHAR(255) NOT NULL  COMMENT '注册中心类型（如 DOCKER, MAVEN）',
  `registry_uri` VARCHAR(255) NOT NULL  COMMENT '注册中心访问地址（如 https://registry.example.com）',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='注册中心表';

DROP TABLE IF EXISTS `mpacks`;
CREATE TABLE `mpacks` (
  `id` BIGINT NOT NULL  COMMENT '唯一标识符',
  `mpack_name` VARCHAR(255) NOT NULL  COMMENT '管理包名称（如 HDP 或 CDH）',
  `mpack_version` VARCHAR(255) NOT NULL  COMMENT '管理包版本（如 3.1.0）',
  `mpack_uri` VARCHAR(255) NULL  COMMENT '管理包的下载路径（可为空）',
  `registry_id` BIGINT NULL  COMMENT '关联的 registries.id（外键）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uni_mpack_name_version` (mpack_name, mpack_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='元数据包表';

DROP TABLE IF EXISTS `stack`;
CREATE TABLE `stack` (
  `stack_id` BIGINT NOT NULL  COMMENT '唯一标识符',
  `stack_name` VARCHAR(100) NOT NULL  COMMENT '技术栈名称（如 HDP）',
  `stack_version` VARCHAR(100) NOT NULL  COMMENT '技术栈版本（如 3.1）',
  `mpack_id` BIGINT NULL  COMMENT '关联的 mpacks.id（外键）',
  PRIMARY KEY (`stack_id`),
  UNIQUE KEY `UQ_stack` (stack_name, stack_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='技术栈表';

DROP TABLE IF EXISTS `extension`;
CREATE TABLE `extension` (
  `extension_id` BIGINT NOT NULL  COMMENT '唯一标识符',
  `extension_name` VARCHAR(100) NOT NULL  COMMENT '扩展组件名称（如 Hive-JDBC）',
  `extension_version` VARCHAR(100) NOT NULL  COMMENT '扩展组件版本（如 2.3.8）',
  PRIMARY KEY (`extension_id`),
  UNIQUE KEY `UQ_extension` (extension_name, extension_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='扩展包表';

DROP TABLE IF EXISTS `extensionlink`;
CREATE TABLE `extensionlink` (
  `link_id` BIGINT NOT NULL  COMMENT '唯一关联标识符',
  `stack_id` BIGINT NOT NULL  COMMENT '关联的 stack.stack\_id（外键）',
  `extension_id` BIGINT NOT NULL  COMMENT '关联的 extension.extension\_id（外键）',
  PRIMARY KEY (`link_id`),
  UNIQUE KEY `UQ_extension_link` (stack_id, extension_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='扩展包与技术栈关联表';

DROP TABLE IF EXISTS `adminresourcetype`;
CREATE TABLE `adminresourcetype` (
  `resource_type_id` INTEGER NOT NULL  COMMENT '资源类型唯一标识符',
  `resource_type_name` VARCHAR(255) NOT NULL  COMMENT '资源类型名称（如 CLUSTER, SERVICE）',
  PRIMARY KEY (`resource_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='资源类型表';

DROP TABLE IF EXISTS `adminresource`;
CREATE TABLE `adminresource` (
  `resource_id` BIGINT NOT NULL  COMMENT '资源唯一标识符',
  `resource_type_id` INTEGER NOT NULL  COMMENT '关联的 adminresourcetype.resource\_type\_id（外键）',
  PRIMARY KEY (`resource_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='资源实例表';

DROP TABLE IF EXISTS `clusters`;
CREATE TABLE `clusters` (
  `cluster_id` BIGINT NOT NULL  COMMENT '集群唯一标识符',
  `resource_id` BIGINT NOT NULL  COMMENT '关联的 adminresource.resource\_id（外键）',
  `upgrade_id` BIGINT NULL  COMMENT '升级任务关联ID（可为空）',
  `cluster_info` VARCHAR(255) NOT NULL  COMMENT '集群基本信息摘要',
  `cluster_name` VARCHAR(100) NOT NULL  COMMENT '集群名称（全库唯一）',
  `provisioning_state` VARCHAR(255) NOT NULL DEFAULT 'INIT' COMMENT '集群供给状态（如 INIT, PROVISIONING, COMPLETED）',
  `security_type` VARCHAR(32) NOT NULL DEFAULT 'NONE' COMMENT '安全认证类型（如 NONE, KERBEROS）',
  `desired_cluster_state` VARCHAR(255) NOT NULL  COMMENT '期望的集群状态（如 INSTALLED, STARTED）',
  `desired_stack_id` BIGINT NOT NULL  COMMENT '关联的 stack.stack\_id（外键，目标技术栈版本）',
  PRIMARY KEY (`cluster_id`),
  UNIQUE KEY `UQ_cluster_name` (`cluster_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='集群表';

DROP TABLE IF EXISTS `clusterconfig`;
CREATE TABLE `clusterconfig` (
  `config_id` BIGINT NOT NULL  COMMENT '配置唯一标识符',
  `version_tag` VARCHAR(100) NOT NULL  COMMENT '版本标签（用户自定义，如 v1.0.0）',
  `version` BIGINT NOT NULL  COMMENT '版本号（递增序列）',
  `type_name` VARCHAR(100) NOT NULL  COMMENT '配置类型（如 core-site.xml, hdfs-site）',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的 clusters.cluster\_id（外键）',
  `stack_id` BIGINT NOT NULL  COMMENT '关联的 stack.stack\_id（外键，技术栈版本）',
  `selected` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否选中当前配置（0=未选中，1=选中）',
  `config_data` LONGTEXT NOT NULL  COMMENT '配置内容（JSON 或 XML 格式）',
  `config_attributes` LONGTEXT NULL  COMMENT '附加配置属性（JSON 格式存储）',
  `create_timestamp` BIGINT NOT NULL  COMMENT '创建时间戳（Unix 毫秒）',
  `unmapped` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否未映射到实际文件（0=已映射，1=未映射）',
  `selected_timestamp` BIGINT NOT NULL DEFAULT 0 COMMENT '配置被选中的时间戳',
  `category_name` VARCHAR(100) NOT NULL  COMMENT '配置分类（如 network, security）',
  `property_name` VARCHAR(100) NOT NULL  COMMENT '配置项名称（如 http.port, ssl.enabled）',
  `property_value` VARCHAR(4000) NOT NULL  COMMENT '配置项值',
  PRIMARY KEY (`config_id`),
  UNIQUE KEY `UQ_config_type_tag` (cluster_id, type_name, version_tag),
  UNIQUE KEY `UQ_config_type_version` (cluster_id, type_name, version),
  PRIMARY KEY (category_name, property_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='集群配置表';

DROP TABLE IF EXISTS `serviceconfig`;
CREATE TABLE `serviceconfig` (
  `service_config_id` BIGINT NOT NULL  COMMENT '服务配置唯一标识符',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的 clusters.cluster\_id（外键）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称（如 HDFS, YARN）',
  `version` BIGINT NOT NULL  COMMENT '配置版本号（递增）',
  `create_timestamp` BIGINT NOT NULL  COMMENT '创建时间戳（Unix 毫秒）',
  `stack_id` BIGINT NOT NULL  COMMENT '关联的 stack.stack\_id（外键）',
  `user_name` VARCHAR(255) NOT NULL DEFAULT '\_db' COMMENT '创建配置的用户名（默认值 \_db 表示系统）',
  `group_id` BIGINT NULL  COMMENT '用户所属组ID（可为空）',
  `note` LONGTEXT NULL  COMMENT '配置备注说明',
  PRIMARY KEY (`service_config_id`),
  UNIQUE KEY `UQ_scv_service_version` (cluster_id, service_name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务配置版本表';

DROP TABLE IF EXISTS `hosts`;
CREATE TABLE `hosts` (
  `host_id` BIGINT NOT NULL  COMMENT '主机唯一标识符',
  `host_name` VARCHAR(255) NOT NULL  COMMENT '主机名称（全库唯一）',
  `cpu_count` INTEGER NOT NULL  COMMENT 'CPU 核心数',
  `cpu_info` VARCHAR(255) NOT NULL  COMMENT 'CPU 型号信息',
  `discovery_status` VARCHAR(2000) NOT NULL  COMMENT '主机发现状态（JSON 格式存储监控状态）',
  `host_attributes` LONGTEXT NOT NULL  COMMENT '主机扩展属性（JSON 格式）',
  `ipv4` VARCHAR(255) NULL  COMMENT 'IPv4 地址',
  `ipv6` VARCHAR(255) NULL  COMMENT 'IPv6 地址',
  `last_registration_time` BIGINT NOT NULL  COMMENT '最后注册时间（Unix 毫秒）',
  `os_arch` VARCHAR(255) NOT NULL  COMMENT '操作系统架构（如 x86\_64, arm64）',
  `os_info` VARCHAR(1000) NOT NULL  COMMENT '操作系统详细信息（如 CentOS 7.9）',
  `os_type` VARCHAR(255) NOT NULL  COMMENT '操作系统类型（如 Linux, Windows）',
  `ph_cpu_count` INTEGER NULL  COMMENT '物理 CPU 数量（如超线程场景下与 cpu\_count 不同）',
  `public_host_name` VARCHAR(255) NULL  COMMENT '对外暴露的主机名',
  `rack_info` VARCHAR(255) NOT NULL  COMMENT '机架信息（如 /rack1/row2）',
  `total_mem` BIGINT NOT NULL  COMMENT '总内存（单位：字节）',
  PRIMARY KEY (`host_id`),
  UNIQUE KEY `UQ_hosts_host_name` (`host_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主机信息表';

DROP TABLE IF EXISTS `serviceconfighosts`;
CREATE TABLE `serviceconfighosts` (
  `service_config_id` BIGINT NOT NULL  COMMENT '关联的 serviceconfig.service\_config\_id',
  `host_id` BIGINT NOT NULL  COMMENT '关联的 hosts.host\_id',
  PRIMARY KEY (service_config_id, host_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务配置与主机关联表';

DROP TABLE IF EXISTS `serviceconfigmapping`;
CREATE TABLE `serviceconfigmapping` (
  `service_config_id` BIGINT NOT NULL  COMMENT '关联的 serviceconfig.service\_config\_id',
  `config_id` BIGINT NOT NULL  COMMENT '关联的 clusterconfig.config\_id',
  PRIMARY KEY (service_config_id, config_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务配置与集群配置关联表';

DROP TABLE IF EXISTS `clusterservices`;
CREATE TABLE `clusterservices` (
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称（如 HDFS, ZOOKEEPER）',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的 clusters.cluster\_id（外键）',
  `service_enabled` INTEGER NOT NULL  COMMENT '服务是否启用（0=禁用，1=启用）',
  PRIMARY KEY (service_name, cluster_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='集群服务状态表';

DROP TABLE IF EXISTS `clusterstate`;
CREATE TABLE `clusterstate` (
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的 clusters.cluster\_id（外键）',
  `current_cluster_state` VARCHAR(255) NOT NULL  COMMENT '当前集群状态（如 INSTALLED, STARTED）',
  `current_stack_id` BIGINT NOT NULL  COMMENT '当前技术栈版本 stack.stack\_id（外键）',
  `repo_version_id` BIGINT NOT NULL  COMMENT '仓库版本唯一标识符',
  `stack_id` BIGINT NOT NULL  COMMENT '关联的 stack.stack\_id（外键，技术栈版本）',
  `version` VARCHAR(255) NOT NULL  COMMENT '仓库版本号（如 7.2.0）',
  `display_name` VARCHAR(128) NOT NULL  COMMENT '显示名称（用户友好标识，如 HDP-3.1.0）',
  `repo_type` VARCHAR(255) NOT NULL DEFAULT 'STANDARD' COMMENT '仓库类型（如 STANDARD, CUSTOM）',
  `hidden` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否隐藏（0=可见，1=隐藏）',
  `resolved` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已完成冲突解决（0=未完成，1=完成）',
  `legacy` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否为旧版本（0=当前版本，1=旧版）',
  `id` BIGINT NOT NULL  COMMENT '主键',
  `repo_version_id` BIGINT NOT NULL  COMMENT '关联的 repo\_version.repo\_version\_id（外键）',
  `family` VARCHAR(255) NOT NULL DEFAULT '''''' COMMENT '操作系统家族（如 RedHat, Ubuntu）',
  `cloud_managed` TINYINT(1) NULL DEFAULT 1 COMMENT '是否由 Cloud 系统管理（0=否，1=是）',
  `id` BIGINT NOT NULL  COMMENT '主键',
  `repo_os_id` BIGINT NULL  COMMENT '关联的 repo\_os.id（外键，为空时表示适用于所有操作系统）',
  `repo_name` VARCHAR(255) NOT NULL  COMMENT '仓库名称（如 HDP, Cloud）',
  `repo_id` VARCHAR(255) NOT NULL  COMMENT '仓库唯一标识（如 HDP-3.1.0）',
  `base_url` MEDIUMTEXT NOT NULL  COMMENT '仓库基础访问URL（如 http://repo.example.com/hdp/centos7/3.1.0）',
  `distribution` MEDIUMTEXT NULL  COMMENT '发行版名称（如 centos7）',
  `components` MEDIUMTEXT NULL  COMMENT '仓库组件列表（如 main,contrib ，逗号分隔）',
  `unique_repo` TINYINT(1) NULL DEFAULT 1 COMMENT '是否唯一仓库（0=允许重复，1=唯一标识）',
  `mirrors` MEDIUMTEXT NULL  COMMENT '镜像地址列表（JSON 或逗号分隔，用于负载均衡）',
  `repo_definition_id` BIGINT NOT NULL  COMMENT '关联的 repo\_definition.id（外键）',
  `tag` VARCHAR(255) NOT NULL  COMMENT '标签名称',
  `repo_definition_id` BIGINT NOT NULL  COMMENT '关联的 repo\_definition.id（外键）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称（如 HDFS, ZOOKEEPER）',
  PRIMARY KEY (`cluster_id`),
  PRIMARY KEY (`repo_version_id`),
  UNIQUE KEY `UQ_repo_version_display_name` (`display_name`),
  UNIQUE KEY `UQ_repo_version_stack_id` (stack_id, version),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (repo_definition_id, tag),
  PRIMARY KEY (repo_definition_id, service_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='集群运行状态表';

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `user_id` INTEGER NOT NULL  COMMENT '用户唯一标识符（主键）',
  `principal_id` BIGINT NOT NULL  COMMENT '权限主体ID（外键 ➔ adminprincipal.principal\_id）',
  `user_name` VARCHAR(255) NOT NULL  COMMENT '用户名（唯一标识，如 admin）',
  `active` INTEGER NOT NULL DEFAULT 1 COMMENT '用户是否激活（0=禁用，1=启用）',
  `consecutive_failures` INTEGER NOT NULL DEFAULT 0 COMMENT '连续登录失败次数（用于锁定策略）',
  `active_widget_layouts` VARCHAR(1024) NULL  COMMENT '用户活动界面布局配置（JSON 或自定义格式）',
  `display_name` VARCHAR(255) NOT NULL  COMMENT '显示名称（用户昵称或全名）',
  `local_username` VARCHAR(255) NOT NULL  COMMENT '本地系统用户名（如操作系统账户）',
  `create_time` BIGINT NOT NULL  COMMENT '用户创建时间（Unix 时间戳）',
  `version` BIGINT NOT NULL DEFAULT 0 COMMENT '版本号（用于乐观锁机制）',
  `user_authentication_id` INTEGER NOT NULL  COMMENT '认证信息唯一标识符（主键）',
  `user_id` INTEGER NOT NULL  COMMENT '关联的用户ID（外键 ➔ users.user\_id）',
  `authentication_type` VARCHAR(50) NOT NULL  COMMENT '认证类型（如 LOCAL, LDAP, OAuth2）',
  `authentication_key` VARCHAR(2048) NULL  COMMENT '加密后的认证密钥（如密码哈希、OAuth令牌）',
  `create_time` BIGINT NOT NULL  COMMENT '认证信息创建时间',
  `update_time` BIGINT NOT NULL  COMMENT '认证信息最近修改时间',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `UNQ_users_0` (`user_name`),
  PRIMARY KEY (`user_authentication_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

DROP TABLE IF EXISTS `groups`;
CREATE TABLE `groups` (
  `group_id` INTEGER NOT NULL  COMMENT '用户组唯一标识符（主键）',
  `principal_id` BIGINT NOT NULL  COMMENT '权限主体ID（外键 ➔ adminprincipal.principal\_id）',
  `group_name` VARCHAR(255) NOT NULL  COMMENT '组名称（如 admins, developers）',
  `ldap_group` INTEGER NOT NULL DEFAULT 0 COMMENT '是否为 LDAP 组（0=本地组，1=LDAP同步组）',
  `group_type` VARCHAR(255) NOT NULL DEFAULT 'LOCAL' COMMENT '组类型（如 LOCAL, LDAP\_SYNC）',
  PRIMARY KEY (`group_id`),
  UNIQUE KEY `UNQ_groups_0` (group_name, ldap_group)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户组表';

DROP TABLE IF EXISTS `members`;
CREATE TABLE `members` (
  `member_id` INTEGER NOT NULL  COMMENT '成员关系唯一标识符（主键）',
  `group_id` INTEGER NOT NULL  COMMENT '关联的组ID（外键 ➔ groups.group\_id）',
  `user_id` INTEGER NOT NULL  COMMENT '关联的用户ID（外键 ➔ users.user\_id）',
  PRIMARY KEY (`member_id`),
  UNIQUE KEY `UNQ_members_0` (group_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组成员关联表';

DROP TABLE IF EXISTS `adminprincipaltype`;
CREATE TABLE `adminprincipaltype` (
  `principal_type_id` INTEGER NOT NULL  COMMENT '权限类型ID',
  `principal_type_name` VARCHAR(255) NOT NULL  COMMENT '类型名称（如 USER, ROLE）',
  PRIMARY KEY (`principal_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员权限类型表';

DROP TABLE IF EXISTS `adminprincipal`;
CREATE TABLE `adminprincipal` (
  `principal_id` BIGINT NOT NULL  COMMENT '权限主体ID（如用户ID、角色ID）',
  `principal_type_id` INTEGER NOT NULL  COMMENT '关联的权限类型ID（外键）',
  PRIMARY KEY (`principal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员权限实体表';

DROP TABLE IF EXISTS `request`;
CREATE TABLE `request` (
  `request_id` BIGINT NOT NULL  COMMENT '请求唯一标识符（主键）',
  `cluster_id` BIGINT NULL  COMMENT '关联的集群ID',
  `request_schedule_id` BIGINT NULL  COMMENT '调度关联ID（外键 ➔ requestschedule.schedule\_id）',
  `command_name` VARCHAR(255) NULL  COMMENT '操作命令名称（如 INSTALL, START\_SERVICE）',
  `create_time` BIGINT NOT NULL  COMMENT '请求创建时间戳',
  `end_time` BIGINT NOT NULL  COMMENT '请求结束时间戳',
  `exclusive_execution` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否独占执行（0=否，1=是，避免并发冲突）',
  `inputs` LONGBLOB NULL  COMMENT '操作输入参数（序列化格式，如 JSON、Protobuf）',
  `request_context` VARCHAR(255) NULL  COMMENT '请求上下文标识（用于跟踪日志）',
  `request_type` VARCHAR(255) NULL  COMMENT '请求类型（如 CLOUD, API）',
  `start_time` BIGINT NOT NULL  COMMENT '请求开始执行时间戳',
  `status` VARCHAR(255) NOT NULL DEFAULT 'PENDING' COMMENT '请求状态（如 IN\_PROGRESS, COMPLETED）',
  `display_status` VARCHAR(255) NOT NULL DEFAULT 'PENDING' COMMENT '用户可见的请求状态（可能更友好的描述）',
  `cluster_host_info` LONGBLOB NULL  COMMENT '集群主机信息快照（序列化格式）',
  `user_name` VARCHAR(255) NULL  COMMENT '触发请求的用户名',
  PRIMARY KEY (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务请求表';

DROP TABLE IF EXISTS `requestschedule`;
CREATE TABLE `requestschedule` (
  `schedule_id` BIGINT NOT NULL  COMMENT '调度任务唯一标识符（主键）',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的集群ID',
  `description` VARCHAR(255) NULL  COMMENT '调度描述信息',
  `status` VARCHAR(255) NULL  COMMENT '调度状态（如 ACTIVE, PAUSED）',
  `batch_separation_seconds` SMALLINT NULL  COMMENT '批次间隔时间（秒）',
  `batch_toleration_limit` SMALLINT NULL  COMMENT '允许失败的批次总数',
  `batch_toleration_limit_per_batch` SMALLINT NULL  COMMENT '单个批次允许的失败任务数',
  `pause_after_first_batch` VARCHAR(1) NULL  COMMENT '是否在第⼀批次后暂停（Y=是，N=否）',
  `authenticated_user_id` INTEGER NULL  COMMENT '认证用户ID（外键 ➔ users.user\_id）',
  `create_user` VARCHAR(255) NULL  COMMENT '创建调度任务的用户',
  `create_timestamp` BIGINT NULL  COMMENT '任务创建时间戳',
  `update_user` VARCHAR(255) NULL  COMMENT '最后更新任务的用户',
  `update_timestamp` BIGINT NULL  COMMENT '任务更新时间戳',
  PRIMARY KEY (`schedule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务调度计划表';

DROP TABLE IF EXISTS `stage`;
CREATE TABLE `stage` (
  `stage_id` BIGINT NOT NULL  COMMENT '阶段唯一标识符（复合主键）',
  `request_id` BIGINT NOT NULL  COMMENT '关联的请求ID（外键 + 复合主键 ➔ request.request\_id）',
  `cluster_id` BIGINT NULL  COMMENT '关联的集群ID',
  `skippable` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否可跳过（0=不可跳过，1=可跳过）',
  `supports_auto_skip_failure` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否支持自动忽略失败继续（0=否，1=是）',
  `log_info` VARCHAR(255) NOT NULL  COMMENT '日志文件路径或标识',
  `request_context` VARCHAR(255) NULL  COMMENT '阶段上下文标识（与请求上下文关联）',
  `command_params` LONGBLOB NULL  COMMENT '执行命令参数（序列化格式）',
  `host_params` LONGBLOB NULL  COMMENT '主机相关配置参数（如节点过滤规则）',
  `command_execution_type` VARCHAR(32) NOT NULL DEFAULT 'STAGE' COMMENT '执行类型（如 STAGE, TASK）',
  `status` VARCHAR(255) NOT NULL DEFAULT 'PENDING' COMMENT '阶段执行状态（如 COMPLETED, FAILED）',
  `task_id` BIGINT NOT NULL  COMMENT '任务唯一标识符',
  `attempt_count` SMALLINT NOT NULL  COMMENT '已尝试执行的次数（>=0）',
  `retry_allowed` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否允许重试（0=禁止，1=允许）',
  `event` LONGTEXT NOT NULL  COMMENT '事件日志（JSON格式记录执行步骤）',
  `exitcode` INTEGER NOT NULL  COMMENT '执行退出码（0=成功，非0=失败代码）',
  `host_id` BIGINT NULL  COMMENT '关联的 hosts.host\_id，可为空（服务级操作无需主机绑定）',
  `last_attempt_time` BIGINT NOT NULL  COMMENT '最近一次尝试的时间戳（Unix毫秒）',
  `request_id` BIGINT NOT NULL  COMMENT '关联 request.request\_id',
  `role` VARCHAR(100) NULL  COMMENT '主机角色名（如 DATANODE, NAMENODE）',
  `role_command` VARCHAR(255) NULL  COMMENT '角色对应的操作命令（如 INSTALL, START）',
  `stage_id` BIGINT NOT NULL  COMMENT '关联 stage.stage\_id',
  `start_time` BIGINT NOT NULL  COMMENT '实际开始时间戳',
  `original_start_time` BIGINT NOT NULL  COMMENT '原始计划开始时间戳',
  `end_time` BIGINT NULL  COMMENT '完成时间戳',
  `status` VARCHAR(100) NOT NULL DEFAULT 'PENDING' COMMENT '任务状态（PENDING, IN\_PROGRESS, COMPLETED, FAILED）',
  `auto_skip_on_failure` SMALLINT NOT NULL DEFAULT 0 COMMENT '失败后是否自动跳过（0=不跳过，1=跳过）',
  `std_error` LONGBLOB NULL  COMMENT '错误日志（二进制存储）',
  `std_out` LONGBLOB NULL  COMMENT '标准输出日志（二进制存储）',
  `output_log` VARCHAR(255) NULL  COMMENT '输出日志文件路径（如 /var/log/hadoop/install.log）',
  `error_log` VARCHAR(255) NULL  COMMENT '错误日志文件路径',
  `structured_out` LONGBLOB NULL  COMMENT '结构化输出（序列化格式，如 ProtoBuf）',
  `command_detail` VARCHAR(255) NULL  COMMENT '命令详情摘要（如 参数：--force --skip-checks）',
  `ops_display_name` VARCHAR(255) NULL  COMMENT '用户界面展示的操作名称（如 “安装DataNode服务”）',
  `custom_command_name` VARCHAR(255) NULL  COMMENT '自定义命令唯一标识',
  `is_background` SMALLINT NOT NULL DEFAULT 0 COMMENT '后台任务标记（0=前台，1=后台）',
  `task_id` BIGINT NOT NULL  COMMENT '主键，关联 host\_role\_command.task\_id',
  `command` LONGBLOB NULL  COMMENT '执行命令的完整内容（序列化格式如 JSON/ProtoBuf）',
  `role` VARCHAR(255) NOT NULL  COMMENT '角色名称',
  `request_id` BIGINT NOT NULL  COMMENT '关联 request.request\_id',
  `stage_id` BIGINT NOT NULL  COMMENT '关联 stage.stage\_id',
  `success_factor` DOUBLE NOT NULL  COMMENT '成功比例阈值（例如 0.7 表示70%成功即为整体成功）',
  PRIMARY KEY (stage_id, request_id),
  KEY `idx_host_component_state（需补充）` (`根据业务需求增加索引优化查询性能`),
  PRIMARY KEY (`task_id`),
  PRIMARY KEY (`task_id`),
  PRIMARY KEY (role, request_id, stage_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务阶段表';

DROP TABLE IF EXISTS `requestresourcefilter`;
CREATE TABLE `requestresourcefilter` (
  `filter_id` BIGINT NOT NULL  COMMENT '过滤器唯一ID',
  `request_id` BIGINT NOT NULL  COMMENT '关联 request.request\_id',
  `service_name` VARCHAR(255) NULL  COMMENT '服务名称（如 HDFS, YARN）',
  `component_name` VARCHAR(255) NULL  COMMENT '组件名称（如 DATANODE, RESOURCEMANAGER）',
  `hosts` LONGBLOB NULL  COMMENT '主机列表（序列化格式，如 JSON数组 \["host1", "host2"]）',
  PRIMARY KEY (`filter_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求资源过滤器表';

DROP TABLE IF EXISTS `requestoperationlevel`;
CREATE TABLE `requestoperationlevel` (
  `operation_level_id` BIGINT NOT NULL  COMMENT '层级唯一ID',
  `request_id` BIGINT NOT NULL  COMMENT '关联 request.request\_id',
  `level_name` VARCHAR(255) NULL  COMMENT '操作级别（CLUSTER, SERVICE, HOST\_COMPONENT）',
  `cluster_name` VARCHAR(255) NULL  COMMENT '集群名称（当操作级别为集群时必填）',
  `service_name` VARCHAR(255) NULL  COMMENT '服务名称（操作级别为服务时必填）',
  `host_component_name` VARCHAR(255) NULL  COMMENT '主机组件名称（如 DATANODE:host1）',
  `host_id` BIGINT NULL  COMMENT '主机ID（允许为空，适用于非主机级别的操作）',
  PRIMARY KEY (`operation_level_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='请求操作层级表';

DROP TABLE IF EXISTS `hostcomponentdesiredstate`;
CREATE TABLE `hostcomponentdesiredstate` (
  `id` BIGINT NOT NULL  COMMENT '主键',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的 clusterservices.cluster\_id',
  `component_name` VARCHAR(100) NOT NULL  COMMENT '组件名称（需与 servicecomponentdesiredstate 一致）',
  `desired_state` VARCHAR(255) NOT NULL  COMMENT '目标状态（如 INSTALLED, STARTED）',
  `host_id` BIGINT NOT NULL  COMMENT '关联的 hosts.host\_id（外键）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称（如 HDFS, ZOOKEEPER）',
  `admin_state` VARCHAR(32) NULL  COMMENT '管理员状态（如 INSERVICE, DECOMMISSIONED）',
  `maintenance_state` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' COMMENT '维护状态（如 ACTIVE, IN\_MAINTENANCE）',
  `blueprint_provisioning_state` VARCHAR(255) NULL DEFAULT 'NONE' COMMENT '蓝图部署状态（如 PROVISIONING, COMPLETED）',
  `restart_required` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否需要重启生效（0=否，1=是）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `UQ_hcdesiredstate_name` (component_name, service_name, host_id, cluster_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主机组件期望状态表';

DROP TABLE IF EXISTS `hostcomponentstate`;
CREATE TABLE `hostcomponentstate` (
  `id` BIGINT NOT NULL  COMMENT '主键',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的集群ID',
  `component_name` VARCHAR(100) NOT NULL  COMMENT '组件名称',
  `version` VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN' COMMENT '当前版本号',
  `current_state` VARCHAR(255) NOT NULL  COMMENT '实时状态（如 RUNNING, STOPPED）',
  `last_live_state` VARCHAR(255) NOT NULL DEFAULT 'UNKNOWN' COMMENT '上一次活跃状态',
  `host_id` BIGINT NOT NULL  COMMENT '关联的主机ID（外键）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称',
  `upgrade_state` VARCHAR(32) NOT NULL DEFAULT 'NONE' COMMENT '升级状态（如 UPGRADING, COMPLETED）',
  PRIMARY KEY (`id`),
  KEY `idx_host_component_state` (host_id, component_name, service_name, cluster_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主机组件实际状态表';

DROP TABLE IF EXISTS `hoststate`;
CREATE TABLE `hoststate` (
  `agent_version` VARCHAR(255) NOT NULL  COMMENT '主机代理版本',
  `available_mem` BIGINT NOT NULL  COMMENT '可用内存（字节）',
  `current_state` VARCHAR(255) NOT NULL  COMMENT '当前主机状态（如 HEALTHY, UNHEALTHY）',
  `health_status` VARCHAR(255) NULL  COMMENT '健康状态（如 OK, CRITICAL）',
  `host_id` BIGINT NOT NULL  COMMENT '关联的主机ID（主键与外键）',
  `time_in_state` BIGINT NOT NULL  COMMENT '当前状态的持续时间（毫秒）',
  `maintenance_state` VARCHAR(512) NULL  COMMENT '维护状态（长文本描述）',
  `id` BIGINT NOT NULL  COMMENT '主键',
  `repo_version_id` BIGINT NOT NULL  COMMENT '关联的仓库版本ID（外键）',
  `host_id` BIGINT NOT NULL  COMMENT '主机ID（外键）',
  `state` VARCHAR(32) NOT NULL  COMMENT '版本状态（如 INSTALLED, UPGRADING）',
  PRIMARY KEY (`host_id`),
  PRIMARY KEY (`id`),
  UNIQUE KEY `UQ_host_repo` (host_id, repo_version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主机运行时状态表';

DROP TABLE IF EXISTS `servicecomponentdesiredstate`;
CREATE TABLE `servicecomponentdesiredstate` (
  `id` BIGINT NOT NULL  COMMENT '主键',
  `component_name` VARCHAR(100) NOT NULL  COMMENT '组件名称（如 NAMENODE, RESOURCEMANAGER）',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的 clusterservices.cluster\_id（外键）',
  `desired_repo_version_id` BIGINT NOT NULL  COMMENT '期望的仓库版本（关联 repo\_version.repo\_version\_id，外键）',
  `desired_state` VARCHAR(255) NOT NULL  COMMENT '目标状态（如 STARTED, INSTALLED）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称（如 HDFS, YARN）',
  `recovery_enabled` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否启用自动恢复（0=禁用，1=启用）',
  `repo_state` VARCHAR(255) NOT NULL DEFAULT 'NOT\_REQUIRED' COMMENT '仓库状态（如 REQUIRED, NOT\_REQUIRED）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `UQ_scdesiredstate_name` (component_name, service_name, cluster_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务组件期望状态表';

DROP TABLE IF EXISTS `servicedesiredstate`;
CREATE TABLE `servicedesiredstate` (
  `cluster_id` BIGINT NOT NULL  COMMENT '关联的集群ID（复合主键）',
  `desired_host_role_mapping` INTEGER NOT NULL  COMMENT '期望的主机角色映射配置（需结合应用逻辑）',
  `desired_repo_version_id` BIGINT NOT NULL  COMMENT '期望的仓库版本（外键）',
  `desired_state` VARCHAR(255) NOT NULL  COMMENT '服务的目标状态（如 STARTED, INSTALLED）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称（复合主键）',
  `maintenance_state` VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' COMMENT '维护状态（如 ACTIVE, IN\_MAINTENANCE）',
  `credential_store_enabled` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否启用凭证存储（0=禁用，1=启用）',
  `key` VARCHAR(255) NOT NULL  COMMENT '键名（主键，唯一标识）',
  `value` LONGTEXT NULL  COMMENT '关联的值（长文本存储）',
  PRIMARY KEY (cluster_id, service_name),
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务级期望状态表';

DROP TABLE IF EXISTS `hostconfigmapping`;
CREATE TABLE `hostconfigmapping` (
  `create_timestamp` BIGINT NOT NULL  COMMENT '配置创建时间戳（复合主键部分）',
  `host_id` BIGINT NOT NULL  COMMENT '关联主机ID（外键 ➔ hosts.host\_id，复合主键部分）',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联集群ID（外键 ➔ clusters.cluster\_id，复合主键部分）',
  `type_name` VARCHAR(255) NOT NULL  COMMENT '配置类型名称（如 core-site, hdfs-site，复合主键部分）',
  `selected` INTEGER NOT NULL DEFAULT 0 COMMENT '是否当前选择（0=否，1=是，标记有效版本）',
  `service_name` VARCHAR(255) NULL  COMMENT '关联服务名称（如 HDFS, YARN）',
  `version_tag` VARCHAR(255) NOT NULL  COMMENT '配置版本标识（如 version123）',
  `user_name` VARCHAR(255) NOT NULL DEFAULT '\_db' COMMENT '操作者名称（默认 \_db 表示系统操作）',
  PRIMARY KEY (create_timestamp, host_id, cluster_id, type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主机配置映射表';

DROP TABLE IF EXISTS `metainfo`;
CREATE TABLE `metainfo` (
  `metainfo_key` VARCHAR(255) NOT NULL  COMMENT '元数据键名（主键）',
  `metainfo_value` LONGTEXT NULL  COMMENT '元数据值（长文本存储）',
  PRIMARY KEY (`metainfo_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='元信息表';

DROP TABLE IF EXISTS `ClusterHostMapping`;
CREATE TABLE `ClusterHostMapping` (
  `cluster_id` BIGINT NOT NULL  COMMENT '集群ID（复合主键部分）',
  `host_id` BIGINT NOT NULL  COMMENT '主机ID（复合主键部分）',
  `sequence_name` VARCHAR(255) NOT NULL  COMMENT '序列名称（主键，如 user\_id）',
  `sequence_value` DECIMAL(38) NOT NULL  COMMENT '当前序列值（整数或高精度数值）',
  PRIMARY KEY (cluster_id, host_id),
  PRIMARY KEY (`sequence_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='集群主机映射表';

DROP TABLE IF EXISTS `configgroup`;
CREATE TABLE `configgroup` (
  `group_id` BIGINT NOT NULL  COMMENT '配置组唯一标识符（主键）',
  `cluster_id` BIGINT NOT NULL  COMMENT '所属集群ID（外键 ➔ clusters.cluster\_id）',
  `group_name` VARCHAR(255) NOT NULL  COMMENT '配置组名称（如 hdfs\_config\_group）',
  `tag` VARCHAR(1024) NOT NULL  COMMENT '配置组标签（用于分类或搜索）',
  `description` VARCHAR(1024) NULL  COMMENT '配置组详细描述',
  `create_timestamp` BIGINT NOT NULL  COMMENT '配置组创建时间戳',
  `service_name` VARCHAR(255) NULL  COMMENT '关联服务名称（如 HDFS，表示该配置组专用于某个服务）',
  PRIMARY KEY (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置组表';

DROP TABLE IF EXISTS `confgroupclusterconfigmapping`;
CREATE TABLE `confgroupclusterconfigmapping` (
  `config_group_id` BIGINT NOT NULL  COMMENT '配置组ID（外键 ➔ configgroup.group\_id，复合主键部分）',
  `cluster_id` BIGINT NOT NULL  COMMENT '集群ID（复合主键部分，外键 ➔ clusters.cluster\_id）',
  `config_type` VARCHAR(100) NOT NULL  COMMENT '配置类型（如 xml, properties，复合主键部分）',
  `version_tag` VARCHAR(100) NOT NULL  COMMENT '关联的版本标识',
  `user_name` VARCHAR(100) NULL DEFAULT '\_db' COMMENT '操作用户（默认 \_db 表示系统操作）',
  `create_timestamp` BIGINT NOT NULL  COMMENT '关联创建时间戳',
  PRIMARY KEY (config_group_id, cluster_id, config_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置组与集群配置映射表';

DROP TABLE IF EXISTS `configgrouphostmapping`;
CREATE TABLE `configgrouphostmapping` (
  `config_group_id` BIGINT NOT NULL  COMMENT '配置组ID（外键 ➔ configgroup.group\_id）',
  `host_id` BIGINT NOT NULL  COMMENT '主机ID（外键 ➔ hosts.host\_id）',
  PRIMARY KEY (config_group_id, host_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配置组与主机映射表';

DROP TABLE IF EXISTS `requestschedulebatchrequest`;
CREATE TABLE `requestschedulebatchrequest` (
  `schedule_id` BIGINT NOT NULL  COMMENT '调度任务ID（主键部分，外键 ➔ requestschedule.schedule\_id）',
  `batch_id` BIGINT NOT NULL  COMMENT '批次ID（主键部分）',
  `request_id` BIGINT NULL  COMMENT '关联的请求ID（可能指向 request 表）',
  `request_type` VARCHAR(255) NULL  COMMENT '请求类型（如 REST, INTERNAL）',
  `request_uri` VARCHAR(1024) NULL  COMMENT '请求API路径（如 /api/v1/clusters）',
  `request_body` LONGBLOB NULL  COMMENT '请求原始数据（序列化格式，如 JSON、XML）',
  `request_status` VARCHAR(255) NULL  COMMENT '批次请求状态（如 SUCCESS, FAILED）',
  `return_code` SMALLINT NULL  COMMENT '返回状态码（如 200, 404, 500）',
  `return_message` VARCHAR(2000) NULL  COMMENT '响应结果描述（如错误详情）',
  PRIMARY KEY (schedule_id, batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='调度批次请求表';

DROP TABLE IF EXISTS `blueprint`;
CREATE TABLE `blueprint` (
  `blueprint_name` VARCHAR(100) NOT NULL  COMMENT '蓝图名称（主键，唯一标识）',
  `stack_id` BIGINT NOT NULL  COMMENT '关联的堆栈版本ID（外键 ➔ stack.stack\_id）',
  `security_type` VARCHAR(32) NOT NULL DEFAULT 'NONE' COMMENT '安全类型（如 KERBEROS, NONE）',
  `security_descriptor_reference` VARCHAR(255) NULL  COMMENT '安全描述符引用（如 Kerberos 配置路径或ID）',
  PRIMARY KEY (`blueprint_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='蓝图定义表';

DROP TABLE IF EXISTS `hostgroup`;
CREATE TABLE `hostgroup` (
  `blueprint_name` VARCHAR(100) NOT NULL  COMMENT '所属蓝图名称（复合主键部分，外键 ➔ blueprint.blueprint\_name）',
  `name` VARCHAR(100) NOT NULL  COMMENT '主机组名称（复合主键部分）',
  `cardinality` VARCHAR(255) NOT NULL  COMMENT '主机数量规则（如 1, 1+, 3-5）',
  `blueprint_name` VARCHAR(100) NOT NULL  COMMENT '所属蓝图名称（复合主键部分，外键 ➔ hostgroup.blueprint\_name）',
  `hostgroup_name` VARCHAR(100) NOT NULL  COMMENT '主机组名称（复合主键部分，外键 ➔ hostgroup.name）',
  `name` VARCHAR(100) NOT NULL  COMMENT '组件名称（复合主键部分，如 ZOOKEEPER\_SERVER）',
  `provision_action` VARCHAR(100) NULL  COMMENT '部署动作（如 INSTALL\_ONLY, START\_AND\_INSTALL）',
  `blueprint_name` VARCHAR(100) NOT NULL  COMMENT '所属蓝图名称（复合主键部分，外键 ➔ blueprint.blueprint\_name）',
  `type_name` VARCHAR(100) NOT NULL  COMMENT '配置类型（复合主键部分，如 hdfs-site）',
  `config_data` LONGTEXT NOT NULL  COMMENT '配置内容（JSON或XML格式）',
  `config_attributes` LONGTEXT NULL  COMMENT '附加属性（如版本、依赖关系）',
  `id` BIGINT NOT NULL  COMMENT '唯一标识符（主键）',
  `blueprint_name` VARCHAR(100) NOT NULL  COMMENT '所属蓝图名称（外键 ➔ blueprint.blueprint\_name）',
  `setting_name` VARCHAR(100) NOT NULL  COMMENT '设置项名称（同一蓝图内唯一）',
  `setting_data` MEDIUMTEXT NOT NULL  COMMENT '设置值（支持中等长度文本存储）',
  `blueprint_name` VARCHAR(100) NOT NULL  COMMENT '所属蓝图名称（复合主键部分）',
  `hostgroup_name` VARCHAR(100) NOT NULL  COMMENT '主机组名称（复合主键部分，外键 ➔ hostgroup.name）',
  `type_name` VARCHAR(100) NOT NULL  COMMENT '配置类型（复合主键部分，如 yarn-site）',
  `config_data` LONGTEXT NOT NULL  COMMENT '主机组专属配置内容',
  `config_attributes` LONGTEXT NULL  COMMENT '附加属性（如作用范围、生效条件）',
  PRIMARY KEY (blueprint_name, name),
  PRIMARY KEY (blueprint_name, hostgroup_name, name),
  PRIMARY KEY (blueprint_name, type_name),
  PRIMARY KEY (`id`),
  UNIQUE KEY `UQ_blueprint_setting_name` (blueprint_name, setting_name),
  PRIMARY KEY (blueprint_name, hostgroup_name, type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='主机组定义表';

DROP TABLE IF EXISTS `viewmain`;
CREATE TABLE `viewmain` (
  `view_name` VARCHAR(100) NOT NULL  COMMENT '视图名称（主键，如 HDFS\_VIEW）',
  `label` VARCHAR(255) NULL  COMMENT '显示名称（如 HDFS 管理）',
  `description` VARCHAR(2048) NULL  COMMENT '视图详细描述',
  `version` VARCHAR(255) NULL  COMMENT '版本号（如 1.0.0）',
  `build` VARCHAR(128) NULL  COMMENT '构建标识（如 20231001）',
  `resource_type_id` INTEGER NOT NULL  COMMENT '资源类型ID（外键 ➔ adminresourcetype.resource\_type\_id）',
  `icon` VARCHAR(255) NULL  COMMENT '图标路径（32x32像素）',
  `icon64` VARCHAR(255) NULL  COMMENT '大图标路径（64x64像素）',
  `archive` VARCHAR(255) NULL  COMMENT '视图包文件路径（如 JAR 包）',
  `mask` VARCHAR(255) NULL  COMMENT '权限掩码（如 HDFS.\*）',
  `system_view` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否系统内置视图（0=否，1=是）',
  PRIMARY KEY (`view_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图元信息表';

DROP TABLE IF EXISTS `viewurl`;
CREATE TABLE `viewurl` (
  `url_id` BIGINT NOT NULL  COMMENT 'URL唯一标识（主键）',
  `url_name` VARCHAR(255) NOT NULL  COMMENT 'URL显示名称',
  `url_suffix` VARCHAR(255) NOT NULL  COMMENT 'URL后缀路径',
  PRIMARY KEY (`url_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图URL表';

DROP TABLE IF EXISTS `viewinstance`;
CREATE TABLE `viewinstance` (
  `view_instance_id` BIGINT NOT NULL  COMMENT '视图实例ID（主键）',
  `resource_id` BIGINT NOT NULL  COMMENT '关联资源ID（外键 ➔ adminresource.resource\_id）',
  `view_name` VARCHAR(100) NOT NULL  COMMENT '所属视图名称（外键 ➔ viewmain.view\_name）',
  `name` VARCHAR(100) NOT NULL  COMMENT '实例名称（同一视图内唯一）',
  `label` VARCHAR(255) NULL  COMMENT '显示标签（如“HDFS实例”）',
  `description` VARCHAR(2048) NULL  COMMENT '实例详细描述',
  `visible` CHAR(1) NULL  COMMENT '是否可见（Y/N）',
  `icon` VARCHAR(255) NULL  COMMENT '小图标路径（32x32）',
  `icon64` VARCHAR(255) NULL  COMMENT '大图标路径（64x64）',
  `xml_driven` CHAR(1) NULL  COMMENT '是否由XML驱动（Y/N）',
  `alter_names` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否允许修改名称（0=否，1=是）',
  `cluster_handle` BIGINT NULL  COMMENT '关联集群句柄（保留字段）',
  `cluster_type` VARCHAR(100) NOT NULL DEFAULT 'LOCAL\_cloud' COMMENT '集群类型（默认本地环境）',
  `short_url` BIGINT NULL  COMMENT '短链ID（外键 ➔ viewurl.url\_id）',
  PRIMARY KEY (`view_instance_id`),
  UNIQUE KEY `UQ_viewinstance_name` (view_name, name),
  UNIQUE KEY `UQ_viewinstance_name_id` (view_instance_id, view_name, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图实例表';

DROP TABLE IF EXISTS `viewinstancedata`;
CREATE TABLE `viewinstancedata` (
  `view_instance_id` BIGINT NOT NULL  COMMENT '视图实例ID（主键部分，外键 ➔ viewinstance.view\_instance\_id）',
  `view_name` VARCHAR(100) NOT NULL  COMMENT '视图名称（冗余设计，可能与外键逻辑冲突）',
  `view_instance_name` VARCHAR(100) NOT NULL  COMMENT '实例名称（冗余设计，需校验外键关系）',
  `name` VARCHAR(100) NOT NULL  COMMENT '数据项名称（如“刷新间隔”）',
  `user_name` VARCHAR(100) NOT NULL  COMMENT '所属用户（支持多用户配置隔离）',
  `value` VARCHAR(2000) NULL  COMMENT '配置值（如“300秒”）',
  PRIMARY KEY (view_instance_id, name, user_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图实例数据表';

DROP TABLE IF EXISTS `viewinstanceproperty`;
CREATE TABLE `viewinstanceproperty` (
  `view_name` VARCHAR(100) NOT NULL  COMMENT '视图名称（主键部分）',
  `view_instance_name` VARCHAR(100) NOT NULL  COMMENT '实例名称（主键部分，冗余设计）',
  `name` VARCHAR(100) NOT NULL  COMMENT '属性名（如“默认配置”）',
  `value` VARCHAR(2000) NULL  COMMENT '属性值（如“启用缓存”）',
  PRIMARY KEY (view_name, view_instance_name, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图实例属性表';

DROP TABLE IF EXISTS `viewparameter`;
CREATE TABLE `viewparameter` (
  `view_name` VARCHAR(100) NOT NULL  COMMENT '视图名称（主键部分）',
  `name` VARCHAR(100) NOT NULL  COMMENT '参数名称（主键部分，如“端口号”）',
  `description` VARCHAR(2048) NULL  COMMENT '参数说明（帮助信息）',
  `label` VARCHAR(255) NULL  COMMENT '显示标签（如“HDFS端口”）',
  `placeholder` VARCHAR(255) NULL  COMMENT '输入提示（如“输入1~65535之间的端口号”）',
  `default_value` VARCHAR(2000) NULL  COMMENT '默认值（如“8020”）',
  `cluster_config` VARCHAR(255) NULL  COMMENT '关联集群配置项（如“hdfs.core.site.port”）',
  `required` CHAR(1) NULL  COMMENT '是否必填（Y/N）',
  `masked` CHAR(1) NULL  COMMENT '是否掩码显示（Y/N，如密码字段）',
  PRIMARY KEY (view_name, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图参数表';

DROP TABLE IF EXISTS `viewresource`;
CREATE TABLE `viewresource` (
  `view_name` VARCHAR(100) NOT NULL  COMMENT '视图名称（主键部分）',
  `name` VARCHAR(100) NOT NULL  COMMENT '资源名称（主键部分）',
  `plural_name` VARCHAR(255) NULL  COMMENT '复数形式（如“Queues”）',
  `id_property` VARCHAR(255) NULL  COMMENT '资源ID属性（如“queue\_id”）',
  `subResource_names` VARCHAR(255) NULL  COMMENT '子资源列表（如“users, groups”）',
  `provider` VARCHAR(255) NULL  COMMENT '资源提供方（如“YARNProvider”）',
  `service` VARCHAR(255) NULL  COMMENT '关联服务名称（如“YARN”）',
  `resource` VARCHAR(255) NULL  COMMENT '资源类型（如“Queue”）',
  PRIMARY KEY (view_name, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图资源表';

DROP TABLE IF EXISTS `viewentity`;
CREATE TABLE `viewentity` (
  `id` BIGINT NOT NULL  COMMENT '实体ID（主键）',
  `view_name` VARCHAR(100) NOT NULL  COMMENT '所属视图名称（外键 ➔ viewinstance.view\_name）',
  `view_instance_name` VARCHAR(100) NOT NULL  COMMENT '实例名称（外键 ➔ viewinstance.name）',
  `class_name` VARCHAR(255) NOT NULL  COMMENT '实体类全名（如“com.example.Plugin”）',
  `id_property` VARCHAR(255) NULL  COMMENT '实体ID属性（如“pluginId”）',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='视图实体表';

DROP TABLE IF EXISTS `adminpermission`;
CREATE TABLE `adminpermission` (
  `permission_id` BIGINT NOT NULL  COMMENT '权限ID（主键）',
  `permission_name` VARCHAR(255) NOT NULL  COMMENT '权限唯一名称（如“CLUSTER\_ADMIN”）',
  `resource_type_id` INTEGER NOT NULL  COMMENT '资源类型ID（外键 ➔ adminresourcetype.resource\_type\_id）',
  `permission_label` VARCHAR(255) NULL  COMMENT '显示标签（如“集群管理员”）',
  `principal_id` BIGINT NOT NULL  COMMENT '关联主体ID（外键 ➔ adminprincipal.principal\_id）',
  `sort_order` SMALLINT NOT NULL DEFAULT 1 COMMENT '排序权重（用于界面显示顺序）',
  PRIMARY KEY (`permission_id`),
  UNIQUE KEY `UQ_perm_name_resource_type_id` (permission_name, resource_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限定义表';

DROP TABLE IF EXISTS `roleauthorization`;
CREATE TABLE `roleauthorization` (
  `authorization_id` VARCHAR(100) NOT NULL  COMMENT '授权ID（主键，如“CLUSTER.ADMIN”）',
  `authorization_name` VARCHAR(255) NOT NULL  COMMENT '显示名称（如“集群管理员权限”）',
  `permission_id` BIGINT NOT NULL  COMMENT '权限ID（主键部分）',
  `authorization_id` VARCHAR(100) NOT NULL  COMMENT '角色授权ID（主键部分）',
  PRIMARY KEY (`authorization_id`),
  PRIMARY KEY (permission_id, authorization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色授权表';

DROP TABLE IF EXISTS `adminprivilege`;
CREATE TABLE `adminprivilege` (
  `privilege_id` BIGINT NULL  COMMENT '权限实例ID（主键）',
  `permission_id` BIGINT NOT NULL  COMMENT '权限ID（外键 ➔ adminpermission.permission\_id）',
  `resource_id` BIGINT NOT NULL  COMMENT '资源ID（外键 ➔ adminresource.resource\_id）',
  `principal_id` BIGINT NOT NULL  COMMENT '主体ID（外键 ➔ adminprincipal.principal\_id）',
  PRIMARY KEY (`privilege_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限实例表';

DROP TABLE IF EXISTS `widget`;
CREATE TABLE `widget` (
  `id` BIGINT NOT NULL  COMMENT '小部件唯一ID（主键）',
  `widget_name` VARCHAR(255) NOT NULL  COMMENT '小部件名称',
  `widget_type` VARCHAR(255) NOT NULL  COMMENT '类型（如“折线图”、“状态卡”）',
  `metrics` LONGTEXT NULL  COMMENT '关联的监控指标（JSON格式）',
  `time_created` BIGINT NOT NULL  COMMENT '创建时间戳',
  `author` VARCHAR(255) NULL  COMMENT '创建者',
  `description` VARCHAR(2048) NULL  COMMENT '详细描述',
  `default_section_name` VARCHAR(255) NULL  COMMENT '默认布局分区名称',
  `scope` VARCHAR(255) NULL  COMMENT '可见范围（如“全局”、“集群”）',
  `widget_values` LONGTEXT NULL  COMMENT '数值配置（如阈值、颜色）',
  `properties` LONGTEXT NULL  COMMENT '扩展属性（JSON格式）',
  `cluster_id` BIGINT NOT NULL  COMMENT '所属集群ID（外键未显式定义）',
  `tag` VARCHAR(255) NULL  COMMENT '标签分类（如“系统监控”、“用户自定义”）',
  `id` BIGINT NOT NULL  COMMENT '布局ID（主键）',
  `layout_name` VARCHAR(255) NOT NULL  COMMENT '布局名称',
  `section_name` VARCHAR(255) NOT NULL  COMMENT '分区名称（如“顶部区”、“侧边栏”）',
  `scope` VARCHAR(255) NOT NULL  COMMENT '作用域（如“用户私有”、“共享”）',
  `user_name` VARCHAR(255) NOT NULL  COMMENT '所属用户',
  `display_name` VARCHAR(255) NULL  COMMENT '布局显示名',
  `cluster_id` BIGINT NOT NULL  COMMENT '关联集群ID',
  `widget_layout_id` BIGINT NOT NULL  COMMENT '布局ID（主键部分，外键 ➔ widget\_layout.id）',
  `widget_id` BIGINT NOT NULL  COMMENT '小部件ID（主键部分，外键 ➔ widget.id）',
  `widget_order` SMALLINT NULL  COMMENT '显示顺序（升序排列）',
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (widget_layout_id, widget_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小部件表';

DROP TABLE IF EXISTS `artifact`;
CREATE TABLE `artifact` (
  `artifact_name` VARCHAR(100) NOT NULL  COMMENT '构件名称（主键部分）',
  `foreign_keys` VARCHAR(100) NOT NULL  COMMENT '关联键（主键部分，可能用于多环境映射）',
  `artifact_data` LONGTEXT NOT NULL  COMMENT '构件内容（如XML/JSON/YAML）',
  `id` BIGINT NOT NULL  COMMENT '请求ID（主键）',
  `action` VARCHAR(255) NOT NULL  COMMENT '操作类型（如“CREATE”、“DELETE”）',
  `cluster_id` BIGINT NOT NULL  COMMENT '集群ID（外键 ➔ clusters.cluster\_id）',
  `bp_name` VARCHAR(100) NOT NULL  COMMENT '关联的蓝图名称（可能指向 blueprint 表）',
  `cluster_properties` LONGTEXT NULL  COMMENT '集群属性（JSON格式配置）',
  `cluster_attributes` LONGTEXT NULL  COMMENT '集群高级参数（如网络策略）',
  `description` VARCHAR(1024) NULL  COMMENT '请求描述',
  `provision_action` VARCHAR(255) NULL  COMMENT '部署动作（如“仅安装”、“安装并启动”）',
  `id` BIGINT NOT NULL  COMMENT '主机组ID（主键）',
  `name` VARCHAR(255) NOT NULL  COMMENT '组名称（如“worker\_group”）',
  `group_properties` LONGTEXT NULL  COMMENT '组级配置（如软件版本）',
  `group_attributes` LONGTEXT NULL  COMMENT '组级扩展参数',
  `request_id` BIGINT NOT NULL  COMMENT '所属请求ID（外键 ➔ topology\_request.id）',
  `id` BIGINT NOT NULL  COMMENT '主机信息ID（主键）',
  `group_id` BIGINT NOT NULL  COMMENT '所属组ID（外键 ➔ topology\_hostgroup.id）',
  `fqdn` VARCHAR(255) NULL  COMMENT '主机完全限定域名',
  `host_id` BIGINT NULL  COMMENT '主机物理ID（外键 ➔ hosts.host\_id）',
  `host_count` INTEGER NULL  COMMENT '主机数量（动态扩展场景）',
  `predicate` VARCHAR(2048) NULL  COMMENT '筛选规则（如特定硬件要求）',
  `rack_info` VARCHAR(255) NULL  COMMENT '机架信息（如“rack-01”）',
  `id` BIGINT NOT NULL  COMMENT '逻辑请求ID（主键）',
  `request_id` BIGINT NOT NULL  COMMENT '拓扑请求ID（外键 ➔ topology\_request.id）',
  `description` VARCHAR(1024) NULL  COMMENT '阶段描述',
  `id` BIGINT NOT NULL  COMMENT '主机请求ID（主键）',
  `logical_request_id` BIGINT NOT NULL  COMMENT '逻辑请求ID（外键 ➔ topology\_logical\_request.id）',
  `group_id` BIGINT NOT NULL  COMMENT '所属主机组ID（外键 ➔ topology\_hostgroup.id）',
  `stage_id` BIGINT NOT NULL  COMMENT '执行阶段ID',
  `host_name` VARCHAR(255) NULL  COMMENT '主机名（动态分配时为空）',
  `status` VARCHAR(255) NULL  COMMENT '执行状态（如“PENDING”、“COMPLETED”）',
  `status_message` VARCHAR(1024) NULL  COMMENT '状态详情（如错误日志）',
  `id` BIGINT NOT NULL  COMMENT '任务ID（主键）',
  `host_request_id` BIGINT NOT NULL  COMMENT '主机请求ID（外键 ➔ topology\_host\_request.id）',
  `type` VARCHAR(255) NOT NULL  COMMENT '任务类型（如“INSTALL”、“CONFIGURE”）',
  `id` BIGINT NOT NULL  COMMENT '逻辑任务ID（主键）',
  `host_task_id` BIGINT NOT NULL  COMMENT '主机任务ID（外键 ➔ topology\_host\_task.id）',
  `physical_task_id` BIGINT NULL  COMMENT '物理任务ID（外键 ➔ host\_role\_command.task\_id）',
  `component` VARCHAR(255) NOT NULL  COMMENT '组件名称（如“HDFS\_NAMENODE”）',
  PRIMARY KEY (artifact_name, foreign_keys),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='构件表';

DROP TABLE IF EXISTS `setting`;
CREATE TABLE `setting` (
  `id` BIGINT NOT NULL  COMMENT '设置项ID（主键）',
  `name` VARCHAR(255) NOT NULL  COMMENT '设置项名称（唯一约束，如“smtp.host”）',
  `setting_type` VARCHAR(255) NOT NULL  COMMENT '类型（如“mail”、“security”）',
  `content` TEXT NOT NULL  COMMENT '配置值（JSON/键值对）',
  `updated_by` VARCHAR(255) NOT NULL DEFAULT '''\_db''' COMMENT '最后修改者（默认系统操作）',
  `update_timestamp` BIGINT NOT NULL  COMMENT '最后更新时间戳',
  PRIMARY KEY (`id`),
  UNIQUE KEY `UQ_setting_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统设置表';

DROP TABLE IF EXISTS `remotecloudcluster`;
CREATE TABLE `remotecloudcluster` (
  `cluster_id` BIGINT NOT NULL  COMMENT '集群唯一ID（主键）',
  `name` VARCHAR(255) NOT NULL  COMMENT '集群名称（全局唯一）',
  `username` VARCHAR(255) NOT NULL  COMMENT '认证用户名',
  `url` VARCHAR(255) NOT NULL  COMMENT '集群API访问地址',
  `password` VARCHAR(255) NOT NULL  COMMENT '认证密码（建议加密存储）',
  PRIMARY KEY (`cluster_id`),
  UNIQUE KEY `UQ_remote_cloud_cluster` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='远程集群表';

DROP TABLE IF EXISTS `remotecloudclusterservice`;
CREATE TABLE `remotecloudclusterservice` (
  `id` BIGINT NOT NULL  COMMENT '服务关联ID（主键）',
  `cluster_id` BIGINT NOT NULL  COMMENT '集群ID（外键 ➔ remotecloudcluster.cluster\_id）',
  `service_name` VARCHAR(255) NOT NULL  COMMENT '服务名称',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='远程集群服务表';