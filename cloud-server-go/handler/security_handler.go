package handler

import (
	"net/http"
	"strings"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type SecurityHandler struct {
	svc *service.SecurityService
}

func NewSecurityHandler(svc *service.SecurityService) *SecurityHandler {
	return &SecurityHandler{svc: svc}
}

func (h *SecurityHandler) Login(c *gin.Context) {
	var req models.LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "用户名和密码不能为空"})
		return
	}

	resp, err := h.svc.Login(req.Username, req.Password)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func (h *SecurityHandler) Register(c *gin.Context) {
	var req struct {
		Username    string `json:"username" binding:"required"`
		Password    string `json:"password" binding:"required"`
		DisplayName string `json:"displayName"`
		Email       string `json:"email"`
		Phone       string `json:"phone"`
		Department  string `json:"department"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "用户名和密码不能为空"})
		return
	}
	
	resp, err := h.svc.Register(req.Username, req.Password, req.DisplayName, req.Email, req.Phone, req.Department)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func (h *SecurityHandler) GetUsers(c *gin.Context) {
	users, err := h.svc.GetAllUsers()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, users)
}

func (h *SecurityHandler) GetActiveUsers(c *gin.Context) {
	users, err := h.svc.GetActiveUsers()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, users)
}

func (h *SecurityHandler) GetUser(c *gin.Context) {
	userIdStr := c.Param("id")
	var userId int
	if _, err := strings.NewReader(userIdStr).Read(nil); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
		return
	}

	for _, ch := range userIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}
		userId = userId*10 + int(ch-'0')
	}

	user, err := h.svc.GetUserById(userId)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, user)
}

func (h *SecurityHandler) GetUserByName(c *gin.Context) {
	userName := c.Param("name")
	user, err := h.svc.GetUserByName(userName)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, user)
}

func (h *SecurityHandler) CreateUser(c *gin.Context) {
	var user models.User
	if err := c.ShouldBindJSON(&user); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreateUser(&user)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *SecurityHandler) UpdateUser(c *gin.Context) {
	userIdStr := c.Param("id")
	var userId int
	for _, ch := range userIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}
		userId = userId*10 + int(ch-'0')
	}

	var user models.User
	if err := c.ShouldBindJSON(&user); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	updated, err := h.svc.UpdateUser(userId, &user)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, updated)
}

func (h *SecurityHandler) DeleteUser(c *gin.Context) {
	userIdStr := c.Param("id")
	var userId int
	for _, ch := range userIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}
		userId = userId*10 + int(ch-'0')
	}

	_, err := h.svc.DeleteUser(userId)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "用户删除成功"})
}

func (h *SecurityHandler) ChangePassword(c *gin.Context) {
	userIdStr := c.Param("id")
	var userId int
	for _, ch := range userIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}
		userId = userId*10 + int(ch-'0')
	}

	var req models.ChangePasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	err := h.svc.ChangePassword(userId, req.OldPassword, req.NewPassword)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "密码修改成功"})
}

func (h *SecurityHandler) GetRoles(c *gin.Context) {
	roles, err := h.svc.GetAllRoles()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, roles)
}

func (h *SecurityHandler) GetRole(c *gin.Context) {
	authIdStr := c.Param("id")
	var authId int
	for _, ch := range authIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid role ID"})
			return
		}
		authId = authId*10 + int(ch-'0')
	}

	role, err := h.svc.GetRoleById(authId)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, role)
}

func (h *SecurityHandler) CreateRole(c *gin.Context) {
	var role models.Role
	if err := c.ShouldBindJSON(&role); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreateRole(&role)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *SecurityHandler) UpdateRole(c *gin.Context) {
	authIdStr := c.Param("id")
	var authId int
	for _, ch := range authIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid role ID"})
			return
		}
		authId = authId*10 + int(ch-'0')
	}

	var role models.Role
	if err := c.ShouldBindJSON(&role); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	updated, err := h.svc.UpdateRole(authId, &role)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, updated)
}

func (h *SecurityHandler) DeleteRole(c *gin.Context) {
	authIdStr := c.Param("id")
	var authId int
	for _, ch := range authIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid role ID"})
			return
		}
		authId = authId*10 + int(ch-'0')
	}

	_, err := h.svc.DeleteRole(authId)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "角色删除成功"})
}

func (h *SecurityHandler) AssignRole(c *gin.Context) {
	var body struct {
		UserID int `json:"userId" binding:"required"`
		AuthID int `json:"authId" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	_, err := h.svc.AssignRoleToUser(body.UserID, body.AuthID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "角色分配成功"})
}

func (h *SecurityHandler) RemoveRole(c *gin.Context) {
	var body struct {
		UserID int `json:"userId" binding:"required"`
		AuthID int `json:"authId" binding:"required"`
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	_, err := h.svc.RemoveRoleFromUser(body.UserID, body.AuthID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"success": true, "message": "角色移除成功"})
}

func (h *SecurityHandler) GetUserRoles(c *gin.Context) {
	userIdStr := c.Param("id")
	var userId int
	for _, ch := range userIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
			return
		}
		userId = userId*10 + int(ch-'0')
	}

	roles, err := h.svc.GetUserRoles(userId)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, roles)
}

func (h *SecurityHandler) GetRoleUsers(c *gin.Context) {
	authIdStr := c.Param("id")
	var authId int
	for _, ch := range authIdStr {
		if ch < '0' || ch > '9' {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid role ID"})
			return
		}
		authId = authId*10 + int(ch-'0')
	}

	users, err := h.svc.GetRoleUsers(authId)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, users)
}

func (h *SecurityHandler) RegisterRoutes(r *gin.RouterGroup) {
	auth := r.Group("/auth")
	{
		auth.POST("/login", h.Login)
		auth.POST("/register", h.Register)
	}

	users := r.Group("/users")
	{
		users.GET("", h.GetUsers)
		users.GET("/active", h.GetActiveUsers)
		users.POST("", h.CreateUser)
		users.GET("/:id", h.GetUser)
		users.GET("/name/:name", h.GetUserByName)
		users.PUT("/:id", h.UpdateUser)
		users.DELETE("/:id", h.DeleteUser)
		users.POST("/:id/password", h.ChangePassword)
		users.GET("/:id/roles", h.GetUserRoles)
	}

	roles := r.Group("/roles")
	{
		roles.GET("", h.GetRoles)
		roles.POST("", h.CreateRole)
		roles.GET("/:id", h.GetRole)
		roles.PUT("/:id", h.UpdateRole)
		roles.DELETE("/:id", h.DeleteRole)
		roles.GET("/:id/users", h.GetRoleUsers)
	}

	userRoles := r.Group("/user-roles")
	{
		userRoles.POST("/assign", h.AssignRole)
		userRoles.POST("/remove", h.RemoveRole)
	}
}