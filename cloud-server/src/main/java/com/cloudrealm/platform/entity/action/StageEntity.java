package com.cloudrealm.platform.entity.action;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "stages")
public class StageEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "stage_id")
    private Long stageId;

    @Column(name = "request_id", nullable = false)
    private Long requestId;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "log_info")
    private String logInfo;

    @Column(name = "request_context")
    private String requestContext;
}
