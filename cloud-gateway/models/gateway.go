package models

import (
	"time"
)

type Route struct {
	ID        string   `yaml:"id" json:"id"`
	URI       string   `yaml:"uri" json:"uri"`
	Predicates []Predicate `yaml:"predicates" json:"predicates"`
	Filters   []string   `yaml:"filters" json:"filters"`
	Metadata  map[string]string `yaml:"metadata" json:"metadata"`
}

type Predicate struct {
	Name   string   `yaml:"name" json:"name"`
	Args   []string `yaml:"args" json:"args"`
}

type GatewayConfig struct {
	Server    ServerConfig    `yaml:"server" json:"server"`
	Discovery DiscoveryConfig `yaml:"discovery" json:"discovery"`
	Routes    []Route        `yaml:"routes" json:"routes"`
}

type ServerConfig struct {
	Port int `yaml:"port" json:"port"`
}

type DiscoveryConfig struct {
	ServerAddr string `yaml:"server-addr" json:"serverAddr"`
}

type ProxyRequest struct {
	Method      string            `json:"method"`
	Path        string            `json:"path"`
	QueryParams map[string]string `json:"queryParams"`
	Headers     map[string]string `json:"headers"`
	Body        string            `json:"body"`
}

type ProxyResponse struct {
	StatusCode int               `json:"statusCode"`
	Headers    map[string]string `json:"headers"`
	Body       string            `json:"body"`
}

type RateLimitRule struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Path        string    `gorm:"column:path;index" json:"path"`
	Method      string    `gorm:"column:method" json:"method"`
	Rate        int       `gorm:"column:rate" json:"rate"`
	Burst       int       `gorm:"column:burst" json:"burst"`
	Enabled     bool      `gorm:"column:enabled;default:true" json:"enabled"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (RateLimitRule) TableName() string {
	return "gateway_rate_limits"
}

type CircuitBreaker struct {
	ID                uint      `gorm:"primaryKey" json:"id"`
	ServiceName       string    `gorm:"column:service_name;index" json:"serviceName"`
	FailureThreshold  int       `gorm:"column:failure_threshold" json:"failureThreshold"`
	SuccessThreshold  int       `gorm:"column:success_threshold" json:"successThreshold"`
	TimeoutSeconds    int       `gorm:"column:timeout_seconds" json:"timeoutSeconds"`
	HalfOpenMaxCalls  int       `gorm:"column:half_open_max_calls" json:"halfOpenMaxCalls"`
	Enabled          bool      `gorm:"column:enabled;default:true" json:"enabled"`
	CreatedAt        time.Time `json:"createdAt"`
	UpdatedAt        time.Time `json:"updatedAt"`
}

func (CircuitBreaker) TableName() string {
	return "gateway_circuit_breakers"
}

type ServiceEndpoint struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	ServiceName string    `gorm:"column:service_name;index" json:"serviceName"`
	Host        string    `gorm:"column:host" json:"host"`
	Port        int       `gorm:"column:port" json:"port"`
	Protocol    string    `gorm:"column:protocol" json:"protocol"`
	Weight      int       `gorm:"column:weight;default:100" json:"weight"`
	Status      string    `gorm:"column:status;default:active" json:"status"`
	LastHealth  int64     `gorm:"column:last_health" json:"lastHealth"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (ServiceEndpoint) TableName() string {
	return "gateway_service_endpoints"
}

type AccessLog struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	RequestID   string    `gorm:"column:request_id;index" json:"requestId"`
	ClientIP    string    `gorm:"column:client_ip" json:"clientIp"`
	Method      string    `gorm:"column:method" json:"method"`
	Path        string    `gorm:"column:path;index" json:"path"`
	Query       string    `gorm:"column:query" json:"query"`
	Scheme      string    `gorm:"column:scheme" json:"scheme"`
	Host        string    `gorm:"column:host" json:"host"`
	UserAgent   string    `gorm:"column:user_agent" json:"userAgent"`
	UpstreamURI string    `gorm:"column:upstream_uri" json:"upstreamUri"`
	StatusCode  int       `gorm:"column:status_code" json:"statusCode"`
	LatencyMs   int64     `gorm:"column:latency_ms" json:"latencyMs"`
	RequestSize  int64    `gorm:"column:request_size" json:"requestSize"`
	ResponseSize int64    `gorm:"column:response_size" json:"responseSize"`
	Error       string    `gorm:"column:error" json:"error"`
	Timestamp   int64     `gorm:"column:timestamp;index" json:"timestamp"`
	CreatedAt   time.Time `json:"createdAt"`
}

func (AccessLog) TableName() string {
	return "gateway_access_logs"
}

type RewriteRule struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	PathPattern string    `gorm:"column:path_pattern" json:"pathPattern"`
	Replacement string    `gorm:"column:replacement" json:"replacement"`
	Regex       bool      `gorm:"column:regex;default:false" json:"regex"`
	Flag        string    `gorm:"column:flag" json:"flag"`
	Enabled     bool      `gorm:"column:enabled;default:true" json:"enabled"`
	Priority    int       `gorm:"column:priority;default:0" json:"priority"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (RewriteRule) TableName() string {
	return "gateway_rewrite_rules"
}

type RouteConfig struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	RouteID     string    `gorm:"column:route_id;uniqueIndex" json:"routeId"`
	Uri         string    `gorm:"column:uri" json:"uri"`
	Predicates  string    `gorm:"column:predicates" json:"predicates"`
	Filters     string    `gorm:"column:filters" json:"filters"`
	Metadata    string    `gorm:"column:metadata" json:"metadata"`
	Enabled     bool      `gorm:"column:enabled;default:true" json:"enabled"`
	Priority    int       `gorm:"column:priority;default:0" json:"priority"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (RouteConfig) TableName() string {
	return "gateway_route_configs"
}