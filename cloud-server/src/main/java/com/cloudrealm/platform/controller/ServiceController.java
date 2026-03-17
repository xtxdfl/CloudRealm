package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.model.ServiceInfo;
import com.cloudrealm.platform.model.ServiceStats;
import com.cloudrealm.platform.service.ServiceService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/services")
@CrossOrigin(origins = "*") // Allow frontend access
public class ServiceController {

    @Autowired
    private ServiceService serviceService;

    @GetMapping
    public List<ServiceInfo> getServices() {
        return serviceService.getAllServices();
    }

    @GetMapping("/stats")
    public ServiceStats getServiceStats() {
        return serviceService.getServiceStats();
    }

    @GetMapping("/{name}")
    public ResponseEntity<ServiceInfo> getService(@PathVariable String name) {
        return serviceService.getServiceByName(name)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{name}/start")
    public ResponseEntity<?> startService(@PathVariable String name) {
        boolean success = serviceService.startService(name);
        if (success) {
            return ResponseEntity.ok(Map.of("message", "Service " + name + " started successfully"));
        } else {
            return ResponseEntity.notFound().build();
        }
    }

    @PostMapping("/{name}/stop")
    public ResponseEntity<?> stopService(@PathVariable String name) {
        boolean success = serviceService.stopService(name);
        if (success) {
            return ResponseEntity.ok(Map.of("message", "Service " + name + " stopped successfully"));
        } else {
            return ResponseEntity.notFound().build();
        }
    }

    @PostMapping("/{name}/restart")
    public ResponseEntity<?> restartService(@PathVariable String name) {
        boolean success = serviceService.restartService(name);
        if (success) {
            return ResponseEntity.ok(Map.of("message", "Service " + name + " restart initiated", "job_id", "job_" + System.currentTimeMillis()));
        } else {
            return ResponseEntity.notFound().build();
        }
    }
}
