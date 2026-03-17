package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.entity.ClusterEntity;
import com.cloudrealm.platform.service.ClusterManagementService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/clusters")
@CrossOrigin(origins = "*")
public class ClusterManagementController {

    @Autowired
    private ClusterManagementService clusterManagementService;

    @PostMapping
    public ResponseEntity<ClusterEntity> createCluster(@RequestBody Map<String, String> payload) {
        String clusterName = payload.get("cluster_name");
        String stackName = payload.get("stack_name");
        String stackVersion = payload.get("stack_version");
        ClusterEntity cluster = clusterManagementService.createCluster(clusterName, stackName, stackVersion);
        return ResponseEntity.ok(cluster);
    }

    @GetMapping
    public ResponseEntity<List<ClusterEntity>> getAllClusters() {
        return ResponseEntity.ok(clusterManagementService.getAllClusters());
    }

    @PostMapping("/{clusterId}/services")
    public ResponseEntity<String> addService(@PathVariable Long clusterId, @RequestBody Map<String, String> payload) {
        String serviceName = payload.get("service_name");
        clusterManagementService.addService(clusterId, serviceName);
        return ResponseEntity.ok("Service added");
    }

    @PostMapping("/{clusterId}/services/{serviceName}/components")
    public ResponseEntity<String> addServiceComponent(@PathVariable Long clusterId, @PathVariable String serviceName, @RequestBody Map<String, String> payload) {
        String componentName = payload.get("component_name");
        clusterManagementService.addServiceComponent(clusterId, serviceName, componentName);
        return ResponseEntity.ok("Component added");
    }
}
