import React, { useState, useEffect } from 'react';
import { Layers, Play, Settings, GitBranch, Share2, Box, RotateCcw, Power, Plus, Save, FileText, CheckCircle, ChevronRight, Server, RotateCw, GitCommit, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ServiceInfo {
  name: string;
  version: string;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL' | 'STOPPED' | 'UNKNOWN';
  configVersion: string;
  role: string;
  components: string[];
}

function DependencyView({ services }: { services: ServiceInfo[] }) {
  // Mock Dependencies
  const dependencies = [
    { source: 'HIVE', target: 'HDFS', type: 'Storage' },
    { source: 'HIVE', target: 'YARN', type: 'Compute' },
    { source: 'SPARK', target: 'HDFS', type: 'Storage' },
    { source: 'SPARK', target: 'YARN', type: 'Compute' },
    { source: 'HBase', target: 'HDFS', type: 'Storage' },
    { source: 'HBase', target: 'ZooKeeper', type: 'Coordination' },
    { source: 'Kafka', target: 'ZooKeeper', type: 'Coordination' },
  ];

  return (
    <div className="glass-panel p-6 rounded-2xl animate-in fade-in duration-500">
       <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
             <Share2 className="w-5 h-5 mr-2 text-[#a855f7]" /> 服务依赖拓扑
          </h3>
          <button className="px-3 py-1.5 bg-white/5 rounded-lg text-xs text-slate-300 hover:text-white">Refresh Graph</button>
       </div>
       
       <div className="bg-[#020617] rounded-xl border border-white/5 p-8 min-h-[500px] relative overflow-hidden flex items-center justify-center">
          <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
          
          {/* Simple Visual Representation of Dependencies */}
          <div className="relative z-10 w-full max-w-4xl grid grid-cols-3 gap-8">
             {/* Layer 1: Core Infra */}
             <div className="space-y-4">
                <div className="text-xs font-bold text-slate-500 uppercase text-center mb-2">Core Infrastructure</div>
                {['ZooKeeper', 'HDFS', 'YARN'].map(svc => (
                   <div key={svc} className="p-4 bg-slate-800 border border-slate-700 rounded-lg text-center shadow-lg relative group">
                      <div className="font-bold text-white">{svc}</div>
                      <div className="text-xs text-slate-400">Foundation</div>
                      {/* Connection Points */}
                      <div className="absolute top-1/2 -right-2 w-4 h-0.5 bg-slate-600"></div>
                   </div>
                ))}
             </div>

             {/* Layer 2: Processing / Storage */}
             <div className="space-y-12 py-8">
                <div className="text-xs font-bold text-slate-500 uppercase text-center mb-2">Engines & DBs</div>
                {['HBase', 'Kafka', 'Spark'].map(svc => (
                   <div key={svc} className="p-4 bg-[#38bdf8]/10 border border-[#38bdf8]/30 rounded-lg text-center shadow-lg relative">
                      {/* Incoming Lines */}
                      <div className="absolute top-1/2 -left-4 w-4 h-0.5 bg-slate-600"></div>
                      <div className="font-bold text-white">{svc}</div>
                      <div className="text-xs text-[#38bdf8]">Processing</div>
                      {/* Outgoing Lines */}
                      <div className="absolute top-1/2 -right-4 w-4 h-0.5 bg-slate-600"></div>
                   </div>
                ))}
             </div>

             {/* Layer 3: Application / SQL */}
             <div className="space-y-24 py-16">
                <div className="text-xs font-bold text-slate-500 uppercase text-center mb-2">Application / SQL</div>
                {['Hive', 'Flink'].map(svc => (
                   <div key={svc} className="p-4 bg-[#a855f7]/10 border border-[#a855f7]/30 rounded-lg text-center shadow-lg relative">
                      {/* Incoming Lines */}
                      <div className="absolute top-1/2 -left-4 w-4 h-0.5 bg-slate-600"></div>
                      <div className="font-bold text-white">{svc}</div>
                      <div className="text-xs text-[#a855f7]">Application</div>
                   </div>
                ))}
             </div>
          </div>
       </div>
       
       <div className="mt-6">
          <h4 className="font-bold text-white mb-3 text-sm">Dependency Details</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
             {dependencies.map((dep, i) => (
                <div key={i} className="flex items-center p-3 bg-white/5 rounded-lg border border-white/5">
                   <span className="font-bold text-white">{dep.source}</span>
                   <div className="flex-1 mx-2 h-px bg-slate-600 relative">
                      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] bg-[#020617] px-1 text-slate-500">{dep.type}</span>
                   </div>
                   <ArrowRightIcon className="w-3 h-3 text-slate-500 mr-1" />
                   <span className="font-bold text-slate-300">{dep.target}</span>
                </div>
             ))}
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

  useEffect(() => {
    if (activeSubView) {
      setCurrentTab(activeSubView);
    }
  }, [activeSubView]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      // Mock Data
      setServices([
        { name: 'HDFS', version: '3.3.6', status: 'HEALTHY', configVersion: 'v24', role: 'Storage', components: [] },
        { name: 'YARN', version: '3.3.6', status: 'HEALTHY', configVersion: 'v12', role: 'Compute', components: [] },
        { name: 'HIVE', version: '3.1.3', status: 'WARNING', configVersion: 'v8', role: 'Database', components: [] },
        { name: 'SPARK', version: '3.5.0', status: 'HEALTHY', configVersion: 'v5', role: 'Compute', components: [] },
        { name: 'KAFKA', version: '3.6.0', status: 'STOPPED', configVersion: 'v10', role: 'Messaging', components: [] },
      ]);
      setStats({ total: 5, healthy: 3, warning: 1, stopped: 1 });
      setLoading(false);
    } catch (error) {
      console.error('Error fetching service data:', error);
      setLoading(false);
    }
  };

  const handleAction = async (serviceName: string, action: 'start' | 'stop' | 'restart') => {
    // Mock action
    console.log(`Performing ${action} on ${serviceName}`);
    fetchData(); // Refresh mock data
  };

  const handleTabChange = (tab: string) => {
    setCurrentTab(tab);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'HEALTHY': return '#00ff9d';
      case 'WARNING': return '#f59e0b';
      case 'CRITICAL': return '#ef4444';
      case 'STOPPED': return '#f43f5e';
      default: return '#94a3b8';
    }
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
                        onClick={() => handleTabChange('依赖管理')}
                        className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-[#a855f7]"
                        title="Dependencies"
                      >
                        <Share2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {services.length === 0 && !loading && (
            <div className="text-center py-10 text-slate-500 text-sm">
              No services found.
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
        return <DependencyView services={services} />;
      default:
        return renderServiceList();
    }
  };

  return (
    <>
      {renderContent()}
    </>
  );
}

// --- Sub Components ---

function DeploymentWizard() {
  const [step, setStep] = useState(1);
  const steps = ['选择服务', '分配角色', '自定义配置', '确认部署'];

  const availableServices = [
    { name: 'HDFS', desc: 'Hadoop Distributed File System', category: 'Storage' },
    { name: 'YARN', desc: 'Yet Another Resource Negotiator', category: 'Compute' },
    { name: 'ZooKeeper', desc: 'High-performance Coordination Service', category: 'Coordination' },
    { name: 'HBase', desc: 'Hadoop Database', category: 'Database' },
    { name: 'Hive', desc: 'Data Warehouse Infrastructure', category: 'Database' },
    { name: 'Spark', desc: 'Unified Analytics Engine', category: 'Compute' },
    { name: 'Kafka', desc: 'Distributed Streaming Platform', category: 'Messaging' },
  ];

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
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {availableServices.map(svc => (
              <div key={svc.name} className="border border-white/10 rounded-xl p-4 hover:border-[#00ff9d]/50 hover:bg-[#00ff9d]/5 cursor-pointer transition-all group relative">
                <div className="absolute top-4 right-4 w-4 h-4 rounded border border-slate-500 group-hover:border-[#00ff9d]"></div>
                <div className="text-xs text-[#38bdf8] font-bold mb-1">{svc.category}</div>
                <div className="text-lg font-bold text-white mb-2">{svc.name}</div>
                <div className="text-xs text-slate-400">{svc.desc}</div>
              </div>
            ))}
          </div>
        )}
        
        {step === 2 && (
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

        {step === 3 && (
          <div className="space-y-4">
             <div className="text-slate-400 mb-4">检查并修改默认配置。</div>
             <div className="bg-[#0f172a] p-4 rounded-lg font-mono text-sm text-slate-300 border border-white/10">
               <div><span className="text-[#38bdf8]">dfs.replication</span> = 3</div>
               <div><span className="text-[#38bdf8]">dfs.namenode.name.dir</span> = /data/hadoop/hdfs/nn</div>
               <div><span className="text-[#38bdf8]">yarn.nodemanager.resource.memory-mb</span> = 8192</div>
             </div>
          </div>
        )}

        {step === 4 && (
          <div className="text-center py-20">
            <CheckCircle className="w-16 h-16 text-[#00ff9d] mx-auto mb-4" />
            <h4 className="text-xl font-bold text-white mb-2">准备就绪</h4>
            <p className="text-slate-400">请确认以上配置无误，点击开始部署将在后台自动执行安装流程。</p>
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
        {step < 4 ? (
          <button 
            onClick={() => setStep(Math.min(4, step + 1))}
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
