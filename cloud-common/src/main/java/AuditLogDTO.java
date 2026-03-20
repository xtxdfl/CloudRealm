package com.cloudrealm.platform.dto;

import lombok.Data;
import java.time.Instant;

@Data
public class AuditLogDTO {
    private String traceId;
    private String action;
    private String resource;
    private Instant timestamp;
}
