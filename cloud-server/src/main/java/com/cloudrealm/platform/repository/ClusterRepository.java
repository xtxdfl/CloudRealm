package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.ClusterEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ClusterRepository extends JpaRepository<ClusterEntity, Long> {
}
