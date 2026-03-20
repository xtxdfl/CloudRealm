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
        String requestContext = payload.getOrDefault("request_context", "Custom Action").toString();
        @SuppressWarnings("unchecked")
        List<String> hosts = (List<String>) payload.get("hosts");
        String role = payload.get("role").toString();
        String command = payload.get("command").toString();

        RequestEntity request = actionQueueService.createActionRequest(requestContext, hosts, role, command);
        return ResponseEntity.ok(request);
    }

    @GetMapping("/requests")
    public ResponseEntity<List<RequestEntity>> getAllRequests() {
        return ResponseEntity.ok(actionQueueService.getAllRequests());
    }
}
