package com.cloudrealm.platform.model;

public class ExtensionLink {
    private Long linkId;
    private Long stackId;
    private Long extensionId;

    public ExtensionLink() {}

    public ExtensionLink(Long linkId, Long stackId, Long extensionId) {
        this.linkId = linkId;
        this.stackId = stackId;
        this.extensionId = extensionId;
    }

    public Long getLinkId() { return linkId; }
    public void setLinkId(Long linkId) { this.linkId = linkId; }

    public Long getStackId() { return stackId; }
    public void setStackId(Long stackId) { this.stackId = stackId; }

    public Long getExtensionId() { return extensionId; }
    public void setExtensionId(Long extensionId) { this.extensionId = extensionId; }
}
