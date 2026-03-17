package com.cloudrealm.platform.entity.state;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "servicecomponentdesiredstate")
public class ServiceComponentDesiredStateEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "component_name")
    private String componentName;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "desired_repo_version_id")
    private Long desiredRepoVersionId;

    @Column(name = "desired_state")
    private String desiredState; // STARTED, INSTALLED

    @Column(name = "service_name")
    private String serviceName;

    @Column(name = "recovery_enabled")
    private Integer recoveryEnabled = 0;

    @Column(name = "repo_state")
    private String repoState = "NOT_REQUIRED";
}
