import React, { useState, useEffect } from 'react';
import { Database, GitMerge, ShieldCheck, Search, FileJson, Layers, Plus, Settings, Download, Upload, ArrowRight } from 'lucide-react';

interface DataAsset {
  name: string;
  type: string;
  owner: string;
  qualityScore: number;
  description: string;
  lineageUpstream: string;
  lineageDownstream: string;
}

interface Registry {
  id: number;
  registryName: string;
  registryType: string;
  registryUri: string;
}

interface Mpack {
  id: number;
  mpackName: string;
  mpackVersion: string;
  mpackUri: string;
  registryId: number;
}

interface Stack {
  stackId: number;
  stackName: string;
  stackVersion: string;
  mpackId: number;
}

interface Extension {
  extensionId: number;
  extensionName: string;
  extensionVersion: string;
}

interface ExtensionLink {
  linkId: number;
  stackId: number;
  extensionId: number;
}

interface DataMartStats {
  managedTables: number;
  qualityScoreAvg: number;
  storageUsagePb: number;
  storageCapacityPercent: number;
}

export default function DataMart() {
  const [assets, setAssets] = useState<DataAsset[]>([]);
  const [registries, setRegistries] = useState<Registry[]>([]);
  const [mpacks, setMpacks] = useState<Mpack[]>([]);
  const [stacks, setStacks] = useState<Stack[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [extensionLinks, setExtensionLinks] = useState<ExtensionLink[]>([]);
  const [stats, setStats] = useState<DataMartStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<DataAsset | null>(null);
  const [showAddRegistry, setShowAddRegistry] = useState(false);
  const [showAddMpack, setShowAddMpack] = useState(false);
  const [showAddStack, setShowAddStack] = useState(false);
  const [showAddExtension, setShowAddExtension] = useState(false);
  const [newRegistry, setNewRegistry] = useState({ registryName: '', registryType: 'DOCKER', registryUri: '' });
  const [newMpack, setNewMpack] = useState({ mpackName: '', mpackVersion: '', mpackUri: '', registryId: 1 });
  const [newStack, setNewStack] = useState({ stackName: '', stackVersion: '', mpackId: 1 });
  const [newExtension, setNewExtension] = useState({ extensionName: '', extensionVersion: '' });

  useEffect(() => {
    fetchDataMartData();
  }, []);

  const fetchDataMartData = async () => {
    try {
      const [assetsRes, registriesRes, mpacksRes, stacksRes, extensionsRes, extensionLinksRes, statsRes] = await Promise.all([
        fetch('/api/datamart/assets').then(res => res.json()),
        fetch('/api/datamart/registries').then(res => res.json()),
        fetch('/api/datamart/mpacks').then(res => res.json()),
        fetch('/api/datamart/stacks').then(res => res.json()),
        fetch('/api/datamart/extensions').then(res => res.json()),
        fetch('/api/datamart/extension-links').then(res => res.json()),
        fetch('/api/datamart/stats').then(res => res.json())
      ]);
      setAssets(assetsRes);
      setRegistries(registriesRes);
      setMpacks(mpacksRes);
      setStacks(stacksRes);
      setExtensions(extensionsRes);
      setExtensionLinks(extensionLinksRes);
      setStats(statsRes);
    } catch (error) {
      console.error('Error fetching data mart data:', error);
      // Fallback to mock data
      setAssets([
        { name: 'dw_sales.fact_orders', type: 'HIVE', owner: 'DataTeam', qualityScore: 98.5, description: 'Daily sales transactions fact table', lineageUpstream: 'ods.orders_log', lineageDownstream: 'dm_sales.daily_report' },
        { name: 'ods_log.clickstream', type: 'KAFKA', owner: 'AppTeam', qualityScore: 100.0, description: 'Real-time user click events', lineageUpstream: 'app_server', lineageDownstream: 'dw_log.user_behavior' },
        { name: 'dim_users', type: 'HBASE', owner: 'UserCenter', qualityScore: 92.0, description: 'User profile dimension table', lineageUpstream: 'crm_db.users', lineageDownstream: 'dw_sales.fact_orders' }
      ]);
      setRegistries([
        { id: 1, registryName: 'Docker Hub', registryType: 'DOCKER', registryUri: 'https://hub.docker.com' },
        { id: 2, registryName: 'Maven Central', registryType: 'MAVEN', registryUri: 'https://repo.maven.apache.org' }
      ]);
      setMpacks([
        { id: 1, mpackName: 'HDP', mpackVersion: '3.1.0', mpackUri: 'https://example.com/hdp-3.1.0.tar.gz', registryId: 1 },
        { id: 2, mpackName: 'CDH', mpackVersion: '6.3.2', mpackUri: 'https://example.com/cdh-6.3.2.tar.gz', registryId: 1 }
      ]);
      setStacks([
        { stackId: 1, stackName: 'HDP', stackVersion: '3.1.0', mpackId: 1 },
        { stackId: 2, stackName: 'CDH', stackVersion: '6.3.2', mpackId: 2 }
      ]);
      setExtensions([
        { extensionId: 1, extensionName: 'Hive-JDBC', extensionVersion: '2.3.8' },
        { extensionId: 2, extensionName: 'Spark-YARN', extensionVersion: '3.5.0' }
      ]);
      setExtensionLinks([
        { linkId: 1, stackId: 1, extensionId: 1 },
        { linkId: 2, stackId: 1, extensionId: 2 }
      ]);
      setStats({ managedTables: 2485, qualityScoreAvg: 94.2, storageUsagePb: 1.2, storageCapacityPercent: 65 });
    }
  };

  const handleAddRegistry = async () => {
    try {
      const response = await fetch('/api/datamart/registries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRegistry)
      });
      if (response.ok) {
        fetchDataMartData();
        setShowAddRegistry(false);
        setNewRegistry({ registryName: '', registryType: 'DOCKER', registryUri: '' });
      }
    } catch (error) {
      console.error('Error adding registry:', error);
    }
  };

  const handleAddMpack = async () => {
    try {
      const response = await fetch('/api/datamart/mpacks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newMpack)
      });
      if (response.ok) {
        fetchDataMartData();
        setShowAddMpack(false);
        setNewMpack({ mpackName: '', mpackVersion: '', mpackUri: '', registryId: 1 });
      }
    } catch (error) {
      console.error('Error adding mpack:', error);
    }
  };

  const handleAddStack = async () => {
    try {
      const response = await fetch('/api/datamart/stacks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newStack)
      });
      if (response.ok) {
        fetchDataMartData();
        setShowAddStack(false);
        setNewStack({ stackName: '', stackVersion: '', mpackId: 1 });
      }
    } catch (error) {
      console.error('Error adding stack:', error);
    }
  };

  const handleAddExtension = async () => {
    try {
      const response = await fetch('/api/datamart/extensions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newExtension)
      });
      if (response.ok) {
        fetchDataMartData();
        setShowAddExtension(false);
        setNewExtension({ extensionName: '', extensionVersion: '' });
      }
    } catch (error) {
      console.error('Error adding extension:', error);
    }
  };

  const filteredAssets = assets.filter(asset =>
    asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    asset.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    asset.owner.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* 1. Data Governance Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
          <div className="relative z-10">
            <div className="text-slate-500 text-xs font-bold uppercase mb-1">Managed Tables</div>
            <div className="text-3xl font-bold text-white">{stats?.managedTables || 0}</div>
            <div className="text-[10px] text-[#00ff9d] mt-2 flex items-center">+124 this week</div>
          </div>
          <Database className="w-16 h-16 text-[#38bdf8]/10 absolute right-4 top-1/2 -translate-y-1/2" />
        </div>
        <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
          <div className="relative z-10">
            <div className="text-slate-500 text-xs font-bold uppercase mb-1">Data Quality Score</div>
            <div className="text-3xl font-bold text-white">{stats?.qualityScoreAvg?.toFixed(1) || 0}</div>
            <div className="text-[10px] text-amber-500 mt-2 flex items-center">3 critical issues</div>
          </div>
          <ShieldCheck className="w-16 h-16 text-[#00ff9d]/10 absolute right-4 top-1/2 -translate-y-1/2" />
        </div>
        <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
          <div className="relative z-10">
            <div className="text-slate-500 text-xs font-bold uppercase mb-1">Storage Usage</div>
            <div className="text-3xl font-bold text-white">{stats?.storageUsagePb || 0} PB</div>
            <div className="text-[10px] text-slate-400 mt-2 flex items-center">{stats?.storageCapacityPercent || 0}% Capacity</div>
          </div>
          <FileJson className="w-16 h-16 text-purple-500/10 absolute right-4 top-1/2 -translate-y-1/2" />
        </div>
        <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
          <div className="relative z-10">
            <div className="text-slate-500 text-xs font-bold uppercase mb-1">Registries</div>
            <div className="text-3xl font-bold text-white">{registries.length}</div>
            <div className="text-[10px] text-[#38bdf8] mt-2 flex items-center">{mpacks.length} mpacks</div>
          </div>
          <Layers className="w-16 h-16 text-[#38bdf8]/10 absolute right-4 top-1/2 -translate-y-1/2" />
        </div>
      </div>

      {/* 2. Registry Management */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Database className="w-5 h-5 mr-2 text-[#38bdf8]" /> 注册中心管理
          </h3>
          <button
            onClick={() => setShowAddRegistry(true)}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加注册中心
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {registries.map(registry => (
            <div key={registry.id} className="p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-all">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold text-white">{registry.registryName}</h4>
                <span className="text-xs bg-[#38bdf8]/20 text-[#38bdf8] px-2 py-1 rounded">{registry.registryType}</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">{registry.registryUri}</p>
              <div className="flex space-x-2">
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Settings className="w-4 h-4" />
                </button>
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Mpack Management */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <FileJson className="w-5 h-5 mr-2 text-[#a855f7]" /> 元数据包管理
          </h3>
          <button
            onClick={() => setShowAddMpack(true)}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加元数据包
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {mpacks.map(mpack => (
            <div key={mpack.id} className="p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-all">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold text-white">{mpack.mpackName}</h4>
                <span className="text-xs bg-[#a855f7]/20 text-[#a855f7] px-2 py-1 rounded">{mpack.mpackVersion}</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">{mpack.mpackUri}</p>
              <div className="flex space-x-2">
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Settings className="w-4 h-4" />
                </button>
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Download className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Stack Management */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <GitMerge className="w-5 h-5 mr-2 text-[#00ff9d]" /> 技术栈管理
          </h3>
          <button
            onClick={() => setShowAddStack(true)}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加技术栈
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {stacks.map(stack => (
            <div key={stack.stackId} className="p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-all">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold text-white">{stack.stackName}</h4>
                <span className="text-xs bg-[#00ff9d]/20 text-[#00ff9d] px-2 py-1 rounded">{stack.stackVersion}</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">Mpack ID: {stack.mpackId}</p>
              <div className="flex space-x-2">
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Settings className="w-4 h-4" />
                </button>
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <GitMerge className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Extension Management */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <ShieldCheck className="w-5 h-5 mr-2 text-amber-500" /> 扩展包管理
          </h3>
          <button
            onClick={() => setShowAddExtension(true)}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加扩展包
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {extensions.map(extension => (
            <div key={extension.extensionId} className="p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-all">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold text-white">{extension.extensionName}</h4>
                <span className="text-xs bg-amber-500/20 text-amber-500 px-2 py-1 rounded">{extension.extensionVersion}</span>
              </div>
              <div className="flex space-x-2">
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Settings className="w-4 h-4" />
                </button>
                <button className="p-2 bg-white/5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                  <Upload className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 6. Data Asset Catalog */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Database className="w-5 h-5 mr-2 text-[#38bdf8]" /> 数据资产目录
          </h3>
          <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
            <Search className="w-4 h-4 text-slate-500 mr-2" />
            <input 
              type="text" 
              placeholder="Search tables, columns..." 
              className="bg-transparent border-none text-xs text-white focus:ring-0 w-full"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAssets.map(asset => (
            <div 
              key={asset.name} 
              className="p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-all cursor-pointer"
              onClick={() => setSelectedAsset(asset)}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold text-white">{asset.name}</h4>
                <span className="text-xs bg-[#38bdf8]/20 text-[#38bdf8] px-2 py-1 rounded">{asset.type}</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">{asset.description}</p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Owner: {asset.owner}</span>
                <div className="flex items-center">
                  <span className="text-xs text-[#00ff9d] mr-2">{asset.qualityScore}%</span>
                  <ArrowRight className="w-3 h-3 text-slate-500" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 7. Data Lineage Visualization */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <GitMerge className="w-5 h-5 mr-2 text-[#a855f7]" /> 数据血缘可视化
          </h3>
          <button className="px-4 py-2 bg-[#38bdf8]/10 text-[#38bdf8] rounded-lg text-sm font-bold hover:bg-[#38bdf8]/20 flex items-center">
            <GitMerge className="w-4 h-4 mr-2" /> 全屏查看
          </button>
        </div>
        <div className="bg-[#020617] rounded-xl border border-white/5 p-4 min-h-[400px] relative overflow-hidden">
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
          <div className="relative z-10">
            {selectedAsset ? (
              <div className="space-y-4">
                <div className="text-center">
                  <h4 className="text-lg font-bold text-white mb-2">{selectedAsset.name}</h4>
                  <p className="text-sm text-slate-400">{selectedAsset.description}</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-white/5 rounded-lg">
                    <h5 className="text-sm font-bold text-white mb-2">上游依赖</h5>
                    <p className="text-xs text-slate-400">{selectedAsset.lineageUpstream}</p>
                  </div>
                  <div className="p-4 bg-white/5 rounded-lg">
                    <h5 className="text-sm font-bold text-white mb-2">下游影响</h5>
                    <p className="text-xs text-slate-400">{selectedAsset.lineageDownstream}</p>
                  </div>
                </div>
                <div className="text-center">
                  <button 
                    onClick={() => setSelectedAsset(null)}
                    className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-400 hover:text-white hover:border-white/20"
                  >
                    清除选择
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full">
                <GitMerge className="w-16 h-16 text-slate-700 mb-4" />
                <div className="text-sm text-slate-500 font-bold mb-2">数据血缘图</div>
                <div className="text-[10px] text-slate-600">选择一个数据资产查看其血缘关系</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add Registry Modal */}
      {showAddRegistry && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-4">添加注册中心</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-2">名称</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newRegistry.registryName}
                  onChange={(e) => setNewRegistry({...newRegistry, registryName: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">类型</label>
                <select
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newRegistry.registryType}
                  onChange={(e) => setNewRegistry({...newRegistry, registryType: e.target.value})}
                >
                  <option value="DOCKER">DOCKER</option>
                  <option value="MAVEN">MAVEN</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">URI</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newRegistry.registryUri}
                  onChange={(e) => setNewRegistry({...newRegistry, registryUri: e.target.value})}
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowAddRegistry(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-400 hover:text-white"
              >
                取消
              </button>
              <button
                onClick={handleAddRegistry}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e]"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Mpack Modal */}
      {showAddMpack && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-4">添加元数据包</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-2">名称</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newMpack.mpackName}
                  onChange={(e) => setNewMpack({...newMpack, mpackName: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">版本</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newMpack.mpackVersion}
                  onChange={(e) => setNewMpack({...newMpack, mpackVersion: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">URI</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newMpack.mpackUri}
                  onChange={(e) => setNewMpack({...newMpack, mpackUri: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">注册中心</label>
                <select
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newMpack.registryId}
                  onChange={(e) => setNewMpack({...newMpack, registryId: parseInt(e.target.value)})}
                >
                  {registries.map(registry => (
                    <option key={registry.id} value={registry.id}>{registry.registryName}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowAddMpack(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-400 hover:text-white"
              >
                取消
              </button>
              <button
                onClick={handleAddMpack}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e]"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Stack Modal */}
      {showAddStack && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-4">添加技术栈</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-2">名称</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newStack.stackName}
                  onChange={(e) => setNewStack({...newStack, stackName: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">版本</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newStack.stackVersion}
                  onChange={(e) => setNewStack({...newStack, stackVersion: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">元数据包</label>
                <select
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newStack.mpackId}
                  onChange={(e) => setNewStack({...newStack, mpackId: parseInt(e.target.value)})}
                >
                  {mpacks.map(mpack => (
                    <option key={mpack.id} value={mpack.id}>{mpack.mpackName}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowAddStack(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-400 hover:text-white"
              >
                取消
              </button>
              <button
                onClick={handleAddStack}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e]"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Extension Modal */}
      {showAddExtension && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
            <h3 className="text-lg font-bold text-white mb-4">添加扩展包</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-2">名称</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newExtension.extensionName}
                  onChange={(e) => setNewExtension({...newExtension, extensionName: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-2">版本</label>
                <input
                  type="text"
                  className="w-full p-3 bg-[#020617] border border-white/10 rounded-lg text-white text-sm"
                  value={newExtension.extensionVersion}
                  onChange={(e) => setNewExtension({...newExtension, extensionVersion: e.target.value})}
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowAddExtension(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-400 hover:text-white"
              >
                取消
              </button>
              <button
                onClick={handleAddExtension}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e]"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
