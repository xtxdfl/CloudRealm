import React, { useState, useEffect } from 'react';
import { 
  Database, GitMerge, ShieldCheck, Search, FileJson, Layers, Plus, 
  Settings, Download, Upload, ArrowRight, AlertTriangle, CheckCircle, 
  XCircle, PieChart
} from 'lucide-react';
import { cn } from '@/lib/utils';

// --- Interfaces ---

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

interface QualityRule {
  id: number;
  ruleName: string;
  targetTable: string;
  type: 'Completeness' | 'Uniqueness' | 'Consistency' | 'Timeliness';
  status: 'Passed' | 'Failed' | 'Warning';
  lastRun: string;
}

// --- Main Component ---

export default function DataMart({ activeSubView }: { activeSubView?: string }) {
  // State
  const [assets, setAssets] = useState<DataAsset[]>([]);
  const [registries, setRegistries] = useState<Registry[]>([]);
  const [mpacks, setMpacks] = useState<Mpack[]>([]);
  const [stacks, setStacks] = useState<Stack[]>([]);
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [extensionLinks, setExtensionLinks] = useState<ExtensionLink[]>([]);
  const [stats, setStats] = useState<DataMartStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<DataAsset | null>(null);
  
  // Modal States
  const [showAddRegistry, setShowAddRegistry] = useState(false);
  const [showAddMpack, setShowAddMpack] = useState(false);
  const [showAddStack, setShowAddStack] = useState(false);
  const [showAddExtension, setShowAddExtension] = useState(false);
  
  // Form States
  const [newRegistry, setNewRegistry] = useState({ registryName: '', registryType: 'DOCKER', registryUri: '' });
  const [newMpack, setNewMpack] = useState({ mpackName: '', mpackVersion: '', mpackUri: '', registryId: 1 });
  const [newStack, setNewStack] = useState({ stackName: '', stackVersion: '', mpackId: 1 });
  const [newExtension, setNewExtension] = useState({ extensionName: '', extensionVersion: '' });

  // Quality Report State
  const [qualityRules, setQualityRules] = useState<QualityRule[]>([
    { id: 1, ruleName: 'Order ID Non-Null', targetTable: 'dw_sales.fact_orders', type: 'Completeness', status: 'Passed', lastRun: '2023-10-27 10:00' },
    { id: 2, ruleName: 'User ID Unique', targetTable: 'dim_users', type: 'Uniqueness', status: 'Passed', lastRun: '2023-10-27 09:30' },
    { id: 3, ruleName: 'Payment Amount Positive', targetTable: 'dw_sales.fact_orders', type: 'Consistency', status: 'Failed', lastRun: '2023-10-27 10:00' },
    { id: 4, ruleName: 'Daily Partition Exists', targetTable: 'ods_log.clickstream', type: 'Timeliness', status: 'Warning', lastRun: '2023-10-27 11:00' },
  ]);

  useEffect(() => {
    fetchDataMartData();
  }, []);

  const fetchDataMartData = async () => {
    try {
      // Mocking fetch for now or using real endpoints if available
      // In a real app, we would fetch from /api/datamart/*
      
      // Fallback Mock Data
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
      setStats({ managedTables: 2485, qualityScoreAvg: 94.2, storageUsagePb: 1.2, storageCapacityPercent: 65 });
    } catch (error) {
      console.error('Error fetching data mart data:', error);
    }
  };

  const handleAddRegistry = async () => {
    // Mock implementation
    const newId = registries.length + 1;
    setRegistries([...registries, { ...newRegistry, id: newId }]);
    setShowAddRegistry(false);
    setNewRegistry({ registryName: '', registryType: 'DOCKER', registryUri: '' });
  };

  const handleAddMpack = async () => {
    const newId = mpacks.length + 1;
    setMpacks([...mpacks, { ...newMpack, id: newId }]);
    setShowAddMpack(false);
    setNewMpack({ mpackName: '', mpackVersion: '', mpackUri: '', registryId: 1 });
  };

  const handleAddStack = async () => {
    const newId = stacks.length + 1;
    setStacks([...stacks, { ...newStack, stackId: newId }]);
    setShowAddStack(false);
    setNewStack({ stackName: '', stackVersion: '', mpackId: 1 });
  };

  const handleAddExtension = async () => {
    const newId = extensions.length + 1;
    setExtensions([...extensions, { ...newExtension, extensionId: newId }]);
    setShowAddExtension(false);
    setNewExtension({ extensionName: '', extensionVersion: '' });
  };

  const filteredAssets = assets.filter(asset =>
    asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    asset.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    asset.owner.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // --- Sub-Views ---

  const renderDataCatalog = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
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
              className="p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-all cursor-pointer group"
              onClick={() => setSelectedAsset(asset)}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold text-white group-hover:text-[#38bdf8] transition-colors">{asset.name}</h4>
                <span className="text-xs bg-[#38bdf8]/20 text-[#38bdf8] px-2 py-1 rounded">{asset.type}</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">{asset.description}</p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Owner: {asset.owner}</span>
                <div className="flex items-center">
                  <span className={cn(
                    "text-xs font-bold mr-2",
                    asset.qualityScore >= 90 ? "text-[#00ff9d]" : 
                    asset.qualityScore >= 80 ? "text-amber-500" : "text-rose-500"
                  )}>{asset.qualityScore}%</span>
                  <ArrowRight className="w-3 h-3 text-slate-500" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderLineageAnalysis = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <GitMerge className="w-5 h-5 mr-2 text-[#a855f7]" /> 数据血缘分析
          </h3>
          <div className="flex space-x-2">
             <button className="px-3 py-1.5 bg-white/5 rounded-lg text-xs text-slate-300 hover:text-white">导出图片</button>
             <button className="px-3 py-1.5 bg-white/5 rounded-lg text-xs text-slate-300 hover:text-white">全屏模式</button>
          </div>
        </div>
        <div className="bg-[#020617] rounded-xl border border-white/5 p-8 min-h-[600px] relative overflow-hidden flex items-center justify-center">
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
          
          {selectedAsset ? (
            <div className="relative z-10 w-full max-w-4xl">
              <div className="flex items-center justify-between mb-12">
                 {/* Upstream */}
                 <div className="flex flex-col items-center">
                    <div className="w-48 p-4 bg-slate-800/80 border border-slate-700 rounded-lg text-center mb-4">
                      <div className="text-xs text-slate-400 mb-1">Upstream Source</div>
                      <div className="font-bold text-white">{selectedAsset.lineageUpstream}</div>
                    </div>
                    <div className="h-12 w-0.5 bg-slate-700"></div>
                    <ArrowRight className="w-6 h-6 text-slate-500 rotate-90" />
                 </div>
                 
                 {/* Center Asset */}
                 <div className="transform scale-110">
                    <div className="w-64 p-6 bg-[#a855f7]/10 border border-[#a855f7] rounded-xl text-center shadow-[0_0_30px_rgba(168,85,247,0.2)]">
                      <Database className="w-8 h-8 text-[#a855f7] mx-auto mb-3" />
                      <div className="font-bold text-white text-lg mb-1">{selectedAsset.name}</div>
                      <div className="text-xs text-[#a855f7]">{selectedAsset.type}</div>
                    </div>
                 </div>

                 {/* Downstream */}
                 <div className="flex flex-col items-center">
                    <ArrowRight className="w-6 h-6 text-slate-500 rotate-90 mb-4" />
                    <div className="h-12 w-0.5 bg-slate-700 mb-4"></div>
                    <div className="w-48 p-4 bg-slate-800/80 border border-slate-700 rounded-lg text-center">
                      <div className="text-xs text-slate-400 mb-1">Downstream Target</div>
                      <div className="font-bold text-white">{selectedAsset.lineageDownstream}</div>
                    </div>
                 </div>
              </div>
              
              <div className="text-center mt-8">
                 <p className="text-slate-400 text-sm">点击节点查看详细元数据信息</p>
                 <button 
                   onClick={() => setSelectedAsset(null)}
                   className="mt-4 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-slate-400 hover:text-white"
                 >
                   重置视图
                 </button>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <GitMerge className="w-20 h-20 text-slate-800 mx-auto mb-4" />
              <h3 className="text-xl font-bold text-slate-600">选择资产以查看血缘</h3>
              <p className="text-slate-500 mt-2">请从“数据目录”中选择一个表或流数据</p>
              <button 
                 onClick={() => {
                   // Ideally switch tab, but here just a hint
                   alert("请切换到‘数据目录’页签选择资产");
                 }}
                 className="mt-6 px-6 py-2 bg-[#a855f7] text-white rounded-lg hover:bg-[#9333ea] transition-colors"
              >
                去选择资产
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderQualityReport = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
       {/* Quality Overview */}
       <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between">
             <div>
                <div className="text-slate-500 text-xs font-bold uppercase mb-1">Avg Quality Score</div>
                <div className="text-3xl font-bold text-[#00ff9d]">{stats?.qualityScoreAvg || 0}</div>
             </div>
             <PieChart className="w-12 h-12 text-[#00ff9d]/20" />
          </div>
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between">
             <div>
                <div className="text-slate-500 text-xs font-bold uppercase mb-1">Rules Executed</div>
                <div className="text-3xl font-bold text-white">1,248</div>
             </div>
             <CheckCircle className="w-12 h-12 text-[#38bdf8]/20" />
          </div>
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between">
             <div>
                <div className="text-slate-500 text-xs font-bold uppercase mb-1">Critical Issues</div>
                <div className="text-3xl font-bold text-rose-500">3</div>
             </div>
             <AlertTriangle className="w-12 h-12 text-rose-500/20" />
          </div>
       </div>

       {/* Quality Rules List */}
       <div className="glass-panel p-6 rounded-2xl">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center">
             <ShieldCheck className="w-5 h-5 mr-2 text-[#00ff9d]" /> 质量规则执行报告
          </h3>
          <div className="overflow-x-auto">
             <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-500 uppercase bg-white/5">
                   <tr>
                      <th className="px-4 py-3 rounded-l-lg">Rule Name</th>
                      <th className="px-4 py-3">Target Table</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3 rounded-r-lg">Last Run</th>
                   </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                   {qualityRules.map(rule => (
                      <tr key={rule.id} className="hover:bg-white/5 transition-colors">
                         <td className="px-4 py-3 font-medium text-white">{rule.ruleName}</td>
                         <td className="px-4 py-3 text-slate-400">{rule.targetTable}</td>
                         <td className="px-4 py-3">
                            <span className="px-2 py-1 rounded text-[10px] bg-white/10 text-slate-300 border border-white/10">
                               {rule.type}
                            </span>
                         </td>
                         <td className="px-4 py-3">
                            <span className={cn(
                               "flex items-center text-xs font-bold",
                               rule.status === 'Passed' ? "text-[#00ff9d]" :
                               rule.status === 'Failed' ? "text-rose-500" : "text-amber-500"
                            )}>
                               {rule.status === 'Passed' && <CheckCircle className="w-3 h-3 mr-1" />}
                               {rule.status === 'Failed' && <XCircle className="w-3 h-3 mr-1" />}
                               {rule.status === 'Warning' && <AlertTriangle className="w-3 h-3 mr-1" />}
                               {rule.status}
                            </span>
                         </td>
                         <td className="px-4 py-3 text-slate-500 font-mono text-xs">{rule.lastRun}</td>
                      </tr>
                   ))}
                </tbody>
             </table>
          </div>
       </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
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
    </div>
  );

  return (
    <>
      {activeSubView === '数据目录' && renderDataCatalog()}
      {activeSubView === '血缘分析' && renderLineageAnalysis()}
      {activeSubView === '质量报告' && renderQualityReport()}
      {(!activeSubView || activeSubView === '') && renderOverview()}

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
    </>
  );
}
