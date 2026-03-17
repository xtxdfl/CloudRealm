package com.cloudrealm.platform.model;

public class HostGroup {
    private String blueprintName;
    private String name;
    private String cardinality;

    public HostGroup() {}

    public HostGroup(String blueprintName, String name, String cardinality) {
        this.blueprintName = blueprintName;
        this.name = name;
        this.cardinality = cardinality;
    }

    public String getBlueprintName() { return blueprintName; }
    public void setBlueprintName(String blueprintName) { this.blueprintName = blueprintName; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getCardinality() { return cardinality; }
    public void setCardinality(String cardinality) { this.cardinality = cardinality; }
}
