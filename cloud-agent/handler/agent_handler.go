package handler

import (
	"net/http"
	"os"
	"runtime"
	"time"

	"github.com/cloudrealm/cloud-agent/models"
	"github.com/cloudrealm/cloud-agent/service"
	"github.com/gin-gonic/gin"
)

type AgentHandler struct {
	executor    *service.CommandExecutor
	serverClient *service.ServerClient
	componentMgr *service.ComponentManager
	alertMgr    *service.AlertManager
	configCache *service.ConfigCache
}

func NewAgentHandler(executor *service.CommandExecutor, serverClient *service.ServerClient, componentMgr *service.ComponentManager, alertMgr *service.AlertManager, configCache *service.ConfigCache) *AgentHandler {
	return &AgentHandler{
		executor:     executor,
		serverClient: serverClient,
		componentMgr: componentMgr,
		alertMgr:    alertMgr,
		configCache: configCache,
	}
}

func (h *AgentHandler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":   "ok",
		"service":  "cloud-agent",
		"uptime":   time.Since(startTime).Seconds(),
		"goroutine": runtime.NumGoroutine(),
	})
}

func (h *AgentHandler) Register(c *gin.Context) {
	var req models.RegistrationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	status, err := h.serverClient.Register(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, status)
}

func (h *AgentHandler) Heartbeat(c *gin.Context) {
	var req models.HeartbeatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	commands, _ := h.serverClient.GetCommands()
	for _, cmd := range commands {
		h.executor.Submit(&cmd)
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Heartbeat received",
	})
}

func (h *AgentHandler) SubmitCommand(c *gin.Context) {
	var req models.CommandRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	h.executor.Submit(&req)

	c.JSON(http.StatusOK, gin.H{
		"success":    true,
		"commandId":  req.CommandId,
		"message":    "Command submitted",
	})
}

func (h *AgentHandler) GetCommandStatus(c *gin.Context) {
	commandId := c.Param("commandId")

	resultChan := h.executor.Results()
	select {
	case result := <-resultChan:
		if result.CommandId == commandId {
			c.JSON(http.StatusOK, result)
			return
		}
	case <-time.After(5 * time.Second):
	}

	c.JSON(http.StatusOK, gin.H{
		"commandId": commandId,
		"status":    "RUNNING",
	})
}

func (h *AgentHandler) GetComponentStatus(c *gin.Context) {
	statuses := h.componentMgr.GetAllStatuses()
	c.JSON(http.StatusOK, statuses)
}

func (h *AgentHandler) StartComponent(c *gin.Context) {
	componentName := c.Param("componentName")
	serviceName := c.Query("service")

	if serviceName == "" {
		serviceName = componentName
	}

	h.componentMgr.Register(componentName, serviceName)
	if err := h.componentMgr.Start(componentName); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Component started",
	})
}

func (h *AgentHandler) StopComponent(c *gin.Context) {
	componentName := c.Param("componentName")

	if err := h.componentMgr.Stop(componentName); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Component stopped",
	})
}

func (h *AgentHandler) GetAlerts(c *gin.Context) {
	alerts := h.alertMgr.GetAlerts()
	c.JSON(http.StatusOK, alerts)
}

func (h *AgentHandler) ClearAlerts(c *gin.Context) {
	h.alertMgr.ClearAlerts()
	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Alerts cleared",
	})
}

func (h *AgentHandler) GetConfigurations(c *gin.Context) {
	clusterName := c.Query("clusterName")
	if clusterName == "" {
		clusterName = "default"
	}

	configs := h.configCache.Get(clusterName)
	c.JSON(http.StatusOK, configs)
}

func (h *AgentHandler) GetHostInfo(c *gin.Context) {
	hostInfo := getHostInfo()
	c.JSON(http.StatusOK, hostInfo)
}

func getHostInfo() map[string]interface{} {
	hostname, _ := os.Hostname()
	return map[string]interface{}{
		"hostname":   hostname,
		"platform":   runtime.GOOS,
		"arch":       runtime.GOARCH,
		"numCPU":     runtime.NumCPU(),
		"goVersion":  runtime.Version(),
	}
}

func (h *AgentHandler) RegisterRoutes(r *gin.Engine) {
	r.GET("/health", h.Health)

	api := r.Group("/api/agent")
	{
		api.POST("/register", h.Register)
		api.POST("/heartbeat", h.Heartbeat)
		api.POST("/commands", h.SubmitCommand)
		api.GET("/commands/:commandId", h.GetCommandStatus)

		api.GET("/components", h.GetComponentStatus)
		api.POST("/components/:componentName/start", h.StartComponent)
		api.POST("/components/:componentName/stop", h.StopComponent)

		api.GET("/alerts", h.GetAlerts)
		api.DELETE("/alerts", h.ClearAlerts)

		api.GET("/configurations", h.GetConfigurations)

		api.GET("/hostinfo", h.GetHostInfo)
	}
}

var startTime = time.Now()