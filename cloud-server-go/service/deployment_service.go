package service

import (
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type DeploymentService struct {
	db *gorm.DB
}

func NewDeploymentService(db *gorm.DB) *DeploymentService {
	return &DeploymentService{db: db}
}

func (s *DeploymentService) VerifyRepository(repoID string) (*models.Repository, error) {
	repo, err := s.GetRepositoryByRepoID(repoID)
	if err != nil {
		return nil, err
	}

	var verifyStatus string
	var verifyMessage string

	if repo.RepoSource == "LOCAL" {
		if repo.LocalPath == "" {
			verifyStatus = "FAILED"
			verifyMessage = "本地仓库路径不能为空"
		} else {
			verifyStatus = "SUCCESS"
			verifyMessage = "本地仓库验证成功"
		}
	} else if repo.RepoSource == "HTTP" || repo.RepoSource == "REMOTE" {
		if repo.BaseURL == "" {
			verifyStatus = "FAILED"
			verifyMessage = "远程仓库URL不能为空"
		} else {
			verifyStatus = "SUCCESS"
			verifyMessage = "远程仓库连接成功"
		}
	} else {
		verifyStatus = "WARNING"
		verifyMessage = "未知的仓库类型"
	}

	repo.VerifyStatus = verifyStatus
	repo.VerifyMessage = verifyMessage
	repo.LastVerifyTime = time.Now().UnixMilli()

	s.db.Save(repo)
	return repo, nil
}

func (s *DeploymentService) SyncRepositoryPackages(repoID string) ([]models.StackPackage, error) {
	repo, err := s.GetRepositoryByRepoID(repoID)
	if err != nil {
		return nil, err
	}

	repo.LastSyncTime = time.Now().UnixMilli()
	s.db.Save(repo)

	var packages []models.StackPackage
	return packages, nil
}

func (s *DeploymentService) GetStackVersions() ([]models.StackVersion, error) {
	var versions []models.StackVersion
	err := s.db.Where("is_deleted = ?", false).Find(&versions).Error
	return versions, err
}

func (s *DeploymentService) GetStackVersionByID(id uint) (*models.StackVersion, error) {
	var version models.StackVersion
	err := s.db.First(&version, id).Error
	if err != nil {
		return nil, err
	}
	return &version, nil
}

func (s *DeploymentService) CreateStackVersion(sv *models.StackVersion) (*models.StackVersion, error) {
	sv.IsVisible = true
	sv.IsDeleted = false
	err := s.db.Create(sv).Error
	return sv, err
}

func (s *DeploymentService) GetPackagesByStackVersion(stackVersionID uint) ([]models.StackPackage, error) {
	var packages []models.StackPackage
	err := s.db.Where("stack_version_id = ? AND is_hidden = ?", stackVersionID, false).Find(&packages).Error
	return packages, err
}

func (s *DeploymentService) CreateStackPackage(sp *models.StackPackage) (*models.StackPackage, error) {
	err := s.db.Create(sp).Error
	return sp, err
}

func (s *DeploymentService) BatchCreateStackPackage(packages []models.StackPackage) error {
	if len(packages) == 0 {
		return nil
	}
	return s.db.CreateInBatches(packages, 100).Error
}

func (s *DeploymentService) GetRepositories() ([]models.Repository, error) {
	var repos []models.Repository
	err := s.db.Find(&repos).Error
	return repos, err
}

func (s *DeploymentService) GetRepositoryByRepoID(repoID string) (*models.Repository, error) {
	var repo models.Repository
	err := s.db.Where("repo_id = ?", repoID).First(&repo).Error
	if err != nil {
		return nil, err
	}
	return &repo, nil
}

func (s *DeploymentService) CreateRepository(repo *models.Repository) (*models.Repository, error) {
	err := s.db.Create(repo).Error
	return repo, err
}

func (s *DeploymentService) UpdateRepository(repo *models.Repository) error {
	return s.db.Save(repo).Error
}

func (s *DeploymentService) GetHostRegisters() ([]models.HostRegister, error) {
	var hosts []models.HostRegister
	err := s.db.Find(&hosts).Error
	return hosts, err
}

func (s *DeploymentService) GetHostRegisterByID(id uint) (*models.HostRegister, error) {
	var host models.HostRegister
	err := s.db.First(&host, id).Error
	if err != nil {
		return nil, err
	}
	return &host, nil
}

func (s *DeploymentService) CreateHostRegister(host *models.HostRegister) (*models.HostRegister, error) {
	host.Status = "PENDING"
	host.CreatedAt = time.Now()
	host.UpdatedAt = time.Now()
	err := s.db.Create(host).Error
	return host, err
}

func (s *DeploymentService) UpdateHostRegister(host *models.HostRegister) error {
	host.UpdatedAt = time.Now()
	return s.db.Save(host).Error
}

func (s *DeploymentService) DeleteHostRegister(id uint) error {
	return s.db.Delete(&models.HostRegister{}, id).Error
}

func (s *DeploymentService) BatchCreateHostRegister(hosts []models.HostRegister) error {
	if len(hosts) == 0 {
		return nil
	}
	now := time.Now()
	for i := range hosts {
		hosts[i].Status = "PENDING"
		hosts[i].CreatedAt = now
		hosts[i].UpdatedAt = now
	}
	return s.db.CreateInBatches(hosts, 100).Error
}

func (s *DeploymentService) CreateHostFromRegistration(host *models.Host) error {
	var existing models.Host
	err := s.db.Where("ipv4 = ? OR host_name = ?", host.IPv4, host.HostName).First(&existing).Error
	if err == nil {
		existing.CPUCount = host.CPUCount
		existing.TotalMem = host.TotalMem
		existing.TotalDisk = host.TotalDisk
		existing.OSType = host.OSType
		existing.OSArch = host.OSArch
		existing.OSInfo = host.OSInfo
		existing.AgentVersion = host.AgentVersion
		existing.AgentStatus = "ONLINE"
		existing.DiscoveryStatus = "ACTIVE"
		existing.LastRegistrationTime = host.LastRegistrationTime
		existing.LastHeartbeatTime = host.LastHeartbeatTime
		return s.db.Save(&existing).Error
	}
	return s.db.Create(host).Error
}

func (s *DeploymentService) GetDeployServices() ([]models.ServiceDeployInfo, error) {
	var results []models.ServiceDeployInfo

	var stackVersions []models.StackVersion
	err := s.db.Where("is_visible = ? AND is_deleted = ?", true, false).Find(&stackVersions).Error
	if err != nil {
		return nil, err
	}

	for _, sv := range stackVersions {
		var packages []models.StackPackage
		s.db.Where("stack_version_id = ? AND is_hidden = ?", sv.ID, false).Find(&packages)

		var services []models.DeployServiceInfo
		for _, pkg := range packages {
			services = append(services, models.DeployServiceInfo{
				ServiceName:   pkg.PackageName,
				DisplayName:   pkg.PackageName,
				Version:       pkg.PackageVersion,
				PackageName:   pkg.PackageName + "-" + pkg.PackageVersion,
				MD5:           pkg.MD5,
				PackageSize:    pkg.PackageSize,
				RepoURL:       pkg.RepoURL,
				Required:      parseRequired(pkg.RequiredBy),
				Optional:     parseRequired(pkg.Provides),
			})
		}

		results = append(results, models.ServiceDeployInfo{
			StackName:     sv.StackName,
			StackVersion:  sv.StackVersion,
			Services:      services,
		})
	}

	return results, nil
}

func parseRequired(deps string) []string {
	if deps == "" {
		return nil
	}
	var result []string
	for _, d := range splitComma(deps) {
		result = append(result, d)
	}
	return result
}

func splitComma(s string) []string {
	if s == "" {
		return nil
	}
	var result []string
	var current string
	for _, c := range s {
		if c == ',' {
			if current != "" {
				result = append(result, current)
			}
			current = ""
		} else {
			current += string(c)
		}
	}
	if current != "" {
		result = append(result, current)
	}
	return result
}