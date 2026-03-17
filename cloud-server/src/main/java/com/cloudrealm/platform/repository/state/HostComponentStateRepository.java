package com.cloudrealm.platform.repository.state;

import com.cloudrealm.platform.entity.state.HostComponentStateEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface HostComponentStateRepository extends JpaRepository<HostComponentStateEntity, Long> {
    List<HostComponentStateEntity> findByClusterId(Long clusterId);
    List<HostComponentStateEntity> findByHostId(Long hostId);
    List<HostComponentStateEntity> findByClusterIdAndServiceName(Long clusterId, String serviceName);
    Optional<HostComponentStateEntity> findByClusterIdAndHostIdAndComponentName(Long clusterId, Long hostId, String componentName);
}
