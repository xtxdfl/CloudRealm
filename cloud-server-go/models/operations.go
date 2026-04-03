package models

import (
	"time"
)

type ActionRequest struct {
	ID                  uint      `gorm:"primaryKey" json:"id"`
	RequestID           uint      `gorm:"column:request_id;uniqueIndex" json:"requestId"`
	ClusterID           *uint     `gorm:"column:cluster_id" json:"clusterId"`
	RequestScheduleID   *uint     `gorm:"column:request_schedule_id" json:"requestScheduleId"`
	CommandName         string    `gorm:"column:command_name" json:"commandName"`
	CreateTime          int64     `gorm:"column:create_time" json:"createTime"`
	EndTime             *int64    `gorm:"column:end_time" json:"endTime"`
	ExclusiveExecution  int       `gorm:"column:exclusive_execution;default:0" json:"exclusiveExecution"`
	Inputs              []byte    `gorm:"column:inputs;type:longblob" json:"inputs"`
	RequestContext      string    `gorm:"column:request_context" json:"requestContext"`
	RequestType         string    `gorm:"column:request_type" json:"requestType"`
	StartTime           *int64    `gorm:"column:start_time" json:"startTime"`
	Status              string    `gorm:"column:status;default:'PENDING'" json:"status"`
	DisplayStatus       string    `gorm:"column:display_status;default:'PENDING'" json:"displayStatus"`
	ClusterHostInfo     []byte    `gorm:"column:cluster_host_info;type:longblob" json:"clusterHostInfo"`
	UserName            string    `gorm:"column:user_name" json:"userName"`
	CreatedAt           time.Time `json:"createdAt"`
	UpdatedAt           time.Time `json:"updatedAt"`
}

func (ActionRequest) TableName() string {
	return "request"
}

type Stage struct {
	ID                     uint      `gorm:"primaryKey" json:"id"`
	StageID                uint      `gorm:"column:stage_id;uniqueIndex" json:"stageId"`
	RequestID              uint      `gorm:"column:request_id;not null;index" json:"requestId"`
	ClusterID              *uint     `gorm:"column:cluster_id" json:"clusterId"`
	LogInfo                string    `gorm:"column:log_info" json:"logInfo"`
	RequestContext         string    `gorm:"column:request_context" json:"requestContext"`
	Skippable              int       `gorm:"column:skippable;default:0" json:"skippable"`
	SupportsAutoSkipFailure int      `gorm:"column:supports_auto_skip_failure;default:0" json:"supportsAutoSkipFailure"`
	CommandParams          []byte    `gorm:"column:command_params;type:longblob" json:"commandParams"`
	HostParams             []byte    `gorm:"column:host_params;type:longblob" json:"hostParams"`
	CommandExecutionType   string    `gorm:"column:command_execution_type;default:'STAGE'" json:"commandExecutionType"`
	Status                 string    `gorm:"column:status;default:'PENDING'" json:"status"`
	DisplayStatus          string    `gorm:"column:display_status;default:'PENDING'" json:"displayStatus"`
	CreatedAt              time.Time `json:"createdAt"`
	UpdatedAt              time.Time `json:"updatedAt"`
}

func (Stage) TableName() string {
	return "stage"
}

type HostRoleCommand struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	TaskID           uint      `gorm:"column:task_id;uniqueIndex" json:"taskId"`
	RequestID        uint      `gorm:"column:request_id;not null;index" json:"requestId"`
	StageID          uint      `gorm:"column:stage_id;not null;index" json:"stageId"`
	HostID           *uint     `gorm:"column:host_id" json:"hostId"`
	HostName         string    `gorm:"column:host_name" json:"hostName"`
	Role             string    `gorm:"column:role" json:"role"`
	RoleCommand      string    `gorm:"column:role_command" json:"roleCommand"`
	Status           string    `gorm:"column:status;default:'PENDING'" json:"status"`
	StdError         []byte    `gorm:"column:std_error;type:longblob" json:"stdError"`
	StdOut           []byte    `gorm:"column:std_out;type:longblob" json:"stdOut"`
	OutputLog        string    `gorm:"column:output_log" json:"outputLog"`
	ErrorLog         string    `gorm:"column:error_log" json:"errorLog"`
	StructuredOut    []byte    `gorm:"column:structured_out;type:longblob" json:"structuredOut"`
	Exitcode         *int      `gorm:"column:exitcode" json:"exitcode"`
	StartTime        *int64    `gorm:"column:start_time" json:"startTime"`
	OriginalStartTime *int64   `gorm:"column:original_start_time" json:"originalStartTime"`
	EndTime          *int64    `gorm:"column:end_time" json:"endTime"`
	AttemptCount     int       `gorm:"column:attempt_count;default:0" json:"attemptCount"`
	RetryAllowed     int       `gorm:"column:retry_allowed;default:0" json:"retryAllowed"`
	Event            string    `gorm:"column:event;type:text" json:"event"`
	LastAttemptTime  int64     `gorm:"column:last_attempt_time;default:0" json:"lastAttemptTime"`
	CommandDetail    string    `gorm:"column:command_detail" json:"commandDetail"`
	CreatedAt        time.Time `json:"createdAt"`
	UpdatedAt        time.Time `json:"updatedAt"`
}

func (HostRoleCommand) TableName() string {
	return "host_role_command"
}

type ServiceOperation struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	ServiceID    uint      `gorm:"column:service_id;not null;index" json:"serviceId"`
	ServiceName  string    `gorm:"column:service_name" json:"serviceName"`
	Operation    string    `gorm:"column:operation" json:"operation"`
	Status       string    `gorm:"column:status;default:'PENDING'" json:"status"`
	TargetHosts  string    `gorm:"column:target_hosts;type:text" json:"targetHosts"`
	CommandID    string    `gorm:"column:command_id" json:"commandId"`
	Output       string    `gorm:"column:output;type:text" json:"output"`
	ErrorMessage string    `gorm:"column:error_message" json:"errorMessage"`
	StartTime    *int64    `gorm:"column:start_time" json:"startTime"`
	EndTime      *int64    `gorm:"column:end_time" json:"endTime"`
	DurationMs   *int64    `gorm:"column:duration_ms" json:"durationMs"`
	Operator     string    `gorm:"column:operator" json:"operator"`
	CreatedTime  int64     `gorm:"column:created_time" json:"createdTime"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (ServiceOperation) TableName() string {
	return "service_operations"
}

type AuditLog struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Action      string    `gorm:"column:action" json:"action"`
	Resource    string    `gorm:"column:resource" json:"resource"`
	ResourceID  string    `gorm:"column:resource_id" json:"resourceId"`
	Details     string    `gorm:"column:details;type:text" json:"details"`
	UserID      *int      `gorm:"column:user_id" json:"userId"`
	UserName    string    `gorm:"column:user_name" json:"userName"`
	IPAddress   string    `gorm:"column:ip_address" json:"ipAddress"`
	Result      string    `gorm:"column:result;default:'SUCCESS'" json:"result"`
	CreateTime  int64     `gorm:"column:create_time" json:"createTime"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (AuditLog) TableName() string {
	return "audit_logs"
}

type RequestInfo struct {
	RequestID     uint                 `json:"requestId"`
	CommandName   string               `json:"commandName"`
	RequestContext string              `json:"requestContext"`
	Status        string               `json:"status"`
	DisplayStatus string               `json:"displayStatus"`
	UserName      string               `json:"userName"`
	CreateTime    int64                `json:"createTime"`
	StartTime     *int64               `json:"startTime"`
	EndTime       *int64               `json:"endTime"`
	Stages        []StageInfo          `json:"stages"`
	TaskCount     int                  `json:"taskCount"`
	CompletedCount int                 `json:"completedCount"`
	FailedCount   int                  `json:"failedCount"`
}

type StageInfo struct {
	StageID       uint   `json:"stageId"`
	RequestID     uint   `json:"requestId"`
	RequestContext string `json:"requestContext"`
	Status        string `json:"status"`
	DisplayStatus string `json:"displayStatus"`
	TaskCount     int    `json:"taskCount"`
	Tasks         []TaskInfo `json:"tasks"`
}

type TaskInfo struct {
	TaskID      uint    `json:"taskId"`
	HostName    string  `json:"hostName"`
	Role        string  `json:"role"`
	RoleCommand string  `json:"roleCommand"`
	Status      string  `json:"status"`
	StartTime   *int64  `json:"startTime"`
	EndTime     *int64  `json:"endTime"`
	Exitcode    *int    `json:"exitcode"`
	OutputLog   string  `json:"outputLog"`
	ErrorLog    string  `json:"errorLog"`
}

type CreateRequestBody struct {
	RequestContext string   `json:"requestContext" binding:"required"`
	Hosts          []string `json:"hosts" binding:"required"`
	Role           string   `json:"role" binding:"required"`
	Command        string   `json:"command" binding:"required"`
	ClusterID      *uint    `json:"clusterId"`
}

type OperationStats struct {
	TotalOperations   int64 `json:"totalOperations"`
	PendingCount      int64 `json:"pendingCount"`
	InProgressCount   int64 `json:"inProgressCount"`
	CompletedCount    int64 `json:"completedCount"`
	FailedCount       int64 `json:"failedCount"`
	AverageDurationMs int64 `json:"averageDurationMs"`
}

type AuditLogEntry struct {
	ID         uint   `json:"id"`
	Action     string `json:"action"`
	Resource   string `json:"resource"`
	ResourceID string `json:"resourceId"`
	Details    string `json:"details"`
	UserName   string `json:"userName"`
	IPAddress  string `json:"ipAddress"`
	Result     string `json:"result"`
	CreateTime int64  `json:"createTime"`
}

type ExecuteCommandBody struct {
	ServiceID    uint     `json:"serviceId" binding:"required"`
	ServiceName  string   `json:"serviceName" binding:"required"`
	Operation    string   `json:"operation" binding:"required"`
	TargetHosts  []string `json:"targetHosts"`
	Operator     string   `json:"operator"`
}