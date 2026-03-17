package com.cloudrealm.platform.service;

import com.cloudrealm.platform.model.ServiceInfo;
import com.cloudrealm.platform.model.ServiceStats;
import com.cloudrealm.platform.model.Status;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

@Service
public class ServiceService {

    private final List<ServiceInfo> services = new ArrayList<>();

    public ServiceService() {
        // Initialize Mock Data
        services.add(new ServiceInfo("HDFS", "3.3.6", Status.HEALTHY, "v24", "Storage", Arrays.asList("NameNode", "DataNode")));
        services.add(new ServiceInfo("YARN", "3.3.6", Status.HEALTHY, "v12", "Compute", Arrays.asList("ResourceManager", "NodeManager")));
        services.add(new ServiceInfo("HIVE", "3.1.3", Status.WARNING, "v8", "Database", Arrays.asList("HiveServer2", "Metastore")));
        services.add(new ServiceInfo("SPARK", "3.5.0", Status.HEALTHY, "v3", "Compute", Arrays.asList("HistoryServer")));
        services.add(new ServiceInfo("KAFKA", "3.6.0", Status.HEALTHY, "v15", "Messaging", Arrays.asList("Broker")));
        services.add(new ServiceInfo("HBASE", "2.5.5", Status.HEALTHY, "v10", "Database", Arrays.asList("HMaster", "RegionServer")));
        services.add(new ServiceInfo("ZOOKEEPER", "3.8.3", Status.HEALTHY, "v5", "Coordination", Arrays.asList("Server")));
        services.add(new ServiceInfo("FLINK", "1.17.1", Status.STOPPED, "v1", "Stream", Arrays.asList("JobManager")));
    }

    public List<ServiceInfo> getAllServices() {
        return services;
    }

    public Optional<ServiceInfo> getServiceByName(String name) {
        return services.stream()
                .filter(s -> s.getName().equalsIgnoreCase(name))
                .findFirst();
    }

    public ServiceStats getServiceStats() {
        long total = services.size();
        long healthy = services.stream().filter(s -> s.getStatus() == Status.HEALTHY).count();
        long warning = services.stream().filter(s -> s.getStatus() == Status.WARNING || s.getStatus() == Status.CRITICAL).count();
        long stopped = services.stream().filter(s -> s.getStatus() == Status.STOPPED).count();
        return new ServiceStats(total, healthy, warning, stopped);
    }

    public boolean startService(String name) {
        Optional<ServiceInfo> serviceOpt = getServiceByName(name);
        if (serviceOpt.isPresent()) {
            System.out.println("Executing Ansible playbook to START " + name);
            serviceOpt.get().setStatus(Status.HEALTHY);
            return true;
        }
        return false;
    }

    public boolean stopService(String name) {
        Optional<ServiceInfo> serviceOpt = getServiceByName(name);
        if (serviceOpt.isPresent()) {
            System.out.println("Executing Ansible playbook to STOP " + name);
            serviceOpt.get().setStatus(Status.STOPPED);
            return true;
        }
        return false;
    }

    public boolean restartService(String name) {
        Optional<ServiceInfo> serviceOpt = getServiceByName(name);
        if (serviceOpt.isPresent()) {
            System.out.println("Executing Ansible playbook to RESTART " + name);
            // Simulate restart delay or state change
            serviceOpt.get().setStatus(Status.HEALTHY); 
            return true;
        }
        return false;
    }
}
