package handler

import (
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"strconv"
	"time"

	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

func executeServiceOperation(serviceName, operation string) (bool, string, error) {
	pythonScript := "c:\\yj\\CloudRealm\\cloud-common\\cloud_commons\\service_operations.py"
	
	cmd := exec.Command("python3", pythonScript, operation, serviceName, "--json")
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return false, string(output), err
	}
	
	return true, string(output), nil
}

func executeServiceOperationSafe(serviceName, operation string) (bool, string, error) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("Recovered from panic in executeServiceOperation: %v", r)
		}
	}()
	
	pythonScript := "c:\\yj\\CloudRealm\\cloud-common\\cloud_commons\\service_operations.py"
	
	cmd := exec.Command("python3", pythonScript, operation, serviceName, "--json")
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		return false, string(output), err
	}
	
	return true, string(output), nil
}

type ServiceHandler struct {
	svc        *service.ServiceService
	hostSvc    *service.HostService
}

func NewServiceHandler(svc *service.ServiceService, hostSvc *service.HostService) *ServiceHandler {
	return &ServiceHandler{svc: svc, hostSvc: hostSvc}
}

func (h *ServiceHandler) GetServices(c *gin.Context) {
	services, err := h.svc.GetAllServices()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, services)
}

func (h *ServiceHandler) CreateService(c *gin.Context) {
	var request struct {
		Name        string `json:"name" binding:"required"`
		Type       string `json:"type"`
		Version    string `json:"version"`
		Description string `json:"description"`
	}

	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Service name is required"})
		return
	}

	serviceType := request.Type
	if serviceType == "" {
		serviceType = "Custom"
	}
	version := request.Version
	if version == "" {
		version = "1.0.0"
	}

	created, err := h.svc.CreateService(request.Name, serviceType, version, request.Description)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Service already exists or creation failed"})
		return
	}

	c.JSON(http.StatusOK, created)
}

func (h *ServiceHandler) GetServiceStats(c *gin.Context) {
	stats, err := h.svc.GetServiceStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (h *ServiceHandler) GetServiceOperations(c *gin.Context) {
	serviceName := c.Query("serviceName")
	limitStr := c.DefaultQuery("limit", "50")
	limit, _ := strconv.Atoi(limitStr)

	operations, err := h.svc.GetServiceOperations(serviceName, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, operations)
}

func (h *ServiceHandler) GetService(c *gin.Context) {
	name := c.Param("name")
	svc, err := h.svc.GetServiceByName(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if svc == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Service not found"})
		return
	}
	c.JSON(http.StatusOK, svc)
}

func (h *ServiceHandler) StartService(c *gin.Context) {
	name := c.Param("name")
	
	hosts, err := h.svc.GetServiceHosts(name)
	if err != nil || len(hosts) == 0 {
		log.Printf("No hosts found for service %s, using default execution", name)
	}
	
	agentResults := make([]map[string]interface{}, 0)
	for _, host := range hosts {
		if host.AgentStatus == "ONLINE" {
			result := map[string]interface{}{
				"hostname": host.Hostname,
				"ip":       host.IP,
				"status":   "sent_to_agent",
				"action":   "start " + name,
			}
			agentResults = append(agentResults, result)
		}
	}
	
	pySuccess, pyOutput, pyErr := executeServiceOperation(name, "start")
	if !pySuccess {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to start service: %v", pyErr)})
		return
	}
	
	success, err := h.svc.StartService(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !success {
		c.JSON(http.StatusNotFound, gin.H{"message": "Service not found or cannot be started"})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"message":       "Service " + name + " started successfully",
		"details":       pyOutput,
		"agentTargets":  agentResults,
	})
}

func (h *ServiceHandler) StopService(c *gin.Context) {
	name := c.Param("name")
	
	hosts, err := h.svc.GetServiceHosts(name)
	if err != nil || len(hosts) == 0 {
		log.Printf("No hosts found for service %s, using default execution", name)
	}
	
	agentResults := make([]map[string]interface{}, 0)
	for _, host := range hosts {
		if host.AgentStatus == "ONLINE" {
			result := map[string]interface{}{
				"hostname": host.Hostname,
				"ip":       host.IP,
				"status":   "sent_to_agent",
				"action":   "stop " + name,
			}
			agentResults = append(agentResults, result)
		}
	}
	
	pySuccess, pyOutput, pyErr := executeServiceOperation(name, "stop")
	if !pySuccess {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to stop service: %v", pyErr)})
		return
	}
	
	success, err := h.svc.StopService(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !success {
		c.JSON(http.StatusNotFound, gin.H{"message": "Service not found or cannot be stopped"})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"message":       "Service " + name + " stopped successfully",
		"details":       pyOutput,
		"agentTargets":  agentResults,
	})
}

func (h *ServiceHandler) RestartService(c *gin.Context) {
	name := c.Param("name")
	
	hosts, err := h.svc.GetServiceHosts(name)
	if err != nil || len(hosts) == 0 {
		log.Printf("No hosts found for service %s, using default execution", name)
	}
	
	agentResults := make([]map[string]interface{}, 0)
	for _, host := range hosts {
		if host.AgentStatus == "ONLINE" {
			result := map[string]interface{}{
				"hostname": host.Hostname,
				"ip":       host.IP,
				"status":   "sent_to_agent",
				"action":   "restart " + name,
			}
			agentResults = append(agentResults, result)
		}
	}
	
	pySuccess, pyOutput, pyErr := executeServiceOperation(name, "restart")
	if !pySuccess {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to restart service: %v", pyErr)})
		return
	}
	
	success, err := h.svc.RestartService(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !success {
		c.JSON(http.StatusNotFound, gin.H{"message": "Service not found or cannot be restarted"})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"message":      "Service " + name + " restart initiated",
		"job_id":       "job_" + fmt.Sprintf("%d", time.Now().UnixMilli()),
		"details":      pyOutput,
		"agentTargets": agentResults,
	})
}

func (h *ServiceHandler) DeleteService(c *gin.Context) {
	name := c.Param("name")
	result, err := h.svc.DeleteService(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if success, ok := result["success"].(bool); !ok || !success {
		c.JSON(http.StatusBadRequest, result)
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *ServiceHandler) CheckDependencies(c *gin.Context) {
	name := c.Param("name")
	result, err := h.svc.CheckDependencies(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *ServiceHandler) GetDependenciesDetail(c *gin.Context) {
	name := c.Param("name")
	result, err := h.svc.GetServiceDependencies(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *ServiceHandler) GetServiceConfig(c *gin.Context) {
	name := c.Param("name")
	result, err := h.svc.GetServiceConfig(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *ServiceHandler) GetServiceOperationDetails(c *gin.Context) {
	name := c.Param("name")
	limitStr := c.DefaultQuery("limit", "10")
	limit, _ := strconv.Atoi(limitStr)

	operations, err := h.svc.GetServiceOperations(name, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, operations)
}

func (h *ServiceHandler) RecordOperation(c *gin.Context) {
	name := c.Param("name")
	var body struct {
		Operation string `json:"operation" binding:"required"`
		Operator  string `json:"operator"`
	}

	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Operation is required"})
		return
	}

	operator := body.Operator
	if operator == "" {
		operator = "admin"
	}

	result, err := h.svc.RecordServiceOperation(name, body.Operation, operator)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *ServiceHandler) RefreshService(c *gin.Context) {
	name := c.Param("name")
	success, err := h.svc.RefreshServiceStatus(name)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !success {
		c.JSON(http.StatusNotFound, gin.H{"message": "Service not found"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Service " + name + " status refreshed"})
}

func (h *ServiceHandler) GetAllDependencies(c *gin.Context) {
	result, err := h.svc.GetAllServiceDependencies()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}