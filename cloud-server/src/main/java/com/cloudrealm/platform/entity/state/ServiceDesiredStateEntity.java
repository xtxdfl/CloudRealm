package com.cloudrealm.platform.entity.state;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "servicedesiredstate")
@IdClass(ClusterServiceId.class)
public class ServiceDesiredStateEntity {

    @Id
    @Column(name = "cluster_id")
    private Long clusterId;

    @Id
    @Column(name = "service_name")
    private String serviceName;

    @Column(name = "desired_host_role_mapping")
    private Integer desiredHostRoleMapping = 0;

    @Column(name = "desired_repo_version_id")
    private Long desiredRepoVersionId;

    @Column(name = "desired_state")
    private String desiredState; // INSTALLED, STARTED, STOPPED

    @Column(name = "maintenance_state")
    private String maintenanceState = "ACTIVE";

    @Column(name = "credential_store_enabled")
    private Integer credentialStoreEnabled = 0;
}
