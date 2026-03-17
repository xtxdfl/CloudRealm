import React, { useState, useEffect } from 'react';
import { Layers, Play, Settings, GitBranch, Share2, Box, RotateCcw, Power } from 'lucide-react';

interface ServiceInfo {
  name: string;
  version: string;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL' | 'STOPPED' | 'UNKNOWN';
  configVersion: string;
  role: string;
  components: string[];
}

interface ServiceStats {
  total: number;
  healthy: number;
  warning: number;
  stopped: number;
}

export default function ServiceMgt() {
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [stats, setStats] = useState<ServiceStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [servicesRes, statsRes] = await Promise.all([
        fetch('/api/services').then(res => res.json()),
        fetch('/api/services/stats').then(res => res.json())
      ]);
      setServices(servicesRes);
      setStats(statsRes);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching service data:', error);
      // Fallback mock data if API fails
      if (services.length === 0) {
        setServices([
          { name: 'HDFS', version: '3.3.6', status: 'HEALTHY', configVersion: 'v24', role: 'Storage', components: [] },
          { name: 'YARN', version: '3.3.6', status: 'HEALTHY', configVersion: 'v12', role: 'Compute', components: [] },
          { name: 'HIVE', version: '3.1.3', status: 'WARNING', configVersion: 'v8', role: 'Database', components: [] },
        ]);
        setStats({ total: 3, healthy: 2, warning: 1, stopped: 0 });
      }
      setLoading(false);
    }
  };

  const handleAction = async (serviceName: string, action: 'start' | 'stop' | 'restart') => {
    try {
      const response = await fetch(`/api/services/${serviceName}/${action}`, {
        method: 'POST'
      });
      if (response.ok) {
        // Refresh data immediately
        fetchData();
      } else {
        console.error(`Failed to ${action} service ${serviceName}`);
      }
    } catch (error) {
      console.error(`Error performing ${action} on ${serviceName}:`, error);
    }
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

  return (
    <div className="space-y-6">
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
            <Layers className="w-5 h-5 mr-2 text-[#00ff9d]" /> 服务管理控制台
          </h3>
          <div className="flex space-x-2">
            <button className="px-3 py-1.5 bg-[#00ff9d]/10 text-[#00ff9d] rounded-lg text-xs font-bold hover:bg-[#00ff9d]/20 flex items-center">
              <Play className="w-3 h-3 mr-1" /> Deploy New Service
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
                    <div className="flex space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
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
                      <button className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                        <Settings className="w-4 h-4" />
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
}
