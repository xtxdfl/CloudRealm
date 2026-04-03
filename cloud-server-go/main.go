package main

import (
	"log"
	"os"
	"strconv"
	"time"

	"github.com/cloudrealm/cloud-server-go/handler"
	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
	"gopkg.in/yaml.v3"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type Config struct {
	Server   ServerConfig   `yaml:"server"`
	Database DatabaseConfig `yaml:"database"`
	Logging  LoggingConfig  `yaml:"logging"`
	Agent    AgentConfig    `yaml:"agent"`
}

type ServerConfig struct {
	Host         string `yaml:"host"`
	Port         string `yaml:"port"`
	Mode         string `yaml:"mode"`
	ReadTimeout  string `yaml:"read_timeout"`
	WriteTimeout string `yaml:"write_timeout"`
}

type DatabaseConfig struct {
	Host            string `yaml:"host"`
	Port            int    `yaml:"port"`
	Username        string `yaml:"username"`
	Password        string `yaml:"password"`
	Name            string `yaml:"name"`
	Charset         string `yaml:"charset"`
	MaxIdleConns    int    `yaml:"max_idle_conns"`
	MaxOpenConns    int    `yaml:"max_open_conns"`
	ConnMaxLifetime int    `yaml:"conn_max_lifetime"`
}

type LoggingConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
	Output string `yaml:"output"`
}

type AgentConfig struct {
	HeartbeatInterval int `yaml:"heartbeat_interval"`
	Timeout           int `yaml:"timeout"`
	RetryCount        int `yaml:"retry_count"`
}

func loadConfig() *Config {
	config := &Config{}
	configFile := "resources/application.yml"
	if _, err := os.Stat(configFile); err != nil {
		configFile = "c:/yj/CloudRealm/cloud-server-go/resources/application.yml"
	}
	if _, err := os.Stat(configFile); err != nil {
		log.Printf("Config file not found, using defaults")
		return nil
	}
	data, err := os.ReadFile(configFile)
	if err != nil {
		log.Printf("Failed to read config: %v", err)
		return nil
	}
	if err := yaml.Unmarshal(data, config); err != nil {
		log.Printf("Failed to parse config: %v", err)
		return nil
	}
	return config
}

func main() {
	cfg := loadConfig()
	
	var dbUser, dbPass, dbHost, dbPort, dbName string
	if cfg != nil {
		dbUser = cfg.Database.Username
		dbPass = cfg.Database.Password
		dbHost = cfg.Database.Host
		dbPort = strconv.Itoa(cfg.Database.Port)
		dbName = cfg.Database.Name
	} else {
		dbUser = getEnv("DB_USER", "root")
		dbPass = getEnv("DB_PASS", "123456")
		dbHost = getEnv("DB_HOST", "172.25.147.213")
		dbPort = getEnv("DB_PORT", "3306")
		dbName = getEnv("DB_NAME", "cloud")
	}

	dsn := dbUser + ":" + dbPass + "@tcp(" + dbHost + ":" + dbPort + ")/" + dbName + "?charset=utf8mb4&parseTime=True&loc=Local"
	
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		log.Printf("Warning: Database connection failed: %v. Running in mock mode.", err)
		db = nil
	}

	if db != nil {
		err = db.AutoMigrate(
			&models.Service{},
			&models.ServiceDependency{},
			&models.ServiceOperationAudit{},
			&models.ServiceHostMapping{},
			&models.Host{},
			&models.HostOperationLog{},
			&models.HostTagCategory{},
			&models.HostTag{},
			&models.HostTagMapping{},
			&models.DataCatalog{},
			&models.DataAsset{},
			&models.DataLineage{},
			&models.DataAssetCatalog{},
			&models.DataQualityRule{},
			&models.DataQualityResult{},
			&models.User{},
			&models.Role{},
			&models.Permission{},
			&models.UserRole{},
			&models.UserAuthentication{},
			&models.Tenant{},
			&models.RolePermission{},
			&models.ActionRequest{},
			&models.Stage{},
			&models.HostRoleCommand{},
			&models.ServiceOperation{},
			&models.AuditLog{},
			&models.Anomaly{},
			&models.Prediction{},
			&models.RootCause{},
			&models.MetricAnomaly{},
			&models.AlertRule{},
			&models.AdminPrincipal{},
			&models.UserOperationLog{},
			&models.RoleOperationLog{},
			&models.HostMetricData{},
			&models.JMXMetric{},
			&models.HostMetric{},
			&models.ServiceMetric{},
			&models.MetricThreshold{},
			&models.AlertEvent{},
			&models.StackVersion{},
			&models.StackPackage{},
			&models.Repository{},
			&models.HostRegister{},
		)
		if err != nil {
			log.Printf("Warning: AutoMigrate failed: %v", err)
		}
	}

	svcService := service.NewServiceService(db)
	hostService := service.NewHostService(db)
	svcHandler := handler.NewServiceHandler(svcService, hostService)
	
	go func() {
		time.Sleep(2 * time.Second)
		if err := svcService.InitDefaultDependencies(); err != nil {
			log.Printf("Warning: InitDefaultDependencies failed: %v", err)
		}
	}()

	hostHandler := handler.NewHostHandler(hostService)

	agentHandler := handler.NewAgentHandler(hostService)

	tagService := service.NewTagService(db)
	tagHandler := handler.NewTagHandler(tagService)

	dataMarketService := service.NewDataMarketService(db)
	dataMarketHandler := handler.NewDataMarketHandler(dataMarketService)

	securityService := service.NewSecurityService(db)
	securityHandler := handler.NewSecurityHandler(securityService)

	operationsService := service.NewOperationsService(db)
	operationsHandler := handler.NewOperationsHandler(operationsService)

	aiopsService := service.NewAIOpsService(db)
	aiopsHandler := handler.NewAIOpsHandler(aiopsService)

	monitorService := service.NewMonitorService(db)
	monitorHandler := handler.NewMonitorHandler(monitorService)

	deploymentService := service.NewDeploymentService(db)
	deploymentHandler := handler.NewDeploymentHandler(deploymentService)

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

	api := r.Group("/api")
	{
		services := api.Group("/services")
		{
			services.GET("", svcHandler.GetServices)
			services.POST("", svcHandler.CreateService)
			services.GET("/stats", svcHandler.GetServiceStats)
			services.GET("/operations", svcHandler.GetServiceOperations)
			services.GET("/dependencies", svcHandler.GetAllDependencies)

			services.GET("/:name", svcHandler.GetService)
			services.POST("/:name/start", svcHandler.StartService)
			services.POST("/:name/stop", svcHandler.StopService)
			services.POST("/:name/restart", svcHandler.RestartService)
			services.DELETE("/:name", svcHandler.DeleteService)
			services.GET("/:name/dependencies", svcHandler.CheckDependencies)
			services.GET("/:name/dependencies/detail", svcHandler.GetDependenciesDetail)
			services.GET("/:name/config", svcHandler.GetServiceConfig)
			services.GET("/:name/operations", svcHandler.GetServiceOperationDetails)
			services.POST("/:name/operations", svcHandler.RecordOperation)
			services.POST("/:name/refresh", svcHandler.RefreshService)
		}

		hosts := api.Group("/hosts")
		hostHandler.RegisterRoutes(hosts)

		agent := api.Group("/agent")
		agentHandler.RegisterRoutes(agent)

		monitorHosts := api.Group("/hosts-metrics")
		monitorHandler.RegisterHostsRoutes(monitorHosts)

		tags := api.Group("/tags")
		tagHandler.RegisterRoutes(tags)

		dataMarket := api.Group("/datamarket")
		dataMarketHandler.RegisterRoutes(dataMarket)

		securityHandler.RegisterRoutes(api)

		actionQueue := api.Group("/action-queue")
		operationsHandler.RegisterRoutes(actionQueue)

		aiops := api.Group("/aiops")
		aiopsHandler.RegisterRoutes(aiops)

		monitorHandler.RegisterRoutes(api)

		deploy := api.Group("/deploy")
		deploymentHandler.RegisterRoutes(deploy)
	}

	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	host := "0.0.0.0"
	port := "8080"
	if cfg != nil {
		if cfg.Server.Host != "" {
			host = cfg.Server.Host
		}
		if cfg.Server.Port != "" {
			port = cfg.Server.Port
		}
	} else if envHost := os.Getenv("HOST"); envHost != "" {
		host = envHost
	}
	if envPort := os.Getenv("PORT"); envPort != "" {
		port = envPort
	}
	addr := host + ":" + port
	log.Printf("Cloud Server Go starting on %s", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}