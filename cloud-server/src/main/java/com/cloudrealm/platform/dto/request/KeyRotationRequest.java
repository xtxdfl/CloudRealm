package com.cloudrealm.platform.dto.request;

import lombok.Data;

@Data
public class KeyRotationRequest {
    private String keyType;
    private String algorithm;
    private int keySize;
}