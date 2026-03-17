package com.cloudrealm.platform.model.agent;

import lombok.Data;
import java.util.List;
import java.util.Map;

@Data
public class AgentHeartbeatRequest {
    private String hostname;
    private Long timestamp;
    private String agentStatus;
    
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
