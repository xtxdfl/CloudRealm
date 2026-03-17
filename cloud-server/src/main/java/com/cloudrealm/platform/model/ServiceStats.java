package com.cloudrealm.platform.model;

public class ServiceStats {
    private long total;
    private long healthy;
    private long warning;
    private long stopped;

    public ServiceStats() {}

    public ServiceStats(long total, long healthy, long warning, long stopped) {
        this.total = total;
        this.healthy = healthy;
        this.warning = warning;
        this.stopped = stopped;
    }

    public long getTotal() { return total; }
    public void setTotal(long total) { this.total = total; }

    public long getHealthy() { return healthy; }
    public void setHealthy(long healthy) { this.healthy = healthy; }

    public long getWarning() { return warning; }
    public void setWarning(long warning) { this.warning = warning; }

    public long getStopped() { return stopped; }
    public void setStopped(long stopped) { this.stopped = stopped; }
}
