import React from 'react';
import { Layers, Play, Settings, GitBranch, Share2, Box, RotateCcw } from 'lucide-react';

export default function ServiceMgt() {
  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Services', value: '18', color: '#38bdf8' },
          { label: 'Healthy', value: '15', color: '#00ff9d' },
          { label: 'Warning', value: '1', color: '#f59e0b' },
          { label: 'Stopped', value: '2', color: '#f43f5e' },
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
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Config Version</th>
                <th className="px-6 py-3 rounded-r-lg">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {[
                { name: 'HDFS', ver: '3.3.6', status: 'Healthy', conf: 'v24' },
                { name: 'YARN', ver: '3.3.6', status: 'Healthy', conf: 'v12' },
                { name: 'HIVE', ver: '3.1.3', status: 'Warning', conf: 'v8' },
                { name: 'SPARK', ver: '3.5.0', status: 'Healthy', conf: 'v3' },
                { name: 'KAFKA', ver: '3.6.0', status: 'Healthy', conf: 'v15' },
              ].map(svc => (
                <tr key={svc.name} className="hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-4 font-bold text-white flex items-center">
                    <div className={`w-2 h-2 rounded-full mr-3 ${svc.status === 'Healthy' ? 'bg-[#00ff9d] shadow-[0_0_5px_#00ff9d]' : 'bg-amber-500 shadow-[0_0_5px_#f59e0b]'}`}></div>
                    {svc.name}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-400">{svc.ver}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                      svc.status === 'Healthy' ? 'bg-[#00ff9d]/10 text-[#00ff9d] border-[#00ff9d]/20' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    }`}>
                      {svc.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-6 py-4 flex items-center">
                    <span className="font-mono text-xs bg-white/10 px-1.5 rounded mr-2">{svc.conf}</span>
                    <GitBranch className="w-3 h-3 text-slate-500 cursor-pointer hover:text-white" />
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-[#38bdf8]"><Settings className="w-4 h-4" /></button>
                      <button className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-[#00ff9d]"><RotateCcw className="w-4 h-4" /></button>
                      <button className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-rose-500"><Box className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
