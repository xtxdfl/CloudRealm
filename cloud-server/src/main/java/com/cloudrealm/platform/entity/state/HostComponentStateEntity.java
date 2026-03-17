package com.cloudrealm.platform.entity.state;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "hostcomponentstate")
public class HostComponentStateEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "component_name")
    private String componentName;

    @Column(name = "version")
    private String version = "UNKNOWN";

    @Column(name = "current_state")
    private String currentState; // STARTED, INSTALLED, UNKNOWN

    @Column(name = "last_live_state")
    private String lastLiveState = "UNKNOWN";

    @Column(name = "host_id")
    private Long hostId;

    @Column(name = "service_name")
    private String serviceName;

    @Column(name = "upgrade_state")
    private String upgradeState = "NONE";
}
