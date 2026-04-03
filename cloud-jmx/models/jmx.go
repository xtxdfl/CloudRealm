package models

import (
	"time"
)

type JMXTarget struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	HostID      int       `gorm:"column:host_id;index" json:"hostId"`
	ServiceName string    `gorm:"column:service_name;index" json:"serviceName"`
	Host        string    `gorm:"column:host" json:"host"`
	Port        int       `gorm:"column:port" json:"port"`
	Protocol    string    `gorm:"column:protocol;default:jmx" json:"protocol"`
	Username    string    `gorm:"column:username" json:"username"`
	Password    string    `gorm:"column:password" json:"password"`
	JmxURL      string    `gorm:"column:jmx_url" json:"jmxUrl"`
	Status      string    `gorm:"column:status;default:active" json:"status"`
	LastCheck   int64     `gorm:"column:last_check" json:"lastCheck"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (JMXTarget) TableName() string {
	return "jmx_targets"
}

type JMXMetric struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	TargetID       uint      `gorm:"column:target_id;index" json:"targetId"`
	ObjectName    string    `gorm:"column:object_name;index" json:"objectName"`
	AttributeName  string    `gorm:"column:attribute_name" json:"attributeName"`
	KeyProperties string    `gorm:"column:key_properties" json:"keyProperties"`
	Value         string    `gorm:"column:value" json:"value"`
	ValueType     string    `gorm:"column:value_type" json:"valueType"`
	Timestamp     int64     `gorm:"column:timestamp;index" json:"timestamp"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (JMXMetric) TableName() string {
	return "jmx_metrics"
}

type JMXAttribute struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	TargetID     uint      `gorm:"column:target_id;index" json:"targetId"`
	ObjectName  string    `gorm:"column:object_name" json:"objectName"`
	Attribute   string    `gorm:"column:attribute" json:"attribute"`
	Description string    `gorm:"column:description" json:"description"`
	Type        string    `gorm:"column:type" json:"type"`
	IsComposite bool      `gorm:"column:is_composite;default:false" json:"isComposite"`
	IsDynamic   bool      `gorm:"column:is_dynamic;default:false" json:"isDynamic"`
	Enabled     bool      `gorm:"column:enabled;default:true" json:"enabled"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (JMXAttribute) TableName() string {
	return "jmx_attributes"
}

type JMXConnection struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	TargetID  uint      `gorm:"column:target_id;index" json:"targetId"`
	Status    string    `gorm:"column:status" json:"status"`
	ErrorMsg  string    `gorm:"column:error_msg" json:"errorMsg"`
	LatencyMs int64     `gorm:"column:latency_ms" json:"latencyMs"`
	CheckedAt int64     `gorm:"column:checked_at" json:"checkedAt"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

func (JMXConnection) TableName() string {
	return "jmx_connections"
}

type CollectConfig struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	ServiceName string    `gorm:"column:service_name;index" json:"serviceName"`
	ObjectName string    `gorm:"column:object_name" json:"objectName"`
	Attributes []string  `gorm:"column:attributes" json:"attributes"`
	Interval   int       `gorm:"column:interval;default:60000" json:"interval"`
	Enabled    bool      `gorm:"column:enabled;default:true" json:"enabled"`
	CreatedAt  time.Time `json:"createdAt"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

func (CollectConfig) TableName() string {
	return "jmx_collect_configs"
}

type JMXHeapMemory struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	TargetID       uint      `gorm:"column:target_id;index" json:"targetId"`
	HeapUsed       int64     `gorm:"column:heap_used" json:"heapUsed"`
	HeapMax        int64     `gorm:"column:heap_max" json:"heapMax"`
	HeapCommitted  int64     `gorm:"column:heap_committed" json:"heapCommitted"`
	HeapUsage      float64   `gorm:"column:heap_usage" json:"heapUsage"`
	NonHeapUsed    int64     `gorm:"column:non_heap_used" json:"nonHeapUsed"`
	NonHeapMax     int64     `gorm:"column:non_heap_max" json:"nonHeapMax"`
	Timestamp      int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (JMXHeapMemory) TableName() string {
	return "jmx_heap_memory"
}

type JMXThreading struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	TargetID      uint      `gorm:"column:target_id;index" json:"targetId"`
	ThreadCount   int       `gorm:"column:thread_count" json:"threadCount"`
	PeakThreadCount int     `gorm:"column:peak_thread_count" json:"peakThreadCount"`
	DaemonThreadCount int   `gorm:"column:daemon_thread_count" json:"daemonThreadCount"`
	TotalStartedThreadCount int64 `gorm:"column:total_started_thread_count" json:"totalStartedThreadCount"`
	Timestamp     int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (JMXThreading) TableName() string {
	return "jmx_threading"
}

type JMXGarbageCollector struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	TargetID         uint      `gorm:"column:target_id;index" json:"targetId"`
	CollectorName   string    `gorm:"column:collector_name" json:"collectorName"`
	CollectionCount int64     `gorm:"column:collection_count" json:"collectionCount"`
	CollectionTime  int64     `gorm:"column:collection_time" json:"collectionTime"`
	LastCollectionTime int64  `gorm:"column:last_collection_time" json:"lastCollectionTime"`
	Timestamp       int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt       time.Time `json:"createdAt"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

func (JMXGarbageCollector) TableName() string {
	return "jmx_garbage_collectors"
}

type JMXClassLoading struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	TargetID           uint      `gorm:"column:target_id;index" json:"targetId"`
	LoadedClassCount   int64     `gorm:"column:loaded_class_count" json:"loadedClassCount"`
	TotalLoadedClassCount int64  `gorm:"column:total_loaded_class_count" json:"totalLoadedClassCount"`
	UnloadedClassCount int64     `gorm:"column:unloaded_class_count" json:"unloadedClassCount"`
	Timestamp          int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt          time.Time `json:"createdAt"`
	UpdatedAt          time.Time `json:"updatedAt"`
}

func (JMXClassLoading) TableName() string {
	return "jmx_class_loading"
}

type JMXRuntime struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	TargetID       uint      `gorm:"column:target_id;index" json:"targetId"`
	Uptime         int64     `gorm:"column:uptime" json:"uptime"`
	StartTime      int64     `gorm:"column:start_time" json:"startTime"`
	VmName         string    `gorm:"column:vm_name" json:"vmName"`
	VmVendor       string    `gorm:"column:vm_vendor" json:"vmVendor"`
	VmVersion      string    `gorm:"column:vm_version" json:"vmVersion"`
	InputArgs      string    `gorm:"column:input_args" json:"inputArgs"`
	Timestamp      int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (JMXRuntime) TableName() string {
	return "jmx_runtime"
}

type JMXMemoryPool struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	TargetID      uint      `gorm:"column:target_id;index" json:"targetId"`
	PoolName      string    `gorm:"column:pool_name" json:"poolName"`
	Type          string    `gorm:"column:type" json:"type"`
	Used          int64     `gorm:"column:used" json:"used"`
	Committed     int64     `gorm:"column:committed" json:"committed"`
	Max           int64     `gorm:"column:max" json:"max"`
	UsagePercent  float64   `gorm:"column:usage_percent" json:"usagePercent"`
	Timestamp     int64     `gorm:"column:timestamp" json:"timestamp"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (JMXMemoryPool) TableName() string {
	return "jmx_memory_pools"
}