package com.cloudrealm.platform.model;

public class Registry {
    private Long id;
    private String registryName;
    private String registryType; // DOCKER, MAVEN
    private String registryUri;

    public Registry() {}

    public Registry(Long id, String registryName, String registryType, String registryUri) {
        this.id = id;
        this.registryName = registryName;
        this.registryType = registryType;
        this.registryUri = registryUri;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getRegistryName() { return registryName; }
    public void setRegistryName(String registryName) { this.registryName = registryName; }

    public String getRegistryType() { return registryType; }
    public void setRegistryType(String registryType) { this.registryType = registryType; }

    public String getRegistryUri() { return registryUri; }
    public void setRegistryUri(String registryUri) { this.registryUri = registryUri; }
}
