package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.util.List;

@Data
@Entity
@Table(name = "host_tag_categories")
public class HostTagCategoryEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "category_id")
    private Long categoryId;

    @Column(name = "category_name", nullable = false)
    private String categoryName;

    @Column(name = "category_type", nullable = false)
    private String categoryType;

    @Column(name = "description")
    private String description;

    @Column(name = "color")
    private String color = "#6366f1";

    @Column(name = "sort_order")
    private Integer sortOrder = 0;

    @Column(name = "created_time")
    private Long createdTime = System.currentTimeMillis();

    @Column(name = "updated_time")
    private Long updatedTime = System.currentTimeMillis();

    // 标签列表
    @OneToMany(mappedBy = "category", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<HostTagEntity> tags;
}
