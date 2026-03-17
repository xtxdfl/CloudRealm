import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, Server, Users, LogOut, 
  Database, Bell, Search, Menu, 
  CheckCircle, AlertTriangle, XCircle, Zap, Layers, FileText,
  Shield, Activity, BrainCircuit
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Overview from '../views/Overview';
import HostMgt from '../views/HostMgt';
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

export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeView, setActiveView] = useState('Overview'); // Controls Main Content View
  const [services, setServices] = useState<ServiceSimple[]>([]);

  useEffect(() => {
    fetchServices();
  }, []);

  const fetchServices = async () => {
    try {
      const response = await fetch('/api/services');
      if (response.ok) {
        const data = await response.json();
        // Map backend status to frontend simple status for sidebar
        const mappedServices = data.map((s: any) => ({
            name: s.name,
            status: s.status.toLowerCase()
        }));
        setServices(mappedServices);
      } else {
        // Fallback if API fails
         setServices([
            { name: 'HDFS', status: 'healthy' },
            { name: 'YARN', status: 'healthy' },
            { name: 'HIVE', status: 'warning' },
            { name: 'SPARK', status: 'healthy' },
            { name: 'KAFKA', status: 'healthy' },
         ]);
      }
    } catch (error) {
      console.error('Error fetching services for sidebar:', error);
       // Fallback
       setServices([
        { name: 'HDFS', status: 'healthy' },
        { name: 'YARN', status: 'healthy' },
        { name: 'HIVE', status: 'warning' },
        { name: 'SPARK', status: 'healthy' },
        { name: 'KAFKA', status: 'healthy' },
     ]);
    }
  };

  // Helper to render current view
  const renderContent = () => {
    switch (activeView) {
      case 'Overview': return <Overview onNavigate={setActiveView} />;
      case 'ServiceMgt': return <ServiceMgt />;
      case 'HostMgt': return <HostMgt />;
      case 'DataMart': return <DataMart />;
      case 'SecurityMgt': return <SecurityMgt />;
      case 'OpsMgt': return <OpsMgt />;
      case 'AIOps': return <AIOps />;
      case 'UserMgt': return <UserCenter />;
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

      {/* Sidebar - Ambari Style (Services List) */}
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
              onClick={() => setActiveView('Overview')}
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
                 { id: 'Overview', label: 'Overview', icon: LayoutDashboard },
                 { id: 'ServiceMgt', label: 'Services', icon: Layers },
                 { id: 'HostMgt', label: 'Hosts', icon: Server },
                 { id: 'DataMart', label: 'DataMart', icon: Database },
                 { id: 'SecurityMgt', label: 'Security', icon: Shield },
                 { id: 'OpsMgt', label: 'Ops', icon: Activity },
                 { id: 'AIOps', label: 'AIOps', icon: BrainCircuit },
                 { id: 'UserMgt', label: 'Users', icon: Users },
               ].map(item => (
                 <button
                   key={item.id}
                   onClick={() => setActiveView(item.id)}
                   className={cn(
                     "flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all",
                     activeView === item.id 
                       ? "bg-[#00ff9d]/10 text-[#00ff9d]" 
                       : "text-slate-400 hover:text-white hover:bg-white/5"
                   )}
                 >
                   <item.icon className="w-4 h-4 mr-2" />
                   {item.label}
                 </button>
               ))}
             </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Service Install Wizard Shortcut */}
            <button className="flex items-center px-3 py-1.5 bg-gradient-to-r from-[#38bdf8] to-blue-600 rounded-lg text-xs font-bold text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 transition-all mr-2">
              <Zap className="w-3 h-3 mr-1.5" />
              Install Wizard
            </button>

            <div className="hidden xl:flex items-center bg-[#0f172a] border border-white/10 rounded-full px-4 py-1.5 w-64 focus-within:border-[#00ff9d]/50 focus-within:ring-1 focus-within:ring-[#00ff9d]/20 transition-all">
              <Search className="w-4 h-4 text-slate-400" />
              <input 
                type="text" 
                placeholder="Search..." 
                className="w-full bg-transparent border-none text-sm text-white placeholder-slate-500 focus:ring-0 ml-2"
              />
            </div>

            <button className="relative p-2 text-slate-400 hover:text-white hover:bg-white/5 rounded-full transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-2 right-2 w-2 h-2 bg-[#00ff9d] rounded-full shadow-[0_0_8px_#00ff9d]"></span>
            </button>
            
            <div className="flex items-center pl-4 border-l border-white/10">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#00ff9d] to-blue-500 p-[1px]">
                 <div className="w-full h-full rounded-full bg-[#020617] flex items-center justify-center">
                    <span className="text-xs font-bold text-white">AD</span>
                 </div>
              </div>
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
