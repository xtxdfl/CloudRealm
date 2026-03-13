import React from 'react';
import { BrainCircuit, Sparkles, Activity, AlertOctagon, ArrowRight } from 'lucide-react';

export default function AIOps() {
  return (
    <div className="space-y-6">
       {/* Hero Section */}
       <div className="glass-panel p-8 rounded-2xl relative overflow-hidden flex items-center justify-between">
          <div className="relative z-10 max-w-lg">
             <div className="flex items-center text-[#00ff9d] mb-2 font-bold tracking-wider text-xs uppercase">
                <Sparkles className="w-4 h-4 mr-2" /> Intelligent Operations
             </div>
             <h2 className="text-2xl font-bold text-white mb-2">AIOps 智能运维引擎</h2>
             <p className="text-slate-400 text-sm mb-6">
                Using machine learning to detect anomalies, analyze root causes, and predict capacity needs automatically.
             </p>
             <button className="px-5 py-2 bg-gradient-to-r from-[#00ff9d] to-blue-600 text-[#020617] font-bold rounded-lg hover:shadow-[0_0_20px_rgba(0,255,157,0.3)] transition-all">
                Run Diagnostics
             </button>
          </div>
          <BrainCircuit className="w-64 h-64 text-[#00ff9d]/5 absolute -right-10 -bottom-10 animate-pulse" />
       </div>

       <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* 1. Anomaly Detection */}
          <div className="glass-panel p-6 rounded-2xl border-t-4 border-t-rose-500">
             <h3 className="text-lg font-bold text-white mb-4 flex items-center">
                <AlertOctagon className="w-5 h-5 mr-2 text-rose-500" /> 异常检测
             </h3>
             <div className="text-center py-6">
                <div className="text-4xl font-bold text-white mb-1">2</div>
                <div className="text-xs text-slate-500 uppercase tracking-widest">Anomalies Detected</div>
             </div>
             <div className="space-y-2 mt-2">
                <div className="p-3 bg-white/5 rounded-lg border border-rose-500/20 text-xs text-slate-300">
                   <div className="font-bold text-rose-400 mb-1">Unusual Traffic Spike</div>
                   <div>HDFS DataNode-04 network in &gt; 3σ baseline</div>
                </div>
             </div>
          </div>

          {/* 2. Root Cause Analysis */}
          <div className="glass-panel p-6 rounded-2xl border-t-4 border-t-[#38bdf8]">
             <h3 className="text-lg font-bold text-white mb-4 flex items-center">
                <Activity className="w-5 h-5 mr-2 text-[#38bdf8]" /> 根因分析
             </h3>
             <div className="relative pl-4 border-l-2 border-white/10 space-y-4">
                <div className="relative">
                   <div className="absolute -left-[21px] top-1 w-3 h-3 bg-[#38bdf8] rounded-full ring-4 ring-[#020617]"></div>
                   <div className="text-xs font-bold text-white">Application Slowdown</div>
                   <div className="text-[10px] text-slate-500 mt-1">Caused by: <span className="text-[#38bdf8]">JVM GC Pause (Stop-the-world)</span></div>
                   <div className="text-[10px] text-slate-500">Confidence: 98%</div>
                </div>
             </div>
             <button className="w-full mt-6 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-[#38bdf8] flex items-center justify-center">
                View Analysis Graph <ArrowRight className="w-3 h-3 ml-1" />
             </button>
          </div>

          {/* 3. Capacity Prediction */}
          <div className="glass-panel p-6 rounded-2xl border-t-4 border-t-[#a855f7]">
             <h3 className="text-lg font-bold text-white mb-4 flex items-center">
                <BrainCircuit className="w-5 h-5 mr-2 text-[#a855f7]" /> 容量预测
             </h3>
             <div className="space-y-4">
                <div>
                   <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>HDFS Storage</span>
                      <span className="text-white font-bold">32 Days left</span>
                   </div>
                   <div className="h-1.5 bg-[#020617] rounded-full overflow-hidden">
                      <div className="h-full bg-[#a855f7] w-[75%]"></div>
                   </div>
                </div>
                <div className="p-3 bg-[#a855f7]/10 rounded-lg text-xs text-[#a855f7]">
                   <strong>Recommendation:</strong> Add 2 DataNodes by next month to maintain 30% buffer.
                </div>
             </div>
          </div>
       </div>
    </div>
  );
}
