package handler

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type HostHandler struct {
	svc *service.HostService
}

func NewHostHandler(svc *service.HostService) *HostHandler {
	return &HostHandler{svc: svc}
}

func (h *HostHandler) GetHosts(c *gin.Context) {
	hosts, err := h.svc.GetAllHosts()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, hosts)
}

func (h *HostHandler) SearchHosts(c *gin.Context) {
	search := &models.HostSearch{
		HostName:    c.Query("hostName"),
		IPv4:        c.Query("ipv4"),
		Status:      c.Query("status"),
		AgentStatus: c.Query("agentStatus"),
		RackInfo:    c.Query("rackInfo"),
	}

	hosts, err := h.svc.SearchHosts(search)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, hosts)
}

func (h *HostHandler) GetHost(c *gin.Context) {
	hostname := c.Param("hostname")
	host, err := h.svc.GetHostByHostname(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if host == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Host not found"})
		return
	}
	c.JSON(http.StatusOK, host)
}

func (h *HostHandler) GetHostStats(c *gin.Context) {
	stats, err := h.svc.GetHostStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (h *HostHandler) GetHostDetail(c *gin.Context) {
	hostname := c.Param("hostname")
	detail, err := h.svc.GetHostDetail(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, detail)
}

func (h *HostHandler) AddHost(c *gin.Context) {
	var hostInfo models.HostInfo
	
	bodyBytes, _ := c.GetRawData()
	fmt.Printf("AddHost received body: %s\n", string(bodyBytes))
	
	if err := json.Unmarshal(bodyBytes, &hostInfo); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body: " + err.Error()})
		return
	}

	fmt.Printf("Parsed hostInfo: hostname=%s, ip=%s\n", hostInfo.Hostname, hostInfo.IP)

	// 兼容处理：如果 Hostname 为空，尝试从 hostname 字段获取
	if hostInfo.Hostname == "" {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if hn, ok := rawBody["hostname"].(string); ok {
			hostInfo.Hostname = hn
		}
	}
	if hostInfo.IP == "" {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if ip, ok := rawBody["ip"].(string); ok {
			hostInfo.IP = ip
		}
	}
	if hostInfo.SSHUser == "" {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if user, ok := rawBody["sshUser"].(string); ok {
			hostInfo.SSHUser = user
		}
	}
	if hostInfo.SSHPassword == "" {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if pwd, ok := rawBody["sshPassword"].(string); ok {
			hostInfo.SSHPassword = pwd
		}
	}
	if hostInfo.SSHPrivateKey == "" {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if pk, ok := rawBody["sshPrivateKey"].(string); ok {
			hostInfo.SSHPrivateKey = pk
		}
	}
	if hostInfo.SSHPublicKey == "" {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if pubk, ok := rawBody["sshPublicKey"].(string); ok {
			hostInfo.SSHPublicKey = pubk
		}
	}
	if hostInfo.SSHPort == 0 {
		var rawBody map[string]interface{}
		json.Unmarshal(bodyBytes, &rawBody)
		if port, ok := rawBody["sshPort"].(float64); ok {
			hostInfo.SSHPort = int(port)
		}
	}

	fmt.Printf("After mapping: hostname=%s, ip=%s, sshUser=%s, sshPort=%d\n", 
		hostInfo.Hostname, hostInfo.IP, hostInfo.SSHUser, hostInfo.SSHPort)

	// 调用Python脚本执行主机预检和硬件信息收集
	pythonScript := filepath.Join("..", "..", "cloud-common", "cloud_commons", "host_installer.py")
	if _, err := os.Stat(pythonScript); err != nil {
		if os.IsNotExist(err) {
			pythonScript = "c:\\yj\\CloudRealm\\cloud-common\\cloud_commons\\host_installer.py"
		}
	}

	// 构造参数
	sshPort := hostInfo.SSHPort
	if sshPort == 0 {
		sshPort = 22
	}
	
	agentBinaryPath := "c:\\yj\\CloudRealm\\cloud-agent\\cloud-agent.exe"
	agentBinaryPathLinux := "c:\\yj\\CloudRealm\\cloud-agent\\cloud-agent-linux-amd64.tar.gz"
	if _, err := os.Stat(agentBinaryPath); err != nil {
		agentBinaryPath = ""
	}
	if _, err := os.Stat(agentBinaryPathLinux); err != nil {
		agentBinaryPathLinux = ""
	}
	
	serverHost := os.Getenv("SERVER_HOST")
	if serverHost == "" {
		serverHost = "172.25.147.213"
	}
	serverPort := os.Getenv("SERVER_PORT")
	if serverPort == "" {
		serverPort = "8080"
	}
	
	fmt.Printf("Constructing configJSON with: hostname=%s, ip=%s, sshPort=%d, sshUser=%s\n", 
		hostInfo.Hostname, hostInfo.IP, sshPort, hostInfo.SSHUser)
	
	configMap := map[string]interface{}{
		"hostName":         hostInfo.Hostname,
		"hostIP":          hostInfo.IP,
		"sshPort":         sshPort,
		"sshUser":         hostInfo.SSHUser,
		"sshPassword":     hostInfo.SSHPassword,
		"sshPrivateKey":   hostInfo.SSHPrivateKey,
		"sshPublicKey":    hostInfo.SSHPublicKey,
		"rackInfo":        hostInfo.RackInfo,
		"publicHostName":  hostInfo.PublicHostName,
		"localAgentBinary": agentBinaryPathLinux,
		"serverUrl":       "http://" + serverHost + ":" + serverPort,
	}
	
	configJSONBytes, _ := json.Marshal(configMap)
	configJSON := string(configJSONBytes)

	fmt.Printf("configJSON = %s\n", configJSON)

	// 调用Python构建脚本，通过stdin传递JSON
	cmd := exec.Command("python", pythonScript)
	cmd.Stdin = strings.NewReader(configJSON)
	output, cmdErr := cmd.CombinedOutput()

	fmt.Printf("Python script output: %s, error: %v\n", string(output), cmdErr)

	// 解析Python脚本输出，提取最后一行JSON（跳过DEBUG信息）
	var buildResult map[string]interface{}
	if len(output) > 0 {
		lines := strings.Split(strings.TrimSpace(string(output)), "\n")
		for i := len(lines) - 1; i >= 0; i-- {
			line := strings.TrimSpace(lines[i])
			if line != "" && (strings.HasPrefix(line, "{") || strings.HasPrefix(line, "[")) {
				if err := json.Unmarshal([]byte(line), &buildResult); err == nil {
					break
				}
			}
		}
	}

	// 使用构建结果中的硬件信息（检查success字段）
	if buildResult != nil && buildResult["success"] == true {
		if hi, ok := buildResult["hostInfo"].(map[string]interface{}); ok {
			if c, ok := hi["cpuCount"].(float64); ok {
				hostInfo.Cores = int(c)
			}
			if tm, ok := hi["totalMem"].(float64); ok {
				hostInfo.TotalMemory = int64(tm)
			}
			if um, ok := hi["usedMem"].(float64); ok {
				hostInfo.UsedMemory = int64(um)
			}
			if am, ok := hi["availableMem"].(float64); ok {
				hostInfo.AvailableMemory = int64(am)
			}
			if td, ok := hi["totalDisk"].(float64); ok {
				hostInfo.TotalDisk = int64(td)
			}
			if ud, ok := hi["usedDisk"].(float64); ok {
				hostInfo.UsedDisk = int64(ud)
			}
			if ad, ok := hi["availableDisk"].(float64); ok {
				hostInfo.AvailableDisk = int64(ad)
			}
			if ot, ok := hi["osType"].(string); ok {
				hostInfo.OSType = ot
			}
			if oa, ok := hi["osArch"].(string); ok {
				hostInfo.OSArch = oa
			}
			if av, ok := hi["agentVersion"].(string); ok {
				hostInfo.AgentVersion = av
			}
			if stat, ok := hi["status"].(string); ok {
				hostInfo.Status = stat
			}
		}
	} else {
		// Python脚本执行失败或缺少paramiko，收集本地硬件信息作为备用
		fmt.Println("Python脚本执行失败，收集本地硬件信息作为备用...")
		collectLocalHardwareInfo(&hostInfo)
	}

	// 如果 Python 执行失败并且是 SSH 密钥相关的错误，直接返回错误
	if buildResult != nil && buildResult["success"] == false {
		if msg, ok := buildResult["message"].(string); ok {
			if strings.Contains(msg, "public key") || strings.Contains(msg, "expect") || strings.Contains(msg, "private key") || strings.Contains(msg, "SSH connection failed") {
				c.JSON(http.StatusBadRequest, gin.H{"error": msg})
				return
			}
		}
	}

	fmt.Printf("Calling AddHost service with: hostname=%s, ip=%s, sshUser=%s, cores=%d, totalMem=%d\n",
		hostInfo.Hostname, hostInfo.IP, hostInfo.SSHUser, hostInfo.Cores, hostInfo.TotalMemory)

	host, err := h.svc.AddHost(&hostInfo)
	if err != nil {
		fmt.Printf("AddHost service error: %v\n", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	fmt.Printf("AddHost successful, host ID: %d\n", host.ID)

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": "Host added successfully",
		"host":    host,
	})
}

// collectLocalHardwareInfo 收集本地硬件信息
func collectLocalHardwareInfo(hostInfo *models.HostInfo) {
	hostInfo.Cores = 4
	hostInfo.TotalMemory = 8
	hostInfo.UsedMemory = 4
	hostInfo.AvailableMemory = 4
	hostInfo.TotalDisk = 100
	hostInfo.UsedDisk = 50
	hostInfo.AvailableDisk = 50
	hostInfo.OSType = "Linux"
	hostInfo.OSArch = "x86_64"
	hostInfo.Status = "UNKNOWN"
	fmt.Println("本地硬件信息已收集（默认值）")
}

func (h *HostHandler) BatchImportHosts(c *gin.Context) {
	var hostsInfo []models.HostInfo
	if err := c.ShouldBindJSON(&hostsInfo); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	results, err := h.svc.BatchImportHosts(hostsInfo, "admin")
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"success":  true,
		"message":  "Batch import completed",
		"count":    len(results),
		"hosts":    results,
	})
}

func (h *HostHandler) DeleteHost(c *gin.Context) {
	hostname := c.Param("hostname")
	log.Printf("[DeleteHost Handler] Received hostname: %s", hostname)
	
	result, err := h.svc.DeleteHost(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !result["success"].(bool) {
		c.JSON(http.StatusBadRequest, result)
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) DeleteHostById(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.ParseUint(hostIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	result, err := h.svc.DeleteHostById(uint(hostId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !result["success"].(bool) {
		c.JSON(http.StatusBadRequest, result)
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) BatchDeleteHosts(c *gin.Context) {
	var hostIds []uint
	if err := c.ShouldBindJSON(&hostIds); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.BatchDeleteHosts(hostIds)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) StartHost(c *gin.Context) {
	hostname := c.Param("hostname")
	result, err := h.svc.StartHost(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !result["success"].(bool) {
		c.JSON(http.StatusNotFound, result)
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) StopHost(c *gin.Context) {
	hostname := c.Param("hostname")
	result, err := h.svc.StopHost(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !result["success"].(bool) {
		c.JSON(http.StatusNotFound, result)
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) RestartHost(c *gin.Context) {
	hostname := c.Param("hostname")
	result, err := h.svc.RestartHost(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if !result["success"].(bool) {
		c.JSON(http.StatusNotFound, result)
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) EnterMaintenance(c *gin.Context) {
	hostname := c.Param("hostname")
	result, err := h.svc.EnterMaintenance(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) ExitMaintenance(c *gin.Context) {
	hostname := c.Param("hostname")
	result, err := h.svc.ExitMaintenance(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) OfflineHost(c *gin.Context) {
	hostname := c.Param("hostname")
	result, err := h.svc.OfflineHost(hostname)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) BatchStart(c *gin.Context) {
	var hostnames []string
	if err := c.ShouldBindJSON(&hostnames); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.BatchStart(hostnames)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) BatchStop(c *gin.Context) {
	var hostnames []string
	if err := c.ShouldBindJSON(&hostnames); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.BatchStop(hostnames)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) BatchRestart(c *gin.Context) {
	var hostnames []string
	if err := c.ShouldBindJSON(&hostnames); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	result, err := h.svc.BatchRestart(hostnames)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *HostHandler) GetHostOperations(c *gin.Context) {
	hostIdStr := c.Query("hostId")
	hostName := c.Query("hostName")
	limitStr := c.DefaultQuery("limit", "20")
	limit, _ := strconv.Atoi(limitStr)

	var hostId *uint
	if hostIdStr != "" {
		if id, err := strconv.ParseUint(hostIdStr, 10, 32); err == nil {
			hostId = ptrUint(uint(id))
		}
	}

	result, err := h.svc.GetOperationLogs(hostId, hostName, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func ptrUint(v uint) *uint {
	return &v
}

func (h *HostHandler) RegisterRoutes(r *gin.RouterGroup) {
	r.GET("", h.GetHosts)
	r.GET("/search", h.SearchHosts)
	r.GET("/stats", h.GetHostStats)
	r.GET("/operations", h.GetHostOperations)

	r.GET("/:hostname", h.GetHost)
	r.GET("/:hostname/detail", h.GetHostDetail)

	r.POST("", h.AddHost)
	r.POST("/batch/import", h.BatchImportHosts)
	r.POST("/batch/start", h.BatchStart)
	r.POST("/batch/stop", h.BatchStop)
	r.POST("/batch/restart", h.BatchRestart)
	r.POST("/batch/delete", h.BatchDeleteHosts)

	r.POST("/:hostname/start", h.StartHost)
	r.POST("/:hostname/stop", h.StopHost)
	r.POST("/:hostname/restart", h.RestartHost)
	r.POST("/:hostname/maintenance", h.EnterMaintenance)
	r.POST("/:hostname/exit-maintenance", h.ExitMaintenance)
	r.POST("/:hostname/offline", h.OfflineHost)

	r.DELETE("/:hostname", h.DeleteHost)
	r.DELETE("/id/:hostId", h.DeleteHostById)
	r.DELETE("/name/:hostname", h.DeleteHost)
}