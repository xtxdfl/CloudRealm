package service

import (
	"encoding/json"
	"errors"
	"time"

	"github.com/cloudrealm/cloud-server-go/models"
	"gorm.io/gorm"
)

type DataMarketService struct {
	db *gorm.DB
}

func NewDataMarketService(db *gorm.DB) *DataMarketService {
	return &DataMarketService{db: db}
}

func (s *DataMarketService) GetAllCatalogs() ([]models.DataCatalogInfo, error) {
	var catalogs []models.DataCatalog
	s.db.Find(&catalogs)

	result := make([]models.DataCatalogInfo, 0, len(catalogs))
	for _, cat := range catalogs {
		var assetCount int64
		s.db.Model(&models.DataAssetCatalog{}).Where("catalog_id = ?", cat.CatalogID).Count(&assetCount)

		info := models.DataCatalogInfo{
			CatalogID:    cat.CatalogID,
			CatalogName:  cat.CatalogName,
			ParentID:     cat.ParentID,
			CatalogType:  cat.CatalogType,
			Description:  cat.Description,
			Owner:        cat.Owner,
			IsPublic:     cat.IsPublic,
			AssetCount:   int(assetCount),
		}
		result = append(result, info)
	}

	if len(result) == 0 {
		return s.getMockCatalogs(), nil
	}

	return result, nil
}

func (s *DataMarketService) GetCatalogById(catalogId uint) (*models.DataCatalogInfo, error) {
	var catalog models.DataCatalog
	if err := s.db.First(&catalog, catalogId).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, cat := range s.getMockCatalogs() {
				if cat.CatalogID == catalogId {
					return &cat, nil
				}
			}
		}
		return nil, err
	}

	var assetCount int64
	s.db.Model(&models.DataAssetCatalog{}).Where("catalog_id = ?", catalog.CatalogID).Count(&assetCount)

	return &models.DataCatalogInfo{
		CatalogID:    catalog.CatalogID,
		CatalogName:  catalog.CatalogName,
		ParentID:     catalog.ParentID,
		CatalogType:  catalog.CatalogType,
		Description:  catalog.Description,
		Owner:        catalog.Owner,
		IsPublic:     catalog.IsPublic,
		AssetCount:   int(assetCount),
	}, nil
}

func (s *DataMarketService) CreateCatalog(catalog *models.DataCatalog) (*models.DataCatalogInfo, error) {
	now := time.Now().UnixMilli()
	catalog.CreatedTime = now
	catalog.UpdatedTime = now
	if catalog.IsPublic {
		catalog.IsPublic = true
	}

	if err := s.db.Create(catalog).Error; err != nil {
		return nil, err
	}

	return &models.DataCatalogInfo{
		CatalogID:    catalog.CatalogID,
		CatalogName:  catalog.CatalogName,
		ParentID:     catalog.ParentID,
		CatalogType:  catalog.CatalogType,
		Description:  catalog.Description,
		Owner:        catalog.Owner,
		IsPublic:     catalog.IsPublic,
		AssetCount:   0,
	}, nil
}

func (s *DataMarketService) UpdateCatalog(catalogId uint, catalog *models.DataCatalog) (*models.DataCatalogInfo, error) {
	var existing models.DataCatalog
	if err := s.db.First(&existing, catalogId).Error; err != nil {
		return nil, errors.New("catalog not found")
	}

	catalog.CatalogID = catalogId
	catalog.UpdatedTime = time.Now().UnixMilli()
	s.db.Save(catalog)

	return &models.DataCatalogInfo{
		CatalogID:    catalog.CatalogID,
		CatalogName:  catalog.CatalogName,
		ParentID:     catalog.ParentID,
		CatalogType:  catalog.CatalogType,
		Description:  catalog.Description,
		Owner:        catalog.Owner,
		IsPublic:     catalog.IsPublic,
	}, nil
}

func (s *DataMarketService) DeleteCatalog(catalogId uint) (bool, error) {
	var existing models.DataCatalog
	if err := s.db.First(&existing, catalogId).Error; err != nil {
		return false, errors.New("catalog not found")
	}

	s.db.Where("catalog_id = ?", catalogId).Delete(&models.DataAssetCatalog{})
	s.db.Delete(&existing)

	return true, nil
}

func (s *DataMarketService) GetAllAssets() ([]models.DataAssetInfo, error) {
	var assets []models.DataAsset
	s.db.Find(&assets)

	result := make([]models.DataAssetInfo, 0, len(assets))
	for _, asset := range assets {
		info := s.assetToInfo(asset)
		result = append(result, info)
	}

	if len(result) == 0 {
		return s.getMockAssets(), nil
	}

	return result, nil
}

func (s *DataMarketService) GetAssetById(assetId uint) (*models.DataAssetInfo, error) {
	var asset models.DataAsset
	if err := s.db.First(&asset, assetId).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			for _, a := range s.getMockAssets() {
				if a.AssetID == assetId {
					return &a, nil
				}
			}
		}
		return nil, err
	}
	info := s.assetToInfo(asset)
	return &info, nil
}

func (s *DataMarketService) CreateAsset(asset *models.DataAsset) (*models.DataAssetInfo, error) {
	now := time.Now().UnixMilli()
	asset.CreatedTime = now
	asset.UpdatedTime = now

	if err := s.db.Create(asset).Error; err != nil {
		return nil, err
	}

	info := s.assetToInfo(*asset)
	return &info, nil
}

func (s *DataMarketService) UpdateAsset(assetId uint, asset *models.DataAsset) (*models.DataAssetInfo, error) {
	var existing models.DataAsset
	if err := s.db.First(&existing, assetId).Error; err != nil {
		return nil, errors.New("asset not found")
	}

	asset.AssetID = assetId
	asset.UpdatedTime = time.Now().UnixMilli()
	s.db.Save(asset)

	info := s.assetToInfo(*asset)
	return &info, nil
}

func (s *DataMarketService) DeleteAsset(assetId uint) (bool, error) {
	var existing models.DataAsset
	if err := s.db.First(&existing, assetId).Error; err != nil {
		return false, errors.New("asset not found")
	}

	s.db.Where("asset_id = ?", assetId).Delete(&models.DataAssetCatalog{})
	s.db.Where("source_asset_id = ? OR target_asset_id = ?", assetId, assetId).Delete(&models.DataLineage{})
	s.db.Delete(&existing)

	return true, nil
}

func (s *DataMarketService) AssignAssetToCatalog(assetId, catalogId uint) (bool, error) {
	var existing models.DataAssetCatalog
	err := s.db.Where("asset_id = ? AND catalog_id = ?", assetId, catalogId).First(&existing).Error
	if err == nil {
		return true, nil
	}

	mapping := models.DataAssetCatalog{
		AssetID:      assetId,
		CatalogID:    catalogId,
		AssignedTime: time.Now().UnixMilli(),
	}
	if err := s.db.Create(&mapping).Error; err != nil {
		return false, err
	}
	return true, nil
}

func (s *DataMarketService) RemoveAssetFromCatalog(assetId, catalogId uint) (bool, error) {
	s.db.Where("asset_id = ? AND catalog_id = ?", assetId, catalogId).Delete(&models.DataAssetCatalog{})
	return true, nil
}

func (s *DataMarketService) GetAssetsByCatalog(catalogId uint) ([]models.DataAssetInfo, error) {
	var mappings []models.DataAssetCatalog
	s.db.Where("catalog_id = ?", catalogId).Find(&mappings)

	assetIds := make([]uint, 0, len(mappings))
	for _, m := range mappings {
		assetIds = append(assetIds, m.AssetID)
	}

	if len(assetIds) == 0 {
		return s.getMockAssets(), nil
	}

	var assets []models.DataAsset
	s.db.Where("asset_id IN ?", assetIds).Find(&assets)

	result := make([]models.DataAssetInfo, 0, len(assets))
	for _, asset := range assets {
		info := s.assetToInfo(asset)
		result = append(result, info)
	}

	return result, nil
}

func (s *DataMarketService) GetLineage(assetId uint) (map[string]interface{}, error) {
	result := make(map[string]interface{})

	var upstream []models.DataLineage
	s.db.Where("target_asset_id = ?", assetId).Find(&upstream)

	var downstream []models.DataLineage
	s.db.Where("source_asset_id = ?", assetId).Find(&downstream)

	upstreamList := make([]models.LineageInfo, 0, len(upstream))
	for _, u := range upstream {
		var sourceName string
		var asset models.DataAsset
		if err := s.db.First(&asset, u.SourceAssetID).Error; err == nil {
			sourceName = asset.AssetName
		}
		upstreamList = append(upstreamList, models.LineageInfo{
			LineageID:           u.LineageID,
			SourceAssetID:       u.SourceAssetID,
			SourceAssetName:     sourceName,
			TargetAssetID:       u.TargetAssetID,
			LineageType:         u.LineageType,
			TransformExpression: u.TransformExpression,
			TransformType:       u.TransformType,
		})
	}

	downstreamList := make([]models.LineageInfo, 0, len(downstream))
	for _, d := range downstream {
		var targetName string
		var asset models.DataAsset
		if err := s.db.First(&asset, d.TargetAssetID).Error; err == nil {
			targetName = asset.AssetName
		}
		downstreamList = append(downstreamList, models.LineageInfo{
			LineageID:           d.LineageID,
			SourceAssetID:      d.SourceAssetID,
			TargetAssetID:      d.TargetAssetID,
			TargetAssetName:    targetName,
			LineageType:         d.LineageType,
			TransformExpression: d.TransformExpression,
			TransformType:       d.TransformType,
		})
	}

	result["upstream"] = upstreamList
	result["downstream"] = downstreamList
	result["upstreamCount"] = len(upstreamList)
	result["downstreamCount"] = len(downstreamList)

	return result, nil
}

func (s *DataMarketService) CreateLineage(lineage *models.DataLineage) (*models.LineageInfo, error) {
	lineage.CreatedTime = time.Now().UnixMilli()
	if lineage.IsActive {
		lineage.IsActive = true
	}

	if err := s.db.Create(lineage).Error; err != nil {
		return nil, err
	}

	var sourceName, targetName string
	var asset models.DataAsset
	if err := s.db.First(&asset, lineage.SourceAssetID).Error; err == nil {
		sourceName = asset.AssetName
	}
	if err := s.db.First(&asset, lineage.TargetAssetID).Error; err == nil {
		targetName = asset.AssetName
	}

	return &models.LineageInfo{
		LineageID:           lineage.LineageID,
		SourceAssetID:       lineage.SourceAssetID,
		SourceAssetName:     sourceName,
		TargetAssetID:       lineage.TargetAssetID,
		TargetAssetName:     targetName,
		LineageType:         lineage.LineageType,
		TransformExpression: lineage.TransformExpression,
		TransformType:       lineage.TransformType,
	}, nil
}

func (s *DataMarketService) DeleteLineage(lineageId uint) (bool, error) {
	var lineage models.DataLineage
	if err := s.db.First(&lineage, lineageId).Error; err != nil {
		return false, errors.New("lineage not found")
	}
	s.db.Delete(&lineage)
	return true, nil
}

func (s *DataMarketService) GetAssetStats() (map[string]interface{}, error) {
	var totalAssets int64
	var totalCatalogs int64
	var totalLineages int64

	s.db.Model(&models.DataAsset{}).Count(&totalAssets)
	s.db.Model(&models.DataCatalog{}).Count(&totalCatalogs)
	s.db.Model(&models.DataLineage{}).Count(&totalLineages)

	result := make(map[string]interface{})
	result["totalAssets"] = totalAssets
	result["totalCatalogs"] = totalCatalogs
	result["totalLineages"] = totalLineages

	if totalAssets == 0 {
		mockAssets := s.getMockAssets()
		result["totalAssets"] = len(mockAssets)
		result["assetTypes"] = map[string]int{
			"HIVE":   3,
			"KAFKA":  2,
			"HBASE":  1,
			"FLATFILE": 2,
		}
	} else {
		var typeCounts map[string]int
		result["assetTypes"] = typeCounts
	}

	return result, nil
}

func (s *DataMarketService) assetToInfo(asset models.DataAsset) models.DataAssetInfo {
	var tags []string
	json.Unmarshal([]byte(asset.Tags), &tags)

	var catalogs []string
	var mappings []models.DataAssetCatalog
	s.db.Where("asset_id = ?", asset.AssetID).Find(&mappings)
	for _, m := range mappings {
		var cat models.DataCatalog
		if err := s.db.First(&cat, m.CatalogID).Error; err == nil {
			catalogs = append(catalogs, cat.CatalogName)
		}
	}

	var upstream, downstream []models.DataLineage
	s.db.Where("target_asset_id = ?", asset.AssetID).Find(&upstream)
	s.db.Where("source_asset_id = ?", asset.AssetID).Find(&downstream)

	upstreamAssets := make([]string, 0, len(upstream))
	for _, u := range upstream {
		var a models.DataAsset
		if err := s.db.First(&a, u.SourceAssetID).Error; err == nil {
			upstreamAssets = append(upstreamAssets, a.AssetName)
		}
	}

	downstreamAssets := make([]string, 0, len(downstream))
	for _, d := range downstream {
		var a models.DataAsset
		if err := s.db.First(&a, d.TargetAssetID).Error; err == nil {
			downstreamAssets = append(downstreamAssets, a.AssetName)
		}
	}

	return models.DataAssetInfo{
		AssetID:          asset.AssetID,
		AssetName:        asset.AssetName,
		AssetType:        asset.AssetType,
		DatabaseName:     asset.DatabaseName,
		TableName_:       asset.TableName_,
		StoragePath:      asset.StoragePath,
		Owner:            asset.Owner,
		Description:      asset.Description,
		Tags:             tags,
		IsPartitioned:   asset.IsPartitioned,
		RecordCount:      asset.RecordCount,
		SizeBytes:        asset.SizeBytes,
		QualityScore:     asset.QualityScore,
		LastAccessTime:   asset.LastAccessTime,
		CreatedTime:      asset.CreatedTime,
		Catalogs:         catalogs,
		UpstreamAssets:   upstreamAssets,
		DownstreamAssets: downstreamAssets,
	}
}

func (s *DataMarketService) getMockCatalogs() []models.DataCatalogInfo {
	return []models.DataCatalogInfo{
		{CatalogID: 1, CatalogName: "ODS层", CatalogType: "ODS", Description: "原始数据层", Owner: "admin", IsPublic: true, AssetCount: 5},
		{CatalogID: 2, CatalogName: "DWD层", CatalogType: "DWD", Description: "明细数据层", Owner: "admin", IsPublic: true, AssetCount: 8},
		{CatalogID: 3, CatalogName: "DWS层", CatalogType: "DWS", Description: "汇总数据层", Owner: "admin", IsPublic: true, AssetCount: 4},
		{CatalogID: 4, CatalogName: "ADS层", CatalogType: "ADS", Description: "应用数据层", Owner: "admin", IsPublic: true, AssetCount: 3},
	}
}

func (s *DataMarketService) getMockAssets() []models.DataAssetInfo {
	return []models.DataAssetInfo{
		{AssetID: 1, AssetName: "user_behavior_log", AssetType: "HIVE", DatabaseName: "ods", TableName_: "user_behavior_log", Owner: "admin", Description: "用户行为日志", RecordCount: 1000000, SizeBytes: 5368709120, QualityScore: 95.5},
		{AssetID: 2, AssetName: "order_detail", AssetType: "HIVE", DatabaseName: "dwd", TableName_: "order_detail", Owner: "admin", Description: "订单明细表", RecordCount: 500000, SizeBytes: 2147483648, QualityScore: 98.2},
		{AssetID: 3, AssetName: "user_dimension", AssetType: "HIVE", DatabaseName: "dws", TableName_: "user_dimension", Owner: "admin", Description: "用户维度表", RecordCount: 100000, SizeBytes: 1073741824, QualityScore: 99.0},
		{AssetID: 4, AssetName: "sales_report", AssetType: "KAFKA", DatabaseName: "ads", TableName_: "sales_report", Owner: "admin", Description: "销售报表主题", RecordCount: 0, SizeBytes: 0, QualityScore: 92.0},
		{AssetID: 5, AssetName: "product_catalog", AssetType: "HBASE", DatabaseName: "dwd", TableName_: "product_catalog", Owner: "admin", Description: "商品目录", RecordCount: 10000, SizeBytes: 104857600, QualityScore: 96.5},
	}
}