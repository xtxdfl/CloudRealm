package handler

import (
	"net/http"
	"strconv"

	"github.com/cloudrealm/cloud-jmx/models"
	"github.com/cloudrealm/cloud-jmx/service"
	"github.com/gin-gonic/gin"
)

type JMXHandler struct {
	svc *service.JMXService
}

func NewJMXHandler(svc *service.JMXService) *JMXHandler {
	return &JMXHandler{svc: svc}
}

func (h *JMXHandler) GetTargets(c *gin.Context) {
	hostIdStr := c.Query("hostId")
	serviceName := c.Query("serviceName")

	var hostId int
	if hostIdStr != "" {
		if id, err := strconv.Atoi(hostIdStr); err == nil {
			hostId = id
		}
	}

	targets, err := h.svc.GetTargets(hostId, serviceName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, targets)
}

func (h *JMXHandler) GetTarget(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	target, err := h.svc.GetTarget(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Target not found"})
		return
	}
	c.JSON(http.StatusOK, target)
}

func (h *JMXHandler) CreateTarget(c *gin.Context) {
	var target models.JMXTarget
	if err := c.ShouldBindJSON(&target); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.CreateTarget(&target)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *JMXHandler) UpdateTarget(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	var target models.JMXTarget
	if err := c.ShouldBindJSON(&target); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.UpdateTarget(uint(id), &target)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *JMXHandler) DeleteTarget(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	if err := h.svc.DeleteTarget(uint(id)); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Target deleted"})
}

func (h *JMXHandler) GetMetrics(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	objectName := c.Query("objectName")
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

	metrics, err := h.svc.GetMetrics(uint(targetId), objectName, startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, metrics)
}

func (h *JMXHandler) GetLatestMetrics(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	limitStr := c.DefaultQuery("limit", "50")
	limit := 50
	if l, err := strconv.Atoi(limitStr); err == nil {
		limit = l
	}

	metrics, err := h.svc.GetLatestMetrics(uint(targetId), limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, metrics)
}

func (h *JMXHandler) GetHeapMemory(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
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

	data, err := h.svc.GetHeapMemory(uint(targetId), startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *JMXHandler) GetThreading(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
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

	data, err := h.svc.GetThreading(uint(targetId), startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *JMXHandler) GetGarbageCollectors(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	data, err := h.svc.GetGarbageCollectors(uint(targetId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *JMXHandler) GetClassLoading(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	data, err := h.svc.GetClassLoading(uint(targetId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *JMXHandler) GetRuntime(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	data, err := h.svc.GetRuntime(uint(targetId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *JMXHandler) GetMemoryPools(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	data, err := h.svc.GetMemoryPools(uint(targetId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *JMXHandler) GetCollectConfigs(c *gin.Context) {
	serviceName := c.Query("serviceName")

	configs, err := h.svc.GetCollectConfigs(serviceName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, configs)
}

func (h *JMXHandler) CreateCollectConfig(c *gin.Context) {
	var config models.CollectConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.CreateCollectConfig(&config)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *JMXHandler) UpdateCollectConfig(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid config ID"})
		return
	}

	var config models.CollectConfig
	if err := c.ShouldBindJSON(&config); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.UpdateCollectConfig(uint(id), &config)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *JMXHandler) DeleteCollectConfig(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid config ID"})
		return
	}

	if err := h.svc.DeleteCollectConfig(uint(id)); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Config deleted"})
}

func (h *JMXHandler) RecordMetric(c *gin.Context) {
	var metric models.JMXMetric
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

func (h *JMXHandler) TestConnection(c *gin.Context) {
	targetIdStr := c.Param("id")
	targetId, err := strconv.ParseUint(targetIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid target ID"})
		return
	}

	result, err := h.svc.TestConnection(uint(targetId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *JMXHandler) RegisterRoutes(r *gin.RouterGroup) {
	targets := r.Group("/targets")
	{
		targets.GET("", h.GetTargets)
		targets.POST("", h.CreateTarget)
		targets.GET("/:id", h.GetTarget)
		targets.PUT("/:id", h.UpdateTarget)
		targets.DELETE("/:id", h.DeleteTarget)
		targets.POST("/:id/test", h.TestConnection)

		targets.GET("/:id/metrics", h.GetMetrics)
		targets.GET("/:id/metrics/latest", h.GetLatestMetrics)
		targets.GET("/:id/heap", h.GetHeapMemory)
		targets.GET("/:id/threading", h.GetThreading)
		targets.GET("/:id/gc", h.GetGarbageCollectors)
		targets.GET("/:id/classloading", h.GetClassLoading)
		targets.GET("/:id/runtime", h.GetRuntime)
		targets.GET("/:id/mempools", h.GetMemoryPools)
	}

	r.POST("/metrics", h.RecordMetric)

	configs := r.Group("/configs")
	{
		configs.GET("", h.GetCollectConfigs)
		configs.POST("", h.CreateCollectConfig)
		configs.PUT("/:id", h.UpdateCollectConfig)
		configs.DELETE("/:id", h.DeleteCollectConfig)
	}
}