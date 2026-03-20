package com.cloudrealm.platform.model.agent;

import lombok.Data;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

@Data
public class AgentHeartbeatRequest {
    private String hostname;
    private Long timestamp;
    private String agentStatus;

    // 主机资源信息（可选，心跳时是否上报完整信息可配置）
    private Integer cpuCount;
    private BigDecimal cpuUsage;
    private Long totalMem;
    private Long usedMem;
    private BigDecimal memoryUsage;
    private Long totalDisk;
    private Long usedDisk;
    private BigDecimal diskUsage;
    private String diskInfo;  // JSON格式的磁盘详情
    private String networkInfo;  // JSON格式的网络详情

    // Live State of components on this host
    private List<ComponentStatus> componentStatus;

    // Command reports (Action results)
    private List<CommandReport> commandReports;

    @Data
    public static class ComponentStatus {
        private String componentName;
        private String status; // STARTED, STOPPED, INSTALLED
    }

    @Data
    public static class CommandReport {
        private Long taskId;
        private String status; // IN_PROGRESS, COMPLETED, FAILED
        private Integer exitCode;
        private String stdout;
        private String stderr;
    }
}
