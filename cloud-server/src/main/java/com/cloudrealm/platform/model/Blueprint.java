package com.cloudrealm.platform.model;

public class Blueprint {
    private String blueprintName;
    private Long stackId;
    private String securityType;
    private String securityDescriptorReference;

    public Blueprint() {}

    public Blueprint(String blueprintName, Long stackId, String securityType, String securityDescriptorReference) {
        this.blueprintName = blueprintName;
        this.stackId = stackId;
        this.securityType = securityType;
        this.securityDescriptorReference = securityDescriptorReference;
    }

    public String getBlueprintName() { return blueprintName; }
    public void setBlueprintName(String blueprintName) { this.blueprintName = blueprintName; }

    public Long getStackId() { return stackId; }
    public void setStackId(Long stackId) { this.stackId = stackId; }

    public String getSecurityType() { return securityType; }
    public void setSecurityType(String securityType) { this.securityType = securityType; }

    public String getSecurityDescriptorReference() { return securityDescriptorReference; }
    public void setSecurityDescriptorReference(String securityDescriptorReference) { this.securityDescriptorReference = securityDescriptorReference; }
}
