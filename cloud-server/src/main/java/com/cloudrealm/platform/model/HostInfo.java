package com.cloudrealm.platform.model;

import java.math.BigDecimal;
import java.util.List;

public class HostInfo {
    private Long hostId;
    private String hostname;
    private String ip;
    private String publicHostName;
    private String role;
    private Status status;
    private String agentStatus;
    private Integer cores;
    private String cpuInfo;
    private BigDecimal cpuUsage;
    private String memory;
    private Long totalMemory;
    private Long usedMemory;
    private BigDecimal memoryUsage;
    private Long totalDisk;
    private Long usedDisk;
    private BigDecimal diskUsage;
    private String osType;
    private String osArch;
    private String osInfo;
    private String rackInfo;
    private String agentVersion;
    private String diskInfo;
    private String networkInfo;
    private Long lastHeartbeatTime;
    private Long lastRegistrationTime;
    private List<String> tags;
    private List<String> components;
    private String uptime;

    public HostInfo() {}

    // Getters and Setters
    public Long getHostId() { return hostId; }
    public void setHostId(Long hostId) { this.hostId = hostId; }

    public String getHostname() { return hostname; }
    public void setHostname(String hostname) { this.hostname = hostname; }

    public String getIp() { return ip; }
    public void setIp(String ip) { this.ip = ip; }

    public String getPublicHostName() { return publicHostName; }
    public void setPublicHostName(String publicHostName) { this.publicHostName = publicHostName; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public Status getStatus() { return status; }
    public void setStatus(Status status) { this.status = status; }

    public String getAgentStatus() { return agentStatus; }
    public void setAgentStatus(String agentStatus) { this.agentStatus = agentStatus; }

    public Integer getCores() { return cores; }
    public void setCores(Integer cores) { this.cores = cores; }

    public String getCpuInfo() { return cpuInfo; }
    public void setCpuInfo(String cpuInfo) { this.cpuInfo = cpuInfo; }

    public BigDecimal getCpuUsage() { return cpuUsage; }
    public void setCpuUsage(BigDecimal cpuUsage) { this.cpuUsage = cpuUsage; }

    public String getMemory() { return memory; }
    public void setMemory(String memory) { this.memory = memory; }

    public Long getTotalMemory() { return totalMemory; }
    public void setTotalMemory(Long totalMemory) { this.totalMemory = totalMemory; }

    public Long getUsedMemory() { return usedMemory; }
    public void setUsedMemory(Long usedMemory) { this.usedMemory = usedMemory; }

    public BigDecimal getMemoryUsage() { return memoryUsage; }
    public void setMemoryUsage(BigDecimal memoryUsage) { this.memoryUsage = memoryUsage; }

    public Long getTotalDisk() { return totalDisk; }
    public void setTotalDisk(Long totalDisk) { this.totalDisk = totalDisk; }

    public Long getUsedDisk() { return usedDisk; }
    public void setUsedDisk(Long usedDisk) { this.usedDisk = usedDisk; }

    public BigDecimal getDiskUsage() { return diskUsage; }
    public void setDiskUsage(BigDecimal diskUsage) { this.diskUsage = diskUsage; }

    public String getOsType() { return osType; }
    public void setOsType(String osType) { this.osType = osType; }

    public String getOsArch() { return osArch; }
    public void setOsArch(String osArch) { this.osArch = osArch; }

    public String getOsInfo() { return osInfo; }
    public void setOsInfo(String osInfo) { this.osInfo = osInfo; }

    public String getRackInfo() { return rackInfo; }
    public void setRackInfo(String rackInfo) { this.rackInfo = rackInfo; }

    public String getAgentVersion() { return agentVersion; }
    public void setAgentVersion(String agentVersion) { this.agentVersion = agentVersion; }

    public String getDiskInfo() { return diskInfo; }
    public void setDiskInfo(String diskInfo) { this.diskInfo = diskInfo; }

    public String getNetworkInfo() { return networkInfo; }
    public void setNetworkInfo(String networkInfo) { this.networkInfo = networkInfo; }

    public Long getLastHeartbeatTime() { return lastHeartbeatTime; }
    public void setLastHeartbeatTime(Long lastHeartbeatTime) { this.lastHeartbeatTime = lastHeartbeatTime; }

    public Long getLastRegistrationTime() { return lastRegistrationTime; }
    public void setLastRegistrationTime(Long lastRegistrationTime) { this.lastRegistrationTime = lastRegistrationTime; }

    public List<String> getTags() { return tags; }
    public void setTags(List<String> tags) { this.tags = tags; }

    public List<String> getComponents() { return components; }
    public void setComponents(List<String> components) { this.components = components; }

    public String getUptime() { return uptime; }
    public void setUptime(String uptime) { this.uptime = uptime; }
}
