package com.cloudrealm.platform.model;

public class Mpack {
    private Long id;
    private String mpackName;
    private String mpackVersion;
    private String mpackUri;
    private Long registryId;

    public Mpack() {}

    public Mpack(Long id, String mpackName, String mpackVersion, String mpackUri, Long registryId) {
        this.id = id;
        this.mpackName = mpackName;
        this.mpackVersion = mpackVersion;
        this.mpackUri = mpackUri;
        this.registryId = registryId;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getMpackName() { return mpackName; }
    public void setMpackName(String mpackName) { this.mpackName = mpackName; }

    public String getMpackVersion() { return mpackVersion; }
    public void setMpackVersion(String mpackVersion) { this.mpackVersion = mpackVersion; }

    public String getMpackUri() { return mpackUri; }
    public void setMpackUri(String mpackUri) { this.mpackUri = mpackUri; }

    public Long getRegistryId() { return registryId; }
    public void setRegistryId(Long registryId) { this.registryId = registryId; }
}
