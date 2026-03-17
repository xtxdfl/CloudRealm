package com.cloudrealm.platform.model;

public class Stack {
    private Long stackId;
    private String stackName;
    private String stackVersion;
    private Long mpackId;

    public Stack() {}

    public Stack(Long stackId, String stackName, String stackVersion, Long mpackId) {
        this.stackId = stackId;
        this.stackName = stackName;
        this.stackVersion = stackVersion;
        this.mpackId = mpackId;
    }

    public Long getStackId() { return stackId; }
    public void setStackId(Long stackId) { this.stackId = stackId; }

    public String getStackName() { return stackName; }
    public void setStackName(String stackName) { this.stackName = stackName; }

    public String getStackVersion() { return stackVersion; }
    public void setStackVersion(String stackVersion) { this.stackVersion = stackVersion; }

    public Long getMpackId() { return mpackId; }
    public void setMpackId(Long mpackId) { this.mpackId = mpackId; }
}
