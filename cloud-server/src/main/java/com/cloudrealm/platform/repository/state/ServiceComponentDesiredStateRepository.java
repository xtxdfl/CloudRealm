package com.cloudrealm.platform.repository.state;

import com.cloudrealm.platform.entity.state.ServiceComponentDesiredStateEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ServiceComponentDesiredStateRepository extends JpaRepository<ServiceComponentDesiredStateEntity, Long> {
    List<ServiceComponentDesiredStateEntity> findByClusterId(Long clusterId);
    List<ServiceComponentDesiredStateEntity> findByClusterIdAndServiceName(Long clusterId, String serviceName);
}
