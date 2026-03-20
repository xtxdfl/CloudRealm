package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.HostEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface HostRepository extends JpaRepository<HostEntity, Long> {

    Optional<HostEntity> findByHostName(String hostName);

    Optional<HostEntity> findByIpv4(String ipv4);

    List<HostEntity> findByDiscoveryStatus(String discoveryStatus);

    List<HostEntity> findByAgentStatus(String agentStatus);

    List<HostEntity> findByRackInfo(String rackInfo);

    @Query("SELECT h FROM HostEntity h WHERE h.lastHeartbeatTime < :threshold AND h.agentStatus = 'ONLINE'")
    List<HostEntity> findHostsWithStaleHeartbeat(@Param("threshold") Long threshold);

    @Query("SELECT h FROM HostEntity h WHERE " +
           "(:hostName IS NULL OR h.hostName LIKE %:hostName%) AND " +
           "(:ipv4 IS NULL OR h.ipv4 LIKE %:ipv4%) AND " +
           "(:status IS NULL OR h.discoveryStatus = :status) AND " +
           "(:agentStatus IS NULL OR h.agentStatus = :agentStatus) AND " +
           "(:rackInfo IS NULL OR h.rackInfo = :rackInfo)")
    List<HostEntity> searchHosts(
            @Param("hostName") String hostName,
            @Param("ipv4") String ipv4,
            @Param("status") String status,
            @Param("agentStatus") String agentStatus,
            @Param("rackInfo") String rackInfo);

    boolean existsByHostName(String hostName);

    boolean existsByIpv4(String ipv4);
}
