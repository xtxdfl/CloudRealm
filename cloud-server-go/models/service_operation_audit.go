package models

import (
	"time"
)

type ServiceOperationAudit struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	ServiceName     string    `gorm:"column:service_name;not null;size:100;index" json:"serviceName"`
	Operation       string    `gorm:"column:operation;not null;size:20" json:"operation"`
	OperationStatus string    `gorm:"column:operation_status;not null;size:20" json:"operationStatus"`
	StatusBefore    string    `gorm:"column:status_before;size:20" json:"statusBefore"`
	StatusAfter     string    `gorm:"column:status_after;size:20" json:"statusAfter"`
	Operator        string    `gorm:"column:operator;size:100" json:"operator"`
	OperationTime   int64     `gorm:"column:operation_time;not null" json:"operationTime"`
	DurationMs      *int64    `gorm:"column:duration_ms;default:0" json:"durationMs"`
	ErrorMessage    string    `gorm:"column:error_message;type:text" json:"errorMessage"`
	CreatedTime     int64     `gorm:"column:created_time" json:"createdTime"`
	CreatedAt       time.Time `json:"createdAt"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

func (ServiceOperationAudit) TableName() string {
	return "service_operation_audit"
}

type OperationRecord struct {
	ID            uint   `json:"id"`
	ServiceName   string `json:"serviceName"`
	Operation     string `json:"operation"`
	OperationStatus string `json:"operationStatus"`
	StatusBefore  string `json:"statusBefore"`
	StatusAfter   string `json:"statusAfter"`
	Operator      string `json:"operator"`
	OperationTime int64  `json:"operationTime"`
	DurationMs    int64  `json:"durationMs"`
	ErrorMessage  string `json:"errorMessage,omitempty"`
}