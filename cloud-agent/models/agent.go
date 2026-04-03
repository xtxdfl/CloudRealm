package models

import (
	"time"
)

type Command struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	CommandID      string    `gorm:"column:command_id;uniqueIndex" json:"commandId"`
	TaskID         string    `gorm:"column:task_id;index" json:"taskId"`
	CommandType    string    `gorm:"column:command_type" json:"commandType"`
	CommandText    string    `gorm:"column:command_text" json:"commandText"`
	TargetHost     string    `gorm:"column:target_host" json:"targetHost"`
	Status         string    `gorm:"column:status;default:pending" json:"status"`
	ExitCode        int       `gorm:"column:exit_code" json:"exitCode"`
	StdOut          string    `gorm:"column:stdout" json:"stdOut"`
	StdErr          string    `gorm:"column:stderr" json:"stdErr"`
	StartTime       int64     `gorm:"column:start_time" json:"startTime"`
	EndTime         int64     `gorm:"column:end_time" json:"endTime"`
	ErrorMessage    string    `gorm:"column:error_message" json:"errorMessage"`
	OutputLogURI    string    `gorm:"column:output_log_uri" json:"outputLogUri"`
	ResultFileDir   string    `gorm:"column:result_file_dir" json:"resultFileDir"`
	CreatedAt       time.Time `json:"createdAt"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

func (Command) TableName() string {
	return "agent_commands"
}

type AgentStatus struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	AgentID     string    `gorm:"column:agent_id;uniqueIndex" json:"agentId"`
	HostName    string    `gorm:"column:host_name" json:"hostName"`
	IPAddress   string    `gorm:"column:ip_address" json:"ipAddress"`
	Status      string    `gorm:"column:status;default:running" json:"status"`
	Version     string    `gorm:"column:version" json:"version"`
	LastHeartbeat int64   `gorm:"column:last_heartbeat" json:"lastHeartbeat"`
	RegisteredAt int64    `gorm:"column:registered_at" json:"registeredAt"`
	Metadata    string    `gorm:"column:metadata" json:"metadata"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (AgentStatus) TableName() string {
	return "agent_status"
}

type HostInfo struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	AgentID       string    `gorm:"column:agent_id;index" json:"agentId"`
	HostName      string    `gorm:"column:host_name" json:"hostName"`
	IPAddress     string    `gorm:"column:ip_address" json:"ipAddress"`
	OSType        string    `gorm:"column:os_type" json:"osType"`
	OSVersion     string    `gorm:"column:os_version" json:"osVersion"`
	Architecture  string    `gorm:"column:architecture" json:"architecture"`
	CPUCount      int       `gorm:"column:cpu_count" json:"cpuCount"`
	MemoryTotal   int64     `gorm:"column:memory_total" json:"memoryTotal"`
	DiskTotal     int64     `gorm:"column:disk_total" json:"diskTotal"`
	Uptime        int64     `gorm:"column:uptime" json:"uptime"`
	LastUpdated   int64     `gorm:"column:last_updated" json:"lastUpdated"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (HostInfo) TableName() string {
	return "agent_host_info"
}

type ExecutionCommand struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	ClusterName   string    `gorm:"column:cluster_name" json:"clusterName"`
	ClusterId     string    `gorm:"column:cluster_id" json:"clusterId"`
	HostName      string    `gorm:"column:host_name" json:"hostName"`
	Role          string    `gorm:"column:role" json:"role"`
	ComponentName string    `gorm:"column:component_name" json:"componentName"`
	CommandType   string    `gorm:"column:command_type" json:"commandType"`
	CommandId     uint      `gorm:"column:command_id" json:"commandId"`
	TaskId        string    `gorm:"column:task_id" json:"taskId"`
	Status        string    `gorm:"column:status" json:"status"`
	ExitCode       int       `gorm:"column:exit_code" json:"exitCode"`
	StdOut        string    `gorm:"column:stdout" json:"stdout"`
	StdErr        string    `gorm:"column:stderr" json:"stderr"`
	StartTime     int64     `gorm:"column:start_time" json:"startTime"`
	EndTime       int64     `gorm:"column:end_time" json:"endTime"`
	ErrorMessage  string    `gorm:"column:error_message" json:"errorMessage"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (ExecutionCommand) TableName() string {
	return "agent_execution_commands"
}

type ComponentStatus struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	ClusterName   string    `gorm:"column:cluster_name" json:"clusterName"`
	ClusterId     string    `gorm:"column:cluster_id" json:"clusterId"`
	HostName      string    `gorm:"column:host_name" json:"hostName"`
	ComponentName string    `gorm:"column:component_name" json:"componentName"`
	ServiceName   string    `gorm:"column:service_name" json:"serviceName"`
	Status        string    `gorm:"column:status" json:"status"`
	State         string    `gorm:"column:state" json:"state"`
	Version       string    `gorm:"column:version" json:"version"`
	StartTime     int64     `gorm:"column:start_time" json:"startTime"`
	LastUpdate    int64     `gorm:"column:last_update" json:"lastUpdate"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (ComponentStatus) TableName() string {
	return "agent_component_status"
}

type Configuration struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	ClusterName string    `gorm:"column:cluster_name;index" json:"clusterName"`
	HostName    string    `gorm:"column:host_name" json:"hostName"`
	Type        string    `gorm:"column:type" json:"type"`
	Filename    string    `gorm:"column:filename" json:"filename"`
	Content     string    `gorm:"column:content" json:"content"`
	Checksum    string    `gorm:"column:checksum" json:"checksum"`
	Version     int       `gorm:"column:version" json:"version"`
	Properties  string    `gorm:"column:properties" json:"properties"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (Configuration) TableName() string {
	return "agent_configurations"
}

type Alert struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	ClusterName string    `gorm:"column:cluster_name" json:"clusterName"`
	HostName    string    `gorm:"column:host_name" json:"hostName"`
	AlertType   string    `gorm:"column:alert_type" json:"alertType"`
	Severity    string    `gorm:"column:severity" json:"severity"`
	Message     string    `gorm:"column:message" json:"message"`
	Source      string    `gorm:"column:source" json:"source"`
	Instance    string    `gorm:"column:instance" json:"instance"`
	Timestamp   int64     `gorm:"column:timestamp" json:"timestamp"`
	State       string    `gorm:"column:state" json:"state"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (Alert) TableName() string {
	return "agent_alerts"
}

type RegistrationRequest struct {
	AgentId      string            `json:"agentId"`
	HostName     string            `json:"hostName"`
	IPAddress    string            `json:"ipAddress"`
	Version      string            `json:"version"`
	OSType       string            `json:"osType"`
	OSVersion    string            `json:"osVersion"`
	CPUCount     int               `json:"cpuCount"`
	MemoryTotal  int64             `json:"memoryTotal"`
	DiskTotal    int64             `json:"diskTotal"`
	Roles        []string          `json:"roles"`
	Components   []string          `json:"components"`
	Metadata     map[string]string `json:"metadata"`
}

type HeartbeatRequest struct {
	AgentId       string            `json:"agentId"`
	Status        string            `json:"status"`
	Timestamp     int64             `json:"timestamp"`
	CPUUsage      float64           `json:"cpuUsage"`
	MemoryUsed    int64             `json:"memoryUsed"`
	MemoryTotal   int64             `json:"memoryTotal"`
	DiskUsed      int64             `json:"diskUsed"`
	DiskTotal     int64             `json:"diskTotal"`
	Components    []ComponentStatus `json:"components"`
	Alerts        []Alert           `json:"alerts"`
	Metadata      map[string]string `json:"metadata"`
}

type CommandRequest struct {
	CommandId     string `json:"commandId"`
	TaskId        string `json:"taskId"`
	CommandType   string `json:"commandType"`
	CommandText   string `json:"commandText"`
	TargetHost    string `json:"targetHost"`
	Timeout       int    `json:"timeout"`
}

type CommandResponse struct {
	CommandId   string `json:"commandId"`
	Status      string `json:"status"`
	ExitCode    int    `json:"exitCode"`
	Output      string `json:"output"`
	ErrorMsg    string `json:"errorMsg"`
	Timestamp   int64  `json:"timestamp"`
}

type ClusterConfig struct {
	ClusterName   string `json:"clusterName"`
	ClusterId     string `json:"clusterId"`
	ConfigType    string `json:"configType"`
	Filename      string `json:"filename"`
	Content       string `json:"content"`
	Version       int    `json:"version"`
}

type ActionResult struct {
	TaskId       string `json:"taskId"`
	Status       string `json:"status"`
	Message      string `json:"message"`
	Timestamp    int64  `json:"timestamp"`
}

type HeartbeatResponse struct {
	Commands []CommandRequest `json:"commands"`
	Actions  []ActionResult   `json:"actions"`
}