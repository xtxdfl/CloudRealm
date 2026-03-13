import React from 'react';
import { Activity, CheckCircle, AlertTriangle, XCircle, Play, Square, RotateCcw, Settings } from 'lucide-react';

const StatusBadge = ({ status }: { status: string }) => {
  if (status === 'healthy') return <span className="flex items-center text-[#00ff9d]"><CheckCircle className="w-4 h-4 mr-1" /> Healthy</span>;
  if (status === 'warning') return <span className="flex items-center text-amber-500"><AlertTriangle className="w-4 h-4 mr-1" /> Warning</span>;
  return <span className="flex items-center text-rose-500"><XCircle className="w-4 h-4 mr-1" /> Critical</span>;
};

export default function ServiceDetail({ serviceName }: { serviceName: string }) {
  // Mock data based on service name
  const isRunning = serviceName !== 'FALCON'; 
  const status = isRunning ? 'healthy' : 'stopped';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center">
            {serviceName} 
            <span className="ml-4 text-sm font-normal bg-white/10 px-2 py-0.5 rounded text-slate-300">v3.3.6</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1">Service Description / Role Information</p>
        </div>
        <div className="flex space-x-2">
           <div className="px-4 py-2 bg-[#020617] border border-white/10 rounded-lg flex items-center">
              <span className="text-slate-400 mr-2">Status:</span>
              <StatusBadge status={status} />
           </div>
           <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-300 transition-colors">
             <Settings className="w-5 h-5" />
           </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex space-x-4">
        <button className="flex-1 py-3 bg-[#00ff9d]/10 border border-[#00ff9d]/20 text-[#00ff9d] rounded-xl flex items-center justify-center hover:bg-[#00ff9d]/20 transition-all font-bold">
          <Play className="w-4 h-4 mr-2" /> Start
        </button>
        <button className="flex-1 py-3 bg-white/5 border border-white/10 text-white rounded-xl flex items-center justify-center hover:bg-white/10 transition-all font-bold">
          <Square className="w-4 h-4 mr-2 text-rose-500" /> Stop
        </button>
        <button className="flex-1 py-3 bg-white/5 border border-white/10 text-white rounded-xl flex items-center justify-center hover:bg-white/10 transition-all font-bold">
          <RotateCcw className="w-4 h-4 mr-2 text-[#38bdf8]" /> Restart
        </button>
      </div>

      {/* Metrics Placeholders */}
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
            {[1, 2, 3].map(i => (
              <tr key={i} className="hover:bg-white/5 transition-colors">
                <td className="py-3 pl-2 text-white font-medium">{serviceName}_COMPONENT_{i}</td>
                <td className="py-3 text-slate-400">host-0{i}.cloudrealm.local</td>
                <td className="py-3"><StatusBadge status="healthy" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
