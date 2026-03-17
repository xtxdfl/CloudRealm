package com.cloudrealm.platform.config;

import com.cloudrealm.platform.model.HostInfo;
import com.cloudrealm.platform.model.Status;
import com.cloudrealm.platform.service.HostService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.util.Arrays;

@Component
public class DataInitializer implements CommandLineRunner {

    @Autowired
    private HostService hostService;

    @Override
    public void run(String... args) throws Exception {
        if (hostService.getAllHosts().isEmpty()) {
            hostService.addHost(new HostInfo("master-01.cloudrealm.local", "192.168.1.10", "Master", Status.HEALTHY, 8, "32GB", Arrays.asList("NameNode", "ResourceManager"), "15d 4h"));
            hostService.addHost(new HostInfo("worker-01.cloudrealm.local", "192.168.1.11", "Worker", Status.HEALTHY, 16, "64GB", Arrays.asList("DataNode", "NodeManager"), "15d 4h"));
            hostService.addHost(new HostInfo("worker-02.cloudrealm.local", "192.168.1.12", "Worker", Status.HEALTHY, 16, "64GB", Arrays.asList("DataNode", "NodeManager"), "15d 4h"));
            hostService.addHost(new HostInfo("worker-03.cloudrealm.local", "192.168.1.13", "Worker", Status.STOPPED, 16, "64GB", Arrays.asList("DataNode", "NodeManager"), "0d 0h"));
            System.out.println("Mock host data initialized in database.");
        }
    }
}
