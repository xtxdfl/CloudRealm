package com.cloudrealm.platform.service;

import com.cloudrealm.platform.dto.PolicyDTO;
import com.cloudrealm.platform.dto.request.PolicyCreateRequest;
import com.cloudrealm.platform.entity.Policy;
import com.cloudrealm.platform.exception.NotFoundException;
import com.cloudrealm.platform.repository.PolicyRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class PolicyServiceImpl implements PolicyService {
    private final PolicyRepository policyRepository;
    private final AuditLogService auditLogService;

    @Override
    public PolicyDTO createPolicy(PolicyCreateRequest request) {
        Policy policy = new Policy();
        // TODO: 实现创建逻辑
        return new PolicyDTO();
    }

    @Override
    public boolean isPolicyActive(Long id) {
        return policyRepository.findById(id)
                .map(Policy::isActive)
                .orElseThrow(() -> new NotFoundException("Policy not found"));
    }
}