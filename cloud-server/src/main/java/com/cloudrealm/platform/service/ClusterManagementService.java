package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.ClusterEntity;
import com.cloudrealm.platform.entity.state.*;
import com.cloudrealm.platform.repository.ClusterRepository;
import com.cloudrealm.platform.repository.state.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ClusterManagementService {

    @Autowired
    private ClusterRepository clusterRepository;

    @Autowired
    private ClusterServiceRepository clusterServiceRepository;

    @Autowired
    private ServiceDesiredStateRepository serviceDesiredStateRepository;

    @Autowired
    private ServiceComponentDesiredStateRepository serviceComponentDesiredStateRepository;

    @Transactional
    public ClusterEntity createCluster(String clusterName, String stackName, String stackVersion) {
        ClusterEntity cluster = new ClusterEntity();
        cluster.setClusterName(clusterName);
        cluster.setProvisioningState("INIT");
        cluster.setDesiredClusterState("INIT");
        cluster.setResourceId(1L); // Default resource
        cluster.setDesiredStackId(1L); // Should look up stack ID
        cluster.setClusterInfo("Created via Ops API");
        return clusterRepository.save(cluster);
    }

    @Transactional
    public void addService(Long clusterId, String serviceName) {
        ClusterServiceEntity clusterService = new ClusterServiceEntity();
        clusterService.setClusterId(clusterId);
        clusterService.setServiceName(serviceName);
        clusterService.setServiceEnabled(1);
        clusterServiceRepository.save(clusterService);

        ServiceDesiredStateEntity desiredState = new ServiceDesiredStateEntity();
        desiredState.setClusterId(clusterId);
        desiredState.setServiceName(serviceName);
        desiredState.setDesiredState("INSTALLED");
        serviceDesiredStateRepository.save(desiredState);
    }

    @Transactional
    public void addServiceComponent(Long clusterId, String serviceName, String componentName) {
        ServiceComponentDesiredStateEntity componentDesiredState = new ServiceComponentDesiredStateEntity();
        componentDesiredState.setClusterId(clusterId);
        componentDesiredState.setServiceName(serviceName);
        componentDesiredState.setComponentName(componentName);
        componentDesiredState.setDesiredState("INSTALLED");
        // Mock IDs for repo version
        componentDesiredState.setDesiredRepoVersionId(1L); 
        serviceComponentDesiredStateRepository.save(componentDesiredState);
    }

    public List<ClusterEntity> getAllClusters() {
        return clusterRepository.findAll();
    }
}
