package com.cloudrealm.platform.service;

import com.cloudrealm.platform.dto.KeyRotationResult;
import com.cloudrealm.platform.dto.request.KeyRotationRequest;

public interface KeyService {
    KeyRotationResult rotateKey(KeyRotationRequest request);
}