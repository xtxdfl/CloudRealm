package handler

import (
	"net/http"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type AgentHandler struct {
	svc *service.HostService
}

func NewAgentHandler(svc *service.HostService) *AgentHandler {
	return &AgentHandler{svc: svc}
}

func (h *AgentHandler) RegisterAgent(c *gin.Context) {
	var req models.AgentRegistrationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	hostInfo := &models.HostInfo{
		Hostname:      req.HostName,
		IP:            req.IPAddress,
		Cores:         req.CPUCount,
		TotalMemory:   req.MemoryTotal,
		TotalDisk:     req.DiskTotal,
		OSType:        req.OSType,
		OSInfo:        req.OSVersion,
		Status:        "RUNNING",
		AgentStatus:   "ONLINE",
		AgentVersion:  req.Version,
	}

	host, err := h.svc.AddHost(hostInfo)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.AgentStatus{
		AgentID:    host.AgentVersion,
		Status:     "REGISTERED",
		ServerTime: time.Now().UnixMilli(),
	})
}

func (h *AgentHandler) Heartbeat(c *gin.Context) {
	var req models.HeartbeatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	err := h.svc.ProcessAgentHeartbeat(req.AgentId, req.Status, req.CPUUsage, req.MemoryUsed, req.MemoryTotal, req.DiskUsed, req.DiskTotal)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.HeartbeatResponse{
		ServerTime: time.Now().UnixMilli(),
		Status:     "OK",
		Message:    "Heartbeat received",
	})
}

func (h *AgentHandler) RegisterRoutes(r *gin.RouterGroup) {
	r.POST("/register", h.RegisterAgent)
	r.POST("/heartbeat", h.Heartbeat)
}