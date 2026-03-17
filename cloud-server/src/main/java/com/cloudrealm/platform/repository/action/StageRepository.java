package com.cloudrealm.platform.repository.action;

import com.cloudrealm.platform.entity.action.StageEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface StageRepository extends JpaRepository<StageEntity, Long> {
    List<StageEntity> findByRequestId(Long requestId);
}
