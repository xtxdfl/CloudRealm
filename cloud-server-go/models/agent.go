package models

type AgentRegistrationRequest struct {
	AgentId      string            `json:"agentId"`
	HostName     string            `json:"hostName"`
	IPAddress    string            `json:"ipAddress"`
	Version      string            `json:"version"`
	OSType       string            `json:"osType"`
	OSVersion    string            `json:"osVersion"`
	CPUCount     int               `json:"cpuCount"`
	MemoryTotal  int64             `json:"memoryTotal"`
	DiskTotal    int64             `json:"diskTotal"`
	Roles        []string          `json:"roles"`
	Components   []string          `json:"components"`
	Metadata     map[string]string `json:"metadata"`
}

type AgentStatus struct {
	AgentID      string `json:"agentId"`
	Status       string `json:"status"`
	ServerTime   int64  `json:"serverTime"`
}

type HeartbeatRequest struct {
	AgentId       string            `json:"agentId"`
	Status        string            `json:"status"`
	Timestamp     int64             `json:"timestamp"`
	CPUUsage      float64           `json:"cpuUsage"`
	MemoryUsed    int64             `json:"memoryUsed"`
	MemoryTotal   int64             `json:"memoryTotal"`
	DiskUsed      int64             `json:"diskUsed"`
	DiskTotal     int64             `json:"diskTotal"`
	Components    []ComponentStatus `json:"components"`
	Alerts        []Alert           `json:"alerts"`
	Metadata      map[string]string `json:"metadata"`
}

type ComponentStatus struct {
	Name    string `json:"name"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type Alert struct {
	Level   string `json:"level"`
	Message string `json:"message"`
	Time    int64  `json:"time"`
}

type HeartbeatResponse struct {
	ServerTime int64  `json:"serverTime"`
	Status     string `json:"status"`
	Message    string `json:"message"`
}