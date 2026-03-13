package com.cloudrealm.platform.model;

import java.util.List;

public class HostInfo {
    private String hostname;
    private String ip;
    private String role;
    private Status status;
    private Integer cores;
    private String memory;
    private List<String> components;
    private String uptime;

    public HostInfo() {}

    public HostInfo(String hostname, String ip, String role, Status status, Integer cores, String memory, List<String> components, String uptime) {
        this.hostname = hostname;
        this.ip = ip;
        this.role = role;
        this.status = status;
        this.cores = cores;
        this.memory = memory;
        this.components = components;
        this.uptime = uptime;
    }

    // Getters and Setters
    public String getHostname() { return hostname; }
    public void setHostname(String hostname) { this.hostname = hostname; }

    public String getIp() { return ip; }
    public void setIp(String ip) { this.ip = ip; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public Status getStatus() { return status; }
    public void setStatus(Status status) { this.status = status; }

    public Integer getCores() { return cores; }
    public void setCores(Integer cores) { this.cores = cores; }

    public String getMemory() { return memory; }
    public void setMemory(String memory) { this.memory = memory; }

    public List<String> getComponents() { return components; }
    public void setComponents(List<String> components) { this.components = components; }

    public String getUptime() { return uptime; }
    public void setUptime(String uptime) { this.uptime = uptime; }
}
