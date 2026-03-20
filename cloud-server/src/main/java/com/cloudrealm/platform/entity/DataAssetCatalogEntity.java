package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "data_asset_catalog")
@IdClass(DataAssetCatalogEntity.DataAssetCatalogId.class)
public class DataAssetCatalogEntity {

    @Id
    @Column(name = "asset_id", nullable = false)
    private Long assetId;

    @Id
    @Column(name = "catalog_id", nullable = false)
    private Long catalogId;

    @Column(name = "assigned_time")
    private Long assignedTime = System.currentTimeMillis();

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "asset_id", insertable = false, updatable = false)
    private DataAssetEntity asset;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "catalog_id", insertable = false, updatable = false)
    private DataCatalogEntity catalog;

    @Data
    public static class DataAssetCatalogId implements java.io.Serializable {
        private Long assetId;
        private Long catalogId;
    }
}
