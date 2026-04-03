package models

import (
	"time"
)

type DataCatalog struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	CatalogID   uint      `gorm:"column:catalog_id;uniqueIndex" json:"catalogId"`
	CatalogName string    `gorm:"column:catalog_name;not null;uniqueIndex" json:"catalogName"`
	ParentID    *uint     `gorm:"column:parent_id" json:"parentId"`
	CatalogType string    `gorm:"column:catalog_type" json:"catalogType"`
	Description string    `gorm:"column:description" json:"description"`
	Owner       string    `gorm:"column:owner" json:"owner"`
	IsPublic    bool      `gorm:"column:is_public;default:true" json:"isPublic"`
	SortOrder   int       `gorm:"column:sort_order;default:0" json:"sortOrder"`
	CreatedTime int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime int64     `gorm:"column:updated_time" json:"updatedTime"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (DataCatalog) TableName() string {
	return "data_catalogs"
}

type DataAsset struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	AssetID          uint      `gorm:"column:asset_id;uniqueIndex" json:"assetId"`
	AssetName        string    `gorm:"column:asset_name;not null" json:"assetName"`
	AssetType        string    `gorm:"column:asset_type;not null" json:"assetType"`
	DatabaseName     string    `gorm:"column:database_name" json:"databaseName"`
	SchemaName       string    `gorm:"column:schema_name" json:"schemaName"`
	TableName_       string    `gorm:"column:table_name;default:''" json:"tableName"`
	ColumnName       string    `gorm:"column:column_name" json:"columnName"`
	DataFormat       string    `gorm:"column:data_format" json:"dataFormat"`
	StoragePath      string    `gorm:"column:storage_path" json:"storagePath"`
	Owner            string    `gorm:"column:owner" json:"owner"`
	Description      string    `gorm:"column:description;type:text" json:"description"`
	Tags             string    `gorm:"column:tags" json:"tags"`
	IsPartitioned   bool      `gorm:"column:is_partitioned;default:false" json:"isPartitioned"`
	PartitionColumns string   `gorm:"column:partition_columns" json:"partitionColumns"`
	RecordCount      int64     `gorm:"column:record_count;default:0" json:"recordCount"`
	SizeBytes        int64     `gorm:"column:size_bytes;default:0" json:"sizeBytes"`
	Location         string    `gorm:"column:location" json:"location"`
	Engine           string    `gorm:"column:engine" json:"engine"`
	CreatedTime      int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime      int64     `gorm:"column:updated_time" json:"updatedTime"`
	LastAccessTime   *int64    `gorm:"column:last_access_time" json:"lastAccessTime"`
	QualityScore     float64   `gorm:"column:quality_score;default:0" json:"qualityScore"`
	CreatedAt        time.Time `json:"createdAt"`
	UpdatedAt        time.Time `json:"updatedAt"`
}

func (DataAsset) TableName() string {
	return "data_assets"
}

type DataLineage struct {
	ID                  uint      `gorm:"primaryKey" json:"id"`
	LineageID           uint      `gorm:"column:lineage_id;uniqueIndex" json:"lineageId"`
	SourceAssetID       uint      `gorm:"column:source_asset_id;not null;index" json:"sourceAssetId"`
	TargetAssetID       uint      `gorm:"column:target_asset_id;not null;index" json:"targetAssetId"`
	LineageType         string    `gorm:"column:lineage_type;not null" json:"lineageType"`
	TransformExpression string   `gorm:"column:transform_expression;type:text" json:"transformExpression"`
	TransformType       string    `gorm:"column:transform_type" json:"transformType"`
	IsActive            bool      `gorm:"column:is_active;default:true" json:"isActive"`
	CreatedTime         int64     `gorm:"column:created_time" json:"createdTime"`
	CreatedAt           time.Time `json:"createdAt"`
	UpdatedAt           time.Time `json:"updatedAt"`
}

func (DataLineage) TableName() string {
	return "data_lineage"
}

type DataAssetCatalog struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	AssetID      uint      `gorm:"column:asset_id;not null;index" json:"assetId"`
	CatalogID    uint      `gorm:"column:catalog_id;not null;index" json:"catalogId"`
	AssignedTime int64     `gorm:"column:assigned_time" json:"assignedTime"`
	CreatedAt    time.Time `json:"createdAt"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

func (DataAssetCatalog) TableName() string {
	return "data_asset_catalog"
}

type DataAssetInfo struct {
	AssetID          uint     `json:"assetId"`
	AssetName        string   `json:"assetName"`
	AssetType        string   `json:"assetType"`
	DatabaseName     string   `json:"databaseName"`
	TableName_       string   `json:"tableName"`
	StoragePath      string   `json:"storagePath"`
	Owner            string   `json:"owner"`
	Description      string   `json:"description"`
	Tags             []string `json:"tags"`
	IsPartitioned   bool     `json:"isPartitioned"`
	RecordCount      int64    `json:"recordCount"`
	SizeBytes        int64    `json:"sizeBytes"`
	QualityScore     float64  `json:"qualityScore"`
	LastAccessTime   *int64   `json:"lastAccessTime,omitempty"`
	CreatedTime      int64    `json:"createdTime"`
	Catalogs         []string `json:"catalogs"`
	UpstreamAssets   []string `json:"upstreamAssets"`
	DownstreamAssets []string `json:"downstreamAssets"`
}

type DataCatalogInfo struct {
	CatalogID    uint             `json:"catalogId"`
	CatalogName string           `json:"catalogName"`
	ParentID    *uint            `json:"parentId,omitempty"`
	CatalogType string           `json:"catalogType"`
	Description string           `json:"description"`
	Owner       string           `json:"owner"`
	IsPublic    bool             `json:"isPublic"`
	AssetCount  int              `json:"assetCount"`
	Children    []DataCatalogInfo `json:"children,omitempty"`
}

type LineageInfo struct {
	LineageID           uint     `json:"lineageId"`
	SourceAssetID       uint     `json:"sourceAssetId"`
	SourceAssetName     string   `json:"sourceAssetName"`
	TargetAssetID       uint     `json:"targetAssetId"`
	TargetAssetName     string   `json:"targetAssetName"`
	LineageType         string   `json:"lineageType"`
	TransformExpression string   `json:"transformExpression"`
	TransformType       string   `json:"transformType"`
}

type DataQualityRule struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	RuleID       uint      `gorm:"column:rule_id;uniqueIndex" json:"ruleId"`
	AssetID      uint      `gorm:"column:asset_id;not null;index" json:"assetId"`
	RuleName     string    `gorm:"column:rule_name;not null" json:"ruleName"`
	RuleType     string    `gorm:"column:rule_type;not null" json:"ruleType"`
	Expression  string    `gorm:"column:expression;type:text" json:"expression"`
	Description string    `gorm:"column:description" json:"description"`
	IsActive    bool      `gorm:"column:is_active;default:true" json:"isActive"`
	CreatedTime int64     `gorm:"column:created_time" json:"createdTime"`
	UpdatedTime int64     `gorm:"column:updated_time" json:"updatedTime"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (DataQualityRule) TableName() string {
	return "data_quality_rules"
}

type DataQualityResult struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	ResultID    uint      `gorm:"column:result_id;uniqueIndex" json:"resultId"`
	RuleID      uint      `gorm:"column:rule_id;not null;index" json:"ruleId"`
	AssetID     uint      `gorm:"column:asset_id;not null;index" json:"assetId"`
	CheckTime   int64     `gorm:"column:check_time;not null" json:"checkTime"`
	Status      string    `gorm:"column:status;not null" json:"status"`
	Passed      bool      `gorm:"column:passed" json:"passed"`
	ActualValue string    `gorm:"column:actual_value" json:"actualValue"`
	ExpectedValue string `gorm:"column:expected_value" json:"expectedValue"`
	Message     string    `gorm:"column:message;type:text" json:"message"`
	CreatedTime int64     `gorm:"column:created_time" json:"createdTime"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

func (DataQualityResult) TableName() string {
	return "data_quality_results"
}