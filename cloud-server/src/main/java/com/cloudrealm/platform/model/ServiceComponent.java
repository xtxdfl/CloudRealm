package com.cloudrealm.platform.model;

public class ServiceComponent {
    private Long id;
    private Long clusterId;
    private String serviceName;

    public ServiceComponent() {}

    public ServiceComponent(Long id, Long clusterId, String serviceName) {
        this.id = id;
        this.clusterId = clusterId;
        this.serviceName = serviceName;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getClusterId() { return clusterId; }
    public void setClusterId(Long clusterId) { this.clusterId = clusterId; }

    public String getServiceName() { return serviceName; }
    public void setServiceName(String serviceName) { this.serviceName = serviceName; }
}
