package handler

import (
	"net/http"
	"strconv"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type AIOpsHandler struct {
	svc *service.AIOpsService
}

func NewAIOpsHandler(svc *service.AIOpsService) *AIOpsHandler {
	return &AIOpsHandler{svc: svc}
}

func (h *AIOpsHandler) GetAnomalies(c *gin.Context) {
	anomalies, err := h.svc.GetAllAnomalies()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, anomalies)
}

func (h *AIOpsHandler) GetAnomaly(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid anomaly ID"})
		return
	}

	anomaly, err := h.svc.GetAnomalyById(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, anomaly)
}

func (h *AIOpsHandler) CreateAnomaly(c *gin.Context) {
	var anomaly models.Anomaly
	if err := c.ShouldBindJSON(&anomaly); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreateAnomaly(&anomaly)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *AIOpsHandler) ResolveAnomaly(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid anomaly ID"})
		return
	}

	if err := h.svc.ResolveAnomaly(uint(id)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Anomaly resolved"})
}

func (h *AIOpsHandler) DeleteAnomaly(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid anomaly ID"})
		return
	}

	if err := h.svc.DeleteAnomaly(uint(id)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Anomaly deleted"})
}

func (h *AIOpsHandler) GetPredictions(c *gin.Context) {
	predictions, err := h.svc.GetAllPredictions()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, predictions)
}

func (h *AIOpsHandler) CreatePrediction(c *gin.Context) {
	var prediction models.Prediction
	if err := c.ShouldBindJSON(&prediction); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreatePrediction(&prediction)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *AIOpsHandler) GetAnomalyStats(c *gin.Context) {
	stats, err := h.svc.GetAnomalyStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (h *AIOpsHandler) GetPredictionStats(c *gin.Context) {
	stats, err := h.svc.GetPredictionStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (h *AIOpsHandler) AnalyzeRootCause(c *gin.Context) {
	var req models.AnalysisRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	rootCauses, err := h.svc.AnalyzeRootCause(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, rootCauses)
}

func (h *AIOpsHandler) GetMetricAnomalies(c *gin.Context) {
	metricName := c.Query("metric")
	startStr := c.Query("start")
	endStr := c.Query("end")

	var startTime, endTime int64
	if startStr != "" {
		if t, err := strconv.ParseInt(startStr, 10, 64); err == nil {
			startTime = t
		}
	}
	if endStr != "" {
		if t, err := strconv.ParseInt(endStr, 10, 64); err == nil {
			endTime = t
		}
	}

	if startTime == 0 {
		startTime = time.Now().Add(-24 * time.Hour).UnixMilli()
	}
	if endTime == 0 {
		endTime = time.Now().UnixMilli()
	}

	anomalies, err := h.svc.GetMetricAnomalies(metricName, startTime, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, anomalies)
}

func (h *AIOpsHandler) GetAlertRules(c *gin.Context) {
	rules, err := h.svc.GetAlertRules()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, rules)
}

func (h *AIOpsHandler) CreateAlertRule(c *gin.Context) {
	var rule models.AlertRule
	if err := c.ShouldBindJSON(&rule); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreateAlertRule(&rule)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *AIOpsHandler) UpdateAlertRule(c *gin.Context) {
	ruleIdStr := c.Param("id")
	ruleId, err := strconv.ParseUint(ruleIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid rule ID"})
		return
	}

	var rule models.AlertRule
	if err := c.ShouldBindJSON(&rule); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if err := h.svc.UpdateAlertRule(uint(ruleId), &rule); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Alert rule updated"})
}

func (h *AIOpsHandler) DeleteAlertRule(c *gin.Context) {
	ruleIdStr := c.Param("id")
	ruleId, err := strconv.ParseUint(ruleIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid rule ID"})
		return
	}

	if err := h.svc.DeleteAlertRule(uint(ruleId)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Alert rule deleted"})
}

func (h *AIOpsHandler) GetMetricHistory(c *gin.Context) {
	metricName := c.Query("metric")
	hoursStr := c.Query("hours")

	hours := 24
	if hoursStr != "" {
		if h, err := strconv.Atoi(hoursStr); err == nil {
			hours = h
		}
	}

	if metricName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "metric parameter is required"})
		return
	}

	data, err := h.svc.GetMetricHistory(metricName, hours)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, data)
}

func (h *AIOpsHandler) CheckMetricAlert(c *gin.Context) {
	var body struct {
		MetricName string  `json:"metricName" binding:"required"`
		Value      float64 `json:"value" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	triggeredRules := h.svc.CheckMetricAgainstRules(body.MetricName, body.Value)
	c.JSON(http.StatusOK, gin.H{"triggered": len(triggeredRules) > 0, "rules": triggeredRules})
}

func (h *AIOpsHandler) RegisterRoutes(r *gin.RouterGroup) {
	anomalies := r.Group("/aiops/anomalies")
	{
		anomalies.GET("", h.GetAnomalies)
		anomalies.POST("", h.CreateAnomaly)
		anomalies.GET("/stats", h.GetAnomalyStats)
		anomalies.GET("/:id", h.GetAnomaly)
		anomalies.POST("/:id/resolve", h.ResolveAnomaly)
		anomalies.DELETE("/:id", h.DeleteAnomaly)
	}

	predictions := r.Group("/aiops/predictions")
	{
		predictions.GET("", h.GetPredictions)
		predictions.POST("", h.CreatePrediction)
		predictions.GET("/stats", h.GetPredictionStats)
	}

	rootCause := r.Group("/aiops/root-cause")
	{
		rootCause.POST("/analyze", h.AnalyzeRootCause)
	}

	metrics := r.Group("/aiops/metrics")
	{
		metrics.GET("/anomalies", h.GetMetricAnomalies)
		metrics.GET("/history", h.GetMetricHistory)
		metrics.POST("/check", h.CheckMetricAlert)
	}

	rules := r.Group("/aiops/rules")
	{
		rules.GET("", h.GetAlertRules)
		rules.POST("", h.CreateAlertRule)
		rules.PUT("/:id", h.UpdateAlertRule)
		rules.DELETE("/:id", h.DeleteAlertRule)
	}
}