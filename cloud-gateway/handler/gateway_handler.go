package handler

import (
	"net/http"
	"strconv"

	"github.com/cloudrealm/cloud-gateway/models"
	"github.com/cloudrealm/cloud-gateway/service"
	"github.com/gin-gonic/gin"
)

type GatewayHandler struct {
	proxySvc *service.ProxyService
}

func NewGatewayHandler(proxySvc *service.ProxyService) *GatewayHandler {
	return &GatewayHandler{proxySvc: proxySvc}
}

func (h *GatewayHandler) ProxyRequest(c *gin.Context) {
	route := h.proxySvc.FindRoute(c)
	if route == nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error":   "No matching route",
			"message": "No route found for the requested path",
		})
		return
	}

	if err := h.proxySvc.ProxyRequest(c, route); err != nil {
		c.JSON(http.StatusBadGateway, gin.H{
			"error":   "Proxy error",
			"message": err.Error(),
		})
	}
}

func (h *GatewayHandler) GetRoutes(c *gin.Context) {
	routes := h.proxySvc.GetRoutes()
	c.JSON(http.StatusOK, routes)
}

func (h *GatewayHandler) AddRoute(c *gin.Context) {
	var route models.Route
	if err := c.ShouldBindJSON(&route); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	routes := h.proxySvc.GetRoutes()
	routes = append(routes, route)
	h.proxySvc.SetRoutes(routes)

	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Route added", "route": route})
}

func (h *GatewayHandler) UpdateRoute(c *gin.Context) {
	id := c.Param("id")

	var route models.Route
	if err := c.ShouldBindJSON(&route); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	route.ID = id
	routes := h.proxySvc.GetRoutes()

	for i, r := range routes {
		if r.ID == id {
			routes[i] = route
			h.proxySvc.SetRoutes(routes)
			c.JSON(http.StatusOK, gin.H{"success": true, "message": "Route updated", "route": route})
			return
		}
	}

	c.JSON(http.StatusNotFound, gin.H{"error": "Route not found"})
}

func (h *GatewayHandler) DeleteRoute(c *gin.Context) {
	id := c.Param("id")

	routes := h.proxySvc.GetRoutes()
	newRoutes := make([]models.Route, 0)
	found := false

	for _, r := range routes {
		if r.ID != id {
			newRoutes = append(newRoutes, r)
		} else {
			found = true
		}
	}

	if !found {
		c.JSON(http.StatusNotFound, gin.H{"error": "Route not found"})
		return
	}

	h.proxySvc.SetRoutes(newRoutes)
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "Route deleted"})
}

func (h *GatewayHandler) GetCircuitBreakerStatus(c *gin.Context) {
	serviceName := c.Param("serviceName")

	status := h.proxySvc.GetCircuitBreakerStatus(serviceName)
	c.JSON(http.StatusOK, status)
}

func (h *GatewayHandler) GetServiceEndpoints(c *gin.Context) {
	serviceName := c.Query("serviceName")

	if serviceName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "serviceName is required"})
		return
	}

	endpoints := h.proxySvc.GetServiceEndpoints(serviceName)
	c.JSON(http.StatusOK, endpoints)
}

func (h *GatewayHandler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "ok",
		"service": "cloud-gateway",
	})
}

func (h *GatewayHandler) GetAccessLogs(c *gin.Context) {
	path := c.Query("path")
	pageStr := c.DefaultQuery("page", "0")
	sizeStr := c.DefaultQuery("size", "20")

	page, _ := strconv.Atoi(pageStr)
	size, _ := strconv.Atoi(sizeStr)

	logs, total := h.proxySvc.GetAccessLogs(path, page, size)

	c.JSON(http.StatusOK, gin.H{
		"data":     logs,
		"total":    total,
		"page":     page,
		"size":     size,
	})
}

func (h *GatewayHandler) RegisterRoutes(r *gin.Engine) {
	r.GET("/health", h.HealthCheck)

	api := r.Group("/api/gateway")
	{
		api.GET("/routes", h.GetRoutes)
		api.POST("/routes", h.AddRoute)
		api.PUT("/routes/:id", h.UpdateRoute)
		api.DELETE("/routes/:id", h.DeleteRoute)

		api.GET("/circuit/:serviceName", h.GetCircuitBreakerStatus)
		api.GET("/endpoints", h.GetServiceEndpoints)
		api.GET("/logs", h.GetAccessLogs)
	}
}