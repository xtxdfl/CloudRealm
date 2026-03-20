import React, { useState } from 'react';
import { 
  Users, Shield, Fingerprint, History, Link2, Key, Search, ExternalLink,
  Plus, Edit, Trash2, Settings, Database, HardDrive, Cpu
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Mock Data
const roles = [
  { id: 1, name: 'Super Admin', description: 'Full access to all resources', usersCount: 2, permissions: ['ALL'] },
  { id: 2, name: 'Data Engineer', description: 'Can manage data pipelines and tables', usersCount: 15, permissions: ['READ_DATA', 'WRITE_DATA', 'SUBMIT_JOB'] },
  { id: 3, name: 'Data Analyst', description: 'Read-only access to specific datasets', usersCount: 24, permissions: ['READ_DATA', 'RUN_QUERY'] },
  { id: 4, name: 'Viewer', description: 'View dashboards only', usersCount: 50, permissions: ['VIEW_DASHBOARD'] },
];

const tenants = [
  { id: 1, name: 'Finance Dept', description: 'Financial data processing', queue: 'root.finance', quotaCores: 100, quotaMem: '400GB', quotaStorage: '50TB', status: 'Active' },
  { id: 2, name: 'Marketing Dept', description: 'User behavior analysis', queue: 'root.marketing', quotaCores: 200, quotaMem: '800GB', quotaStorage: '100TB', status: 'Active' },
  { id: 3, name: 'R&D Team', description: 'Development and testing', queue: 'root.dev', quotaCores: 50, quotaMem: '200GB', quotaStorage: '10TB', status: 'Active' },
];

const auditLogs = Array.from({ length: 15 }).map((_, i) => ({
  id: i,
  user: ['Admin', 'Bob', 'Alice', 'Dave'][i % 4],
  action: ['Create User', 'Delete Table', 'Update Quota', 'Grant Role'][i % 4],
  resource: ['user_01', 'db_sales.tbl_orders', 'root.finance', 'role_analyst'][i % 4],
  time: `2023-10-27 10:${i + 10}:00`,
  status: i % 5 === 0 ? 'Failed' : 'Success',
  details: 'Operation executed via UI'
}));

export default function UserCenter({ activeSubView }: { activeSubView?: string }) {
  const [searchTerm, setSearchTerm] = useState('');

  const renderRoleAssignment = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Shield className="w-5 h-5 mr-2 text-[#00ff9d]" /> 角色分配 (RBAC)
          </h3>
          <button className="px-3 py-1.5 bg-[#00ff9d] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#00e68e] flex items-center">
             <Plus className="w-4 h-4 mr-1" /> Create Role
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4">
           {roles.map(role => (
              <div key={role.id} className="p-4 bg-white/5 border border-white/5 rounded-xl hover:border-white/10 transition-all">
                 <div className="flex justify-between items-start">
                    <div>
                       <div className="flex items-center">
                          <h4 className="font-bold text-white mr-3">{role.name}</h4>
                          <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded text-slate-300">{role.usersCount} Users</span>
                       </div>
                       <p className="text-xs text-slate-400 mt-1">{role.description}</p>
                       <div className="flex flex-wrap gap-2 mt-3">
                          {role.permissions.map(perm => (
                             <span key={perm} className="text-[10px] px-2 py-1 bg-[#38bdf8]/10 text-[#38bdf8] rounded border border-[#38bdf8]/20">
                                {perm}
                             </span>
                          ))}
                       </div>
                    </div>
                    <div className="flex space-x-2">
                       <button className="p-2 hover:bg-white/10 rounded text-slate-400 hover:text-white">
                          <Edit className="w-4 h-4" />
                       </button>
                       <button className="p-2 hover:bg-rose-500/10 rounded text-slate-400 hover:text-rose-500">
                          <Trash2 className="w-4 h-4" />
                       </button>
                    </div>
                 </div>
              </div>
           ))}
        </div>
      </div>
    </div>
  );

  const renderTenantConfig = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Users className="w-5 h-5 mr-2 text-[#a855f7]" /> 租户配置 (Multi-Tenancy)
          </h3>
          <button className="px-3 py-1.5 bg-[#a855f7] text-white rounded-lg text-xs font-bold hover:bg-[#9333ea] flex items-center">
             <Plus className="w-4 h-4 mr-1" /> Add Tenant
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
           {tenants.map(tenant => (
              <div key={tenant.id} className="p-6 bg-white/5 border border-white/5 rounded-xl hover:border-white/10 transition-all">
                 <div className="flex justify-between items-start mb-4">
                    <div>
                       <h4 className="text-lg font-bold text-white">{tenant.name}</h4>
                       <div className="text-xs text-slate-400 mt-1">{tenant.description}</div>
                    </div>
                    <span className="px-2 py-1 bg-[#00ff9d]/10 text-[#00ff9d] text-[10px] font-bold rounded border border-[#00ff9d]/20">
                       {tenant.status}
                    </span>
                 </div>
                 
                 <div className="space-y-3">
                    <div className="flex items-center justify-between text-xs p-2 bg-[#020617] rounded-lg">
                       <span className="text-slate-400 flex items-center"><Database className="w-3 h-3 mr-2" /> YARN Queue</span>
                       <span className="text-white font-mono">{tenant.queue}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs p-2 bg-[#020617] rounded-lg">
                       <span className="text-slate-400 flex items-center"><Cpu className="w-3 h-3 mr-2" /> Max Cores</span>
                       <span className="text-white font-mono">{tenant.quotaCores} vCores</span>
                    </div>
                    <div className="flex items-center justify-between text-xs p-2 bg-[#020617] rounded-lg">
                       <span className="text-slate-400 flex items-center"><HardDrive className="w-3 h-3 mr-2" /> Max Memory</span>
                       <span className="text-white font-mono">{tenant.quotaMem}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs p-2 bg-[#020617] rounded-lg">
                       <span className="text-slate-400 flex items-center"><HardDrive className="w-3 h-3 mr-2" /> HDFS Storage</span>
                       <span className="text-white font-mono">{tenant.quotaStorage}</span>
                    </div>
                 </div>

                 <div className="mt-6 pt-4 border-t border-white/5 flex justify-end space-x-3">
                    <button className="text-xs text-slate-400 hover:text-white flex items-center">
                       <Settings className="w-3 h-3 mr-1" /> Configure
                    </button>
                    <button className="text-xs text-slate-400 hover:text-white flex items-center">
                       <Users className="w-3 h-3 mr-1" /> Members
                    </button>
                 </div>
              </div>
           ))}
        </div>
      </div>
    </div>
  );

  const renderOperationRecords = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Fingerprint className="w-5 h-5 mr-2 text-[#f59e0b]" /> 操作记录 (Audit Logs)
          </h3>
          <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
             <Search className="w-4 h-4 text-slate-500 mr-2" />
             <input 
               type="text" 
               placeholder="Search logs..." 
               className="bg-transparent border-none text-xs text-white focus:ring-0 w-full"
               value={searchTerm}
               onChange={(e) => setSearchTerm(e.target.value)}
             />
          </div>
        </div>

        <div className="overflow-x-auto">
           <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 uppercase bg-white/5">
                 <tr>
                    <th className="px-6 py-3 rounded-l-lg">Time</th>
                    <th className="px-6 py-3">User</th>
                    <th className="px-6 py-3">Action</th>
                    <th className="px-6 py-3">Resource</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3 rounded-r-lg">Details</th>
                 </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                 {auditLogs.map(log => (
                    <tr key={log.id} className="hover:bg-white/5 transition-colors">
                       <td className="px-6 py-4 font-mono text-xs text-slate-400">{log.time}</td>
                       <td className="px-6 py-4 font-bold text-white">{log.user}</td>
                       <td className="px-6 py-4 text-[#38bdf8]">{log.action}</td>
                       <td className="px-6 py-4 font-mono text-xs">{log.resource}</td>
                       <td className="px-6 py-4">
                          <span className={cn(
                             "px-2 py-0.5 rounded text-[10px] font-bold",
                             log.status === 'Success' ? "bg-[#00ff9d]/10 text-[#00ff9d]" : "bg-rose-500/10 text-rose-500"
                          )}>
                             {log.status}
                          </span>
                       </td>
                       <td className="px-6 py-4 text-xs text-slate-500">{log.details}</td>
                    </tr>
                 ))}
              </tbody>
           </table>
        </div>
      </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
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

  return (
    <>
      {activeSubView === '角色分配' && renderRoleAssignment()}
      {activeSubView === '租户配置' && renderTenantConfig()}
      {activeSubView === '操作记录' && renderOperationRecords()}
      {(!activeSubView || activeSubView === '') && renderOverview()}
    </>
  );
}
