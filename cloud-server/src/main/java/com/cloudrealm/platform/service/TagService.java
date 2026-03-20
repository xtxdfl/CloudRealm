package com.cloudrealm.platform.service;

import com.cloudrealm.platform.entity.HostEntity;
import com.cloudrealm.platform.entity.HostTagCategoryEntity;
import com.cloudrealm.platform.entity.HostTagEntity;
import com.cloudrealm.platform.entity.HostTagMappingEntity;
import com.cloudrealm.platform.repository.HostRepository;
import com.cloudrealm.platform.repository.HostTagCategoryRepository;
import com.cloudrealm.platform.repository.HostTagMappingRepository;
import com.cloudrealm.platform.repository.HostTagRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service
public class TagService {

    @Autowired
    private HostTagCategoryRepository categoryRepository;

    @Autowired
    private HostTagRepository tagRepository;

    @Autowired
    private HostTagMappingRepository mappingRepository;

    @Autowired
    private HostRepository hostRepository;

    // ==================== 标签分类管理 ====================

    /**
     * 获取所有标签分类
     */
    public List<HostTagCategoryEntity> getAllCategories() {
        return categoryRepository.findAll();
    }

    /**
     * 按类型获取标签分类
     */
    public List<HostTagCategoryEntity> getCategoriesByType(String categoryType) {
        return categoryRepository.findByCategoryType(categoryType);
    }

    /**
     * 创建标签分类
     */
    @Transactional
    public HostTagCategoryEntity createCategory(HostTagCategoryEntity category) {
        if (categoryRepository.existsByCategoryNameAndCategoryType(
                category.getCategoryName(), category.getCategoryType())) {
            throw new RuntimeException("Category with same name and type already exists");
        }
        category.setCreatedTime(System.currentTimeMillis());
        category.setUpdatedTime(System.currentTimeMillis());
        return categoryRepository.save(category);
    }

    /**
     * 更新标签分类
     */
    @Transactional
    public HostTagCategoryEntity updateCategory(Long categoryId, HostTagCategoryEntity category) {
        HostTagCategoryEntity existing = categoryRepository.findById(categoryId)
                .orElseThrow(() -> new RuntimeException("Category not found"));

        if (category.getCategoryName() != null) {
            existing.setCategoryName(category.getCategoryName());
        }
        if (category.getDescription() != null) {
            existing.setDescription(category.getDescription());
        }
        if (category.getColor() != null) {
            existing.setColor(category.getColor());
        }
        if (category.getSortOrder() != null) {
            existing.setSortOrder(category.getSortOrder());
        }
        existing.setUpdatedTime(System.currentTimeMillis());

        return categoryRepository.save(existing);
    }

    /**
     * 删除标签分类
     */
    @Transactional
    public void deleteCategory(Long categoryId) {
        categoryRepository.deleteById(categoryId);
    }

    // ==================== 标签管理 ====================

    /**
     * 获取所有标签
     */
    public List<HostTagEntity> getAllTags() {
        return tagRepository.findAll();
    }

    /**
     * 按分类获取标签
     */
    public List<HostTagEntity> getTagsByCategory(Long categoryId) {
        return tagRepository.findByCategoryCategoryId(categoryId);
    }

    /**
     * 按分类类型获取标签
     */
    public List<HostTagEntity> getTagsByCategoryType(String categoryType) {
        return tagRepository.findByCategoryType(categoryType);
    }

    /**
     * 创建标签
     */
    @Transactional
    public HostTagEntity createTag(HostTagEntity tag) {
        if (tag.getCategory() == null || tag.getCategory().getCategoryId() == null) {
            throw new RuntimeException("Category is required for tag");
        }

        HostTagCategoryEntity category = categoryRepository.findById(tag.getCategory().getCategoryId())
                .orElseThrow(() -> new RuntimeException("Category not found"));
        tag.setCategory(category);

        if (tagRepository.existsByTagNameAndCategoryCategoryId(tag.getTagName(), category.getCategoryId())) {
            throw new RuntimeException("Tag with same name in this category already exists");
        }

        tag.setCreatedTime(System.currentTimeMillis());
        tag.setUpdatedTime(System.currentTimeMillis());
        return tagRepository.save(tag);
    }

    /**
     * 更新标签
     */
    @Transactional
    public HostTagEntity updateTag(Long tagId, HostTagEntity tag) {
        HostTagEntity existing = tagRepository.findById(tagId)
                .orElseThrow(() -> new RuntimeException("Tag not found"));

        if (tag.getTagName() != null) {
            existing.setTagName(tag.getTagName());
        }
        if (tag.getDescription() != null) {
            existing.setDescription(tag.getDescription());
        }
        if (tag.getColor() != null) {
            existing.setColor(tag.getColor());
        }
        existing.setUpdatedTime(System.currentTimeMillis());

        return tagRepository.save(existing);
    }

    /**
     * 删除标签
     */
    @Transactional
    public void deleteTag(Long tagId) {
        tagRepository.deleteById(tagId);
    }

    // ==================== 主机标签关联管理 ====================

    /**
     * 为主机添加标签
     */
    @Transactional
    public void addTagToHost(Long hostId, Long tagId) {
        HostEntity host = hostRepository.findById(hostId)
                .orElseThrow(() -> new RuntimeException("Host not found"));
        HostTagEntity tag = tagRepository.findById(tagId)
                .orElseThrow(() -> new RuntimeException("Tag not found"));

        if (!mappingRepository.existsByHostIdAndTagId(hostId, tagId)) {
            HostTagMappingEntity mapping = new HostTagMappingEntity();
            mapping.setHostId(hostId);
            mapping.setTagId(tagId);
            mapping.setAssignedTime(System.currentTimeMillis());
            mappingRepository.save(mapping);
        }
    }

    /**
     * 移除主机标签
     */
    @Transactional
    public void removeTagFromHost(Long hostId, Long tagId) {
        HostTagMappingEntity mapping = new HostTagMappingEntity();
        mapping.setHostId(hostId);
        mapping.setTagId(tagId);
        mappingRepository.delete(mapping);
    }

    /**
     * 批量为主机添加标签
     */
    @Transactional
    public void addTagsToHost(Long hostId, List<Long> tagIds) {
        for (Long tagId : tagIds) {
            addTagToHost(hostId, tagId);
        }
    }

    /**
     * 批量移除主机标签
     */
    @Transactional
    public void removeAllTagsFromHost(Long hostId) {
        mappingRepository.deleteByHostId(hostId);
    }

    /**
     * 为多个主机添加相同标签
     */
    @Transactional
    public void addTagToHosts(List<Long> hostIds, Long tagId) {
        for (Long hostId : hostIds) {
            addTagToHost(hostId, tagId);
        }
    }

    /**
     * 获取主机所有标签
     */
    public List<HostTagEntity> getTagsForHost(Long hostId) {
        return tagRepository.findTagsByHostId(hostId);
    }

    /**
     * 获取标签关联的所有主机
     */
    public List<HostEntity> getHostsForTag(Long tagId) {
        List<Long> hostIds = mappingRepository.findHostIdsByTagId(tagId);
        List<HostEntity> hosts = new ArrayList<>();
        for (Long hostId : hostIds) {
            Optional<HostEntity> host = hostRepository.findById(hostId);
            host.ifPresent(hosts::add);
        }
        return hosts;
    }

    /**
     * 初始化默认标签分类和标签
     */
    @Transactional
    public void initDefaultTags() {
        // 创建默认分类
        List<HostTagCategoryEntity> defaultCategories = new ArrayList<>();

        HostTagCategoryEntity purposeCategory = new HostTagCategoryEntity();
        purposeCategory.setCategoryName("用途");
        purposeCategory.setCategoryType("PURPOSE");
        purposeCategory.setDescription("按主机用途分类，如Hadoop DataNode、Master节点等");
        purposeCategory.setColor("#6366f1");
        purposeCategory.setSortOrder(1);
        if (!categoryRepository.existsByCategoryNameAndCategoryType("用途", "PURPOSE")) {
            defaultCategories.add(categoryRepository.save(purposeCategory));
        }

        HostTagCategoryEntity envCategory = new HostTagCategoryEntity();
        envCategory.setCategoryName("环境");
        envCategory.setCategoryType("ENVIRONMENT");
        envCategory.setDescription("按环境分类，如生产环境、测试环境等");
        envCategory.setColor("#10b981");
        envCategory.setSortOrder(2);
        if (!categoryRepository.existsByCategoryNameAndCategoryType("环境", "ENVIRONMENT")) {
            defaultCategories.add(categoryRepository.save(envCategory));
        }

        HostTagCategoryEntity regionCategory = new HostTagCategoryEntity();
        regionCategory.setCategoryName("区域");
        regionCategory.setCategoryType("REGION");
        regionCategory.setDescription("按网络区域或机房分类");
        regionCategory.setColor("#f59e0b");
        regionCategory.setSortOrder(3);
        if (!categoryRepository.existsByCategoryNameAndCategoryType("区域", "REGION")) {
            defaultCategories.add(categoryRepository.save(regionCategory));
        }

        // 创建默认标签
        for (HostTagCategoryEntity category : defaultCategories) {
            createDefaultTagsForCategory(category);
        }
    }

    private void createDefaultTagsForCategory(HostTagCategoryEntity category) {
        List<HostTagEntity> defaultTags = new ArrayList<>();

        switch (category.getCategoryType()) {
            case "PURPOSE":
                defaultTags.add(createTagIfNotExists("Hadoop DataNode", category, "#8b5cf6"));
                defaultTags.add(createTagIfNotExists("Hadoop NameNode", category, "#ec4899"));
                defaultTags.add(createTagIfNotExists("Master节点", category, "#ef4444"));
                defaultTags.add(createTagIfNotExists("Worker节点", category, "#3b82f6"));
                defaultTags.add(createTagIfNotExists("Gateway", category, "#14b8a6"));
                defaultTags.add(createTagIfNotExists("数据库", category, "#f97316"));
                break;
            case "ENVIRONMENT":
                defaultTags.add(createTagIfNotExists("生产环境", category, "#22c55e"));
                defaultTags.add(createTagIfNotExists("测试环境", category, "#eab308"));
                defaultTags.add(createTagIfNotExists("开发环境", category, "#3b82f6"));
                defaultTags.add(createTagIfNotExists("预发布环境", category, "#a855f7"));
                break;
            case "REGION":
                defaultTags.add(createTagIfNotExists("华北区域", category, "#06b6d4"));
                defaultTags.add(createTagIfNotExists("华东区域", category, "#0ea5e9"));
                defaultTags.add(createTagIfNotExists("华南区域", category, "#0284c7"));
                defaultTags.add(createTagIfNotExists("海外区域", category, "#6366f1"));
                break;
        }
    }

    private HostTagEntity createTagIfNotExists(String tagName, HostTagCategoryEntity category, String color) {
        if (tagRepository.existsByTagNameAndCategoryCategoryId(tagName, category.getCategoryId())) {
            return null;
        }
        HostTagEntity tag = new HostTagEntity();
        tag.setTagName(tagName);
        tag.setCategory(category);
        tag.setColor(color);
        tag.setCreatedTime(System.currentTimeMillis());
        tag.setUpdatedTime(System.currentTimeMillis());
        return tagRepository.save(tag);
    }
}
