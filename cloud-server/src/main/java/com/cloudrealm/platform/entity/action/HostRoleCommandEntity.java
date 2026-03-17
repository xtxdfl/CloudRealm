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
    private String status; // PENDING, QUEUED, IN_PROGRESS, COMPLETED, FAILED

    @Column(name = "std_error", columnDefinition = "LONGTEXT")
    private String stdError;

    @Column(name = "std_out", columnDefinition = "LONGTEXT")
    private String stdOut;

    @Column(name = "exitcode")
    private Integer exitcode;

    @Column(name = "start_time")
    private Long startTime;

    @Column(name = "end_time")
    private Long endTime;
}
