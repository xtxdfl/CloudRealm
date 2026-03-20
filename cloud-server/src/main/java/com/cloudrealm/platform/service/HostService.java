package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.entity.HostRegistrationLogEntity;
import com.cloudrealm.platform.entity.HostTagEntity;
import com.cloudrealm.platform.model.HostInfo;
import com.cloudrealm.platform.model.Status;
import com.cloudrealm.platform.repository.HostRegistrationLogRepository;
import com.cloudrealm.platform.repository.HostRepository;
import com.cloudrealm.platform.repository.HostTagMappingRepository;
import com.cloudrealm.platform.repository.HostTagRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class HostService {

    @Autowired
    private HostRepository hostRepository;

    @Autowired
    private HostTagRepository hostTagRepository;

    @Autowired
    private HostTagMappingRepository hostTagMappingRepository;

    @Autowired
    private HostRegistrationLogRepository registrationLogRepository;

    public HostService() {
    }

    public List<HostInfo> getAllHosts() {
        List<HostEntity> entities = hostRepository.findAll();
        return entities.stream().map(this::convertToHostInfo).collect(Collectors.toList());
    }

    /**
     * 手动添加主机
     */
    @Transactional
    public HostEntity addHost(HostInfo host) {
        return addHost(host, "MANUAL", null);
    }

    /**
     * 添加主机（带注册来源）
     */
    @Transactional
    public HostEntity addHost(HostInfo host, String registrationType, String sourceIp) {
        // 检查是否已存在
        Optional<HostEntity> existing = hostRepository.findByHostName(host.getHostname());
        if (existing.isPresent()) {
            throw new RuntimeException("Host with hostname " + host.getHostname() + " already exists");
        }

        HostEntity entity = new HostEntity();
        entity.setHostName(host.getHostname());
        entity.setIpv4(host.getIp());
        entity.setCpuCount(host.getCores() != null ? host.getCores() : 0);
        entity.setCpuInfo(host.getCpuInfo() != null ? host.getCpuInfo() : "Generic CPU");
        entity.setDiscoveryStatus(host.getStatus() != null ? host.getStatus().name() : "UNKNOWN");
        entity.setHostAttributes("{}");
        entity.setLastRegistrationTime(System.currentTimeMillis());
        entity.setLastHeartbeatTime(System.currentTimeMillis());
        entity.setOsArch(host.getOsArch() != null ? host.getOsArch() : "x86_64");
        entity.setOsInfo(host.getOsInfo() != null ? host.getOsInfo() : "Linux");
        entity.setOsType(host.getOsType() != null ? host.getOsType() : "Linux");
        entity.setRackInfo(host.getRackInfo() != null ? host.getRackInfo() : "/default-rack");
        entity.setTotalMem(parseMemoryToBytes(host.getMemory()));
        entity.setAgentStatus("MANUAL_ADDED");

        HostEntity saved = hostRepository.save(entity);

        // 记录注册日志
        logRegistration(saved, registrationType != null ? registrationType : "MANUAL", sourceIp, "SUCCESS", null);

        System.out.println("Host added: " + host.getHostname());
        return saved;
    }

    /**
     * 批量导入主机
     */
    @Transactional
    public List<HostEntity> batchImportHosts(List<HostInfo> hosts, String sourceIp) {
        List<HostEntity> results = new ArrayList<>();
        for (HostInfo host : hosts) {
            try {
                HostEntity entity = addHost(host, "BATCH_IMPORT", sourceIp);
                results.add(entity);
            } catch (Exception e) {
                // 记录失败日志
                logRegistration(null, "BATCH_IMPORT", sourceIp, "FAILED", e.getMessage());
            }
        }
        return results;
    }

    /**
     * 自动发现主机（由Agent自动注册触发）
     */
    @Transactional
    public HostEntity autoRegisterHost(HostInfo host) {
        return addHost(host, "AGENT_AUTO", null);
    }

    /**
     * 记录注册日志
     */
    private void logRegistration(HostEntity host, String type, String sourceIp, String status, String errorMsg) {
        HostRegistrationLogEntity log = new HostRegistrationLogEntity();
        if (host != null) {
            log.setHostId(host.getHostId());
            log.setHostName(host.getHostName());
            log.setIpv4(host.getIpv4());
        }
        log.setRegistrationType(type);
        log.setSourceIp(sourceIp);
        log.setStatus(status);
        log.setErrorMessage(errorMsg);
        log.setRegisteredTime(System.currentTimeMillis());
        registrationLogRepository.save(log);
    }

    /**
     * 搜索主机
     */
    public List<HostInfo> searchHosts(String hostName, String ipv4, String status, String agentStatus, String rackInfo) {
        List<HostEntity> entities = hostRepository.searchHosts(hostName, ipv4, status, agentStatus, rackInfo);
        return entities.stream().map(this::convertToHostInfo).collect(Collectors.toList());
    }

    public void batchStart(List<String> hostnames) {
        System.out.println("Batch starting hosts: " + hostnames);
        List<HostEntity> hosts = hostRepository.findAll().stream()
            .filter(h -> hostnames.contains(h.getHostName()))
            .collect(Collectors.toList());

        hosts.forEach(h -> h.setDiscoveryStatus(Status.HEALTHY.name()));
        hostRepository.saveAll(hosts);
    }

    public void batchStop(List<String> hostnames) {
        System.out.println("Batch stopping hosts: " + hostnames);
        List<HostEntity> hosts = hostRepository.findAll().stream()
            .filter(h -> hostnames.contains(h.getHostName()))
            .collect(Collectors.toList());

        hosts.forEach(h -> h.setDiscoveryStatus(Status.STOPPED.name()));
        hostRepository.saveAll(hosts);
    }

    public void batchRestart(List<String> hostnames) {
        System.out.println("Batch restarting hosts: " + hostnames);
        List<HostEntity> hosts = hostRepository.findAll().stream()
            .filter(h -> hostnames.contains(h.getHostName()))
            .collect(Collectors.toList());

        hosts.forEach(h -> h.setDiscoveryStatus(Status.WARNING.name()));
        hostRepository.saveAll(hosts);
    }

    /**
     * 删除主机
     */
    @Transactional
    public void deleteHost(Long hostId) {
        Optional<HostEntity> host = hostRepository.findById(hostId);
        if (host.isPresent()) {
            String hostname = host.get().getHostName();
            // 移除标签关联
            hostTagMappingRepository.deleteByHostId(hostId);
            // 删除主机
            hostRepository.deleteById(hostId);
            System.out.println("Host deleted: " + hostname);
        }
    }

    /**
     * 根据主机名删除主机
     */
    @Transactional
    public void deleteHostByHostname(String hostname) {
        Optional<HostEntity> host = hostRepository.findByHostName(hostname);
        if (host.isPresent()) {
            Long hostId = host.get().getHostId();
            hostTagMappingRepository.deleteByHostId(hostId);
            hostRepository.delete(host.get());
            System.out.println("Host deleted: " + hostname);
        }
    }

    /**
     * 批量删除主机
     */
    @Transactional
    public void batchDeleteHosts(List<Long> hostIds) {
        for (Long hostId : hostIds) {
            deleteHost(hostId);
        }
    }

    public Optional<HostInfo> getHostByHostname(String hostname) {
        return hostRepository.findByHostName(hostname)
                .map(this::convertToHostInfo);
    }

    public Optional<HostEntity> getHostEntityByHostname(String hostname) {
        return hostRepository.findByHostName(hostname);
    }

    public Optional<HostEntity> getHostEntityById(Long hostId) {
        return hostRepository.findById(hostId);
    }

    /**
     * 获取主机标签
     */
    public List<HostTagEntity> getHostTags(Long hostId) {
        List<Long> tagIds = hostTagMappingRepository.findTagIdsByHostId(hostId);
        return tagIds.stream()
                .map(hostTagRepository::findById)
                .filter(Optional::isPresent)
                .map(Optional::get)
                .collect(Collectors.toList());
    }

    /**
     * 更新主机心跳
     */
    @Transactional
    public void updateHeartbeat(String hostname, HostInfo hostInfo) {
        Optional<HostEntity> existing = hostRepository.findByHostName(hostname);
        if (existing.isPresent()) {
            HostEntity entity = existing.get();
            entity.setLastHeartbeatTime(System.currentTimeMillis());
            entity.setAgentStatus("ONLINE");

            if (hostInfo != null) {
                if (hostInfo.getCores() != null) entity.setCpuCount(hostInfo.getCores());
                if (hostInfo.getMemory() != null) entity.setTotalMem(parseMemoryToBytes(hostInfo.getMemory()));
                if (hostInfo.getCpuUsage() != null) entity.setCpuUsage(hostInfo.getCpuUsage());
                if (hostInfo.getMemoryUsage() != null) entity.setMemoryUsage(hostInfo.getMemoryUsage());
                if (hostInfo.getDiskUsage() != null) entity.setDiskUsage(hostInfo.getDiskUsage());
                if (hostInfo.getAgentVersion() != null) entity.setAgentVersion(hostInfo.getAgentVersion());
            }

            hostRepository.save(entity);
        }
    }

    /**
     * 检查并标记失联主机
     */
    @Transactional
    public void checkStaleHeartbeats() {
        long threshold = System.currentTimeMillis() - (2 * 60 * 1000); // 2分钟超时
        List<HostEntity> staleHosts = hostRepository.findHostsWithStaleHeartbeat(threshold);
        for (HostEntity host : staleHosts) {
            host.setAgentStatus("UNHEALTHY");
            host.setDiscoveryStatus("UNREACHABLE");
            hostRepository.save(host);
        }
    }

    private HostInfo convertToHostInfo(HostEntity entity) {
        HostInfo info = new HostInfo();
        info.setHostId(entity.getHostId());
        info.setHostname(entity.getHostName());
        info.setIp(entity.getIpv4());
        info.setPublicHostName(entity.getPublicHostName());
        info.setRole("Worker");

        try {
            info.setStatus(Status.valueOf(entity.getDiscoveryStatus()));
        } catch (Exception e) {
            info.setStatus(Status.UNKNOWN);
        }

        info.setAgentStatus(entity.getAgentStatus());
        info.setCores(entity.getCpuCount());
        info.setCpuInfo(entity.getCpuInfo());
        info.setCpuUsage(entity.getCpuUsage() != null ? entity.getCpuUsage() : BigDecimal.ZERO);
        info.setMemory(formatMemory(entity.getTotalMem()));
        info.setTotalMemory(entity.getTotalMem());
        info.setUsedMemory(entity.getUsedMem());
        info.setMemoryUsage(entity.getMemoryUsage() != null ? entity.getMemoryUsage() : BigDecimal.ZERO);
        info.setTotalDisk(entity.getTotalDisk());
        info.setUsedDisk(entity.getUsedDisk());
        info.setDiskUsage(entity.getDiskUsage() != null ? entity.getDiskUsage() : BigDecimal.ZERO);
        info.setOsType(entity.getOsType());
        info.setOsArch(entity.getOsArch());
        info.setOsInfo(entity.getOsInfo());
        info.setRackInfo(entity.getRackInfo());
        info.setAgentVersion(entity.getAgentVersion());
        info.setDiskInfo(entity.getDiskInfo());
        info.setNetworkInfo(entity.getNetworkInfo());
        info.setLastHeartbeatTime(entity.getLastHeartbeatTime());
        info.setLastRegistrationTime(entity.getLastRegistrationTime());

        // 获取标签
        List<HostTagEntity> tags = getHostTags(entity.getHostId());
        if (tags != null && !tags.isEmpty()) {
            info.setTags(tags.stream().map(HostTagEntity::getTagName).collect(Collectors.toList()));
        }

        info.setComponents(Arrays.asList("DataNode", "NodeManager"));
        info.setUptime("0d 0h");
        return info;
    }

    private Long parseMemoryToBytes(String memory) {
        if (memory == null) return 0L;
        memory = memory.trim().toUpperCase();
        try {
            if (memory.endsWith("GB")) {
                return Long.parseLong(memory.substring(0, memory.length() - 2).trim()) * 1024 * 1024 * 1024;
            } else if (memory.endsWith("MB")) {
                return Long.parseLong(memory.substring(0, memory.length() - 2).trim()) * 1024 * 1024;
            } else if (memory.endsWith("TB")) {
                return Long.parseLong(memory.substring(0, memory.length() - 2).trim()) * 1024 * 1024 * 1024 * 1024;
            }
            return Long.parseLong(memory) * 1024 * 1024 * 1024; // 默认GB
        } catch (Exception e) {
            return 0L;
        }
    }

    private String formatMemory(Long bytes) {
        if (bytes == null || bytes == 0) return "0GB";
        long gb = bytes / (1024 * 1024 * 1024);
        if (gb > 0) {
            return gb + "GB";
        }
        long mb = bytes / (1024 * 1024);
        return mb + "MB";
    }
}
