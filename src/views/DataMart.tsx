import React from 'react';
import { Database, GitMerge, ShieldCheck, Search, FileJson } from 'lucide-react';

export default function DataMart() {
  return (
    <div className="space-y-6">
      {/* 1. Data Governance Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
         <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
            <div className="relative z-10">
               <div className="text-slate-500 text-xs font-bold uppercase mb-1">Managed Tables</div>
               <div className="text-3xl font-bold text-white">2,485</div>
               <div className="text-[10px] text-[#00ff9d] mt-2 flex items-center">+124 this week</div>
            </div>
            <Database className="w-16 h-16 text-[#38bdf8]/10 absolute right-4 top-1/2 -translate-y-1/2" />
         </div>
         <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
            <div className="relative z-10">
               <div className="text-slate-500 text-xs font-bold uppercase mb-1">Data Quality Score</div>
               <div className="text-3xl font-bold text-white">94.2</div>
               <div className="text-[10px] text-amber-500 mt-2 flex items-center">3 critical issues</div>
            </div>
            <ShieldCheck className="w-16 h-16 text-[#00ff9d]/10 absolute right-4 top-1/2 -translate-y-1/2" />
         </div>
         <div className="glass-panel p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
            <div className="relative z-10">
               <div className="text-slate-500 text-xs font-bold uppercase mb-1">Storage Usage</div>
               <div className="text-3xl font-bold text-white">1.2 PB</div>
               <div className="text-[10px] text-slate-400 mt-2 flex items-center">65% Capacity</div>
            </div>
            <FileJson className="w-16 h-16 text-purple-500/10 absolute right-4 top-1/2 -translate-y-1/2" />
         </div>
      </div>

      {/* 2. Data Catalog & Lineage */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <GitMerge className="w-5 h-5 mr-2 text-[#a855f7]" /> 数据血缘与资产目录
          </h3>
          <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
             <Search className="w-4 h-4 text-slate-500 mr-2" />
             <input type="text" placeholder="Search tables, columns..." className="bg-transparent border-none text-xs text-white focus:ring-0 w-full" />
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
           {/* Recent Assets */}
           <div className="space-y-3">
              <div className="text-xs font-bold text-slate-500 uppercase">Recent Assets</div>
              {[
                 { name: 'dw_sales.fact_orders', type: 'HIVE', owner: 'DataTeam' },
                 { name: 'ods_log.clickstream', type: 'KAFKA', owner: 'AppTeam' },
                 { name: 'dim_users', type: 'HBASE', owner: 'UserCenter' },
              ].map(asset => (
                 <div key={asset.name} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-transparent hover:border-white/10 cursor-pointer group">
                    <div className="flex items-center">
                       <div className="w-8 h-8 rounded bg-[#020617] flex items-center justify-center text-[10px] font-bold text-slate-400 mr-3 border border-white/5">
                          {asset.type[0]}
                       </div>
                       <div>
                          <div className="text-sm font-bold text-slate-200 group-hover:text-[#38bdf8] transition-colors">{asset.name}</div>
                          <div className="text-[10px] text-slate-500">{asset.type} • Owner: {asset.owner}</div>
                       </div>
                    </div>
                 </div>
              ))}
           </div>

           {/* Lineage Preview Placeholder */}
           <div className="bg-[#020617] rounded-xl border border-white/5 p-4 flex flex-col items-center justify-center min-h-[200px] relative overflow-hidden">
              <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
              <GitMerge className="w-12 h-12 text-slate-700 mb-2" />
              <div className="text-sm text-slate-500 font-bold">Data Lineage Graph Visualization</div>
              <div className="text-[10px] text-slate-600">Select an asset to view dependencies</div>
           </div>
        </div>
      </div>
    </div>
  );
}
