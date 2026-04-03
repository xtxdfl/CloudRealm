package handler

import (
	"net/http"
	"strconv"

	"github.com/cloudrealm/cloud-server-go/models"
	"github.com/cloudrealm/cloud-server-go/service"
	"github.com/gin-gonic/gin"
)

type TagHandler struct {
	svc *service.TagService
}

func NewTagHandler(svc *service.TagService) *TagHandler {
	return &TagHandler{svc: svc}
}

func (h *TagHandler) GetCategories(c *gin.Context) {
	categories, err := h.svc.GetAllCategories()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, categories)
}

func (h *TagHandler) GetCategoriesByType(c *gin.Context) {
	categoryType := c.Param("categoryType")
	categories, err := h.svc.GetCategoriesByType(categoryType)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, categories)
}

func (h *TagHandler) CreateCategory(c *gin.Context) {
	var category models.HostTagCategory
	if err := c.ShouldBindJSON(&category); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreateCategory(&category)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *TagHandler) UpdateCategory(c *gin.Context) {
	categoryIdStr := c.Param("categoryId")
	categoryId, err := strconv.ParseUint(categoryIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid category ID"})
		return
	}

	var category models.HostTagCategory
	if err := c.ShouldBindJSON(&category); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	updated, err := h.svc.UpdateCategory(uint(categoryId), &category)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, updated)
}

func (h *TagHandler) DeleteCategory(c *gin.Context) {
	categoryIdStr := c.Param("categoryId")
	categoryId, err := strconv.ParseUint(categoryIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid category ID"})
		return
	}

	_, err = h.svc.DeleteCategory(uint(categoryId))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Category deleted"})
}

func (h *TagHandler) GetTags(c *gin.Context) {
	tags, err := h.svc.GetAllTags()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, tags)
}

func (h *TagHandler) GetTagsByCategory(c *gin.Context) {
	categoryIdStr := c.Param("categoryId")
	categoryId, err := strconv.ParseUint(categoryIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid category ID"})
		return
	}

	tags, err := h.svc.GetTagsByCategory(uint(categoryId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, tags)
}

func (h *TagHandler) GetTagsByCategoryType(c *gin.Context) {
	categoryType := c.Param("categoryType")
	tags, err := h.svc.GetTagsByCategoryType(categoryType)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, tags)
}

func (h *TagHandler) CreateTag(c *gin.Context) {
	var tag models.HostTag
	if err := c.ShouldBindJSON(&tag); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	created, err := h.svc.CreateTag(&tag)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, created)
}

func (h *TagHandler) UpdateTag(c *gin.Context) {
	tagIdStr := c.Param("tagId")
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	var tag models.HostTag
	if err := c.ShouldBindJSON(&tag); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	updated, err := h.svc.UpdateTag(uint(tagId), &tag)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, updated)
}

func (h *TagHandler) DeleteTag(c *gin.Context) {
	tagIdStr := c.Param("tagId")
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	_, err = h.svc.DeleteTag(uint(tagId))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Tag deleted"})
}

func (h *TagHandler) AddTagToHost(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	tagIdStr := c.Param("tagId")

	hostId, err := strconv.ParseUint(hostIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	_, err = h.svc.AddTagToHost(uint(hostId), uint(tagId))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Tag added to host"})
}

func (h *TagHandler) RemoveTagFromHost(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	tagIdStr := c.Param("tagId")

	hostId, err := strconv.ParseUint(hostIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	_, err = h.svc.RemoveTagFromHost(uint(hostId), uint(tagId))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Tag removed from host"})
}

func (h *TagHandler) AddTagsToHost(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.ParseUint(hostIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	var tagIds []uint
	if err := c.ShouldBindJSON(&tagIds); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	_, err = h.svc.AddTagsToHost(uint(hostId), tagIds)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Tags added to host"})
}

func (h *TagHandler) RemoveAllTagsFromHost(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.ParseUint(hostIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	_, err = h.svc.RemoveAllTagsFromHost(uint(hostId))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "All tags removed from host"})
}

func (h *TagHandler) GetTagsForHost(c *gin.Context) {
	hostIdStr := c.Param("hostId")
	hostId, err := strconv.ParseUint(hostIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid host ID"})
		return
	}

	tags, err := h.svc.GetTagsForHost(uint(hostId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, tags)
}

func (h *TagHandler) GetHostsForTag(c *gin.Context) {
	tagIdStr := c.Param("tagId")
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	hostIds, err := h.svc.GetHostsForTag(uint(tagId))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, hostIds)
}

func (h *TagHandler) AddTagToHosts(c *gin.Context) {
	tagIdStr := c.Param("tagId")
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	var hostIds []uint
	if err := c.ShouldBindJSON(&hostIds); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	_, err = h.svc.AddTagToHosts(uint(tagId), hostIds)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Tag added to hosts"})
}

func (h *TagHandler) RemoveTagFromHosts(c *gin.Context) {
	tagIdStr := c.Param("tagId")
	tagId, err := strconv.ParseUint(tagIdStr, 10, 32)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid tag ID"})
		return
	}

	var hostIds []uint
	if err := c.ShouldBindJSON(&hostIds); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	_, err = h.svc.RemoveTagFromHosts(uint(tagId), hostIds)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "Tag removed from hosts"})
}

func (h *TagHandler) RegisterRoutes(r *gin.RouterGroup) {
	r.GET("/categories", h.GetCategories)
	r.GET("/categories/type/:categoryType", h.GetCategoriesByType)
	r.POST("/categories", h.CreateCategory)
	r.PUT("/categories/:categoryId", h.UpdateCategory)
	r.DELETE("/categories/:categoryId", h.DeleteCategory)

	r.GET("", h.GetTags)
	r.GET("/category/:categoryId", h.GetTagsByCategory)
	r.GET("/type/:categoryType", h.GetTagsByCategoryType)
	r.POST("", h.CreateTag)
	r.PUT("/:tagId", h.UpdateTag)
	r.DELETE("/:tagId", h.DeleteTag)

	r.POST("/host/:hostId/tag/:tagId", h.AddTagToHost)
	r.DELETE("/host/:hostId/tag/:tagId", h.RemoveTagFromHost)
	r.POST("/host/:hostId/tags", h.AddTagsToHost)
	r.DELETE("/host/:hostId/tags", h.RemoveAllTagsFromHost)
	r.GET("/host/:hostId", h.GetTagsForHost)

	r.GET("/:tagId/hosts", h.GetHostsForTag)
	r.POST("/hosts/:tagId", h.AddTagToHosts)
	r.DELETE("/hosts/:tagId", h.RemoveTagFromHosts)
}