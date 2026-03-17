package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.model.agent.AgentHeartbeatRequest;
import com.cloudrealm.platform.model.agent.AgentHeartbeatResponse;
import com.cloudrealm.platform.model.agent.AgentRegistrationRequest;
import com.cloudrealm.platform.service.AgentService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/agent")
@CrossOrigin(origins = "*")
public class AgentController {

    @Autowired
    private AgentService agentService;

    @PostMapping("/register")
    public ResponseEntity<String> registerAgent(@RequestBody AgentRegistrationRequest request) {
        agentService.registerAgent(request);
        return ResponseEntity.ok("Registered successfully");
    }

    @PostMapping("/heartbeat")
    public ResponseEntity<AgentHeartbeatResponse> heartbeat(@RequestBody AgentHeartbeatRequest request) {
        AgentHeartbeatResponse response = agentService.processHeartbeat(request);
        return ResponseEntity.ok(response);
    }
}
