package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.HostTagEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface HostTagRepository extends JpaRepository<HostTagEntity, Long> {

    Optional<HostTagEntity> findByTagName(String tagName);

    List<HostTagEntity> findByCategoryCategoryId(Long categoryId);

    @Query("SELECT t FROM HostTagEntity t WHERE t.category.categoryType = :categoryType")
    List<HostTagEntity> findByCategoryType(@Param("categoryType") String categoryType);

    @Query("SELECT t FROM HostTagEntity t JOIN HostTagMappingEntity m ON t.tagId = m.tagId WHERE m.hostId = :hostId")
    List<HostTagEntity> findTagsByHostId(@Param("hostId") Long hostId);

    boolean existsByTagNameAndCategoryCategoryId(String tagName, Long categoryId);
}
