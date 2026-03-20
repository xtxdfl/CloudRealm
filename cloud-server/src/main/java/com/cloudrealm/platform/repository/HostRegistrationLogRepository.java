package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.HostRegistrationLogEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HostRegistrationLogRepository extends JpaRepository<HostRegistrationLogEntity, Long> {

    List<HostRegistrationLogEntity> findByHostName(String hostName);

    List<HostRegistrationLogEntity> findByRegistrationType(String registrationType);

    List<HostRegistrationLogEntity> findByStatus(String status);

    @Query("SELECT r FROM HostRegistrationLogEntity r WHERE r.registeredTime >= :startTime AND r.registeredTime <= :endTime")
    List<HostRegistrationLogEntity> findByTimeRange(@Param("startTime") Long startTime, @Param("endTime") Long endTime);
}
