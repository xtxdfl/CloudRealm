package service

import (
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type HostService struct {
	db               *gorm.DB
	operationLogRepo *HostOperationLogRepository
}

func NewHostService(db *gorm.DB) *HostService {
	return &HostService{
		db:               db,
		operationLogRepo: NewHostOperationLogRepository(db),
	}
}

func (s *HostService) GetAllHosts() ([]models.HostInfo, error) {
	var hosts []models.Host
	if err := s.db.Where("1=1").Find(&hosts).Error; err != nil {
		return []models.HostInfo{}, nil
	}

	result := make([]models.HostInfo, 0, len(hosts))
	for _, h := range hosts {
		info := h.ToHostInfo()
		result = append(result, info)
	}

	return result, nil
}

func (s *HostService) GetHostByHostname(hostname string) (*models.HostInfo, error) {
	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil
		}
		return nil, err
	}
	info := host.ToHostInfo()
	return &info, nil
}

func (s *HostService) SearchHosts(search *models.HostSearch) ([]models.HostInfo, error) {
	var hosts []models.Host
	query := s.db.Model(&models.Host{})

	if search.HostName != "" {
		query = query.Where("host_name LIKE ?", "%"+search.HostName+"%")
	}
	if search.IPv4 != "" {
		query = query.Where("ipv4 LIKE ?", "%"+search.IPv4+"%")
	}
	if search.Status != "" {
		query = query.Where("discovery_status = ?", search.Status)
	}
	if search.AgentStatus != "" {
		query = query.Where("agent_status = ?", search.AgentStatus)
	}
	if search.RackInfo != "" {
		query = query.Where("rack_info = ?", search.RackInfo)
	}

	if err := query.Find(&hosts).Error; err != nil {
		return []models.HostInfo{}, nil
	}

	result := make([]models.HostInfo, 0, len(hosts))
	for _, h := range hosts {
		info := h.ToHostInfo()
		result = append(result, info)
	}

	return result, nil
}

func (s *HostService) GetHostStats() (*models.HostStats, error) {
	var total int64
	var online int64
	var offline int64
	var unhealthy int64

	s.db.Model(&models.Host{}).Count(&total)
	s.db.Model(&models.Host{}).Where("agent_status = ?", "ONLINE").Count(&online)
	s.db.Model(&models.Host{}).Where("agent_status = ?", "OFFLINE").Count(&offline)
	s.db.Model(&models.Host{}).Where("agent_status = ?", "UNHEALTHY").Count(&unhealthy)

	return &models.HostStats{
		Total:     total,
		Online:    online,
		Offline:   offline,
		Unhealthy: unhealthy,
	}, nil
}

func (s *HostService) AddHost(info *models.HostInfo) (*models.Host, error) {
	var existing models.Host
	err := s.db.Where("host_name = ? OR ipv4 = ?", info.Hostname, info.IP).First(&existing).Error
	if err == nil {
		return nil, errors.New("host already exists")
	}

	now := time.Now().UnixMilli()
	discoveryStatus := info.Status
	if discoveryStatus == "" {
		discoveryStatus = "UNKNOWN"
	}
	host := models.Host{
		HostName:           info.Hostname,
		IPv4:               info.IP,
		PublicHostName:     info.PublicHostName,
		DiscoveryStatus:   discoveryStatus,
		AgentStatus:        "OFFLINE",
		CPUCount:           info.Cores,
		CPUInfo:            info.CPUInfo,
		TotalMem:           info.TotalMemory,
		UsedMem:            info.UsedMemory,
		AvailableMem:       info.AvailableMemory,
		MemoryUsage:        info.MemoryUsage,
		TotalDisk:          info.TotalDisk,
		UsedDisk:           info.UsedDisk,
		AvailableDisk:      info.AvailableDisk,
		DiskUsage:          info.DiskUsage,
		OSType:             info.OSType,
		OSArch:             info.OSArch,
		OSInfo:             info.OSInfo,
		RackInfo:           info.RackInfo,
		LastRegistrationTime: now,
		LastHeartbeatTime:  now,
		StorageSize:        info.StorageSize,
		AgentVersion:       info.AgentVersion,
		SSHPrivateKey:      info.SSHPrivateKey,
		SSHPublicKey:       info.SSHPublicKey,
	}

	if err := s.db.Create(&host).Error; err != nil {
		return nil, err
	}

	return &host, nil
}

func (s *HostService) BatchImportHosts(hostsInfo []models.HostInfo, operator string) ([]models.Host, error) {
	results := make([]models.Host, 0)
	now := time.Now().UnixMilli()

	for _, info := range hostsInfo {
		var existing models.Host
		err := s.db.Where("host_name = ? OR ipv4 = ?", info.Hostname, info.IP).First(&existing).Error
		if err == nil {
			continue
		}

		host := models.Host{
			HostName:           info.Hostname,
			IPv4:               info.IP,
			PublicHostName:     info.PublicHostName,
			DiscoveryStatus:    "UNKNOWN",
			AgentStatus:        "OFFLINE",
			CPUCount:           info.Cores,
			TotalMem:           info.TotalMemory,
			TotalDisk:          info.TotalDisk,
			OSType:             info.OSType,
			RackInfo:           info.RackInfo,
			LastRegistrationTime: now,
			LastHeartbeatTime:  now,
		}

		if err := s.db.Create(&host).Error; err != nil {
			continue
		}
		results = append(results, host)
	}

	return results, nil
}

func (s *HostService) StartHost(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	startTime := time.Now().UnixMilli()

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found"
		return result, nil
	}

	statusBefore := host.DiscoveryStatus
	host.DiscoveryStatus = "RUNNING"
	host.LastOperationTime = startTime
	s.db.Save(&host)

	time.Sleep(300 * time.Millisecond)

	host.DiscoveryStatus = "RUNNING"
	host.AgentStatus = "ONLINE"
	host.LastHeartbeatTime = startTime
	s.db.Save(&host)

	duration := time.Now().UnixMilli() - startTime
	s.operationLogRepo.Save(&models.HostOperationLog{
		HostID:          host.HostID,
		HostName:        hostname,
		HostIP:          host.IPv4,
		Operation:       "START",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "HEALTHY",
		Operator:        "admin",
		DurationMs:      duration,
		OperationTime:   startTime,
		CreatedTime:     startTime,
	})

	result["success"] = true
	result["message"] = "Host " + hostname + " started successfully"
	result["jobId"] = fmt.Sprintf("job_%d", startTime)

	return result, nil
}

func (s *HostService) StopHost(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	startTime := time.Now().UnixMilli()

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found"
		return result, nil
	}

	statusBefore := host.DiscoveryStatus
	host.DiscoveryStatus = "STOPPING"
	host.LastOperationTime = startTime
	s.db.Save(&host)

	time.Sleep(300 * time.Millisecond)

	host.DiscoveryStatus = "DISCONNECT"
	host.AgentStatus = "OFFLINE"
	s.db.Save(&host)

	duration := time.Now().UnixMilli() - startTime
	s.operationLogRepo.Save(&models.HostOperationLog{
		HostID:          host.HostID,
		HostName:        hostname,
		HostIP:          host.IPv4,
		Operation:       "STOP",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "STOPPED",
		Operator:        "admin",
		DurationMs:      duration,
		OperationTime:   startTime,
		CreatedTime:     startTime,
	})

	result["success"] = true
	result["message"] = "Host " + hostname + " stopped successfully"
	result["jobId"] = fmt.Sprintf("job_%d", startTime)

	return result, nil
}

func (s *HostService) RestartHost(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	startTime := time.Now().UnixMilli()

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found"
		return result, nil
	}

	statusBefore := host.DiscoveryStatus

	host.DiscoveryStatus = "STOPPING"
	host.LastOperationTime = startTime
	s.db.Save(&host)
	time.Sleep(200 * time.Millisecond)

	host.DiscoveryStatus = "STOPPED"
	s.db.Save(&host)
	time.Sleep(200 * time.Millisecond)

	host.DiscoveryStatus = "STARTING"
	s.db.Save(&host)
	time.Sleep(300 * time.Millisecond)

	host.DiscoveryStatus = "HEALTHY"
	host.AgentStatus = "ONLINE"
	host.LastHeartbeatTime = startTime
	s.db.Save(&host)

	duration := time.Now().UnixMilli() - startTime
	s.operationLogRepo.Save(&models.HostOperationLog{
		HostID:          host.HostID,
		HostName:        hostname,
		HostIP:          host.IPv4,
		Operation:       "RESTART",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "HEALTHY",
		Operator:        "admin",
		DurationMs:      duration,
		OperationTime:   startTime,
		CreatedTime:     startTime,
	})

	result["success"] = true
	result["message"] = "Host " + hostname + " restart initiated"
	result["jobId"] = fmt.Sprintf("job_%d", startTime)

	return result, nil
}

func (s *HostService) EnterMaintenance(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	startTime := time.Now().UnixMilli()

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found"
		return result, nil
	}

	host.DiscoveryStatus = "MAINTENANCE"
	host.LastOperationTime = startTime
	s.db.Save(&host)

	s.operationLogRepo.Save(&models.HostOperationLog{
		HostID:          host.HostID,
		HostName:        hostname,
		HostIP:          host.IPv4,
		Operation:       "ENTER_MAINTENANCE",
		OperationStatus: "SUCCESS",
		StatusBefore:    "HEALTHY",
		StatusAfter:     "MAINTENANCE",
		Operator:        "admin",
		DurationMs:      0,
		OperationTime:   startTime,
		CreatedTime:     startTime,
	})

	result["success"] = true
	result["message"] = "Host " + hostname + " entered maintenance mode"

	return result, nil
}

func (s *HostService) ExitMaintenance(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	startTime := time.Now().UnixMilli()

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found"
		return result, nil
	}

	host.DiscoveryStatus = "HEALTHY"
	host.LastOperationTime = startTime
	s.db.Save(&host)

	s.operationLogRepo.Save(&models.HostOperationLog{
		HostID:          host.HostID,
		HostName:        hostname,
		HostIP:          host.IPv4,
		Operation:       "EXIT_MAINTENANCE",
		OperationStatus: "SUCCESS",
		StatusBefore:    "MAINTENANCE",
		StatusAfter:     "HEALTHY",
		Operator:        "admin",
		DurationMs:      0,
		OperationTime:   startTime,
		CreatedTime:     startTime,
	})

	result["success"] = true
	result["message"] = "Host " + hostname + " exited maintenance mode"

	return result, nil
}

func (s *HostService) OfflineHost(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	startTime := time.Now().UnixMilli()

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found"
		return result, nil
	}

	statusBefore := host.DiscoveryStatus
	host.DiscoveryStatus = "OFFLINE"
	host.AgentStatus = "OFFLINE"
	host.LastOperationTime = startTime
	s.db.Save(&host)

	s.operationLogRepo.Save(&models.HostOperationLog{
		HostID:          host.HostID,
		HostName:        hostname,
		HostIP:          host.IPv4,
		Operation:       "OFFLINE",
		OperationStatus: "SUCCESS",
		StatusBefore:    statusBefore,
		StatusAfter:     "OFFLINE",
		Operator:        "admin",
		DurationMs:      0,
		OperationTime:   startTime,
		CreatedTime:     startTime,
	})

	result["success"] = true
	result["message"] = "Host " + hostname + " set to offline"

	return result, nil
}

func (s *HostService) DeleteHost(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	
	log.Printf("[DeleteHost] Attempting to delete host: %s", hostname)

	var host models.Host
	
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		log.Printf("[DeleteHost] Query by host_name failed: %v", err)
	}
	
	if host.ID == 0 {
		err = s.db.Where("ipv4 = ?", hostname).First(&host).Error
		if err != nil {
			log.Printf("[DeleteHost] Query by ipv4 failed: %v", err)
		}
	}
	
	if host.ID == 0 {
		err = s.db.Where("host_name LIKE ?", "%"+hostname+"%").First(&host).Error
		if err != nil {
			log.Printf("[DeleteHost] Query by LIKE failed: %v", err)
		}
	}
	
	if host.ID == 0 {
		log.Printf("[DeleteHost] Host still not found after all attempts: %s", hostname)
		result["success"] = false
		result["message"] = "Host not found: " + hostname
		return result, nil
	}
	
	log.Printf("[DeleteHost] Found host: ID=%d, HostName=%s, IPv4=%s", host.ID, host.HostName, host.IPv4)
	
	if err := s.db.Delete(&host).Error; err != nil {
		log.Printf("[DeleteHost] Delete error: %v", err)
		result["success"] = false
		result["message"] = "Delete failed: " + err.Error()
		return result, nil
	}
	
	log.Printf("[DeleteHost] Successfully deleted host: %s", hostname)
	result["success"] = true
	result["message"] = "Host " + hostname + " deleted successfully"

	return result, nil
}

func (s *HostService) DeleteHostById(hostId uint) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var host models.Host
	err := s.db.First(&host, hostId).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Host not found by ID"
		return result, nil
	}
	
	err = s.db.Delete(&host).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Delete failed: " + err.Error()
		return result, nil
	}
	
	result["success"] = true
	result["message"] = "Host deleted successfully"
	result["hostId"] = hostId

	return result, nil
}

func (s *HostService) BatchDeleteHosts(hostIds []uint) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	err := s.db.Delete(&models.Host{}, hostIds).Error
	if err != nil {
		result["success"] = false
		result["message"] = "Batch delete failed: " + err.Error()
		return result, nil
	}

	result["success"] = true
	result["message"] = "Batch delete completed"
	result["count"] = len(hostIds)
	result["hostIds"] = hostIds

	return result, nil
}

func (s *HostService) BatchStart(hostnames []string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	now := time.Now().UnixMilli()

	for _, hostname := range hostnames {
		var host models.Host
		if err := s.db.Where("host_name = ?", hostname).First(&host).Error; err == nil {
			host.DiscoveryStatus = "STARTING"
			host.LastOperationTime = now
			s.db.Save(&host)

			go func(h string) {
				time.Sleep(500 * time.Millisecond)
				s.db.Model(&models.Host{}).Where("host_name = ?", h).Updates(map[string]interface{}{
					"discovery_status": "HEALTHY",
					"agent_status":     "ONLINE",
				})
			}(hostname)
		}
	}

	result["success"] = true
	result["message"] = "Batch start initiated"
	result["hosts"] = hostnames
	result["timestamp"] = now

	return result, nil
}

func (s *HostService) BatchStop(hostnames []string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	now := time.Now().UnixMilli()

	for _, hostname := range hostnames {
		var host models.Host
		if err := s.db.Where("host_name = ?", hostname).First(&host).Error; err == nil {
			host.DiscoveryStatus = "STOPPING"
			host.LastOperationTime = now
			s.db.Save(&host)

			go func(h string) {
				time.Sleep(300 * time.Millisecond)
				s.db.Model(&models.Host{}).Where("host_name = ?", h).Updates(map[string]interface{}{
					"discovery_status": "STOPPED",
					"agent_status":     "OFFLINE",
				})
			}(hostname)
		}
	}

	result["success"] = true
	result["message"] = "Batch stop initiated"
	result["hosts"] = hostnames
	result["timestamp"] = now

	return result, nil
}

func (s *HostService) BatchRestart(hostnames []string) (map[string]interface{}, error) {
	result := make(map[string]interface{})
	now := time.Now().UnixMilli()

	for _, hostname := range hostnames {
		s.db.Model(&models.Host{}).Where("host_name = ?", hostname).Updates(map[string]interface{}{
			"status":            "STOPPING",
			"last_operation_time": now,
		})

		go func(h string) {
			time.Sleep(300 * time.Millisecond)
			s.db.Model(&models.Host{}).Where("host_name = ?", h).Updates(map[string]interface{}{
				"status": "STOPPED",
			})
			time.Sleep(300 * time.Millisecond)
			s.db.Model(&models.Host{}).Where("host_name = ?", h).Updates(map[string]interface{}{
				"status":        "STARTING",
			})
			time.Sleep(500 * time.Millisecond)
			s.db.Model(&models.Host{}).Where("host_name = ?", h).Updates(map[string]interface{}{
				"status":        "HEALTHY",
				"agent_status": "ONLINE",
			})
		}(hostname)
	}

	result["success"] = true
	result["message"] = "Batch restart initiated"
	result["hosts"] = hostnames
	result["timestamp"] = now

	return result, nil
}

func (s *HostService) GetHostDetail(hostname string) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var host models.Host
	err := s.db.Where("host_name = ?", hostname).First(&host).Error
	if err != nil {
		result["error"] = "Host not found"
		return result, nil
	}

	info := host.ToHostInfo()
	result["host"] = info

	logs, _ := s.operationLogRepo.FindByHostName(hostname, 10)
	result["recentOperations"] = logs

	return result, nil
}

func (s *HostService) GetOperationLogs(hostId *uint, hostName string, limit int) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var logs []models.HostOperationLog
	var err error

	if hostId != nil {
		logs, err = s.operationLogRepo.FindByHostId(*hostId, limit)
	} else if hostName != "" {
		logs, err = s.operationLogRepo.FindByHostName(hostName, limit)
	} else {
		logs, err = s.operationLogRepo.FindAll(limit)
	}

	if err != nil {
		result["success"] = false
		result["error"] = err.Error()
		return result, nil
	}

	result["success"] = true
	result["count"] = len(logs)
	result["operations"] = logs

	return result, nil
}

func (s *HostService) ProcessAgentHeartbeat(agentId string, status string, cpuUsage float64, memoryUsed int64, memoryTotal int64, diskUsed int64, diskTotal int64) error {
	var host models.Host
	err := s.db.Where("host_name = ? OR ipv4 = ?", agentId, agentId).First(&host).Error
	if err != nil {
		return err
	}
	
	now := time.Now().UnixMilli()
	host.DiscoveryStatus = status
	host.AgentStatus = "ONLINE"
	host.LastHeartbeatTime = now
	
	if cpuUsage > 0 {
		host.CPUUsage = cpuUsage
	}
	if memoryTotal > 0 {
		host.TotalMem = memoryTotal
		host.AvailableMem = memoryTotal - memoryUsed
		host.UsedMem = memoryUsed
	}
	if diskTotal > 0 {
		host.TotalDisk = diskTotal
		host.AvailableDisk = diskTotal - diskUsed
		host.UsedDisk = diskUsed
	}
	
	return s.db.Save(&host).Error
}

func (s *HostService) getMockHosts() []models.HostInfo {
	return []models.HostInfo{
		{
			Hostname:     "master-01",
			IP:           "192.168.1.101",
			Status:       "HEALTHY",
			AgentStatus:  "ONLINE",
			Cores:        8,
			CPUInfo:      "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
			CPUUsage:     35.5,
			TotalMemory:  32768,
			UsedMemory:   12288,
			MemoryUsage:  37.5,
			TotalDisk:    1024000,
			UsedDisk:     512000,
			DiskUsage:    50.0,
			OSType:       "Linux",
			OSArch:       "x86_64",
			RackInfo:     "/rack-a",
			AgentVersion: "1.0.0",
		},
		{
			Hostname:     "worker-01",
			IP:           "192.168.1.102",
			Status:       "HEALTHY",
			AgentStatus:  "ONLINE",
			Cores:        16,
			CPUInfo:      "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
			CPUUsage:     62.3,
			TotalMemory:  65536,
			UsedMemory:   32768,
			MemoryUsage:  50.0,
			TotalDisk:    2048000,
			UsedDisk:     1024000,
			DiskUsage:    50.0,
			OSType:       "Linux",
			OSArch:       "x86_64",
			RackInfo:     "/rack-b",
			AgentVersion: "1.0.0",
		},
		{
			Hostname:     "worker-02",
			IP:           "192.168.1.103",
			Status:       "HEALTHY",
			AgentStatus:  "ONLINE",
			Cores:        16,
			CPUInfo:      "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
			CPUUsage:     45.8,
			TotalMemory:  65536,
			UsedMemory:   24576,
			MemoryUsage:  37.5,
			TotalDisk:    2048000,
			UsedDisk:     614400,
			DiskUsage:    30.0,
			OSType:       "Linux",
			OSArch:       "x86_64",
			RackInfo:     "/rack-b",
			AgentVersion: "1.0.0",
		},
		{
			Hostname:     "worker-03",
			IP:           "192.168.1.104",
			Status:       "WARNING",
			AgentStatus:  "UNHEALTHY",
			Cores:        16,
			CPUInfo:      "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
			CPUUsage:     85.2,
			TotalMemory:  65536,
			UsedMemory:   57344,
			MemoryUsage:  87.5,
			TotalDisk:    2048000,
			UsedDisk:     1843200,
			DiskUsage:    90.0,
			OSType:       "Linux",
			OSArch:       "x86_64",
			RackInfo:     "/rack-c",
			AgentVersion: "1.0.0",
		},
		{
			Hostname:     "slave-01",
			IP:           "192.168.1.105",
			Status:       "STOPPED",
			AgentStatus:  "OFFLINE",
			Cores:        8,
			CPUInfo:      "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
			CPUUsage:     0.0,
			TotalMemory:  16384,
			UsedMemory:   0,
			MemoryUsage:  0.0,
			TotalDisk:    512000,
			UsedDisk:     0,
			DiskUsage:    0.0,
			OSType:       "Linux",
			OSArch:       "x86_64",
			RackInfo:     "/rack-a",
			AgentVersion: "1.0.0",
		},
		{
			Hostname:     "slave-02",
			IP:           "192.168.1.106",
			Status:       "HEALTHY",
			AgentStatus:  "ONLINE",
			Cores:        8,
			CPUInfo:      "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
			CPUUsage:     28.4,
			TotalMemory:  16384,
			UsedMemory:   4096,
			MemoryUsage:  25.0,
			TotalDisk:    512000,
			UsedDisk:     153600,
			DiskUsage:    30.0,
			OSType:       "Linux",
			OSArch:       "x86_64",
			RackInfo:     "/rack-a",
			AgentVersion: "1.0.0",
		},
	}
}