package com.cloudrealm.platform.repository;

import com.cloudrealm.platform.entity.Policy;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PolicyRepository extends JpaRepository<Policy, Long> {
}