package service

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/cloudrealm/cloud-agent/models"
	"github.com/go-resty/resty/v2"
	"github.com/sirupsen/logrus"
)

type ServerClient struct {
	serverURL  string
	client     *resty.Client
	agentID    string
	logger     *logrus.Logger
	mu         sync.RWMutex
	registered bool
}

func NewServerClient(serverURL string, logger *logrus.Logger) *ServerClient {
	client := resty.New().
		SetTimeout(30 * time.Second).
		SetRetryCount(3).
		SetHeader("User-Agent", "cloud-agent-go")

	return &ServerClient{
		serverURL: serverURL,
		client:    client,
		logger:    logger,
	}
}

func (sc *ServerClient) Register(req *models.RegistrationRequest) (*models.AgentStatus, error) {
	resp, err := sc.client.R().
		SetHeader("Content-Type", "application/json").
		SetBody(req).
		Post(sc.serverURL + "/api/agent/register")

	if err != nil {
		return nil, fmt.Errorf("registration request failed: %v", err)
	}

	if resp.StatusCode() != 200 && resp.StatusCode() != 201 {
		return nil, fmt.Errorf("registration failed with status: %d, body: %s", resp.StatusCode(), string(resp.Body()))
	}

	var status models.AgentStatus
	if err := json.Unmarshal(resp.Body(), &status); err != nil {
		return nil, fmt.Errorf("failed to parse registration response: %v", err)
	}

	sc.mu.Lock()
	sc.agentID = status.AgentID
	sc.registered = true
	sc.mu.Unlock()

	sc.logger.Infof("Agent registered successfully with ID: %s", status.AgentID)
	return &status, nil
}

func (sc *ServerClient) Heartbeat(req *models.HeartbeatRequest) (*models.HeartbeatResponse, error) {
	resp, err := sc.client.R().
		SetHeader("Content-Type", "application/json").
		SetBody(req).
		Post(sc.serverURL + "/api/agent/heartbeat")

	if err != nil {
		return nil, fmt.Errorf("heartbeat request failed: %v", err)
	}

	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("heartbeat failed with status: %d", resp.StatusCode())
	}

	var response models.HeartbeatResponse
	if err := json.Unmarshal(resp.Body(), &response); err != nil {
		return nil, fmt.Errorf("failed to parse heartbeat response: %v", err)
	}

	return &response, nil
}

func (sc *ServerClient) ReportCommandResult(cmdResult *models.CommandResponse) error {
	resp, err := sc.client.R().
		SetHeader("Content-Type", "application/json").
		SetBody(cmdResult).
		Post(sc.serverURL + "/api/agent/command/result")

	if err != nil {
		return fmt.Errorf("failed to report command result: %v", err)
	}

	if resp.StatusCode() != 200 {
		return fmt.Errorf("report failed with status: %d", resp.StatusCode())
	}

	return nil
}

func (sc *ServerClient) ReportComponentStatus(status []models.ComponentStatus) error {
	resp, err := sc.client.R().
		SetHeader("Content-Type", "application/json").
		SetBody(status).
		Post(sc.serverURL + "/api/agent/components/status")

	if err != nil {
		return fmt.Errorf("failed to report component status: %v", err)
	}

	if resp.StatusCode() != 200 {
		return fmt.Errorf("report failed with status: %d", resp.StatusCode())
	}

	return nil
}

func (sc *ServerClient) GetCommands() ([]models.CommandRequest, error) {
	resp, err := sc.client.R().
		Get(sc.serverURL + "/api/agent/commands")

	if err != nil {
		return nil, fmt.Errorf("failed to get commands: %v", err)
	}

	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("get commands failed with status: %d", resp.StatusCode())
	}

	var commands []models.CommandRequest
	if err := json.Unmarshal(resp.Body(), &commands); err != nil {
		return nil, fmt.Errorf("failed to parse commands: %v", err)
	}

	return commands, nil
}

func (sc *ServerClient) GetConfigurations(clusterName string) ([]models.ClusterConfig, error) {
	resp, err := sc.client.R().
		SetQueryParam("clusterName", clusterName).
		Get(sc.serverURL + "/api/agent/configurations")

	if err != nil {
		return nil, fmt.Errorf("failed to get configurations: %v", err)
	}

	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("get configurations failed with status: %d", resp.StatusCode())
	}

	var configs []models.ClusterConfig
	if err := json.Unmarshal(resp.Body(), &configs); err != nil {
		return nil, fmt.Errorf("failed to parse configurations: %v", err)
	}

	return configs, nil
}

func (sc *ServerClient) IsRegistered() bool {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	return sc.registered
}

func (sc *ServerClient) GetAgentID() string {
	sc.mu.RLock()
	defer sc.mu.RUnlock()
	return sc.agentID
}

type HeartbeatService struct {
	serverClient *ServerClient
	executor     *CommandExecutor
	logger       *logrus.Logger
	ticker       *time.Ticker
	stopCh       chan struct{}
	wg            sync.WaitGroup
	componentMgr *ComponentManager
	alertMgr     *AlertManager
}

func NewHeartbeatService(serverClient *ServerClient, executor *CommandExecutor, componentMgr *ComponentManager, alertMgr *AlertManager, logger *logrus.Logger) *HeartbeatService {
	return &HeartbeatService{
		serverClient: serverClient,
		executor:     executor,
		logger:       logger,
		componentMgr: componentMgr,
		alertMgr:     alertMgr,
		stopCh:       make(chan struct{}),
	}
}

func (hs *HeartbeatService) Start(intervalSec int) {
	if intervalSec <= 0 {
		intervalSec = 30
	}

	hs.ticker = time.NewTicker(time.Duration(intervalSec) * time.Second)
	hs.wg.Add(1)

	go func() {
		defer hs.wg.Done()
		hs.runHeartbeatLoop()
	}()

	hs.logger.Infof("Heartbeat service started with %d second interval", intervalSec)
}

func (hs *HeartbeatService) Stop() {
	if hs.ticker != nil {
		hs.ticker.Stop()
	}
	close(hs.stopCh)
	hs.wg.Wait()
	hs.logger.Info("Heartbeat service stopped")
}

func (hs *HeartbeatService) runHeartbeatLoop() {
	for {
		select {
		case <-hs.ticker.C:
			hs.sendHeartbeat()
		case <-hs.stopCh:
			return
		}
	}
}

func (hs *HeartbeatService) sendHeartbeat() {
	components := hs.componentMgr.GetAllStatuses()
	componentStatuses := make([]models.ComponentStatus, 0)
	for _, comp := range components {
		componentStatuses = append(componentStatuses, models.ComponentStatus{
			ComponentName: comp.Name,
			ServiceName:   comp.Service,
			Status:        comp.Status,
			Version:       comp.Version,
			StartTime:     comp.StartTime,
			LastUpdate:    comp.LastUpdate,
		})
	}

	alerts := hs.alertMgr.GetAlerts()

	req := &models.HeartbeatRequest{
		AgentId:     hs.serverClient.GetAgentID(),
		Status:      "RUNNING",
		Timestamp:  time.Now().UnixMilli(),
		CPUUsage:    GetCPUUsage(),
		MemoryUsed:  GetMemoryUsed(),
		MemoryTotal: GetMemoryTotal(),
		DiskUsed:    GetDiskUsed(),
		DiskTotal:   GetDiskTotal(),
		Components: componentStatuses,
		Alerts:     alerts,
	}

	resp, err := hs.serverClient.Heartbeat(req)
	if err != nil {
		hs.logger.Warnf("Heartbeat failed: %v", err)
		return
	}

	if resp.Commands != nil && len(resp.Commands) > 0 {
		for _, cmd := range resp.Commands {
			hs.executor.Submit(&cmd)
		}
	}

	if resp.Actions != nil && len(resp.Actions) > 0 {
		for _, action := range resp.Actions {
			hs.logger.Infof("Received action: %s", action.TaskId)
		}
	}

	hs.logger.Debug("Heartbeat sent successfully")
}

type HeartbeatResponse struct {
	Commands []models.CommandRequest `json:"commands"`
	Actions  []models.ActionResult   `json:"actions"`
}

type ConfigCache struct {
	mu         sync.RWMutex
	configs    map[string][]models.ClusterConfig
	logger     *logrus.Logger
}

func NewConfigCache(logger *logrus.Logger) *ConfigCache {
	return &ConfigCache{
		configs: make(map[string][]models.ClusterConfig),
		logger:  logger,
	}
}

func (cc *ConfigCache) Set(clusterName string, configs []models.ClusterConfig) {
	cc.mu.Lock()
	defer cc.mu.Unlock()
	cc.configs[clusterName] = configs
	cc.logger.Infof("Updated config cache for cluster %s with %d configs", clusterName, len(configs))
}

func (cc *ConfigCache) Get(clusterName string) []models.ClusterConfig {
	cc.mu.RLock()
	defer cc.mu.RUnlock()
	return cc.configs[clusterName]
}

func (cc *ConfigCache) GetConfig(clusterName, filename string) *models.ClusterConfig {
	cc.mu.RLock()
	defer cc.mu.RUnlock()

	configs := cc.configs[clusterName]
	for i := range configs {
		if configs[i].Filename == filename {
			return &configs[i]
		}
	}
	return nil
}

func (cc *ConfigCache) Clear() {
	cc.mu.Lock()
	defer cc.mu.Unlock()
	cc.configs = make(map[string][]models.ClusterConfig)
	cc.logger.Info("Config cache cleared")
}

type AgentLogger struct {
	logger     *logrus.Logger
	logFile    string
	logLevel   string
	logDir     string
}

func NewAgentLogger(logDir string, logLevel string) *AgentLogger {
	return &AgentLogger{
		logDir:   logDir,
		logLevel: logLevel,
	}
}

func (al *AgentLogger) InitLogger(logger *logrus.Logger) error {
	al.logger = logger

	if al.logDir != "" {
		if err := os.MkdirAll(al.logDir, 0755); err != nil {
			return fmt.Errorf("failed to create log directory: %v", err)
		}
		al.logFile = filepath.Join(al.logDir, "cloud-agent.log")

		file, err := os.OpenFile(al.logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err != nil {
			return fmt.Errorf("failed to open log file: %v", err)
		}

		logger.SetOutput(file)
	}

	level, err := logrus.ParseLevel(al.logLevel)
	if err != nil {
		level = logrus.InfoLevel
	}
	logger.SetLevel(level)
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})

	return nil
}

func (al *AgentLogger) GetLogFile() string {
	return al.logFile
}

type ServiceManager struct {
	pidFile  string
	dataDir string
	logger  *logrus.Logger
}

func NewServiceManager(dataDir string, logger *logrus.Logger) *ServiceManager {
	return &ServiceManager{
		dataDir: dataDir,
		logger:  logger,
		pidFile: filepath.Join(dataDir, "cloud-agent.pid"),
	}
}

func (sm *ServiceManager) WritePIDFile() error {
	if sm.dataDir != "" {
		if err := os.MkdirAll(sm.dataDir, 0755); err != nil {
			return fmt.Errorf("failed to create data directory: %v", err)
		}
	}

	pid := os.Getpid()
	if err := os.WriteFile(sm.pidFile, []byte(fmt.Sprintf("%d", pid)), 0644); err != nil {
		return fmt.Errorf("failed to write PID file: %v", err)
	}

	sm.logger.Infof("PID file written: %s", sm.pidFile)
	return nil
}

func (sm *ServiceManager) RemovePIDFile() error {
	if _, err := os.Stat(sm.pidFile); err == nil {
		if err := os.Remove(sm.pidFile); err != nil {
			return fmt.Errorf("failed to remove PID file: %v", err)
		}
		sm.logger.Infof("PID file removed: %s", sm.pidFile)
	}
	return nil
}

func (sm *ServiceManager) CheckRunningInstance() (bool, error) {
	if _, err := os.Stat(sm.pidFile); err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}

	data, err := os.ReadFile(sm.pidFile)
	if err != nil {
		return false, err
	}

	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return false, nil
	}

	process, err := os.FindProcess(pid)
	if err != nil {
		return false, nil
	}

	if err := process.Signal(syscall.Signal(0)); err == nil {
		return true, nil
	}

	return false, nil
}

type AutoRecovery struct {
	logger       *logrus.Logger
	errorCounter map[string]int
	lastError    map[string]int64
}

func NewAutoRecovery(logger *logrus.Logger) *AutoRecovery {
	return &AutoRecovery{
		logger:       logger,
		errorCounter: make(map[string]int),
		lastError:    make(map[string]int64),
	}
}

func (ar *AutoRecovery) RecordError(errorType string) string {
	now := time.Now().Unix()
	ar.errorCounter[errorType]++
	lastTime := ar.lastError[errorType]
	ar.lastError[errorType] = now

	switch errorType {
	case "server_connection":
		return ar.handleConnectionError(now, lastTime)
	case "resource_limit":
		ar.logger.Warning("Resource limitation detected")
		ar.increaseResourceLimits()
		return "retry"
	default:
		ar.logger.Error("Unknown error type: ", errorType)
		return "continue"
	}
}

func (ar *AutoRecovery) handleConnectionError(now, lastTime int64) string {
	count := ar.errorCounter["server_connection"]
	timeSince := now - lastTime

	if count <= 3 {
		waitTime := count * 5
		if waitTime > 15 {
			waitTime = 15
		}
		ar.logger.Warningf("Connection failed, retry after %ds", waitTime)
		return fmt.Sprintf("retry after %ds", waitTime)
	} else if timeSince < 300 {
		waitTime := 30 * (count - 2)
		if waitTime > 300 {
			waitTime = 300
		}
		ar.logger.Criticalf("Persistent connection issues (count=%d)", count)
		return fmt.Sprintf("retry after %ds", waitTime)
	} else {
		ar.errorCounter["server_connection"] = 0
		return "continue"
	}
}

func (ar *AutoRecovery) increaseResourceLimits() {
	ar.logger.Info("Attempting to increase resource limits")
}