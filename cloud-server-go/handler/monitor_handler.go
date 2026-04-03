package handler

import (
	"net/http"
	"strconv"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type MonitorHandler struct {
	svc *service.MonitorService
}

func NewMonitorHandler(svc *service.MonitorService) *MonitorHandler {
	return &MonitorHandler{svc: svc}
}

func (h *MonitorHandler) GetHostMetrics(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.Atoi(hostIdStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	startTimeStr := c.Query("startTime")
	endTimeStr := c.Query("endTime")

	var startTime, endTime int64
	if startTimeStr != "" {
		if t, err := strconv.ParseInt(startTimeStr, 10, 64); err == nil {
			startTime = t
		}
	}
	if endTimeStr != "" {
		if t, err := strconv.ParseInt(endTimeStr, 10, 64); err == nil {
			endTime = t
		}
	}

	metrics, err := h.svc.GetHostMetrics(hostId, startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, metrics)
}

func (h *MonitorHandler) GetServiceMetrics(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.Atoi(hostIdStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	serviceName := c.Param("serviceName")
	if serviceName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Service name is required"})
		return
	}

	startTimeStr := c.Query("startTime")
	endTimeStr := c.Query("endTime")

	var startTime, endTime int64
	if startTimeStr != "" {
		if t, err := strconv.ParseInt(startTimeStr, 10, 64); err == nil {
			startTime = t
		}
	}
	if endTimeStr != "" {
		if t, err := strconv.ParseInt(endTimeStr, 10, 64); err == nil {
			endTime = t
		}
	}

	metrics, err := h.svc.GetServiceMetrics(hostId, serviceName, startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, metrics)
}

func (h *MonitorHandler) GetJMXMetrics(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.Atoi(hostIdStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	serviceName := c.Param("serviceName")
	if serviceName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Service name is required"})
		return
	}

	objectName := c.Query("objectName")

	metrics, err := h.svc.GetJMXMetrics(hostId, serviceName, objectName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, metrics)
}

func (h *MonitorHandler) QueryMetrics(c *gin.Context) {
	var query models.MetricQuery
	if err := c.ShouldBindJSON(&query); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.QueryMetrics(&query)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *MonitorHandler) GetThresholds(c *gin.Context) {
	serviceName := c.Query("serviceName")

	thresholds, err := h.svc.GetMetricThresholds(serviceName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, thresholds)
}

func (h *MonitorHandler) CreateThreshold(c *gin.Context) {
	var threshold models.MetricThreshold
	if err := c.ShouldBindJSON(&threshold); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.CreateThreshold(&threshold)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *MonitorHandler) UpdateThreshold(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid threshold ID"})
		return
	}

	var threshold models.MetricThreshold
	if err := c.ShouldBindJSON(&threshold); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.UpdateThreshold(uint(id), &threshold)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *MonitorHandler) DeleteThreshold(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid threshold ID"})
		return
	}

	if err := h.svc.DeleteThreshold(uint(id)); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Threshold deleted"})
}

func (h *MonitorHandler) GetAlertEvents(c *gin.Context) {
	hostIdStr := c.Query("hostId")
	serviceName := c.Query("serviceName")
	status := c.Query("status")
	startTimeStr := c.Query("startTime")
	endTimeStr := c.Query("endTime")
	pageStr := c.DefaultQuery("page", "0")
	sizeStr := c.DefaultQuery("size", "20")

	var hostId *int
	if hostIdStr != "" {
		if id, err := strconv.Atoi(hostIdStr); err == nil && id > 0 {
			hostId = &id
		}
	}

	var startTime, endTime int64
	if startTimeStr != "" {
		if t, err := strconv.ParseInt(startTimeStr, 10, 64); err == nil {
			startTime = t
		}
	}
	if endTimeStr != "" {
		if t, err := strconv.ParseInt(endTimeStr, 10, 64); err == nil {
			endTime = t
		}
	}

	page := 0
	if p, err := strconv.Atoi(pageStr); err == nil {
		page = p
	}

	size := 20
	if s, err := strconv.Atoi(sizeStr); err == nil {
		size = s
	}

	events, total, err := h.svc.GetAlertEvents(hostId, serviceName, status, startTime, endTime, page, size)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"content":       events,
		"totalElements": total,
		"currentPage":   page,
	})
}

func (h *MonitorHandler) ResolveAlert(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid alert ID"})
		return
	}

	if err := h.svc.ResolveAlertEvent(uint(id)); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Alert resolved"})
}

func (h *MonitorHandler) RecordMetric(c *gin.Context) {
	var metric models.HostMetricData
	if err := c.ShouldBindJSON(&metric); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if metric.Timestamp == 0 {
		metric.Timestamp = 0
	}

	if err := h.svc.RecordMetric(&metric); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Metric recorded"})
}

func (h *MonitorHandler) RecordJMXMetric(c *gin.Context) {
	var metric models.JMXMetric
	if err := c.ShouldBindJSON(&metric); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if metric.Timestamp == 0 {
		metric.Timestamp = 0
	}

	if err := h.svc.RecordJMXMetric(&metric); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "JMX metric recorded"})
}

func (h *MonitorHandler) RegisterRoutes(r *gin.RouterGroup) {
	r.POST("/metrics/query", h.QueryMetrics)
	r.POST("/metrics", h.RecordMetric)
	r.POST("/metrics/jmx", h.RecordJMXMetric)

	thresholds := r.Group("/thresholds")
	{
		thresholds.GET("", h.GetThresholds)
		thresholds.POST("", h.CreateThreshold)
		thresholds.PUT("/:id", h.UpdateThreshold)
		thresholds.DELETE("/:id", h.DeleteThreshold)
	}

	alerts := r.Group("/alerts")
	{
		alerts.GET("", h.GetAlertEvents)
		alerts.POST("/:id/resolve", h.ResolveAlert)
	}
}

func (h *MonitorHandler) RegisterHostsRoutes(r *gin.RouterGroup) {
	hosts := r.Group("/hosts/:hostId/metrics")
	{
		hosts.GET("", h.GetHostMetrics)
	}

	services := r.Group("/hosts/:hostId/services/:serviceName/metrics")
	{
		services.GET("", h.GetServiceMetrics)
	}

	jmx := r.Group("/hosts/:hostId/services/:serviceName/jmx")
	{
		jmx.GET("", h.GetJMXMetrics)
	}
}