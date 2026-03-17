package com.cloudrealm.platform.model;

public class AdminResource {
    private Long resourceId;
    private Integer resourceTypeId;

    public AdminResource() {}

    public AdminResource(Long resourceId, Integer resourceTypeId) {
        this.resourceId = resourceId;
        this.resourceTypeId = resourceTypeId;
    }

    public Long getResourceId() { return resourceId; }
    public void setResourceId(Long resourceId) { this.resourceId = resourceId; }

    public Integer getResourceTypeId() { return resourceTypeId; }
    public void setResourceTypeId(Integer resourceTypeId) { this.resourceTypeId = resourceTypeId; }
}
