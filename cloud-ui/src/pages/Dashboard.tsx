import React, { useState, useEffect, useRef } from 'react';
import {
  LayoutDashboard, Server, Users, LogOut,
  Database, Bell, Search, Menu, ChevronDown,
  CheckCircle, AlertTriangle, XCircle, Zap, Layers, FileText,
  Shield, Activity, BrainCircuit, Settings, User, Tags
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Overview from '../views/Overview';
import HostMgt from '../views/HostMgt';
import AgentAndExporterMgt from '../views/AgentAndExporterMgt';
import TagMgt from '../views/TagMgt';
import ServiceMgt from '../views/ServiceMgt';
import DataMart from '../views/DataMart';
import SecurityMgt from '../views/SecurityMgt';
import OpsMgt from '../views/OpsMgt';
import AIOps from '../views/AIOps';
import UserCenter from '../views/UserCenter';
import ServiceDetail from '../views/ServiceDetail';

// --- Main Dashboard Layout ---

interface ServiceSimple {
  name: string;
  status: string;
}

interface SearchResult {
  id: string;
  type: 'Service' | 'Host' | 'Data' | 'Security' | 'Alert';
  name: string;
  detail: string;
}

export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeView, setActiveView] = useState('Overview'); // Controls Main Content View
  const [activeSubView, setActiveSubView] = useState(''); // Controls Sub Content View
  const [services, setServices] = useState<ServiceSimple[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  
  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const notifRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchServices();
    const interval = setInterval(fetchServices, 5000);
    
    // Click outside handler
    const handleClickOutside = (event: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowSearch(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      clearInterval(interval);
    };
  }, []);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    // Mock Search Logic (In a real app, this would be an API call or searching through context)
    const mockData: SearchResult[] = [
      // Services
      { id: 'hdfs', type: 'Service', name: 'HDFS', detail: 'Distributed File System' },
      { id: 'yarn', type: 'Service', name: 'YARN', detail: 'Resource Negotiator' },
      { id: 'hive', type: 'Service', name: 'HIVE', detail: 'Data Warehouse' },
      { id: 'spark', type: 'Service', name: 'SPARK', detail: 'Analytics Engine' },
      { id: 'kafka', type: 'Service', name: 'KAFKA', detail: 'Streaming Platform' },
      // Hosts
      { id: 'master01', type: 'Host', name: 'Master01', detail: '192.168.1.10 (Control Plane)' },
      { id: 'worker01', type: 'Host', name: 'Worker01', detail: '192.168.1.11 (Worker)' },
      { id: 'worker02', type: 'Host', name: 'Worker02', detail: '192.168.1.12 (Worker)' },
      // Data Assets
      { id: 'fact_orders', type: 'Data', name: 'dw_sales.fact_orders', detail: 'Daily sales transactions' },
      { id: 'clickstream', type: 'Data', name: 'ods_log.clickstream', detail: 'Real-time user click events' },
    ];

    const lowerQuery = query.toLowerCase();
    const filtered = mockData.filter(item => 
      item.name.toLowerCase().includes(lowerQuery) || 
      item.detail.toLowerCase().includes(lowerQuery)
    );
    setSearchResults(filtered);
    setShowSearch(true);
  };

  const handleSearchResultClick = (result: SearchResult) => {
    setSearchQuery('');
    setShowSearch(false);
    
    switch (result.type) {
      case 'Service':
        setActiveView('ServiceMgt');
        // If it's a specific service, we might want to navigate to detail, but for now ServiceMgt list
        // Or if the architecture supports it, set active service
        // For simplicity, let's go to ServiceMgt and maybe filter? 
        // Current ServiceMgt doesn't support prop filter, so just go there.
        break;
      case 'Host':
        setActiveView('HostMgt');
        break;
      case 'Data':
        setActiveView('DataMart');
        setActiveSubView('数据目录'); // Assuming we want to see catalog
        break;
      case 'Security':
        setActiveView('SecurityMgt');
        break;
      case 'Alert':
        setActiveView('OpsMgt');
        setActiveSubView('告警中心');
        break;
    }
  };

  const handleSidebarClick = (view: string) => {
    setActiveView(view);
    setActiveSubView(''); // Reset sub view when switching main view
  };

  const fetchServices = async () => {
    try {
      const response = await fetch('/api/services');
      if (response.ok) {
        const data = await response.json();
        if (data && data.length > 0) {
          const mappedServices = data.map((s: any) => ({
            name: s.name || s.serviceName || '',
            status: (s.status || 'unknown').toLowerCase()
          }));
          setServices(mappedServices);
        } else {
          setServices([]);
        }
      } else {
        setServices([]);
      }
    } catch (error) {
      console.error('Error fetching services for sidebar:', error);
      setServices([]);
    }
  };

  // Helper to render current view
  const renderContent = () => {
    switch (activeView) {
      case 'Overview': return <Overview onNavigate={setActiveView} />;
      case 'ServiceMgt': return <ServiceMgt activeSubView={activeSubView} />;
      case 'HostMgt': 
        if (activeSubView === 'agent-exporter') {
          return <AgentAndExporterMgt />;
        }
        return <HostMgt activeSubView={activeSubView} setActiveSubView={setActiveSubView} />;
      case 'TagMgt': return <TagMgt activeSubView={activeSubView} />;
      case 'DataMart': return <DataMart activeSubView={activeSubView} />;
      case 'SecurityMgt': return <SecurityMgt activeSubView={activeSubView} />;
      case 'OpsMgt': return <OpsMgt activeSubView={activeSubView} />;
      case 'AIOps': return <AIOps activeSubView={activeSubView} />;
      case 'UserMgt': return <UserCenter activeSubView={activeSubView} />;
      default:
        // If view matches a service name, render Service Detail
        if (services.some(s => s.name === activeView)) {
          return <ServiceDetail serviceName={activeView} />;
        }
        return <Overview onNavigate={setActiveView} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] text-slate-200 flex font-sans overflow-hidden">
      {/* Background Ambience */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-900/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-[#00ff9d]/5 rounded-full blur-[120px]" />
      </div>

      {/* Sidebar - Cloud Style (Services List) */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-[#020617]/95 backdrop-blur-xl border-r border-white/5 transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 flex flex-col",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        {/* Sidebar Header */}
        <div className="h-16 flex items-center px-6 border-b border-white/5 shrink-0">
          <div className="w-8 h-8 bg-[#00ff9d] rounded-lg flex items-center justify-center mr-3 shadow-[0_0_15px_rgba(0,255,157,0.3)]">
            <Zap className="w-5 h-5 text-[#020617]" fill="currentColor" />
          </div>
          <span className="text-lg font-bold text-white tracking-tight">CloudRealm</span>
        </div>

        {/* Navigation List */}
        <div className="flex-1 overflow-y-auto custom-scrollbar py-4">
          
          {/* Dashboard Link */}
          <div className="px-3 mb-6">
            <button
              onClick={() => handleSidebarClick('Overview')}
              className={cn(
                "w-full flex items-center px-3 py-2.5 rounded-lg text-sm font-bold transition-all duration-200",
                activeView === 'Overview'
                  ? "bg-[#00ff9d] text-[#020617] shadow-[0_0_10px_#00ff9d]" 
                  : "text-white hover:bg-white/10"
              )}
            >
              <LayoutDashboard className="w-4 h-4 mr-3" />
              Dashboard
            </button>
          </div>

          {/* Services List Header */}
          <div className="px-6 mb-2 flex items-center justify-between">
             <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Services</span>
             <span className="text-[10px] bg-white/10 px-1.5 rounded text-slate-400">{services.length}</span>
          </div>

          {/* Services Items */}
          <nav className="space-y-0.5 px-3">
            {services.map((service) => (
              <button
                key={service.name}
                onClick={() => setActiveView(service.name)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group border border-transparent",
                  activeView === service.name
                    ? "bg-white/10 text-white border-white/10" 
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                )}
              >
                <span className="flex items-center">
                  <div className={cn("w-2 h-2 rounded-full mr-3 shadow-[0_0_5px]", 
                      service.status === 'healthy' ? "bg-[#00ff9d] shadow-[#00ff9d]/50" : 
                      service.status === 'warning' ? "bg-amber-500 shadow-amber-500/50" : 
                      "bg-slate-600"
                  )}></div>
                  {service.name}
                </span>
                {service.status === 'warning' && <AlertTriangle className="w-3 h-3 text-amber-500" />}
                {service.status === 'stopped' && <div className="text-[10px] text-slate-600 font-mono">STOP</div>}
              </button>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-white/5 bg-[#020617]/95">
          <button className="w-full flex items-center px-4 py-3 text-sm font-medium text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition-colors group">
            <LogOut className="w-5 h-5 mr-3 group-hover:text-rose-500" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        {/* Top Header */}
        <header className="h-16 bg-[#020617]/80 backdrop-blur-md border-b border-white/5 flex items-center justify-between px-4 lg:px-8 sticky top-0 z-40">
          <div className="flex items-center">
             <button onClick={() => setSidebarOpen(!sidebarOpen)} className="lg:hidden p-2 text-slate-400 hover:text-white mr-4">
               <Menu className="w-6 h-6" />
             </button>
             
             {/* Functional Modules Navigation */}
             <div className="hidden md:flex space-x-1">
               {[
                 { 
                   id: 'ServiceMgt', label: '服务管理', icon: Layers,
                   subItems: ['服务列表', '部署向导', '配置中心', '服务依赖拓扑']
                 },
                 {
                   id: 'HostMgt', label: '主机管理', icon: Server,
                   subItems: ['主机列表', '资源监控', '集群拓扑', '硬件诊断']
                 },
                 {
                   id: 'TagMgt', label: '标签管理', icon: Tags,
                   subItems: ['标签分类', '标签管理']
                 },
                 {
                   id: 'DataMart', label: '数据集市', icon: Database,
                   subItems: ['数据目录', '血缘分析', '质量报告']
                 },
                 { 
                   id: 'SecurityMgt', label: '安全管理', icon: Shield,
                   subItems: ['策略管理', '审计日志', '密钥管理']
                 },
                 { 
                   id: 'OpsMgt', label: '运维管理', icon: Activity,
                   subItems: ['实时监控', '任务调度', '告警中心']
                 },
                 { 
                   id: 'AIOps', label: 'AIOps', icon: BrainCircuit,
                   subItems: ['智能分析', '根因定位', '预测视图']
                 },
                 { 
                   id: 'UserMgt', label: '用户管理', icon: Users,
                   subItems: ['用户列表', '角色管理', '租户配置', '操作记录']
                 },
               ].map(item => (
                <div key={item.id} className="relative group">
                  <button
                    onClick={() => handleSidebarClick(item.id)}
                    className={cn(
                       "flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all",
                       activeView === item.id 
                         ? "bg-[#00ff9d]/10 text-[#00ff9d]" 
                         : "text-slate-400 hover:text-white hover:bg-white/5"
                     )}
                   >
                     <item.icon className="w-4 h-4 mr-2" />
                     {item.label}
                     <ChevronDown className="w-3 h-3 ml-1 opacity-50 group-hover:opacity-100 transition-opacity" />
                   </button>
                   
                   {/* Dropdown Menu */}
                   <div className="absolute left-0 top-full pt-1 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                     <div className="bg-[#0f172a] border border-white/10 rounded-lg shadow-xl shadow-black/50 py-1.5 min-w-[120px]">
                       {item.subItems.map(sub => (
                         <button 
                           key={sub}
                           onClick={() => {
                             setActiveView(item.id);
                             setActiveSubView(sub);
                           }}
                           className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-[#00ff9d]/10 hover:text-[#00ff9d] transition-colors"
                         >
                           {sub}
                         </button>
                       ))}
                     </div>
                   </div>
                 </div>
               ))}
             </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Service Install Wizard Shortcut */}
            <button 
              onClick={() => {
                setActiveView('ServiceMgt');
                setActiveSubView('部署向导');
              }}
              className="flex items-center px-3 py-1.5 bg-gradient-to-r from-[#38bdf8] to-blue-600 rounded-lg text-xs font-bold text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 transition-all mr-2">
              <Zap className="w-3 h-3 mr-1.5" />
              Install Wizard
            </button>

            <div className="hidden xl:flex relative items-center w-64" ref={searchRef}>
              <div className="flex items-center bg-[#0f172a] border border-white/10 rounded-full px-4 py-1.5 w-full focus-within:border-[#00ff9d]/50 focus-within:ring-1 focus-within:ring-[#00ff9d]/20 transition-all">
                <Search className="w-4 h-4 text-slate-400" />
                <input 
                  type="text" 
                  placeholder="Search..." 
                  className="w-full bg-transparent border-none text-sm text-white placeholder-slate-500 focus:ring-0 ml-2"
                  value={searchQuery}
                  onChange={(e) => handleSearch(e.target.value)}
                  onFocus={() => { if(searchQuery) setShowSearch(true); }}
                />
              </div>

              {/* Global Search Dropdown */}
              {showSearch && searchResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-[#0f172a] border border-white/10 rounded-xl shadow-2xl shadow-black/50 z-50 overflow-hidden max-h-80 overflow-y-auto custom-scrollbar">
                  {searchResults.map(result => (
                    <button
                      key={result.id}
                      onClick={() => handleSearchResultClick(result)}
                      className="w-full text-left px-4 py-3 hover:bg-white/5 border-b border-white/5 last:border-0 flex items-center group transition-colors"
                    >
                      <div className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center mr-3 shrink-0",
                        result.type === 'Service' ? "bg-blue-500/10 text-blue-500" :
                        result.type === 'Host' ? "bg-purple-500/10 text-purple-500" :
                        result.type === 'Security' ? "bg-amber-500/10 text-amber-500" :
                        result.type === 'Alert' ? "bg-rose-500/10 text-rose-500" :
                        "bg-[#00ff9d]/10 text-[#00ff9d]"
                      )}>
                        {result.type === 'Service' && <Layers className="w-4 h-4" />}
                        {result.type === 'Host' && <Server className="w-4 h-4" />}
                        {result.type === 'Data' && <Database className="w-4 h-4" />}
                        {result.type === 'Security' && <Shield className="w-4 h-4" />}
                        {result.type === 'Alert' && <AlertTriangle className="w-4 h-4" />}
                      </div>
                      <div>
                        <div className="text-sm font-bold text-white group-hover:text-[#00ff9d] transition-colors">{result.name}</div>
                        <div className="text-xs text-slate-500">{result.detail}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="relative" ref={notifRef}>
              <button 
                onClick={() => setShowNotifications(!showNotifications)}
                className="relative p-2 text-slate-400 hover:text-white hover:bg-white/5 rounded-full transition-colors"
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-2 right-2 w-2 h-2 bg-[#00ff9d] rounded-full shadow-[0_0_8px_#00ff9d]"></span>
              </button>
              
              {/* Notification Dropdown */}
              {showNotifications && (
                <div className="absolute right-0 top-full mt-2 w-80 bg-[#0f172a] border border-white/10 rounded-xl shadow-2xl shadow-black/50 z-50 overflow-hidden">
                  <div className="p-3 border-b border-white/10 flex items-center justify-between bg-white/5">
                    <span className="font-bold text-white">通知中心</span>
                    <span className="text-xs text-[#00ff9d] cursor-pointer hover:underline">全部已读</span>
                  </div>
                  <div className="max-h-64 overflow-y-auto custom-scrollbar">
                    <div className="p-3 border-b border-white/5 hover:bg-white/5 cursor-pointer">
                      <div className="flex items-start">
                        <AlertTriangle className="w-4 h-4 text-amber-500 mr-2 mt-0.5 flex-shrink-0" />
                        <div>
                          <div className="text-sm font-bold text-white">HDFS 存储容量警告</div>
                          <div className="text-xs text-slate-400 mt-1">DataNode-03 磁盘使用率超过 85%</div>
                          <div className="text-[10px] text-slate-500 mt-1">10分钟前</div>
                        </div>
                      </div>
                    </div>
                    <div className="p-3 border-b border-white/5 hover:bg-white/5 cursor-pointer">
                      <div className="flex items-start">
                        <XCircle className="w-4 h-4 text-rose-500 mr-2 mt-0.5 flex-shrink-0" />
                        <div>
                          <div className="text-sm font-bold text-white">YARN NodeManager 离线</div>
                          <div className="text-xs text-slate-400 mt-1">NodeManager-05 心跳丢失</div>
                          <div className="text-[10px] text-slate-500 mt-1">1小时前</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="p-2 text-center border-t border-white/10 bg-white/5 cursor-pointer hover:bg-white/10">
                    <span className="text-xs text-slate-300">查看全部告警</span>
                  </div>
                </div>
              )}
            </div>
            
            <div className="relative flex items-center pl-4 border-l border-white/10" ref={userMenuRef}>
              <button 
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#00ff9d] to-blue-500 p-[1px] hover:shadow-[0_0_10px_rgba(0,255,157,0.3)] transition-shadow"
              >
                 <div className="w-full h-full rounded-full bg-[#020617] flex items-center justify-center">
                    <span className="text-xs font-bold text-white">AD</span>
                 </div>
              </button>

              {/* User Dropdown */}
              {showUserMenu && (
                <div className="absolute right-0 top-full mt-2 w-48 bg-[#0f172a] border border-white/10 rounded-xl shadow-2xl shadow-black/50 z-50 overflow-hidden">
                  <div className="p-4 border-b border-white/10 bg-white/5">
                    <div className="font-bold text-white">Admin User</div>
                    <div className="text-xs text-slate-400">admin@cloudrealm.com</div>
                  </div>
                  <div className="p-2">
                    <button className="w-full text-left px-3 py-2 text-sm text-slate-300 hover:text-white hover:bg-white/5 rounded-lg flex items-center">
                      <Settings className="w-4 h-4 mr-2" /> 个人设置
                    </button>
                    <button className="w-full text-left px-3 py-2 text-sm text-rose-500 hover:bg-rose-500/10 rounded-lg flex items-center mt-1">
                      <LogOut className="w-4 h-4 mr-2" /> 退出登录
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6 custom-scrollbar">
          <div className="max-w-[1600px] mx-auto fade-in">
             {renderContent()}
          </div>
        </main>
      </div>
    </div>
  );
}
