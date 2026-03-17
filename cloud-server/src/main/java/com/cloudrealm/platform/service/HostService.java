package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.model.HostInfo;
import com.cloudrealm.platform.model.Status;
import com.cloudrealm.platform.repository.HostRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class HostService {

    @Autowired
    private HostRepository hostRepository;

    public HostService() {
    }

    public List<HostInfo> getAllHosts() {
        List<HostEntity> entities = hostRepository.findAll();
        return entities.stream().map(this::convertToHostInfo).collect(Collectors.toList());
    }

    public void addHost(HostInfo host) {
        HostEntity entity = new HostEntity();
        entity.setHostName(host.getHostname());
        entity.setIpv4(host.getIp());
        entity.setCpuCount(host.getCores() != null ? host.getCores() : 0);
        entity.setCpuInfo("Generic CPU");
        entity.setDiscoveryStatus(host.getStatus() != null ? host.getStatus().name() : Status.UNKNOWN.name());
        entity.setHostAttributes("{}");
        entity.setLastRegistrationTime(System.currentTimeMillis());
        entity.setOsArch("x86_64");
        entity.setOsInfo("Linux");
        entity.setOsType("Linux");
        entity.setRackInfo("/default-rack");
        entity.setTotalMem(parseMemoryToBytes(host.getMemory()));
        
        hostRepository.save(entity);
        System.out.println("Host added: " + host.getHostname());
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

    public Optional<HostInfo> getHostByHostname(String hostname) {
        return hostRepository.findAll().stream()
                .filter(h -> h.getHostName().equalsIgnoreCase(hostname))
                .map(this::convertToHostInfo)
                .findFirst();
    }
    
    private HostInfo convertToHostInfo(HostEntity entity) {
        HostInfo info = new HostInfo();
        info.setHostname(entity.getHostName());
        info.setIp(entity.getIpv4());
        info.setRole("Worker"); // Dummy role
        
        try {
            info.setStatus(Status.valueOf(entity.getDiscoveryStatus()));
        } catch (Exception e) {
            info.setStatus(Status.UNKNOWN);
        }
        
        info.setCores(entity.getCpuCount());
        info.setMemory(entity.getTotalMem() / (1024 * 1024 * 1024) + "GB");
        info.setComponents(Arrays.asList("DataNode", "NodeManager")); // Dummy components
        info.setUptime("0d 0h");
        return info;
    }
    
    private Long parseMemoryToBytes(String memory) {
        if (memory == null) return 0L;
        if (memory.toUpperCase().endsWith("GB")) {
            try {
                return Long.parseLong(memory.substring(0, memory.length() - 2).trim()) * 1024 * 1024 * 1024;
            } catch (Exception e) {}
        }
        return 0L;
    }
}
