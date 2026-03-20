package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.math.BigDecimal;

@Data
@Entity
@Table(name = "data_quality_results")
public class DataQualityResultEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "result_id")
    private Long resultId;

    @Column(name = "rule_id", nullable = false)
    private Long ruleId;

    @Column(name = "asset_id", nullable = false)
    private Long assetId;

    @Column(name = "check_time", nullable = false)
    private Long checkTime;

    @Column(name = "check_status", nullable = false)
    private String checkStatus;

    @Column(name = "total_records")
    private Long totalRecords = 0L;

    @Column(name = "valid_records")
    private Long validRecords = 0L;

    @Column(name = "invalid_records")
    private Long invalidRecords = 0L;

    @Column(name = "valid_percentage")
    private BigDecimal validPercentage = BigDecimal.ZERO;

    @Column(name = "error_details", columnDefinition = "TEXT")
    private String errorDetails;

    @Column(name = "duration_ms")
    private Integer durationMs = 0;

    @Column(name = "executed_by")
    private String executedBy;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "rule_id", insertable = false, updatable = false)
    private DataQualityRuleEntity rule;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "asset_id", insertable = false, updatable = false)
    private DataAssetEntity asset;
}
