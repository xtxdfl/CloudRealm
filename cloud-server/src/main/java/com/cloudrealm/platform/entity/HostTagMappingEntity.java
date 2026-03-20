package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.io.Serializable;

@Data
@Entity
@Table(name = "host_tag_mapping")
@IdClass(HostTagMappingEntity.HostTagMappingId.class)
public class HostTagMappingEntity {

    @Id
    @Column(name = "host_id", nullable = false)
    private Long hostId;

    @Id
    @Column(name = "tag_id", nullable = false)
    private Long tagId;

    @Column(name = "assigned_time")
    private Long assignedTime = System.currentTimeMillis();

    @Column(name = "assigned_by")
    private String assignedBy;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "host_id", insertable = false, updatable = false)
    private HostEntity host;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "tag_id", insertable = false, updatable = false)
    private HostTagEntity tag;

    // 复合主键类
    @Data
    public static class HostTagMappingId implements Serializable {
        private Long hostId;
        private Long tagId;
    }
}
