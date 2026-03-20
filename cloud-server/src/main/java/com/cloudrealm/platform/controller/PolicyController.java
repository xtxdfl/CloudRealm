package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.annotation.Auditable;
import com.cloudrealm.platform.dto.PolicyDTO;
import com.cloudrealm.platform.dto.request.PolicyCreateRequest;
import com.cloudrealm.platform.service.PolicyService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/v1/security/policies")
@RequiredArgsConstructor
public class PolicyController {
    private final PolicyService policyService;

    @PostMapping
    @Auditable(action = "CREATE_POLICY")
    public PolicyDTO createPolicy(@Valid @RequestBody PolicyCreateRequest request) {
        return policyService.createPolicy(request);
    }

    @GetMapping("/{id}/status")
    public boolean checkPolicyStatus(@PathVariable Long id) {
        return policyService.isPolicyActive(id);
    }
}

