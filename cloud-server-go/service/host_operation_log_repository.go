package service

import (
	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type HostOperationLogRepository struct {
	db *gorm.DB
}

func NewHostOperationLogRepository(db *gorm.DB) *HostOperationLogRepository {
	return &HostOperationLogRepository{db: db}
}

func (r *HostOperationLogRepository) Save(log *models.HostOperationLog) error {
	return r.db.Create(log).Error
}

func (r *HostOperationLogRepository) FindByHostId(hostId uint, limit int) ([]models.HostOperationLog, error) {
	var logs []models.HostOperationLog
	err := r.db.Where("host_id = ?", hostId).
		Order("operation_time DESC").
		Limit(limit).
		Find(&logs).Error
	return logs, err
}

func (r *HostOperationLogRepository) FindByHostName(hostName string, limit int) ([]models.HostOperationLog, error) {
	var logs []models.HostOperationLog
	err := r.db.Where("host_name = ?", hostName).
		Order("operation_time DESC").
		Limit(limit).
		Find(&logs).Error
	return logs, err
}

func (r *HostOperationLogRepository) FindAll(limit int) ([]models.HostOperationLog, error) {
	var logs []models.HostOperationLog
	err := r.db.Order("operation_time DESC").Limit(limit).Find(&logs).Error
	return logs, err
}