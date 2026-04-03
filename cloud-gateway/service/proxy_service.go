package service

import (
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/cloudrealm/cloud-gateway/models"
	"github.com/gin-gonic/gin"
	"github.com/go-resty/resty/v2"
)

type ProxyService struct {
	routes      []models.Route
	client      *resty.Client
	circuitMap  map[string]*CircuitBreakerState
	rewriteRules []models.RewriteRule
	mu          sync.RWMutex
}

type CircuitBreakerState struct {
	failures       int
	successes      int
	state          string
	lastFailure    time.Time
	halfOpenCalls  int
}

func NewProxyService() *ProxyService {
	client := resty.New().
		SetTimeout(30 * time.Second).
		SetTLSClientConfig(&tls.Config{InsecureSkipVerify: true}).
		SetRetryCount(3).
		SetHeader("X-Gateway", "cloud-gateway-go")

	return &ProxyService{
		routes:      getDefaultRoutes(),
		client:      client,
		circuitMap: make(map[string]*CircuitBreakerState),
		rewriteRules: getDefaultRewriteRules(),
	}
}

func (s *ProxyService) SetRoutes(routes []models.Route) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.routes = routes
}

func (s *ProxyService) GetRoutes() []models.Route {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.routes
}

func (s *ProxyService) FindRoute(ctx *gin.Context) *models.Route {
	s.mu.RLock()
	defer s.mu.RUnlock()

	requestPath := ctx.Request.URL.Path

	for _, route := range s.routes {
		for _, predicate := range route.Predicates {
			if predicate.Name == "Path" && len(predicate.Args) > 0 {
				pattern := predicate.Args[0]
				if matchPath(pattern, requestPath) {
					return &route
				}
			}
		}
	}

	return nil
}

func matchPath(pattern, requestPath string) bool {
	pattern = strings.TrimPrefix(pattern, "/")
	requestPath = strings.TrimPrefix(requestPath, "/")

	if strings.HasSuffix(pattern, "/**") {
		prefix := strings.TrimSuffix(pattern, "/**")
		return strings.HasPrefix(requestPath, prefix)
	}

	if strings.HasSuffix(pattern, "*") {
		prefix := strings.TrimSuffix(pattern, "*")
		return strings.HasPrefix(requestPath, prefix)
	}

	return requestPath == pattern || requestPath == pattern+"/"
}

func (s *ProxyService) RewritePath(originalPath string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, rule := range s.rewriteRules {
		if !rule.Enabled {
			continue
		}

		if rule.Regex {
			replaced, err := replaceRegex(originalPath, rule.PathPattern, rule.Replacement)
			if err == nil && replaced != originalPath {
				return replaced
			}
		} else if strings.HasPrefix(originalPath, rule.PathPattern) {
			return strings.Replace(originalPath, rule.PathPattern, rule.Replacement, 1)
		}
	}

	return originalPath
}

func replaceRegex(input, pattern, replacement string) (string, error) {
	result := input
	if strings.Contains(pattern, "(") && strings.Contains(pattern, ")") {
		simplePattern := strings.Trim(pattern, "()")
		if strings.Contains(input, simplePattern) {
			result = strings.Replace(input, simplePattern, replacement, 1)
		}
	}
	return result, nil
}

func (s *ProxyService) ProxyRequest(ctx *gin.Context, route *models.Route) error {
	upstreamURL := route.URI

	if strings.HasPrefix(upstreamURL, "lb://") {
		serviceName := strings.TrimPrefix(upstreamURL, "lb://")
		upstreamURL = s.getLoadBalancedURL(serviceName)
		if upstreamURL == "" {
			return fmt.Errorf("no available endpoint for service: %s", serviceName)
		}
	}

	if s.isCircuitOpen(route.ID) {
		return fmt.Errorf("circuit breaker is open for: %s", route.ID)
	}

	rewrittenPath := s.RewritePath(ctx.Request.URL.Path)
	fullURL := upstreamURL + rewrittenPath

	if ctx.Request.URL.RawQuery != "" {
		fullURL += "?" + ctx.Request.URL.RawQuery
	}

	var resp *resty.Response
	var err error

	switch ctx.Request.Method {
	case http.MethodGet:
		resp, err = s.client.R().
			SetHeaders(map[string]string{
				"X-Forwarded-For":   ctx.ClientIP(),
				"X-Forwarded-Proto":  ctx.Request.URL.Scheme,
				"X-Forwarded-Host":   ctx.Request.Host,
				"X-Real-IP":          ctx.ClientIP(),
			}).
			SetContext(ctx.Request.Context()).
			Get(fullURL)
	case http.MethodPost:
		body, _ := io.ReadAll(ctx.Request.Body)
		resp, err = s.client.R().
			SetHeaders(map[string]string{
				"X-Forwarded-For":   ctx.ClientIP(),
				"X-Forwarded-Proto":  ctx.Request.URL.Scheme,
				"X-Forwarded-Host":   ctx.Request.Host,
				"X-Real-IP":          ctx.ClientIP(),
			}).
			SetHeader("Content-Type", ctx.GetHeader("Content-Type")).
			SetBody(body).
			SetContext(ctx.Request.Context()).
			Post(fullURL)
	case http.MethodPut:
		body, _ := io.ReadAll(ctx.Request.Body)
		resp, err = s.client.R().
			SetHeaders(map[string]string{
				"X-Forwarded-For":   ctx.ClientIP(),
				"X-Forwarded-Proto":  ctx.Request.URL.Scheme,
				"X-Forwarded-Host":   ctx.Request.Host,
				"X-Real-IP":          ctx.ClientIP(),
			}).
			SetHeader("Content-Type", ctx.GetHeader("Content-Type")).
			SetBody(body).
			SetContext(ctx.Request.Context()).
			Put(fullURL)
	case http.MethodDelete:
		resp, err = s.client.R().
			SetHeaders(map[string]string{
				"X-Forwarded-For":   ctx.ClientIP(),
				"X-Forwarded-Proto":  ctx.Request.URL.Scheme,
				"X-Forwarded-Host":   ctx.Request.Host,
				"X-Real-IP":          ctx.ClientIP(),
			}).
			SetContext(ctx.Request.Context()).
			Delete(fullURL)
	case http.MethodPatch:
		body, _ := io.ReadAll(ctx.Request.Body)
		resp, err = s.client.R().
			SetHeaders(map[string]string{
				"X-Forwarded-For":   ctx.ClientIP(),
				"X-Forwarded-Proto":  ctx.Request.URL.Scheme,
				"X-Forwarded-Host":   ctx.Request.Host,
				"X-Real-IP":          ctx.ClientIP(),
			}).
			SetHeader("Content-Type", ctx.GetHeader("Content-Type")).
			SetBody(body).
			SetContext(ctx.Request.Context()).
			Patch(fullURL)
	default:
		return fmt.Errorf("unsupported method: %s", ctx.Request.Method)
	}

	if err != nil {
		s.recordFailure(route.ID)
		return fmt.Errorf("proxy error: %v", err)
	}

	s.recordSuccess(route.ID)

	for k, v := range resp.Header() {
		for _, hv := range v {
			if strings.ToLower(k) != "content-length" {
				ctx.Header(k, hv)
			}
		}
	}

	ctx.Status(resp.StatusCode())
	ctx.Data(resp.StatusCode(), resp.Header().Get("Content-Type"), resp.Body())

	return nil
}

func (s *ProxyService) getLoadBalancedURL(serviceName string) string {
	return getServiceURL(serviceName)
}

func (s *ProxyService) isCircuitOpen(serviceName string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	state, exists := s.circuitMap[serviceName]
	if !exists {
		return false
	}

	switch state.state {
	case "open":
		if time.Since(state.lastFailure) > 30*time.Second {
			state.state = "half-open"
			state.halfOpenCalls = 0
			return false
		}
		return true
	case "half-open":
		if state.halfOpenCalls >= 3 {
			return true
		}
		state.halfOpenCalls++
		return false
	default:
		return false
	}
}

func (s *ProxyService) recordFailure(serviceName string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state, exists := s.circuitMap[serviceName]
	if !exists {
		state = &CircuitBreakerState{}
		s.circuitMap[serviceName] = state
	}

	state.failures++
	state.successes = 0
	state.lastFailure = time.Now()

	if state.failures >= 5 {
		state.state = "open"
	}
}

func (s *ProxyService) recordSuccess(serviceName string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state, exists := s.circuitMap[serviceName]
	if !exists {
		return
	}

	state.successes++
	state.failures = 0

	if state.state == "half-open" && state.successes >= 3 {
		state.state = "closed"
		state.failures = 0
		state.halfOpenCalls = 0
	}
}

func (s *ProxyService) GetCircuitBreakerStatus(serviceName string) map[string]interface{} {
	s.mu.RLock()
	defer s.mu.RUnlock()

	state, exists := s.circuitMap[serviceName]
	if !exists {
		return map[string]interface{}{
			"state": "closed",
			"failures": 0,
		}
	}

	return map[string]interface{}{
		"state":   state.state,
		"failures": state.failures,
		"successes": state.successes,
	}
}

func (s *ProxyService) GetServiceEndpoints(serviceName string) []models.ServiceEndpoint {
	return getMockEndpoints(serviceName)
}

func (s *ProxyService) GetAccessLogs(path string, page, size int) ([]models.AccessLog, int64) {
	logs := getMockAccessLogs(path)
	total := int64(len(logs))

	start := page * size
	if start >= len(logs) {
		return []models.AccessLog{}, total
	}

	end := start + size
	if end > len(logs) {
		end = len(logs)
	}

	return logs[start:end], total
}

func getServiceURL(serviceName string) string {
	switch serviceName {
	case "cloudrealm-platform":
		return "http://localhost:8080"
	case "cloud-server-go":
		return "http://localhost:8080"
	case "cloud-aiops":
		return "http://localhost:8000"
	default:
		return "http://localhost:8080"
	}
}

func getDefaultRoutes() []models.Route {
	return []models.Route{
		{
			ID:   "platform-service",
			URI:  "lb://cloudrealm-platform",
			Predicates: []models.Predicate{
				{Name: "Path", Args: []string{"/api/**"}},
			},
		},
		{
			ID:   "aiops-service",
			URI:  "http://localhost:8000",
			Predicates: []models.Predicate{
				{Name: "Path", Args: []string{"/api/aiops/**"}},
			},
		},
		{
			ID:   "jmx-service",
			URI:  "http://localhost:9090",
			Predicates: []models.Predicate{
				{Name: "Path", Args: []string{"/jmx/**"}},
			},
		},
		{
			ID:   "monitor-service",
			URI:  "http://localhost:8080",
			Predicates: []models.Predicate{
				{Name: "Path", Args: []string{"/api/monitor/**"}},
			},
		},
	}
}

func getDefaultRewriteRules() []models.RewriteRule {
	return []models.RewriteRule{
		{
			ID:          1,
			PathPattern: "/api/v1/",
			Replacement: "/api/",
			Enabled:     true,
			Priority:    0,
		},
	}
}

func getMockEndpoints(serviceName string) []models.ServiceEndpoint {
	now := time.Now().UnixMilli()
	return []models.ServiceEndpoint{
		{
			ID:          1,
			ServiceName: serviceName,
			Host:        "localhost",
			Port:        8080,
			Protocol:    "http",
			Weight:      100,
			Status:      "active",
			LastHealth:  now,
		},
	}
}

func getMockAccessLogs(path string) []models.AccessLog {
	now := time.Now().UnixMilli()
	return []models.AccessLog{
		{
			ID:          1,
			RequestID:   "req-001",
			ClientIP:    "192.168.1.100",
			Method:      "GET",
			Path:        "/api/services",
			Query:       "",
			Scheme:      "http",
			Host:        "localhost:8080",
			UserAgent:   "Mozilla/5.0",
			UpstreamURI: "http://localhost:8080/api/services",
			StatusCode:  200,
			LatencyMs:   45,
			RequestSize: 0,
			ResponseSize: 1245,
			Error:       "",
			Timestamp:   now - 60000,
		},
		{
			ID:          2,
			RequestID:   "req-002",
			ClientIP:    "192.168.1.101",
			Method:      "POST",
			Path:        "/api/hosts",
			Query:       "",
			Scheme:      "http",
			Host:        "localhost:8080",
			UserAgent:   "Mozilla/5.0",
			UpstreamURI: "http://localhost:8080/api/hosts",
			StatusCode:  201,
			LatencyMs:   120,
			RequestSize: 256,
			ResponseSize: 512,
			Error:       "",
			Timestamp:   now - 120000,
		},
		{
			ID:          3,
			RequestID:   "req-003",
			ClientIP:    "192.168.1.102",
			Method:      "GET",
			Path:        "/api/aiops/anomalies",
			Query:       "page=0&size=20",
			Scheme:      "http",
			Host:        "localhost:8080",
			UserAgent:   "curl/7.68.0",
			UpstreamURI: "http://localhost:8000/api/aiops/anomalies?page=0&size=20",
			StatusCode:  200,
			LatencyMs:   85,
			RequestSize: 0,
			ResponseSize: 3456,
			Error:       "",
			Timestamp:   now - 180000,
		},
	}
}

type RouterManager struct {
	routes    map[string]*RouteInfo
	Predicate PredicateMatcher
	Filter    []FilterFunc
	mu        sync.RWMutex
}

type RouteInfo struct {
	ID         string
	URI        string
	Predicates []models.Predicate
	Filters    []FilterFunc
	Metadata   map[string]string
}

type PredicateMatcher interface {
	Match(ctx *gin.Context, predicate models.Predicate) bool
}

type FilterFunc func(c *gin.Context)

func NewRouterManager() *RouterManager {
	return &RouterManager{
		routes: make(map[string]*RouteInfo),
		Predicate: &DefaultPredicateMatcher{},
		Filter:    make([]FilterFunc, 0),
	}
}

func (rm *RouterManager) AddRoute(route *RouteInfo) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	rm.routes[route.ID] = route
}

func (rm *RouterManager) RemoveRoute(id string) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	delete(rm.routes, id)
}

func (rm *RouterManager) GetRoute(id string) (*RouteInfo, bool) {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	route, exists := rm.routes[id]
	return route, exists
}

func (rm *RouterManager) GetAllRoutes() []*RouteInfo {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	routes := make([]*RouteInfo, 0, len(rm.routes))
	for _, r := range rm.routes {
		routes = append(routes, r)
	}
	return routes
}

func (rm *RouterManager) MatchRoute(ctx *gin.Context) *RouteInfo {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	for _, route := range rm.routes {
		matched := true
		for _, predicate := range route.Predicates {
			if !rm.Predicate.Match(ctx, predicate) {
				matched = false
				break
			}
		}
		if matched {
			return route
		}
	}
	return nil
}

type DefaultPredicateMatcher struct{}

func (m *DefaultPredicateMatcher) Match(ctx *gin.Context, predicate models.Predicate) bool {
	if predicate.Name == "Path" && len(predicate.Args) > 0 {
		return matchPath(predicate.Args[0], ctx.Request.URL.Path)
	}
	return true
}

func parseURI(uri string) (scheme, host string, port int, path string, err error) {
	if strings.HasPrefix(uri, "http://") {
		uri = strings.TrimPrefix(uri, "http://")
	} else if strings.HasPrefix(uri, "https://") {
		uri = strings.TrimPrefix(uri, "https://")
	}

	parts := strings.SplitN(uri, "/", 2)
	hostPort := parts[0]
	path = "/"
	if len(parts) > 1 {
		path = "/" + parts[1]
	}

	if strings.Contains(hostPort, ":") {
		hostParts := strings.SplitN(hostPort, ":", 2)
		host = hostParts[0]
		fmt.Sscanf(hostParts[1], "%d", &port)
	} else {
		host = hostPort
		port = 80
	}

	return "http", host, port, path, nil
}

func buildUpstreamURL(scheme, host, port int, path string) string {
	if port == 80 || port == 443 {
		return fmt.Sprintf("%s://%s%s", scheme, host, path)
	}
	return fmt.Sprintf("%s://%s:%d%s", scheme, host, port, path)
}

func extractPathParams(pattern, path string) map[string]string {
	params := make(map[string]string)

	patternParts := strings.Split(pattern, "/")
	pathParts := strings.Split(path, "/")

	for i, pp := range patternParts {
		if i >= len(pathParts) {
			break
		}

		if strings.HasPrefix(pp, ":") {
			key := strings.TrimPrefix(pp, ":")
			params[key] = pathParts[i]
		}
	}

	return params
}

func (s *ProxyService) HealthCheck(serviceName string) bool {
	upstreamURL := getServiceURL(serviceName)
	if upstreamURL == "" {
		return false
	}

	healthURL := upstreamURL + "/health"
	resp, err := s.client.R().Get(healthURL)
	if err != nil {
		return false
	}

	return resp.StatusCode() == 200
}

func (s *ProxyService) IsCircuitOpen(serviceName string) bool {
	return s.isCircuitOpen(serviceName)
}