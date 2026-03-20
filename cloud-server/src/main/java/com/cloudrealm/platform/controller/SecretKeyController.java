package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.annotation.Auditable;
import com.cloudrealm.platform.dto.KeyRotationResult;
import com.cloudrealm.platform.dto.request.KeyRotationRequest;
import com.cloudrealm.platform.service.KeyService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/security/keys")
@RequiredArgsConstructor
public class SecretKeyController {
    private final KeyService keyService;

    @PostMapping("/rotate")
    @Auditable(action = "ROTATE_KEY")
    public KeyRotationResult rotateKey(@RequestBody KeyRotationRequest request) {
        return keyService.rotateKey(request);
    }
}