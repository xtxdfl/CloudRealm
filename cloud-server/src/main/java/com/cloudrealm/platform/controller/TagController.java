package com.cloudrealm.platform.controller;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.entity.HostTagCategoryEntity;
import com.cloudrealm.platform.entity.HostTagEntity;
import com.cloudrealm.platform.service.TagService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/tags")
@CrossOrigin(origins = "*")
public class TagController {

    @Autowired
    private TagService tagService;

    // ==================== 标签分类管理 ====================

    /**
     * 获取所有标签分类
     */
    @GetMapping("/categories")
    public List<HostTagCategoryEntity> getAllCategories() {
        return tagService.getAllCategories();
    }

    /**
     * 按类型获取标签分类
     */
    @GetMapping("/categories/type/{categoryType}")
    public List<HostTagCategoryEntity> getCategoriesByType(@PathVariable String categoryType) {
        return tagService.getCategoriesByType(categoryType);
    }

    /**
     * 创建标签分类
     */
    @PostMapping("/categories")
    public ResponseEntity<HostTagCategoryEntity> createCategory(@RequestBody HostTagCategoryEntity category) {
        try {
            HostTagCategoryEntity created = tagService.createCategory(category);
            return ResponseEntity.ok(created);
        } catch (Exception e) {
            return ResponseEntity.badRequest().build();
        }
    }

    /**
     * 更新标签分类
     */
    @PutMapping("/categories/{categoryId}")
    public ResponseEntity<HostTagCategoryEntity> updateCategory(
            @PathVariable Long categoryId,
            @RequestBody HostTagCategoryEntity category) {
        try {
            HostTagCategoryEntity updated = tagService.updateCategory(categoryId, category);
            return ResponseEntity.ok(updated);
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * 删除标签分类
     */
    @DeleteMapping("/categories/{categoryId}")
    public ResponseEntity<String> deleteCategory(@PathVariable Long categoryId) {
        tagService.deleteCategory(categoryId);
        return ResponseEntity.ok("Category deleted");
    }

    // ==================== 标签管理 ====================

    /**
     * 获取所有标签
     */
    @GetMapping
    public List<HostTagEntity> getAllTags() {
        return tagService.getAllTags();
    }

    /**
     * 按分类获取标签
     */
    @GetMapping("/category/{categoryId}")
    public List<HostTagEntity> getTagsByCategory(@PathVariable Long categoryId) {
        return tagService.getTagsByCategory(categoryId);
    }

    /**
     * 按分类类型获取标签
     */
    @GetMapping("/type/{categoryType}")
    public List<HostTagEntity> getTagsByCategoryType(@PathVariable String categoryType) {
        return tagService.getTagsByCategoryType(categoryType);
    }

    /**
     * 创建标签
     */
    @PostMapping
    public ResponseEntity<HostTagEntity> createTag(@RequestBody HostTagEntity tag) {
        try {
            HostTagEntity created = tagService.createTag(tag);
            return ResponseEntity.ok(created);
        } catch (Exception e) {
            return ResponseEntity.badRequest().build();
        }
    }

    /**
     * 更新标签
     */
    @PutMapping("/{tagId}")
    public ResponseEntity<HostTagEntity> updateTag(
            @PathVariable Long tagId,
            @RequestBody HostTagEntity tag) {
        try {
            HostTagEntity updated = tagService.updateTag(tagId, tag);
            return ResponseEntity.ok(updated);
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * 删除标签
     */
    @DeleteMapping("/{tagId}")
    public ResponseEntity<String> deleteTag(@PathVariable Long tagId) {
        tagService.deleteTag(tagId);
        return ResponseEntity.ok("Tag deleted");
    }

    // ==================== 主机标签关联管理 ====================

    /**
     * 为主机添加标签
     */
    @PostMapping("/host/{hostId}/tag/{tagId}")
    public ResponseEntity<String> addTagToHost(
            @PathVariable Long hostId,
            @PathVariable Long tagId) {
        try {
            tagService.addTagToHost(hostId, tagId);
            return ResponseEntity.ok("Tag added to host");
        } catch (Exception e) {
            return ResponseEntity.badRequest().build();
        }
    }

    /**
     * 移除主机标签
     */
    @DeleteMapping("/host/{hostId}/tag/{tagId}")
    public ResponseEntity<String> removeTagFromHost(
            @PathVariable Long hostId,
            @PathVariable Long tagId) {
        tagService.removeTagFromHost(hostId, tagId);
        return ResponseEntity.ok("Tag removed from host");
    }

    /**
     * 批量为主机添加标签
     */
    @PostMapping("/host/{hostId}/tags")
    public ResponseEntity<String> addTagsToHost(
            @PathVariable Long hostId,
            @RequestBody List<Long> tagIds) {
        tagService.addTagsToHost(hostId, tagIds);
        return ResponseEntity.ok("Tags added to host");
    }

    /**
     * 移除主机所有标签
     */
    @DeleteMapping("/host/{hostId}/tags")
    public ResponseEntity<String> removeAllTagsFromHost(@PathVariable Long hostId) {
        tagService.removeAllTagsFromHost(hostId);
        return ResponseEntity.ok("All tags removed from host");
    }

    /**
     * 获取主机所有标签
     */
    @GetMapping("/host/{hostId}")
    public List<HostTagEntity> getTagsForHost(@PathVariable Long hostId) {
        return tagService.getTagsForHost(hostId);
    }

    /**
     * 获取标签关联的所有主机
     */
    @GetMapping("/{tagId}/hosts")
    public List<HostEntity> getHostsForTag(@PathVariable Long tagId) {
        return tagService.getHostsForTag(tagId);
    }

    /**
     * 为多个主机添加相同标签
     */
    @PostMapping("/hosts/{tagId}")
    public ResponseEntity<String> addTagToHosts(
            @PathVariable Long tagId,
            @RequestBody List<Long> hostIds) {
        tagService.addTagToHosts(hostIds, tagId);
        return ResponseEntity.ok("Tag added to hosts");
    }

    /**
     * 初始化默认标签
     */
    @PostMapping("/init-defaults")
    public ResponseEntity<String> initDefaultTags() {
        tagService.initDefaultTags();
        return ResponseEntity.ok("Default tags initialized");
    }
}
