package com.cloudrealm.platform.repository.action;

import com.cloudrealm.platform.entity.action.HostRoleCommandEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HostRoleCommandRepository extends JpaRepository<HostRoleCommandEntity, Long> {
    List<HostRoleCommandEntity> findByHostNameAndStatus(String hostName, String status);
    List<HostRoleCommandEntity> findByRequestId(Long requestId);
}
