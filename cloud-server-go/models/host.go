package models

import (
	"encoding/json"
	"time"
)

type Host struct {
	ID                 uint      `gorm:"column:host_id;primaryKey" json:"id"`
	HostID             uint      `gorm:"column:host_id" json:"hostId"`
	HostName           string    `gorm:"column:host_name;uniqueIndex;not null" json:"hostName"`
	IPv4               string    `gorm:"column:ipv4;uniqueIndex" json:"ipv4"`
	IPv6               string    `gorm:"column:ipv6" json:"ipv6"`
	PublicHostName     string    `gorm:"column:public_host_name" json:"publicHostName"`
	CPUCount           int       `gorm:"column:cpu_count;default:0" json:"cpuCount"`
	CPUInfo            string    `gorm:"column:cpu_info;default:''" json:"cpuInfo"`
	CPUUsage           float64   `gorm:"column:cpu_usage;default:0" json:"cpuUsage"`
	TotalMem           int64     `gorm:"column:total_mem;default:0" json:"totalMem"`
	UsedMem            int64     `gorm:"column:used_mem;default:0" json:"usedMem"`
	AvailableMem       int64     `gorm:"column:available_mem;default:0" json:"availableMem"`
	MemoryUsage        float64   `gorm:"column:memory_usage;default:0" json:"memoryUsage"`
	TotalDisk          int64     `gorm:"column:total_disk;default:0" json:"totalDisk"`
	UsedDisk           int64     `gorm:"column:used_disk;default:0" json:"usedDisk"`
	AvailableDisk      int64     `gorm:"column:available_disk;default:0" json:"availableDisk"`
	DiskUsage          float64   `gorm:"column:disk_usage;default:0" json:"diskUsage"`
	OSType             string    `gorm:"column:os_type;default:Linux" json:"osType"`
	OSArch             string    `gorm:"column:os_arch;default:x86_64" json:"osArch"`
	OSInfo             string    `gorm:"column:os_info;default:''" json:"osInfo"`
	DiscoveryStatus   string    `gorm:"column:discovery_status;default:UNKNOWN" json:"discoveryStatus"`
	HostAttributes    string    `gorm:"column:host_attributes;default:'{}'" json:"hostAttributes"`
	RackInfo           string    `gorm:"column:rack_info;default:/default-rack" json:"rackInfo"`
	LastRegistrationTime int64   `gorm:"column:last_registration_time;default:0" json:"lastRegistrationTime"`
	LastHeartbeatTime  int64     `gorm:"column:last_heartbeat_time;default:0" json:"lastHeartbeatTime"`
	LastOperationTime int64     `gorm:"column:last_operation_time;default:0" json:"lastOperationTime"`
	StorageSize        int64     `gorm:"column:storage_size;default:0" json:"storageSize"`
	HeartbeatInterval int       `gorm:"column:heartbeat_interval;default:30" json:"heartbeatInterval"`
	AgentVersion      string    `gorm:"column:agent_version" json:"agentVersion"`
	AgentStatus       string    `gorm:"column:agent_status;default:OFFLINE" json:"agentStatus"`
	SSHPrivateKey     string    `gorm:"column:ssh_private_key;type:text" json:"-"`
	SSHPublicKey      string    `gorm:"column:ssh_public_key;type:text" json:"-"`
	DiskInfo          string    `gorm:"column:disk_info;default:'[]'" json:"diskInfo"`
	NetworkInfo        string    `gorm:"column:network_info;default:'[]'" json:"networkInfo"`
	CreatedAt          time.Time `gorm:"-" json:"createdAt"`
	UpdatedAt          time.Time `gorm:"-" json:"updatedAt"`
}

func (Host) TableName() string {
	return "hosts"
}

type HostInfo struct {
	HostID            uint     `json:"hostId"`
	Hostname          string   `json:"hostname"`
	IP                string   `json:"ip"`
	PublicHostName    string   `json:"publicHostName"`
	Role              string   `json:"role"`
	Status            string   `json:"status"`
	AgentStatus       string   `json:"agentStatus"`
	Cores             int      `json:"cores"`
	CPUInfo           string   `json:"cpuInfo"`
	CPUUsage          float64  `json:"cpuUsage"`
	Memory            string   `json:"memory"`
	TotalMemory       int64    `json:"totalMemory"`
	UsedMemory        int64    `json:"usedMemory"`
	AvailableMemory   int64    `json:"availableMemory"`
	MemoryUsage       float64  `json:"memoryUsage"`
	TotalDisk         int64    `json:"totalDisk"`
	UsedDisk          int64    `json:"usedDisk"`
	AvailableDisk     int64    `json:"availableDisk"`
	DiskUsage         float64  `json:"diskUsage"`
	OSType            string   `json:"osType"`
	OSArch            string   `json:"osArch"`
	OSInfo            string   `json:"osInfo"`
	RackInfo          string   `json:"rackInfo"`
	AgentVersion      string   `json:"agentVersion"`
	DiskInfo          string   `json:"diskInfo"`
	NetworkInfo       string   `json:"networkInfo"`
	LastHeartbeatTime int64    `json:"lastHeartbeatTime"`
	LastRegistrationTime int64 `json:"lastRegistrationTime"`
	LastOperationTime int64    `json:"lastOperationTime"`
	StorageSize       int64    `json:"storageSize"`
	StorageUsage      int64    `json:"storageUsage"`
	Tags              []string `json:"tags"`
	Components        []string `json:"components"`
	Uptime            string   `json:"uptime"`
	SSHPort           int      `json:"sshPort"`
	SSHUser           string   `json:"sshUser"`
	SSHPassword       string   `json:"sshPassword"`
	SSHPrivateKey     string   `json:"sshPrivateKey"`
	SSHPublicKey      string   `json:"sshPublicKey"`
}

type HostStats struct {
	Total     int64 `json:"total"`
	Online    int64 `json:"online"`
	Offline   int64 `json:"offline"`
	Unhealthy int64 `json:"unhealthy"`
}

type HostSearch struct {
	HostName   string `json:"hostName"`
	IPv4       string `json:"ipv4"`
	Status     string `json:"status"`
	AgentStatus string `json:"agentStatus"`
	RackInfo   string `json:"rackInfo"`
}

func (h *Host) ToHostInfo() HostInfo {
	var tags []string
	var components []string
	json.Unmarshal([]byte(h.HostAttributes), &tags)

	return HostInfo{
		HostID:              h.HostID,
		Hostname:            h.HostName,
		IP:                  h.IPv4,
		PublicHostName:      h.PublicHostName,
		Status:              h.DiscoveryStatus,
		AgentStatus:         h.AgentStatus,
		Cores:               h.CPUCount,
		CPUInfo:             h.CPUInfo,
		CPUUsage:            h.CPUUsage,
		TotalMemory:         h.TotalMem,
		UsedMemory:          h.UsedMem,
		AvailableMemory:     h.AvailableMem,
		MemoryUsage:        h.MemoryUsage,
		TotalDisk:           h.TotalDisk,
		UsedDisk:            h.UsedDisk,
		AvailableDisk:       h.AvailableDisk,
		DiskUsage:           h.DiskUsage,
		OSType:              h.OSType,
		OSArch:              h.OSArch,
		OSInfo:              h.OSInfo,
		RackInfo:            h.RackInfo,
		AgentVersion:        h.AgentVersion,
		DiskInfo:            h.DiskInfo,
		NetworkInfo:         h.NetworkInfo,
		LastHeartbeatTime:   h.LastHeartbeatTime,
		LastRegistrationTime: h.LastRegistrationTime,
		LastOperationTime:   h.LastOperationTime,
		StorageSize:         h.StorageSize,
		Tags:                tags,
		Components:          components,
	}
}