package service

import (
	"errors"
	"math"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type AIOpsService struct {
	db *gorm.DB
}

func NewAIOpsService(db *gorm.DB) *AIOpsService {
	return &AIOpsService{db: db}
}

func (s *AIOpsService) GetAllAnomalies() ([]models.AnomalyInfo, error) {
	var anomalies []models.Anomaly
	s.db.Order("timestamp DESC").Find(&anomalies)

	result := make([]models.AnomalyInfo, 0, len(anomalies))
	for _, a := range anomalies {
		result = append(result, models.AnomalyInfo{
			ID:          a.ID,
			Title:       a.Title,
			Description: a.Description,
			Severity:    a.Severity,
			Source:      a.Source,
			Type:        a.Type,
			Confidence:  a.Confidence,
			Timestamp:   formatTimestamp(a.Timestamp),
			Status:      a.Status,
		})
	}

	if len(result) == 0 {
		return s.getMockAnomalies(), nil
	}

	return result, nil
}

func (s *AIOpsService) GetAnomalyById(id uint) (*models.AnomalyInfo, error) {
	var anomaly models.Anomaly
	if err := s.db.First(&anomaly, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, a := range s.getMockAnomalies() {
				if a.ID == id {
					return &a, nil
				}
			}
		}
		return nil, errors.New("anomaly not found")
	}

	return &models.AnomalyInfo{
		ID:          anomaly.ID,
		Title:       anomaly.Title,
		Description: anomaly.Description,
		Severity:    anomaly.Severity,
		Source:      anomaly.Source,
		Type:        anomaly.Type,
		Confidence:  anomaly.Confidence,
		Timestamp:   formatTimestamp(anomaly.Timestamp),
		Status:      anomaly.Status,
	}, nil
}

func (s *AIOpsService) CreateAnomaly(anomaly *models.Anomaly) (*models.AnomalyInfo, error) {
	anomaly.Timestamp = time.Now().UnixMilli()
	anomaly.Status = "OPEN"

	if err := s.db.Create(anomaly).Error; err != nil {
		return nil, err
	}

	return &models.AnomalyInfo{
		ID:          anomaly.ID,
		Title:       anomaly.Title,
		Description: anomaly.Description,
		Severity:    anomaly.Severity,
		Source:      anomaly.Source,
		Type:        anomaly.Type,
		Confidence:  anomaly.Confidence,
		Timestamp:   formatTimestamp(anomaly.Timestamp),
		Status:      anomaly.Status,
	}, nil
}

func (s *AIOpsService) ResolveAnomaly(id uint) error {
	var anomaly models.Anomaly
	if err := s.db.First(&anomaly, id).Error; err != nil {
		return errors.New("anomaly not found")
	}

	now := time.Now().UnixMilli()
	anomaly.Status = "RESOLVED"
	anomaly.ResolvedAt = &now

	s.db.Save(&anomaly)
	return nil
}

func (s *AIOpsService) DeleteAnomaly(id uint) error {
	return s.db.Delete(&models.Anomaly{}, id).Error
}

func (s *AIOpsService) GetAllPredictions() ([]models.PredictionInfo, error) {
	var predictions []models.Prediction
	s.db.Order("days_left ASC").Find(&predictions)

	result := make([]models.PredictionInfo, 0, len(predictions))
	for _, p := range predictions {
		alertLevel := "Normal"
		if p.PredictedValue > p.Threshold {
			alertLevel = "Critical"
		} else if p.PredictedValue > p.Threshold*0.8 {
			alertLevel = "Warning"
		}

		result = append(result, models.PredictionInfo{
			ID:             p.ID,
			Metric:         p.Metric,
			CurrentValue:   p.CurrentValue,
			PredictedValue: p.PredictedValue,
			DaysLeft:       p.DaysLeft,
			Recommendation: p.Recommendation,
			AlertLevel:     alertLevel,
		})
	}

	if len(result) == 0 {
		return s.getMockPredictions(), nil
	}

	return result, nil
}

func (s *AIOpsService) CreatePrediction(prediction *models.Prediction) (*models.PredictionInfo, error) {
	if err := s.db.Create(prediction).Error; err != nil {
		return nil, err
	}

	alertLevel := "Normal"
	if prediction.PredictedValue > prediction.Threshold {
		alertLevel = "Critical"
	} else if prediction.PredictedValue > prediction.Threshold*0.8 {
		alertLevel = "Warning"
	}

	return &models.PredictionInfo{
		ID:             prediction.ID,
		Metric:         prediction.Metric,
		CurrentValue:   prediction.CurrentValue,
		PredictedValue: prediction.PredictedValue,
		DaysLeft:       prediction.DaysLeft,
		Recommendation: prediction.Recommendation,
		AlertLevel:     alertLevel,
	}, nil
}

func (s *AIOpsService) GetAnomalyStats() (*models.AnomalyStats, error) {
	var stats models.AnomalyStats

	s.db.Model(&models.Anomaly{}).Count(&stats.TotalAnomalies)
	s.db.Model(&models.Anomaly{}).Where("severity = ?", "Critical").Count(&stats.CriticalCount)
	s.db.Model(&models.Anomaly{}).Where("severity = ?", "Warning").Count(&stats.WarningCount)
	s.db.Model(&models.Anomaly{}).Where("status = ?", "RESOLVED").Count(&stats.ResolvedCount)
	s.db.Model(&models.Anomaly{}).Where("status = ?", "OPEN").Count(&stats.OpenCount)

	var avgConfidence float64
	s.db.Model(&models.Anomaly{}).Select("AVG(confidence)").Scan(&avgConfidence)
	stats.AvgConfidence = avgConfidence

	if stats.TotalAnomalies == 0 {
		stats.TotalAnomalies = 15
		stats.CriticalCount = 3
		stats.WarningCount = 5
		stats.ResolvedCount = 7
		stats.OpenCount = 8
		stats.AvgConfidence = 89.5
	}

	return &stats, nil
}

func (s *AIOpsService) GetPredictionStats() (*models.PredictionStats, error) {
	var stats models.PredictionStats

	s.db.Model(&models.Prediction{}).Count(&stats.TotalPredictions)

	var avgDaysLeft float64
	s.db.Model(&models.Prediction{}).Select("AVG(days_left)").Scan(&avgDaysLeft)
	stats.AvgDaysLeft = avgDaysLeft

	var predictions []models.Prediction
	s.db.Find(&predictions)
	for _, p := range predictions {
		if p.PredictedValue > p.Threshold {
			stats.CriticalAlerts++
		} else if p.PredictedValue > p.Threshold*0.8 {
			stats.WarningAlerts++
		}
	}

	if stats.TotalPredictions == 0 {
		stats.TotalPredictions = 8
		stats.CriticalAlerts = 2
		stats.WarningAlerts = 3
		stats.AvgDaysLeft = 25
	}

	return &stats, nil
}

func (s *AIOpsService) AnalyzeRootCause(req *models.AnalysisRequest) ([]models.RootCauseInfo, error) {
	incidentID := generateIncidentID()

	rootCauses := []models.RootCauseInfo{
		{
			ID:             1,
			IncidentID:     incidentID,
			Title:          "Database Connection Pool Exhausted",
			Description:    "Connection pool reaching maximum capacity causing application delays",
			RootCauseType:  "Database",
			Probability:    85.0,
			AffectedEntity: "PrimaryDB",
			Status:         "CONFIRMED",
			Severity:       "High",
		},
		{
			ID:             2,
			IncidentID:     incidentID,
			Title:          "Network Latency Spike",
			Description:    "Intermittent network latency affecting service communication",
			RootCauseType:  "Network",
			Probability:    60.0,
			AffectedEntity: "Gateway",
			Status:         "ANALYZING",
			Severity:       "Medium",
		},
		{
			ID:             3,
			IncidentID:     incidentID,
			Title:          "Memory Pressure on JVM",
			Description:    "High memory usage triggering frequent GC pauses",
			RootCauseType:  "Application",
			Probability:    45.0,
			AffectedEntity: "ApplicationServer",
			Status:         "SUSPECTED",
			Severity:       "Medium",
		},
	}

	return rootCauses, nil
}

func (s *AIOpsService) GetMetricAnomalies(metricName string, startTime, endTime int64) ([]models.MetricAnomaly, error) {
	var anomalies []models.MetricAnomaly
	query := s.db.Where("timestamp BETWEEN ? AND ?", startTime, endTime)

	if metricName != "" {
		query = query.Where("metric_name = ?", metricName)
	}

	query.Order("timestamp DESC").Find(&anomalies)

	if len(anomalies) == 0 {
		return s.getMockMetricAnomalies(metricName), nil
	}

	return anomalies, nil
}

func (s *AIOpsService) CreateAlertRule(rule *models.AlertRule) (*models.AlertRule, error) {
	rule.IsEnabled = true
	rule.Cooldown = 300

	if err := s.db.Create(rule).Error; err != nil {
		return nil, err
	}

	return rule, nil
}

func (s *AIOpsService) GetAlertRules() ([]models.AlertRule, error) {
	var rules []models.AlertRule
	s.db.Where("is_enabled = ?", true).Find(&rules)

	if len(rules) == 0 {
		return s.getMockAlertRules(), nil
	}

	return rules, nil
}

func (s *AIOpsService) UpdateAlertRule(ruleId uint, rule *models.AlertRule) error {
	var existing models.AlertRule
	if err := s.db.Where("rule_id = ?", ruleId).First(&existing).Error; err != nil {
		return errors.New("rule not found")
	}

	rule.RuleID = ruleId
	s.db.Save(rule)

	return nil
}

func (s *AIOpsService) DeleteAlertRule(ruleId uint) error {
	return s.db.Where("rule_id = ?", ruleId).Delete(&models.AlertRule{}).Error
}

func (s *AIOpsService) CheckMetricAgainstRules(metricName string, value float64) []models.AlertRule {
	var rules []models.AlertRule
	s.db.Where("metric_name = ? AND is_enabled = ?", metricName, true).Find(&rules)

	triggered := make([]models.AlertRule, 0)
	for _, rule := range rules {
		triggeredAlert := false

		switch rule.Condition {
		case ">":
			triggeredAlert = value > rule.Threshold
		case ">=":
			triggeredAlert = value >= rule.Threshold
		case "<":
			triggeredAlert = value < rule.Threshold
		case "<=":
			triggeredAlert = value <= rule.Threshold
		case "==":
			triggeredAlert = math.Abs(value-rule.Threshold) < 0.0001
		}

		if triggeredAlert {
			triggered = append(triggered, rule)
		}
	}

	return triggered
}

func (s *AIOpsService) GetMetricHistory(metricName string, hours int) ([]models.MetricData, error) {
	endTime := time.Now().UnixMilli()
	startTime := endTime - int64(hours*3600*1000)

	var data []models.MetricData
	s.db.Where("metric_name = ? AND timestamp > ?", metricName, startTime).
		Order("timestamp ASC").Find(&data)

	if len(data) == 0 {
		data = s.getMockMetricData(metricName, hours)
	}

	return data, nil
}

func (s *AIOpsService) getMockAnomalies() []models.AnomalyInfo {
	now := time.Now()
	return []models.AnomalyInfo{
		{ID: 1, Title: "Unusual Traffic Spike", Description: "HDFS DataNode-04 network in > 3σ baseline", Severity: "Critical", Source: "DataNode-04", Type: "Network", Confidence: 95.0, Timestamp: now.Add(-10 * time.Minute).Format("15:04"), Status: "OPEN"},
		{ID: 2, Title: "Application Slowdown", Description: "JVM GC Pause (Stop-the-world) > 5s", Severity: "Warning", Source: "ApplicationServer-02", Type: "Performance", Confidence: 88.0, Timestamp: now.Add(-1 * time.Hour).Format("15:04"), Status: "OPEN"},
		{ID: 3, Title: "Multiple Failed Logins", Description: "Detected 15 failed login attempts in 5 minutes", Severity: "Critical", Source: "Gateway", Type: "Security", Confidence: 92.0, Timestamp: now.Add(-2 * time.Hour).Format("15:04"), Status: "RESOLVED"},
		{ID: 4, Title: "High CPU Usage", Description: "CPU usage > 90% for 10 minutes", Severity: "Warning", Source: "WorkerNode-01", Type: "Performance", Confidence: 85.0, Timestamp: now.Add(-3 * time.Hour).Format("15:04"), Status: "RESOLVED"},
		{ID: 5, Title: "Disk Space Low", Description: "Disk usage > 85% on /data partition", Severity: "Warning", Source: "NameNode", Type: "System", Confidence: 98.0, Timestamp: now.Add(-4 * time.Hour).Format("15:04"), Status: "OPEN"},
	}
}

func (s *AIOpsService) getMockPredictions() []models.PredictionInfo {
	return []models.PredictionInfo{
		{ID: 1, Metric: "HDFS Storage", CurrentValue: 1.2, PredictedValue: 1.8, DaysLeft: 32, Recommendation: "Add 2 DataNodes by next month", AlertLevel: "Critical"},
		{ID: 2, Metric: "YARN Memory", CurrentValue: 75.0, PredictedValue: 90.0, DaysLeft: 15, Recommendation: "Scale up YARN memory allocation", AlertLevel: "Warning"},
		{ID: 3, Metric: "Kafka Disk", CurrentValue: 60.0, PredictedValue: 85.0, DaysLeft: 25, Recommendation: "Add more Kafka brokers", AlertLevel: "Warning"},
		{ID: 4, Metric: "ZooKeeper Connections", CurrentValue: 200, PredictedValue: 450, DaysLeft: 45, Recommendation: "Monitor connection pool", AlertLevel: "Normal"},
	}
}

func (s *AIOpsService) getMockMetricAnomalies(metricName string) []models.MetricAnomaly {
	now := time.Now().UnixMilli()
	return []models.MetricAnomaly{
		{ID: 1, MetricName: metricName, HostName: "DataNode-01", Value: 95.5, Baseline: 50.0, StdDeviation: 15.0, AnomalyType: "SPIKE", Severity: "Critical", Timestamp: now - 600000},
		{ID: 2, MetricName: metricName, HostName: "DataNode-02", Value: 88.2, Baseline: 50.0, StdDeviation: 15.0, AnomalyType: "HIGH", Severity: "Warning", Timestamp: now - 1200000},
	}
}

func (s *AIOpsService) getMockAlertRules() []models.AlertRule {
	return []models.AlertRule{
		{ID: 1, RuleID: 1, RuleName: "High CPU Alert", Description: "Alert when CPU > 90%", MetricName: "cpu_usage", Condition: ">", Threshold: 90.0, Severity: "Critical", IsEnabled: true, Cooldown: 300},
		{ID: 2, RuleID: 2, RuleName: "Memory Warning", Description: "Alert when Memory > 85%", MetricName: "memory_usage", Condition: ">", Threshold: 85.0, Severity: "Warning", IsEnabled: true, Cooldown: 600},
		{ID: 3, RuleID: 3, RuleName: "Disk Space Low", Description: "Alert when Disk > 90%", MetricName: "disk_usage", Condition: ">", Threshold: 90.0, Severity: "Critical", IsEnabled: true, Cooldown: 900},
	}
}

func (s *AIOpsService) getMockMetricData(metricName string, hours int) []models.MetricData {
	data := make([]models.MetricData, 0, hours*12)
	now := time.Now().UnixMilli()

	for i := hours * 12; i > 0; i-- {
		timestamp := now - int64(i*300000)
		base := 50.0 + float64(hours*2-i)
		value := base + (float64(i%10) * 2)

		data = append(data, models.MetricData{
			Timestamp: timestamp,
			Value:     value,
			Label:     formatTimestamp(timestamp),
			HostName:  "localhost",
		})
	}

	return data
}

func formatTimestamp(ts int64) string {
	if ts == 0 {
		return ""
	}
	t := time.UnixMilli(ts)
	return t.Format("15:04")
}

func generateIncidentID() string {
	now := time.Now()
	return "INC-" + now.Format("20060102") + "-" + now.Format("150405")
}