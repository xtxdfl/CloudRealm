package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.entity.action.RequestEntity;
import com.cloudrealm.platform.service.ActionQueueService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/action-queue")
@CrossOrigin(origins = "*")
public class ActionQueueController {

    @Autowired
    private ActionQueueService actionQueueService;

    @PostMapping("/requests")
    public ResponseEntity<RequestEntity> createRequest(@RequestBody Map<String, Object> payload) {
        String requestContext = (String) payload.getOrDefault("request_context", "Custom Action");
        List<String> hosts = (List<String>) payload.get("hosts");
        String role = (String) payload.get("role");
        String command = (String) payload.get("command");

        RequestEntity request = actionQueueService.createActionRequest(requestContext, hosts, role, command);
        return ResponseEntity.ok(request);
    }

    @GetMapping("/requests")
    public ResponseEntity<List<RequestEntity>> getAllRequests() {
        return ResponseEntity.ok(actionQueueService.getAllRequests());
    }
}
