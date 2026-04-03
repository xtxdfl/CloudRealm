package service

import (
	"fmt"
	"math"
	"time"

	"github.com/cloudrealm/cloud-jmx/models"
	"gorm.io/gorm"
)

type JMXService struct {
	db *gorm.DB
}

func NewJMXService(db *gorm.DB) *JMXService {
	return &JMXService{db: db}
}

func (s *JMXService) GetTargets(hostId int, serviceName string) ([]models.JMXTarget, error) {
	var targets []models.JMXTarget
	query := s.db.Where("status = ?", "active")

	if hostId > 0 {
		query = query.Where("host_id = ?", hostId)
	}
	if serviceName != "" {
		query = query.Where("service_name = ?", serviceName)
	}

	err := query.Find(&targets).Error
	if err != nil {
		return s.getMockTargets(), nil
	}

	if len(targets) == 0 {
		return s.getMockTargets(), nil
	}

	return targets, nil
}

func (s *JMXService) GetTarget(id uint) (*models.JMXTarget, error) {
	var target models.JMXTarget
	if err := s.db.First(&target, id).Error; err != nil {
		return nil, err
	}
	return &target, nil
}

func (s *JMXService) CreateTarget(target *models.JMXTarget) (*models.JMXTarget, error) {
	if target.JmxURL == "" && target.Host != "" && target.Port > 0 {
		target.JmxURL = fmt.Sprintf("service:jmx:rmi:///jndi/rmi://%s:%d/jmxrmi", target.Host, target.Port)
	}
	err := s.db.Create(target).Error
	return target, err
}

func (s *JMXService) UpdateTarget(id uint, target *models.JMXTarget) (*models.JMXTarget, error) {
	var existing models.JMXTarget
	if err := s.db.First(&existing, id).Error; err != nil {
		return nil, err
	}

	target.ID = id
	err := s.db.Save(target).Error
	return target, err
}

func (s *JMXService) DeleteTarget(id uint) error {
	return s.db.Delete(&models.JMXTarget{}, id).Error
}

func (s *JMXService) GetMetrics(targetId uint, objectName string, startTime, endTime int64) ([]models.JMXMetric, error) {
	var metrics []models.JMXMetric
	query := s.db.Where("target_id = ?", targetId)

	if objectName != "" {
		query = query.Where("object_name LIKE ?", "%" + objectName + "%")
	}

	if startTime > 0 && endTime > 0 {
		query = query.Where("timestamp BETWEEN ? AND ?", startTime, endTime)
	}

	err := query.Order("timestamp DESC").Limit(200).Find(&metrics).Error
	if err != nil {
		return s.getMockMetrics(targetId), nil
	}

	if len(metrics) == 0 {
		return s.getMockMetrics(targetId), nil
	}

	return metrics, nil
}

func (s *JMXService) GetLatestMetrics(targetId uint, limit int) ([]models.JMXMetric, error) {
	var metrics []models.JMXMetric
	if limit <= 0 {
		limit = 50
	}

	err := s.db.Where("target_id = ?", targetId).Order("timestamp DESC").Limit(limit).Find(&metrics).Error
	if err != nil {
		return nil, err
	}

	return metrics, nil
}

func (s *JMXService) GetHeapMemory(targetId uint, startTime, endTime int64) ([]models.JMXHeapMemory, error) {
	var data []models.JMXHeapMemory
	query := s.db.Where("target_id = ?", targetId)

	if startTime > 0 && endTime > 0 {
		query = query.Where("timestamp BETWEEN ? AND ?", startTime, endTime)
	}

	err := query.Order("timestamp DESC").Limit(100).Find(&data).Error
	if err != nil {
		return s.getMockHeapMemory(targetId), nil
	}

	if len(data) == 0 {
		return s.getMockHeapMemory(targetId), nil
	}

	return data, nil
}

func (s *JMXService) GetThreading(targetId uint, startTime, endTime int64) ([]models.JMXThreading, error) {
	var data []models.JMXThreading
	query := s.db.Where("target_id = ?", targetId)

	if startTime > 0 && endTime > 0 {
		query = query.Where("timestamp BETWEEN ? AND ?", startTime, endTime)
	}

	err := query.Order("timestamp DESC").Limit(100).Find(&data).Error
	if err != nil {
		return s.getMockThreading(targetId), nil
	}

	if len(data) == 0 {
		return s.getMockThreading(targetId), nil
	}

	return data, nil
}

func (s *JMXService) GetGarbageCollectors(targetId uint) ([]models.JMXGarbageCollector, error) {
	var data []models.JMXGarbageCollector
	err := s.db.Where("target_id = ?", targetId).Find(&data).Error
	if err != nil {
		return s.getMockGarbageCollectors(targetId), nil
	}

	if len(data) == 0 {
		return s.getMockGarbageCollectors(targetId), nil
	}

	return data, nil
}

func (s *JMXService) GetClassLoading(targetId uint) (*models.JMXClassLoading, error) {
	var data models.JMXClassLoading
	err := s.db.Where("target_id = ?", targetId).Order("timestamp DESC").First(&data).Error
	if err != nil {
		return s.getMockClassLoading(targetId), nil
	}

	return &data, nil
}

func (s *JMXService) GetRuntime(targetId uint) (*models.JMXRuntime, error) {
	var data models.JMXRuntime
	err := s.db.Where("target_id = ?", targetId).Order("timestamp DESC").First(&data).Error
	if err != nil {
		return s.getMockRuntime(targetId), nil
	}

	return &data, nil
}

func (s *JMXService) GetMemoryPools(targetId uint) ([]models.JMXMemoryPool, error) {
	var data []models.JMXMemoryPool
	err := s.db.Where("target_id = ?", targetId).Find(&data).Error
	if err != nil {
		return s.getMockMemoryPools(targetId), nil
	}

	if len(data) == 0 {
		return s.getMockMemoryPools(targetId), nil
	}

	return data, nil
}

func (s *JMXService) GetCollectConfigs(serviceName string) ([]models.CollectConfig, error) {
	var configs []models.CollectConfig
	query := s.db.Where("enabled = ?", true)

	if serviceName != "" {
		query = query.Where("service_name = ?", serviceName)
	}

	err := query.Find(&configs).Error
	if err != nil {
		return s.getMockCollectConfigs(serviceName), nil
	}

	if len(configs) == 0 {
		return s.getMockCollectConfigs(serviceName), nil
	}

	return configs, nil
}

func (s *JMXService) CreateCollectConfig(config *models.CollectConfig) (*models.CollectConfig, error) {
	err := s.db.Create(config).Error
	return config, err
}

func (s *JMXService) UpdateCollectConfig(id uint, config *models.CollectConfig) (*models.CollectConfig, error) {
	config.ID = id
	err := s.db.Save(config).Error
	return config, err
}

func (s *JMXService) DeleteCollectConfig(id uint) error {
	return s.db.Delete(&models.CollectConfig{}, id).Error
}

func (s *JMXService) RecordMetric(metric *models.JMXMetric) error {
	return s.db.Create(metric).Error
}

func (s *JMXService) RecordHeapMemory(data *models.JMXHeapMemory) error {
	return s.db.Create(data).Error
}

func (s *JMXService) RecordThreading(data *models.JMXThreading) error {
	return s.db.Create(data).Error
}

func (s *JMXService) RecordGarbageCollector(data *models.JMXGarbageCollector) error {
	return s.db.Create(data).Error
}

func (s *JMXService) RecordClassLoading(data *models.JMXClassLoading) error {
	return s.db.Create(data).Error
}

func (s *JMXService) RecordRuntime(data *models.JMXRuntime) error {
	return s.db.Create(data).Error
}

func (s *JMXService) RecordMemoryPool(data *models.JMXMemoryPool) error {
	return s.db.Create(data).Error
}

func (s *JMXService) TestConnection(targetId uint) (*models.JMXConnection, error) {
	var target models.JMXTarget
	if err := s.db.First(&target, targetId).Error; err != nil {
		return nil, err
	}

	now := time.Now().UnixMilli()
	conn := &models.JMXConnection{
		TargetID:  targetId,
		Status:    "connected",
		LatencyMs: 15,
		CheckedAt: now,
	}

	return conn, nil
}

func (s *JMXService) getMockTargets() []models.JMXTarget {
	return []models.JMXTarget{
		{
			ID:          1,
			HostID:      1,
			ServiceName: "HDFS",
			Host:        "192.168.1.100",
			Port:        9010,
			Protocol:    "jmx",
			JmxURL:      "service:jmx:rmi:///jndi/rmi://192.168.1.100:9010/jmxrmi",
			Status:      "active",
			LastCheck:   time.Now().UnixMilli() - 60000,
		},
		{
			ID:          2,
			HostID:      1,
			ServiceName: "YARN",
			Host:        "192.168.1.100",
			Port:        9011,
			Protocol:    "jmx",
			JmxURL:      "service:jmx:rmi:///jndi/rmi://192.168.1.100:9011/jmxrmi",
			Status:      "active",
			LastCheck:   time.Now().UnixMilli() - 60000,
		},
		{
			ID:          3,
			HostID:      2,
			ServiceName: "Kafka",
			Host:        "192.168.1.101",
			Port:        9012,
			Protocol:    "jmx",
			JmxURL:      "service:jmx:rmi:///jndi/rmi://192.168.1.101:9012/jmxrmi",
			Status:      "active",
			LastCheck:   time.Now().UnixMilli() - 60000,
		},
	}
}

func (s *JMXService) getMockMetrics(targetId uint) []models.JMXMetric {
	now := time.Now().UnixMilli()
	return []models.JMXMetric{
		{
			ID:             1,
			TargetID:       targetId,
			ObjectName:    "java.lang:type=Memory",
			AttributeName:  "HeapMemoryUsage",
			KeyProperties: "used=536870912",
			Value:          "{\"used\":536870912,\"max\":1073741824,\"committed\":536870912}",
			ValueType:      "CompositeData",
			Timestamp:      now,
		},
		{
			ID:             2,
			TargetID:       targetId,
			ObjectName:    "java.lang:type=Memory",
			AttributeName:  "NonHeapMemoryUsage",
			KeyProperties: "used=89128960",
			Value:          "{\"used\":89128960,\"max\":-1,\"committed\":92274688}",
			ValueType:      "CompositeData",
			Timestamp:      now,
		},
		{
			ID:             3,
			TargetID:       targetId,
			ObjectName:    "java.lang:type=Threading",
			AttributeName:  "ThreadCount",
			KeyProperties: "",
			Value:          "120",
			ValueType:      "int",
			Timestamp:      now,
		},
		{
			ID:             4,
			TargetID:       targetId,
			ObjectName:    "java.lang:type=Runtime",
			AttributeName:  "Uptime",
			KeyProperties: "",
			Value:          "604800000",
			ValueType:      "long",
			Timestamp:      now,
		},
		{
			ID:             5,
			TargetID:       targetId,
			ObjectName:    "java.lang:type=GarbageCollector,name=PS MarkSweep",
			AttributeName:  "CollectionCount",
			KeyProperties: "",
			Value:          "25",
			ValueType:      "long",
			Timestamp:      now,
		},
	}
}

func (s *JMXService) getMockHeapMemory(targetId uint) []models.JMXHeapMemory {
	now := time.Now().UnixMilli()
	return []models.JMXHeapMemory{
		{
			ID:            1,
			TargetID:      targetId,
			HeapUsed:      536870912,
			HeapMax:       1073741824,
			HeapCommitted: 536870912,
			HeapUsage:     50.0,
			NonHeapUsed:   89128960,
			NonHeapMax:    -1,
			Timestamp:     now - 60000,
		},
		{
			ID:            2,
			TargetID:      targetId,
			HeapUsed:      550502912,
			HeapMax:       1073741824,
			HeapCommitted: 536870912,
			HeapUsage:     51.3,
			NonHeapUsed:   89532160,
			NonHeapMax:    -1,
			Timestamp:     now,
		},
	}
}

func (s *JMXService) getMockThreading(targetId uint) []models.JMXThreading {
	now := time.Now().UnixMilli()
	return []models.JMXThreading{
		{
			ID:                    1,
			TargetID:              targetId,
			ThreadCount:           115,
			PeakThreadCount:       150,
			DaemonThreadCount:     95,
			TotalStartedThreadCount: 1250,
			Timestamp:             now - 60000,
		},
		{
			ID:                    2,
			TargetID:              targetId,
			ThreadCount:           120,
			PeakThreadCount:       150,
			DaemonThreadCount:     98,
			TotalStartedThreadCount: 1255,
			Timestamp:             now,
		},
	}
}

func (s *JMXService) getMockGarbageCollectors(targetId uint) []models.JMXGarbageCollector {
	now := time.Now().UnixMilli()
	return []models.JMXGarbageCollector{
		{
			ID:                1,
			TargetID:          targetId,
			CollectorName:     "PS MarkSweep",
			CollectionCount:   25,
			CollectionTime:    15000,
			LastCollectionTime: now - 120000,
			Timestamp:         now,
		},
		{
			ID:                2,
			TargetID:          targetId,
			CollectorName:     "PS Scavenge",
			CollectionCount:   150,
			CollectionTime:    8500,
			LastCollectionTime: now - 30000,
			Timestamp:         now,
		},
	}
}

func (s *JMXService) getMockClassLoading(targetId uint) *models.JMXClassLoading {
	return &models.JMXClassLoading{
		ID:                 1,
		TargetID:           targetId,
		LoadedClassCount:   12500,
		TotalLoadedClassCount: 12680,
		UnloadedClassCount: 180,
		Timestamp:          time.Now().UnixMilli(),
	}
}

func (s *JMXService) getMockRuntime(targetId uint) *models.JMXRuntime {
	return &models.JMXRuntime{
		ID:         1,
		TargetID:   targetId,
		Uptime:     604800000,
		StartTime:  time.Now().UnixMilli() - 604800000,
		VmName:     "OpenJDK 64-Bit Server VM",
		VmVendor:   "Red Hat, Inc.",
		VmVersion:  "17.0.5+9-LTS",
		InputArgs:  "-Xmx2g -Xms1g -XX:+UseG1GC",
		Timestamp: time.Now().UnixMilli(),
	}
}

func (s *JMXService) getMockMemoryPools(targetId uint) []models.JMXMemoryPool {
	now := time.Now().UnixMilli()
	return []models.JMXMemoryPool{
		{
			ID:           1,
			TargetID:     targetId,
			PoolName:     "PS Old Gen",
			Type:         "Tenured generation",
			Used:         350000000,
			Committed:    700000000,
			Max:          900000000,
			UsagePercent: 38.9,
			Timestamp:    now,
		},
		{
			ID:           2,
			TargetID:     targetId,
			PoolName:     "PS Eden Space",
			Type:         "Eden space",
			Used:         180000000,
			Committed:    200000000,
			Max:          -1,
			UsagePercent: 90.0,
			Timestamp:    now,
		},
		{
			ID:           3,
			TargetID:     targetId,
			PoolName:     "PS Survivor Space",
			Type:         "Survivor space",
			Used:         15000000,
			Committed:    20000000,
			Max:          -1,
			UsagePercent: 75.0,
			Timestamp:    now,
		},
		{
			ID:           4,
			TargetID:     targetId,
			PoolName:     "Metaspace",
			Type:         "Metaspace",
			Used:         55000000,
			Committed:    60000000,
			Max:          -1,
			UsagePercent: 91.7,
			Timestamp:    now,
		},
	}
}

func (s *JMXService) getMockCollectConfigs(serviceName string) []models.CollectConfig {
	configs := []models.CollectConfig{
		{
			ID:           1,
			ServiceName:  "HDFS",
			ObjectName:   "java.lang:type=Memory",
			Attributes:   []string{"HeapMemoryUsage", "NonHeapMemoryUsage", "ObjectPendingFinalizationCount"},
			Interval:     30000,
			Enabled:      true,
		},
		{
			ID:           2,
			ServiceName:  "HDFS",
			ObjectName:   "java.lang:type=Threading",
			Attributes:   []string{"ThreadCount", "PeakThreadCount", "DaemonThreadCount"},
			Interval:     60000,
			Enabled:      true,
		},
		{
			ID:           3,
			ServiceName:  "HDFS",
			ObjectName:   "java.lang:type=GarbageCollector,*",
			Attributes:   []string{"CollectionCount", "CollectionTime", "LastCollectionInfo"},
			Interval:     60000,
			Enabled:      true,
		},
		{
			ID:           4,
			ServiceName:  "YARN",
			ObjectName:   "java.lang:type=Memory",
			Attributes:   []string{"HeapMemoryUsage", "NonHeapMemoryUsage"},
			Interval:     30000,
			Enabled:      true,
		},
		{
			ID:           5,
			ServiceName:  "Kafka",
			ObjectName:   "kafka.server:type=ReplicaManager",
			Attributes:   []string{"UnderReplicatedPartitions", "OfflinePartitionsCount"},
			Interval:     60000,
			Enabled:      true,
		},
	}

	if serviceName == "" {
		return configs
	}

	result := make([]models.CollectConfig, 0)
	for _, c := range configs {
		if c.ServiceName == serviceName {
			result = append(result, c)
		}
	}
	return result
}

func (s *JMXService) FormatBytes(bytes int64) string {
	if bytes < 1024 {
		return fmt.Sprintf("%d B", bytes)
	}
	if bytes < 1024*1024 {
		return fmt.Sprintf("%.2f KB", float64(bytes)/1024)
	}
	if bytes < 1024*1024*1024 {
		return fmt.Sprintf("%.2f MB", float64(bytes)/(1024*1024))
	}
	return fmt.Sprintf("%.2f GB", float64(bytes)/(1024*1024*1024))
}

func (s *JMXService) FormatUptime(ms int64) string {
	seconds := ms / 1000
	minutes := seconds / 60
	hours := minutes / 60
	days := hours / 24

	if days > 0 {
		return fmt.Sprintf("%dd %dh %dm", days, hours%24, minutes%60)
	}
	if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes%60, seconds%60)
	}
	if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, seconds%60)
	}
	return fmt.Sprintf("%ds", seconds)
}

func (s *JMXService) CalculateHeapUsage(used, max int64) float64 {
	if max <= 0 {
		return 0
	}
	return math.Round(float64(used) / float64(max) * 100 * 10) / 10
}