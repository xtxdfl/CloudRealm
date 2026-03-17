package com.cloudrealm.platform.model;

public class AdminResourceType {
    private Integer resourceTypeId;
    private String resourceTypeName;

    public AdminResourceType() {}

    public AdminResourceType(Integer resourceTypeId, String resourceTypeName) {
        this.resourceTypeId = resourceTypeId;
        this.resourceTypeName = resourceTypeName;
    }

    public Integer getResourceTypeId() { return resourceTypeId; }
    public void setResourceTypeId(Integer resourceTypeId) { this.resourceTypeId = resourceTypeId; }

    public String getResourceTypeName() { return resourceTypeName; }
    public void setResourceTypeName(String resourceTypeName) { this.resourceTypeName = resourceTypeName; }
}
