package models

import (
	"time"
)

type HostOperationLog struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	HostID          uint      `gorm:"column:host_id" json:"hostId"`
	HostName        string    `gorm:"column:host_name;size:255" json:"hostName"`
	HostIP          string    `gorm:"column:host_ip;size:255" json:"hostIp"`
	Operation       string    `gorm:"column:operation;size:50;not null" json:"operation"`
	OperationStatus string    `gorm:"column:operation_status;size:20;not null" json:"operationStatus"`
	StatusBefore    string    `gorm:"column:status_before;size:20" json:"statusBefore"`
	StatusAfter     string    `gorm:"column:status_after;size:20" json:"statusAfter"`
	Operator        string    `gorm:"column:operator;size:100" json:"operator"`
	OperatorIP      string    `gorm:"column:operator_ip;size:50" json:"operatorIp"`
	RequestParams   string    `gorm:"column:request_params;type:text" json:"requestParams"`
	ResponseResult  string    `gorm:"column:response_result;type:text" json:"responseResult"`
	ErrorMessage    string    `gorm:"column:error_message;size:1000" json:"errorMessage"`
	DurationMs      int64     `gorm:"column:duration_ms" json:"durationMs"`
	OperationTime   int64     `gorm:"column:operation_time;not null" json:"operationTime"`
	CreatedTime     int64     `gorm:"column:created_time;not null" json:"createdTime"`
	CreatedAt       time.Time `json:"createdAt"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

func (HostOperationLog) TableName() string {
	return "host_operation_log"
}