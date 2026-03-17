package com.cloudrealm.platform.repository.state;

import com.cloudrealm.platform.entity.state.ServiceDesiredStateEntity;
import com.cloudrealm.platform.entity.state.ClusterServiceId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ServiceDesiredStateRepository extends JpaRepository<ServiceDesiredStateEntity, ClusterServiceId> {
    List<ServiceDesiredStateEntity> findByClusterId(Long clusterId);
}
