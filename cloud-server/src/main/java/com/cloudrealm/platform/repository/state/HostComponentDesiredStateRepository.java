package com.cloudrealm.platform.repository.state;

import com.cloudrealm.platform.entity.state.HostComponentDesiredStateEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HostComponentDesiredStateRepository extends JpaRepository<HostComponentDesiredStateEntity, Long> {
    List<HostComponentDesiredStateEntity> findByClusterId(Long clusterId);
    List<HostComponentDesiredStateEntity> findByHostId(Long hostId);
    List<HostComponentDesiredStateEntity> findByClusterIdAndServiceName(Long clusterId, String serviceName);
}
