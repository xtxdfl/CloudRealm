package com.cloudrealm.platform.repository.state;

import com.cloudrealm.platform.entity.state.ClusterServiceEntity;
import com.cloudrealm.platform.entity.state.ClusterServiceId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ClusterServiceRepository extends JpaRepository<ClusterServiceEntity, ClusterServiceId> {
    List<ClusterServiceEntity> findByClusterId(Long clusterId);
}
