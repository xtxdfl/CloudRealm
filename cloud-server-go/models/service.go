package models

import (
	"time"
)

type Service struct {
	ID                uint      `gorm:"primaryKey" json:"id"`
	ServiceName       string    `gorm:"column:service_name;uniqueIndex;not null;size:100" json:"serviceName"`
	ServiceType       string    `gorm:"column:service_type;not null;size:50" json:"serviceType"`
	Version           string    `gorm:"column:version;not null;size:50" json:"version"`
	Description       string    `gorm:"column:description;size:500" json:"description"`
	Status            string    `gorm:"column:status;not null;size:20;default:STOPPED" json:"status"`
	ConfigVersion     string    `gorm:"column:config_version;size:50" json:"configVersion"`
	ClusterID         *uint     `gorm:"column:cluster_id" json:"clusterId"`
	CreatedTime       int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime       int64     `gorm:"column:updated_time" json:"updatedTime"`
	LastRestartTime   *int64    `gorm:"column:last_restart_time" json:"lastRestartTime"`
	LastOperationTime *int64    `gorm:"column:last_operation_time" json:"lastOperationTime"`
	LastOperation     string    `gorm:"column:last_operation;size:20" json:"lastOperation"`
	IsDeleted         bool      `gorm:"column:is_deleted;default:false" json:"isDeleted"`
	CreatedAt         time.Time `json:"createdAt"`
	UpdatedAt         time.Time `json:"updatedAt"`
}

func (Service) TableName() string {
	return "services"
}

type ServiceInfo struct {
	Name            string   `json:"name"`
	Version         string   `json:"version"`
	Status          string   `json:"status"`
	ConfigVersion   string   `json:"configVersion"`
	Role            string   `json:"role"`
	Components      []string `json:"components"`
	LastRestartTime *int64   `json:"lastRestartTime,omitempty"`
	LastOperationTime *int64 `json:"lastOperationTime,omitempty"`
	LastOperation   string   `json:"lastOperation,omitempty"`
}

type ServiceStats struct {
	Total   int64 `json:"total"`
	Healthy int64 `json:"healthy"`
	Warning int64 `json:"warning"`
	Stopped int64 `json:"stopped"`
}