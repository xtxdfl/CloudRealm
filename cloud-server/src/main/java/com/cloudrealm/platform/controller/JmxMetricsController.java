package com.cloudrealm.platform.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/jmx")
@CrossOrigin(origins = "*")
public class JmxMetricsController {

    // 1. Push: Agent pushes JMX metrics to server
    @PostMapping("/metrics/push")
    public ResponseEntity<String> pushMetrics(@RequestBody Map<String, Object> metricsPayload) {
        System.out.println("Received JMX metrics push: " + metricsPayload);
        // TODO: Save metrics to TSDB or internal DB
        return ResponseEntity.ok("Metrics received successfully");
    }

    // 2. Pull: Server initiates pull from Agent/JMX exporter
    @GetMapping("/metrics/pull/{hostname}/{component}")
    public ResponseEntity<Map<String, Object>> pullMetrics(
            @PathVariable String hostname,
            @PathVariable String component) {
        System.out.println("Pulling JMX metrics for " + component + " on " + hostname);
        // TODO: Call cloud-jmx or agent to pull metrics
        return ResponseEntity.ok(Map.of(
                "hostname", hostname,
                "component", component,
                "metrics", Map.of("cpuLoad", 0.45, "heapMemoryUsage", 1024576)
        ));
    }
}
