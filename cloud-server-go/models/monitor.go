package models

import (
	"time"
)

type HostMetricData struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	HostID        int       `gorm:"column:host_id;index" json:"hostId"`
	ServiceName   string    `gorm:"column:service_name;index" json:"serviceName"`
	MetricName   string    `gorm:"column:metric_name;index" json:"metricName"`
	MetricValue  float64   `gorm:"column:metric_value" json:"metricValue"`
	MetricType   string    `gorm:"column:metric_type" json:"metricType"`
	Unit         string    `gorm:"column:unit" json:"unit"`
	Timestamp    int64     `gorm:"column:timestamp;index" json:"timestamp"`
	Labels       string    `gorm:"column:labels" json:"labels"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (HostMetricData) TableName() string {
	return "metric_data"
}

type JMXMetric struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	HostID         int       `gorm:"column:host_id;index" json:"hostId"`
	ServiceName    string    `gorm:"column:service_name;index" json:"serviceName"`
	ObjectName    string    `gorm:"column:object_name" json:"objectName"`
	AttributeName  string    `gorm:"column:attribute_name" json:"attributeName"`
	KeyProperties string    `gorm:"column:key_properties" json:"keyProperties"`
	Value         string    `gorm:"column:value" json:"value"`
	ValueType     string    `gorm:"column:value_type" json:"valueType"`
	Timestamp     int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (JMXMetric) TableName() string {
	return "jmx_metrics"
}

type HostMetric struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	HostID       int       `gorm:"column:host_id;index" json:"hostId"`
	MetricType   string    `gorm:"column:metric_type" json:"metricType"`
	CPUUsage     float64   `gorm:"column:cpu_usage" json:"cpuUsage"`
	MemoryUsage  float64   `gorm:"column:memory_usage" json:"memoryUsage"`
	DiskUsage    float64   `gorm:"column:disk_usage" json:"diskUsage"`
	NetworkIn    float64   `gorm:"column:network_in" json:"networkIn"`
	NetworkOut   float64   `gorm:"column:network_out" json:"networkOut"`
	LoadAverage  float64   `gorm:"column:load_average" json:"loadAverage"`
	Timestamp    int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (HostMetric) TableName() string {
	return "host_metrics"
}

type ServiceMetric struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	HostID        int       `gorm:"column:host_id;index" json:"hostId"`
	ServiceName   string    `gorm:"column:service_name;index" json:"serviceName"`
	ComponentName string    `gorm:"column:component_name" json:"componentName"`
	Status        string    `gorm:"column:status" json:"status"`
	Uptime        int64     `gorm:"column:uptime" json:"uptime"`
	HeapUsed      int64     `gorm:"column:heap_used" json:"heapUsed"`
	HeapMax       int64     `gorm:"column:heap_max" json:"heapMax"`
	HeapUsage     float64   `gorm:"column:heap_usage" json:"heapUsage"`
	NonHeapUsed   int64     `gorm:"column:non_heap_used" json:"nonHeapUsed"`
	ThreadCount   int       `gorm:"column:thread_count" json:"threadCount"`
	ThreadPeak    int       `gorm:"column:thread_peak" json:"threadPeak"`
	GCCount       int       `gorm:"column:gc_count" json:"gcCount"`
	GCTime        int64     `gorm:"column:gc_time" json:"gcTime"`
	Timestamp     int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (ServiceMetric) TableName() string {
	return "service_metrics"
}

type MetricQuery struct {
	HostID      int      `json:"hostId"`
	ServiceName string   `json:"serviceName"`
	MetricNames []string `json:"metricNames"`
	StartTime   int64    `json:"startTime"`
	EndTime     int64    `json:"endTime"`
	Interval    int      `json:"interval"`
	Aggregate   string   `json:"aggregate"`
}

type MetricResponse struct {
	MetricName string        `json:"metricName"`
	Unit      string        `json:"unit"`
	DataPoints []DataPoint   `json:"dataPoints"`
}

type DataPoint struct {
	Timestamp int64   `json:"timestamp"`
	Value     float64 `json:"value"`
}

type MetricThreshold struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	ServiceName  string    `gorm:"column:service_name;index" json:"serviceName"`
	MetricName   string    `gorm:"column:metric_name;index" json:"metricName"`
	ThresholdMin float64   `gorm:"column:threshold_min" json:"thresholdMin"`
	ThresholdMax float64   `gorm:"column:threshold_max" json:"thresholdMax"`
	Severity     string    `gorm:"column:severity" json:"severity"`
	Enabled      bool      `gorm:"column:enabled;default:true" json:"enabled"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (MetricThreshold) TableName() string {
	return "metric_thresholds"
}

type AlertEvent struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	AlertID     int       `gorm:"column:alert_id;index" json:"alertId"`
	HostID      int       `gorm:"column:host_id;index" json:"hostId"`
	ServiceName string    `gorm:"column:service_name" json:"serviceName"`
	MetricName  string    `gorm:"column:metric_name" json:"metricName"`
	Threshold   float64   `gorm:"column:threshold" json:"threshold"`
	CurrentValue float64  `gorm:"column:current_value" json:"currentValue"`
	Severity    string    `gorm:"column:severity" json:"severity"`
	Message     string    `gorm:"column:message" json:"message"`
	Status      string    `gorm:"column:status" json:"status"`
	FiredAt     int64     `gorm:"column:fired_at" json:"firedAt"`
	ResolvedAt  *int64    `gorm:"column:resolved_at" json:"resolvedAt"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (AlertEvent) TableName() string {
	return "alert_events"
}