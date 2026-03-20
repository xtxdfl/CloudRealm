package com.cloudrealm.platform.service.impl;

import com.cloudrealm.platform.service.AuditLogService;
import org.springframework.stereotype.Service;

@Service
public class AuditLogServiceImpl implements AuditLogService {
    @Override
    public void logAction(String action, String resource, String details) {
        // TODO: 实现审计日志记录逻辑
        System.out.printf("[AUDIT] action=%s, resource=%s, details=%s%n", action, resource, details);
    }
}