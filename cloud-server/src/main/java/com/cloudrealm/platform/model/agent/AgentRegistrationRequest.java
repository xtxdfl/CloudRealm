package com.cloudrealm.platform.model.agent;

import lombok.Data;
import java.math.BigDecimal;
import java.util.List;

@Data
public class AgentRegistrationRequest {
    private String hostname;
    private String publicHostname;
    private String ipv4;
    private String ipv6;
    private String osType;
    private String osArch;
    private String osInfo;
    private Integer cpuCount;
    private String cpuInfo;
    private Long totalMem;
    private Long totalDisk;
    private String diskInfo;  // JSON格式的磁盘信息
    private String networkInfo;  // JSON格式的网络信息
    private String agentVersion;
    private String rackInfo;
}
