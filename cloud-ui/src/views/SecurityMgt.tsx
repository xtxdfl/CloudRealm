import React, { useState } from 'react';
import { 
  Shield, Lock, Key, Eye, FileText, UserCheck, AlertOctagon, 
  Search, Plus, MoreHorizontal, CheckCircle, XCircle, AlertTriangle,
  Filter, Download, RefreshCw
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Policy {
  id: number;
  name: string;
  service: string;
  resource: string;
  users: string[];
  permissions: string[];
  status: 'Enabled' | 'Disabled';
}

interface AuditLog {
  id: number;
  time: string;
  user: string;
  service: string;
  operation: string;
  resource: string;
  result: 'Success' | 'Denied' | 'Failed';
  clientIp: string;
}

interface KeyEntry {
  id: number;
  name: string;
  version: number;
  algorithm: string;
  created: string;
  expires: string;
  status: 'Active' | 'Rotated' | 'Revoked';
}

export default function SecurityMgt({ activeSubView }: { activeSubView?: string }) {
  const [searchTerm, setSearchTerm] = useState('');
  
  // Mock Data
  const [policies] = useState<Policy[]>([
    { id: 1, name: 'HDFS Admin Access', service: 'HDFS', resource: '/', users: ['admin', 'hdfs'], permissions: ['ALL'], status: 'Enabled' },
    { id: 2, name: 'Finance Data Read', service: 'HIVE', resource: 'db_finance.*', users: ['group_finance'], permissions: ['SELECT'], status: 'Enabled' },
    { id: 3, name: 'Dev Team Scratch', service: 'HDFS', resource: '/tmp/dev', users: ['group_dev'], permissions: ['READ', 'WRITE'], status: 'Enabled' },
    { id: 4, name: 'Kafka Topic Produce', service: 'KAFKA', resource: 'topic_logs', users: ['app_logger'], permissions: ['PUBLISH'], status: 'Disabled' },
  ]);

  const [logs] = useState<AuditLog[]>([
    { id: 1, time: '2023-10-27 10:23:45', user: 'admin', service: 'HDFS', operation: 'Mkdirs', resource: '/user/new_user', result: 'Success', clientIp: '192.168.1.10' },
    { id: 2, time: '2023-10-27 10:21:12', user: 'bob', service: 'HIVE', operation: 'Select', resource: 'db_finance.salary', result: 'Denied', clientIp: '192.168.1.105' },
    { id: 3, time: '2023-10-27 10:15:30', user: 'spark_user', service: 'YARN', operation: 'SubmitApp', resource: 'cluster', result: 'Success', clientIp: '192.168.1.50' },
    { id: 4, time: '2023-10-27 09:55:00', user: 'alice', service: 'KAFKA', operation: 'Consume', resource: 'topic_sales', result: 'Success', clientIp: '192.168.1.102' },
    { id: 5, time: '2023-10-27 09:40:22', user: 'unknown', service: 'KNOX', operation: 'Login', resource: 'gateway', result: 'Failed', clientIp: '203.0.113.5' },
  ]);

  const [keys] = useState<KeyEntry[]>([
    { id: 1, name: 'hdfs/nn.cloudrealm.com', version: 3, algorithm: 'AES-256', created: '2023-09-01', expires: '2024-09-01', status: 'Active' },
    { id: 2, name: 'hive/server.cloudrealm.com', version: 2, algorithm: 'AES-256', created: '2023-08-15', expires: '2024-08-15', status: 'Active' },
    { id: 3, name: 'spark/history.cloudrealm.com', version: 1, algorithm: 'RC4-HMAC', created: '2023-01-10', expires: '2024-01-10', status: 'Rotated' },
    { id: 4, name: 'kafka/broker.cloudrealm.com', version: 4, algorithm: 'AES-256', created: '2023-10-01', expires: '2024-10-01', status: 'Active' },
  ]);

  const renderPolicyManagement = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Shield className="w-5 h-5 mr-2 text-[#00ff9d]" /> 策略管理
          </h3>
          <div className="flex space-x-3">
             <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
                <Search className="w-4 h-4 text-slate-500 mr-2" />
                <input 
                  type="text" 
                  placeholder="Search policies..." 
                  className="bg-transparent border-none text-xs text-white focus:ring-0 w-full"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
             </div>
             <button className="px-3 py-1.5 bg-[#00ff9d] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#00e68e] flex items-center">
                <Plus className="w-4 h-4 mr-1" /> Add Policy
             </button>
          </div>
        </div>
        
        <div className="overflow-x-auto">
           <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 uppercase bg-white/5">
                 <tr>
                    <th className="px-4 py-3 rounded-l-lg">Policy Name</th>
                    <th className="px-4 py-3">Service</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Users / Groups</th>
                    <th className="px-4 py-3">Permissions</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 rounded-r-lg">Actions</th>
                 </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                 {policies.map(policy => (
                    <tr key={policy.id} className="hover:bg-white/5 transition-colors">
                       <td className="px-4 py-3 font-medium text-white">{policy.name}</td>
                       <td className="px-4 py-3">
                          <span className="px-2 py-1 rounded text-[10px] bg-white/10 text-slate-300 border border-white/10">
                             {policy.service}
                          </span>
                       </td>
                       <td className="px-4 py-3 text-slate-400 font-mono text-xs">{policy.resource}</td>
                       <td className="px-4 py-3 text-slate-300">
                          {policy.users.join(', ')}
                       </td>
                       <td className="px-4 py-3">
                          <div className="flex gap-1 flex-wrap">
                             {policy.permissions.map(perm => (
                                <span key={perm} className="text-[10px] px-1.5 py-0.5 bg-[#38bdf8]/10 text-[#38bdf8] rounded">
                                   {perm}
                                </span>
                             ))}
                          </div>
                       </td>
                       <td className="px-4 py-3">
                          <span className={cn(
                             "text-[10px] px-2 py-1 rounded-full font-bold",
                             policy.status === 'Enabled' ? "bg-[#00ff9d]/10 text-[#00ff9d]" : "bg-slate-700 text-slate-400"
                          )}>
                             {policy.status}
                          </span>
                       </td>
                       <td className="px-4 py-3 text-slate-500">
                          <button className="p-1 hover:text-white hover:bg-white/10 rounded">
                             <MoreHorizontal className="w-4 h-4" />
                          </button>
                       </td>
                    </tr>
                 ))}
              </tbody>
           </table>
        </div>
      </div>
    </div>
  );

  const renderAuditLogs = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Eye className="w-5 h-5 mr-2 text-[#38bdf8]" /> 安全审计日志
          </h3>
          <div className="flex space-x-3">
             <button className="px-3 py-1.5 bg-white/5 text-slate-300 rounded-lg text-xs hover:text-white flex items-center">
                <Filter className="w-3 h-3 mr-1" /> Filter
             </button>
             <button className="px-3 py-1.5 bg-white/5 text-slate-300 rounded-lg text-xs hover:text-white flex items-center">
                <Download className="w-3 h-3 mr-1" /> Export
             </button>
             <button className="px-3 py-1.5 bg-white/5 text-slate-300 rounded-lg text-xs hover:text-white flex items-center">
                <RefreshCw className="w-3 h-3 mr-1" /> Refresh
             </button>
          </div>
        </div>
        
        <div className="overflow-x-auto">
           <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 uppercase bg-white/5">
                 <tr>
                    <th className="px-4 py-3 rounded-l-lg">Time</th>
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Service</th>
                    <th className="px-4 py-3">Operation</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Client IP</th>
                    <th className="px-4 py-3 rounded-r-lg">Result</th>
                 </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                 {logs.map(log => (
                    <tr key={log.id} className="hover:bg-white/5 transition-colors">
                       <td className="px-4 py-3 text-slate-400 font-mono text-xs">{log.time}</td>
                       <td className="px-4 py-3 font-bold text-white">{log.user}</td>
                       <td className="px-4 py-3 text-slate-300">{log.service}</td>
                       <td className="px-4 py-3 text-[#38bdf8]">{log.operation}</td>
                       <td className="px-4 py-3 text-slate-400 font-mono text-xs max-w-[200px] truncate" title={log.resource}>{log.resource}</td>
                       <td className="px-4 py-3 text-slate-500 text-xs">{log.clientIp}</td>
                       <td className="px-4 py-3">
                          <span className={cn(
                             "flex items-center text-xs font-bold",
                             log.result === 'Success' ? "text-[#00ff9d]" : 
                             log.result === 'Denied' ? "text-rose-500" : "text-amber-500"
                          )}>
                             {log.result === 'Success' && <CheckCircle className="w-3 h-3 mr-1" />}
                             {log.result === 'Denied' && <XCircle className="w-3 h-3 mr-1" />}
                             {log.result === 'Failed' && <AlertTriangle className="w-3 h-3 mr-1" />}
                             {log.result}
                          </span>
                       </td>
                    </tr>
                 ))}
              </tbody>
           </table>
        </div>
      </div>
    </div>
  );

  const renderKeyManagement = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Key className="w-5 h-5 mr-2 text-[#f59e0b]" /> 密钥管理 (KMS/Kerberos)
          </h3>
          <button className="px-3 py-1.5 bg-[#f59e0b] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#d97706] flex items-center">
             <Plus className="w-4 h-4 mr-1" /> Create Key
          </button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
           {keys.map(key => (
              <div key={key.id} className="p-4 bg-white/5 rounded-xl border border-white/10 hover:border-white/20 transition-all">
                 <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center">
                       <div className="w-8 h-8 rounded-full bg-[#f59e0b]/10 flex items-center justify-center mr-3">
                          <Lock className="w-4 h-4 text-[#f59e0b]" />
                       </div>
                       <div>
                          <div className="text-sm font-bold text-white truncate max-w-[150px]" title={key.name}>{key.name}</div>
                          <div className="text-[10px] text-slate-500">Ver. {key.version}</div>
                       </div>
                    </div>
                    <span className={cn(
                       "text-[10px] px-2 py-0.5 rounded",
                       key.status === 'Active' ? "bg-[#00ff9d]/10 text-[#00ff9d]" : 
                       key.status === 'Rotated' ? "bg-slate-700 text-slate-400" : "bg-rose-500/10 text-rose-500"
                    )}>{key.status}</span>
                 </div>
                 <div className="space-y-2 text-xs text-slate-400">
                    <div className="flex justify-between">
                       <span>Algorithm:</span>
                       <span className="text-slate-300">{key.algorithm}</span>
                    </div>
                    <div className="flex justify-between">
                       <span>Created:</span>
                       <span className="text-slate-300">{key.created}</span>
                    </div>
                    <div className="flex justify-between">
                       <span>Expires:</span>
                       <span className="text-slate-300">{key.expires}</span>
                    </div>
                 </div>
                 <div className="mt-4 pt-3 border-t border-white/5 flex justify-end space-x-2">
                    <button className="text-xs text-[#38bdf8] hover:text-white">Rotate</button>
                    <button className="text-xs text-rose-500 hover:text-rose-400">Revoke</button>
                 </div>
              </div>
           ))}
        </div>
      </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Identity & Access */}
        <div className="glass-panel p-6 rounded-2xl">
           <h3 className="text-lg font-bold text-white mb-6 flex items-center">
             <Key className="w-5 h-5 mr-2 text-[#f59e0b]" /> 身份认证与访问控制 (IAM)
           </h3>
           <div className="space-y-4">
              <div className="p-4 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between">
                 <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full bg-[#00ff9d]/10 flex items-center justify-center mr-3">
                       <Shield className="w-5 h-5 text-[#00ff9d]" />
                    </div>
                    <div>
                       <div className="text-sm font-bold text-white">LDAP / AD Integration</div>
                       <div className="text-[10px] text-slate-400">Connected: ad.cloudrealm.internal</div>
                    </div>
                 </div>
                 <div className="px-2 py-1 bg-[#00ff9d]/10 text-[#00ff9d] text-[10px] font-bold rounded">ACTIVE</div>
              </div>

              <div className="p-4 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between">
                 <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full bg-[#38bdf8]/10 flex items-center justify-center mr-3">
                       <Lock className="w-5 h-5 text-[#38bdf8]" />
                    </div>
                    <div>
                       <div className="text-sm font-bold text-white">Kerberos Realm</div>
                       <div className="text-[10px] text-slate-400">CLOUDREALM.COM (MIT KDC)</div>
                    </div>
                 </div>
                 <button className="text-xs text-[#38bdf8] hover:text-white">Manage Keytabs</button>
              </div>
           </div>
        </div>

        {/* 2. Audit Logs Preview */}
        <div className="glass-panel p-6 rounded-2xl">
           <h3 className="text-lg font-bold text-white mb-6 flex items-center">
             <Eye className="w-5 h-5 mr-2 text-rose-500" /> 安全审计日志概览
           </h3>
           <div className="space-y-0.5">
              {logs.slice(0, 4).map((log, i) => (
                 <div key={i} className="flex items-center justify-between p-3 hover:bg-white/5 rounded-lg transition-colors border-b border-white/5 last:border-0">
                    <div className="flex items-center">
                       <div className={cn(
                          "w-1.5 h-1.5 rounded-full mr-3",
                          log.result === 'Success' ? 'bg-[#00ff9d]' : 
                          log.result === 'Denied' ? 'bg-rose-500' : 'bg-amber-500'
                       )}></div>
                       <div>
                          <div className="text-xs font-bold text-slate-300">{log.operation} <span className="text-slate-500 font-normal">by {log.user}</span></div>
                          <div className="text-[10px] text-slate-500 font-mono">{log.service}</div>
                       </div>
                    </div>
                    <div className="text-[10px] text-slate-500">{log.time.split(' ')[1]}</div>
                 </div>
              ))}
           </div>
           <button className="w-full mt-4 py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10 flex items-center justify-center text-slate-400">
              <FileText className="w-3 h-3 mr-2" /> View All Logs
           </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {activeSubView === '策略管理' && renderPolicyManagement()}
      {activeSubView === '审计日志' && renderAuditLogs()}
      {activeSubView === '密钥管理' && renderKeyManagement()}
      {(!activeSubView || activeSubView === '') && renderOverview()}
    </>
  );
}
