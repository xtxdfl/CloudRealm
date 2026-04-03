package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type DeploymentHandler struct {
	deploySvc *service.DeploymentService
}

func NewDeploymentHandler(deploySvc *service.DeploymentService) *DeploymentHandler {
	return &DeploymentHandler{deploySvc: deploySvc}
}

func (h *DeploymentHandler) RegisterRoutes(r *gin.RouterGroup) {
	repos := r.Group("/repositories")
	{
		repos.GET("", h.GetRepositories)
		repos.GET("/:repoId", h.GetRepository)
		repos.POST("", h.CreateRepository)
		repos.PUT("/:repoId", h.UpdateRepository)
		repos.DELETE("/:repoId", h.DeleteRepository)
		repos.POST("/verify", h.VerifyRepository)
		repos.POST("/:repoId/sync", h.SyncRepository)
	}

	stack := r.Group("/stack")
	{
		stack.GET("/versions", h.GetStackVersions)
		stack.POST("/versions", h.CreateStackVersion)
		stack.GET("/versions/:id/packages", h.GetPackages)
	}

	hosts := r.Group("/hosts-register")
	{
		hosts.GET("", h.GetHostRegisters)
		hosts.POST("", h.CreateHostRegister)
		hosts.POST("/batch", h.BatchCreateHostRegister)
		hosts.PUT("/:id", h.UpdateHostRegister)
		hosts.DELETE("/:id", h.DeleteHostRegister)
		hosts.POST("/:id/register", h.RegisterHost)
	}

	r.GET("/services", h.GetDeployServices)
	r.GET("/progress", h.GetDeployProgress)
	r.POST("/sync-packages", h.SyncPackagesFromRepo)
}

func (h *DeploymentHandler) GetRepositories(c *gin.Context) {
	repos, err := h.deploySvc.GetRepositories()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if repos == nil {
		repos = []models.Repository{}
	}
	c.JSON(http.StatusOK, repos)
}

func (h *DeploymentHandler) GetRepository(c *gin.Context) {
	repoID := c.Param("repoId")
	repo, err := h.deploySvc.GetRepositoryByRepoID(repoID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Repository not found"})
		return
	}
	c.JSON(http.StatusOK, repo)
}

func (h *DeploymentHandler) CreateRepository(c *gin.Context) {
	var repo models.Repository
	if err := c.ShouldBindJSON(&repo); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if repo.RepoID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repo_id is required"})
		return
	}

	if repo.RepoSource == "" {
		repo.RepoSource = "LOCAL"
	}

	if repo.RepoSource == "LOCAL" && repo.LocalPath == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "local_path is required for LOCAL repository"})
		return
	}

	if repo.RepoSource == "HTTP" && repo.BaseURL == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "base_url is required for HTTP repository"})
		return
	}

	created, err := h.deploySvc.CreateRepository(&repo)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, created)
}

func (h *DeploymentHandler) UpdateRepository(c *gin.Context) {
	repoID := c.Param("repoId")
	repo, err := h.deploySvc.GetRepositoryByRepoID(repoID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Repository not found"})
		return
	}

	var update models.Repository
	if err := c.ShouldBindJSON(&update); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	repo.RepoName = update.RepoName
	repo.DisplayName = update.DisplayName
	repo.RepoSource = update.RepoSource
	repo.BaseURL = update.BaseURL
	repo.LocalPath = update.LocalPath
	repo.MirrorURL = update.MirrorURL
	repo.RepoType = update.RepoType
	repo.Status = update.Status
	repo.Description = update.Description

	if err := h.deploySvc.UpdateRepository(repo); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, repo)
}

func (h *DeploymentHandler) DeleteRepository(c *gin.Context) {
	repoID := c.Param("repoId")
	repo, err := h.deploySvc.GetRepositoryByRepoID(repoID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Repository not found"})
		return
	}

	repo.IsPublished = false
	if err := h.deploySvc.UpdateRepository(repo); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Repository deleted"})
}

func (h *DeploymentHandler) VerifyRepository(c *gin.Context) {
	var request struct {
		RepoID string `json:"repoId" binding:"required"`
	}
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repoId is required"})
		return
	}

	repo, err := h.deploySvc.VerifyRepository(request.RepoID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"repoId":        repo.RepoID,
		"verifyStatus":  repo.VerifyStatus,
		"verifyMessage": repo.VerifyMessage,
		"lastVerifyTime": repo.LastVerifyTime,
	})
}

func (h *DeploymentHandler) SyncRepository(c *gin.Context) {
	repoID := c.Param("repoId")

	packages, err := h.deploySvc.SyncRepositoryPackages(repoID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"repoId":       repoID,
		"packageCount": len(packages),
		"packages":     packages,
	})
}

func (h *DeploymentHandler) GetStackVersions(c *gin.Context) {
	versions, err := h.deploySvc.GetStackVersions()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if versions == nil {
		versions = []models.StackVersion{}
	}
	c.JSON(http.StatusOK, versions)
}

func (h *DeploymentHandler) CreateStackVersion(c *gin.Context) {
	var sv models.StackVersion
	if err := c.ShouldBindJSON(&sv); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if sv.StackName == "" || sv.StackVersion == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "stack_name and stack_version are required"})
		return
	}

	created, err := h.deploySvc.CreateStackVersion(&sv)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, created)
}

func (h *DeploymentHandler) GetPackages(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid stack version ID"})
		return
	}

	packages, err := h.deploySvc.GetPackagesByStackVersion(uint(id))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if packages == nil {
		packages = []models.StackPackage{}
	}
	c.JSON(http.StatusOK, packages)
}

func (h *DeploymentHandler) GetHostRegisters(c *gin.Context) {
	hosts, err := h.deploySvc.GetHostRegisters()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if hosts == nil {
		hosts = []models.HostRegister{}
	}
	c.JSON(http.StatusOK, hosts)
}

func (h *DeploymentHandler) CreateHostRegister(c *gin.Context) {
	var host models.HostRegister
	if err := c.ShouldBindJSON(&host); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if host.HostName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "host_name is required"})
		return
	}

	created, err := h.deploySvc.CreateHostRegister(&host)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, created)
}

func (h *DeploymentHandler) BatchCreateHostRegister(c *gin.Context) {
	var request struct {
		Hosts []models.HostRegister `json:"hosts"`
	}
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if len(request.Hosts) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "hosts is required"})
		return
	}

	if err := h.deploySvc.BatchCreateHostRegister(request.Hosts); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Hosts created successfully", "count": len(request.Hosts)})
}

func (h *DeploymentHandler) UpdateHostRegister(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	host, err := h.deploySvc.GetHostRegisterByID(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Host not found"})
		return
	}

	var update models.HostRegister
	if err := c.ShouldBindJSON(&update); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	host.SSHPort = update.SSHPort
	host.SSHUser = update.SSHUser
	host.SSHKeyType = update.SSHKeyType
	host.SSHPassword = update.SSHPassword
	host.RackInfo = update.RackInfo

	if err := h.deploySvc.UpdateHostRegister(host); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, host)
}

func (h *DeploymentHandler) DeleteHostRegister(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	if err := h.deploySvc.DeleteHostRegister(uint(id)); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Host deleted"})
}

func (h *DeploymentHandler) RegisterHost(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	host, err := h.deploySvc.GetHostRegisterByID(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Host not found"})
		return
	}

	host.Status = "REGISTERING"
	if err := h.deploySvc.UpdateHostRegister(host); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	pythonScript := filepath.Join("..", "..", "cloud-common", "cloud_commons", "host_installer.py")
	if _, err := os.Stat(pythonScript); err != nil {
		if os.IsNotExist(err) {
			pythonScript = "c:\\yj\\CloudRealm\\cloud-common\\cloud_commons\\host_installer.py"
		}
	}

	configJSON := fmt.Sprintf(`{
		"hostName": "%s",
		"hostIP": "%s",
		"sshPort": %d,
		"sshUser": "%s",
		"sshKeyType": "%s",
		"agentPort": 8123,
		"agentDownloadURL": "%s"
	}`, host.HostName, host.HostIP, host.SSHPort, host.SSHUser, host.SSHKeyType, host.AgentDownloadURL)

	cmd := exec.Command("python3", pythonScript, configJSON)
	output, cmdErr := cmd.CombinedOutput()

	var result map[string]interface{}
	if cmdErr == nil {
		json.Unmarshal(output, &result)
	}

	if result != nil && result["success"] == true {
		host.Status = "REGISTERED"
		host.RegistrationResult = string(output)
		h.deploySvc.UpdateHostRegister(host)

		if hostInfo, ok := result["hostInfo"].(map[string]interface{}); ok {
			newHost := &models.Host{
				HostName:           getString(hostInfo, "hostName"),
				IPv4:               getString(hostInfo, "ipv4"),
				CPUCount:           int(getFloat64(hostInfo, "cpuCount")),
				TotalMem:           int64(getFloat64(hostInfo, "totalMem")),
				TotalDisk:          int64(getFloat64(hostInfo, "totalDisk")),
				OSType:             getString(hostInfo, "osType"),
				OSArch:             getString(hostInfo, "osArch"),
				OSInfo:             getString(hostInfo, "osInfo"),
				AgentVersion:       getString(hostInfo, "agentVersion"),
				AgentStatus:       "ONLINE",
				DiscoveryStatus:    "ACTIVE",
				LastRegistrationTime: time.Now().Unix(),
				LastHeartbeatTime:  time.Now().Unix(),
			}
			h.deploySvc.CreateHostFromRegistration(newHost)
		}

		c.JSON(http.StatusOK, gin.H{"message": "Host registered successfully", "host": host})
	} else {
		errMsg := string(output)
		if result != nil {
			if msg, ok := result["message"].(string); ok {
				errMsg = msg
			}
		}
		host.Status = "FAILED"
		host.ErrorMessage = errMsg
		host.FailCount = host.FailCount + 1
		h.deploySvc.UpdateHostRegister(host)
		c.JSON(http.StatusInternalServerError, gin.H{"error": errMsg})
	}
}

func executeSSHRegister(host *models.HostRegister) (string, error) {
	if host.AgentDownloadURL == "" {
		host.AgentDownloadURL = "http://repo.cloud.com/packages/cloud-agent.rpm"
	}

	tmpDir, err := os.MkdirTemp("", "cloud-deploy-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(tmpDir)

	scriptPath := filepath.Join(tmpDir, "install_agent.sh")
	scriptContent := generateInstallScript(host)
	if err := os.WriteFile(scriptPath, []byte(scriptContent), 0755); err != nil {
		return "", err
	}

	port := host.SSHPort
	if port == 0 {
		port = 22
	}

	cmdStr := fmt.Sprintf("ssh -o StrictHostKeyChecking=no -p %d %s@%s 'bash -s' < %s",
		port, host.SSHUser, host.HostName, scriptPath)

	cmd := exec.Command("bash", "-c", cmdStr)
	cmd.Env = append(os.Environ(), "AGENT_PORT=8123")

	output, err := cmd.CombinedOutput()
	if err != nil {
		return string(output), err
	}

	return string(output), nil
}

func generateInstallScript(host *models.HostRegister) string {
	downloadURL := host.AgentDownloadURL
	if downloadURL == "" {
		downloadURL = "http://repo.cloud.com/packages/cloud-agent.rpm"
	}

	return fmt.Sprintf(`#!/bin/bash
set -e
AGENT_PORT=8123
AGENT_USER=%s
curl -o /tmp/cloud-agent.rpm %s
rpm -ivh /tmp/cloud-agent.rpm
systemctl enable cloud-agent
systemctl start cloud-agent
`, host.SSHUser, downloadURL)
}

func (h *DeploymentHandler) GetDeployServices(c *gin.Context) {
	services, err := h.deploySvc.GetDeployServices()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if services == nil {
		services = []models.ServiceDeployInfo{}
	}
	c.JSON(http.StatusOK, services)
}

func (h *DeploymentHandler) GetDeployProgress(c *gin.Context) {
	progress := models.DeployProgress{
		TotalHosts:  0,
		Success:     0,
		Failed:      0,
		InProgress: 0,
		Status:     "IDLE",
		Logs:        []models.DeployLog{},
	}
	c.JSON(http.StatusOK, progress)
}

func (h *DeploymentHandler) SyncPackagesFromRepo(c *gin.Context) {
	var request struct {
		RepoID   string `json:"repoId"`
		RepoName string `json:"repoName"`
	}
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	pythonScript := filepath.Join("..", "..", "cloud-common", "cloud_commons", "yum_package_parser.py")
	if _, err := os.Stat(pythonScript); err != nil {
		if os.IsNotExist(err) {
			pythonScript = "c:\\yj\\CloudRealm\\cloud-common\\cloud_commons\\yum_package_parser.py"
		}
	}

	cmd := exec.Command("python3", pythonScript, request.RepoName)
	output, err := cmd.CombinedOutput()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse repo: " + err.Error()})
		return
	}

	var result map[string]interface{}
	if err := json.Unmarshal(output, &result); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse Python output: " + err.Error()})
		return
	}

	repo, err := h.deploySvc.GetRepositoryByRepoID(request.RepoID)
	if err != nil {
		repo = &models.Repository{
			RepoID:   request.RepoID,
			RepoName: request.RepoName,
			Status:   "ACTIVE",
		}
		h.deploySvc.CreateRepository(repo)
	}

	var packages []models.StackPackage
	servicesData, ok := result["services"].(map[string]interface{})
	if ok {
		for serviceName, pkgs := range servicesData {
			pkgList, ok := pkgs.([]interface{})
			if !ok {
				continue
			}
			for _, p := range pkgList {
				pkgMap, ok := p.(map[string]interface{})
				if !ok {
					continue
				}

				version := ""
				if v, ok := pkgMap["version"].(string); ok {
					version = v
				}
				release := ""
				if r, ok := pkgMap["release"].(string); ok {
					release = r
				}
				fullVersion := version
				if release != "" {
					fullVersion = version + "-" + release
				}

				arch := "x86_64"
				if a, ok := pkgMap["arch"].(string); ok {
					arch = a
				}

				size := int64(0)
				if s, ok := pkgMap["size"].(float64); ok {
					size = int64(s)
				}

				checksum := ""
				if cs, ok := pkgMap["checksum"].(string); ok {
					checksum = cs
				}

				packages = append(packages, models.StackPackage{
					PackageName:    getString(pkgMap, "name"),
					PackageVersion: fullVersion,
					RepositoryID:   repo.ID,
					Architecture:   arch,
					MD5:            checksum,
					PackageSize:    size,
					RepoURL:        repo.BaseURL,
					ServiceType:    serviceName,
				})
			}
		}
	}

	if len(packages) > 0 {
		h.deploySvc.BatchCreateStackPackage(packages)
	}

	stackVersion := &models.StackVersion{
		StackName:    "Cloud",
		StackVersion: "1.0.0",
		RepositoryID: &repo.ID,
	}
	h.deploySvc.CreateStackVersion(stackVersion)

	for i := range packages {
		packages[i].StackVersionID = stackVersion.ID
	}
	if len(packages) > 0 {
		h.deploySvc.BatchCreateStackPackage(packages)
	}

	c.JSON(http.StatusOK, gin.H{
		"message":         "Packages synced successfully",
		"totalPackages":   len(packages),
		"stackVersion":    stackVersion,
		"repository":      repo,
		"services":        servicesData,
	})
}

func getString(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func getFloat64(m map[string]interface{}, key string) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	return 0
}