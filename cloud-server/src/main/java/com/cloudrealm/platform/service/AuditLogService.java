package com.cloudrealm.platform.service;

public interface AuditLogService {
    void logAction(String action, String resource, String details);
}