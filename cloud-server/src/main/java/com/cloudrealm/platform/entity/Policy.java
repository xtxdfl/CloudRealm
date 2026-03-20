package com.cloudrealm.platform.entity;

import jakarta.persistence.*;
import lombok.Data;

@Data
@Entity
@Table(name = "policies")
public class Policy {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String name;
    private String description;
    private boolean active;
}