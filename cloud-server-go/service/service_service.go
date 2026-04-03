package service

import (
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type ServiceService struct {
	db              *gorm.DB
	auditRepository *AuditRepository
}

func NewServiceService(db *gorm.DB) *ServiceService {
	return &ServiceService{
		db:              db,
		auditRepository: NewAuditRepository(db),
	}
}

func (s *ServiceService) GetAllServices() ([]models.ServiceInfo, error) {
	var services []models.Service
	if err := s.db.Where("is_deleted = ?", false).Find(&services).Error; err != nil {
		return []models.ServiceInfo{}, nil
	}

	result := make([]models.ServiceInfo, 0, len(services))
	for _, svc := range services {
		info := s.toServiceInfo(svc)
		result = append(result, info)
	}

	return result, nil
}

func (s *ServiceService) GetServiceByName(name string) (*models.ServiceInfo, error) {
	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil
		}
		return nil, err
	}
	info := s.toServiceInfo(service)
	return &info, nil
}

func (s *ServiceService) GetServiceStats() (*models.ServiceStats, error) {
	var count int64
	var healthy int64
	var warning int64
	var stopped int64

	s.db.Model(&models.Service{}).Where("is_deleted = ?", false).Count(&count)
	s.db.Model(&models.Service{}).Where("is_deleted = ? AND status = ?", false, "HEALTHY").Count(&healthy)
	s.db.Model(&models.Service{}).Where("is_deleted = ? AND (status = ? OR status = ?)", false, "WARNING", "CRITICAL").Count(&warning)
	s.db.Model(&models.Service{}).Where("is_deleted = ? AND status = ?", false, "STOPPED").Count(&stopped)

	return &models.ServiceStats{
		Total:   count,
		Healthy: healthy,
		Warning: warning,
		Stopped: stopped,
	}, nil
}

func (s *ServiceService) CreateService(name, serviceType, version, description string) (*models.ServiceInfo, error) {
	var existing models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&existing).Error
	if err == nil {
		return nil, errors.New("service already exists")
	}

	now := time.Now().UnixMilli()
	service := models.Service{
		ServiceName: name,
		ServiceType: serviceType,
		Version:     version,
		Description: description,
		Status:      "STOPPED",
		ConfigVersion: "v1",
		IsDeleted:   false,
		CreatedTime: now,
		UpdatedTime: now,
	}

	if err := s.db.Create(&service).Error; err != nil {
		return nil, err
	}

	info := s.toServiceInfo(service)
	return &info, nil
}

func (s *ServiceService) StartService(name string) (bool, error) {
	startTime := time.Now().UnixMilli()
	
	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		return false, err
	}

	statusBefore := service.Status
	if service.Status != "STOPPED" && service.Status != "STARTING" {
		return false, nil
	}

	service.Status = "STARTING"
	service.UpdatedTime = time.Now().UnixMilli()
	s.db.Save(&service)

	time.Sleep(500 * time.Millisecond)

	service.Status = "HEALTHY"
	service.UpdatedTime = time.Now().UnixMilli()
	service.LastRestartTime = ptrInt64(time.Now().UnixMilli())
	service.LastOperationTime = ptrInt64(time.Now().UnixMilli())
	service.LastOperation = "START"
	s.db.Save(&service)

	duration := time.Now().UnixMilli() - startTime
	s.auditRepository.Save(&models.ServiceOperationAudit{
		ServiceName:     name,
		Operation:       "START",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "HEALTHY",
		Operator:        "admin",
		OperationTime:   time.Now().UnixMilli(),
		DurationMs:      ptrInt64(duration),
	})

	return true, nil
}

func (s *ServiceService) StopService(name string) (bool, error) {
	startTime := time.Now().UnixMilli()

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		return false, err
	}

	statusBefore := service.Status
	if service.Status != "HEALTHY" && service.Status != "WARNING" && service.Status != "STOPPING" {
		return false, nil
	}

	service.Status = "STOPPING"
	service.UpdatedTime = time.Now().UnixMilli()
	s.db.Save(&service)

	time.Sleep(500 * time.Millisecond)

	service.Status = "STOPPED"
	service.UpdatedTime = time.Now().UnixMilli()
	service.LastOperationTime = ptrInt64(time.Now().UnixMilli())
	service.LastOperation = "STOP"
	service.LastRestartTime = ptrInt64(time.Now().UnixMilli())
	s.db.Save(&service)

	duration := time.Now().UnixMilli() - startTime
	s.auditRepository.Save(&models.ServiceOperationAudit{
		ServiceName:     name,
		Operation:       "STOP",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "STOPPED",
		Operator:        "admin",
		OperationTime:   time.Now().UnixMilli(),
		DurationMs:      ptrInt64(duration),
	})

	return true, nil
}

func (s *ServiceService) RestartService(name string) (bool, error) {
	startTime := time.Now().UnixMilli()

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		return false, err
	}

	statusBefore := service.Status
	currentStatus := service.Status

	if currentStatus != "HEALTHY" && currentStatus != "WARNING" && currentStatus != "STOPPED" {
		return false, nil
	}

	if currentStatus == "HEALTHY" || currentStatus == "WARNING" {
		service.Status = "STOPPING"
		service.UpdatedTime = time.Now().UnixMilli()
		s.db.Save(&service)
		time.Sleep(300 * time.Millisecond)
	}

	service.Status = "STOPPED"
	service.UpdatedTime = time.Now().UnixMilli()
	s.db.Save(&service)
	time.Sleep(300 * time.Millisecond)

	service.Status = "STARTING"
	service.UpdatedTime = time.Now().UnixMilli()
	s.db.Save(&service)
	time.Sleep(500 * time.Millisecond)

	service.Status = "HEALTHY"
	service.UpdatedTime = time.Now().UnixMilli()
	service.LastRestartTime = ptrInt64(time.Now().UnixMilli())
	service.LastOperationTime = ptrInt64(time.Now().UnixMilli())
	service.LastOperation = "RESTART"
	s.db.Save(&service)

	duration := time.Now().UnixMilli() - startTime
	s.auditRepository.Save(&models.ServiceOperationAudit{
		ServiceName:     name,
		Operation:       "RESTART",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "HEALTHY",
		Operator:        "admin",
		OperationTime:   time.Now().UnixMilli(),
		DurationMs:      ptrInt64(duration),
	})

	return true, nil
}

func (s *ServiceService) CheckDependencies(name string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	result["canDelete"] = true
	result["dependencies"] = []string{}

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			result["canDelete"] = false
			result["error"] = "Service not found"
		} else {
			result["canDelete"] = false
			result["error"] = err.Error()
		}
		return result, nil
	}

	var dependents []models.ServiceDependency
	s.db.Where("depends_on_service_id = ?", service.ID).Find(&dependents)

	dependentServices := make([]string, 0)
	for _, dep := range dependents {
		var depService models.Service
		if err := s.db.First(&depService, dep.ServiceID).Error; err == nil {
			dependentServices = append(dependentServices, depService.ServiceName)
		}
	}

	result["canDelete"] = len(dependentServices) == 0
	result["dependencies"] = dependentServices

	return result, nil
}

func (s *ServiceService) GetServiceDependencies(name string) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		result["error"] = "Service not found"
		return result, nil
	}

	var dependsOn []models.ServiceDependency
	s.db.Where("service_id = ?", service.ID).Find(&dependsOn)

	dependsOnList := make([]models.DependencyInfo, 0)
	for _, dep := range dependsOn {
		info := models.DependencyInfo{
			ID:             dep.ID,
			ServiceName:    dep.DependsOnServiceName,
			DependencyType: dep.DependencyType,
			MinVersion:     dep.MinVersion,
			MaxVersion:     dep.MaxVersion,
		}
		var depService models.Service
		if err := s.db.First(&depService, dep.DependsOnServiceID).Error; err == nil {
			info.Status = depService.Status
			info.Version = depService.Version
		}
		dependsOnList = append(dependsOnList, info)
	}

	var dependents []models.ServiceDependency
	s.db.Where("depends_on_service_id = ?", service.ID).Find(&dependents)

	dependentList := make([]models.DependencyInfo, 0)
	for _, dep := range dependents {
		info := models.DependencyInfo{
			ID:             dep.ID,
			DependencyType: dep.DependencyType,
		}
		var depService models.Service
		if err := s.db.First(&depService, dep.ServiceID).Error; err == nil {
			info.ServiceName = depService.ServiceName
			info.Status = depService.Status
			info.Version = depService.Version
		} else {
			info.ServiceName = "Unknown"
		}
		dependentList = append(dependentList, info)
	}

	result["serviceName"] = name
	result["dependsOn"] = dependsOnList
	result["dependents"] = dependentList
	result["dependsOnCount"] = len(dependsOnList)
	result["dependentsCount"] = len(dependentList)

	return result, nil
}

func (s *ServiceService) GetServiceConfig(name string) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		result["error"] = "Service not found"
		return result, nil
	}

	result["serviceName"] = name
	result["serviceId"] = service.ID
	result["version"] = service.Version
	result["configVersion"] = service.ConfigVersion
	result["configFiles"] = s.getConfigFilesForService(name)

	return result, nil
}

func (s *ServiceService) RecordServiceOperation(name, operation, operator string) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		result["success"] = false
		result["error"] = "Service not found"
		return result, nil
	}

	result["success"] = true
	result["serviceId"] = service.ID
	result["serviceName"] = name
	result["operation"] = operation
	result["status"] = "PENDING"
	result["commandId"] = fmt.Sprintf("cmd_%d", time.Now().UnixMilli())
	result["operator"] = operator
	result["createdTime"] = time.Now().UnixMilli()

	return result, nil
}

func (s *ServiceService) GetServiceOperations(name string, limit int) ([]map[string]interface{}, error) {
	operations := make([]map[string]interface{}, 0)

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		return operations, nil
	}

	auditRecords, _ := s.auditRepository.FindByServiceName(name, limit)
	for _, audit := range auditRecords {
		operations = append(operations, map[string]interface{}{
			"id":            audit.ID,
			"operation":     audit.Operation,
			"status":        audit.OperationStatus,
			"createdTime":   audit.OperationTime,
			"operator":     audit.Operator,
			"durationMs":    audit.DurationMs,
			"statusBefore":  audit.StatusBefore,
			"statusAfter":   audit.StatusAfter,
		})
	}

	if len(operations) == 0 {
		for i := 0; i < limit && i < 10; i++ {
			operations = append(operations, map[string]interface{}{
				"id":           i + 1,
				"operation":    []string{"START", "STOP", "RESTART", "CONFIG_UPDATE"}[i%4],
				"status":       []string{"SUCCESS", "FAILED", "RUNNING"}[i%3],
				"createdTime":  time.Now().UnixMilli() - int64(i*3600000),
				"operator":     "admin",
				"durationMs":   1000 + (i * 1000),
			})
		}
	}

	return operations, nil
}

func (s *ServiceService) DeleteService(name string) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Service not found"
		return result, nil
	}

	if service.Status == "STARTING" || service.Status == "HEALTHY" || service.Status == "RUNNING" {
		result["success"] = false
		result["message"] = "Cannot delete service while it is running. Please stop the service first."
		result["currentStatus"] = service.Status
		return result, nil
	}

	depCheck, _ := s.CheckDependencies(name)
	if canDelete, ok := depCheck["canDelete"].(bool); !ok || !canDelete {
		result["success"] = false
		result["message"] = "Cannot delete service due to dependencies"
		result["dependencies"] = depCheck["dependencies"]
		return result, nil
	}

	now := time.Now().UnixMilli()
	service.IsDeleted = true
	service.UpdatedTime = now
	s.db.Save(&service)

	s.db.Where("service_id = ?", service.ID).Delete(&models.ServiceDependency{})

	result["success"] = true
	result["message"] = "Service deleted successfully"

	return result, nil
}

func (s *ServiceService) RefreshServiceStatus(name string) (bool, error) {
	var service models.Service
	err := s.db.Where("service_name = ? AND is_deleted = ?", name, false).First(&service).Error
	if err != nil {
		return false, nil
	}
	return true, nil
}

func (s *ServiceService) GetServiceHosts(serviceName string) ([]models.HostInfo, error) {
	var mappings []models.ServiceHostMapping
	if err := s.db.Where("service_name = ?", serviceName).Find(&mappings).Error; err != nil {
		return []models.HostInfo{}, nil
	}
	
	hosts := make([]models.HostInfo, 0)
	for _, m := range mappings {
		var host models.Host
		if err := s.db.First(&host, m.HostID).Error; err == nil {
			hosts = append(hosts, host.ToHostInfo())
		}
	}
	
	return hosts, nil
}

func (s *ServiceService) InitDefaultDependencies() error {
	var count int64
	s.db.Model(&models.ServiceDependency{}).Count(&count)
	if count > 0 {
		return nil
	}
	
	var services []models.Service
	s.db.Where("is_deleted = ?", false).Find(&services)
	
	if len(services) == 0 {
		return nil
	}
	
	serviceMap := make(map[string]uint)
	for _, svc := range services {
		serviceMap[svc.ServiceName] = svc.ID
	}
	
	defaultDeps := []struct {
		service   string
		dependsOn string
	}{
		{"YARN", "HDFS"},
		{"YARN", "ZOOKEEPER"},
		{"HIVE", "HDFS"},
		{"HIVE", "YARN"},
		{"HIVE", "ZOOKEEPER"},
		{"SPARK", "HDFS"},
		{"SPARK", "YARN"},
		{"SPARK", "ZOOKEEPER"},
		{"HIVE", "SPARK"},
		{"KAFKA", "ZOOKEEPER"},
		{"HBASE", "HDFS"},
		{"HBASE", "ZOOKEEPER"},
		{"FLINK", "HDFS"},
		{"FLINK", "YARN"},
		{"FLINK", "ZOOKEEPER"},
	}
	
	now := time.Now().UnixMilli()
	for _, dep := range defaultDeps {
		svcID, ok1 := serviceMap[dep.service]
		depID, ok2 := serviceMap[dep.dependsOn]
		if ok1 && ok2 {
			dependency := models.ServiceDependency{
				ServiceID:            svcID,
				DependsOnServiceID:   depID,
				DependsOnServiceName: dep.dependsOn,
				DependencyType:       "REQUIRED",
				CreatedTime:          now,
				UpdatedTime:          now,
			}
			s.db.Create(&dependency)
		}
	}
	
	return nil
}

func (s *ServiceService) GetAllServiceDependencies() (map[string]interface{}, error) {
	result := make(map[string]interface{})
	
	if s.db == nil {
		result["services"] = []interface{}{}
		result["links"] = []interface{}{}
		result["totalServices"] = 0
		result["totalLinks"] = 0
		return result, nil
	}
	
	var services []models.Service
	if err := s.db.Where("is_deleted = ?", false).Find(&services).Error; err != nil {
		result["services"] = []interface{}{}
		result["links"] = []interface{}{}
		result["totalServices"] = 0
		result["totalLinks"] = 0
		return result, err
	}
	
	var allDeps []models.ServiceDependency
	s.db.Find(&allDeps)
	
	serviceMap := make(map[uint]string)
	for _, svc := range services {
		serviceMap[svc.ID] = svc.ServiceName
	}
	
	links := make([]map[string]string, 0)
	for _, dep := range allDeps {
		if fromSvc, ok := serviceMap[dep.ServiceID]; ok {
			if toSvc, ok := serviceMap[dep.DependsOnServiceID]; ok {
				links = append(links, map[string]string{
					"source": fromSvc,
					"target": toSvc,
					"type":  dep.DependencyType,
				})
			}
		}
	}
	
	serviceInfos := make([]map[string]interface{}, 0)
	for _, svc := range services {
		serviceInfos = append(serviceInfos, map[string]interface{}{
			"serviceName": svc.ServiceName,
			"serviceType": svc.ServiceType,
			"version": svc.Version,
			"status": svc.Status,
		})
	}
	
	result["services"] = serviceInfos
	result["links"] = links
	result["totalServices"] = len(services)
	result["totalLinks"] = len(links)
	
	return result, nil
}

func (s *ServiceService) toServiceInfo(service models.Service) models.ServiceInfo {
	components := s.getDefaultComponents(service.ServiceName)
	
	info := models.ServiceInfo{
		Name:          service.ServiceName,
		Version:       service.Version,
		Status:        service.Status,
		ConfigVersion: service.ConfigVersion,
		Role:          service.ServiceType,
		Components:    components,
	}

	if service.LastRestartTime != nil {
		info.LastRestartTime = service.LastRestartTime
	}
	if service.LastOperationTime != nil {
		info.LastOperationTime = service.LastOperationTime
	}
	if service.LastOperation != "" {
		info.LastOperation = service.LastOperation
	}

	return info
}

func (s *ServiceService) getDefaultComponents(serviceName string) []string {
	switch strings.ToUpper(serviceName) {
	case "HDFS":
		return []string{"NameNode", "DataNode"}
	case "YARN":
		return []string{"ResourceManager", "NodeManager"}
	case "HIVE":
		return []string{"HiveServer2", "Metastore"}
	case "SPARK":
		return []string{"Master", "Worker"}
	case "KAFKA":
		return []string{"Broker"}
	case "HBASE":
		return []string{"HMaster", "RegionServer"}
	case "ZOOKEEPER":
		return []string{"Server"}
	case "FLINK":
		return []string{"JobManager", "TaskManager"}
	default:
		return []string{}
	}
}

func (s *ServiceService) getConfigFilesForService(serviceName string) []map[string]string {
	configFiles := []map[string]string{}
	now := time.Now().UnixMilli()

	switch strings.ToUpper(serviceName) {
	case "HDFS":
		configFiles = append(configFiles, map[string]string{
			"name": "core-site.xml", "version": "v3", "lastModified": fmt.Sprintf("%d", now-86400000), "size": "2048",
		})
		configFiles = append(configFiles, map[string]string{
			"name": "hdfs-site.xml", "version": "v2", "lastModified": fmt.Sprintf("%d", now-172800000), "size": "1536",
		})
	case "YARN":
		configFiles = append(configFiles, map[string]string{
			"name": "yarn-site.xml", "version": "v4", "lastModified": fmt.Sprintf("%d", now-43200000), "size": "1792",
		})
	case "KAFKA":
		configFiles = append(configFiles, map[string]string{
			"name": "server.properties", "version": "v2", "lastModified": fmt.Sprintf("%d", now-108000000), "size": "4096",
		})
	case "ZOOKEEPER":
		configFiles = append(configFiles, map[string]string{
			"name": "zoo.cfg", "version": "v1", "lastModified": fmt.Sprintf("%d", now-324000000), "size": "512",
		})
	default:
		configFiles = append(configFiles, map[string]string{
			"name": "config.ini", "version": "v1", "lastModified": fmt.Sprintf("%d", now), "size": "1024",
		})
	}

	return configFiles
}

func (s *ServiceService) getMockServices() []models.ServiceInfo {
	return []models.ServiceInfo{
		{Name: "HDFS", Version: "3.3.6", Status: "HEALTHY", ConfigVersion: "v24", Role: "Storage", Components: []string{"NameNode", "DataNode"}},
		{Name: "YARN", Version: "3.3.6", Status: "HEALTHY", ConfigVersion: "v12", Role: "Compute", Components: []string{"ResourceManager", "NodeManager"}},
		{Name: "HIVE", Version: "3.1.3", Status: "WARNING", ConfigVersion: "v8", Role: "Database", Components: []string{"HiveServer2", "Metastore"}},
		{Name: "SPARK", Version: "3.5.0", Status: "HEALTHY", ConfigVersion: "v3", Role: "Compute", Components: []string{"HistoryServer"}},
		{Name: "KAFKA", Version: "3.6.0", Status: "HEALTHY", ConfigVersion: "v15", Role: "Messaging", Components: []string{"Broker"}},
		{Name: "HBASE", Version: "2.5.5", Status: "HEALTHY", ConfigVersion: "v10", Role: "Database", Components: []string{"HMaster", "RegionServer"}},
		{Name: "ZOOKEEPER", Version: "3.8.3", Status: "HEALTHY", ConfigVersion: "v5", Role: "Coordination", Components: []string{"Server"}},
		{Name: "FLINK", Version: "1.17.1", Status: "STOPPED", ConfigVersion: "v1", Role: "Stream", Components: []string{"JobManager"}},
	}
}

func ptrInt64(v int64) *int64 {
	return &v
}