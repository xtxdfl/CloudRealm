package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.action.HostRoleCommandEntity;
import com.cloudrealm.platform.entity.action.RequestEntity;
import com.cloudrealm.platform.entity.action.StageEntity;
import com.cloudrealm.platform.repository.action.HostRoleCommandRepository;
import com.cloudrealm.platform.repository.action.RequestRepository;
import com.cloudrealm.platform.repository.action.StageRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ActionQueueService {

    @Autowired
    private RequestRepository requestRepository;

    @Autowired
    private StageRepository stageRepository;

    @Autowired
    private HostRoleCommandRepository commandRepository;

    @Transactional
    public RequestEntity createActionRequest(String requestContext, List<String> hosts, String role, String command) {
        // 1. Create Request
        RequestEntity request = new RequestEntity();
        request.setRequestContext(requestContext);
        request.setStartTime(System.currentTimeMillis());
        request.setStatus("IN_PROGRESS");
        request = requestRepository.save(request);

        // 2. Create Stage
        StageEntity stage = new StageEntity();
        stage.setRequestId(request.getRequestId());
        stage.setRequestContext(requestContext);
        stage = stageRepository.save(stage);

        // 3. Create HostRoleCommands (Tasks)
        for (String host : hosts) {
            HostRoleCommandEntity task = new HostRoleCommandEntity();
            task.setRequestId(request.getRequestId());
            task.setStageId(stage.getStageId());
            task.setHostName(host);
            task.setRole(role);
            task.setRoleCommand(command);
            task.setStatus("PENDING");
            task.setStartTime(System.currentTimeMillis());
            commandRepository.save(task);
        }

        return request;
    }

    public List<RequestEntity> getAllRequests() {
        return requestRepository.findAll();
    }
}
