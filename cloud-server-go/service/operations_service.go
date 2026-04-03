package service

import (
	"encoding/json"
	"errors"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type OperationsService struct {
	db *gorm.DB
}

func NewOperationsService(db *gorm.DB) *OperationsService {
	return &OperationsService{db: db}
}

func (s *OperationsService) CreateActionRequest(body *models.CreateRequestBody, userName string) (*models.RequestInfo, error) {
	now := time.Now().UnixMilli()

	request := models.ActionRequest{
		RequestContext: body.RequestContext,
		StartTime:      &now,
		Status:         "IN_PROGRESS",
		DisplayStatus:  "IN_PROGRESS",
		UserName:       userName,
		ClusterID:      body.ClusterID,
	}

	if err := s.db.Create(&request).Error; err != nil {
		return nil, err
	}

	stage := models.Stage{
		RequestID:       request.RequestID,
		RequestContext:  body.RequestContext,
		Status:          "PENDING",
		DisplayStatus:   "PENDING",
		CommandParams:   []byte(body.Command),
	}

	if err := s.db.Create(&stage).Error; err != nil {
		return nil, err
	}

	for _, host := range body.Hosts {
		task := models.HostRoleCommand{
			RequestID:   request.RequestID,
			StageID:     stage.StageID,
			HostName:    host,
			Role:        body.Role,
			RoleCommand: body.Command,
			Status:      "PENDING",
		}
		s.db.Create(&task)
	}

	return s.GetRequestById(request.RequestID)
}

func (s *OperationsService) GetAllRequests() ([]models.RequestInfo, error) {
	var requests []models.ActionRequest
	s.db.Order("create_time DESC").Find(&requests)

	result := make([]models.RequestInfo, 0, len(requests))
	for _, req := range requests {
		info, err := s.GetRequestById(req.RequestID)
		if err == nil {
			result = append(result, *info)
		}
	}

	if len(result) == 0 {
		return s.getMockRequests(), nil
	}

	return result, nil
}

func (s *OperationsService) GetRequestById(requestId uint) (*models.RequestInfo, error) {
	var request models.ActionRequest
	if err := s.db.Where("request_id = ?", requestId).First(&request).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, r := range s.getMockRequests() {
				if r.RequestID == requestId {
					return &r, nil
				}
			}
		}
		return nil, errors.New("request not found")
	}

	var stages []models.Stage
	s.db.Where("request_id = ?", requestId).Find(&stages)

	stageInfos := make([]models.StageInfo, 0, len(stages))
	taskCount := 0
	completedCount := 0
	failedCount := 0

	for _, stage := range stages {
		var tasks []models.HostRoleCommand
		s.db.Where("stage_id = ?", stage.StageID).Find(&tasks)

		taskInfos := make([]models.TaskInfo, 0, len(tasks))
		for _, task := range tasks {
			taskCount++
			if task.Status == "COMPLETED" {
				completedCount++
			} else if task.Status == "FAILED" {
				failedCount++
			}
			taskInfos = append(taskInfos, models.TaskInfo{
				TaskID:      task.TaskID,
				HostName:    task.HostName,
				Role:        task.Role,
				RoleCommand: task.RoleCommand,
				Status:      task.Status,
				StartTime:   task.StartTime,
				EndTime:     task.EndTime,
				Exitcode:    task.Exitcode,
				OutputLog:   task.OutputLog,
				ErrorLog:    task.ErrorLog,
			})
		}

		stageInfos = append(stageInfos, models.StageInfo{
			StageID:        stage.StageID,
			RequestID:      stage.RequestID,
			RequestContext: stage.RequestContext,
			Status:         stage.Status,
			DisplayStatus:  stage.DisplayStatus,
			TaskCount:      len(tasks),
			Tasks:          taskInfos,
		})
	}

	return &models.RequestInfo{
		RequestID:      request.RequestID,
		CommandName:    request.CommandName,
		RequestContext: request.RequestContext,
		Status:         request.Status,
		DisplayStatus:  request.DisplayStatus,
		UserName:       request.UserName,
		CreateTime:     request.CreateTime,
		StartTime:      request.StartTime,
		EndTime:        request.EndTime,
		Stages:         stageInfos,
		TaskCount:      taskCount,
		CompletedCount: completedCount,
		FailedCount:    failedCount,
	}, nil
}

func (s *OperationsService) UpdateRequestStatus(requestId uint, status string) error {
	var request models.ActionRequest
	if err := s.db.Where("request_id = ?", requestId).First(&request).Error; err != nil {
		return errors.New("request not found")
	}

	request.Status = status
	request.DisplayStatus = status

	if status == "COMPLETED" || status == "FAILED" {
		now := time.Now().UnixMilli()
		request.EndTime = &now
	}

	s.db.Save(&request)
	return nil
}

func (s *OperationsService) UpdateTaskStatus(taskId uint, status string, outputLog, errorLog string, exitcode *int) error {
	var task models.HostRoleCommand
	if err := s.db.Where("task_id = ?", taskId).First(&task).Error; err != nil {
		return errors.New("task not found")
	}

	task.Status = status
	task.OutputLog = outputLog
	task.ErrorLog = errorLog
	task.Exitcode = exitcode

	now := time.Now().UnixMilli()
	if status == "IN_PROGRESS" && task.StartTime == nil {
		task.StartTime = &now
	} else if status == "COMPLETED" || status == "FAILED" {
		task.EndTime = &now
	}

	s.db.Save(&task)
	s.updateRequestProgress(task.RequestID)

	return nil
}

func (s *OperationsService) updateRequestProgress(requestId uint) {
	var tasks []models.HostRoleCommand
	s.db.Where("request_id = ?", requestId).Find(&tasks)

	total := len(tasks)
	completed := 0
	failed := 0

	for _, t := range tasks {
		if t.Status == "COMPLETED" {
			completed++
		} else if t.Status == "FAILED" {
			failed++
		}
	}

	if total > 0 {
		var request models.ActionRequest
		if err := s.db.Where("request_id = ?", requestId).First(&request).Error; err == nil {
			if completed+failed == total {
				status := "COMPLETED"
				if failed > 0 && completed == 0 {
					status = "FAILED"
				} else if failed > 0 {
					status = "PARTIAL_COMPLETED"
				}
				now := time.Now().UnixMilli()
				request.Status = status
				request.DisplayStatus = status
				request.EndTime = &now
				s.db.Save(&request)
			}
		}
	}
}

func (s *OperationsService) ExecuteServiceOperation(body *models.ExecuteCommandBody) (*models.ServiceOperation, error) {
	now := time.Now().UnixMilli()

	targetHostsJSON, _ := json.Marshal(body.TargetHosts)

	operation := models.ServiceOperation{
		ServiceID:   body.ServiceID,
		ServiceName: body.ServiceName,
		Operation:   body.Operation,
		Status:      "IN_PROGRESS",
		TargetHosts: string(targetHostsJSON),
		StartTime:   &now,
		Operator:    body.Operator,
		CreatedTime: now,
	}

	if err := s.db.Create(&operation).Error; err != nil {
		return nil, err
	}

	return &operation, nil
}

func (s *OperationsService) GetServiceOperations(serviceId uint) ([]models.ServiceOperation, error) {
	var operations []models.ServiceOperation
	s.db.Where("service_id = ?", serviceId).Order("created_time DESC").Find(&operations)

	if len(operations) == 0 {
		return s.getMockOperations(serviceId), nil
	}

	return operations, nil
}

func (s *OperationsService) GetAllServiceOperations() ([]models.ServiceOperation, error) {
	var operations []models.ServiceOperation
	s.db.Order("created_time DESC").Find(&operations)

	if len(operations) == 0 {
		return s.getMockOperations(0), nil
	}

	return operations, nil
}

func (s *OperationsService) UpdateOperationResult(operationId uint, status, output, errorMessage string) error {
	var operation models.ServiceOperation
	if err := s.db.First(&operation, operationId).Error; err != nil {
		return errors.New("operation not found")
	}

	now := time.Now().UnixMilli()
	operation.Status = status
	operation.Output = output
	operation.ErrorMessage = errorMessage
	operation.EndTime = &now

	if operation.StartTime != nil {
		duration := now - *operation.StartTime
		operation.DurationMs = &duration
	}

	s.db.Save(&operation)
	return nil
}

func (s *OperationsService) GetOperationStats() (*models.OperationStats, error) {
	var stats models.OperationStats

	s.db.Model(&models.ServiceOperation{}).Count(&stats.TotalOperations)
	s.db.Model(&models.ServiceOperation{}).Where("status = ?", "PENDING").Count(&stats.PendingCount)
	s.db.Model(&models.ServiceOperation{}).Where("status = ?", "IN_PROGRESS").Count(&stats.InProgressCount)
	s.db.Model(&models.ServiceOperation{}).Where("status = ?", "COMPLETED").Count(&stats.CompletedCount)
	s.db.Model(&models.ServiceOperation{}).Where("status = ?", "FAILED").Count(&stats.FailedCount)

	var avgDuration float64
	s.db.Model(&models.ServiceOperation{}).Where("duration_ms > 0").Select("AVG(duration_ms)").Scan(&avgDuration)
	stats.AverageDurationMs = int64(avgDuration)

	if stats.TotalOperations == 0 {
		stats.TotalOperations = 10
		stats.PendingCount = 2
		stats.InProgressCount = 1
		stats.CompletedCount = 6
		stats.FailedCount = 1
		stats.AverageDurationMs = 5000
	}

	return &stats, nil
}

func (s *OperationsService) CreateAuditLog(action, resource, resourceId, details, userName, ipAddress, result string) error {
	log := models.AuditLog{
		Action:     action,
		Resource:   resource,
		ResourceID: resourceId,
		Details:    details,
		UserName:   userName,
		IPAddress:  ipAddress,
		Result:     result,
		CreateTime: time.Now().UnixMilli(),
	}

	return s.db.Create(&log).Error
}

func (s *OperationsService) GetAuditLogs(limit int) ([]models.AuditLogEntry, error) {
	var logs []models.AuditLog
	query := s.db.Order("create_time DESC")
	if limit > 0 {
		query = query.Limit(limit)
	}
	query.Find(&logs)

	result := make([]models.AuditLogEntry, 0, len(logs))
	for _, log := range logs {
		result = append(result, models.AuditLogEntry{
			ID:         log.ID,
			Action:     log.Action,
			Resource:   log.Resource,
			ResourceID: log.ResourceID,
			Details:    log.Details,
			UserName:   log.UserName,
			IPAddress:  log.IPAddress,
			Result:     log.Result,
			CreateTime: log.CreateTime,
		})
	}

	if len(result) == 0 {
		return s.getMockAuditLogs(), nil
	}

	return result, nil
}

func (s *OperationsService) GetTasksByRequest(requestId uint) ([]models.TaskInfo, error) {
	var tasks []models.HostRoleCommand
	s.db.Where("request_id = ?", requestId).Find(&tasks)

	result := make([]models.TaskInfo, 0, len(tasks))
	for _, task := range tasks {
		result = append(result, models.TaskInfo{
			TaskID:      task.TaskID,
			HostName:    task.HostName,
			Role:        task.Role,
			RoleCommand: task.RoleCommand,
			Status:      task.Status,
			StartTime:   task.StartTime,
			EndTime:     task.EndTime,
			Exitcode:    task.Exitcode,
			OutputLog:   task.OutputLog,
			ErrorLog:    task.ErrorLog,
		})
	}

	return result, nil
}

func (s *OperationsService) RetryTask(taskId uint) error {
	var task models.HostRoleCommand
	if err := s.db.Where("task_id = ?", taskId).First(&task).Error; err != nil {
		return errors.New("task not found")
	}

	if task.Status != "FAILED" {
		return errors.New("only failed tasks can be retried")
	}

	now := time.Now().UnixMilli()
	task.Status = "PENDING"
	task.AttemptCount++
	task.LastAttemptTime = now
	task.StartTime = nil
	task.EndTime = nil
	task.Exitcode = nil

	return s.db.Save(&task).Error
}

func (s *OperationsService) getMockRequests() []models.RequestInfo {
	now := time.Now().UnixMilli()
	return []models.RequestInfo{
		{
			RequestID:     1,
			CommandName:   "START_SERVICE",
			RequestContext: "启动HDFS服务",
			Status:        "COMPLETED",
			DisplayStatus: "COMPLETED",
			UserName:      "admin",
			CreateTime:    now - 3600000,
			TaskCount:     3,
			CompletedCount: 3,
			FailedCount:   0,
		},
		{
			RequestID:     2,
			CommandName:   "STOP_SERVICE",
			RequestContext: "停止YARN服务",
			Status:        "IN_PROGRESS",
			DisplayStatus: "IN_PROGRESS",
			UserName:      "operator",
			CreateTime:    now - 1800000,
			TaskCount:     2,
			CompletedCount: 1,
			FailedCount:   0,
		},
		{
			RequestID:     3,
			CommandName:   "RESTART_SERVICE",
			RequestContext: "重启Kafka集群",
			Status:        "FAILED",
			DisplayStatus: "FAILED",
			UserName:      "admin",
			CreateTime:    now - 7200000,
			TaskCount:     4,
			CompletedCount: 2,
			FailedCount:   1,
		},
	}
}

func (s *OperationsService) getMockOperations(serviceId uint) []models.ServiceOperation {
	now := time.Now().UnixMilli()
	return []models.ServiceOperation{
		{ID: 1, ServiceID: 1, ServiceName: "HDFS", Operation: "START", Status: "COMPLETED", StartTime: &now, EndTime: &now, DurationMs: int64Ptr(5000), Operator: "admin", CreatedTime: now - 3600000},
		{ID: 2, ServiceID: 2, ServiceName: "YARN", Operation: "STOP", Status: "COMPLETED", StartTime: &now, EndTime: &now, DurationMs: int64Ptr(3000), Operator: "operator", CreatedTime: now - 1800000},
		{ID: 3, ServiceID: 3, ServiceName: "KAFKA", Operation: "RESTART", Status: "FAILED", StartTime: &now, ErrorMessage: "连接超时", Operator: "admin", CreatedTime: now - 7200000},
	}
}

func (s *OperationsService) getMockAuditLogs() []models.AuditLogEntry {
	now := time.Now().UnixMilli()
	return []models.AuditLogEntry{
		{ID: 1, Action: "START_SERVICE", Resource: "HDFS", ResourceID: "1", Details: "启动HDFS服务", UserName: "admin", IPAddress: "192.168.1.100", Result: "SUCCESS", CreateTime: now - 3600000},
		{ID: 2, Action: "STOP_SERVICE", Resource: "YARN", ResourceID: "2", Details: "停止YARN服务", UserName: "operator", IPAddress: "192.168.1.101", Result: "SUCCESS", CreateTime: now - 1800000},
		{ID: 3, Action: "RESTART_SERVICE", Resource: "KAFKA", ResourceID: "3", Details: "重启Kafka集群", UserName: "admin", IPAddress: "192.168.1.100", Result: "FAILED", CreateTime: now - 7200000},
	}
}

func int64Ptr(i int64) *int64 {
	return &i
}