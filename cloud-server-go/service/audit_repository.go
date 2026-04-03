package service

import (
	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type AuditRepository struct {
	db *gorm.DB
}

func NewAuditRepository(db *gorm.DB) *AuditRepository {
	return &AuditRepository{db: db}
}

func (r *AuditRepository) Save(audit *models.ServiceOperationAudit) error {
	return r.db.Create(audit).Error
}

func (r *AuditRepository) FindByServiceName(serviceName string, limit int) ([]models.ServiceOperationAudit, error) {
	var audits []models.ServiceOperationAudit
	err := r.db.Where("service_name = ?", serviceName).
		Order("operation_time DESC").
		Limit(limit).
		Find(&audits).Error
	return audits, err
}

func (r *AuditRepository) FindAll(limit int) ([]models.ServiceOperationAudit, error) {
	var audits []models.ServiceOperationAudit
	err := r.db.Order("operation_time DESC").Limit(limit).Find(&audits).Error
	return audits, err
}

func (r *AuditRepository) FindTopByServiceName(serviceName string) ([]models.ServiceOperationAudit, error) {
	var audits []models.ServiceOperationAudit
	err := r.db.Where("service_name = ?", serviceName).
		Order("operation_time DESC").
		Limit(1).
		Find(&audits).Error
	return audits, err
}