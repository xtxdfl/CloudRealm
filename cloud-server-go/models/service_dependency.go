package models

import (
	"time"
)

type ServiceDependency struct {
	ID                 uint      `gorm:"primaryKey" json:"id"`
	ServiceID          uint      `gorm:"column:service_id;not null;index" json:"serviceId"`
	DependsOnServiceID uint      `gorm:"column:depends_on_service_id;not null" json:"dependsOnServiceId"`
	DependsOnServiceName string   `gorm:"column:depends_on_service_name;not null;size:100" json:"dependsOnServiceName"`
	DependencyType     string    `gorm:"column:dependency_type;size:50;default:REQUIRED" json:"dependencyType"`
	MinVersion         string    `gorm:"column:min_version;size:50" json:"minVersion"`
	MaxVersion         string    `gorm:"column:max_version;size:50" json:"maxVersion"`
	CreatedTime        int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime        int64     `gorm:"column:updated_time" json:"updatedTime"`
	CreatedAt          time.Time `json:"createdAt"`
	UpdatedAt          time.Time `json:"updatedAt"`
}

func (ServiceDependency) TableName() string {
	return "service_dependencies"
}

type DependencyInfo struct {
	ID           uint   `json:"id"`
	ServiceName  string `json:"serviceName"`
	DependencyType string `json:"dependencyType"`
	MinVersion   string `json:"minVersion,omitempty"`
	MaxVersion   string `json:"maxVersion,omitempty"`
	Status       string `json:"status,omitempty"`
	Version      string `json:"version,omitempty"`
}