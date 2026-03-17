import React, { useState } from 'react';
import { Search, Filter, Download, Terminal, Database, ShieldCheck, History, Activity, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

const services = ['HDFS', 'YARN', 'HIVE', 'SPARK', 'KAFKA', 'ZOOKEEPER'];

export default function LogCenter() {
  const [selectedService, setSelectedService] = useState('HDFS');

  return (
    <div className="h-full flex flex-col space-y-6">
      {/* 1. 采集与存储状态 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Filebeat Status', value: 'Active', color: '#00ff9d', icon: Activity },
          { label: 'Today Logs', value: '4.2 GB', color: '#38bdf8', icon: Database },
          { label: 'Retention Policy', value: '30 Days', color: '#f59e0b', icon: History },
          { label: 'Clustering', value: 'Enabled', color: '#a855f7', icon: ShieldCheck },
        ].map(stat => (
          <div key={stat.label} className="glass-panel p-4 rounded-xl flex items-center space-x-4 border border-white/5">
            <div className="p-2 rounded-lg" style={{ backgroundColor: `${stat.color}10` }}>
              <stat.icon className="w-5 h-5" style={{ color: stat.color }} />
            </div>
            <div>
              <div className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">{stat.label}</div>
              <div className="text-sm font-bold text-white">{stat.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* 2. 搜索与工具栏 */}
      <div className="glass-panel p-4 rounded-xl flex flex-wrap items-center gap-4 border border-white/5">
        <div className="flex-1 min-w-[300px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="Search keywords, error codes, or trace IDs..." 
            className="w-full pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white focus:border-[#38bdf8] outline-none font-mono"
          />
        </div>
        <div className="flex space-x-2">
          {services.map(s => (
            <button 
              key={s}
              onClick={() => setSelectedService(s)}
              className={cn(
                "px-3 py-1.5 rounded text-[10px] font-bold transition-all border",
                selectedService === s 
                  ? "bg-[#38bdf8]/20 text-[#38bdf8] border-[#38bdf8]/30" 
                  : "bg-white/5 text-slate-500 border-transparent hover:border-white/10 hover:text-white"
              )}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="h-8 w-[1px] bg-white/10 hidden lg:block"></div>
        <button className="p-2 bg-white/5 text-slate-400 rounded-lg hover:text-white border border-white/5 transition-all">
          <Download className="w-4 h-4" />
        </button>
        <button className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-[10px] font-bold hover:bg-[#00e68e] flex items-center">
          <Terminal className="w-3 h-3 mr-2" /> 实时 TAIL
        </button>
      </div>

      {/* 3. 日志显示区 (智能聚类/分析) */}
      <div className="flex-1 glass-panel rounded-2xl overflow-hidden flex flex-col border border-white/5 min-h-[400px]">
        <div className="p-4 border-b border-white/5 bg-white/5 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <span className="text-xs font-bold text-white flex items-center">
              <Terminal className="w-4 h-4 mr-2 text-[#00ff9d]" /> Console Output
            </span>
            <span className="text-[10px] text-slate-500 font-mono">Showing last 1000 lines for {selectedService}</span>
          </div>
          <div className="flex space-x-2">
             <span className="text-[10px] bg-rose-500/20 text-rose-500 px-2 py-0.5 rounded font-bold">Errors: 42</span>
             <span className="text-[10px] bg-amber-500/20 text-amber-500 px-2 py-0.5 rounded font-bold">Warn: 128</span>
          </div>
        </div>
        <div className="flex-1 bg-[#020617] p-4 font-mono text-xs overflow-y-auto custom-scrollbar leading-relaxed">
          <div className="space-y-1">
            <div className="text-[#00ff9d] opacity-50">[2026-03-10 11:30:01] INFO  org.apache.hadoop.hdfs.server.datanode.DataNode: Block pool BP-12345 (Datanode Registration) successful.</div>
            <div className="text-slate-400">[2026-03-10 11:30:05] DEBUG org.apache.hadoop.ipc.Server: IPC Server Responder: thread 1 starting</div>
            <div className="text-amber-500">[2026-03-10 11:30:12] WARN  org.apache.hadoop.hdfs.server.common.Util: Path /data/hdfs/dn exists but is not a directory.</div>
            <div className="text-rose-500 bg-rose-500/10 py-1">[2026-03-10 11:30:15] ERROR org.apache.hadoop.hdfs.server.datanode.DataNode: Exception in secureMain: java.io.IOException: Invalid argument at ...</div>
            <div className="text-slate-400">[2026-03-10 11:30:20] INFO  org.apache.hadoop.hdfs.server.datanode.DataNode: Shutdown hook called</div>
            <div className="text-slate-500 italic opacity-50">... (Loading more logs) ...</div>
          </div>
        </div>
      </div>
    </div>
  );
}
