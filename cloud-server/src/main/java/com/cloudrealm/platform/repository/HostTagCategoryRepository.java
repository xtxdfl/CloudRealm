package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.HostTagCategoryEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface HostTagCategoryRepository extends JpaRepository<HostTagCategoryEntity, Long> {

    Optional<HostTagCategoryEntity> findByCategoryName(String categoryName);

    List<HostTagCategoryEntity> findByCategoryType(String categoryType);

    boolean existsByCategoryNameAndCategoryType(String categoryName, String categoryType);
}
