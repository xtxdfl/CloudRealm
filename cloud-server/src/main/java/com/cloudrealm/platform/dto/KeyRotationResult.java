package com.cloudrealm.platform.dto;

import lombok.Data;

@Data
public class KeyRotationResult {
    private boolean success;
    private String message;

    public KeyRotationResult(boolean success, String message) {
        this.success = success;
        this.message = message;
    }

    // 保留无参构造器供框架使用
    public KeyRotationResult() {}
}