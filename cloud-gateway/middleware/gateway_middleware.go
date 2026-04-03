package middleware

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

func Logger() gin.HandlerFunc {
	return func(c *gin.Context) {
		startTime := time.Now()

		path := c.Request.URL.Path
		query := c.Request.URL.RawQuery
		method := c.Request.Method
		clientIP := c.ClientIP()

		if query != "" {
			path = path + "?" + query
		}

		c.Next()

		latency := time.Since(startTime)
		statusCode := c.Writer.Status()

		log.Printf("[%s] %s %s %d %v %s",
			time.Now().Format("2006-01-02 15:04:05"),
			method,
			path,
			statusCode,
			latency,
			clientIP,
		)
	}
}

func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			requestID = generateRequestID()
		}
		c.Set("requestID", requestID)
		c.Header("X-Request-ID", requestID)
		c.Next()
	}
}

func generateRequestID() string {
	b := make([]byte, 16)
	rand.Read(b)
	return hex.EncodeToString(b)
}

func CORSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Request-ID, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE, PATCH")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

func RateLimiter() gin.HandlerFunc {
	type clientInfo struct {
		count     int
		resetTime time.Time
	}

	clients := make(map[string]*clientInfo)
	var mu sync.Mutex

	rate := 100
	burst := 20
	windowDuration := time.Minute

	return func(c *gin.Context) {
		key := c.ClientIP()

		mu.Lock()

		client, exists := clients[key]
		now := time.Now()

		if !exists {
			clients[key] = &clientInfo{
				count:     1,
				resetTime: now.Add(windowDuration),
			}
			mu.Unlock()
			c.Next()
			return
		}

		if now.After(client.resetTime) {
			client.count = 1
			client.resetTime = now.Add(windowDuration)
			mu.Unlock()
			c.Next()
			return
		}

		if client.count >= rate {
			mu.Unlock()
			c.JSON(429, gin.H{
				"error":       "Rate limit exceeded",
				"message":     "Too many requests, please try again later",
				"retryAfter":  client.resetTime.Unix() - now.Unix(),
			})
			c.Abort()
			return
		}

		if client.count >= burst {
			remaining := rate - client.count
			c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", remaining))
			c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", client.resetTime.Unix()))
		}

		client.count++
		mu.Unlock()

		c.Next()
	}
}

func AuthenticationMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")

		if authHeader == "" {
			c.Set("authenticated", false)
		} else {
			if strings.HasPrefix(authHeader, "Bearer ") {
				token := strings.TrimPrefix(authHeader, "Bearer ")
				if token != "" {
					c.Set("authenticated", true)
					c.Set("token", token)
				}
			}
		}

		c.Next()
	}
}

func MetricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		startTime := time.Now()

		c.Next()

		duration := time.Since(startTime)
		statusCode := c.Writer.Status()
		path := c.Request.URL.Path

		log.Printf("[METRICS] path=%s method=%s status=%d duration=%v",
			path,
			c.Request.Method,
			statusCode,
			duration,
		)
	}
}

func TimeoutMiddleware(timeout time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		done := make(chan struct{})

		go func() {
			c.Next()
			close(done)
		}()

		select {
		case <-done:
			return
		case <-time.After(timeout):
			c.JSON(504, gin.H{
				"error":   "Gateway timeout",
				"message": "Request timeout after " + timeout.String(),
			})
			c.Abort()
		}
	}
}

func ValidateRequestMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		contentType := c.GetHeader("Content-Type")

		if c.Request.Method == "POST" || c.Request.Method == "PUT" || c.Request.Method == "PATCH" {
			if contentType != "" && contentType != "application/json" && contentType != "application/x-www-form-urlencoded" {
				c.JSON(415, gin.H{
					"error": "Unsupported Media Type",
				})
				c.Abort()
				return
			}
		}

		c.Next()
	}
}

func ProxyHeadersMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Header("X-Gateway", "cloud-gateway-go")
		c.Header("X-Content-Type-Options", "nosniff")
		c.Header("X-Frame-Options", "DENY")
		c.Next()
	}
}

func PanicRecovery() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[PANIC RECOVERY] %v", err)
				c.JSON(500, gin.H{
					"error":   "Internal Server Error",
					"message": "An unexpected error occurred",
				})
				c.Abort()
			}
		}()
		c.Next()
	}
}

func HMACSignMiddleware(secret string) gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.Method == "GET" {
			path := c.Request.URL.Path
			if c.Request.URL.RawQuery != "" {
				path += "?" + c.Request.URL.RawQuery
			}

			signature := c.GetHeader("X-Signature")
			if signature != "" {
				expectedSig := computeHMAC(path, secret)
				if signature == expectedSig {
					c.Set("signed", true)
				}
			}
		}
		c.Next()
	}
}

func computeHMAC(message string, secret string) string {
	h := sha256.New()
	h.Write([]byte(message))
	h.Write([]byte(secret))
	return hex.EncodeToString(h.Sum(nil))
}