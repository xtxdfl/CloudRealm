package main

import (
	"log"
	"os"
	"time"

	"github.com/cloudrealm/cloud-gateway/handler"
	"github.com/cloudrealm/cloud-gateway/middleware"
	"github.com/cloudrealm/cloud-gateway/service"
	"github.com/gin-gonic/gin"
)

func main() {
	port := getEnv("PORT", "8080")

	r := gin.Default()

	r.Use(middleware.Logger())
	r.Use(middleware.RequestID())
	r.Use(middleware.CORSMiddleware())
	r.Use(middleware.PanicRecovery())
	r.Use(middleware.ProxyHeadersMiddleware())

	proxySvc := service.NewProxyService()
	gatewayHandler := handler.NewGatewayHandler(proxySvc)

	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok", "service": "cloud-gateway"})
	})

	api := r.Group("/api/gateway")
	{
		api.GET("/routes", gatewayHandler.GetRoutes)
		api.POST("/routes", gatewayHandler.AddRoute)
		api.PUT("/routes/:id", gatewayHandler.UpdateRoute)
		api.DELETE("/routes/:id", gatewayHandler.DeleteRoute)
		api.GET("/circuit/:serviceName", gatewayHandler.GetCircuitBreakerStatus)
		api.GET("/endpoints", gatewayHandler.GetServiceEndpoints)
		api.GET("/logs", gatewayHandler.GetAccessLogs)
	}

	r.Use(middleware.RateLimiter())
	r.Use(middleware.TimeoutMiddleware(30 * time.Second))

	r.NoRoute(func(c *gin.Context) {
		c.JSON(404, gin.H{
			"error":   "Not Found",
			"message": "The requested path does not exist",
		})
	})

	log.Printf("Cloud Gateway starting on port %s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}