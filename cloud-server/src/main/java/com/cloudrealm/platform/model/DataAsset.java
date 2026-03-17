package com.cloudrealm.platform.model;

public class DataAsset {
    private String name;
    private String type; // HIVE, HBASE, KAFKA
    private String owner;
    private Double qualityScore;
    private String description;
    private String lineageUpstream;
    private String lineageDownstream;

    public DataAsset() {}

    public DataAsset(String name, String type, String owner, Double qualityScore, String description, String lineageUpstream, String lineageDownstream) {
        this.name = name;
        this.type = type;
        this.owner = owner;
        this.qualityScore = qualityScore;
        this.description = description;
        this.lineageUpstream = lineageUpstream;
        this.lineageDownstream = lineageDownstream;
    }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public String getOwner() { return owner; }
    public void setOwner(String owner) { this.owner = owner; }

    public Double getQualityScore() { return qualityScore; }
    public void setQualityScore(Double qualityScore) { this.qualityScore = qualityScore; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getLineageUpstream() { return lineageUpstream; }
    public void setLineageUpstream(String lineageUpstream) { this.lineageUpstream = lineageUpstream; }

    public String getLineageDownstream() { return lineageDownstream; }
    public void setLineageDownstream(String lineageDownstream) { this.lineageDownstream = lineageDownstream; }
}
