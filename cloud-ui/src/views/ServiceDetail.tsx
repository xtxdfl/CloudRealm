import React, { useState, useEffect } from 'react';
import { Activity, CheckCircle, AlertTriangle, XCircle, Play, Square, RotateCcw, Settings, Server } from 'lucide-react';

interface ServiceInfo {
  name: string;
  version: string;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL' | 'STOPPED' | 'UNKNOWN';
  configVersion: string;
  role: string;
  components: string[];
}

const StatusBadge = ({ status }: { status: string }) => {
  const s = status.toUpperCase();
  if (s === 'HEALTHY') return <span className="flex items-center text-[#00ff9d]"><CheckCircle className="w-4 h-4 mr-1" /> Healthy</span>;
  if (s === 'WARNING') return <span className="flex items-center text-amber-500"><AlertTriangle className="w-4 h-4 mr-1" /> Warning</span>;
  if (s === 'STOPPED') return <span className="flex items-center text-slate-500"><XCircle className="w-4 h-4 mr-1" /> Stopped</span>;
  return <span className="flex items-center text-rose-500"><XCircle className="w-4 h-4 mr-1" /> Critical</span>;
};

export default function ServiceDetail({ serviceName }: { serviceName: string }) {
  const [service, setService] = useState<ServiceInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchServiceDetails();
  }, [serviceName]);

  const fetchServiceDetails = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/services/${serviceName}`);
      if (response.ok) {
        const data = await response.json();
        setService(data);
      } else {
        // Fallback or error handling
        console.error('Failed to fetch service details');
        setService({
            name: serviceName,
            version: 'Unknown',
            status: 'UNKNOWN',
            configVersion: 'N/A',
            role: 'Unknown',
            components: []
        });
      }
    } catch (error) {
      console.error('Error fetching service details:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action: 'start' | 'stop' | 'restart') => {
    try {
      const response = await fetch(`/api/services/${serviceName}/${action}`, {
        method: 'POST'
      });
      if (response.ok) {
        fetchServiceDetails();
      }
    } catch (error) {
      console.error(`Error performing ${action}:`, error);
    }
  };

  if (loading) {
    return <div className="text-white">Loading service details...</div>;
  }

  if (!service) {
    return <div className="text-white">Service not found.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center">
            {service.name} 
            <span className="ml-4 text-sm font-normal bg-white/10 px-2 py-0.5 rounded text-slate-300">v{service.version}</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1">{service.role} Service</p>
        </div>
        <div className="flex space-x-2">
           <div className="px-4 py-2 bg-[#020617] border border-white/10 rounded-lg flex items-center">
              <span className="text-slate-400 mr-2">Status:</span>
              <StatusBadge status={service.status} />
           </div>
           <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-300 transition-colors">
             <Settings className="w-5 h-5" />
           </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex space-x-4">
        <button 
          onClick={() => handleAction('start')}
          className="flex-1 py-3 bg-[#00ff9d]/10 border border-[#00ff9d]/20 text-[#00ff9d] rounded-xl flex items-center justify-center hover:bg-[#00ff9d]/20 transition-all font-bold"
        >
          <Play className="w-4 h-4 mr-2" /> Start
        </button>
        <button 
          onClick={() => handleAction('stop')}
          className="flex-1 py-3 bg-white/5 border border-white/10 text-white rounded-xl flex items-center justify-center hover:bg-white/10 transition-all font-bold"
        >
          <Square className="w-4 h-4 mr-2 text-rose-500" /> Stop
        </button>
        <button 
          onClick={() => handleAction('restart')}
          className="flex-1 py-3 bg-white/5 border border-white/10 text-white rounded-xl flex items-center justify-center hover:bg-white/10 transition-all font-bold"
        >
          <RotateCcw className="w-4 h-4 mr-2 text-[#38bdf8]" /> Restart
        </button>
      </div>

      {/* Metrics Placeholders (Mock for now as backend doesn't provide metrics yet) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {['Heap Usage', 'Total Files', 'Under Replicated', 'DataNodes Live'].map(metric => (
          <div key={metric} className="glass-panel p-4 rounded-xl">
            <div className="text-slate-500 text-xs uppercase font-bold">{metric}</div>
            <div className="text-xl font-bold text-white mt-1">
              {Math.floor(Math.random() * 1000)}
            </div>
            <div className="w-full h-1 bg-white/10 rounded-full mt-2">
               <div className="h-full bg-[#38bdf8]" style={{ width: `${Math.random() * 100}%` }}></div>
            </div>
          </div>
        ))}
      </div>

      {/* Component List */}
      <div className="glass-panel p-6 rounded-2xl">
        <h3 className="text-lg font-bold text-white mb-4">Components</h3>
        <table className="w-full text-left text-sm">
          <thead className="text-slate-500 border-b border-white/5">
            <tr>
              <th className="pb-2 pl-2">Name</th>
              <th className="pb-2">Host</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {service.components && service.components.length > 0 ? (
                service.components.map((comp, i) => (
                <tr key={i} className="hover:bg-white/5 transition-colors">
                    <td className="py-3 pl-2 text-white font-medium">{comp}</td>
                    <td className="py-3 text-slate-400">host-0{i+1}.cloudrealm.local</td>
                    <td className="py-3"><StatusBadge status={service.status} /></td>
                </tr>
                ))
            ) : (
                <tr>
                    <td colSpan={3} className="py-3 text-slate-500 text-center">No components found</td>
                </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
