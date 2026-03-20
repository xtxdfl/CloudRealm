package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.HostTagMappingEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HostTagMappingRepository extends JpaRepository<HostTagMappingEntity, HostTagMappingEntity.HostTagMappingId> {

    @Query("SELECT m.tagId FROM HostTagMappingEntity m WHERE m.hostId = :hostId")
    List<Long> findTagIdsByHostId(@Param("hostId") Long hostId);

    @Query("SELECT m.hostId FROM HostTagMappingEntity m WHERE m.tagId = :tagId")
    List<Long> findHostIdsByTagId(@Param("tagId") Long tagId);

    @Modifying
    @Query("DELETE FROM HostTagMappingEntity m WHERE m.hostId = :hostId")
    void deleteByHostId(@Param("hostId") Long hostId);

    @Modifying
    @Query("DELETE FROM HostTagMappingEntity m WHERE m.tagId = :tagId")
    void deleteByTagId(@Param("tagId") Long tagId);

    boolean existsByHostIdAndTagId(Long hostId, Long tagId);
}
