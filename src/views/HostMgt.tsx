import React from 'react';
import { Server, UserPlus, Play, Square, RefreshCcw, ShieldCheck, ShoppingCart, Settings2 } from 'lucide-react';

export default function HostMgt() {
  const hosts = [
    { name: 'Master01', ip: '192.168.1.10', status: 'Running', cores: 8, mem: '32GB', role: 'Control Plane' },
    { name: 'Worker01', ip: '192.168.1.11', status: 'Running', cores: 16, mem: '64GB', role: 'Worker' },
    { name: 'Worker02', ip: '192.168.1.12', status: 'Running', cores: 16, mem: '64GB', role: 'Worker' },
    { name: 'Worker03', ip: '192.168.1.13', status: 'Maintenance', cores: 16, mem: '64GB', role: 'Worker' },
  ];

  return (
    <div className="space-y-6">
      {/* 功能工具栏 */}
      <div className="flex flex-wrap gap-3">
        <button className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold flex items-center hover:bg-[#00e68e] transition-all">
          <UserPlus className="w-4 h-4 mr-2" /> 添加主机
        </button>
        <button className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/10 flex items-center transition-all">
          <Play className="w-4 h-4 mr-2 text-[#00ff9d]" /> 批量启动
        </button>
        <button className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/10 flex items-center transition-all">
          <Square className="w-4 h-4 mr-2 text-rose-500" /> 批量停止
        </button>
        <button className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/10 flex items-center transition-all">
          <RefreshCcw className="w-4 h-4 mr-2 text-[#38bdf8]" /> 批量重启
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 1. 主机管理列表 */}
        <div className="lg:col-span-2 glass-panel rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-white/5 flex justify-between items-center">
            <h3 className="font-bold text-white flex items-center">
              <Server className="w-5 h-5 mr-2 text-[#38bdf8]" /> 主机列表
            </h3>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-6 py-3">主机名 / IP</th>
                <th className="px-6 py-3">角色</th>
                <th className="px-6 py-3">资源 (C/M)</th>
                <th className="px-6 py-3">状态</th>
                <th className="px-6 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {hosts.map(host => (
                <tr key={host.name} className="hover:bg-white/5 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-white">{host.name}</div>
                    <div className="text-xs text-slate-500">{host.ip}</div>
                  </td>
                  <td className="px-6 py-4 text-xs">{host.role}</td>
                  <td className="px-6 py-4 text-xs font-mono">{host.cores}C / {host.mem}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      host.status === 'Running' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    }`}>
                      {host.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button className="text-[#38bdf8] hover:underline text-xs">详情</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 2. Agent & Worker 管理 */}
        <div className="space-y-6">
          <div className="glass-panel p-6 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center">
              <ShieldCheck className="w-5 h-5 mr-2 text-[#00ff9d]" /> Agent 管理
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-white/5">
                <span className="text-sm">运行状态</span>
                <span className="text-xs text-[#00ff9d] font-bold">142 Active</span>
              </div>
              <button className="w-full py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10 transition-all">
                版本热升级 (JMX/Exporter)
              </button>
              <button className="w-full py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10 transition-all">
                配置模板库
              </button>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center">
              <ShoppingCart className="w-5 h-5 mr-2 text-amber-500" /> 插件市场
            </h3>
            <p className="text-xs text-slate-500 mb-4">扩展集群监控能力，一键安装 Exporter</p>
            <div className="grid grid-cols-2 gap-2">
              {['MySQL Exp', 'Redis Exp', 'Nginx Exp', 'ES Exp'].map(plugin => (
                <div key={plugin} className="p-2 bg-white/5 border border-white/5 rounded text-[10px] text-center hover:border-[#38bdf8] cursor-pointer">
                  {plugin}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
