package com.cloudrealm.platform.model;

public class Extension {
    private Long extensionId;
    private String extensionName;
    private String extensionVersion;

    public Extension() {}

    public Extension(Long extensionId, String extensionName, String extensionVersion) {
        this.extensionId = extensionId;
        this.extensionName = extensionName;
        this.extensionVersion = extensionVersion;
    }

    public Long getExtensionId() { return extensionId; }
    public void setExtensionId(Long extensionId) { this.extensionId = extensionId; }

    public String getExtensionName() { return extensionName; }
    public void setExtensionName(String extensionName) { this.extensionName = extensionName; }

    public String getExtensionVersion() { return extensionVersion; }
    public void setExtensionVersion(String extensionVersion) { this.extensionVersion = extensionVersion; }
}
