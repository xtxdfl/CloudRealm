package models

import (
	"time"
)

type User struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	UserID         int       `gorm:"column:user_id;uniqueIndex" json:"userId"`
	PrincipalID    *uint     `gorm:"column:principal_id" json:"principalId"`
	UserName       string    `gorm:"column:user_name;uniqueIndex" json:"userName"`
	Active         int       `gorm:"column:active;default:1" json:"active"`
	DisplayName    string    `gorm:"column:display_name" json:"displayName"`
	LocalUsername  string    `gorm:"column:local_username" json:"localUsername"`
	CreateTime     int64     `gorm:"column:create_time" json:"createTime"`
	Version        *int64    `gorm:"column:version" json:"version"`
	Email          string    `gorm:"column:email" json:"email"`
	Phone          string    `gorm:"column:phone" json:"phone"`
	Department     string    `gorm:"column:department" json:"department"`
	Password       string    `gorm:"column:password" json:"password"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (User) TableName() string {
	return "users"
}

type UserInfo struct {
	UserID      int      `json:"userId"`
	UserName    string   `json:"userName"`
	DisplayName string   `json:"displayName"`
	Email       string   `json:"email"`
	Phone       string   `json:"phone"`
	Department  string   `json:"department"`
	Active      int      `json:"active"`
	Roles       []string `json:"roles"`
	CreateTime  int64    `json:"createTime"`
}

type Role struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	AuthorizationID  int       `gorm:"column:authorization_id;uniqueIndex" json:"authorizationId"`
	AuthorizationName string   `gorm:"column:authorization_name" json:"authorizationName"`
	Description      string    `gorm:"column:description" json:"description"`
	RoleType         string    `gorm:"column:role_type" json:"roleType"`
	CreateTime       int64     `gorm:"column:create_time" json:"createTime"`
	UpdateTime       int64     `gorm:"column:update_time" json:"updateTime"`
	IsSystem         int       `gorm:"column:is_system;default:0" json:"isSystem"`
	Scope            string    `gorm:"column:scope;default:'GLOBAL'" json:"scope"`
	CreatedAt        time.Time `json:"createdAt"`
	UpdatedAt        time.Time `json:"updatedAt"`
}

func (Role) TableName() string {
	return "roleauthorization"
}

type RoleInfo struct {
	AuthorizationID   int      `json:"authorizationId"`
	AuthorizationName string   `json:"authorizationName"`
	Description       string   `json:"description"`
	RoleType          string   `json:"roleType"`
	IsSystem          int      `json:"isSystem"`
	Scope             string   `json:"scope"`
	Permissions       []string `json:"permissions"`
	UserCount         int      `json:"userCount"`
}

type Permission struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	PermissionID    uint      `gorm:"column:permission_id;uniqueIndex" json:"permissionId"`
	PermissionName  string    `gorm:"column:permission_name" json:"permissionName"`
	ResourceTypeID  *int      `gorm:"column:resource_type_id" json:"resourceTypeId"`
	PermissionLabel string    `gorm:"column:permission_label" json:"permissionLabel"`
	PrincipalID     *uint     `gorm:"column:principal_id" json:"principalId"`
	SortOrder       int       `gorm:"column:sort_order;default:0" json:"sortOrder"`
	CreatedAt       time.Time `json:"createdAt"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

func (Permission) TableName() string {
	return "adminpermission"
}

type UserRole struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	UserID         int       `gorm:"column:user_id;not null;index" json:"userId"`
	AuthorizationID int      `gorm:"column:authorization_id;not null;index" json:"authorizationId"`
	TenantID       *int      `gorm:"column:tenant_id" json:"tenantId"`
	CreateTime     int64     `gorm:"column:create_time" json:"createTime"`
	Creator        string    `gorm:"column:creator" json:"creator"`
	ExpiryTime     *int64    `gorm:"column:expiry_time" json:"expiryTime"`
	IsActive       int       `gorm:"column:is_active;default:1" json:"isActive"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (UserRole) TableName() string {
	return "user_role"
}

type UserAuthentication struct {
	ID                  uint      `gorm:"primaryKey" json:"id"`
	UserAuthenticationID int      `gorm:"column:user_authentication_id;uniqueIndex" json:"userAuthenticationId"`
	UserID              *int      `gorm:"column:user_id;index" json:"userId"`
	AuthenticationType  string    `gorm:"column:authentication_type" json:"authenticationType"`
	AuthenticationKey    string    `gorm:"column:authentication_key" json:"authenticationKey"`
	CreateTime          int64     `gorm:"column:create_time" json:"createTime"`
	UpdateTime          int64     `gorm:"column:update_time" json:"updateTime"`
	CreatedAt           time.Time `json:"createdAt"`
	UpdatedAt           time.Time `json:"updatedAt"`
}

func (UserAuthentication) TableName() string {
	return "user_authentication"
}

type Tenant struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	TenantID    int       `gorm:"column:tenant_id;uniqueIndex" json:"tenantId"`
	TenantName  string    `gorm:"column:tenant_name" json:"tenantName"`
	Description string    `gorm:"column:description" json:"description"`
	Status      int       `gorm:"column:status;default:1" json:"status"`
	CreateTime  int64     `gorm:"column:create_time" json:"createTime"`
	ExpireTime  *int64    `gorm:"column:expire_time" json:"expireTime"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (Tenant) TableName() string {
	return "tenants"
}

type RolePermission struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	RoleID         int       `gorm:"column:role_id;not null;index" json:"roleId"`
	PermissionID   uint      `gorm:"column:permission_id;not null;index" json:"permissionId"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (RolePermission) TableName() string {
	return "role_permission"
}

type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

type LoginResponse struct {
	Token     string      `json:"token"`
	UserInfo  *UserInfo   `json:"userInfo"`
	ExpiresIn int64       `json:"expiresIn"`
}

type ChangePasswordRequest struct {
	OldPassword string `json:"oldPassword" binding:"required"`
	NewPassword string `json:"newPassword" binding:"required"`
}

type AdminPrincipal struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	PrincipalID     uint      `gorm:"column:principal_id;uniqueIndex" json:"principalId"`
	PrincipalTypeID *int      `gorm:"column:principal_type_id" json:"principalTypeId"`
	CreatedAt      time.Time `json:"createdAt"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

func (AdminPrincipal) TableName() string {
	return "adminprincipal"
}

type AdminPrincipalType struct {
	ID             uint      `gorm:"primaryKey" json:"id"`
	PrincipalTypeID int       `gorm:"column:principal_type_id;uniqueIndex" json:"principalTypeId"`
	TypeName       string    `gorm:"column:type_name" json:"typeName"`
	Description   string    `gorm:"column:description" json:"description"`
	CreateTime    int64     `gorm:"column:create_time" json:"createTime"`
	CreatedAt     time.Time `json:"createdAt"`
	UpdatedAt     time.Time `json:"updatedAt"`
}

func (AdminPrincipalType) TableName() string {
	return "admin_principal_type"
}