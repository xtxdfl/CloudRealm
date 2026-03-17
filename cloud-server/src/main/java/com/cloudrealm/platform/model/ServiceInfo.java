package com.cloudrealm.platform.model;

import java.util.List;

public class ServiceInfo {
    private String name;
    private String version;
    private Status status;
    private String configVersion;
    private String role;
    private List<String> components;

    public ServiceInfo() {}

    public ServiceInfo(String name, String version, Status status, String configVersion, String role, List<String> components) {
        this.name = name;
        this.version = version;
        this.status = status;
        this.configVersion = configVersion;
        this.role = role;
        this.components = components;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getVersion() {
        return version;
    }

    public void setVersion(String version) {
        this.version = version;
    }

    public Status getStatus() {
        return status;
    }

    public void setStatus(Status status) {
        this.status = status;
    }

    public String getConfigVersion() {
        return configVersion;
    }

    public void setConfigVersion(String configVersion) {
        this.configVersion = configVersion;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public List<String> getComponents() {
        return components;
    }

    public void setComponents(List<String> components) {
        this.components = components;
    }
}
