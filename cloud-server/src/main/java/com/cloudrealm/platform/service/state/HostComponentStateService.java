package com.cloudrealm.platform.service.state;

import com.cloudrealm.platform.entity.state.HostComponentStateEntity;
import com.cloudrealm.platform.repository.state.HostComponentStateRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
public class HostComponentStateService {

    @Autowired
    private HostComponentStateRepository repository;

    @Transactional
    public void updateState(Long clusterId, Long hostId, String componentName, String currentState) {
        Optional<HostComponentStateEntity> existing = repository.findByClusterIdAndHostIdAndComponentName(clusterId, hostId, componentName);
        HostComponentStateEntity entity;
        if (existing.isPresent()) {
            entity = existing.get();
            entity.setCurrentState(currentState);
        } else {
            entity = new HostComponentStateEntity();
            entity.setClusterId(clusterId);
            entity.setHostId(hostId);
            entity.setComponentName(componentName);
            entity.setCurrentState(currentState);
            // Default service name needs to be resolved or passed
            entity.setServiceName("UNKNOWN"); 
        }
        repository.save(entity);
    }
}
