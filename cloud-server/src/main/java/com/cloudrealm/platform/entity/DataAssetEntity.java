package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.math.BigDecimal;
import java.util.List;

@Data
@Entity
@Table(name = "data_assets")
public class DataAssetEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "asset_id")
    private Long assetId;

    @Column(name = "asset_name", nullable = false)
    private String assetName;

    @Column(name = "asset_type", nullable = false)
    private String assetType;

    @Column(name = "database_name")
    private String databaseName;

    @Column(name = "schema_name")
    private String schemaName;

    @Column(name = "table_name")
    private String tableName;

    @Column(name = "column_name")
    private String columnName;

    @Column(name = "data_format")
    private String dataFormat;

    @Column(name = "storage_path")
    private String storagePath;

    @Column(name = "owner")
    private String owner;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "tags")
    private String tags;

    @Column(name = "is_partitioned")
    private Boolean isPartitioned = false;

    @Column(name = "partition_columns")
    private String partitionColumns;

    @Column(name = "record_count")
    private Long recordCount = 0L;

    @Column(name = "size_bytes")
    private Long sizeBytes = 0L;

    @Column(name = "location")
    private String location;

    @Column(name = "engine")
    private String engine;

    @Column(name = "created_time")
    private Long createdTime = System.currentTimeMillis();

    @Column(name = "updated_time")
    private Long updatedTime = System.currentTimeMillis();

    @Column(name = "last_access_time")
    private Long lastAccessTime;

    @Column(name = "quality_score")
    private BigDecimal qualityScore = BigDecimal.ZERO;

    // 关联
    @OneToMany(mappedBy = "sourceAsset", cascade = CascadeType.ALL)
    private List<DataLineageEntity> upstreamLineages;

    @OneToMany(mappedBy = "targetAsset", cascade = CascadeType.ALL)
    private List<DataLineageEntity> downstreamLineages;
}
