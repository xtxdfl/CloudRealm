package com.cloudrealm.platform.model.agent;

import lombok.Data;
import java.util.List;

@Data
public class AgentHeartbeatResponse {
    private String responseId;
    private List<AgentCommand> executionCommands;

    @Data
    public static class AgentCommand {
        private Long taskId;
        private String commandType; // START, STOP, INSTALL, EXECUTE
        private String componentName;
        private String payload; // JSON params
    }
}
