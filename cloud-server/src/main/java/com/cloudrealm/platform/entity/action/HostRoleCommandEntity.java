package com.cloudrealm.platform.entity.action;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "host_role_command")
public class HostRoleCommandEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "task_id")
    private Long taskId;

    @Column(name = "request_id", nullable = false)
    private Long requestId;

    @Column(name = "stage_id", nullable = false)
    private Long stageId;

    @Column(name = "host_id")
    private Long hostId;

    @Column(name = "host_name")
    private String hostName;

    @Column(name = "role")
    private String role; // Component name e.g., DATANODE

    @Column(name = "role_command")
    private String roleCommand; // INSTALL, START, STOP

    @Column(name = "status")
    private String status = "PENDING"; // PENDING, QUEUED, IN_PROGRESS, COMPLETED, FAILED

    @Column(name = "std_error", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] stdError;

    @Column(name = "std_out", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] stdOut;

    @Column(name = "output_log")
    private String outputLog;

    @Column(name = "error_log")
    private String errorLog;

    @Column(name = "structured_out", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] structuredOut;

    @Column(name = "exitcode")
    private Integer exitcode;

    @Column(name = "start_time")
    private Long startTime;

    @Column(name = "original_start_time")
    private Long originalStartTime;

    @Column(name = "end_time")
    private Long endTime;

    @Column(name = "attempt_count")
    private Integer attemptCount = 0;

    @Column(name = "retry_allowed")
    private Integer retryAllowed = 0;

    @Column(name = "event", columnDefinition = "LONGTEXT")
    private String event = "";

    @Column(name = "last_attempt_time")
    private Long lastAttemptTime = 0L;
    
    @Column(name = "command_detail")
    private String commandDetail;

    @Column(name = "ops_display_name")
    private String opsDisplayName;

    @Column(name = "custom_command_name")
    private String customCommandName;

    @Column(name = "is_background")
    private Integer isBackground = 0;

    @Column(name = "auto_skip_on_failure")
    private Integer autoSkipOnFailure = 0;
}
