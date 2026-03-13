package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.model.HostInfo;
import com.cloudrealm.platform.service.HostService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/hosts")
@CrossOrigin(origins = "*") // Allow frontend access
public class HostController {

    @Autowired
    private HostService hostService;

    @GetMapping
    public List<HostInfo> getHosts() {
        return hostService.getAllHosts();
    }

    @PostMapping
    public ResponseEntity<String> addHost(@RequestBody HostInfo host) {
        hostService.addHost(host);
        return ResponseEntity.ok("Host added successfully");
    }

    @PostMapping("/batch/start")
    public ResponseEntity<Map<String, Object>> batchStart(@RequestBody List<String> hostnames) {
        hostService.batchStart(hostnames);
        return ResponseEntity.ok(Map.of("message", "Batch start initiated", "hosts", hostnames));
    }

    @PostMapping("/batch/stop")
    public ResponseEntity<Map<String, Object>> batchStop(@RequestBody List<String> hostnames) {
        hostService.batchStop(hostnames);
        return ResponseEntity.ok(Map.of("message", "Batch stop initiated", "hosts", hostnames));
    }

    @PostMapping("/batch/restart")
    public ResponseEntity<Map<String, Object>> batchRestart(@RequestBody List<String> hostnames) {
        hostService.batchRestart(hostnames);
        return ResponseEntity.ok(Map.of("message", "Batch restart initiated", "hosts", hostnames));
    }
}
