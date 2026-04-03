package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
)

type DataMarketHandler struct {
	service *service.DataMarketService
}

func NewDataMarketHandler(svc *service.DataMarketService) *DataMarketHandler {
	return &DataMarketHandler{service: svc}
}

func (h *DataMarketHandler) GetCatalogs(c *gin.Context) {
	catalogs, err := h.service.GetAllCatalogs()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, catalogs)
}

func (h *DataMarketHandler) GetCatalog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid catalog id"})
		return
	}

	catalog, err := h.service.GetCatalogById(uint(id))
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "catalog not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, catalog)
}

func (h *DataMarketHandler) CreateCatalog(c *gin.Context) {
	var catalog models.DataCatalog
	if err := c.ShouldBindJSON(&catalog); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result, err := h.service.CreateCatalog(&catalog)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, result)
}

func (h *DataMarketHandler) UpdateCatalog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid catalog id"})
		return
	}

	var catalog models.DataCatalog
	if err := c.ShouldBindJSON(&catalog); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result, err := h.service.UpdateCatalog(uint(id), &catalog)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *DataMarketHandler) DeleteCatalog(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid catalog id"})
		return
	}

	_, err = h.service.DeleteCatalog(uint(id))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "catalog deleted"})
}

func (h *DataMarketHandler) GetAssets(c *gin.Context) {
	assets, err := h.service.GetAllAssets()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, assets)
}

func (h *DataMarketHandler) GetAsset(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid asset id"})
		return
	}

	asset, err := h.service.GetAssetById(uint(id))
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "asset not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, asset)
}

func (h *DataMarketHandler) CreateAsset(c *gin.Context) {
	var asset models.DataAsset
	if err := c.ShouldBindJSON(&asset); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result, err := h.service.CreateAsset(&asset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, result)
}

func (h *DataMarketHandler) UpdateAsset(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid asset id"})
		return
	}

	var asset models.DataAsset
	if err := c.ShouldBindJSON(&asset); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result, err := h.service.UpdateAsset(uint(id), &asset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, result)
}

func (h *DataMarketHandler) DeleteAsset(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid asset id"})
		return
	}

	_, err = h.service.DeleteAsset(uint(id))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "asset deleted"})
}

func (h *DataMarketHandler) GetAssetsByCatalog(c *gin.Context) {
	catalogIdStr := c.Param("catalogId")
	catalogId, err := strconv.ParseUint(catalogIdStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid catalog id"})
		return
	}

	assets, err := h.service.GetAssetsByCatalog(uint(catalogId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, assets)
}

func (h *DataMarketHandler) AssignAssetToCatalog(c *gin.Context) {
	var req struct {
		AssetID   uint `json:"assetId"`
		CatalogID uint `json:"catalogId"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	_, err := h.service.AssignAssetToCatalog(req.AssetID, req.CatalogID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "asset assigned to catalog"})
}

func (h *DataMarketHandler) RemoveAssetFromCatalog(c *gin.Context) {
	var req struct {
		AssetID   uint `json:"assetId"`
		CatalogID uint `json:"catalogId"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	_, err := h.service.RemoveAssetFromCatalog(req.AssetID, req.CatalogID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "asset removed from catalog"})
}

func (h *DataMarketHandler) GetAssetLineage(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid asset id"})
		return
	}

	lineage, err := h.service.GetLineage(uint(id))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, lineage)
}

func (h *DataMarketHandler) CreateLineage(c *gin.Context) {
	var lineage models.DataLineage
	if err := c.ShouldBindJSON(&lineage); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	result, err := h.service.CreateLineage(&lineage)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, result)
}

func (h *DataMarketHandler) DeleteLineage(c *gin.Context) {
	idStr := c.Param("lineageId")
	id, err := strconv.ParseUint(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid lineage id"})
		return
	}

	_, err = h.service.DeleteLineage(uint(id))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "lineage deleted"})
}

func (h *DataMarketHandler) GetStats(c *gin.Context) {
	stats, err := h.service.GetAssetStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (h *DataMarketHandler) RegisterRoutes(r *gin.RouterGroup) {
	r.GET("/catalogs", h.GetCatalogs)
	r.GET("/catalogs/:id", h.GetCatalog)
	r.POST("/catalogs", h.CreateCatalog)
	r.PUT("/catalogs/:id", h.UpdateCatalog)
	r.DELETE("/catalogs/:id", h.DeleteCatalog)

	r.GET("/assets", h.GetAssets)
	r.GET("/assets/:id", h.GetAsset)
	r.POST("/assets", h.CreateAsset)
	r.PUT("/assets/:id", h.UpdateAsset)
	r.DELETE("/assets/:id", h.DeleteAsset)

	r.POST("/assets/assign", h.AssignAssetToCatalog)
	r.POST("/assets/remove", h.RemoveAssetFromCatalog)

	r.GET("/assets/:id/lineage", h.GetAssetLineage)
	r.POST("/lineage", h.CreateLineage)
	r.DELETE("/lineage/:lineageId", h.DeleteLineage)

	r.GET("/stats", h.GetStats)
}