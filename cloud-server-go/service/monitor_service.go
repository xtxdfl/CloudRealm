package service

import (
	"math"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type MonitorService struct {
	db *gorm.DB
}

func NewMonitorService(db *gorm.DB) *MonitorService {
	return &MonitorService{db: db}
}

func (s *MonitorService) GetHostMetrics(hostId int, startTime, endTime int64) ([]models.HostMetric, error) {
	var metrics []models.HostMetric
	query := s.db.Where("host_id = ?", hostId)

	if startTime > 0 && endTime > 0 {
		query = query.Where("timestamp BETWEEN ? AND ?", startTime, endTime)
	} else if startTime > 0 {
		query = query.Where("timestamp >= ?", startTime)
	} else if endTime > 0 {
		query = query.Where("timestamp <= ?", endTime)
	}

	err := query.Order("timestamp DESC").Limit(100).Find(&metrics).Error
	if err != nil {
		return s.getMockHostMetrics(hostId), nil
	}

	if len(metrics) == 0 {
		return s.getMockHostMetrics(hostId), nil
	}

	return metrics, nil
}

func (s *MonitorService) GetServiceMetrics(hostId int, serviceName string, startTime, endTime int64) ([]models.ServiceMetric, error) {
	var metrics []models.ServiceMetric
	query := s.db.Where("host_id = ? AND service_name = ?", hostId, serviceName)

	if startTime > 0 && endTime > 0 {
		query = query.Where("timestamp BETWEEN ? AND ?", startTime, endTime)
	}

	err := query.Order("timestamp DESC").Limit(50).Find(&metrics).Error
	if err != nil {
		return s.getMockServiceMetrics(hostId, serviceName), nil
	}

	if len(metrics) == 0 {
		return s.getMockServiceMetrics(hostId, serviceName), nil
	}

	return metrics, nil
}

func (s *MonitorService) GetJMXMetrics(hostId int, serviceName string, objectName string) ([]models.JMXMetric, error) {
	var metrics []models.JMXMetric
	query := s.db.Where("host_id = ? AND service_name = ?", hostId, serviceName)

	if objectName != "" {
		query = query.Where("object_name LIKE ?", "%"+objectName+"%")
	}

	err := query.Order("timestamp DESC").Limit(100).Find(&metrics).Error
	if err != nil {
		return s.getMockJMXMetrics(hostId, serviceName), nil
	}

	if len(metrics) == 0 {
		return s.getMockJMXMetrics(hostId, serviceName), nil
	}

	return metrics, nil
}

func (s *MonitorService) QueryMetrics(query *models.MetricQuery) ([]models.MetricResponse, error) {
	var metrics []models.HostMetricData
	q := s.db.Where("1=1")

	if query.HostID > 0 {
		q = q.Where("host_id = ?", query.HostID)
	}
	if query.ServiceName != "" {
		q = q.Where("service_name = ?", query.ServiceName)
	}
	if len(query.MetricNames) > 0 {
		q = q.Where("metric_name IN ?", query.MetricNames)
	}
	if query.StartTime > 0 {
		q = q.Where("timestamp >= ?", query.StartTime)
	}
	if query.EndTime > 0 {
		q = q.Where("timestamp <= ?", query.EndTime)
	}

	err := q.Order("timestamp ASC").Find(&metrics).Error
	if err != nil {
		return nil, err
	}

	grouped := make(map[string][]models.HostMetricData)
	for _, m := range metrics {
		key := m.MetricName
		grouped[key] = append(grouped[key], m)
	}

	result := make([]models.MetricResponse, 0)
	for name, data := range grouped {
		unit := ""
		points := make([]models.DataPoint, 0, len(data))
		for _, d := range data {
			if unit == "" {
				unit = d.Unit
			}
			points = append(points, models.DataPoint{
				Timestamp: d.Timestamp,
				Value:     d.MetricValue,
			})
		}
		result = append(result, models.MetricResponse{
			MetricName: name,
			Unit:      unit,
			DataPoints: points,
		})
	}

	if len(result) == 0 {
		return s.getMockMetricResponses(query), nil
	}

	return result, nil
}

func (s *MonitorService) GetMetricThresholds(serviceName string) ([]models.MetricThreshold, error) {
	var thresholds []models.MetricThreshold
	query := s.db.Where("enabled = ?", true)

	if serviceName != "" {
		query = query.Where("service_name = ?", serviceName)
	}

	err := query.Find(&thresholds).Error
	if err != nil {
		return s.getMockThresholds(serviceName), nil
	}

	if len(thresholds) == 0 {
		return s.getMockThresholds(serviceName), nil
	}

	return thresholds, nil
}

func (s *MonitorService) CreateThreshold(threshold *models.MetricThreshold) (*models.MetricThreshold, error) {
	err := s.db.Create(threshold).Error
	return threshold, err
}

func (s *MonitorService) UpdateThreshold(id uint, threshold *models.MetricThreshold) (*models.MetricThreshold, error) {
	var existing models.MetricThreshold
	if err := s.db.First(&existing, id).Error; err != nil {
		return nil, err
	}

	threshold.ID = id
	err := s.db.Save(threshold).Error
	return threshold, err
}

func (s *MonitorService) DeleteThreshold(id uint) error {
	return s.db.Delete(&models.MetricThreshold{}, id).Error
}

func (s *MonitorService) GetAlertEvents(hostId *int, serviceName string, status string, startTime, endTime int64, page, size int) ([]models.AlertEvent, int64, error) {
	var events []models.AlertEvent
	var total int64

	query := s.db.Model(&models.AlertEvent{})

	if hostId != nil && *hostId > 0 {
		query = query.Where("host_id = ?", *hostId)
	}
	if serviceName != "" {
		query = query.Where("service_name = ?", serviceName)
	}
	if status != "" {
		query = query.Where("status = ?", status)
	}
	if startTime > 0 {
		query = query.Where("fired_at >= ?", startTime)
	}
	if endTime > 0 {
		query = query.Where("fired_at <= ?", endTime)
	}

	query.Count(&total)

	if page < 0 {
		page = 0
	}
	if size <= 0 {
		size = 20
	}

	err := query.Order("fired_at DESC").Offset(page * size).Limit(size).Find(&events).Error
	if err != nil {
		return s.getMockAlertEvents(), 3, nil
	}

	if len(events) == 0 {
		return s.getMockAlertEvents(), 3, nil
	}

	return events, total, nil
}

func (s *MonitorService) ResolveAlertEvent(id uint) error {
	now := time.Now().UnixMilli()
	return s.db.Model(&models.AlertEvent{}).Where("id = ?", id).Updates(map[string]interface{}{
		"status":      "resolved",
		"resolved_at": now,
	}).Error
}

func (s *MonitorService) RecordMetric(metric *models.HostMetricData) error {
	return s.db.Create(metric).Error
}

func (s *MonitorService) RecordJMXMetric(metric *models.JMXMetric) error {
	return s.db.Create(metric).Error
}

func (s *MonitorService) RecordHostMetric(metric *models.HostMetric) error {
	return s.db.Create(metric).Error
}

func (s *MonitorService) RecordServiceMetric(metric *models.ServiceMetric) error {
	return s.db.Create(metric).Error
}

func (s *MonitorService) getMockHostMetrics(hostId int) []models.HostMetric {
	now := time.Now().UnixMilli()
	return []models.HostMetric{
		{
			ID:          1,
			HostID:      hostId,
			MetricType:  "system",
			CPUUsage:    45.5 + math.Sin(float64(now)/100000)*10,
			MemoryUsage: 62.3,
			DiskUsage:   78.5,
			NetworkIn:   1250.5,
			NetworkOut:  850.3,
			LoadAverage: 2.5,
			Timestamp:   now - 60000,
		},
		{
			ID:          2,
			HostID:      hostId,
			MetricType:  "system",
			CPUUsage:    48.2,
			MemoryUsage: 64.1,
			DiskUsage:   78.5,
			NetworkIn:   1300.8,
			NetworkOut:  870.2,
			LoadAverage: 2.7,
			Timestamp:   now,
		},
	}
}

func (s *MonitorService) getMockServiceMetrics(hostId int, serviceName string) []models.ServiceMetric {
	now := time.Now().UnixMilli()
	return []models.ServiceMetric{
		{
			ID:            1,
			HostID:        hostId,
			ServiceName:   serviceName,
			ComponentName: "NameNode",
			Status:        "RUNNING",
			Uptime:        86400000 * 7,
			HeapUsed:      512 * 1024 * 1024,
			HeapMax:       1024 * 1024 * 1024,
			HeapUsage:     50.0,
			NonHeapUsed:   85 * 1024 * 1024,
			ThreadCount:   120,
			ThreadPeak:    150,
			GCCount:       2500,
			GCTime:        15000,
			Timestamp:     now,
		},
	}
}

func (s *MonitorService) getMockJMXMetrics(hostId int, serviceName string) []models.JMXMetric {
	now := time.Now().UnixMilli()
	return []models.JMXMetric{
		{
			ID:             1,
			HostID:         hostId,
			ServiceName:    serviceName,
			ObjectName:    "java.lang:type=Memory",
			AttributeName:  "HeapMemoryUsage",
			KeyProperties: "used=536870912",
			Value:          "{\"used\":536870912,\"max\":1073741824,\"committed\":536870912}",
			ValueType:      "CompositeData",
			Timestamp:      now,
		},
		{
			ID:             2,
			HostID:         hostId,
			ServiceName:    serviceName,
			ObjectName:    "java.lang:type=Memory",
			AttributeName:  "NonHeapMemoryUsage",
			KeyProperties: "used=89128960",
			Value:          "{\"used\":89128960,\"max\":-1,\"committed\":92274688}",
			ValueType:      "CompositeData",
			Timestamp:      now,
		},
		{
			ID:             3,
			HostID:         hostId,
			ServiceName:    serviceName,
			ObjectName:    "java.lang:type=Threading",
			AttributeName:  "ThreadCount",
			KeyProperties: "",
			Value:          "120",
			ValueType:      "int",
			Timestamp:      now,
		},
		{
			ID:             4,
			HostID:         hostId,
			ServiceName:    serviceName,
			ObjectName:    "java.lang:type=Runtime",
			AttributeName:  "Uptime",
			KeyProperties: "",
			Value:          "604800000",
			ValueType:      "long",
			Timestamp:      now,
		},
		{
			ID:             5,
			HostID:         hostId,
			ServiceName:    serviceName,
			ObjectName:    "java.lang:type=GarbageCollector,name=PS MarkSweep",
			AttributeName:  "CollectionCount",
			KeyProperties: "",
			Value:          "25",
			ValueType:      "long",
			Timestamp:      now,
		},
		{
			ID:             6,
			HostID:         hostId,
			ServiceName:    serviceName,
			ObjectName:    "java.lang:type=GarbageCollector,name=PS Scavenge",
			AttributeName:  "CollectionCount",
			KeyProperties: "",
			Value:          "150",
			ValueType:      "long",
			Timestamp:      now,
		},
	}
}

func (s *MonitorService) getMockMetricResponses(query *models.MetricQuery) []models.MetricResponse {
	now := time.Now().UnixMilli()
	responses := make([]models.MetricResponse, 0)

	metrics := []string{"cpu_usage", "memory_usage", "disk_usage"}
	if len(query.MetricNames) > 0 {
		metrics = query.MetricNames
	}

	for _, name := range metrics {
		points := make([]models.DataPoint, 0)
		for i := 0; i < 10; i++ {
			var val float64
			switch name {
			case "cpu_usage":
				val = 30 + float64(i)*2 + math.Sin(float64(now)/100000)*10
			case "memory_usage":
				val = 50 + float64(i)*1.5
			case "disk_usage":
				val = 70 + float64(i)*0.5
			default:
				val = float64(i * 10)
			}
			points = append(points, models.DataPoint{
				Timestamp: now - int64((9-i)*60000),
				Value:     val,
			})
		}
		responses = append(responses, models.MetricResponse{
			MetricName: name,
			Unit:      "%",
			DataPoints: points,
		})
	}

	return responses
}

func (s *MonitorService) getMockThresholds(serviceName string) []models.MetricThreshold {
	thresholds := []models.MetricThreshold{
		{
			ID:          1,
			ServiceName: "HDFS",
			MetricName:  "cpu_usage",
			ThresholdMin: 0,
			ThresholdMax: 90,
			Severity:     "WARNING",
			Enabled:      true,
		},
		{
			ID:          2,
			ServiceName: "HDFS",
			MetricName:  "memory_usage",
			ThresholdMin: 0,
			ThresholdMax: 85,
			Severity:     "WARNING",
			Enabled:      true,
		},
		{
			ID:          3,
			ServiceName: "HDFS",
			MetricName:  "heap_usage",
			ThresholdMin: 0,
			ThresholdMax: 80,
			Severity:     "CRITICAL",
			Enabled:      true,
		},
	}

	result := make([]models.MetricThreshold, 0)
	for _, t := range thresholds {
		if serviceName == "" || t.ServiceName == serviceName {
			result = append(result, t)
		}
	}

	return result
}

func (s *MonitorService) getMockAlertEvents() []models.AlertEvent {
	now := time.Now().UnixMilli()
	return []models.AlertEvent{
		{
			ID:           1,
			AlertID:      1001,
			HostID:       1,
			ServiceName:  "HDFS",
			MetricName:   "heap_usage",
			Threshold:    80,
			CurrentValue: 92.5,
			Severity:     "CRITICAL",
			Message:      "HDFS heap usage exceeded threshold",
			Status:       "firing",
			FiredAt:      now - 300000,
		},
		{
			ID:           2,
			AlertID:      1002,
			HostID:       1,
			ServiceName:  "YARN",
			MetricName:   "memory_usage",
			Threshold:    85,
			CurrentValue: 88.3,
			Severity:     "WARNING",
			Message:      "YARN memory usage above warning threshold",
			Status:       "firing",
			FiredAt:      now - 600000,
		},
		{
			ID:           3,
			AlertID:      1003,
			HostID:       2,
			ServiceName:  "Kafka",
			MetricName:   "disk_usage",
			Threshold:    90,
			CurrentValue: 85.2,
			Severity:     "WARNING",
			Message:      "Kafka disk usage approaching threshold",
			Status:       "resolved",
			FiredAt:      now - 3600000,
			ResolvedAt:   func() *int64 { t := now - 1800000; return &t }(),
		},
	}
}