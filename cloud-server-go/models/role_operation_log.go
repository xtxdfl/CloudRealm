package models

import (
	"time"
)

type RoleOperationLog struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	UserID          int       `gorm:"column:user_id;index" json:"userId"`
	UserName        string    `gorm:"column:user_name" json:"userName"`
	Operation       string    `gorm:"column:operation" json:"operation"`
	TargetType     string    `gorm:"column:target_type" json:"targetType"`
	TargetID       *int      `gorm:"column:target_id" json:"targetId"`
	TargetName     string    `gorm:"column:target_name" json:"targetName"`
	Status         string    `gorm:"column:status" json:"status"`
	ErrorMessage   string    `gorm:"column:error_message" json:"errorMessage"`
	OperationTime  int64     `gorm:"column:operation_time" json:"operationTime"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (RoleOperationLog) TableName() string {
	return "role_operation_log"
}

type UserOperationLog struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	UserID          int       `gorm:"column:user_id;index" json:"userId"`
	UserName        string    `gorm:"column:user_name" json:"userName"`
	Operation      string    `gorm:"column:operation" json:"operation"`
	TargetType     string    `gorm:"column:target_type" json:"targetType"`
	TargetID       *int      `gorm:"column:target_id" json:"targetId"`
	TargetName     string    `gorm:"column:target_name" json:"targetName"`
	Status         string    `gorm:"column:status" json:"status"`
	ErrorMessage   string    `gorm:"column:error_message" json:"errorMessage"`
	OperationTime  int64     `gorm:"column:operation_time" json:"operationTime"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (UserOperationLog) TableName() string {
	return "user_operation_log"
}