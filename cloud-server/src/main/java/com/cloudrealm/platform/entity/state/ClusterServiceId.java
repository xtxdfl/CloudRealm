package com.cloudrealm.platform.entity.state;

import lombok.Data;
import java.io.Serializable;

@Data
public class ClusterServiceId implements Serializable {
    private String serviceName;
    private Long clusterId;
}
