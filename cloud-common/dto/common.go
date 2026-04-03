package dto

import (
	"time"
)

type AuditLogDTO struct {
	TraceID   string    `json:"traceId"`
	Action    string    `json:"action"`
	Resource  string    `json:"resource"`
	Timestamp time.Time `json:"timestamp"`
}

type PageRequest struct {
	Page     int `json:"page"`
	PageSize int `json:"pageSize"`
}

type PageResponse struct {
	Data       interface{} `json:"data"`
	Total      int64       `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"pageSize"`
	TotalPages int         `json:"totalPages"`
}

type ApiResponse struct {
	Success bool        `json:"success"`
	Message string      `json:"message"`
	Data    interface{} `json:"data"`
	Error   string      `json:"error,omitempty"`
}

type ErrorResponse struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
}

type RequestContext struct {
	TraceID    string
	UserID     string
	UserName   string
	Roles      []string
	IPAddress  string
	UserAgent  string
	Timestamp  time.Time
	Metadata   map[string]string
}