package main

import (
	"flag"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"runtime"
	"strconv"
	"strings"
	"syscall"

	"github.com/cloudrealm/cloud-agent/handler"
	"github.com/cloudrealm/cloud-agent/models"
	"github.com/cloudrealm/cloud-agent/service"
	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"
)

var (
	logger       *logrus.Logger
	serverURL    string
	agentID      string
	heartbeatInt int
	maxCon       int
)

func init() {
	logger = logrus.New()
	logger.SetLevel(logrus.InfoLevel)
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})
}

func main() {
	flag.StringVar(&serverURL, "server", "http://localhost:8080", "Server URL")
	flag.StringVar(&agentID, "id", "", "Agent ID")
	flag.IntVar(&heartbeatInt, "heartbeat", 5, "Heartbeat interval in seconds")
	flag.IntVar(&maxCon, "max-concurrent", 5, "Max concurrent commands")
	flag.Parse()

	logger.Infof("Cloud Agent starting...")
	logger.Infof("Server URL: %s", serverURL)
	logger.Infof("Agent ID: %s", agentID)

	executor := service.NewCommandExecutor(logger, maxCon)
	executor.Start()

	componentMgr := service.NewComponentManager(logger)
	alertMgr := service.NewAlertManager(logger, 100)
	configCache := service.NewConfigCache(logger)
	serverClient := service.NewServerClient(serverURL, logger)

	hostname, _ := os.Hostname()
	regReq := &models.RegistrationRequest{
		AgentId:    agentID,
		HostName:   hostname,
		IPAddress:  getLocalIP(),
		Version:    "1.0.0",
		OSType:     runtime.GOOS,
		OSVersion:  runtime.GOARCH,
		CPUCount:   runtime.NumCPU(),
		MemoryTotal: getMemoryTotal(),
		Metadata:   make(map[string]string),
	}

	if _, err := serverClient.Register(regReq); err != nil {
		logger.Warnf("Registration failed: %v (continuing without registration)", err)
	}

	heartbeatSvc := service.NewHeartbeatService(serverClient, executor, componentMgr, alertMgr, logger)
	heartbeatSvc.Start(heartbeatInt)

	r := gin.Default()
	r.Use(gin.Logger())
	r.Use(gin.Recovery())

	r.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	agentHandler := handler.NewAgentHandler(executor, serverClient, componentMgr, alertMgr, configCache)
	agentHandler.RegisterRoutes(r)

	go func() {
		for result := range executor.Results() {
			logger.Infof("Command %s completed: %s", result.CommandId, result.Status)
			if err := serverClient.ReportCommandResult(result); err != nil {
				logger.Warnf("Failed to report command result: %v", err)
			}
		}
	}()

	port := os.Getenv("PORT")
	if port == "" {
		port = "8123"
	}

	go func() {
		logger.Infof("Agent HTTP server starting on port %s", port)
		if err := r.Run(":" + port); err != nil {
			logger.Fatalf("Failed to start server: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	logger.Info("Shutting down...")
	heartbeatSvc.Stop()
	executor.Stop()
	logger.Info("Cloud Agent stopped")
}

func getLocalIP() string {
	addrs, err := net.Interfaces()
	if err != nil {
		return "127.0.0.1"
	}
	for _, addr := range addrs {
		if addr.Flags&net.FlagUp == 0 || addr.Flags&net.FlagLoopback != 0 {
			continue
		}
		if addrs, err := addr.Addrs(); err == nil && len(addrs) > 0 {
			for _, a := range addrs {
				if ip := a.(*net.IPNet).IP.To4(); ip != nil {
					return ip.String()
				}
			}
		}
	}
	return "127.0.0.1"
}

func getMemoryTotal() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "OS", "get", "TotalVisibleMemorySize", "/value")
		output, _ := cmd.Output()
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "TotalVisibleMemorySize") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						return val * 1024
					}
				}
			}
		}
	}
	cmd := exec.Command("sh", "-c", "free -b 2>/dev/null | awk '/Mem:/ {print $2}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 8 * 1024 * 1024 * 1024
}

func getMemoryUsed() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "OS", "get", "FreePhysicalMemory", "/value")
		output, _ := cmd.Output()
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "FreePhysicalMemory") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						total := getMemoryTotal()
						return total - (val * 1024)
					}
				}
			}
		}
	}
	cmd := exec.Command("sh", "-c", "free -b 2>/dev/null | awk '/Mem:/ {print $3}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 4 * 1024 * 1024 * 1024
}

func getDiskTotal() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "logicaldisk", "get", "size", "/value")
		output, _ := cmd.Output()
		var total int64
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "Size=") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						total += val
					}
				}
			}
		}
		if total > 0 {
			return total
		}
	}
	cmd := exec.Command("sh", "-c", "df -B1 2>/dev/null | awk 'NR>1 {sum+=$2} END {print sum}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 100 * 1024 * 1024 * 1024
}

func getDiskUsed() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "logicaldisk", "get", "size,freespace", "/value")
		output, _ := cmd.Output()
		var totalSize, freeSize int64
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "Size=") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						totalSize += val
					}
				}
			}
			if strings.Contains(line, "FreeSpace=") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						freeSize += val
					}
				}
			}
		}
		if totalSize > 0 {
			return totalSize - freeSize
		}
	}
	cmd := exec.Command("sh", "-c", "df -B1 2>/dev/null | awk 'NR>1 {sum+=$3} END {print sum}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 50 * 1024 * 1024 * 1024
}

func getCPUUsage() float64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "cpu", "get", "loadpercentage", "/value")
		output, _ := cmd.Output()
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "LoadPercentage") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64); err == nil {
						return val
					}
				}
			}
		}
	}
	cmd := exec.Command("sh", "-c", "top -bn1 | grep 'Cpu' | awk '{print $2}' | cut -d'%' -f1")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseFloat(strings.TrimSpace(string(output)), 64); err == nil {
			return val
		}
	}
	return 0.0
}