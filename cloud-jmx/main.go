package main

import (
	"log"
	"os"

	"github.com/cloudrealm/cloud-jmx/handler"
	"github.com/cloudrealm/cloud-jmx/models"
	"github.com/cloudrealm/cloud-jmx/service"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

func main() {
	dbUser := getEnv("DB_USER", "root")
	dbPass := getEnv("DB_PASS", "password")
	dbHost := getEnv("DB_HOST", "localhost")
	dbPort := getEnv("DB_PORT", "3306")
	dbName := getEnv("DB_NAME", "cloud_jmx")

	dsn := dbUser + ":" + dbPass + "@tcp(" + dbHost + ":" + dbPort + ")/" + dbName + "?charset=utf8mb4&parseTime=True&loc=Local"

	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Printf("Warning: Database connection failed: %v. Running in mock mode.", err)
		db = nil
	}

	if db != nil {
		err = db.AutoMigrate(
			&models.JMXTarget{},
			&models.JMXMetric{},
			&models.JMXAttribute{},
			&models.JMXConnection{},
			&models.CollectConfig{},
			&models.JMXHeapMemory{},
			&models.JMXThreading{},
			&models.JMXGarbageCollector{},
			&models.JMXClassLoading{},
			&models.JMXRuntime{},
			&models.JMXMemoryPool{},
		)
		if err != nil {
			log.Printf("Warning: AutoMigrate failed: %v", err)
		}
	}

	jmxService := service.NewJMXService(db)
	jmxHandler := handler.NewJMXHandler(jmxService)

	r := gin.Default()

	r.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	api := r.Group("/api/jmx")
	{
		jmxHandler.RegisterRoutes(api)
	}

	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok", "service": "cloud-jmx"})
	})

	port := getEnv("PORT", "9090")
	log.Printf("Cloud JMX starting on port %s", port)
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