package handler

import (
	"net/http"
	"strconv"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type OperationsHandler struct {
	svc *service.OperationsService
}

func NewOperationsHandler(svc *service.OperationsService) *OperationsHandler {
	return &OperationsHandler{svc: svc}
}

func (h *OperationsHandler) CreateRequest(c *gin.Context) {
	var body models.CreateRequestBody
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	userName := c.GetString("userName")
	if userName == "" {
		userName = "anonymous"
	}

	request, err := h.svc.CreateActionRequest(&body, userName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, request)
}

func (h *OperationsHandler) GetRequests(c *gin.Context) {
	requests, err := h.svc.GetAllRequests()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, requests)
}

func (h *OperationsHandler) GetRequest(c *gin.Context) {
	requestIdStr := c.Param("id")
	requestId, err := strconv.ParseUint(requestIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request ID"})
		return
	}

	request, err := h.svc.GetRequestById(uint(requestId))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, request)
}

func (h *OperationsHandler) UpdateRequestStatus(c *gin.Context) {
	requestIdStr := c.Param("id")
	requestId, err := strconv.ParseUint(requestIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request ID"})
		return
	}

	var body struct {
		Status string `json:"status" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if err := h.svc.UpdateRequestStatus(uint(requestId), body.Status); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Request status updated"})
}

func (h *OperationsHandler) GetTasksByRequest(c *gin.Context) {
	requestIdStr := c.Param("id")
	requestId, err := strconv.ParseUint(requestIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request ID"})
		return
	}

	tasks, err := h.svc.GetTasksByRequest(uint(requestId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, tasks)
}

func (h *OperationsHandler) UpdateTaskStatus(c *gin.Context) {
	taskIdStr := c.Param("taskId")
	taskId, err := strconv.ParseUint(taskIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid task ID"})
		return
	}

	var body struct {
		Status     string `json:"status" binding:"required"`
		OutputLog  string `json:"outputLog"`
		ErrorLog   string `json:"errorLog"`
		Exitcode   *int   `json:"exitcode"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if err := h.svc.UpdateTaskStatus(uint(taskId), body.Status, body.OutputLog, body.ErrorLog, body.Exitcode); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Task status updated"})
}

func (h *OperationsHandler) RetryTask(c *gin.Context) {
	taskIdStr := c.Param("taskId")
	taskId, err := strconv.ParseUint(taskIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid task ID"})
		return
	}

	if err := h.svc.RetryTask(uint(taskId)); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Task retry initiated"})
}

func (h *OperationsHandler) ExecuteOperation(c *gin.Context) {
	var body models.ExecuteCommandBody
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	operation, err := h.svc.ExecuteServiceOperation(&body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, operation)
}

func (h *OperationsHandler) GetServiceOperations(c *gin.Context) {
	serviceIdStr := c.Param("serviceId")
	serviceId, err := strconv.ParseUint(serviceIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid service ID"})
		return
	}

	operations, err := h.svc.GetServiceOperations(uint(serviceId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, operations)
}

func (h *OperationsHandler) GetAllOperations(c *gin.Context) {
	operations, err := h.svc.GetAllServiceOperations()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, operations)
}

func (h *OperationsHandler) UpdateOperationResult(c *gin.Context) {
	opIdStr := c.Param("id")
	opId, err := strconv.ParseUint(opIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid operation ID"})
		return
	}

	var body struct {
		Status       string `json:"status" binding:"required"`
		Output       string `json:"output"`
		ErrorMessage string `json:"errorMessage"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if err := h.svc.UpdateOperationResult(uint(opId), body.Status, body.Output, body.ErrorMessage); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Operation result updated"})
}

func (h *OperationsHandler) GetOperationStats(c *gin.Context) {
	stats, err := h.svc.GetOperationStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (h *OperationsHandler) CreateAuditLog(c *gin.Context) {
	var body struct {
		Action     string `json:"action" binding:"required"`
		Resource   string `json:"resource" binding:"required"`
		ResourceID string `json:"resourceId"`
		Details    string `json:"details"`
		UserName   string `json:"userName"`
		IPAddress  string `json:"ipAddress"`
		Result     string `json:"result"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	if body.Result == "" {
		body.Result = "SUCCESS"
	}

	if err := h.svc.CreateAuditLog(body.Action, body.Resource, body.ResourceID, body.Details, body.UserName, body.IPAddress, body.Result); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Audit log created"})
}

func (h *OperationsHandler) GetAuditLogs(c *gin.Context) {
	limitStr := c.Query("limit")
	limit := 100
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil {
			limit = l
		}
	}

	logs, err := h.svc.GetAuditLogs(limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, logs)
}

func (h *OperationsHandler) RegisterRoutes(r *gin.RouterGroup) {
	requests := r.Group("/requests")
	{
		requests.POST("", h.CreateRequest)
		requests.GET("", h.GetRequests)
		requests.GET("/:id", h.GetRequest)
		requests.PUT("/:id/status", h.UpdateRequestStatus)
		requests.GET("/:id/tasks", h.GetTasksByRequest)
	}

	tasks := r.Group("/tasks")
	{
		tasks.PUT("/:taskId/status", h.UpdateTaskStatus)
		tasks.POST("/:taskId/retry", h.RetryTask)
	}

	operations := r.Group("/operations")
	{
		operations.POST("", h.ExecuteOperation)
		operations.GET("", h.GetAllOperations)
		operations.GET("/stats", h.GetOperationStats)
		operations.GET("/service/:serviceId", h.GetServiceOperations)
		operations.PUT("/:id/result", h.UpdateOperationResult)
	}

	audit := r.Group("/audit")
	{
		audit.POST("", h.CreateAuditLog)
		audit.GET("", h.GetAuditLogs)
	}
}