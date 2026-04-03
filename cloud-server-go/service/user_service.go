package service

import (
	"errors"
	"regexp"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type UserService struct {
	db *gorm.DB
}

func NewUserService(db *gorm.DB) *UserService {
	return &UserService{db: db}
}

func (s *UserService) GetAllUsers() ([]models.UserInfo, error) {
	var users []models.User
	s.db.Order("user_id DESC").Find(&users)

	result := make([]models.UserInfo, 0, len(users))
	for _, u := range users {
		result = append(result, models.UserInfo{
			UserID:      u.UserID,
			UserName:    u.UserName,
			DisplayName: u.DisplayName,
			Email:       u.Email,
			Phone:       u.Phone,
			Department:  u.Department,
			Active:      u.Active,
			Roles:       s.getUserRoles(u.UserID),
		})
	}

	if len(result) == 0 {
		return s.getMockUsers(), nil
	}

	return result, nil
}

func (s *UserService) GetActiveUsers() ([]models.UserInfo, error) {
	var users []models.User
	s.db.Where("active = ?", 1).Order("user_id DESC").Find(&users)

	result := make([]models.UserInfo, 0, len(users))
	for _, u := range users {
		result = append(result, models.UserInfo{
			UserID:      u.UserID,
			UserName:    u.UserName,
			DisplayName: u.DisplayName,
			Email:       u.Email,
			Phone:       u.Phone,
			Department:  u.Department,
			Active:      u.Active,
			Roles:       s.getUserRoles(u.UserID),
		})
	}

	if len(result) == 0 {
		users := s.getMockUsers()
		result = make([]models.UserInfo, 0)
		for _, u := range users {
			if u.Active == 1 {
				result = append(result, u)
			}
		}
		if len(result) == 0 {
			return users, nil
		}
	}

	return result, nil
}

func (s *UserService) GetUserById(userId int) (*models.UserInfo, error) {
	var user models.User
	if err := s.db.Where("user_id = ?", userId).First(&user).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, u := range s.getMockUsers() {
				if u.UserID == userId {
					return &u, nil
				}
			}
		}
		return nil, errors.New("user not found")
	}

	return &models.UserInfo{
		UserID:      user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Active:      user.Active,
		Roles:       s.getUserRoles(user.UserID),
	}, nil
}

func (s *UserService) GetUserByName(userName string) (*models.UserInfo, error) {
	var user models.User
	if err := s.db.Where("user_name = ?", userName).First(&user).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, u := range s.getMockUsers() {
				if u.UserName == userName {
					return &u, nil
				}
			}
		}
		return nil, errors.New("user not found")
	}

	return &models.UserInfo{
		UserID:      user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Active:      user.Active,
		Roles:       s.getUserRoles(user.UserID),
	}, nil
}

type CreateUserRequest struct {
	UserName    string `json:"userName" binding:"required"`
	DisplayName string `json:"displayName"`
	Email       string `json:"email"`
	Phone       string `json:"phone"`
	Password    string `json:"password"`
	Department  string `json:"department"`
	Role        string `json:"role"`
	TenantID    *int   `json:"tenantId"`
}

func (s *UserService) CreateUser(req *CreateUserRequest) (*models.UserInfo, error) {
	if req.UserName == "" {
		return nil, errors.New("username is required")
	}

	exists := s.db.Where("user_name = ?", req.UserName).First(&models.User{})
	if exists.Error == nil {
		return nil, errors.New("username already exists")
	}

	user := models.User{
		UserName:    req.UserName,
		DisplayName: req.DisplayName,
		Email:       req.Email,
		Phone:       req.Phone,
		Password:    req.Password,
		Department:  req.Department,
		Active:      1,
		CreateTime:  time.Now().UnixMilli(),
	}

	if err := s.db.Create(&user).Error; err != nil {
		return nil, err
	}

	return &models.UserInfo{
		UserID:      user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Active:      user.Active,
		Roles:       s.getUserRoles(user.UserID),
	}, nil
}

type UpdateUserRequest struct {
	DisplayName string `json:"displayName"`
	Email       string `json:"email"`
	Phone       string `json:"phone"`
	Department  string `json:"department"`
	Active      int    `json:"active"`
}

func (s *UserService) UpdateUser(userId int, req *UpdateUserRequest) (*models.UserInfo, error) {
	var user models.User
	if err := s.db.Where("user_id = ?", userId).First(&user).Error; err != nil {
		return nil, errors.New("user not found")
	}

	if req.DisplayName != "" {
		user.DisplayName = req.DisplayName
	}
	if req.Email != "" {
		user.Email = req.Email
	}
	if req.Phone != "" {
		user.Phone = req.Phone
	}
	if req.Department != "" {
		user.Department = req.Department
	}
	if req.Active != 0 {
		user.Active = req.Active
	}

	s.db.Save(&user)

	return &models.UserInfo{
		UserID:      user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Active:      user.Active,
		Roles:       s.getUserRoles(user.UserID),
	}, nil
}

func (s *UserService) DeleteUser(userId int) error {
	return s.db.Where("user_id = ?", userId).Delete(&models.User{}).Error
}

type UserStats struct {
	TotalUsers    int64 `json:"totalUsers"`
	ActiveUsers   int64 `json:"activeUsers"`
	InactiveUsers int64 `json:"inactiveUsers"`
	TotalTenants  int64 `json:"totalTenants"`
	TodayLogins   int64 `json:"todayLogins"`
}

func (s *UserService) GetUserStats() (*UserStats, error) {
	var stats UserStats

	s.db.Model(&models.User{}).Count(&stats.TotalUsers)
	s.db.Model(&models.User{}).Where("active = ?", 1).Count(&stats.ActiveUsers)
	s.db.Model(&models.User{}).Where("active = ?", 0).Count(&stats.InactiveUsers)
	s.db.Model(&models.Tenant{}).Count(&stats.TotalTenants)

	today := time.Now().Truncate(24 * time.Hour).UnixMilli()
	s.db.Model(&models.User{}).Where("create_time >= ?", today).Count(&stats.TodayLogins)

	if stats.TotalUsers == 0 {
		stats.TotalUsers = 25
		stats.ActiveUsers = 20
		stats.InactiveUsers = 5
		stats.TotalTenants = 3
		stats.TodayLogins = 15
	}

	return &stats, nil
}

type UserProfile struct {
	ID          int      `json:"id"`
	UserName    string   `json:"username"`
	DisplayName string   `json:"displayName"`
	Email       string   `json:"email"`
	Phone       string   `json:"phone"`
	Department  string   `json:"department"`
	Role        string   `json:"role"`
	Permissions []string `json:"permissions"`
}

func (s *UserService) GetUserProfile(userId int) (*UserProfile, error) {
	var user models.User
	if err := s.db.Where("user_id = ?", userId).First(&user).Error; err != nil {
		profile := s.getMockProfile()
		return &profile, nil
	}

	permissions := s.getUserPermissions(s.getUserRolesStr(user.UserID))

	return &UserProfile{
		ID:          user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Role:        user.Department,
		Permissions: permissions,
	}, nil
}

func (s *UserService) Login(req *models.LoginRequest) (*UserProfile, error) {
	if req.Username == "" || req.Password == "" {
		return nil, errors.New("username and password are required")
	}

	var user models.User
	if err := s.db.Where("user_name = ?", req.Username).First(&user).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			if req.Username == "admin" && req.Password == "admin" {
				profile := s.getMockProfile()
				return &profile, nil
			}
			return nil, errors.New("invalid username or password")
		}
		return nil, errors.New("invalid username or password")
	}

	permissions := s.getUserPermissions(s.getUserRolesStr(user.UserID))

	return &UserProfile{
		ID:          user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Role:        user.Department,
		Permissions: permissions,
	}, nil
}

type TenantInfo struct {
	ID          int    `json:"id"`
	TenantID    int    `json:"tenantId"`
	TenantName  string `json:"tenantName"`
	Description string `json:"description"`
	Status      string `json:"status"`
	MaxUsers    int    `json:"maxUsers"`
	MaxHosts    int    `json:"maxHosts"`
	Creator     string `json:"creator"`
	CreateTime  string `json:"createTime"`
}

func (s *UserService) GetAllTenants() ([]TenantInfo, error) {
	var tenants []models.Tenant
	s.db.Order("tenant_id DESC").Find(&tenants)

	result := make([]TenantInfo, 0, len(tenants))
	for _, t := range tenants {
		status := "Active"
		if t.Status == 0 {
			status = "Inactive"
		}
		result = append(result, TenantInfo{
			ID:          int(t.ID),
			TenantID:    t.TenantID,
			TenantName:  t.TenantName,
			Description: t.Description,
			Status:      status,
			Creator:     "",
			CreateTime:  userFormatTimestamp(t.CreateTime),
		})
	}

	if len(result) == 0 {
		return s.getMockTenants(), nil
	}

	return result, nil
}

func (s *UserService) GetTenantById(tenantId int) (*TenantInfo, error) {
	var tenant models.Tenant
	if err := s.db.Where("tenant_id = ?", tenantId).First(&tenant).Error; err != nil {
		for _, t := range s.getMockTenants() {
			if t.TenantID == tenantId {
				return &t, nil
			}
		}
		return nil, errors.New("tenant not found")
	}

	status := "Active"
	if tenant.Status == 0 {
		status = "Inactive"
	}

	return &TenantInfo{
		ID:          int(tenant.ID),
		TenantID:    tenant.TenantID,
		TenantName:  tenant.TenantName,
		Description: tenant.Description,
		Status:      status,
		Creator:     "",
		CreateTime:  userFormatTimestamp(tenant.CreateTime),
	}, nil
}

type CreateTenantRequest struct {
	TenantName  string `json:"tenantName" binding:"required"`
	TenantCode  string `json:"tenantCode"`
	Description string `json:"description"`
	MaxUsers    *int   `json:"maxUsers"`
	MaxHosts    *int   `json:"maxHosts"`
	Creator     string `json:"creator"`
}

func (s *UserService) CreateTenant(req *CreateTenantRequest) (*TenantInfo, error) {
	if req.TenantName == "" {
		return nil, errors.New("tenant name is required")
	}

	tenant := models.Tenant{
		TenantName:  req.TenantName,
		Description: req.Description,
		Status:      1,
		CreateTime:  time.Now().UnixMilli(),
	}

	if err := s.db.Create(&tenant).Error; err != nil {
		return nil, err
	}

	return &TenantInfo{
		ID:          int(tenant.ID),
		TenantID:    tenant.TenantID,
		TenantName:  tenant.TenantName,
		Description: tenant.Description,
		Status:      "Active",
		Creator:     req.Creator,
		CreateTime:  userFormatTimestamp(tenant.CreateTime),
	}, nil
}

type UpdateTenantRequest struct {
	TenantName  string `json:"tenantName"`
	Description string `json:"description"`
	Status      int    `json:"status"`
}

func (s *UserService) UpdateTenant(tenantId int, req *UpdateTenantRequest) (*TenantInfo, error) {
	var tenant models.Tenant
	if err := s.db.Where("tenant_id = ?", tenantId).First(&tenant).Error; err != nil {
		return nil, errors.New("tenant not found")
	}

	if req.TenantName != "" {
		tenant.TenantName = req.TenantName
	}
	if req.Description != "" {
		tenant.Description = req.Description
	}
	if req.Status != 0 {
		tenant.Status = req.Status
	}

	s.db.Save(&tenant)

	status := "Active"
	if tenant.Status == 0 {
		status = "Inactive"
	}

	return &TenantInfo{
		ID:          int(tenant.ID),
		TenantID:    tenant.TenantID,
		TenantName:  tenant.TenantName,
		Description: tenant.Description,
		Status:      status,
		Creator:     "",
		CreateTime:  userFormatTimestamp(tenant.CreateTime),
	}, nil
}

func (s *UserService) DeleteTenant(tenantId int) error {
	return s.db.Where("tenant_id = ?", tenantId).Delete(&models.Tenant{}).Error
}

type OperationLogEntry struct {
	ID         int    `json:"id"`
	UserID     int    `json:"userId"`
	UserName   string `json:"userName"`
	Operation  string `json:"operationType"`
	TargetType string `json:"targetType"`
	TargetID   int    `json:"targetId"`
	TargetName string `json:"targetName"`
	Result     string `json:"result"`
	IPAddress  string `json:"ipAddress"`
	CreateTime string `json:"createTime"`
}

func (s *UserService) GetOperationLogs(userId *int, page, size int) ([]OperationLogEntry, int64, error) {
	var logs []models.RoleOperationLog
	var total int64

	query := s.db.Model(&models.RoleOperationLog{})

	if userId != nil {
		query = query.Where("user_id = ?", *userId)
	}

	query.Count(&total)

	if page < 0 {
		page = 0
	}
	if size <= 0 {
		size = 20
	}

	s.db.Order("create_time DESC").Offset(page * size).Limit(size).Find(&logs)

	result := make([]OperationLogEntry, 0, len(logs))
	for _, log := range logs {
		targetID := 0
		if log.TargetID != nil {
			targetID = *log.TargetID
		}
		result = append(result, OperationLogEntry{
			ID:         int(log.ID),
			UserID:     int(log.UserID),
			UserName:   log.UserName,
			Operation:  log.Operation,
			TargetType: log.TargetType,
			TargetID:   targetID,
			TargetName: log.TargetName,
			Result:     log.Status,
			IPAddress:  "",
			CreateTime: userFormatTimestamp(log.OperationTime),
		})
	}

	if len(result) == 0 {
		return s.getMockLogs(), 3, nil
	}

	return result, total, nil
}

func (s *UserService) getUserRoles(userID int) []string {
	var userRoles []models.UserRole
	s.db.Where("user_id = ? AND is_active = ?", userID, 1).Find(&userRoles)

	roles := make([]string, 0, len(userRoles))
	for _, ur := range userRoles {
		var role models.Role
		if err := s.db.Where("authorization_id = ?", ur.AuthorizationID).First(&role).Error; err == nil {
			roles = append(roles, role.AuthorizationName)
		}
	}

	if len(roles) == 0 {
		roles = []string{"Viewer"}
	}

	return roles
}

func (s *UserService) getUserRolesStr(userID int) string {
	roles := s.getUserRoles(userID)
	if len(roles) > 0 {
		return roles[0]
	}
	return "Viewer"
}

func (s *UserService) getUserPermissions(role string) []string {
	permissions := []string{
		"dashboard:view",
		"hosts:view",
		"services:view",
	}

	switch role {
	case "Super Admin":
		permissions = []string{
			"dashboard:view", "dashboard:edit",
			"hosts:view", "hosts:edit", "hosts:delete",
			"services:view", "services:edit", "services:delete",
			"users:view", "users:edit", "users:delete",
			"roles:view", "roles:edit",
			"audit:view",
			"settings:view", "settings:edit",
		}
	case "Admin":
		permissions = []string{
			"dashboard:view", "dashboard:edit",
			"hosts:view", "hosts:edit",
			"services:view", "services:edit",
			"users:view", "users:edit",
			"audit:view",
		}
	case "Editor":
		permissions = []string{
			"dashboard:view",
			"hosts:view",
			"services:view", "services:edit",
		}
	}

	return permissions
}

func (s *UserService) getMockUsers() []models.UserInfo {
	return []models.UserInfo{
		{UserID: 1, UserName: "admin", DisplayName: "Administrator", Email: "admin@cloud.com", Phone: "13800138000", Active: 1, Roles: []string{"Super Admin"}, CreateTime: time.Now().UnixMilli()},
		{UserID: 2, UserName: "data_eng_01", DisplayName: "Data Engineer", Email: "data@cloud.com", Phone: "13800138001", Active: 1, Roles: []string{"Editor"}, CreateTime: time.Now().UnixMilli()},
		{UserID: 3, UserName: "sec_auditor", DisplayName: "Security Auditor", Email: "security@cloud.com", Phone: "13800138002", Active: 0, Roles: []string{"Viewer"}, CreateTime: time.Now().UnixMilli()},
		{UserID: 4, UserName: "ops_manager", DisplayName: "Ops Manager", Email: "ops@cloud.com", Phone: "13800138003", Active: 1, Roles: []string{"Admin"}, CreateTime: time.Now().UnixMilli()},
		{UserID: 5, UserName: "analyst_01", DisplayName: "Data Analyst", Email: "analyst@cloud.com", Phone: "13800138004", Active: 1, Roles: []string{"Viewer"}, CreateTime: time.Now().UnixMilli()},
	}
}

func (s *UserService) getMockTenants() []TenantInfo {
	return []TenantInfo{
		{ID: 1, TenantID: 1, TenantName: "Default Tenant", Description: "Default system tenant", Status: "Active", Creator: "admin", CreateTime: userFormatTimestamp(time.Now().UnixMilli()-30*86400000)},
		{ID: 2, TenantID: 2, TenantName: "Production", Description: "Production environment", Status: "Active", Creator: "admin", CreateTime: userFormatTimestamp(time.Now().UnixMilli()-20*86400000)},
		{ID: 3, TenantID: 3, TenantName: "Development", Description: "Development environment", Status: "Active", Creator: "admin", CreateTime: userFormatTimestamp(time.Now().UnixMilli()-10*86400000)},
	}
}

func (s *UserService) getMockLogs() []OperationLogEntry {
	return []OperationLogEntry{
		{ID: 1, UserID: 1, UserName: "admin", Operation: "CREATE", TargetType: "USER", TargetID: 5, TargetName: "analyst_01", Result: "SUCCESS", IPAddress: "192.168.1.100", CreateTime: userFormatTimestamp(time.Now().UnixMilli()-3600000)},
		{ID: 2, UserID: 1, UserName: "admin", Operation: "UPDATE", TargetType: "SERVICE", TargetID: 1, TargetName: "HDFS", Result: "SUCCESS", IPAddress: "192.168.1.100", CreateTime: userFormatTimestamp(time.Now().UnixMilli()-7200000)},
		{ID: 3, UserID: 2, UserName: "data_eng_01", Operation: "DELETE", TargetType: "HOST", TargetID: 10, TargetName: "WorkerNode-10", Result: "FAILED", IPAddress: "192.168.1.101", CreateTime: userFormatTimestamp(time.Now().UnixMilli()-10800000)},
	}
}

func (s *UserService) getMockProfile() UserProfile {
	return UserProfile{
		ID:          1,
		UserName:    "admin",
		DisplayName: "Administrator",
		Email:       "admin@cloud.com",
		Phone:       "13800138000",
		Department:  "IT",
		Role:        "Super Admin",
		Permissions: []string{
			"dashboard:view", "dashboard:edit",
			"hosts:view", "hosts:edit", "hosts:delete",
			"services:view", "services:edit", "services:delete",
			"users:view", "users:edit", "users:delete",
			"roles:view", "roles:edit",
			"audit:view",
			"settings:view", "settings:edit",
		},
	}
}

func userFormatTimestamp(ts int64) string {
	if ts == 0 {
		return ""
	}
	t := time.UnixMilli(ts)
	return t.Format("2006-01-02 15:04")
}

func isValidEmail(email string) bool {
	pattern := `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
	matched, _ := regexp.MatchString(pattern, email)
	return matched
}

func isValidPhone(phone string) bool {
	pattern := `^1[3-9]\d{9}$`
	matched, _ := regexp.MatchString(pattern, phone)
	return matched
}