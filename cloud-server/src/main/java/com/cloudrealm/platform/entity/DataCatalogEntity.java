package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.util.List;

@Data
@Entity
@Table(name = "data_catalogs")
public class DataCatalogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "catalog_id")
    private Long catalogId;

    @Column(name = "catalog_name", nullable = false, unique = true)
    private String catalogName;

    @Column(name = "parent_id")
    private Long parentId;

    @Column(name = "catalog_type")
    private String catalogType;

    @Column(name = "description")
    private String description;

    @Column(name = "owner")
    private String owner;

    @Column(name = "is_public")
    private Boolean isPublic = true;

    @Column(name = "sort_order")
    private Integer sortOrder = 0;

    @Column(name = "created_time")
    private Long createdTime = System.currentTimeMillis();

    @Column(name = "updated_time")
    private Long updatedTime = System.currentTimeMillis();

    @OneToMany(mappedBy = "catalog", cascade = CascadeType.ALL)
    private List<DataAssetCatalogEntity> assetMappings;
}
