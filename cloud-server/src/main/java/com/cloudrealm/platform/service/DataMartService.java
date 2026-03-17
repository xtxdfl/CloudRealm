package com.cloudrealm.platform.service;

import com.cloudrealm.platform.model.*;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class DataMartService {

    private final List<Registry> registries = new ArrayList<>();
    private final List<Mpack> mpacks = new ArrayList<>();
    private final List<Stack> stacks = new ArrayList<>();
    private final List<Extension> extensions = new ArrayList<>();
    private final List<ExtensionLink> extensionLinks = new ArrayList<>();
    private final List<DataAsset> dataAssets = new ArrayList<>();

    public DataMartService() {
        // Initialize Mock Data for Registries
        registries.add(new Registry(1L, "Docker Hub", "DOCKER", "https://hub.docker.com"));
        registries.add(new Registry(2L, "Maven Central", "MAVEN", "https://repo.maven.apache.org"));

        // Initialize Mock Data for Mpacks
        mpacks.add(new Mpack(1L, "HDP", "3.1.0", "https://archive.apache.org/dist/ambari/", 1L));
        mpacks.add(new Mpack(2L, "CDH", "6.3.2", "https://archive.cloudera.com/", 2L));

        // Initialize Mock Data for Stacks
        stacks.add(new Stack(1L, "HDP", "3.1.0", 1L));
        stacks.add(new Stack(2L, "CDH", "6.3.2", 2L));

        // Initialize Mock Data for Extensions
        extensions.add(new Extension(1L, "Hive-JDBC", "2.3.8"));
        extensions.add(new Extension(2L, "Spark-SQL", "3.5.0"));

        // Initialize Mock Data for Extension Links
        extensionLinks.add(new ExtensionLink(1L, 1L, 1L));
        extensionLinks.add(new ExtensionLink(2L, 2L, 2L));

        // Initialize Mock Data for Data Assets
        dataAssets.add(new DataAsset(
            "dw_sales.fact_orders", "HIVE", "DataTeam", 98.5,
            "Daily sales transactions fact table",
            "ods.orders_log", "dm_sales.daily_report"
        ));
        dataAssets.add(new DataAsset(
            "ods_log.clickstream", "KAFKA", "AppTeam", 100.0,
            "Real-time user click events",
            "app_server", "dw_log.user_behavior"
        ));
        dataAssets.add(new DataAsset(
            "dim_users", "HBASE", "UserCenter", 92.0,
            "User profile dimension table",
            "crm_db.users", "dw_sales.fact_orders"
        ));
    }

    public List<Registry> getAllRegistries() {
        return registries;
    }

    public List<Mpack> getAllMpacks() {
        return mpacks;
    }

    public List<Stack> getAllStacks() {
        return stacks;
    }

    public List<Extension> getAllExtensions() {
        return extensions;
    }

    public List<ExtensionLink> getAllExtensionLinks() {
        return extensionLinks;
    }

    public List<DataAsset> getAllDataAssets() {
        return dataAssets;
    }

    public DataMartStats getDataMartStats() {
        return new DataMartStats(dataAssets.size(), 94.2, 1.2, 65);
    }

    public void addRegistry(Registry registry) {
        registry.setId((long) (registries.size() + 1));
        registries.add(registry);
    }

    public void addMpack(Mpack mpack) {
        mpack.setId((long) (mpacks.size() + 1));
        mpacks.add(mpack);
    }

    public void addStack(Stack stack) {
        stack.setStackId((long) (stacks.size() + 1));
        stacks.add(stack);
    }

    public void addExtension(Extension extension) {
        extension.setExtensionId((long) (extensions.size() + 1));
        extensions.add(extension);
    }

    public void addDataAsset(DataAsset dataAsset) {
        dataAssets.add(dataAsset);
    }
}
