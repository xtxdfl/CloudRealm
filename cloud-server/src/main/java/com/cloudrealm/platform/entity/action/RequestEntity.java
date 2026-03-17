package com.cloudrealm.platform.entity.action;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "requests")
public class RequestEntity {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "request_id")
    private Long requestId;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "request_context")
    private String requestContext;

    @Column(name = "start_time")
    private Long startTime;

    @Column(name = "end_time")
    private Long endTime;

    @Column(name = "status")
    private String status; // PENDING, IN_PROGRESS, COMPLETED, FAILED
    
    @Column(name = "inputs", columnDefinition = "LONGTEXT")
    private String inputs;
}
