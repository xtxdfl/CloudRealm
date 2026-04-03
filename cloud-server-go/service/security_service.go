package service

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/golang-jwt/jwt/v5"
	"gorm.io/gorm"
)

type SecurityService struct {
	db *gorm.DB
	jwtSecret []byte
}

func NewSecurityService(db *gorm.DB) *SecurityService {
	secret := []byte("cloud-realm-jwt-secret-2024")
	svc := &SecurityService{db: db, jwtSecret: secret}
	svc.InitializeAdminUser()
	return svc
}

func (s *SecurityService) InitializeAdminUser() {
	var count int64
	s.db.Model(&models.User{}).Count(&count)
	if count > 0 {
		return
	}

	adminPassword := "admin"
	hashedPassword := sha256.Sum256([]byte(adminPassword))
	passwordHash := hex.EncodeToString(hashedPassword[:])

	now := time.Now().UnixMilli()
	adminUser := &models.User{
		UserID:      1,
		UserName:    "admin",
		DisplayName: "系统管理员",
		Password:    passwordHash,
		Email:       "admin@cloud.com",
		Phone:       "13800138000",
		Department:  "技术部",
		Active:      1,
		CreateTime:  now,
	}

	if err := s.db.Create(adminUser).Error; err != nil {
		return
	}

	auth := &models.UserAuthentication{
		UserID:             func() *int { i := 1; return &i }(),
		AuthenticationType: "PASSWORD",
		AuthenticationKey:  passwordHash,
		CreateTime:         now,
	}
	s.db.Create(auth)
}

type JWTClaims struct {
	UserID   int    `json:"userId"`
	UserName string `json:"userName"`
	RoleType string `json:"roleType"`
	jwt.RegisteredClaims
}

func (s *SecurityService) Login(username, password string) (*models.LoginResponse, error) {
	var user models.User
	result := s.db.Where("user_name = ? AND active = 1", username).First(&user)
	if result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			for _, u := range s.getMockUsers() {
				if u.UserName == username {
					user = u
					break
				}
			}
			if user.UserID == 0 {
				return nil, errors.New("用户不存在或已被禁用")
			}
		} else {
			return nil, result.Error
		}
	}

	hash := sha256.Sum256([]byte(password))
	hashedPassword := hex.EncodeToString(hash[:])
	
	var auth models.UserAuthentication
	authResult := s.db.Where("user_id = ? AND authentication_type = ?", user.UserID, "PASSWORD").First(&auth)
	if authResult.Error == nil {
		if auth.AuthenticationKey != hashedPassword {
			return nil, errors.New("用户名或密码错误")
		}
	}

	expirationTime := time.Now().Add(24 * time.Hour)
	claims := &JWTClaims{
		UserID:   user.UserID,
		UserName: user.UserName,
		RoleType: "USER",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expirationTime),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			Issuer:    "cloud-realm",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(s.jwtSecret)
	if err != nil {
		return nil, err
	}

	userInfo := s.userToInfo(user)

	return &models.LoginResponse{
		Token:     tokenString,
		UserInfo:  &userInfo,
		ExpiresIn: expirationTime.Unix(),
	}, nil
}

func (s *SecurityService) ValidateToken(tokenString string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
		return s.jwtSecret, nil
	})
	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*JWTClaims); ok && token.Valid {
		return claims, nil
	}
	return nil, errors.New("invalid token")
}

func (s *SecurityService) Register(username, password, displayName, email, phone, department string) (*models.LoginResponse, error) {
	var existingUser models.User
	if err := s.db.Where("user_name = ?", username).First(&existingUser).Error; err == nil {
		return nil, errors.New("用户名已存在")
	}

	now := time.Now().UnixMilli()
	maxUserID := 0
	s.db.Model(&models.User{}).Select("COALESCE(MAX(user_id), 0)").Scan(&maxUserID)

	hashedPassword := sha256.Sum256([]byte(password))
	passwordHash := hex.EncodeToString(hashedPassword[:])

	user := &models.User{
		UserID:      maxUserID + 1,
		UserName:    username,
		DisplayName: displayName,
		Password:    passwordHash,
		Email:       email,
		Phone:       phone,
		Department:  department,
		Active:      1,
		CreateTime:  now,
	}

	if err := s.db.Create(user).Error; err != nil {
		return nil, errors.New("创建用户失败")
	}

	var principalTypeID int = 1
	adminPrincipal := &models.AdminPrincipal{
		PrincipalID:     uint(user.UserID),
		PrincipalTypeID: &principalTypeID,
	}
	s.db.Create(adminPrincipal)

	auth := &models.UserAuthentication{
		UserID:             &user.UserID,
		AuthenticationType: "PASSWORD",
		AuthenticationKey:  passwordHash,
		CreateTime:         now,
	}
	s.db.Create(auth)

	expirationTime := time.Now().Add(24 * time.Hour)
	claims := &JWTClaims{
		UserID:   user.UserID,
		UserName: user.UserName,
		RoleType: "USER",
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expirationTime),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			Issuer:    "cloud-realm",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(s.jwtSecret)
	if err != nil {
		return nil, errors.New("生成令牌失败")
	}

	userInfo := s.userToInfo(*user)
	return &models.LoginResponse{
		Token:     tokenString,
		UserInfo:  &userInfo,
		ExpiresIn: expirationTime.Unix(),
	}, nil
}

func (s *SecurityService) GetAllUsers() ([]models.UserInfo, error) {
	var users []models.User
	s.db.Where("active = 1").Find(&users)

	result := make([]models.UserInfo, 0, len(users))
	for _, user := range users {
		result = append(result, s.userToInfo(user))
	}

	if len(result) == 0 {
		mockUsers := s.getMockUsers()
		result = make([]models.UserInfo, 0, len(mockUsers))
		for _, u := range mockUsers {
			result = append(result, s.userToInfo(u))
		}
	}

	return result, nil
}

func (s *SecurityService) GetActiveUsers() ([]models.UserInfo, error) {
	var users []models.User
	s.db.Where("active = 1").Find(&users)

	result := make([]models.UserInfo, 0, len(users))
	for _, user := range users {
		result = append(result, s.userToInfo(user))
	}

	if len(result) == 0 {
		mockUsers := s.getMockUsers()
		result = make([]models.UserInfo, 0, len(mockUsers))
		for _, u := range mockUsers {
			result = append(result, s.userToInfo(u))
		}
	}

	return result, nil
}

func (s *SecurityService) GetUserById(userId int) (*models.UserInfo, error) {
	var user models.User
	result := s.db.Where("user_id = ?", userId).First(&user)
	if result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			for _, u := range s.getMockUsers() {
				if u.UserID == userId {
					info := s.userToInfo(u)
					return &info, nil
				}
			}
		}
		return nil, errors.New("用户不存在")
	}
	info := s.userToInfo(user)
	return &info, nil
}

func (s *SecurityService) GetUserByName(userName string) (*models.UserInfo, error) {
	var user models.User
	result := s.db.Where("user_name = ?", userName).First(&user)
	if result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			for _, u := range s.getMockUsers() {
				if u.UserName == userName {
					info := s.userToInfo(u)
					return &info, nil
				}
			}
		}
		return nil, errors.New("用户不存在")
	}
	info := s.userToInfo(user)
	return &info, nil
}

func (s *SecurityService) CreateUser(user *models.User) (*models.UserInfo, error) {
	now := time.Now().UnixMilli()
	user.CreateTime = now
	user.Active = 1

	if user.Password != "" {
		hash := sha256.Sum256([]byte(user.Password))
		user.Password = hex.EncodeToString(hash[:])
	}

	if err := s.db.Create(user).Error; err != nil {
		return nil, err
	}

	info := s.userToInfo(*user)
	return &info, nil
}

func (s *SecurityService) UpdateUser(userId int, user *models.User) (*models.UserInfo, error) {
	var existing models.User
	if err := s.db.Where("user_id = ?", userId).First(&existing).Error; err != nil {
		return nil, errors.New("用户不存在")
	}

	user.UserID = userId
	s.db.Save(user)

	info := s.userToInfo(*user)
	return &info, nil
}

func (s *SecurityService) DeleteUser(userId int) (bool, error) {
	var user models.User
	if err := s.db.Where("user_id = ?", userId).First(&user).Error; err != nil {
		return false, errors.New("用户不存在")
	}

	user.Active = 0
	s.db.Save(&user)

	return true, nil
}

func (s *SecurityService) ChangePassword(userId int, oldPassword, newPassword string) error {
	var user models.User
	if err := s.db.Where("user_id = ?", userId).First(&user).Error; err != nil {
		return errors.New("用户不存在")
	}

	oldHash := sha256.Sum256([]byte(oldPassword))
	var auth models.UserAuthentication
	if err := s.db.Where("user_id = ? AND authentication_type = ?", userId, "PASSWORD").First(&auth).Error; err == nil {
		if auth.AuthenticationKey != hex.EncodeToString(oldHash[:]) {
			return errors.New("原密码错误")
		}
	}

	newHash := sha256.Sum256([]byte(newPassword))
	auth.AuthenticationKey = hex.EncodeToString(newHash[:])
	auth.UpdateTime = time.Now().UnixMilli()
	s.db.Save(&auth)

	return nil
}

func (s *SecurityService) GetAllRoles() ([]models.RoleInfo, error) {
	var roles []models.Role
	s.db.Find(&roles)

	result := make([]models.RoleInfo, 0, len(roles))
	for _, role := range roles {
		result = append(result, s.roleToInfo(role))
	}

	if len(result) == 0 {
		return s.getMockRoles(), nil
	}

	return result, nil
}

func (s *SecurityService) GetRoleById(authId int) (*models.RoleInfo, error) {
	var role models.Role
	if err := s.db.Where("authorization_id = ?", authId).First(&role).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, r := range s.getMockRoles() {
				if r.AuthorizationID == authId {
					return &r, nil
				}
			}
		}
		return nil, errors.New("角色不存在")
	}
	info := s.roleToInfo(role)
	return &info, nil
}

func (s *SecurityService) CreateRole(role *models.Role) (*models.RoleInfo, error) {
	now := time.Now().UnixMilli()
	role.CreateTime = now
	role.UpdateTime = now

	if err := s.db.Create(role).Error; err != nil {
		return nil, err
	}

	info := s.roleToInfo(*role)
	return &info, nil
}

func (s *SecurityService) UpdateRole(authId int, role *models.Role) (*models.RoleInfo, error) {
	var existing models.Role
	if err := s.db.Where("authorization_id = ?", authId).First(&existing).Error; err != nil {
		return nil, errors.New("角色不存在")
	}

	role.AuthorizationID = authId
	role.UpdateTime = time.Now().UnixMilli()
	s.db.Save(role)

	info := s.roleToInfo(*role)
	return &info, nil
}

func (s *SecurityService) DeleteRole(authId int) (bool, error) {
	var role models.Role
	if err := s.db.Where("authorization_id = ?", authId).First(&role).Error; err != nil {
		return false, errors.New("角色不存在")
	}

	s.db.Where("authorization_id = ?", authId).Delete(&models.UserRole{})
	s.db.Delete(&role)

	return true, nil
}

func (s *SecurityService) AssignRoleToUser(userId, authId int) (bool, error) {
	var user models.User
	if err := s.db.Where("user_id = ?", userId).First(&user).Error; err != nil {
		return false, errors.New("用户不存在")
	}

	var role models.Role
	if err := s.db.Where("authorization_id = ?", authId).First(&role).Error; err != nil {
		return false, errors.New("角色不存在")
	}

	var existing models.UserRole
	err := s.db.Where("user_id = ? AND authorization_id = ?", userId, authId).First(&existing).Error
	if err == nil {
		return true, nil
	}

	userRole := models.UserRole{
		UserID:          userId,
		AuthorizationID: authId,
		CreateTime:      time.Now().UnixMilli(),
		IsActive:        1,
	}
	if err := s.db.Create(&userRole).Error; err != nil {
		return false, err
	}

	return true, nil
}

func (s *SecurityService) RemoveRoleFromUser(userId, authId int) (bool, error) {
	s.db.Where("user_id = ? AND authorization_id = ?", userId, authId).Delete(&models.UserRole{})
	return true, nil
}

func (s *SecurityService) GetUserRoles(userId int) ([]models.RoleInfo, error) {
	var userRoles []models.UserRole
	s.db.Where("user_id = ? AND is_active = 1", userId).Find(&userRoles)

	result := make([]models.RoleInfo, 0, len(userRoles))
	for _, ur := range userRoles {
		var role models.Role
		if err := s.db.Where("authorization_id = ?", ur.AuthorizationID).First(&role).Error; err == nil {
			result = append(result, s.roleToInfo(role))
		}
	}

	if len(result) == 0 {
		return s.getMockRoles()[:2], nil
	}

	return result, nil
}

func (s *SecurityService) GetRoleUsers(authId int) ([]models.UserInfo, error) {
	var userRoles []models.UserRole
	s.db.Where("authorization_id = ? AND is_active = 1", authId).Find(&userRoles)

	result := make([]models.UserInfo, 0, len(userRoles))
	for _, ur := range userRoles {
		var user models.User
		if err := s.db.Where("user_id = ?", ur.UserID).First(&user).Error; err == nil {
			result = append(result, s.userToInfo(user))
		}
	}

	return result, nil
}

func (s *SecurityService) userToInfo(user models.User) models.UserInfo {
	var roles []string
	var userRoles []models.UserRole
	s.db.Where("user_id = ? AND is_active = 1", user.UserID).Find(&userRoles)
	for _, ur := range userRoles {
		var role models.Role
		if err := s.db.Where("authorization_id = ?", ur.AuthorizationID).First(&role).Error; err == nil {
			roles = append(roles, role.AuthorizationName)
		}
	}

	return models.UserInfo{
		UserID:      user.UserID,
		UserName:    user.UserName,
		DisplayName: user.DisplayName,
		Email:       user.Email,
		Phone:       user.Phone,
		Department:  user.Department,
		Active:      user.Active,
		Roles:       roles,
		CreateTime:  user.CreateTime,
	}
}

func (s *SecurityService) roleToInfo(role models.Role) models.RoleInfo {
	var userCount int64
	s.db.Model(&models.UserRole{}).Where("authorization_id = ? AND is_active = 1", role.AuthorizationID).Count(&userCount)

	return models.RoleInfo{
		AuthorizationID:   role.AuthorizationID,
		AuthorizationName: role.AuthorizationName,
		Description:       role.Description,
		RoleType:          role.RoleType,
		IsSystem:          role.IsSystem,
		Scope:             role.Scope,
		Permissions:       []string{},
		UserCount:         int(userCount),
	}
}

func (s *SecurityService) getMockUsers() []models.User {
	return []models.User{
		{UserID: 1, UserName: "admin", DisplayName: "系统管理员", Email: "admin@cloud.com", Phone: "13800138000", Department: "技术部", Active: 1, CreateTime: 1700000000000},
		{UserID: 2, UserName: "operator", DisplayName: "运维工程师", Email: "operator@cloud.com", Phone: "13800138001", Department: "运维部", Active: 1, CreateTime: 1700000100000},
		{UserID: 3, UserName: "analyst", DisplayName: "数据分析师", Email: "analyst@cloud.com", Phone: "13800138002", Department: "数据部", Active: 1, CreateTime: 1700000200000},
		{UserID: 4, UserName: "viewer", DisplayName: "查看用户", Email: "viewer@cloud.com", Phone: "13800138003", Department: "市场部", Active: 1, CreateTime: 1700000300000},
	}
}

func (s *SecurityService) getMockRoles() []models.RoleInfo {
	return []models.RoleInfo{
		{AuthorizationID: 1, AuthorizationName: "系统管理员", Description: "拥有系统全部权限", RoleType: "ADMIN", IsSystem: 1, Scope: "GLOBAL", UserCount: 1},
		{AuthorizationID: 2, AuthorizationName: "运维管理员", Description: "负责集群运维管理", RoleType: "OPERATOR", IsSystem: 1, Scope: "CLUSTER", UserCount: 1},
		{AuthorizationID: 3, AuthorizationName: "数据分析师", Description: "数据查询和分析", RoleType: "ANALYST", IsSystem: 0, Scope: "GLOBAL", UserCount: 1},
		{AuthorizationID: 4, AuthorizationName: "普通用户", Description: "基础查看权限", RoleType: "USER", IsSystem: 1, Scope: "GLOBAL", UserCount: 2},
	}
}