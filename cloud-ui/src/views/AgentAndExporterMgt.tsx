import React, { useState, useEffect } from 'react';
import { RefreshCw, Upload, Download, Search, Package, Server, ChevronRight, X, Save, Trash2, Star, Clock } from 'lucide-react';
import { cn, formatBytes, formatTimestamp } from '@/lib/utils';

interface AgentVersion {
  id?: number;
  version: string;
  downloadUrl?: string;
  packagePath: string;
  description?: string;
  fileSize?: number;
  fileHash?: string;
  isActive: number;
  isLatest: number;
  createTime?: number;
  updateTime?: number;
}

interface ExporterInfo {
  id?: number;
  exporterName: string;
  exporterVersion: string;
  serviceName: string;
  serviceType: string;
  packageName: string;
  packagePath: string;
  downloadUrl?: string;
  description?: string;
  configTemplate?: string;
  ports?: string;
  dependencies?: string;
  fileSize?: number;
  fileHash?: string;
  isActive: number;
  createTime?: number;
  updateTime?: number;
}

interface ConfigTemplate {
  id?: number;
  templateName: string;
  templateType: string;
  serviceName: string;
  configContent: string;
  description?: string;
  version: string;
  isDefault: number;
  createTime?: number;
  updateTime?: number;
}

const API_BASE = 'http://localhost:8080/api';

export default function AgentAndExporterMgt() {
  const [activeTab, setActiveTab] = useState<'agent' | 'exporter' | 'template'>('agent');
  const [agentVersions, setAgentVersions] = useState<AgentVersion[]>([]);
  const [exporters, setExporters] = useState<ExporterInfo[]>([]);
  const [templates, setTemplates] = useState<ConfigTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedExporter, setSelectedExporter] = useState<ExporterInfo | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [searchService, setSearchService] = useState('');
  const [editingItem, setEditingItem] = useState<any>(null);
  const [availableServices, setAvailableServices] = useState<string[]>([]);

  useEffect(() => {
    if (activeTab === 'agent') fetchAgentVersions();
    else if (activeTab === 'exporter') fetchExporters();
    else if (activeTab === 'template') fetchTemplates();
  }, [activeTab]);

  const fetchAgentVersions = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/agent/versions`);
      const data = await res.json();
      setAgentVersions(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const fetchExporters = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/exporter`);
      const data = await res.json();
      setExporters(data);
      
      const servicesRes = await fetch(`${API_BASE}/exporter/services`);
      const services = await servicesRes.json();
      setAvailableServices(services);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/config-template`);
      const data = await res.json();
      setTemplates(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const searchExportersByService = async (serviceName: string) => {
    if (!serviceName) {
      fetchExporters();
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/exporter/search?serviceName=${encodeURIComponent(serviceName)}`);
      const data = await res.json();
      setExporters(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const getExporterVersions = async (exporterName: string, serviceName: string) => {
    try {
      const res = await fetch(`${API_BASE}/exporter/versions?exporterName=${encodeURIComponent(exporterName)}&serviceName=${encodeURIComponent(serviceName)}`);
      return await res.json();
    } catch (e) {
      console.error(e);
      return [];
    }
  };

  const saveAgentVersion = async (version: AgentVersion) => {
    try {
      const method = version.id ? 'PUT' : 'POST';
      const url = version.id ? `${API_BASE}/agent/versions/${version.id}` : `${API_BASE}/agent/versions`;
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(version)
      });
      fetchAgentVersions();
      setShowAddModal(false);
      setEditingItem(null);
    } catch (e) {
      console.error(e);
    }
  };

  const saveExporter = async (exporter: ExporterInfo) => {
    try {
      const method = exporter.id ? 'PUT' : 'POST';
      const url = exporter.id ? `${API_BASE}/exporter/${exporter.id}` : `${API_BASE}/exporter`;
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(exporter)
      });
      fetchExporters();
      setShowAddModal(false);
      setEditingItem(null);
    } catch (e) {
      console.error(e);
    }
  };

  const saveTemplate = async (template: ConfigTemplate) => {
    try {
      const method = template.id ? 'PUT' : 'POST';
      const url = template.id ? `${API_BASE}/config-template/${template.id}` : `${API_BASE}/config-template`;
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(template)
      });
      fetchTemplates();
      setShowAddModal(false);
      setEditingItem(null);
    } catch (e) {
      console.error(e);
    }
  };

  const deleteItem = async (id: number, type: 'agent' | 'exporter' | 'template') => {
    if (!confirm('确定要删除吗？')) return;
    try {
      const url = type === 'agent' ? `${API_BASE}/agent/versions/${id}` 
                  : type === 'exporter' ? `${API_BASE}/exporter/${id}` 
                  : `${API_BASE}/config-template/${id}`;
      await fetch(url, { method: 'DELETE' });
      if (type === 'agent') fetchAgentVersions();
      else if (type === 'exporter') fetchExporters();
      else fetchTemplates();
    } catch (e) {
      console.error(e);
    }
  };

  const setLatestVersion = async (id: number) => {
    try {
      await fetch(`${API_BASE}/agent/versions/${id}/set-latest`, { method: 'POST' });
      fetchAgentVersions();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-white">Agent管理与插件市场</h2>
        <div className="flex space-x-2">
          <button
            onClick={() => {
              setEditingItem(null);
              setShowAddModal(true);
            }}
            className="px-4 py-2 bg-[#00ff9d]/10 text-[#00ff9d] rounded-lg text-sm hover:bg-[#00ff9d]/20 transition-all flex items-center"
          >
            <Upload className="w-4 h-4 mr-2" /> 新增
          </button>
        </div>
      </div>

      <div className="flex space-x-1 bg-white/5 p-1 rounded-lg w-fit">
        <button
          onClick={() => setActiveTab('agent')}
          className={cn(
            "px-4 py-2 rounded-md text-sm transition-all",
            activeTab === 'agent' ? "bg-[#00ff9d] text-black font-bold" : "text-slate-400 hover:text-white"
          )}
        >
          <Server className="w-4 h-4 inline mr-2" /> Agent管理
        </button>
        <button
          onClick={() => setActiveTab('exporter')}
          className={cn(
            "px-4 py-2 rounded-md text-sm transition-all",
            activeTab === 'exporter' ? "bg-[#00ff9d] text-black font-bold" : "text-slate-400 hover:text-white"
          )}
        >
          <Package className="w-4 h-4 inline mr-2" /> 插件市场
        </button>
        <button
          onClick={() => setActiveTab('template')}
          className={cn(
            "px-4 py-2 rounded-md text-sm transition-all",
            activeTab === 'template' ? "bg-[#00ff9d] text-black font-bold" : "text-slate-400 hover:text-white"
          )}
        >
          <Save className="w-4 h-4 inline mr-2" /> 配置模板库
        </button>
      </div>

      {activeTab === 'exporter' && (
        <div className="flex items-center space-x-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="搜索服务Exporter (如 HDFS, Kafka)"
              value={searchService}
              onChange={(e) => setSearchService(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && searchExportersByService(searchService)}
              className="w-full bg-[#020617] border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white text-sm"
            />
          </div>
          <select
            onChange={(e) => searchExportersByService(e.target.value)}
            className="bg-[#020617] border border-white/10 rounded-lg px-4 py-2 text-white text-sm"
            value={searchService}
          >
            <option value="">所有服务</option>
            {availableServices.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      )}

      <div className="glass-panel rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
            加载中...
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                {activeTab === 'agent' && (
                  <>
                    <th className="px-6 py-3">版本号</th>
                    <th className="px-6 py-3">包路径</th>
                    <th className="px-6 py-3">文件大小</th>
                    <th className="px-6 py-3">状态</th>
                    <th className="px-6 py-3">最新版本</th>
                    <th className="px-6 py-3">操作</th>
                  </>
                )}
                {activeTab === 'exporter' && (
                  <>
                    <th className="px-6 py-3">Exporter名称</th>
                    <th className="px-6 py-3">版本</th>
                    <th className="px-6 py-3">服务名称</th>
                    <th className="px-6 py-3">服务类型</th>
                    <th className="px-6 py-3">端口</th>
                    <th className="px-6 py-3">包名</th>
                    <th className="px-6 py-3">操作</th>
                  </>
                )}
                {activeTab === 'template' && (
                  <>
                    <th className="px-6 py-3">模板名称</th>
                    <th className="px-6 py-3">类型</th>
                    <th className="px-6 py-3">服务</th>
                    <th className="px-6 py-3">版本</th>
                    <th className="px-6 py-3">默认</th>
                    <th className="px-6 py-3">操作</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {activeTab === 'agent' && agentVersions.map(ver => (
                <tr key={ver.id} className="hover:bg-white/5">
                  <td className="px-6 py-4 font-mono text-[#00ff9d]">{ver.version}</td>
                  <td className="px-6 py-4 text-xs truncate max-w-[200px]">{ver.packagePath}</td>
                  <td className="px-6 py-4 text-xs">{ver.fileSize ? formatBytes(ver.fileSize) : '-'}</td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "px-2 py-0.5 rounded-full text-[10px]",
                      ver.isActive ? "bg-emerald-500/10 text-emerald-500" : "bg-slate-500/10 text-slate-500"
                    )}>
                      {ver.isActive ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {ver.isLatest === 1 && <Star className="w-4 h-4 text-amber-500" />}
                  </td>
                  <td className="px-6 py-4 space-x-2">
                    <button onClick={() => { setEditingItem(ver); setShowAddModal(true); }} className="text-[#38bdf8] hover:underline text-xs">编辑</button>
                    {ver.isLatest !== 1 && <button onClick={() => setLatestVersion(ver.id!)} className="text-amber-500 hover:underline text-xs">设为最新</button>}
                    <button onClick={() => deleteItem(ver.id!, 'agent')} className="text-rose-400 hover:underline text-xs">删除</button>
                  </td>
                </tr>
              ))}
              {activeTab === 'exporter' && exporters.map(exp => (
                <tr key={exp.id} className="hover:bg-white/5">
                  <td className="px-6 py-4 font-medium text-white">{exp.exporterName}</td>
                  <td className="px-6 py-4 font-mono text-[#a855f7]">{exp.exporterVersion}</td>
                  <td className="px-6 py-4">{exp.serviceName}</td>
                  <td className="px-6 py-4">{exp.serviceType}</td>
                  <td className="px-6 py-4 font-mono text-xs">{exp.ports || '-'}</td>
                  <td className="px-6 py-4 text-xs truncate max-w-[150px]">{exp.packageName}</td>
                  <td className="px-6 py-4 space-x-2">
                    <button onClick={() => { setSelectedExporter(exp); setShowDetailModal(true); }} className="text-[#38bdf8] hover:underline text-xs">详情</button>
                    <button onClick={() => { setEditingItem(exp); setShowAddModal(true); }} className="text-[#38bdf8] hover:underline text-xs">编辑</button>
                    <button onClick={() => deleteItem(exp.id!, 'exporter')} className="text-rose-400 hover:underline text-xs">删除</button>
                  </td>
                </tr>
              ))}
              {activeTab === 'template' && templates.map(tpl => (
                <tr key={tpl.id} className="hover:bg-white/5">
                  <td className="px-6 py-4 font-medium text-white">{tpl.templateName}</td>
                  <td className="px-6 py-4">{tpl.templateType}</td>
                  <td className="px-6 py-4">{tpl.serviceName}</td>
                  <td className="px-6 py-4 font-mono text-xs">{tpl.version}</td>
                  <td className="px-6 py-4">
                    {tpl.isDefault === 1 && <Star className="w-4 h-4 text-amber-500" />}
                  </td>
                  <td className="px-6 py-4 space-x-2">
                    <button onClick={() => { setEditingItem(tpl); setShowAddModal(true); }} className="text-[#38bdf8] hover:underline text-xs">编辑</button>
                    <button onClick={() => deleteItem(tpl.id!, 'template')} className="text-rose-400 hover:underline text-xs">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[500px] max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">
                {activeTab === 'agent' ? '新增Agent版本' : activeTab === 'exporter' ? '新增Exporter' : '新增配置模板'}
              </h3>
              <button onClick={() => { setShowAddModal(false); setEditingItem(null); }} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              {activeTab === 'agent' && (
                <>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">版本号 *</label>
                    <input type="text" value={editingItem?.version || ''} onChange={(e) => setEditingItem({ ...editingItem, version: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="1.0.0" />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">包路径 *</label>
                    <input type="text" value={editingItem?.packagePath || ''} onChange={(e) => setEditingItem({ ...editingItem, packagePath: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="/etc/cloud-agent/..." />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">下载URL</label>
                    <input type="text" value={editingItem?.downloadUrl || ''} onChange={(e) => setEditingItem({ ...editingItem, downloadUrl: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">描述</label>
                    <textarea value={editingItem?.description || ''} onChange={(e) => setEditingItem({ ...editingItem, description: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" rows={3} />
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" checked={editingItem?.isActive === 1} onChange={(e) => setEditingItem({ ...editingItem, isActive: e.target.checked ? 1 : 0 })} className="w-4 h-4" />
                    <span className="text-sm text-slate-400">启用</span>
                  </div>
                </>
              )}
              {activeTab === 'exporter' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">Exporter名称 *</label>
                      <input type="text" value={editingItem?.exporterName || ''} onChange={(e) => setEditingItem({ ...editingItem, exporterName: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="node_exporter" />
                    </div>
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">版本 *</label>
                      <input type="text" value={editingItem?.exporterVersion || ''} onChange={(e) => setEditingItem({ ...editingItem, exporterVersion: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="1.0.0" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">服务名称 *</label>
                      <input type="text" value={editingItem?.serviceName || ''} onChange={(e) => setEditingItem({ ...editingItem, serviceName: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="HDFS" />
                    </div>
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">服务类型 *</label>
                      <input type="text" value={editingItem?.serviceType || ''} onChange={(e) => setEditingItem({ ...editingItem, serviceType: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="HADOOP" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">包名 *</label>
                      <input type="text" value={editingItem?.packageName || ''} onChange={(e) => setEditingItem({ ...editingItem, packageName: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
                    </div>
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">端口</label>
                      <input type="text" value={editingItem?.ports || ''} onChange={(e) => setEditingItem({ ...editingItem, ports: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" placeholder="9100" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">包路径 *</label>
                    <input type="text" value={editingItem?.packagePath || ''} onChange={(e) => setEditingItem({ ...editingItem, packagePath: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">描述</label>
                    <textarea value={editingItem?.description || ''} onChange={(e) => setEditingItem({ ...editingItem, description: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" rows={3} />
                  </div>
                </>
              )}
              {activeTab === 'template' && (
                <>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">模板名称 *</label>
                    <input type="text" value={editingItem?.templateName || ''} onChange={(e) => setEditingItem({ ...editingItem, templateName: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">模板类型 *</label>
                      <select value={editingItem?.templateType || ''} onChange={(e) => setEditingItem({ ...editingItem, templateType: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm">
                        <option value="">选择类型</option>
                        <option value="JMX">JMX</option>
                        <option value="EXPORTER">EXPORTER</option>
                        <option value="PLUGIN">PLUGIN</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">版本</label>
                      <input type="text" value={editingItem?.version || '1.0.0'} onChange={(e) => setEditingItem({ ...editingItem, version: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">服务名称 *</label>
                    <input type="text" value={editingItem?.serviceName || ''} onChange={(e) => setEditingItem({ ...editingItem, serviceName: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">配置内容 *</label>
                    <textarea value={editingItem?.configContent || ''} onChange={(e) => setEditingItem({ ...editingItem, configContent: e.target.value })} className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm font-mono" rows={6} />
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" checked={editingItem?.isDefault === 1} onChange={(e) => setEditingItem({ ...editingItem, isDefault: e.target.checked ? 1 : 0 })} className="w-4 h-4" />
                    <span className="text-sm text-slate-400">设为默认模板</span>
                  </div>
                </>
              )}
            </div>
            <div className="mt-6 flex justify-end space-x-2">
              <button onClick={() => { setShowAddModal(false); setEditingItem(null); }} className="px-4 py-2 bg-white/5 text-slate-400 rounded-lg text-sm hover:bg-white/10">取消</button>
              <button 
                onClick={() => {
                  if (activeTab === 'agent') saveAgentVersion(editingItem);
                  else if (activeTab === 'exporter') saveExporter(editingItem);
                  else saveTemplate(editingItem);
                }} 
                className="px-4 py-2 bg-[#00ff9d] text-black rounded-lg text-sm font-bold hover:bg-[#00ff9d]/80"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {showDetailModal && selectedExporter && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[600px] max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">Exporter详情</h3>
              <button onClick={() => { setShowDetailModal(false); setSelectedExporter(null); }} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-slate-500">Exporter名称</div>
                  <div className="text-white font-medium">{selectedExporter.exporterName}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">版本号</div>
                  <div className="text-[#a855f7] font-mono">{selectedExporter.exporterVersion}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-slate-500">服务名称</div>
                  <div className="text-white">{selectedExporter.serviceName}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">服务类型</div>
                  <div className="text-white">{selectedExporter.serviceType}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-slate-500">包名</div>
                  <div className="text-white text-sm">{selectedExporter.packageName}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">端口</div>
                  <div className="text-white font-mono">{selectedExporter.ports || '-'}</div>
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">包路径</div>
                <div className="text-white text-sm font-mono">{selectedExporter.packagePath}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">描述</div>
                <div className="text-slate-300 text-sm">{selectedExporter.description || '-'}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
