import React, { useState, useEffect } from 'react';
import { Layers, Play, Settings, GitBranch, Share2, Box, RotateCcw, Power, Plus, Save, FileText, CheckCircle, ChevronRight, Server, RotateCw, GitCommit, ArrowRight, X, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ServiceInfo {
  name: string;
  version: string;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL' | 'STOPPED' | 'UNKNOWN';
  configVersion: string;
  role: string;
  components: string[];
  lastOperationTime?: number;
  lastOperation?: string;
}

function DependencyView({ services, dependencies, selectedService, onSelectService }: { 
  services: ServiceInfo[]; 
  dependencies: { services: any[]; links: any[] };
  selectedService: string;
  onSelectService: (name: string) => void;
}) {
  const serviceNames = services.map(s => s.name);
  
  const allDeps = [
    { source: 'YARN', target: 'HDFS', type: 'Storage' },
    { source: 'YARN', target: 'ZOOKEEPER', type: 'Coordination' },
    { source: 'HIVE', target: 'HDFS', type: 'Storage' },
    { source: 'HIVE', target: 'YARN', type: 'Compute' },
    { source: 'HIVE', target: 'ZOOKEEPER', type: 'Coordination' },
    { source: 'HIVE', target: 'SPARK', type: 'Processing' },
    { source: 'SPARK', target: 'HDFS', type: 'Storage' },
    { source: 'SPARK', target: 'YARN', type: 'Compute' },
    { source: 'SPARK', target: 'ZOOKEEPER', type: 'Coordination' },
    { source: 'KAFKA', target: 'ZOOKEEPER', type: 'Coordination' },
    { source: 'HBASE', target: 'HDFS', type: 'Storage' },
    { source: 'HBASE', target: 'ZOOKEEPER', type: 'Coordination' },
    { source: 'FLINK', target: 'HDFS', type: 'Storage' },
    { source: 'FLINK', target: 'YARN', type: 'Compute' },
    { source: 'FLINK', target: 'ZOOKEEPER', type: 'Coordination' },
  ];
  
  const filteredDeps = selectedService 
    ? allDeps.filter(d => d.source === selectedService || d.target === selectedService)
    : allDeps.filter(d => serviceNames.includes(d.source) || serviceNames.includes(d.target));
  
  const getServiceLayer = (name: string) => {
    const upperName = name.toUpperCase();
    if (['ZOOKEEPER', 'HDFS', 'YARN'].includes(upperName)) return 'core';
    if (['HBASE', 'KAFKA', 'SPARK'].includes(upperName)) return 'processing';
    if (['HIVE', 'FLINK'].includes(upperName)) return 'application';
    return 'other';
  };

  const coreServices = ['ZOOKEEPER', 'HDFS', 'YARN'].filter(s => 
    selectedService === '' || s === selectedService.toUpperCase() || filteredDeps.some(d => d.source === s || d.target === s)
  );
  const processingServices = ['HBASE', 'KAFKA', 'SPARK'].filter(s => 
    selectedService === '' || s === selectedService.toUpperCase() || filteredDeps.some(d => d.source === s || d.target === s)
  );
  const appServices = ['HIVE', 'FLINK'].filter(s => 
    selectedService === '' || s === selectedService.toUpperCase() || filteredDeps.some(d => d.source === s || d.target === s)
  );

  return (
    <div className="glass-panel p-6 rounded-2xl animate-in fade-in duration-500">
       <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
             <Share2 className="w-5 h-5 mr-2 text-[#a855f7]" /> 服务依赖拓扑
          </h3>
          <div className="flex items-center space-x-3">
            <select 
              value={selectedService}
              onChange={(e) => onSelectService(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:border-[#a855f7] focus:outline-none"
            >
              <option value="">全部服务</option>
              {services.map(svc => (
                <option key={svc.name} value={svc.name}>{svc.name}</option>
              ))}
            </select>
            <button className="px-3 py-1.5 bg-white/5 rounded-lg text-xs text-slate-300 hover:text-white">刷新</button>
          </div>
       </div>
       
       <div className="bg-[#020617] rounded-xl border border-white/5 p-8 min-h-[400px] relative overflow-hidden flex items-center justify-center">
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
          
          <div className="relative z-10 w-full max-w-4xl grid grid-cols-3 gap-8">
             <div className="space-y-4">
                <div className="text-xs font-bold text-slate-500 uppercase text-center mb-2">核心基础设施</div>
                {coreServices.map(svc => (
                   <div 
                    key={svc} 
                    onClick={() => onSelectService(svc)}
                    className={`p-4 bg-slate-800 border rounded-lg text-center shadow-lg relative cursor-pointer transition-all hover:scale-105 ${
                      selectedService === svc.toLowerCase() ? 'border-[#a855f7] ring-2 ring-[#a855f7]/30' : 'border-slate-700'
                    }`}>
                      <div className="font-bold text-white">{svc}</div>
                      <div className="text-xs text-slate-400">Foundation</div>
                      <div className="absolute top-1/2 -right-2 w-4 h-0.5 bg-slate-600"></div>
                   </div>
                ))}
                {coreServices.length === 0 && <div className="text-slate-600 text-center text-sm">无服务</div>}
             </div>

             <div className="space-y-12 py-8">
                <div className="text-xs font-bold text-slate-500 uppercase text-center mb-2">处理引擎</div>
                {processingServices.map(svc => (
                   <div 
                    key={svc} 
                    onClick={() => onSelectService(svc)}
                    className={`p-4 bg-[#38bdf8]/10 border rounded-lg text-center shadow-lg relative cursor-pointer transition-all hover:scale-105 ${
                      selectedService === svc.toLowerCase() ? 'border-[#a855f7] ring-2 ring-[#a855f7]/30' : 'border-[#38bdf8]/30'
                    }`}>
                      <div className="absolute top-1/2 -left-4 w-4 h-0.5 bg-slate-600"></div>
                      <div className="font-bold text-white">{svc}</div>
                      <div className="text-xs text-[#38bdf8]">Processing</div>
                      <div className="absolute top-1/2 -right-4 w-4 h-0.5 bg-slate-600"></div>
                   </div>
                ))}
                {processingServices.length === 0 && <div className="text-slate-600 text-center text-sm">无服务</div>}
             </div>

             <div className="space-y-24 py-16">
                <div className="text-xs font-bold text-slate-500 uppercase text-center mb-2">应用层</div>
                {appServices.map(svc => (
                   <div 
                    key={svc} 
                    onClick={() => onSelectService(svc)}
                    className={`p-4 bg-[#a855f7]/10 border rounded-lg text-center shadow-lg relative cursor-pointer transition-all hover:scale-105 ${
                      selectedService === svc.toLowerCase() ? 'border-[#a855f7] ring-2 ring-[#a855f7]/30' : 'border-[#a855f7]/30'
                    }`}>
                      <div className="absolute top-1/2 -left-4 w-4 h-0.5 bg-slate-600"></div>
                      <div className="font-bold text-white">{svc}</div>
                      <div className="text-xs text-[#a855f7]">Application</div>
                   </div>
                ))}
                {appServices.length === 0 && <div className="text-slate-600 text-center text-sm">无服务</div>}
             </div>
          </div>
       </div>
       
       <div className="mt-6">
          <h4 className="font-bold text-white mb-3 text-sm">依赖详情 {selectedService && `- ${selectedService}`}</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
             {filteredDeps.map((dep: any, i: number) => (
                <div key={i} className="flex items-center p-3 bg-white/5 rounded-lg border border-white/5">
                   <span className="font-bold text-white">{dep.source}</span>
                   <div className="flex-1 mx-2 h-px bg-slate-600 relative">
                      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] bg-[#020617] px-1 text-slate-500">{dep.type}</span>
                   </div>
                   <ArrowRightIcon className="w-3 h-3 text-slate-500 mr-1" />
                   <span className="font-bold text-slate-300">{dep.target}</span>
                </div>
             ))}
             {filteredDeps.length === 0 && <div className="text-slate-500 text-sm">暂无依赖关系</div>}
          </div>
       </div>
    </div>
  );
}

function ArrowRightIcon(props: React.SVGProps<SVGSVGElement>) {
   return (
      <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
   )
}

interface ServiceStats {
  total: number;
  healthy: number;
  warning: number;
  stopped: number;
}

interface ServiceMgtProps {
  activeSubView?: string;
}

export default function ServiceMgt({ activeSubView }: ServiceMgtProps) {
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [stats, setStats] = useState<ServiceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentTab, setCurrentTab] = useState<string>(activeSubView || '服务列表');
  const [deleteModal, setDeleteModal] = useState<{
    show: boolean; 
    serviceName: string; 
    inputName: string;
    dependsOn: string[];
    dependentBy: string[];
  }>({show: false, serviceName: '', inputName: '', dependsOn: [], dependentBy: []});
  const [deleteError, setDeleteError] = useState<string>('');
  const [dependencies, setDependencies] = useState<{services: any[]; links: any[]}>({services: [], links: []});
  const [selectedService, setSelectedService] = useState<string>('');
  const [showDependencyModal, setShowDependencyModal] = useState<boolean>(false);
  const [dependencyModalService, setDependencyModalService] = useState<string>('');

  useEffect(() => {
    if (activeSubView) {
      setCurrentTab(activeSubView);
    }
  }, [activeSubView]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [servicesRes, statsRes, depsRes] = await Promise.all([
        fetch('/api/services'),
        fetch('/api/services/stats'),
        fetch('/api/services/dependencies')
      ]);
      
      if (servicesRes.ok) {
        const servicesData = await servicesRes.json();
        setServices(servicesData.map((s: any) => ({
          name: s.serviceName || s.name,
          version: s.version,
          status: s.status,
          configVersion: s.configVersion || 'v1',
          role: s.serviceType || s.serviceType,
          components: s.components || [],
          lastOperationTime: s.lastOperationTime,
          lastOperation: s.lastOperation
        })));
      }
      
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (depsRes.ok) {
        const depsData = await depsRes.json();
        setDependencies({services: depsData.services || [], links: depsData.links || []});
      } else {
        setDependencies({services: [], links: []});
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching service data:', error);
      setServices([]);
      setStats(null);
      setDependencies({services: [], links: []});
      setLoading(false);
    }
  };

  const handleAction = async (serviceName: string, action: 'start' | 'stop' | 'restart') => {
    try {
      const response = await fetch(`/api/services/${serviceName}/${action}`, { method: 'POST' });
      if (response.ok) {
        fetchData();
      }
    } catch (error) {
      console.error(`Error performing ${action} on ${serviceName}:`, error);
    }
  };

  const handleCheckDependencies = async (serviceName: string): Promise<{canDelete: boolean; dependsOn: string[]; dependentBy: string[]}> => {
    try {
      const response = await fetch(`/api/services/${serviceName}/dependencies/detail`);
      if (response.ok) {
        const data = await response.json();
        return { 
          canDelete: data.dependentCount === 0, 
          dependsOn: data.dependsOn || [],
          dependentBy: data.dependentList || []
        };
      }
      return { canDelete: true, dependsOn: [], dependentBy: [] };
    } catch (error) {
      console.error('Error checking dependencies:', error);
      return { canDelete: true, dependsOn: [], dependentBy: [] };
    }
  };

  const handleDeleteClick = async (serviceName: string) => {
    setDeleteModal({show: true, serviceName, inputName: '', dependsOn: [], dependentBy: []});
    setDeleteError('');
    const depCheck = await handleCheckDependencies(serviceName);
    setDeleteModal(prev => ({
      ...prev,
      dependsOn: depCheck.dependsOn,
      dependentBy: depCheck.dependentBy
    }));
  };

  const handleConfirmDelete = async () => {
    if (deleteModal.inputName !== deleteModal.serviceName) {
      setDeleteError('请输入正确的服务名称');
      return;
    }
    
    if (deleteModal.dependentBy.length > 0) {
      setDeleteError(`该服务被以下服务依赖: ${deleteModal.dependentBy.join(', ')}，无法删除`);
      return;
    }

    try {
      const response = await fetch(`/api/services/${deleteModal.serviceName}`, { method: 'DELETE' });
      if (response.ok) {
        setDeleteModal({show: false, serviceName: '', inputName: '', dependsOn: [], dependentBy: []});
        fetchData();
      }
    } catch (error) {
      console.error('Error deleting service:', error);
    }
  };

  const handleTabChange = (tab: string) => {
    setCurrentTab(tab);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'HEALTHY': return '#00ff9d';
      case 'WARNING': return '#fbbf24';
      case 'CRITICAL': return '#ef4444';
      case 'STOPPED': return '#ef4444';
      default: return '#94a3b8';
    }
  };

  const formatTime = (timestamp: number) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
    
    return date.toLocaleString('zh-CN', { 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const renderServiceList = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Services', value: stats?.total || 0, color: '#38bdf8' },
          { label: 'Healthy', value: stats?.healthy || 0, color: '#00ff9d' },
          { label: 'Warning', value: stats?.warning || 0, color: '#f59e0b' },
          { label: 'Stopped', value: stats?.stopped || 0, color: '#f43f5e' },
        ].map(stat => (
          <div key={stat.label} className="glass-panel p-4 rounded-xl flex items-center justify-between">
            <div>
              <div className="text-slate-500 text-xs font-bold uppercase">{stat.label}</div>
              <div className="text-2xl font-bold text-white mt-1">{stat.value}</div>
            </div>
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${stat.color}20` }}>
              <Layers className="w-5 h-5" style={{ color: stat.color }} />
            </div>
          </div>
        ))}
      </div>

      {/* Service List & Actions */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Layers className="w-5 h-5 mr-2 text-[#00ff9d]" /> 服务列表
          </h3>
          <div className="flex space-x-2">
            <button
              onClick={() => handleTabChange('部署向导')}
              className="px-3 py-1.5 bg-[#00ff9d]/10 text-[#00ff9d] rounded-lg text-xs font-bold hover:bg-[#00ff9d]/20 flex items-center">
              <Plus className="w-3 h-3 mr-1" /> Deploy New Service
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-6 py-3 rounded-l-lg">Service Name</th>
                <th className="px-6 py-3">Version</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Config Version</th>
                <th className="px-6 py-3">Last Operation</th>
                <th className="px-6 py-3 rounded-r-lg">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {services.map(svc => (
                <tr key={svc.name} className="hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-4 font-bold text-white flex items-center">
                    <div className="w-2 h-2 rounded-full mr-3" style={{ 
                      backgroundColor: getStatusColor(svc.status),
                      boxShadow: `0 0 5px ${getStatusColor(svc.status)}`
                    }}></div>
                    {svc.name}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-400">{svc.version}</td>
                  <td className="px-6 py-4 text-xs text-slate-400">{svc.role}</td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold border" style={{
                      backgroundColor: `${getStatusColor(svc.status)}10`,
                      color: getStatusColor(svc.status),
                      borderColor: `${getStatusColor(svc.status)}20`
                    }}>
                      {svc.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 flex items-center">
                    <span className="font-mono text-xs bg-white/10 px-1.5 rounded mr-2">{svc.configVersion}</span>
                    <GitBranch className="w-3 h-3 text-slate-500 cursor-pointer hover:text-white" />
                  </td>
                  <td className="px-6 py-4">
                    {svc.lastOperationTime ? (
                      <div className="text-xs">
                        <div className="text-slate-300">{svc.lastOperation || '-'}</div>
                        <div className="text-slate-500">{formatTime(svc.lastOperationTime)}</div>
                      </div>
                    ) : (
                      <span className="text-slate-500 text-xs">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex space-x-2">
                      <button 
                        onClick={() => handleAction(svc.name, 'start')}
                        title="Start Service"
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-[#00ff9d]"
                      >
                        <Play className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleAction(svc.name, 'restart')}
                        title="Restart Service"
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-[#38bdf8]"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleAction(svc.name, 'stop')}
                        title="Stop Service"
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-rose-500"
                      >
                        <Power className="w-4 h-4" />
                      </button>
                      <button 
                        // In a real app, this might navigate to config center via parent
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                        <Settings className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => {
                          setDependencyModalService(svc.name);
                          setShowDependencyModal(true);
                        }}
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-[#a855f7]"
                        title="Dependencies"
                      >
                        <Share2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteClick(svc.name)}
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-rose-500"
                        title="Delete Service"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {services.length === 0 && !loading && (
            <div className="text-center py-10 text-slate-500 text-sm">
              暂无已安装的服务，请使用部署向导添加服务
            </div>
          )}
          {loading && (
            <div className="text-center py-10 text-slate-500 text-sm">
              加载中...
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
        {renderServiceList()}
    </div>
  );

  // Render tab content based on current view
  const renderContent = () => {
    const activeTab = activeSubView || currentTab || '服务列表';

    switch (activeTab) {
      case '服务列表':
        return renderServiceList();
      case '部署向导':
        return <DeploymentWizard />;
      case '配置中心':
        return <ConfigCenter services={services} />;
      case '依赖管理':
        return <DependencyView services={services} dependencies={dependencies} selectedService={selectedService} onSelectService={setSelectedService} />;
      case '服务依赖拓扑':
        return <DependencyView services={services} dependencies={dependencies} selectedService={selectedService} onSelectService={setSelectedService} />;
      default:
        return renderServiceList();
    }
  };

  return (
    <>
      {deleteModal.show && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#0f172a] border border-white/10 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white flex items-center">
                <Trash2 className="w-5 h-5 mr-2 text-rose-500" /> 删除服务
              </h3>
              <button onClick={() => setDeleteModal({show: false, serviceName: '', inputName: '', dependsOn: [], dependentBy: []})} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <p className="text-slate-300">
                确定要删除服务 <span className="font-bold text-white">{deleteModal.serviceName}</span> 吗？
              </p>
              {deleteModal.dependsOn.length > 0 && (
                <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <div className="text-xs text-blue-400 mb-1">当前服务依赖以下服务：</div>
                  <div className="text-sm text-slate-300">{deleteModal.dependsOn.join(', ')}</div>
                </div>
              )}
              {deleteModal.dependentBy.length > 0 && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <div className="text-xs text-amber-400 mb-1">以下服务依赖当前服务：</div>
                  <div className="text-sm text-slate-300">{deleteModal.dependentBy.join(', ')}</div>
                </div>
              )}
              <div>
                <label className="text-sm text-slate-400 block mb-2">请输入服务名称以确认删除:</label>
                <input
                  type="text"
                  value={deleteModal.inputName}
                  onChange={(e) => setDeleteModal({...deleteModal, inputName: e.target.value})}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:border-rose-500 focus:outline-none"
                  placeholder={`输入 ${deleteModal.serviceName}`}
                />
              </div>
              {deleteError && (
                <div className="text-rose-500 text-sm p-2 bg-rose-500/10 rounded-lg">{deleteError}</div>
              )}
              <div className="flex justify-end space-x-3 pt-2">
                <button
                  onClick={() => setDeleteModal({show: false, serviceName: '', inputName: '', dependsOn: [], dependentBy: []})}
                  className="px-4 py-2 bg-white/10 text-slate-300 rounded-lg hover:bg-white/20"
                >
                  取消
                </button>
                <button
                  onClick={handleConfirmDelete}
                  className="px-4 py-2 bg-rose-500 text-white rounded-lg hover:bg-rose-600"
                >
                  确认删除
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {showDependencyModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#0f172a] border border-white/10 rounded-2xl p-6 w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white flex items-center">
                <Share2 className="w-5 h-5 mr-2 text-[#a855f7]" /> {dependencyModalService} 服务依赖拓扑
              </h3>
              <button onClick={() => setShowDependencyModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="overflow-y-auto max-h-[calc(90vh-100px)]">
              <DependencyView 
                services={services} 
                dependencies={dependencies} 
                selectedService={dependencyModalService} 
                onSelectService={setDependencyModalService} 
              />
            </div>
          </div>
        </div>
      )}
      {renderContent()}
    </>
  );
}

// --- Sub Components ---

function DeploymentWizard() {
  const [step, setStep] = useState(1);
  const steps = ['服务包仓库', '服务包部署', '安装主机', '选择服务', '分配角色', '配置参数'];

  const [repos, setRepos] = useState<any[]>([]);
  const [showRepoModal, setShowRepoModal] = useState(false);
  const [editingRepo, setEditingRepo] = useState<any>(null);
  const [verifyingRepo, setVerifyingRepo] = useState<string | null>(null);
  const [syncingRepo, setSyncingRepo] = useState<string | null>(null);
  const [newRepo, setNewRepo] = useState({
    repoId: '',
    repoName: '',
    displayName: '',
    repoType: 'yum',
    repoSource: 'LOCAL',
    baseURL: '',
    localPath: '',
    osType: 'centos7',
    architecture: 'x86_64',
    username: '',
    password: '',
    sslVerify: true,
    description: ''
  });

  const fetchRepos = async () => {
    try {
      const response = await fetch('/api/deploy/repositories');
      if (response.ok) {
        const data = await response.json();
        setRepos(data);
      }
    } catch (error) {
      console.error('Failed to fetch repos:', error);
    }
  };

  useEffect(() => {
    fetchRepos();
  }, []);

  const handleSaveRepo = async () => {
    if (!newRepo.repoId || !newRepo.displayName) {
      alert('请填写仓库ID和显示名称');
      return;
    }
    if (newRepo.repoSource === 'LOCAL' && !newRepo.localPath) {
      alert('本地仓库请填写本地路径');
      return;
    }
    if (newRepo.repoSource !== 'LOCAL' && !newRepo.baseURL) {
      alert('远程仓库请填写URL');
      return;
    }
    try {
      const method = editingRepo ? 'PUT' : 'POST';
      const url = editingRepo ? `/api/deploy/repositories/${editingRepo.repoId}` : '/api/deploy/repositories';
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRepo)
      });
      if (response.ok) {
        setShowRepoModal(false);
        setEditingRepo(null);
        setNewRepo({
          repoId: '',
          repoName: '',
          displayName: '',
          repoType: 'yum',
          repoSource: 'LOCAL',
          baseURL: '',
          localPath: '',
          osType: 'centos7',
          architecture: 'x86_64',
          username: '',
          password: '',
          sslVerify: true,
          description: ''
        });
        fetchRepos();
      } else {
        const errorData = await response.json();
        alert('保存失败: ' + (errorData.error || '未知错误'));
      }
    } catch (error) {
      console.error('Failed to save repo:', error);
      alert('保存失败: 网络错误');
    }
  };

  const handleVerifyRepo = async (repoId: string) => {
    setVerifyingRepo(repoId);
    try {
      await fetch('/api/deploy/repositories/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repoId })
      });
      fetchRepos();
    } catch (error) {
      console.error('Failed to verify repo:', error);
    } finally {
      setVerifyingRepo(null);
    }
  };

  const handleSyncRepo = async (repoId: string) => {
    setSyncingRepo(repoId);
    try {
      await fetch(`/api/deploy/repositories/${repoId}/sync`, { method: 'POST' });
    } catch (error) {
      console.error('Failed to sync repo:', error);
    } finally {
      setSyncingRepo(null);
    }
  };

  const handleDeleteRepo = async (repoId: string) => {
    if (!confirm('确定要删除此仓库吗？')) return;
    try {
      await fetch(`/api/deploy/repositories/${repoId}`, { method: 'DELETE' });
      fetchRepos();
    } catch (error) {
      console.error('Failed to delete repo:', error);
    }
  };

  const [hosts, setHosts] = useState<{id?: number; hostName: string; hostIP: string; sshUser: string; sshPort: number; sshKeyType: string; sshPrivateKey: string; sshKey: string; sshPassword: string; status: string}[]>([]);
  const [newHost, setNewHost] = useState({ hostName: '', hostIP: '', sshUser: 'root', sshPort: 22, sshKeyType: 'rsa', sshPrivateKey: '', sshKey: '', sshPassword: '' });

  const handleNextStep = async () => {
    if (step === 3 && hosts.length > 0) {
      try {
        const response = await fetch('/api/deploy/hosts-register/batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ hosts })
        });
        if (response.ok) {
          console.log('Hosts saved successfully');
        }
      } catch (error) {
        console.error('Failed to save hosts:', error);
      }
    }
    setStep(Math.min(6, step + 1));
  };

  const [availableServices, setAvailableServices] = useState<{name: string; version: string; desc: string; category: string; md5?: string}[]>([]);
  const [loadingServices, setLoadingServices] = useState(true);

  useEffect(() => {
    const fetchServices = async () => {
      try {
        const response = await fetch('/api/deploy/services');
        if (response.ok) {
          const data = await response.json();
          const mapped = data.map((s: any) => ({
            name: s.serviceName || s.ServiceName || '',
            version: s.version || s.Version || '',
            desc: s.displayName || s.DisplayName || s.serviceName || '',
            category: s.category || 'Storage',
            md5: s.md5 || s.MD5
          }));
          setAvailableServices(mapped);
        }
      } catch (error) {
        console.error('Failed to fetch services:', error);
      } finally {
        setLoadingServices(false);
      }
    };
    fetchServices();
  }, []);

  return (
    <div className="glass-panel p-6 rounded-2xl min-h-[600px] flex flex-col animate-in fade-in duration-500">
      <div className="flex items-center justify-between mb-8">
        <h3 className="text-lg font-bold text-white flex items-center">
          <Box className="w-5 h-5 mr-2 text-[#38bdf8]" /> 部署向导
        </h3>
        
        {/* Progress Steps */}
        <div className="flex items-center space-x-2">
          {steps.map((s, i) => (
            <React.Fragment key={s}>
              <div className={cn(
                "flex items-center",
                step > i + 1 ? "text-[#00ff9d]" : step === i + 1 ? "text-[#38bdf8] font-bold" : "text-slate-500"
              )}>
                <div className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2",
                  step > i + 1 ? "bg-[#00ff9d]/20 text-[#00ff9d]" : step === i + 1 ? "bg-[#38bdf8]/20 text-[#38bdf8] ring-2 ring-[#38bdf8]/50" : "bg-white/5"
                )}>
                  {step > i + 1 ? <CheckCircle className="w-3 h-3" /> : i + 1}
                </div>
                {s}
              </div>
              {i < steps.length - 1 && <ChevronRight className="w-4 h-4 text-slate-600 mx-2" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div className="flex-1">
        {step === 1 && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h4 className="text-white font-bold flex items-center">
                <Server className="w-5 h-5 mr-2 text-[#38bdf8]" /> 服务包仓库配置
              </h4>
              <button
                onClick={() => { setShowRepoModal(true); setEditingRepo(null); setNewRepo({
                  repoId: '',
                  repoName: '',
                  displayName: '',
                  repoType: 'yum',
                  repoSource: 'LOCAL',
                  baseURL: '',
                  localPath: '',
                  osType: 'centos7',
                  architecture: 'x86_64',
                  username: '',
                  password: '',
                  sslVerify: true,
                  description: ''
                }); }}
                className="px-4 py-2 bg-[#38bdf8] text-white rounded-lg text-sm font-bold hover:bg-[#0ea5e9] transition-colors flex items-center"
              >
                <Plus className="w-4 h-4 mr-1" /> 添加仓库
              </button>
            </div>
            
            {repos.length === 0 ? (
              <div className="text-center py-20 text-slate-400">
                <Server className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>暂无仓库配置，请添加服务包仓库</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {repos.map(repo => (
                  <div key={repo.repoId} className="bg-[#0f172a] rounded-xl border border-white/10 p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="text-lg font-bold text-white">{repo.displayName || repo.repoName}</div>
                        <div className="text-xs text-slate-500">{repo.repoId}</div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-1 rounded text-xs ${repo.verifyStatus === 'SUCCESS' ? 'bg-green-500/20 text-green-400' : repo.verifyStatus === 'FAILED' ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-400'}`}>
                          {repo.verifyStatus || '未验证'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs ${repo.repoSource === 'LOCAL' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'}`}>
                          {repo.repoSource === 'LOCAL' ? '本地仓库' : '远程仓库'}
                        </span>
                      </div>
                    </div>
                    
                    <div className="text-sm text-slate-400 mb-3 space-y-1">
                      <div className="flex items-center">
                        <span className="w-20 text-slate-500">类型:</span>
                        <span>{repo.repoType}</span>
                      </div>
                      <div className="flex items-center">
                        <span className="w-20 text-slate-500">操作系统:</span>
                        <span>{repo.osType}</span>
                      </div>
                      <div className="flex items-center">
                        <span className="w-20 text-slate-500">架构:</span>
                        <span>{repo.architecture}</span>
                      </div>
                      <div className="flex items-center">
                        <span className="w-20 text-slate-500">路径/URL:</span>
                        <span className="truncate">{repo.repoSource === 'LOCAL' ? repo.localPath : repo.baseURL}</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between pt-3 border-t border-white/10">
                      <button
                        onClick={() => handleVerifyRepo(repo.repoId)}
                        disabled={verifyingRepo === repo.repoId}
                        className="px-3 py-1.5 bg-white/5 text-slate-300 rounded text-xs hover:bg-white/10 disabled:opacity-50"
                      >
                        {verifyingRepo === repo.repoId ? '验证中...' : '验证'}
                      </button>
                      <button
                        onClick={() => handleSyncRepo(repo.repoId)}
                        disabled={syncingRepo === repo.repoId}
                        className="px-3 py-1.5 bg-white/5 text-slate-300 rounded text-xs hover:bg-white/10 disabled:opacity-50"
                      >
                        {syncingRepo === repo.repoId ? '同步中...' : '同步'}
                      </button>
                      <button
                        onClick={() => { setEditingRepo(repo); setNewRepo(repo); setShowRepoModal(true); }}
                        className="px-3 py-1.5 bg-white/5 text-slate-300 rounded text-xs hover:bg-white/10"
                      >
                        编辑
                      </button>
                      <button
                        onClick={() => handleDeleteRepo(repo.repoId)}
                        className="px-3 py-1.5 bg-red-500/20 text-red-400 rounded text-xs hover:bg-red-500/30"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {step === 3 && (
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="flex-1 bg-[#0f172a] rounded-xl border border-white/10 p-6">
              <h4 className="text-white font-bold mb-4 flex items-center">
                <Server className="w-5 h-5 mr-2 text-[#38bdf8]" /> 添加主机
              </h4>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">主机名称/域名</label>
                  <input 
                    type="text" 
                    value={newHost.hostName}
                    onChange={(e) => setNewHost({...newHost, hostName: e.target.value})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                    placeholder="例如: node1.example.com 或 192.168.1.100"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">用户名</label>
                  <input 
                    type="text" 
                    value={newHost.sshUser}
                    onChange={(e) => setNewHost({...newHost, sshUser: e.target.value})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                    placeholder="root"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">端口</label>
                  <input 
                    type="number" 
                    value={newHost.sshPort}
                    onChange={(e) => setNewHost({...newHost, sshPort: parseInt(e.target.value) || 22})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                    placeholder="22"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">加密方式</label>
                  <select 
                    value={newHost.sshKeyType}
                    onChange={(e) => setNewHost({...newHost, sshKeyType: e.target.value})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-[#38bdf8] focus:outline-none"
                  >
                    <option value="rsa">RSA密钥</option>
                    <option value="ed25519">Ed25519密钥</option>
                    <option value="password">密码</option>
                  </select>
                </div>
                {newHost.sshKeyType !== 'password' ? (
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">私钥内容</label>
                    <textarea 
                      value={newHost.sshPrivateKey}
                      onChange={(e) => setNewHost({...newHost, sshPrivateKey: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none font-mono text-sm"
                      placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                      rows={4}
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">密码</label>
                    <input 
                      type="password" 
                      value={newHost.sshPassword}
                      onChange={(e) => setNewHost({...newHost, sshPassword: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                      placeholder="请输入密码"
                    />
                  </div>
                )}
                <button 
                  onClick={() => {
                    if (newHost.hostName && newHost.sshUser) {
                      setHosts([...hosts, {...newHost, id: Date.now(), status: 'pending'}]);
                      setNewHost({ hostName: '', hostIP: '', sshUser: 'root', sshPort: 22, sshKeyType: 'rsa', sshPrivateKey: '', sshKey: '', sshPassword: '' });
                    }
                  }}
                  className="w-full py-2 bg-[#38bdf8] text-white rounded-lg font-bold hover:bg-[#2563eb] flex items-center justify-center"
                >
                  <Plus className="w-4 h-4 mr-2" /> 添加主机
                </button>
              </div>
            </div>
            <div className="flex-1">
              <h4 className="text-white font-bold mb-4 flex items-center">
                <Server className="w-5 h-5 mr-2 text-[#00ff9d]" /> 已添加的主机 ({hosts.length})
              </h4>
              {hosts.length === 0 ? (
                <div className="text-slate-500 text-center py-10 border border-dashed border-white/10 rounded-xl">
                  暂无主机，请先添加主机
                </div>
              ) : (
                <div className="space-y-2 max-h-[400px] overflow-y-auto custom-scrollbar">
                  {hosts.map((host, idx) => (
                    <div key={host.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/10">
                      <div>
                        <div className="text-white font-medium">{host.hostName}</div>
                        <div className="text-xs text-slate-400">{host.sshUser}@{host.hostName}:{host.sshPort}</div>
                      </div>
                      <button 
                        onClick={() => setHosts(hosts.filter(h => h.id !== host.id))}
                        className="p-1 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            {loadingServices ? (
              <div className="text-center py-20 text-slate-400">加载服务数据中...</div>
            ) : availableServices.length === 0 ? (
              <div className="text-center py-20 text-slate-400">暂无服务数据</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {availableServices.map(svc => (
                  <div key={svc.name} className="border border-white/10 rounded-xl p-4 hover:border-[#00ff9d]/50 hover:bg-[#00ff9d]/5 cursor-pointer transition-all group relative">
                    <div className="absolute top-4 right-4 w-4 h-4 rounded border border-slate-500 group-hover:border-[#00ff9d]"></div>
                    <div className="text-xs text-[#38bdf8] font-bold mb-1">{svc.category}</div>
                    <div className="text-lg font-bold text-white mb-2">{svc.name}</div>
                    <div className="text-xs text-slate-400">{svc.desc}</div>
                    {svc.version && <div className="text-xs text-slate-500 mt-1">v{svc.version}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {step === 3 && (
          <div className="space-y-4">
            <div className="text-slate-400 mb-4">将服务组件分配到集群主机上。</div>
            {['NameNode', 'DataNode', 'ResourceManager', 'NodeManager'].map(role => (
              <div key={role} className="flex items-center justify-between p-4 border border-white/5 rounded-lg bg-white/5">
                <div className="font-bold text-white">{role}</div>
                <button className="px-4 py-1.5 bg-white/10 rounded-lg text-sm text-slate-300 hover:text-white flex items-center">
                  <Server className="w-4 h-4 mr-2" /> 选择主机
                </button>
              </div>
            ))}
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
             <div className="text-slate-400 mb-4">检查并修改默认配置。</div>
             <div className="bg-[#0f172a] p-4 rounded-lg font-mono text-sm text-slate-300 border border-white/10">
               <div><span className="text-[#38bdf8]">dfs.replication</span> = 3</div>
               <div><span className="text-[#38bdf8]">dfs.namenode.name.dir</span> = /data/hadoop/hdfs/nn</div>
               <div><span className="text-[#38bdf8]">yarn.nodemanager.resource.memory-mb</span> = 8192</div>
             </div>
          </div>
        )}

        {step === 6 && (
          <div className="text-center py-20">
            <CheckCircle className="w-16 h-16 text-[#00ff9d] mx-auto mb-4" />
            <h4 className="text-xl font-bold text-white mb-2">准备就绪</h4>
            <p className="text-slate-400">请确认以上配置无误，点击开始部署将在后台自动执行安装流程。</p>
          </div>
        )}

        {/* Repository Modal */}
        {showRepoModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-[#0f172a] rounded-xl border border-white/10 p-6 w-[600px] max-h-[80vh] overflow-y-auto">
              <h3 className="text-lg font-bold text-white mb-4">
                {editingRepo ? '编辑仓库' : '添加仓库'}
              </h3>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">仓库ID</label>
                    <input 
                      type="text" 
                      value={newRepo.repoId}
                      onChange={(e) => setNewRepo({...newRepo, repoId: e.target.value})}
                      disabled={!!editingRepo}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none disabled:opacity-50"
                      placeholder="例如: local-repo"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">显示名称</label>
                    <input 
                      type="text" 
                      value={newRepo.displayName}
                      onChange={(e) => setNewRepo({...newRepo, displayName: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                      placeholder="例如: 本地仓库"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">仓库类型</label>
                    <select 
                      value={newRepo.repoType}
                      onChange={(e) => setNewRepo({...newRepo, repoType: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-[#38bdf8] focus:outline-none"
                    >
                      <option value="yum">yum</option>
                      <option value="apt">apt</option>
                      <option value="docker">docker</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">仓库来源</label>
                    <select 
                      value={newRepo.repoSource}
                      onChange={(e) => setNewRepo({...newRepo, repoSource: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-[#38bdf8] focus:outline-none"
                    >
                      <option value="LOCAL">本地仓库</option>
                      <option value="REMOTE">远程仓库</option>
                    </select>
                  </div>
                </div>
                
                {newRepo.repoSource === 'LOCAL' ? (
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">本地路径</label>
                    <input 
                      type="text" 
                      value={newRepo.localPath}
                      onChange={(e) => setNewRepo({...newRepo, localPath: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                      placeholder="例如: /opt/repository"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">远程URL</label>
                    <input 
                      type="text" 
                      value={newRepo.baseURL}
                      onChange={(e) => setNewRepo({...newRepo, baseURL: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                      placeholder="例如: http://repo.example.com/centos"
                    />
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">操作系统</label>
                    <select 
                      value={newRepo.osType}
                      onChange={(e) => setNewRepo({...newRepo, osType: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-[#38bdf8] focus:outline-none"
                    >
                      <option value="centos7">CentOS 7</option>
                      <option value="centos8">CentOS 8</option>
                      <option value="ubuntu20">Ubuntu 20.04</option>
                      <option value="ubuntu22">Ubuntu 22.04</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">架构</label>
                    <select 
                      value={newRepo.architecture}
                      onChange={(e) => setNewRepo({...newRepo, architecture: e.target.value})}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-[#38bdf8] focus:outline-none"
                    >
                      <option value="x86_64">x86_64</option>
                      <option value="aarch64">aarch64</option>
                    </select>
                  </div>
                </div>
                
                {newRepo.repoSource === 'REMOTE' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">用户名</label>
                      <input 
                        type="text" 
                        value={newRepo.username}
                        onChange={(e) => setNewRepo({...newRepo, username: e.target.value})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                        placeholder="可选"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-slate-400 mb-1">密码</label>
                      <input 
                        type="password" 
                        value={newRepo.password}
                        onChange={(e) => setNewRepo({...newRepo, password: e.target.value})}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                        placeholder="可选"
                      />
                    </div>
                  </div>
                )}
                
                {newRepo.repoSource === 'REMOTE' && (
                  <div className="flex items-center">
                    <input 
                      type="checkbox" 
                      checked={newRepo.sslVerify}
                      onChange={(e) => setNewRepo({...newRepo, sslVerify: e.target.checked})}
                      className="w-4 h-4 mr-2"
                    />
                    <label className="text-sm text-slate-400">验证SSL证书</label>
                  </div>
                )}
                
                <div>
                  <label className="block text-sm text-slate-400 mb-1">描述</label>
                  <textarea 
                    value={newRepo.description}
                    onChange={(e) => setNewRepo({...newRepo, description: e.target.value})}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:border-[#38bdf8] focus:outline-none"
                    rows={2}
                    placeholder="可选描述"
                  />
                </div>
              </div>
              
              <div className="flex justify-end mt-6 space-x-3">
                <button 
                  onClick={() => { setShowRepoModal(false); setEditingRepo(null); }}
                  className="px-4 py-2 bg-white/10 text-slate-300 rounded-lg hover:bg-white/20"
                >
                  取消
                </button>
                <button 
                  onClick={handleSaveRepo}
                  className="px-4 py-2 bg-[#38bdf8] text-white rounded-lg hover:bg-[#0ea5e9]"
                >
                  保存
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="flex justify-between mt-8 pt-4 border-t border-white/10">
        <button 
          onClick={() => setStep(Math.max(1, step - 1))}
          disabled={step === 1}
          className="px-6 py-2 bg-white/5 text-slate-300 rounded-lg font-bold hover:bg-white/10 disabled:opacity-50"
        >
          上一步
        </button>
        {step < 6 ? (
          <button 
            onClick={handleNextStep}
            className="px-6 py-2 bg-[#38bdf8] text-white rounded-lg font-bold hover:bg-[#2563eb] shadow-lg shadow-blue-500/20"
          >
            下一步
          </button>
        ) : (
          <button 
            onClick={() => alert('开始部署...')}
            className="px-6 py-2 bg-[#00ff9d] text-[#020617] rounded-lg font-bold hover:bg-[#00e68d] shadow-[0_0_15px_rgba(0,255,157,0.3)]"
          >
            开始部署
          </button>
        )}
      </div>
    </div>
  );
}

function ConfigCenter({ services }: { services: ServiceInfo[] }) {
  const [selectedService, setSelectedService] = useState(services[0]?.name || 'HDFS');

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 animate-in fade-in duration-500">
      {/* Service List Sidebar */}
      <div className="glass-panel p-4 rounded-xl lg:col-span-1 h-[600px] overflow-y-auto custom-scrollbar">
        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 px-2">Services</div>
        <div className="space-y-1">
          {services.map(svc => (
            <button
              key={svc.name}
              onClick={() => setSelectedService(svc.name)}
              className={cn(
                "w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all",
                selectedService === svc.name
                  ? "bg-white/10 text-white border border-white/10"
                  : "text-slate-400 hover:bg-white/5 hover:text-white border border-transparent"
              )}
            >
              <FileText className="w-4 h-4 mr-3 opacity-70" />
              {svc.name}
            </button>
          ))}
        </div>
      </div>

      {/* Config Editor Area */}
      <div className="glass-panel p-6 rounded-xl lg:col-span-3 h-[600px] flex flex-col">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center">
              {selectedService} 配置
            </h3>
            <div className="text-xs text-slate-400 mt-1">Version: <span className="font-mono text-[#38bdf8]">v24</span> • Last updated 2 hours ago</div>
          </div>
          <div className="flex space-x-2">
            <button className="px-4 py-2 bg-white/5 text-slate-300 rounded-lg text-sm font-bold hover:bg-white/10 flex items-center">
              <RotateCcw className="w-4 h-4 mr-2" /> 历史版本
            </button>
            <button className="px-4 py-2 bg-[#00ff9d]/10 text-[#00ff9d] border border-[#00ff9d]/30 rounded-lg text-sm font-bold hover:bg-[#00ff9d]/20 flex items-center">
              <Save className="w-4 h-4 mr-2" /> 保存配置
            </button>
          </div>
        </div>

        {/* Version Control / History List (Mock) */}
        <div className="mb-4 flex space-x-2 overflow-x-auto pb-2 border-b border-white/5">
           {[24, 23, 22, 21, 20].map((v, i) => (
              <div key={v} className={cn(
                 "flex-shrink-0 px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-all",
                 i === 0 ? "bg-[#38bdf8]/10 border-[#38bdf8]/30 text-[#38bdf8]" : "bg-white/5 border-white/5 text-slate-400 hover:bg-white/10"
              )}>
                 <div className="flex items-center font-bold">
                    <GitCommit className="w-3 h-3 mr-1" /> v{v}
                 </div>
                 <div className="text-[10px] opacity-70 mt-0.5">2023-10-{27-i}</div>
              </div>
           ))}
        </div>

        {/* Mock Config Editor */}
        <div className="flex-1 bg-[#0f172a] rounded-lg border border-white/10 overflow-hidden flex flex-col">
          <div className="flex border-b border-white/10 bg-white/5 px-2">
            {['core-site.xml', 'hdfs-site.xml', 'Advanced'].map(tab => (
              <button key={tab} className="px-4 py-2 text-sm text-slate-300 hover:text-white border-b-2 border-transparent focus:border-[#38bdf8]">
                {tab}
              </button>
            ))}
          </div>
          <div className="p-4 flex-1 overflow-y-auto custom-scrollbar font-mono text-sm">
            <div className="text-slate-500 mb-2">{`<!-- hdfs-site.xml -->`}</div>
            <div className="text-[#f87171]">{`<configuration>`}</div>
            <div className="pl-4">
              <div className="text-[#f87171]">{`<property>`}</div>
              <div className="pl-4 text-[#38bdf8]">{`<name>dfs.replication</name>`}</div>
              <div className="pl-4 text-[#a3e635]">{`<value>3</value>`}</div>
              <div className="text-[#f87171]">{`</property>`}</div>
              
              <div className="text-[#f87171] mt-2">{`<property>`}</div>
              <div className="pl-4 text-[#38bdf8]">{`<name>dfs.namenode.name.dir</name>`}</div>
              <div className="pl-4 text-[#a3e635]">{`<value>file:///data/hadoop/hdfs/nn</value>`}</div>
              <div className="text-[#f87171]">{`</property>`}</div>
            </div>
            <div className="text-[#f87171]">{`</configuration>`}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
