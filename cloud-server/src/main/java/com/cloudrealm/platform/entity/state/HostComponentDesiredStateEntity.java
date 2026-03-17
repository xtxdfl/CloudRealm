package com.cloudrealm.platform.entity.state;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "hostcomponentdesiredstate")
public class HostComponentDesiredStateEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "component_name")
    private String componentName;

    @Column(name = "desired_state")
    private String desiredState; // STARTED, INSTALLED

    @Column(name = "host_id")
    private Long hostId;

    @Column(name = "service_name")
    private String serviceName;

    @Column(name = "admin_state")
    private String adminState;

    @Column(name = "maintenance_state")
    private String maintenanceState = "ACTIVE";

    @Column(name = "blueprint_provisioning_state")
    private String blueprintProvisioningState = "NONE";

    @Column(name = "restart_required")
    private Integer restartRequired = 0;
}
