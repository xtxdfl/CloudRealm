package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.math.BigDecimal;

@Data
@Entity
@Table(name = "data_quality_rules")
public class DataQualityRuleEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "rule_id")
    private Long ruleId;

    @Column(name = "rule_name", nullable = false)
    private String ruleName;

    @Column(name = "rule_type", nullable = false)
    private String ruleType;

    @Column(name = "target_asset_id", nullable = false)
    private Long targetAssetId;

    @Column(name = "target_column")
    private String targetColumn;

    @Column(name = "rule_definition", columnDefinition = "TEXT", nullable = false)
    private String ruleDefinition;

    @Column(name = "rule_params")
    private String ruleParams;

    @Column(name = "severity")
    private String severity = "WARNING";

    @Column(name = "is_enabled")
    private Boolean isEnabled = true;

    @Column(name = "schedule_cron")
    private String scheduleCron;

    @Column(name = "last_run_time")
    private Long lastRunTime;

    @Column(name = "last_run_status")
    private String lastRunStatus;

    @Column(name = "created_time")
    private Long createdTime = System.currentTimeMillis();

    @Column(name = "updated_time")
    private Long updatedTime = System.currentTimeMillis();

    @Column(name = "created_by")
    private String createdBy;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "target_asset_id", insertable = false, updatable = false)
    private DataAssetEntity targetAsset;
}
