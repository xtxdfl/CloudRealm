package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.HostEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface HostRepository extends JpaRepository<HostEntity, Long> {
}
