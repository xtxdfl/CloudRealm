import React from 'react';
import { Shield, Lock, Key, Eye, FileText, UserCheck, AlertOctagon } from 'lucide-react';

export default function SecurityMgt() {
  return (
    <div className="space-y-6">
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

        {/* 2. Audit Logs */}
        <div className="glass-panel p-6 rounded-2xl">
           <h3 className="text-lg font-bold text-white mb-6 flex items-center">
             <Eye className="w-5 h-5 mr-2 text-rose-500" /> 安全审计日志
           </h3>
           <div className="space-y-0.5">
              {[
                 { user: 'admin', action: 'Granted Policy', resource: '/hdfs/data/finance', time: '10:23 AM', status: 'Success' },
                 { user: 'user_dev', action: 'Access Denied', resource: '/hive/finance.salary', time: '09:45 AM', status: 'Failed' },
                 { user: 'system', action: 'Keytab Renew', resource: 'hdfs/nn', time: '08:00 AM', status: 'Success' },
                 { user: 'external_ip', action: 'SSH Login', resource: 'Master01', time: '02:11 AM', status: 'Warning' },
              ].map((log, i) => (
                 <div key={i} className="flex items-center justify-between p-3 hover:bg-white/5 rounded-lg transition-colors border-b border-white/5 last:border-0">
                    <div className="flex items-center">
                       <div className={`w-1.5 h-1.5 rounded-full mr-3 ${
                          log.status === 'Success' ? 'bg-[#00ff9d]' : 
                          log.status === 'Failed' ? 'bg-rose-500' : 'bg-amber-500'
                       }`}></div>
                       <div>
                          <div className="text-xs font-bold text-slate-300">{log.action} <span className="text-slate-500 font-normal">by {log.user}</span></div>
                          <div className="text-[10px] text-slate-500 font-mono">{log.resource}</div>
                       </div>
                    </div>
                    <div className="text-[10px] text-slate-500">{log.time}</div>
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
}
