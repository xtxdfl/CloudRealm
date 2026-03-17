package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;

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

    @Column(name = "cpu_count", nullable = false)
    private Integer cpuCount;

    @Column(name = "cpu_info", nullable = false)
    private String cpuInfo;

    @Column(name = "discovery_status", nullable = false, length = 2000)
    private String discoveryStatus;

    @Column(name = "host_attributes", nullable = false, columnDefinition = "LONGTEXT")
    private String hostAttributes;

    @Column(name = "ipv4")
    private String ipv4;

    @Column(name = "ipv6")
    private String ipv6;

    @Column(name = "last_registration_time", nullable = false)
    private Long lastRegistrationTime;

    @Column(name = "os_arch", nullable = false)
    private String osArch;

    @Column(name = "os_info", nullable = false, length = 1000)
    private String osInfo;

    @Column(name = "os_type", nullable = false)
    private String osType;

    @Column(name = "ph_cpu_count")
    private Integer phCpuCount;

    @Column(name = "public_host_name")
    private String publicHostName;

    @Column(name = "rack_info", nullable = false)
    private String rackInfo;

    @Column(name = "total_mem", nullable = false)
    private Long totalMem;
}
