package models

import (
	"time"
)

type HostTagCategory struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	CategoryID   uint      `gorm:"column:category_id;uniqueIndex" json:"categoryId"`
	CategoryName string    `gorm:"column:category_name;not null" json:"categoryName"`
	CategoryType string    `gorm:"column:category_type;not null" json:"categoryType"`
	Description  string    `gorm:"column:description" json:"description"`
	Color        string    `gorm:"column:color;default:#6366f1" json:"color"`
	SortOrder    int       `gorm:"column:sort_order;default:0" json:"sortOrder"`
	CreatedTime  int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime  int64     `gorm:"column:updated_time" json:"updatedTime"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (HostTagCategory) TableName() string {
	return "host_tag_categories"
}

type HostTag struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	TagID       uint      `gorm:"column:tag_id;uniqueIndex" json:"tagId"`
	TagName     string    `gorm:"column:tag_name;not null" json:"tagName"`
	CategoryID uint      `gorm:"column:category_id;not null;index" json:"categoryId"`
	Description string   `gorm:"column:description" json:"description"`
	Color       string    `gorm:"column:color;default:#6366f1" json:"color"`
	CreatedTime int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime int64     `gorm:"column:updated_time" json:"updatedTime"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (HostTag) TableName() string {
	return "host_tags"
}

type HostTagMapping struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	HostID     uint      `gorm:"column:host_id;not null;index" json:"hostId"`
	TagID      uint      `gorm:"column:tag_id;not null;index" json:"tagId"`
	CreateTime int64     `gorm:"column:create_time" json:"createTime"`
	CreatedAt  time.Time `json:"createdAt"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

func (HostTagMapping) TableName() string {
	return "host_tag_mapping"
}

type TagInfo struct {
	TagID       uint   `json:"tagId"`
	TagName     string `json:"tagName"`
	CategoryID  uint   `json:"categoryId"`
	CategoryName string `json:"categoryName"`
	Description string `json:"description"`
	Color       string `json:"color"`
	HostCount   int    `json:"hostCount"`
}

type TagCategoryInfo struct {
	CategoryID   uint      `json:"categoryId"`
	CategoryName string    `json:"categoryName"`
	CategoryType string    `json:"categoryType"`
	Description  string    `json:"description"`
	Color        string    `json:"color"`
	SortOrder    int       `json:"sortOrder"`
	TagCount     int       `json:"tagCount"`
	Tags         []TagInfo `json:"tags"`
}