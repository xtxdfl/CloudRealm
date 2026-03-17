package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.entity.action.HostRoleCommandEntity;
import com.cloudrealm.platform.model.Status;
import com.cloudrealm.platform.model.agent.AgentHeartbeatRequest;
import com.cloudrealm.platform.model.agent.AgentHeartbeatResponse;
import com.cloudrealm.platform.model.agent.AgentRegistrationRequest;
import com.cloudrealm.platform.repository.HostRepository;
import com.cloudrealm.platform.repository.action.HostRoleCommandRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class AgentService {

    @Autowired
    private HostRepository hostRepository;

    @Autowired
    private HostRoleCommandRepository commandRepository;

    @Transactional
    public void registerAgent(AgentRegistrationRequest request) {
        Optional<HostEntity> existingHost = hostRepository.findAll().stream()
                .filter(h -> h.getHostName().equals(request.getHostname()))
                .findFirst();

        HostEntity host = existingHost.orElse(new HostEntity());
        host.setHostName(request.getHostname());
        host.setIpv4(request.getIpv4());
        host.setOsType(request.getOsType() != null ? request.getOsType() : "Unknown");
        host.setOsArch(request.getOsArch() != null ? request.getOsArch() : "Unknown");
        host.setCpuCount(request.getCpuCount() != null ? request.getCpuCount() : 0);
        host.setTotalMem(request.getTotalMem() != null ? request.getTotalMem() : 0L);
        host.setLastRegistrationTime(System.currentTimeMillis());
        host.setDiscoveryStatus(Status.HEALTHY.name());
        host.setHostAttributes("{}");
        host.setCpuInfo("Agent Registered CPU");
        host.setOsInfo(request.getOsType() != null ? request.getOsType() : "Linux");
        host.setRackInfo("/default-rack");

        hostRepository.save(host);
        System.out.println("Agent registered: " + request.getHostname());
    }

    @Transactional
    public AgentHeartbeatResponse processHeartbeat(AgentHeartbeatRequest request) {
        // 1. Update host last heartbeat time
        Optional<HostEntity> existingHost = hostRepository.findAll().stream()
                .filter(h -> h.getHostName().equals(request.getHostname()))
                .findFirst();

        if (existingHost.isPresent()) {
            HostEntity host = existingHost.get();
            host.setLastRegistrationTime(System.currentTimeMillis());
            host.setDiscoveryStatus(Status.HEALTHY.name());
            hostRepository.save(host);
        }

        // 2. Process command reports
        if (request.getCommandReports() != null) {
            for (AgentHeartbeatRequest.CommandReport report : request.getCommandReports()) {
                commandRepository.findById(report.getTaskId()).ifPresent(cmd -> {
                    cmd.setStatus(report.getStatus());
                    cmd.setExitcode(report.getExitCode());
                    if (report.getStdout() != null) cmd.setStdOut(report.getStdout().getBytes());
                    if (report.getStderr() != null) cmd.setStdError(report.getStderr().getBytes());
                    
                    if ("COMPLETED".equals(report.getStatus()) || "FAILED".equals(report.getStatus())) {
                        cmd.setEndTime(System.currentTimeMillis());
                    }
                    commandRepository.save(cmd);
                });
            }
        }

        // 3. Fetch pending commands for this host
        List<HostRoleCommandEntity> pendingCommands = commandRepository.findByHostNameAndStatus(request.getHostname(), "PENDING");
        
        AgentHeartbeatResponse response = new AgentHeartbeatResponse();
        response.setResponseId(UUID.randomUUID().toString());
        List<AgentHeartbeatResponse.AgentCommand> commandsToExecute = new ArrayList<>();

        for (HostRoleCommandEntity cmd : pendingCommands) {
            // Change status to QUEUED
            cmd.setStatus("QUEUED");
            commandRepository.save(cmd);

            AgentHeartbeatResponse.AgentCommand agentCommand = new AgentHeartbeatResponse.AgentCommand();
            agentCommand.setTaskId(cmd.getTaskId());
            agentCommand.setCommandType(cmd.getRoleCommand());
            agentCommand.setComponentName(cmd.getRole());
            agentCommand.setPayload("{}"); // Should be loaded from execution command payload
            
            commandsToExecute.add(agentCommand);
        }

        response.setExecutionCommands(commandsToExecute);
        return response;
    }
}
