package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.model.*;
import com.cloudrealm.platform.service.DataMartService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/datamart")
@CrossOrigin(origins = "*")
public class DataMartController {

    @Autowired
    private DataMartService dataMartService;

    @GetMapping("/assets")
    public List<DataAsset> getDataAssets() {
        return dataMartService.getAllDataAssets();
    }

    @GetMapping("/registries")
    public List<Registry> getRegistries() {
        return dataMartService.getAllRegistries();
    }

    @GetMapping("/mpacks")
    public List<Mpack> getMpacks() {
        return dataMartService.getAllMpacks();
    }

    @GetMapping("/stacks")
    public List<Stack> getStacks() {
        return dataMartService.getAllStacks();
    }

    @GetMapping("/extensions")
    public List<Extension> getExtensions() {
        return dataMartService.getAllExtensions();
    }

    @GetMapping("/extensionlinks")
    public List<ExtensionLink> getExtensionLinks() {
        return dataMartService.getAllExtensionLinks();
    }

    @GetMapping("/stats")
    public DataMartStats getDataMartStats() {
        return dataMartService.getDataMartStats();
    }

    @PostMapping("/registries")
    public ResponseEntity<Map<String, Object>> addRegistry(@RequestBody Registry registry) {
        dataMartService.addRegistry(registry);
        return ResponseEntity.ok(Map.of("message", "Registry added successfully", "registry", registry));
    }

    @PostMapping("/mpacks")
    public ResponseEntity<Map<String, Object>> addMpack(@RequestBody Mpack mpack) {
        dataMartService.addMpack(mpack);
        return ResponseEntity.ok(Map.of("message", "Mpack added successfully", "mpack", mpack));
    }

    @PostMapping("/stacks")
    public ResponseEntity<Map<String, Object>> addStack(@RequestBody Stack stack) {
        dataMartService.addStack(stack);
        return ResponseEntity.ok(Map.of("message", "Stack added successfully", "stack", stack));
    }

    @PostMapping("/extensions")
    public ResponseEntity<Map<String, Object>> addExtension(@RequestBody Extension extension) {
        dataMartService.addExtension(extension);
        return ResponseEntity.ok(Map.of("message", "Extension added successfully", "extension", extension));
    }

    @PostMapping("/assets")
    public ResponseEntity<Map<String, Object>> addDataAsset(@RequestBody DataAsset dataAsset) {
        dataMartService.addDataAsset(dataAsset);
        return ResponseEntity.ok(Map.of("message", "Data asset added successfully", "asset", dataAsset));
    }
}
