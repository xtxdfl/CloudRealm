package com.cloudrealm.platform.model;

public class DataMartStats {
    private Integer managedTables;
    private Double qualityScoreAvg;
    private Double storageUsagePb;
    private Integer storageCapacityPercent;

    public DataMartStats() {}

    public DataMartStats(Integer managedTables, Double qualityScoreAvg, Double storageUsagePb, Integer storageCapacityPercent) {
        this.managedTables = managedTables;
        this.qualityScoreAvg = qualityScoreAvg;
        this.storageUsagePb = storageUsagePb;
        this.storageCapacityPercent = storageCapacityPercent;
    }

    public Integer getManagedTables() { return managedTables; }
    public void setManagedTables(Integer managedTables) { this.managedTables = managedTables; }

    public Double getQualityScoreAvg() { return qualityScoreAvg; }
    public void setQualityScoreAvg(Double qualityScoreAvg) { this.qualityScoreAvg = qualityScoreAvg; }

    public Double getStorageUsagePb() { return storageUsagePb; }
    public void setStorageUsagePb(Double storageUsagePb) { this.storageUsagePb = storageUsagePb; }

    public Integer getStorageCapacityPercent() { return storageCapacityPercent; }
    public void setStorageCapacityPercent(Integer storageCapacityPercent) { this.storageCapacityPercent = storageCapacityPercent; }
}
