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
            HostInfo host1 = new HostInfo();
            host1.setHostname("master-01.cloudrealm.local");
            host1.setIp("192.168.1.10");
            host1.setRole("Master");
            host1.setStatus(Status.HEALTHY);
            host1.setCores(8);
            host1.setMemory("32GB");
            host1.setComponents(Arrays.asList("NameNode", "ResourceManager"));
            host1.setUptime("15d 4h");
            hostService.addHost(host1);

            HostInfo host2 = new HostInfo();
            host2.setHostname("worker-01.cloudrealm.local");
            host2.setIp("192.168.1.11");
            host2.setRole("Worker");
            host2.setStatus(Status.HEALTHY);
            host2.setCores(16);
            host2.setMemory("64GB");
            host2.setComponents(Arrays.asList("DataNode", "NodeManager"));
            host2.setUptime("15d 4h");
            hostService.addHost(host2);

            HostInfo host3 = new HostInfo();
            host3.setHostname("worker-02.cloudrealm.local");
            host3.setIp("192.168.1.12");
            host3.setRole("Worker");
            host3.setStatus(Status.HEALTHY);
            host3.setCores(16);
            host3.setMemory("64GB");
            host3.setComponents(Arrays.asList("DataNode", "NodeManager"));
            host3.setUptime("15d 4h");
            hostService.addHost(host3);

            HostInfo host4 = new HostInfo();
            host4.setHostname("worker-03.cloudrealm.local");
            host4.setIp("192.168.1.13");
            host4.setRole("Worker");
            host4.setStatus(Status.STOPPED);
            host4.setCores(16);
            host4.setMemory("64GB");
            host4.setComponents(Arrays.asList("DataNode", "NodeManager"));
            host4.setUptime("0d 0h");
            hostService.addHost(host4);

            System.out.println("Mock host data initialized in database.");
        }
    }
}
