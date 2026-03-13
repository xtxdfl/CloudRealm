import React from 'react';
import { Users, Shield, Fingerprint, History, Link2, Key, Search, ExternalLink } from 'lucide-react';

export default function UserCenter() {
  return (
    <div className="space-y-6">
      {/* 1. 用户与认证管理 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
              <Users className="w-5 h-5 mr-2 text-[#38bdf8]" /> 用户管理
            </h3>
            <button className="px-4 py-2 bg-[#38bdf8] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#0ea5e9] flex items-center">
              <Link2 className="w-4 h-4 mr-2" /> OAuth 集成配置
            </button>
          </div>
          
          <div className="relative mb-6">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input 
              type="text" 
              placeholder="Search users by name, role or email..." 
              className="w-full pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white focus:border-[#38bdf8] outline-none"
            />
          </div>

          <div className="space-y-3">
            {[
              { name: 'Admin User', role: 'Super Admin', status: 'Active', lastLogin: 'Just now' },
              { name: 'Data Engineer 01', role: 'Editor', status: 'Active', lastLogin: '2h ago' },
              { name: 'Security Auditor', role: 'Viewer', status: 'Inactive', lastLogin: '3d ago' },
            ].map(user => (
              <div key={user.name} className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-all">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#38bdf8] to-[#00ff9d] flex items-center justify-center font-bold text-[#020617]">
                    {user.name[0]}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">{user.name}</div>
                    <div className="text-[10px] text-slate-500">{user.role} • {user.lastLogin}</div>
                  </div>
                </div>
                <button className="text-slate-400 hover:text-white text-xs">编辑权限</button>
              </div>
            ))}
          </div>
        </div>

        {/* 2. 权限策略 (Ranger/RBAC) */}
        <div className="space-y-6">
          <div className="glass-panel p-6 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center">
              <Shield className="w-5 h-5 mr-2 text-[#00ff9d]" /> 权限策略
            </h3>
            <div className="space-y-4">
              <div className="p-3 bg-white/5 rounded-lg border border-[#00ff9d]/20 flex items-center justify-between">
                <div className="flex items-center">
                  <Shield className="w-4 h-4 mr-3 text-[#00ff9d]" />
                  <span className="text-xs">Ranger 集成状态</span>
                </div>
                <span className="text-[10px] text-[#00ff9d] font-bold">CONNECTED</span>
              </div>
              <p className="text-[10px] text-slate-500">RBAC 模型控制资源访问权限</p>
              <button className="w-full py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10 transition-all flex items-center justify-center">
                <ExternalLink className="w-3 h-3 mr-2" /> 打开 Ranger UI
              </button>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center">
              <Fingerprint className="w-5 h-5 mr-2 text-amber-500" /> 操作审计
            </h3>
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="text-[10px] text-slate-400 pb-2 border-b border-white/5 last:border-0">
                  <div className="flex justify-between mb-1">
                    <span className="text-slate-300 font-bold">Admin</span>
                    <span>11:2{i} AM</span>
                  </div>
                  <div>Modified HDFS config (dfs.replication)</div>
                </div>
              ))}
              <button className="w-full py-2 bg-[#38bdf8]/10 text-[#38bdf8] rounded-lg text-[10px] font-bold hover:bg-[#38bdf8]/20 mt-2">
                查看完整审计轨迹
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
