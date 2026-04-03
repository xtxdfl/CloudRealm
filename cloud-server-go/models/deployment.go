package models

import (
	"time"
)

type StackVersion struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	StackName     string    `gorm:"column:stack_name;not null;size:100" json:"stackName"`
	StackVersion  string    `gorm:"column:stack_version;not null;size:50" json:"stackVersion"`
	StackType     string    `gorm:"column:stack_type;size:50" json:"stackType"`
	Description  string    `gorm:"column:description;size:500" json:"description"`
	RepositoryID *uint     `gorm:"column:repository_id" json:"repositoryId"`
	MinOSVersion  string    `gorm:"column:min_os_version;size:20" json:"minOsVersion"`
	IsVisible    bool      `gorm:"column:is_visible;default:true" json:"isVisible"`
	IsDeleted    bool      `gorm:"column:is_deleted;default:false" json:"isDeleted"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (StackVersion) TableName() string {
	return "stack_version"
}

type StackPackage struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	PackageName     string    `gorm:"column:package_name;not null;size:200" json:"packageName"`
	PackageVersion string    `gorm:"column:package_version;not null;size:100" json:"packageVersion"`
	StackVersionID uint      `gorm:"column:stack_version_id;not null" json:"stackVersionId"`
	RepositoryID   uint      `gorm:"column:repository_id;not null" json:"repositoryId"`
	Architecture   string    `gorm:"column:architecture;size:50" json:"architecture"`
	MD5            string    `gorm:"column:md5;size:100" json:"md5"`
	SHA256         string    `gorm:"column:sha256;size:100" json:"sha256"`
	PackageSize    int64     `gorm:"column:package_size;default:0" json:"packageSize"`
	RepoURL        string    `gorm:"column:repo_url;size:500" json:"repoUrl"`
	NeedsRestart   string    `gorm:"column:needs_restart;size:20" json:"needsRestart"`
	Conflicts      string    `gorm:"column:conflicts;size:500" json:"conflicts"`
	Provides      string    `gorm:"column:provides;size:500" json:"provides"`
	RequiredBy    string    `gorm:"column:required_by;size:500" json:"requiredBy"`
	IsHidden       bool      `gorm:"column:is_hidden;default:false" json:"isHidden"`
	IsCompatible  bool      `gorm:"column:is_compatible;default:true" json:"isCompatible"`
	ServiceType   string    `gorm:"column:service_type;size:50" json:"serviceType"`
	Priority      int       `gorm:"column:priority;default:0" json:"priority"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (StackPackage) TableName() string {
	return "stack_package"
}

type Repository struct {
	ID                uint      `gorm:"primaryKey" json:"id"`
	RepoID            string    `gorm:"column:repo_id;uniqueIndex;not null;size:100" json:"repoId"`
	RepoName          string    `gorm:"column:repo_name;not null;size:200" json:"repoName"`
	DisplayName      string    `gorm:"column:display_name;size:200" json:"displayName"`
	RepoType          string    `gorm:"column:repo_type;size:20;default:yum" json:"repoType"`
	RepoSource        string    `gorm:"column:repo_source;size:20;default:LOCAL" json:"repoSource"`
	BaseURL           string    `gorm:"column:base_url;size:500" json:"baseURL"`
	LocalPath         string    `gorm:"column:local_path;size:500" json:"localPath"`
	MirrorURL        string    `gorm:"column:mirror_url;size:500" json:"mirrorUrl"`
	OsType           string    `gorm:"column:os_type;size:50" json:"osType"`
	Architecture     string    `gorm:"column:architecture;size:50" json:"architecture"`
	Priority         int       `gorm:"column:priority;default:0" json:"priority"`
	Checksum         string    `gorm:"column:checksum;size:100" json:"checksum"`
	IsDefault        bool      `gorm:"column:is_default;default:false" json:"isDefault"`
	IsPublished      bool      `gorm:"column:is_published;default:false" json:"isPublished"`
	IsOperational    bool      `gorm:"column:is_operational;default:true" json:"isOperational"`
	Status           string    `gorm:"column:status;size:20;default:ACTIVE" json:"status"`
	Description      string    `gorm:"column:description;size:500" json:"description"`
	Username         string    `gorm:"column:username;size:100" json:"username"`
	Password         string    `gorm:"column:password;size:200" json:"password"`
	SSLVerify        bool      `gorm:"column:ssl_verify;default:true" json:"sslVerify"`
	SSLCertPath      string    `gorm:"column:ssl_cert_path;size:500" json:"sslCertPath"`
	ProxyEnabled     bool      `gorm:"column:proxy_enabled;default:false" json:"proxyEnabled"`
	ProxyURL         string    `gorm:"column:proxy_url;size:500" json:"proxyUrl"`
	ProxyUsername    string    `gorm:"column:proxy_username;size:100" json:"proxyUsername"`
	ProxyPassword    string    `gorm:"column:proxy_password;size:200" json:"proxyPassword"`
	Tags             string    `gorm:"column:tags;size:500" json:"tags"`
	LastSyncTime     int64     `gorm:"column:last_sync_time" json:"lastSyncTime"`
	LastVerifyTime   int64     `gorm:"column:last_verify_time" json:"lastVerifyTime"`
	VerifyStatus     string    `gorm:"column:verify_status;size:20" json:"verifyStatus"`
	VerifyMessage    string    `gorm:"column:verify_message;size:500" json:"verifyMessage"`
	CreatedAt        time.Time `json:"createdAt"`
	UpdatedAt        time.Time `json:"updatedAt"`
}

func (Repository) TableName() string {
	return "repository"
}

type HostRegister struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	HostName        string    `gorm:"column:host_name;not null;size:200" json:"hostName"`
	HostIP         string    `gorm:"column:host_ip;size:50" json:"hostIP"`
	Domain         string    `gorm:"column:domain;size:100" json:"domain"`
	SSHPort        int       `gorm:"column:ssh_port;default:12308" json:"sshPort"`
	SSHUser        string    `gorm:"column:ssh_user;size:100" json:"sshUser"`
	SSHKeyType     string    `gorm:"column:ssh_key_type;size:20" json:"sshKeyType"`
	SSHPrivateKey string    `gorm:"column:ssh_private_key;type:text" json:"sshPrivateKey"`
	SSHPublicKey   string    `gorm:"column:ssh_public_key;type:text" json:"sshPublicKey"`
	SSHPassword   string    `gorm:"column:ssh_password;size:200" json:"sshPassword"`
	AgentPackage  string    `gorm:"column:agent_package;size:200" json:"agentPackage"`
	AgentDownloadURL string `gorm:"column:agent_download_url;size:500" json:"agentDownloadURL"`
	RackInfo       string    `gorm:"column:rack_info;size:100" json:"rackInfo"`
	CPUCount       int       `gorm:"column:cpu_count;default:0" json:"cpuCount"`
	Memory        int64     `gorm:"column:memory;default:0" json:"memory"`
	DiskSize      int64     `gorm:"column:disk_size;default:0" json:"diskSize"`
	OSType        string    `gorm:"column:os_type;size:50" json:"osType"`
	OSVersion     string    `gorm:"column:os_version;size:50" json:"osVersion"`
	OSArch        string    `gorm:"column:os_arch;size:50" json:"osArch"`
	Status        string    `gorm:"column:status;size:20;default:PENDING" json:"status"`
	RegistrationResult string `gorm:"column:registration_result;size:500" json:"registrationResult"`
	ErrorMessage  string    `gorm:"column:error_message;size:500" json:"errorMessage"`
	FailCount     int       `gorm:"column:fail_count;default:0" json:"failCount"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (HostRegister) TableName() string {
	return "host_register"
}

type ServiceDeployInfo struct {
	StackName     string `json:"stackName"`
	StackVersion string `json:"stackVersion"`
	Services     []DeployServiceInfo `json:"services"`
}

type DeployServiceInfo struct {
	ServiceName    string   `json:"serviceName"`
	DisplayName   string   `json:"displayName"`
	Version      string   `json:"version"`
	PackageName  string   `json:"packageName"`
	MD5          string   `json:"md5"`
	PackageSize int64    `json:"packageSize"`
	RepoURL      string   `json:"repoUrl"`
	Required    []string `json:"required"`
	Optional    []string `json:"optional"`
}

type DeployProgress struct {
	TotalHosts  int    `json:"totalHosts"`
	Success     int    `json:"success"`
	Failed      int    `json:"failed"`
	InProgress int    `json:"inProgress"`
	Status     string `json:"status"`
	Logs        []DeployLog `json:"logs"`
}

type DeployLog struct {
	Timestamp int64  `json:"timestamp"`
	HostName  string `json:"hostName"`
	Message  string `json:"message"`
	Level    string `json:"level"`
}