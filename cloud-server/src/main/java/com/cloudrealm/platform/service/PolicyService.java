package com.cloudrealm.platform.service;

import com.cloudrealm.platform.dto.PolicyDTO;
import com.cloudrealm.platform.dto.request.PolicyCreateRequest;

public interface PolicyService {
    PolicyDTO createPolicy(PolicyCreateRequest request);
    boolean isPolicyActive(Long id);
}