package com.cloudrealm.platform.model.agent;

import lombok.Data;
import java.util.List;

@Data
public class AgentRegistrationRequest {
    private String hostname;
    private String ipv4;
    private String osType;
    private String osArch;
    private Integer cpuCount;
    private Long totalMem;
    private String agentVersion;
}
