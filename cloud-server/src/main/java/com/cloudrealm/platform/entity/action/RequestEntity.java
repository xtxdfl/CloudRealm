package com.cloudrealm.platform.entity.action;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "request")
public class RequestEntity {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "request_id")
    private Long requestId;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "request_schedule_id")
    private Long requestScheduleId;

    @Column(name = "command_name")
    private String commandName;

    @Column(name = "create_time")
    private Long createTime;

    @Column(name = "end_time")
    private Long endTime;

    @Column(name = "exclusive_execution")
    private Integer exclusiveExecution = 0;

    @Column(name = "inputs", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] inputs;

    @Column(name = "request_context")
    private String requestContext;

    @Column(name = "request_type")
    private String requestType;

    @Column(name = "start_time")
    private Long startTime;

    @Column(name = "status")
    private String status = "PENDING"; // PENDING, IN_PROGRESS, COMPLETED, FAILED

    @Column(name = "display_status")
    private String displayStatus = "PENDING";
    
    @Column(name = "cluster_host_info", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] clusterHostInfo;

    @Column(name = "user_name")
    private String userName;
}
