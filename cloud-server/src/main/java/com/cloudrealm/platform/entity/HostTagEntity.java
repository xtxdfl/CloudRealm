package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.util.ArrayList;
import java.util.List;

@Data
@Entity
@Table(name = "host_tags")
public class HostTagEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "tag_id")
    private Long tagId;

    @Column(name = "tag_name", nullable = false)
    private String tagName;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "category_id", nullable = false)
    private HostTagCategoryEntity category;

    @Column(name = "description")
    private String description;

    @Column(name = "color")
    private String color = "#6366f1";

    @Column(name = "created_time")
    private Long createdTime = System.currentTimeMillis();

    @Column(name = "updated_time")
    private Long updatedTime = System.currentTimeMillis();

    // 主机列表
    @ManyToMany(mappedBy = "tags", fetch = FetchType.LAZY)
    private List<HostEntity> hosts = new ArrayList<>();
}
