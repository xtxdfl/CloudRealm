package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.entity.HostRegistrationLogEntity;
import com.cloudrealm.platform.entity.action.HostRoleCommandEntity;
import com.cloudrealm.platform.model.Status;
import com.cloudrealm.platform.model.agent.AgentHeartbeatRequest;
import com.cloudrealm.platform.model.agent.AgentHeartbeatResponse;
import com.cloudrealm.platform.model.agent.AgentRegistrationRequest;
import com.cloudrealm.platform.repository.HostRegistrationLogRepository;
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

    @Autowired
    private HostRegistrationLogRepository registrationLogRepository;

    /**
     * Agent注册处理
     */
    @Transactional
    public void registerAgent(AgentRegistrationRequest request) {
        Optional<HostEntity> existingHost = hostRepository.findByHostName(request.getHostname());

        HostEntity host;
        boolean isNew = false;

        if (existingHost.isPresent()) {
            host = existingHost.get();
            // 更新已存在的主机信息
            if (request.getIpv4() != null) host.setIpv4(request.getIpv4());
            if (request.getPublicHostname() != null) host.setPublicHostName(request.getPublicHostname());
            if (request.getIpv6() != null) host.setIpv6(request.getIpv6());
            if (request.getOsType() != null) host.setOsType(request.getOsType());
            if (request.getOsArch() != null) host.setOsArch(request.getOsArch());
            if (request.getOsInfo() != null) host.setOsInfo(request.getOsInfo());
            if (request.getCpuCount() != null) host.setCpuCount(request.getCpuCount());
            if (request.getCpuInfo() != null) host.setCpuInfo(request.getCpuInfo());
            if (request.getTotalMem() != null) host.setTotalMem(request.getTotalMem());
            if (request.getTotalDisk() != null) host.setTotalDisk(request.getTotalDisk());
            if (request.getDiskInfo() != null) host.setDiskInfo(request.getDiskInfo());
            if (request.getNetworkInfo() != null) host.setNetworkInfo(request.getNetworkInfo());
            if (request.getAgentVersion() != null) host.setAgentVersion(request.getAgentVersion());
            if (request.getRackInfo() != null) host.setRackInfo(request.getRackInfo());
        } else {
            // 新建主机
            isNew = true;
            host = new HostEntity();
            host.setHostName(request.getHostname());
            host.setIpv4(request.getIpv4());
            host.setPublicHostName(request.getPublicHostname());
            host.setIpv6(request.getIpv6());
            host.setOsType(request.getOsType() != null ? request.getOsType() : "Linux");
            host.setOsArch(request.getOsArch() != null ? request.getOsArch() : "x86_64");
            host.setOsInfo(request.getOsInfo() != null ? request.getOsInfo() : "Linux");
            host.setCpuCount(request.getCpuCount() != null ? request.getCpuCount() : 0);
            host.setCpuInfo(request.getCpuInfo() != null ? request.getCpuInfo() : "Unknown");
            host.setTotalMem(request.getTotalMem() != null ? request.getTotalMem() : 0L);
            host.setTotalDisk(request.getTotalDisk() != null ? request.getTotalDisk() : 0L);
            host.setDiskInfo(request.getDiskInfo() != null ? request.getDiskInfo() : "[]");
            host.setNetworkInfo(request.getNetworkInfo() != null ? request.getNetworkInfo() : "[]");
            host.setAgentVersion(request.getAgentVersion());
            host.setRackInfo(request.getRackInfo() != null ? request.getRackInfo() : "/default-rack");
            host.setHostAttributes("{}");
            host.setDiscoveryStatus("INITIALIZING");
        }

        host.setLastRegistrationTime(System.currentTimeMillis());
        host.setLastHeartbeatTime(System.currentTimeMillis());
        host.setAgentStatus("ONLINE");
        host.setDiscoveryStatus(Status.HEALTHY.name());

        hostRepository.save(host);
        System.out.println("Agent registered: " + request.getHostname() + (isNew ? " (New)" : " (Updated)"));

        // 记录注册日志
        logRegistration(host, isNew ? "AGENT_AUTO" : "AGENT_UPDATE", "SUCCESS", null);
    }

    /**
     * 处理Agent心跳
     */
    @Transactional
    public AgentHeartbeatResponse processHeartbeat(AgentHeartbeatRequest request) {
        // 1. Update host last heartbeat time and status
        Optional<HostEntity> existingHost = hostRepository.findByHostName(request.getHostname());

        if (existingHost.isPresent()) {
            HostEntity host = existingHost.get();
            host.setLastHeartbeatTime(System.currentTimeMillis());
            host.setAgentStatus(request.getAgentStatus() != null ? request.getAgentStatus() : "ONLINE");
            host.setDiscoveryStatus(Status.HEALTHY.name());

            // 更新主机资源信息（可选）
            if (request.getCpuCount() != null) host.setCpuCount(request.getCpuCount());
            if (request.getCpuUsage() != null) host.setCpuUsage(request.getCpuUsage());
            if (request.getTotalMem() != null) host.setTotalMem(request.getTotalMem());
            if (request.getUsedMem() != null) host.setUsedMem(request.getUsedMem());
            if (request.getMemoryUsage() != null) host.setMemoryUsage(request.getMemoryUsage());
            if (request.getTotalDisk() != null) host.setTotalDisk(request.getTotalDisk());
            if (request.getUsedDisk() != null) host.setUsedDisk(request.getUsedDisk());
            if (request.getDiskUsage() != null) host.setDiskUsage(request.getDiskUsage());
            if (request.getDiskInfo() != null) host.setDiskInfo(request.getDiskInfo());
            if (request.getNetworkInfo() != null) host.setNetworkInfo(request.getNetworkInfo());

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
            agentCommand.setPayload("{}");

            commandsToExecute.add(agentCommand);
        }

        response.setExecutionCommands(commandsToExecute);
        return response;
    }

    /**
     * 记录注册日志
     */
    private void logRegistration(HostEntity host, String type, String status, String errorMsg) {
        HostRegistrationLogEntity log = new HostRegistrationLogEntity();
        log.setHostId(host.getHostId());
        log.setHostName(host.getHostName());
        log.setIpv4(host.getIpv4());
        log.setRegistrationType(type);
        log.setStatus(status);
        log.setErrorMessage(errorMsg);
        log.setRegisteredTime(System.currentTimeMillis());
        registrationLogRepository.save(log);
    }
}
