package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Data
@Entity
@Table(name = "hosts")
public class HostEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "host_id")
    private Long hostId;

    @Column(name = "host_name", nullable = false, unique = true)
    private String hostName;

    @Column(name = "ipv4", unique = true)
    private String ipv4;

    @Column(name = "ipv6")
    private String ipv6;

    @Column(name = "public_host_name")
    private String publicHostName;

    @Column(name = "cpu_count", nullable = false)
    private Integer cpuCount = 0;

    @Column(name = "cpu_info", nullable = false)
    private String cpuInfo = "";

    @Column(name = "cpu_usage")
    private BigDecimal cpuUsage = BigDecimal.ZERO;

    @Column(name = "total_mem", nullable = false)
    private Long totalMem = 0L;

    @Column(name = "used_mem")
    private Long usedMem = 0L;

    @Column(name = "memory_usage")
    private BigDecimal memoryUsage = BigDecimal.ZERO;

    @Column(name = "total_disk")
    private Long totalDisk = 0L;

    @Column(name = "used_disk")
    private Long usedDisk = 0L;

    @Column(name = "disk_usage")
    private BigDecimal diskUsage = BigDecimal.ZERO;

    @Column(name = "os_type", nullable = false)
    private String osType = "Linux";

    @Column(name = "os_arch", nullable = false)
    private String osArch = "x86_64";

    @Column(name = "os_info", length = 1000)
    private String osInfo = "";

    @Column(name = "discovery_status", length = 2000)
    private String discoveryStatus = "UNKNOWN";

    @Column(name = "host_attributes", columnDefinition = "LONGTEXT")
    private String hostAttributes = "{}";

    @Column(name = "rack_info")
    private String rackInfo = "/default-rack";

    @Column(name = "last_registration_time")
    private Long lastRegistrationTime = 0L;

    @Column(name = "last_heartbeat_time")
    private Long lastHeartbeatTime = 0L;

    @Column(name = "heartbeat_interval")
    private Integer heartbeatInterval = 30;

    @Column(name = "agent_version")
    private String agentVersion;

    @Column(name = "agent_status")
    private String agentStatus = "OFFLINE";

    @Column(name = "disk_info", columnDefinition = "TEXT")
    private String diskInfo = "[]";

    @Column(name = "network_info", columnDefinition = "TEXT")
    private String networkInfo = "[]";

    // 标签关联
    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
        name = "host_tag_mapping",
        joinColumns = @JoinColumn(name = "host_id"),
        inverseJoinColumns = @JoinColumn(name = "tag_id")
    )
    private List<HostTagEntity> tags;
}
