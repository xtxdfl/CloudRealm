package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "host_registration_log")
public class HostRegistrationLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "reg_id")
    private Long regId;

    @Column(name = "host_id")
    private Long hostId;

    @Column(name = "host_name", nullable = false)
    private String hostName;

    @Column(name = "ipv4")
    private String ipv4;

    @Column(name = "registration_type", nullable = false)
    private String registrationType;

    @Column(name = "source_ip")
    private String sourceIp;

    @Column(name = "status")
    private String status = "PENDING";

    @Column(name = "error_message", length = 1000)
    private String errorMessage;

    @Column(name = "registered_time")
    private Long registeredTime = System.currentTimeMillis();
}
