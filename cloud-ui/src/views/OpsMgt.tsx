import React from 'react';
import { Activity, Terminal, Clock, BellRing, Search, Server } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const metricData = Array.from({ length: 20 }).map((_, i) => ({
  time: i,
  cpu: Math.floor(Math.random() * 40) + 20,
  mem: Math.floor(Math.random() * 30) + 40,
}));

export default function OpsMgt() {
  return (
    <div className="space-y-6">
      {/* 1. Integrated Monitoring (Prometheus style) */}
      <div className="glass-panel p-6 rounded-2xl">
         <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
              <Activity className="w-5 h-5 mr-2 text-[#00ff9d]" /> 监控概览 (Prometheus)
            </h3>
            <div className="flex space-x-2">
               {['CPU', 'Memory', 'Network', 'Disk I/O'].map(m => (
                  <button key={m} className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-[10px] text-slate-300 hover:bg-white/10 transition-all">
                     {m}
                  </button>
               ))}
            </div>
         </div>
         <div className="h-[250px] w-full">
            <ResponsiveContainer width="100%" height="100%">
               <AreaChart data={metricData}>
                  <defs>
                     <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00ff9d" stopOpacity={0.2}/>
                        <stop offset="95%" stopColor="#00ff9d" stopOpacity={0}/>
                     </linearGradient>
                     <linearGradient id="colorMem" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.2}/>
                        <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}/>
                     </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                  <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '8px'}} />
                  <Area type="monotone" dataKey="cpu" stroke="#00ff9d" fillOpacity={1} fill="url(#colorCpu)" />
                  <Area type="monotone" dataKey="mem" stroke="#38bdf8" fillOpacity={1} fill="url(#colorMem)" />
               </AreaChart>
            </ResponsiveContainer>
         </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
         {/* 2. Log Analysis (ELK) */}
         <div className="glass-panel p-6 rounded-2xl">
            <div className="flex items-center justify-between mb-4">
               <h3 className="text-lg font-bold text-white flex items-center">
                 <Terminal className="w-5 h-5 mr-2 text-[#f59e0b]" /> 日志分析 (ELK)
               </h3>
               <div className="relative">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
                  <input type="text" placeholder='error AND "timeout"' className="pl-7 pr-3 py-1 bg-[#020617] border border-white/10 rounded text-xs text-white w-48" />
               </div>
            </div>
            <div className="space-y-2 font-mono text-[10px] text-slate-400 h-[200px] overflow-y-auto custom-scrollbar p-2 bg-[#020617] rounded-lg border border-white/5">
               {[...Array(8)].map((_, i) => (
                  <div key={i} className="hover:bg-white/5 p-1 rounded cursor-pointer">
                     <span className="text-[#38bdf8]">2024-03-10 12:0{i}:23</span> 
                     <span className={i % 3 === 0 ? "text-rose-500 ml-2" : "text-[#00ff9d] ml-2"}>
                        {i % 3 === 0 ? "[ERROR]" : "[INFO]"}
                     </span> 
                     <span className="ml-2 text-slate-300">Connection refused to host: worker-0{i % 3}</span>
                  </div>
               ))}
            </div>
         </div>

         {/* 3. Task Scheduling */}
         <div className="glass-panel p-6 rounded-2xl">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center">
              <Clock className="w-5 h-5 mr-2 text-[#a855f7]" /> 任务调度
            </h3>
            <div className="space-y-3">
               {[
                  { name: 'Daily ETL Workflow', status: 'Running', progress: 45 },
                  { name: 'Hourly Aggregation', status: 'Pending', progress: 0 },
                  { name: 'Data Cleanup', status: 'Success', progress: 100 },
               ].map(task => (
                  <div key={task.name} className="p-3 bg-white/5 rounded-xl border border-white/5">
                     <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-bold text-white">{task.name}</span>
                        <span className={`text-[10px] px-1.5 rounded ${
                           task.status === 'Running' ? 'bg-[#38bdf8]/10 text-[#38bdf8]' : 
                           task.status === 'Success' ? 'bg-[#00ff9d]/10 text-[#00ff9d]' : 'bg-slate-700 text-slate-300'
                        }`}>{task.status}</span>
                     </div>
                     <div className="h-1.5 w-full bg-[#020617] rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-[#38bdf8] to-[#00ff9d]" style={{ width: `${task.progress}%` }}></div>
                     </div>
                  </div>
               ))}
            </div>
         </div>
      </div>
    </div>
  );
}
