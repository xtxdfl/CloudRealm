import React, { useState, useEffect } from 'react';
import { Tags, Plus, Edit, Trash2, Search, Check, X, Folder } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TagCategory {
  categoryId: number;
  categoryName: string;
  categoryType: string;
  description: string;
  color: string;
  sortOrder: number;
}

interface HostTag {
  tagId: number;
  tagName: string;
  categoryId: number;
  category?: TagCategory;
  description: string;
  color: string;
}

export default function TagMgt({ activeSubView }: { activeSubView?: string }) {
  const [categories, setCategories] = useState<TagCategory[]>([]);
  const [tags, setTags] = useState<HostTag[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<TagCategory | null>(null);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showTagModal, setShowTagModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<TagCategory | null>(null);
  const [editingTag, setEditingTag] = useState<HostTag | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  // 表单状态
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryType, setNewCategoryType] = useState('');
  const [newCategoryDesc, setNewCategoryDesc] = useState('');
  const [newCategoryColor, setNewCategoryColor] = useState('#6366f1');
  const [newCategoryOrder, setNewCategoryOrder] = useState(1);

  const [newTagName, setNewTagName] = useState('');
  const [newTagCategory, setNewTagCategory] = useState<number | null>(null);
  const [newTagDesc, setNewTagDesc] = useState('');
  const [newTagColor, setNewTagColor] = useState('#8b5cf6');

  const [isProcessing, setIsProcessing] = useState(false);

  // 模拟API调用
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    // 模拟数据，保留原有模拟数据
    const mockCategories: TagCategory[] = [
      { categoryId: 1, categoryName: '用途', categoryType: 'PURPOSE', description: '按主机用途分类', color: '#6366f1', sortOrder: 1 },
      { categoryId: 2, categoryName: '环境', categoryType: 'ENVIRONMENT', description: '按环境分类', color: '#10b981', sortOrder: 2 },
      { categoryId: 3, categoryName: '区域', categoryType: 'REGION', description: '按网络区域分类', color: '#f59e0b', sortOrder: 3 },
    ];

    const mockTags: HostTag[] = [
      { tagId: 1, tagName: 'Hadoop DataNode', categoryId: 1, description: 'Hadoop数据节点', color: '#8b5cf6' },
      { tagId: 2, tagName: 'Hadoop NameNode', categoryId: 1, description: 'Hadoop名称节点', color: '#ec4899' },
      { tagId: 3, tagName: 'Master节点', categoryId: 1, description: '主节点', color: '#ef4444' },
      { tagId: 4, tagName: 'Worker节点', categoryId: 1, description: '工作节点', color: '#3b82f6' },
      { tagId: 5, tagName: '生产环境', categoryId: 2, description: '生产环境主机', color: '#22c55e' },
      { tagId: 6, tagName: '测试环境', categoryId: 2, description: '测试环境主机', color: '#eab308' },
      { tagId: 7, tagName: '开发环境', categoryId: 2, description: '开发环境主机', color: '#3b82f6' },
      { tagId: 8, tagName: '华北区域', categoryId: 3, description: '华北机房', color: '#06b6d4' },
      { tagId: 9, tagName: '华东区域', categoryId: 3, description: '华东机房', color: '#0ea5e9' },
    ];

    setCategories(mockCategories);
    setTags(mockTags);
  };

  // 重置分类表单
  const resetCategoryForm = () => {
    setNewCategoryName('');
    setNewCategoryType('');
    setNewCategoryDesc('');
    setNewCategoryColor('#6366f1');
    setNewCategoryOrder(Math.max(1, ...categories.map(c => c.sortOrder)) + 1);
    setEditingCategory(null);
  };

  // 添加或更新分类
  const saveCategory = () => {
    setIsProcessing(true);
    setTimeout(() => {
      if (editingCategory) {
        // 更新现有分类
        setCategories(categories.map(c =>
          c.categoryId === editingCategory.categoryId
            ? {
                ...c,
                categoryName: newCategoryName,
                categoryType: newCategoryType,
                description: newCategoryDesc,
                color: newCategoryColor,
                sortOrder: newCategoryOrder
              }
            : c
        ));
      } else {
        // 添加新分类
        const newCategory: TagCategory = {
          categoryId: Math.max(0, ...categories.map(c => c.categoryId)) + 1,
          categoryName: newCategoryName,
          categoryType: newCategoryType,
          description: newCategoryDesc,
          color: newCategoryColor,
          sortOrder: newCategoryOrder
        };
        setCategories([...categories, newCategory]);
      }
      setIsProcessing(false);
      setShowCategoryModal(false);
      resetCategoryForm();
    }, 500);
  };

  // 删除分类
  const deleteCategory = (id: number) => {
    if (window.confirm('确定要删除此分类吗？相关标签也会被删除')) {
      // 删除分类
      setCategories(categories.filter(c => c.categoryId !== id));
      // 同时删除属于此分类的标签
      setTags(tags.filter(t => t.categoryId !== id));
    }
  };

  // 重置标签表单
  const resetTagForm = () => {
    setNewTagName('');
    setNewTagCategory(null);
    setNewTagDesc('');
    setNewTagColor('#8b5cf6');
    setEditingTag(null);
  };

  // 添加或更新标签
  const saveTag = () => {
    if (!newTagCategory) {
      alert('请选择分类');
      return;
    }

    setIsProcessing(true);
    setTimeout(() => {
      if (editingTag) {
        // 更新现有标签
        setTags(tags.map(t =>
          t.tagId === editingTag.tagId
            ? {
                ...t,
                tagName: newTagName,
                categoryId: newTagCategory,
                description: newTagDesc,
                color: newTagColor
              }
            : t
        ));
      } else {
        // 添加新标签
        const newTag: HostTag = {
          tagId: Math.max(0, ...tags.map(t => t.tagId)) + 1,
          tagName: newTagName,
          categoryId: newTagCategory,
          description: newTagDesc,
          color: newTagColor
        };
        setTags([...tags, newTag]);
      }
      setIsProcessing(false);
      setShowTagModal(false);
      resetTagForm();
    }, 500);
  };

  // 删除标签
  const deleteTag = (id: number) => {
    if (window.confirm('确定要删除此标签吗？')) {
      setTags(tags.filter(t => t.tagId !== id));
    }
  };

  // 分类模态框组件
  const renderCategoryModal = () => {
    if (!showCategoryModal) return null;

    const isEditing = !!editingCategory;

    // 如果正在编辑，用编辑的值填充表单
    if (isEditing && editingCategory && newCategoryName === '') {
      setNewCategoryName(editingCategory.categoryName);
      setNewCategoryType(editingCategory.categoryType);
      setNewCategoryDesc(editingCategory.description);
      setNewCategoryColor(editingCategory.color);
      setNewCategoryOrder(editingCategory.sortOrder);
    }

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-lg p-4">
        <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
          <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
            <h3 className="text-xl font-bold text-white">
              {isEditing ? '编辑分类' : '添加新分类'}
            </h3>
            <button
              onClick={() => {
                setShowCategoryModal(false);
                resetCategoryForm();
              }}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-300 mb-1 block">分类名称 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="用途分类名称"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">分类类型 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="PURPOSE / ENVIRONMENT / REGION"
                value={newCategoryType}
                onChange={(e) => setNewCategoryType(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">描述</label>
              <textarea
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="详细描述此分类"
                rows={3}
                value={newCategoryDesc}
                onChange={(e) => setNewCategoryDesc(e.target.value)}
              ></textarea>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-slate-300 mb-1 block">颜色标识</label>
                <div className="flex">
                  <input
                    type="color"
                    className="w-10 h-10 rounded cursor-pointer"
                    value={newCategoryColor}
                    onChange={(e) => setNewCategoryColor(e.target.value)}
                  />
                  <span className="ml-2 flex items-center text-slate-400 text-sm">
                    {newCategoryColor}
                  </span>
                </div>
              </div>

              <div>
                <label className="text-sm text-slate-300 mb-1 block">排序</label>
                <input
                  type="number"
                  min="1"
                  className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                  value={newCategoryOrder}
                  onChange={(e) => setNewCategoryOrder(parseInt(e.target.value))}
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-5 mt-4 border-t border-white/10">
            <button
              onClick={() => {
                setShowCategoryModal(false);
                resetCategoryForm();
              }}
              className="px-4 py-2 rounded-lg border border-slate-500 text-white hover:bg-white/5 transition-colors"
            >
              取消
            </button>
            <button
              onClick={saveCategory}
              disabled={isProcessing || !newCategoryName || !newCategoryType}
              className={cn(
                "px-4 py-2 rounded-lg flex items-center",
                isProcessing || !newCategoryName || !newCategoryType
                  ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                  : "bg-[#00ff9d] text-[#020617] hover:bg-[#00e68e]"
              )}
            >
              {isProcessing ? (
                <span>处理中...</span>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  {isEditing ? '更新分类' : '添加分类'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // 标签模态框组件
  const renderTagModal = () => {
    if (!showTagModal) return null;

    const isEditing = !!editingTag;

    // 如果正在编辑，用编辑的值填充表单
    if (isEditing && editingTag && newTagName === '') {
      setNewTagName(editingTag.tagName);
      setNewTagCategory(editingTag.categoryId);
      setNewTagDesc(editingTag.description);
      setNewTagColor(editingTag.color);
    }

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-lg p-4">
        <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
          <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
            <h3 className="text-xl font-bold text-white">
              {isEditing ? '编辑标签' : '添加新标签'}
            </h3>
            <button
              onClick={() => {
                setShowTagModal(false);
                resetTagForm();
              }}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-300 mb-1 block">标签名称 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="标签名称"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">所属分类 *</label>
              <select
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors appearance-none"
                value={newTagCategory || ''}
                onChange={(e) => setNewTagCategory(parseInt(e.target.value))}
              >
                <option value="" disabled>选择分类</option>
                {categories.map(category => (
                  <option
                    key={category.categoryId}
                    value={category.categoryId}
                    style={{ color: category.color }}
                  >
                    {category.categoryName}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">描述</label>
              <textarea
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="详细描述此标签"
                rows={3}
                value={newTagDesc}
                onChange={(e) => setNewTagDesc(e.target.value)}
              ></textarea>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm text-slate-300 mb-1 block">颜色标识</label>
                <div className="flex items-center">
                  <input
                    type="color"
                    className="w-10 h-10 rounded cursor-pointer"
                    value={newTagColor}
                    onChange={(e) => setNewTagColor(e.target.value)}
                  />
                  <span className="ml-2 text-slate-400 text-sm">
                    {newTagColor}
                  </span>
                </div>
              </div>

              {newTagCategory && (
                <div className="flex items-center">
                  <span className="text-sm text-slate-400 mr-3">分类颜色：</span>
                  <div
                    className="w-8 h-8 rounded-lg"
                    style={{
                      backgroundColor: categories.find(c => c.categoryId === newTagCategory)?.color + '30',
                      border: `2px solid ${categories.find(c => c.categoryId === newTagCategory)?.color}`
                    }}
                  />
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-5 mt-4 border-t border-white/10">
            <button
              onClick={() => {
                setShowTagModal(false);
                resetTagForm();
              }}
              className="px-4 py-2 rounded-lg border border-slate-500 text-white hover:bg-white/5 transition-colors"
            >
              取消
            </button>
            <button
              onClick={saveTag}
              disabled={isProcessing || !newTagName || !newTagCategory}
              className={cn(
                "px-4 py-2 rounded-lg flex items-center",
                isProcessing || !newTagName || !newTagCategory
                  ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                  : "bg-[#00ff9d] text-[#020617] hover:bg-[#00e68e]"
              )}
            >
              {isProcessing ? (
                <span>处理中...</span>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  {isEditing ? '更新标签' : '添加标签'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderTagCategories = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-white">标签分类管理</h2>
        <button
          onClick={() => {
            resetCategoryForm();
            setShowCategoryModal(true);
          }}
          className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold flex items-center hover:bg-[#00e68e]"
        >
          <Plus className="w-4 h-4 mr-2" /> 添加分类
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.map(category => (
          <div
            key={category.categoryId}
            className={cn(
              "glass-panel p-6 rounded-2xl hover:border-white/20 transition-all cursor-pointer",
              selectedCategory?.categoryId === category.categoryId && "ring-2 ring-[#00ff9d]"
            )}
            onClick={() => {
              setSelectedCategory(category);
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center mr-3"
                  style={{ backgroundColor: category.color + '20' }}
                >
                  <Folder className="w-5 h-5" style={{ color: category.color }} />
                </div>
                <div>
                  <h3 className="font-bold text-white">{category.categoryName}</h3>
                  <span className="text-xs text-slate-400">{category.categoryType}</span>
                </div>
              </div>
            </div>
            <p className="text-sm text-slate-400 mb-4">{category.description}</p>
            <div className="flex justify-between items-center pt-4 border-t border-white/5">
              <span className="text-xs text-slate-500">排序: {category.sortOrder}</span>
              <div className="flex space-x-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingCategory(category);
                    setShowCategoryModal(true);
                  }}
                  className="p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded"
                >
                  <Edit className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteCategory(category.categoryId);
                  }}
                  className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {categories.length === 0 && (
        <div className="glass-panel text-center py-16 rounded-2xl">
          <Folder className="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-white mb-2">暂无标签分类</h3>
          <p className="text-slate-500 mb-4">创建一个标签分类来组织你的资源</p>
          <button
            onClick={() => {
              resetCategoryForm();
              setShowCategoryModal(true);
            }}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg font-bold flex items-center justify-center mx-auto hover:bg-[#00e68e]"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加分类
          </button>
        </div>
      )}
    </div>
  );

  const renderTagManagement = () => {
    const filteredTags = searchTerm
      ? tags.filter(t => t.tagName.toLowerCase().includes(searchTerm.toLowerCase()))
      : tags;

    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">标签管理</h2>
          <button
            onClick={() => {
              resetTagForm();
              setShowTagModal(true);
            }}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold flex items-center hover:bg-[#00e68e]"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加标签
          </button>
        </div>

        <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full max-w-md">
          <Search className="w-4 h-4 text-slate-500 mr-2" />
          <input
            type="text"
            placeholder="搜索标签名称..."
            className="bg-transparent border-none text-sm text-white focus:ring-0 w-full"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {tags.length > 0 ? (
          <div className="glass-panel rounded-2xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="px-6 py-3">标签名称</th>
                  <th className="px-6 py-3">分类</th>
                  <th className="px-6 py-3">描述</th>
                  <th className="px-6 py-3">颜色</th>
                  <th className="px-6 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                {filteredTags.map(tag => {
                  const category = categories.find(c => c.categoryId === tag.categoryId);
                  return (
                    <tr key={tag.tagId} className="hover:bg-white/5 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <span
                            className="w-3 h-3 rounded-full mr-2"
                            style={{ backgroundColor: tag.color }}
                          />
                          <span className="font-medium text-white">{tag.tagName}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {category ? (
                          <span
                            className="px-2 py-1 rounded text-xs font-medium"
                            style={{ backgroundColor: category?.color + '20', color: category?.color }}
                          >
                            {category?.categoryName}
                          </span>
                        ) : (
                          <span className="text-red-500 text-xs">分类已删除</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-400">{tag.description}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          <div
                            className="w-6 h-6 rounded"
                            style={{ backgroundColor: tag.color }}
                          />
                          <span className="ml-2 text-xs text-slate-500">{tag.color}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => {
                              setEditingTag(tag);
                              setShowTagModal(true);
                            }}
                            className="p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteTag(tag.tagId)}
                            className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="glass-panel text-center py-16 rounded-2xl">
            <Tags className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">暂无标签数据</h3>
            <p className="text-slate-500 mb-4">添加标签来管理你的主机资源</p>
            <button
              onClick={() => {
                resetTagForm();
                setShowTagModal(true);
              }}
              className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg font-bold flex items-center justify-center mx-auto hover:bg-[#00e68e]"
            >
              <Plus className="w-4 h-4 mr-2" /> 添加标签
            </button>
          </div>
        )}

        {tags.length > 0 && filteredTags.length === 0 && (
          <div className="glass-panel text-center py-12 rounded-2xl">
            <Search className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">未找到匹配的标签</h3>
            <p className="text-slate-500">请尝试不同的搜索关键词</p>
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      {activeSubView === '标签分类' && renderTagCategories()}
      {activeSubView === '标签管理' && renderTagManagement()}
      {(!activeSubView || activeSubView === '') && (
        <div className="space-y-6">
          <div className="glass-panel p-12 rounded-2xl text-center">
            <Tags className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">标签管理</h3>
            <p className="text-slate-400 mb-6">按用途、环境、区域等维度对主机进行分组管理</p>
            <div className="flex justify-center space-x-4">
              <button
                onClick={() => loadData()}
                className="px-6 py-3 bg-[#00ff9d] text-[#020617] rounded-lg font-bold hover:bg-[#00e68e]"
              >
                查看标签
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-panel p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-bold text-white">标签分类</h4>
                <span className="text-2xl font-bold text-[#00ff9d]">{categories.length}</span>
              </div>
              <p className="text-sm text-slate-400">用途、环境、区域等分类</p>
            </div>
            <div className="glass-panel p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-bold text-white">标签数量</h4>
                <span className="text-2xl font-bold text-[#38bdf8]">{tags.length}</span>
              </div>
              <p className="text-sm text-slate-400">已创建的标签总数</p>
            </div>
            <div className="glass-panel p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-bold text-white">主机关联</h4>
                <span className="text-2xl font-bold text-[#a855f7]">0</span>
              </div>
              <p className="text-sm text-slate-400">已标记的主机数量</p>
            </div>
          </div>
        </div>
      )}

      {renderCategoryModal()}
      {renderTagModal()}
    </>
  );
}
