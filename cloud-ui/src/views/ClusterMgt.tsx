import React from 'react';
import { Layers, Plus, Trash2, Settings, History, ArrowUpCircle, RotateCcw } from 'lucide-react';

export default function ClusterMgt() {
  return (
    <div className="space-y-6">
      {/* 1. 组件管理 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
              <Layers className="w-5 h-5 mr-2 text-[#00ff9d]" /> 组件管理
            </h3>
            <div className="flex space-x-2">
              <button className="p-2 bg-[#00ff9d]/10 text-[#00ff9d] rounded-lg hover:bg-[#00ff9d]/20 transition-all">
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="space-y-3">
            {['HDFS', 'YARN', 'HIVE', 'SPARK', 'KAFKA'].map(comp => (
              <div key={comp} className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-all group">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 rounded-lg bg-[#020617] flex items-center justify-center font-bold text-[#38bdf8]">
                    {comp[0]}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">{comp}</div>
                    <div className="text-[10px] text-slate-500">v3.3.6 • Running</div>
                  </div>
                </div>
                <button className="p-2 text-slate-500 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* 2. 配置管理 (版本控制) */}
        <div className="glass-panel p-6 rounded-2xl">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center">
            <Settings className="w-5 h-5 mr-2 text-[#38bdf8]" /> 配置中心
          </h3>
          <div className="space-y-4">
            <div className="p-4 bg-[#020617] border border-white/5 rounded-xl">
              <div className="flex justify-between items-center mb-4">
                <span className="text-xs font-bold text-slate-400 uppercase">当前版本</span>
                <span className="text-xs bg-[#38bdf8]/20 text-[#38bdf8] px-2 py-0.5 rounded">V24 (Active)</span>
              </div>
              <div className="text-xs text-slate-500 font-mono line-clamp-3 mb-4">
                # hdfs-site.xml updated<br />
                dfs.replication: 3 -&gt; 2<br />
                dfs.blocksize: 128MB
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button className="py-2 bg-[#38bdf8] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#0ea5e9]">批量分发</button>
                <button className="py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10">动态更新</button>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-1">历史版本</div>
              {[23, 22, 21].map(v => (
                <div key={v} className="flex items-center justify-between p-3 bg-white/5 rounded-lg text-xs border border-transparent hover:border-white/10 cursor-pointer">
                  <span className="text-slate-300">Configuration Version V{v}</span>
                  <span className="text-slate-500 font-mono">2026-03-09</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 3. 版本管理 (升级回滚) */}
      <div className="glass-panel p-6 rounded-2xl">
        <h3 className="text-lg font-bold text-white mb-6 flex items-center">
          <History className="w-5 h-5 mr-2 text-amber-500" /> 集群版本治理
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="text-sm font-bold text-slate-300 flex items-center">
              <ArrowUpCircle className="w-4 h-4 mr-2 text-[#00ff9d]" /> 可用升级
            </div>
            <div className="p-4 bg-white/5 border border-[#00ff9d]/20 rounded-xl relative overflow-hidden group">
               <div className="flex justify-between items-start relative z-10">
                  <div>
                    <div className="text-sm font-bold text-white">HDFS 3.3.6 -&gt; 3.4.0</div>
                    <div className="text-xs text-slate-500 mt-1">优化了 NameNode 的内存占用...</div>
                  </div>
                  <button className="px-3 py-1 bg-[#00ff9d] text-[#020617] text-[10px] font-bold rounded hover:bg-[#00e68e]">
                    开始升级
                  </button>
               </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="text-sm font-bold text-slate-300 flex items-center">
              <RotateCcw className="w-4 h-4 mr-2 text-rose-500" /> 版本回滚
            </div>
            <div className="p-4 bg-white/5 border border-rose-500/20 rounded-xl">
               <div className="flex justify-between items-start">
                  <div>
                    <div className="text-sm font-bold text-white">HIVE 3.1.3</div>
                    <div className="text-xs text-slate-500 mt-1">回滚至上一个稳定运行的版本</div>
                  </div>
                  <button className="px-3 py-1 bg-rose-500/20 text-rose-500 border border-rose-500/30 text-[10px] font-bold rounded hover:bg-rose-500/30">
                    执行回滚
                  </button>
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
