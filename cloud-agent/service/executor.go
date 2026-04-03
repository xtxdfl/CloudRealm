package service

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"github.com/cloudrealm/cloud-agent/models"
	"github.com/sirupsen/logrus"
)

type CommandExecutor struct {
	queue      chan *models.CommandRequest
	resultChan chan *models.CommandResponse
	wg         sync.WaitGroup
	logger     *logrus.Logger
	maxConcurrent int
}

func NewCommandExecutor(logger *logrus.Logger, maxConcurrent int) *CommandExecutor {
	if maxConcurrent <= 0 {
		maxConcurrent = 5
	}
	return &CommandExecutor{
		queue:         make(chan *models.CommandRequest, 100),
		resultChan:    make(chan *models.CommandResponse, 100),
		logger:        logger,
		maxConcurrent: maxConcurrent,
	}
}

func (e *CommandExecutor) Start() {
	for i := 0; i < e.maxConcurrent; i++ {
		e.wg.Add(1)
		go e.worker(i)
	}
	e.logger.Infof("CommandExecutor started with %d workers", e.maxConcurrent)
}

func (e *CommandExecutor) Stop() {
	close(e.queue)
	e.wg.Wait()
	close(e.resultChan)
	e.logger.Info("CommandExecutor stopped")
}

func (e *CommandExecutor) Submit(cmd *models.CommandRequest) {
	e.queue <- cmd
}

func (e *CommandExecutor) Results() <-chan *models.CommandResponse {
	return e.resultChan
}

func (e *CommandExecutor) worker(id int) {
	defer e.wg.Done()

	for cmd := range e.queue {
		e.executeCommand(id, cmd)
	}
}

func (e *CommandExecutor) executeCommand(workerId int, cmd *models.CommandRequest) {
	e.logger.Infof("[Worker %d] Executing command: %s (type: %s)", workerId, cmd.CommandId, cmd.CommandType)

	response := &models.CommandResponse{
		CommandId: cmd.CommandId,
		Status:    "RUNNING",
		Timestamp: time.Now().UnixMilli(),
	}

	switch cmd.CommandType {
	case "EXECUTE":
		output, exitCode, err := e.executeShell(cmd.CommandText, cmd.Timeout)
		if err != nil {
			response.Status = "FAILED"
			response.ErrorMsg = err.Error()
			response.Output = output
		} else {
			response.Status = "COMPLETED"
			response.ExitCode = exitCode
			response.Output = output
		}
	case "START":
		output, err := e.startService(cmd.CommandText)
		if err != nil {
			response.Status = "FAILED"
			response.ErrorMsg = err.Error()
		} else {
			response.Status = "COMPLETED"
			response.Output = output
		}
	case "STOP":
		output, err := e.stopService(cmd.CommandText)
		if err != nil {
			response.Status = "FAILED"
			response.ErrorMsg = err.Error()
		} else {
			response.Status = "COMPLETED"
			response.Output = output
		}
	case "RESTART":
		output, err := e.restartService(cmd.CommandText)
		if err != nil {
			response.Status = "FAILED"
			response.ErrorMsg = err.Error()
		} else {
			response.Status = "COMPLETED"
			response.Output = output
		}
	case "SCRIPT":
		output, exitCode, err := e.executeScript(cmd.CommandText)
		if err != nil {
			response.Status = "FAILED"
			response.ErrorMsg = err.Error()
			response.Output = output
		} else {
			response.Status = "COMPLETED"
			response.ExitCode = exitCode
			response.Output = output
		}
	default:
		response.Status = "FAILED"
		response.ErrorMsg = fmt.Sprintf("Unknown command type: %s", cmd.CommandType)
	}

	response.Timestamp = time.Now().UnixMilli()
	e.logger.Infof("[Worker %d] Command %s completed with status: %s", workerId, cmd.CommandId, response.Status)

	e.resultChan <- response
}

func (e *CommandExecutor) executeShell(command string, timeout int) (string, int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
	defer cancel()

	shell := "sh"
	args := []string{"-c", command}
	if isWindows() {
		shell = "cmd"
		args = []string{"/c", command}
	}

	cmd := exec.CommandContext(ctx, shell, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	output := stdout.String()
	if stderr.Len() > 0 {
		output += "\n" + stderr.String()
	}

	if ctx.Err() == context.DeadlineExceeded {
		return output, -1, fmt.Errorf("command timed out after %d seconds", timeout)
	}

	exitCode := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			return output, -1, err
		}
	}

	return output, exitCode, nil
}

func (e *CommandExecutor) executeScript(script string) (string, int, error) {
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("cloud_agent_script_%d.sh", time.Now().UnixNano()))
	defer os.Remove(tmpFile)

	if isWindows() {
		tmpFile = filepath.Join(os.TempDir(), fmt.Sprintf("cloud_agent_script_%d.bat", time.Now().UnixNano()))
	}

	if err := os.WriteFile(tmpFile, []byte(script), 0755); err != nil {
		return "", -1, err
	}

	return e.executeShell(tmpFile, 300)
}

func (e *CommandExecutor) startService(serviceName string) (string, error) {
	cmd := fmt.Sprintf("systemctl start %s || service %s start", serviceName, serviceName)
	if isWindows() {
		cmd = fmt.Sprintf("net start %s", serviceName)
	}
	output, _, err := e.executeShell(cmd, 60)
	return output, err
}

func (e *CommandExecutor) stopService(serviceName string) (string, error) {
	cmd := fmt.Sprintf("systemctl stop %s || service %s stop", serviceName, serviceName)
	if isWindows() {
		cmd = fmt.Sprintf("net stop %s", serviceName)
	}
	output, _, err := e.executeShell(cmd, 60)
	return output, err
}

func (e *CommandExecutor) restartService(serviceName string) (string, error) {
	cmd := fmt.Sprintf("systemctl restart %s || service %s restart", serviceName, serviceName)
	if isWindows() {
		cmd = fmt.Sprintf("net stop %s && net start %s", serviceName, serviceName)
	}
	output, _, err := e.executeShell(cmd, 120)
	return output, err
}

func isWindows() bool {
	return os.PathSeparator == '\\'
}

type ActionQueue struct {
	queue    []models.CommandRequest
	mu       sync.Mutex
	notEmpty *sync.Cond
	logger   *logrus.Logger
}

func NewActionQueue(logger *logrus.Logger) *ActionQueue {
	aq := &ActionQueue{
		queue:  make([]models.CommandRequest, 0),
		logger: logger,
	}
	aq.notEmpty = sync.NewCond(&aq.mu)
	return aq
}

func (aq *ActionQueue) Enqueue(cmd models.CommandRequest) {
	aq.mu.Lock()
	defer aq.mu.Unlock()

	aq.queue = append(aq.queue, cmd)
	aq.notEmpty.Signal()
	aq.logger.Debugf("Command %s enqueued, queue size: %d", cmd.CommandId, len(aq.queue))
}

func (aq *ActionQueue) Dequeue() models.CommandRequest {
	aq.mu.Lock()
	defer aq.mu.Unlock()

	for len(aq.queue) == 0 {
		aq.notEmpty.Wait()
	}

	cmd := aq.queue[0]
	aq.queue = aq.queue[1:]
	aq.logger.Debugf("Command %s dequeued, queue size: %d", cmd.CommandId, len(aq.queue))

	return cmd
}

func (aq *ActionQueue) Size() int {
	aq.mu.Lock()
	defer aq.mu.Unlock()
	return len(aq.queue)
}

func (aq *ActionQueue) Clear() {
	aq.mu.Lock()
	defer aq.mu.Unlock()
	aq.queue = nil
	aq.queue = make([]models.CommandRequest, 0)
	aq.logger.Info("ActionQueue cleared")
}

type RecoveryManager struct {
	logger      *logrus.Logger
	maxRetries  int
	retryDelay  time.Duration
}

func NewRecoveryManager(logger *logrus.Logger, maxRetries int, retryDelaySec int) *RecoveryManager {
	if maxRetries <= 0 {
		maxRetries = 3
	}
	if retryDelaySec <= 0 {
		retryDelaySec = 5
	}
	return &RecoveryManager{
		logger:     logger,
		maxRetries: maxRetries,
		retryDelay: time.Duration(retryDelaySec) * time.Second,
	}
}

func (rm *RecoveryManager) Recover(commandId string, fn func() error) error {
	var lastErr error
	for i := 0; i < rm.maxRetries; i++ {
		err := fn()
		if err == nil {
			rm.logger.Infof("Recovery successful for command %s on attempt %d", commandId, i+1)
			return nil
		}
		lastErr = err
		rm.logger.Warnf("Recovery attempt %d failed for command %s: %v", i+1, commandId, err)
		time.Sleep(rm.retryDelay)
	}
	rm.logger.Errorf("Recovery failed for command %s after %d attempts: %v", commandId, rm.maxRetries, lastErr)
	return lastErr
}

type ComponentManager struct {
	logger *logrus.Logger
	mu     sync.RWMutex
	components map[string]*ComponentState
}

type ComponentState struct {
	Name       string
	Service    string
	Status     string
	Version    string
	StartTime  int64
	LastUpdate int64
	PID        int
}

func NewComponentManager(logger *logrus.Logger) *ComponentManager {
	return &ComponentManager{
		logger:     logger,
		components: make(map[string]*ComponentState),
	}
}

func (cm *ComponentManager) Register(componentName, serviceName string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	cm.components[componentName] = &ComponentState{
		Name:       componentName,
		Service:    serviceName,
		Status:     "STOPPED",
		LastUpdate: time.Now().UnixMilli(),
	}
	cm.logger.Infof("Component %s registered (service: %s)", componentName, serviceName)
}

func (cm *ComponentManager) Start(componentName string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	comp, exists := cm.components[componentName]
	if !exists {
		return fmt.Errorf("component %s not found", componentName)
	}

	comp.Status = "STARTING"
	comp.StartTime = time.Now().UnixMilli()
	comp.LastUpdate = time.Now().UnixMilli()

	comp.Status = "RUNNING"
	cm.logger.Infof("Component %s started", componentName)
	return nil
}

func (cm *ComponentManager) Stop(componentName string) error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	comp, exists := cm.components[componentName]
	if !exists {
		return fmt.Errorf("component %s not found", componentName)
	}

	comp.Status = "STOPPING"
	comp.LastUpdate = time.Now().UnixMilli()

	comp.Status = "STOPPED"
	cm.logger.Infof("Component %s stopped", componentName)
	return nil
}

func (cm *ComponentManager) GetStatus(componentName string) (*ComponentState, bool) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	comp, exists := cm.components[componentName]
	if !exists {
		return nil, false
	}
	return comp, true
}

func (cm *ComponentManager) GetAllStatuses() map[string]*ComponentState {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	result := make(map[string]*ComponentState, len(cm.components))
	for k, v := range cm.components {
		result[k] = v
	}
	return result
}

type AlertManager struct {
	logger   *logrus.Logger
	alerts   []models.Alert
	mu       sync.RWMutex
	maxAlerts int
}

func NewAlertManager(logger *logrus.Logger, maxAlerts int) *AlertManager {
	if maxAlerts <= 0 {
		maxAlerts = 100
	}
	return &AlertManager{
		logger:    logger,
		alerts:    make([]models.Alert, 0),
		maxAlerts: maxAlerts,
	}
}

func (am *AlertManager) AddAlert(alert models.Alert) {
	am.mu.Lock()
	defer am.mu.Unlock()

	am.alerts = append(am.alerts, alert)
	if len(am.alerts) > am.maxAlerts {
		am.alerts = am.alerts[1:]
	}
	am.logger.Infof("Alert added: %s (severity: %s)", alert.AlertType, alert.Severity)
}

func (am *AlertManager) GetAlerts() []models.Alert {
	am.mu.RLock()
	defer am.mu.RUnlock()

	result := make([]models.Alert, len(am.alerts))
	copy(result, am.alerts)
	return result
}

func (am *AlertManager) ClearAlerts() {
	am.mu.Lock()
	defer am.mu.Unlock()
	am.alerts = nil
	am.alerts = make([]models.Alert, 0)
	am.logger.Info("All alerts cleared")
}