package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "data_lineage")
public class DataLineageEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "lineage_id")
    private Long lineageId;

    @Column(name = "source_asset_id", nullable = false)
    private Long sourceAssetId;

    @Column(name = "target_asset_id", nullable = false)
    private Long targetAssetId;

    @Column(name = "lineage_type", nullable = false)
    private String lineageType;

    @Column(name = "transform_expression", columnDefinition = "TEXT")
    private String transformExpression;

    @Column(name = "transform_type")
    private String transformType;

    @Column(name = "is_active")
    private Boolean isActive = true;

    @Column(name = "created_time")
    private Long createdTime = System.currentTimeMillis();

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "source_asset_id", insertable = false, updatable = false)
    private DataAssetEntity sourceAsset;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "target_asset_id", insertable = false, updatable = false)
    private DataAssetEntity targetAsset;
}
