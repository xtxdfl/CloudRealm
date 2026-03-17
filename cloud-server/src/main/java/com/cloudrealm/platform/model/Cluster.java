package com.cloudrealm.platform.model;

public class Cluster {
    private Long clusterId;
    private Long resourceId;
    private Long upgradeId;
    private String clusterInfo;
    private String clusterName;
    private String provisioningState;
    private String securityType;
    private String desiredClusterState;
    private Long desiredStackId;

    public Cluster() {}

    public Cluster(Long clusterId, Long resourceId, Long upgradeId, String clusterInfo, String clusterName, String provisioningState, String securityType, String desiredClusterState, Long desiredStackId) {
        this.clusterId = clusterId;
        this.resourceId = resourceId;
        this.upgradeId = upgradeId;
        this.clusterInfo = clusterInfo;
        this.clusterName = clusterName;
        this.provisioningState = provisioningState;
        this.securityType = securityType;
        this.desiredClusterState = desiredClusterState;
        this.desiredStackId = desiredStackId;
    }

    public Long getClusterId() { return clusterId; }
    public void setClusterId(Long clusterId) { this.clusterId = clusterId; }

    public Long getResourceId() { return resourceId; }
    public void setResourceId(Long resourceId) { this.resourceId = resourceId; }

    public Long getUpgradeId() { return upgradeId; }
    public void setUpgradeId(Long upgradeId) { this.upgradeId = upgradeId; }

    public String getClusterInfo() { return clusterInfo; }
    public void setClusterInfo(String clusterInfo) { this.clusterInfo = clusterInfo; }

    public String getClusterName() { return clusterName; }
    public void setClusterName(String clusterName) { this.clusterName = clusterName; }

    public String getProvisioningState() { return provisioningState; }
    public void setProvisioningState(String provisioningState) { this.provisioningState = provisioningState; }

    public String getSecurityType() { return securityType; }
    public void setSecurityType(String securityType) { this.securityType = securityType; }

    public String getDesiredClusterState() { return desiredClusterState; }
    public void setDesiredClusterState(String desiredClusterState) { this.desiredClusterState = desiredClusterState; }

    public Long getDesiredStackId() { return desiredStackId; }
    public void setDesiredStackId(Long desiredStackId) { this.desiredStackId = desiredStackId; }
}
