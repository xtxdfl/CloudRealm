package models

import (
	"time"
)

type ServiceHostMapping struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	ServiceID  uint      `gorm:"column:service_id;not null;index" json:"serviceId"`
	ServiceName string   `gorm:"column:service_name;not null;size:100" json:"serviceName"`
	HostID     uint      `gorm:"column:host_id;not null;index" json:"hostId"`
	HostName   string    `gorm:"column:host_name;size:255" json:"hostName"`
	HostIP     string    `gorm:"column:host_ip;size:50" json:"hostIp"`
	Role       string    `gorm:"column:role;size:50" json:"role"`
	Status     string    `gorm:"column:status;size:20;default:ACTIVE" json:"status"`
	CreateTime int64     `gorm:"column:create_time" json:"createTime"`
	UpdateTime int64     `gorm:"column:update_time" json:"updateTime"`
	CreatedAt  time.Time `json:"createdAt"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

func (ServiceHostMapping) TableName() string {
	return "service_host_mapping"
}