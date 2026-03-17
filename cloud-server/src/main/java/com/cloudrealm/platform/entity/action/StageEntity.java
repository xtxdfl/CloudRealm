package com.cloudrealm.platform.entity.action;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "stage")
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

    @Column(name = "skippable")
    private Integer skippable = 0;

    @Column(name = "supports_auto_skip_failure")
    private Integer supportsAutoSkipFailure = 0;

    @Column(name = "command_params", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] commandParams;

    @Column(name = "host_params", columnDefinition = "LONGBLOB")
    @Lob
    private byte[] hostParams;

    @Column(name = "command_execution_type")
    private String commandExecutionType = "STAGE";

    @Column(name = "status")
    private String status = "PENDING";

    @Column(name = "display_status")
    private String displayStatus = "PENDING";
}
