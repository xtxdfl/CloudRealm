package com.cloudrealm.platform.entity.state;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "clusterservices")
@IdClass(ClusterServiceId.class)
public class ClusterServiceEntity {
    
    @Id
    @Column(name = "service_name")
    private String serviceName;
    
    @Id
    @Column(name = "cluster_id")
    private Long clusterId;
    
    @Column(name = "service_enabled")
    private Integer serviceEnabled;
}
