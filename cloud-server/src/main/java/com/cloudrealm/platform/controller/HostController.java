package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.model.HostInfo;
import com.cloudrealm.platform.service.HostService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/hosts")
@CrossOrigin(origins = "*")
public class HostController {

    @Autowired
    private HostService hostService;

    /**
     * 获取所有主机
     */
    @GetMapping
    public List<HostInfo> getHosts() {
        return hostService.getAllHosts();
    }

    /**
     * 搜索主机
     */
    @GetMapping("/search")
    public List<HostInfo> searchHosts(
            @RequestParam(required = false) String hostName,
            @RequestParam(required = false) String ipv4,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String agentStatus,
            @RequestParam(required = false) String rackInfo) {
        return hostService.searchHosts(hostName, ipv4, status, agentStatus, rackInfo);
    }

    /**
     * 获取单个主机详情
     */
    @GetMapping("/{hostname}")
    public ResponseEntity<HostInfo> getHost(@PathVariable String hostname) {
        return hostService.getHostByHostname(hostname)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * 手动添加主机
     */
    @PostMapping
    public ResponseEntity<?> addHost(@RequestBody HostInfo host) {
        try {
            HostEntity entity = hostService.addHost(host);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Host added successfully");
            response.put("host", entity);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 批量导入主机
     */
    @PostMapping("/batch/import")
    public ResponseEntity<?> batchImportHosts(@RequestBody List<HostInfo> hosts) {
        try {
            List<HostEntity> results = hostService.batchImportHosts(hosts, null);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Batch import completed");
            response.put("count", results.size());
            response.put("hosts", results);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 批量启动主机
     */
    @PostMapping("/batch/start")
    public ResponseEntity<?> batchStart(@RequestBody List<String> hostnames) {
        try {
            hostService.batchStart(hostnames);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Batch start initiated");
            response.put("hosts", hostnames);
            response.put("timestamp", System.currentTimeMillis());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 批量停止主机
     */
    @PostMapping("/batch/stop")
    public ResponseEntity<?> batchStop(@RequestBody List<String> hostnames) {
        try {
            hostService.batchStop(hostnames);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Batch stop initiated");
            response.put("hosts", hostnames);
            response.put("timestamp", System.currentTimeMillis());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 批量重启主机
     */
    @PostMapping("/batch/restart")
    public ResponseEntity<?> batchRestart(@RequestBody List<String> hostnames) {
        try {
            hostService.batchRestart(hostnames);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Batch restart initiated");
            response.put("hosts", hostnames);
            response.put("timestamp", System.currentTimeMillis());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 删除单个主机（根据ID）
     */
    @DeleteMapping("/id/{hostId}")
    public ResponseEntity<?> deleteHostById(@PathVariable Long hostId) {
        try {
            hostService.deleteHost(hostId);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Host deleted successfully");
            response.put("hostId", hostId);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 删除主机（根据主机名）
     */
    @DeleteMapping("/{hostname}")
    public ResponseEntity<?> deleteHost(@PathVariable String hostname) {
        try {
            hostService.deleteHostByHostname(hostname);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Host deleted successfully");
            response.put("hostname", hostname);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 批量删除主机
     */
    @PostMapping("/batch/delete")
    public ResponseEntity<?> batchDeleteHosts(@RequestBody List<Long> hostIds) {
        try {
            hostService.batchDeleteHosts(hostIds);
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Batch delete completed");
            response.put("count", hostIds.size());
            response.put("hostIds", hostIds);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("message", e.getMessage());
            return ResponseEntity.badRequest().body(response);
        }
    }

    /**
     * 获取主机统计信息
     */
    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getHostStats() {
        List<HostInfo> allHosts = hostService.getAllHosts();
        Map<String, Object> stats = new HashMap<>();

        stats.put("total", allHosts.size());
        stats.put("online", allHosts.stream().filter(h -> "ONLINE".equals(h.getAgentStatus())).count());
        stats.put("offline", allHosts.stream().filter(h -> "OFFLINE".equals(h.getAgentStatus())).count());
        stats.put("unhealthy", allHosts.stream().filter(h -> "UNHEALTHY".equals(h.getAgentStatus())).count());

        return ResponseEntity.ok(stats);
    }
}
