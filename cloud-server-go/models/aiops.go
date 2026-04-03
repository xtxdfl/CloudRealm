package models

import (
	"time"
)

type Anomaly struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	AnomalyID   uint      `gorm:"column:anomaly_id;uniqueIndex" json:"anomalyId"`
	Title       string    `gorm:"column:title" json:"title"`
	Description string    `gorm:"column:description;type:text" json:"description"`
	Severity    string    `gorm:"column:severity" json:"severity"`
	Source      string    `gorm:"column:source" json:"source"`
	Type        string    `gorm:"column:type" json:"type"`
	Confidence  float64   `gorm:"column:confidence;default:0" json:"confidence"`
	Status      string    `gorm:"column:status;default:'OPEN'" json:"status"`
	Timestamp   int64     `gorm:"column:timestamp" json:"timestamp"`
	ResolvedAt  *int64    `gorm:"column:resolved_at" json:"resolvedAt"`
	Details     string    `gorm:"column:details;type:text" json:"details"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (Anomaly) TableName() string {
	return "aiops_anomalies"
}

type Prediction struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	PredictionID   uint      `gorm:"column:prediction_id;uniqueIndex" json:"predictionId"`
	Metric         string    `gorm:"column:metric" json:"metric"`
	CurrentValue   float64   `gorm:"column:current_value" json:"currentValue"`
	PredictedValue float64   `gorm:"column:predicted_value" json:"predictedValue"`
	Threshold      float64   `gorm:"column:threshold" json:"threshold"`
	DaysLeft       int       `gorm:"column:days_left" json:"daysLeft"`
	Recommendation string    `gorm:"column:recommendation;type:text" json:"recommendation"`
	Confidence     float64   `gorm:"column:confidence;default:0" json:"confidence"`
	AlertLevel     string    `gorm:"column:alert_level" json:"alertLevel"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (Prediction) TableName() string {
	return "aiops_predictions"
}

type RootCause struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	IncidentID     string    `gorm:"column:incident_id;index" json:"incidentId"`
	Title          string    `gorm:"column:title" json:"title"`
	Description    string    `gorm:"column:description;type:text" json:"description"`
	RootCauseType  string    `gorm:"column:root_cause_type" json:"rootCauseType"`
	Probability    float64   `gorm:"column:probability;default:0" json:"probability"`
	AffectedEntity string    `gorm:"column:affected_entity" json:"affectedEntity"`
	Evidence       string    `gorm:"column:evidence;type:text" json:"evidence"`
	Status         string    `gorm:"column:status;default:'ANALYZING'" json:"status"`
	Severity       string    `gorm:"column:severity" json:"severity"`
	StartTime      int64     `gorm:"column:start_time" json:"startTime"`
	EndTime        *int64    `gorm:"column:end_time" json:"endTime"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (RootCause) TableName() string {
	return "aiops_root_causes"
}

type MetricAnomaly struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	MetricName     string    `gorm:"column:metric_name;index" json:"metricName"`
	HostName       string    `gorm:"column:host_name" json:"hostName"`
	ServiceName    string    `gorm:"column:service_name" json:"serviceName"`
	Value          float64   `gorm:"column:value" json:"value"`
	Baseline       float64   `gorm:"column:baseline" json:"baseline"`
	StdDeviation   float64   `gorm:"column:std_deviation" json:"stdDeviation"`
	AnomalyType    string    `gorm:"column:anomaly_type" json:"anomalyType"`
	Severity       string    `gorm:"column:severity" json:"severity"`
	Timestamp      int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (MetricAnomaly) TableName() string {
	return "aiops_metric_anomalies"
}

type AlertRule struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	RuleID        uint      `gorm:"column:rule_id;uniqueIndex" json:"ruleId"`
	RuleName      string    `gorm:"column:rule_name" json:"ruleName"`
	Description   string    `gorm:"column:description;type:text" json:"description"`
	MetricName    string    `gorm:"column:metric_name" json:"metricName"`
	Condition     string    `gorm:"column:condition" json:"condition"`
	Threshold     float64   `gorm:"column:threshold" json:"threshold"`
	Severity      string    `gorm:"column:severity" json:"severity"`
	IsEnabled     bool      `gorm:"column:is_enabled;default:true" json:"isEnabled"`
	NotifyChannels string   `gorm:"column:notify_channels" json:"notifyChannels"`
	Cooldown      int       `gorm:"column:cooldown;default:300" json:"cooldown"`
	CreatedBy     string    `gorm:"column:created_by" json:"createdBy"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (AlertRule) TableName() string {
	return "aiops_alert_rules"
}

type AnomalyInfo struct {
	ID          uint    `json:"id"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Severity    string  `json:"severity"`
	Source      string  `json:"source"`
	Type        string  `json:"type"`
	Confidence  float64 `json:"confidence"`
	Timestamp   string  `json:"timestamp"`
	Status      string  `json:"status"`
}

type PredictionInfo struct {
	ID             uint    `json:"id"`
	Metric         string  `json:"metric"`
	CurrentValue   float64 `json:"currentValue"`
	PredictedValue float64 `json:"predictedValue"`
	DaysLeft       int     `json:"daysLeft"`
	Recommendation string  `json:"recommendation"`
	AlertLevel     string  `json:"alertLevel"`
}

type RootCauseInfo struct {
	ID             uint    `json:"id"`
	IncidentID     string  `json:"incidentId"`
	Title          string  `json:"title"`
	Description    string  `json:"description"`
	RootCauseType  string  `json:"rootCauseType"`
	Probability    float64 `json:"probability"`
	AffectedEntity string  `json:"affectedEntity"`
	Status         string  `json:"status"`
	Severity       string  `json:"severity"`
}

type MetricData struct {
	Timestamp   int64   `json:"timestamp"`
	Value       float64 `json:"value"`
	Label       string  `json:"label"`
	HostName    string  `json:"hostName"`
	ServiceName string  `json:"serviceName"`
}

type AnomalyStats struct {
	TotalAnomalies  int64 `json:"totalAnomalies"`
	CriticalCount   int64 `json:"criticalCount"`
	WarningCount    int64 `json:"warningCount"`
	ResolvedCount   int64 `json:"resolvedCount"`
	OpenCount       int64 `json:"openCount"`
	AvgConfidence   float64 `json:"avgConfidence"`
}

type PredictionStats struct {
	TotalPredictions int64  `json:"totalPredictions"`
	CriticalAlerts   int64  `json:"criticalAlerts"`
	WarningAlerts    int64  `json:"warningAlerts"`
	AvgDaysLeft      float64 `json:"avgDaysLeft"`
}

type AnalysisRequest struct {
	IncidentID   string   `json:"incidentId" binding:"required"`
	StartTime    int64    `json:"startTime" binding:"required"`
	EndTime      int64    `json:"endTime" binding:"required"`
	Services     []string `json:"services"`
	Hosts        []string `json:"hosts"`
}

type AlertRequest struct {
	RuleName   string  `json:"ruleName" binding:"required"`
	MetricName string  `json:"metricName" binding:"required"`
	Condition  string  `json:"condition" binding:"required"`
	Threshold float64 `json:"threshold" binding:"required"`
	Severity  string  `json:"severity" binding:"required"`
}

type ThresholdConfig struct {
	UpperWarning   float64 `json:"upperWarning"`
	UpperCritical  float64 `json:"upperCritical"`
	LowerWarning   float64 `json:"lowerWarning"`
	LowerCritical  float64 `json:"lowerCritical"`
}