package com.cloudrealm.platform.service;

import com.cloudrealm.platform.model.HostInfo;
import com.cloudrealm.platform.model.Status;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class HostService {

    private final List<HostInfo> hosts = new ArrayList<>();

    public HostService() {
        // Initialize Mock Data
        hosts.add(new HostInfo("master-01.cloudrealm.local", "192.168.1.10", "Master", Status.HEALTHY, 8, "32GB", Arrays.asList("NameNode", "ResourceManager"), "15d 4h"));
        hosts.add(new HostInfo("worker-01.cloudrealm.local", "192.168.1.11", "Worker", Status.HEALTHY, 16, "64GB", Arrays.asList("DataNode", "NodeManager"), "15d 4h"));
        hosts.add(new HostInfo("worker-02.cloudrealm.local", "192.168.1.12", "Worker", Status.HEALTHY, 16, "64GB", Arrays.asList("DataNode", "NodeManager"), "15d 4h"));
        hosts.add(new HostInfo("worker-03.cloudrealm.local", "192.168.1.13", "Worker", Status.STOPPED, 16, "64GB", Arrays.asList("DataNode", "NodeManager"), "0d 0h"));
    }

    public List<HostInfo> getAllHosts() {
        return hosts;
    }

    public void addHost(HostInfo host) {
        if (host.getStatus() == null) host.setStatus(Status.UNKNOWN);
        hosts.add(host);
        System.out.println("Host added: " + host.getHostname());
    }

    public void batchStart(List<String> hostnames) {
        System.out.println("Batch starting hosts: " + hostnames);
        hosts.stream()
            .filter(h -> hostnames.contains(h.getHostname()))
            .forEach(h -> h.setStatus(Status.HEALTHY));
    }

    public void batchStop(List<String> hostnames) {
        System.out.println("Batch stopping hosts: " + hostnames);
        hosts.stream()
            .filter(h -> hostnames.contains(h.getHostname()))
            .forEach(h -> h.setStatus(Status.STOPPED));
    }

    public void batchRestart(List<String> hostnames) {
        System.out.println("Batch restarting hosts: " + hostnames);
        hosts.stream()
            .filter(h -> hostnames.contains(h.getHostname()))
            .forEach(h -> {
                h.setStatus(Status.WARNING); // Transition state
                // Simulate restart complete after some time (in a real app)
            });
    }

    public Optional<HostInfo> getHostByHostname(String hostname) {
        return hosts.stream()
                .filter(h -> h.getHostname().equalsIgnoreCase(hostname))
                .findFirst();
    }
}
