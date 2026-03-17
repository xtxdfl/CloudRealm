package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "clusters")
public class ClusterEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "resource_id", nullable = false)
    private Long resourceId;

    @Column(name = "upgrade_id")
    private Long upgradeId;

    @Column(name = "cluster_info", nullable = false)
    private String clusterInfo;

    @Column(name = "cluster_name", nullable = false, unique = true, length = 100)
    private String clusterName;

    @Column(name = "provisioning_state", nullable = false)
    private String provisioningState = "INIT";

    @Column(name = "security_type", nullable = false, length = 32)
    private String securityType = "NONE";

    @Column(name = "desired_cluster_state", nullable = false)
    private String desiredClusterState;

    @Column(name = "desired_stack_id", nullable = false)
    private Long desiredStackId;
}
