import React, { useState } from 'react';
import { 
  BrainCircuit, Sparkles, Activity, AlertOctagon, ArrowRight, 
  Search, CheckCircle, AlertTriangle, XCircle, TrendingUp, 
  BarChart2, Zap, GitCommit
} from 'lucide-react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { cn } from '@/lib/utils';

// Mock Data
const predictionData = Array.from({ length: 30 }).map((_, i) => ({
  day: `Day ${i + 1}`,
  actual: i < 20 ? Math.floor(50 + i * 2 + Math.random() * 10) : null,
  predicted: i >= 20 ? Math.floor(50 + i * 2) : null,
  upper: i >= 20 ? Math.floor(50 + i * 2 + 10) : null,
  lower: i >= 20 ? Math.floor(50 + i * 2 - 10) : null,
}));

const anomalies = [
  { id: 1, type: 'Network', severity: 'Critical', description: 'Unusual Traffic Spike', time: '10:23 AM', source: 'DataNode-04', confidence: 98 },
  { id: 2, type: 'Performance', severity: 'Warning', description: 'High Latency in HBase RegionServer', time: '09:45 AM', source: 'RegionServer-02', confidence: 85 },
  { id: 3, type: 'Security', severity: 'Critical', description: 'Multiple Failed Logins', time: '08:00 AM', source: 'Gateway', confidence: 92 },
];

export default function AIOps({ activeSubView }: { activeSubView?: string }) {
  
  const renderIntelligentAnalysis = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Sparkles className="w-5 h-5 mr-2 text-[#00ff9d]" /> 智能异常分析 (Anomaly Detection)
          </h3>
          <div className="flex space-x-3">
             <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
                <Search className="w-4 h-4 text-slate-500 mr-2" />
                <input 
                  type="text" 
                  placeholder="Search anomalies..." 
                  className="bg-transparent border-none text-xs text-white focus:ring-0 w-full"
                />
             </div>
             <button className="px-3 py-1.5 bg-[#00ff9d] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#00e68e] flex items-center">
                <Zap className="w-4 h-4 mr-1" /> Run Scan
             </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
           <div className="lg:col-span-2 space-y-4">
              {anomalies.map(anomaly => (
                 <div key={anomaly.id} className="p-4 bg-white/5 rounded-xl border border-white/5 hover:border-white/20 transition-all cursor-pointer group">
                    <div className="flex items-start justify-between">
                       <div className="flex items-start">
                          <div className={cn(
                             "w-10 h-10 rounded-lg flex items-center justify-center mr-4 shrink-0",
                             anomaly.severity === 'Critical' ? "bg-rose-500/10 text-rose-500" : "bg-amber-500/10 text-amber-500"
                          )}>
                             <AlertOctagon className="w-6 h-6" />
                          </div>
                          <div>
                             <h4 className="font-bold text-white group-hover:text-[#38bdf8] transition-colors">{anomaly.description}</h4>
                             <div className="text-xs text-slate-400 mt-1">Source: <span className="text-slate-300">{anomaly.source}</span> • Time: {anomaly.time}</div>
                             <div className="flex items-center mt-2 space-x-2">
                                <span className="text-[10px] px-2 py-0.5 rounded bg-white/10 text-slate-300">{anomaly.type}</span>
                                <span className="text-[10px] text-[#00ff9d]">Confidence: {anomaly.confidence}%</span>
                             </div>
                          </div>
                       </div>
                       <div className="flex flex-col items-end">
                          <span className={cn(
                             "text-xs font-bold px-2 py-1 rounded",
                             anomaly.severity === 'Critical' ? "bg-rose-500 text-[#020617]" : "bg-amber-500 text-[#020617]"
                          )}>{anomaly.severity}</span>
                          <button className="mt-4 text-xs text-[#38bdf8] hover:underline flex items-center">
                             Analyze <ArrowRight className="w-3 h-3 ml-1" />
                          </button>
                       </div>
                    </div>
                 </div>
              ))}
           </div>
           
           <div className="glass-panel p-6 rounded-xl bg-[#020617]/50 border border-white/5">
              <h4 className="font-bold text-white mb-4">Anomaly Stats</h4>
              <div className="h-[200px]">
                 <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[
                       { name: 'Network', value: 12 },
                       { name: 'Perf', value: 8 },
                       { name: 'Sec', value: 5 },
                       { name: 'Sys', value: 3 },
                    ]}>
                       <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                       <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                       <Tooltip cursor={{fill: 'transparent'}} contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '8px', color: '#fff'}} />
                       <Bar dataKey="value" fill="#38bdf8" radius={[4, 4, 0, 0]} barSize={20} />
                    </BarChart>
                 </ResponsiveContainer>
              </div>
           </div>
        </div>
      </div>
    </div>
  );

  const renderRootCauseAnalysis = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Activity className="w-5 h-5 mr-2 text-[#38bdf8]" /> 根因定位 (Root Cause Analysis)
          </h3>
          <div className="flex items-center space-x-2">
             <span className="text-xs text-slate-400">Analysis ID: #RCA-20231027-001</span>
             <button className="px-3 py-1.5 bg-white/5 text-slate-300 rounded-lg text-xs hover:text-white">Export Report</button>
          </div>
        </div>

        <div className="bg-[#020617] rounded-xl border border-white/5 p-8 min-h-[500px] relative overflow-hidden flex flex-col items-center">
           <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
           
           {/* RCA Tree Visualization Mock */}
           <div className="relative z-10 w-full max-w-4xl space-y-8">
              {/* Root Event */}
              <div className="flex justify-center">
                 <div className="p-4 bg-rose-500/20 border border-rose-500 rounded-xl text-center w-64 shadow-[0_0_20px_rgba(244,63,94,0.2)]">
                    <div className="text-xs text-rose-400 font-bold uppercase mb-1">Incident</div>
                    <div className="font-bold text-white">Application Slowdown</div>
                    <div className="text-[10px] text-slate-400 mt-1">Latency &gt; 5000ms</div>
                 </div>
              </div>

              {/* Connector */}
              <div className="flex justify-center">
                 <div className="h-8 w-0.5 bg-slate-600"></div>
              </div>

              {/* Intermediate Nodes */}
              <div className="grid grid-cols-2 gap-12 relative">
                 <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[50%] h-0.5 bg-slate-600"></div>
                 <div className="flex flex-col items-center relative">
                    <div className="h-4 w-0.5 bg-slate-600 absolute -top-4"></div>
                    <div className="p-3 bg-slate-800 border border-slate-600 rounded-lg text-center w-48 opacity-50">
                       <div className="text-xs text-slate-400 mb-1">Database</div>
                       <div className="font-bold text-slate-300">DB Connections OK</div>
                       <div className="text-[10px] text-slate-500">Probability: 5%</div>
                    </div>
                 </div>
                 <div className="flex flex-col items-center relative">
                    <div className="h-4 w-0.5 bg-slate-600 absolute -top-4"></div>
                    <div className="p-3 bg-[#38bdf8]/10 border border-[#38bdf8] rounded-lg text-center w-48 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
                       <div className="text-xs text-[#38bdf8] mb-1">Application Server</div>
                       <div className="font-bold text-white">JVM High Pause</div>
                       <div className="text-[10px] text-[#38bdf8]">Probability: 85%</div>
                    </div>
                 </div>
              </div>

              {/* Connector */}
              <div className="grid grid-cols-2 gap-12">
                 <div></div>
                 <div className="flex flex-col items-center">
                    <div className="h-8 w-0.5 bg-slate-600"></div>
                 </div>
              </div>

              {/* Leaf Nodes */}
              <div className="grid grid-cols-2 gap-12">
                 <div></div>
                 <div className="flex flex-col items-center">
                    <div className="p-4 bg-[#00ff9d]/10 border border-[#00ff9d] rounded-xl text-center w-64 shadow-[0_0_20px_rgba(0,255,157,0.2)] animate-pulse">
                       <div className="flex items-center justify-center text-[#00ff9d] mb-1">
                          <CheckCircle className="w-4 h-4 mr-1" /> Root Cause Found
                       </div>
                       <div className="font-bold text-white text-lg">Full GC (Stop-the-world)</div>
                       <div className="text-xs text-slate-400 mt-2">
                          Heap usage reached 98%. <br/> Recommendation: Increase Heap Size or Tune GC.
                       </div>
                    </div>
                 </div>
              </div>
           </div>
        </div>
      </div>
    </div>
  );

  const renderPredictionView = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <BrainCircuit className="w-5 h-5 mr-2 text-[#a855f7]" /> 容量预测 (Capacity Prediction)
          </h3>
          <div className="flex space-x-2">
             {['Storage', 'Compute', 'Network'].map(m => (
                <button key={m} className={cn(
                   "px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                   m === 'Storage' ? "bg-[#a855f7] text-white" : "bg-white/5 text-slate-400 hover:text-white"
                )}>
                   {m}
                </button>
             ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
           <div className="lg:col-span-3 h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                 <AreaChart data={predictionData}>
                    <defs>
                       <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}/>
                       </linearGradient>
                       <linearGradient id="colorPred" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#a855f7" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                       </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                    <XAxis dataKey="day" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '8px', color: '#fff'}} />
                    <Area type="monotone" dataKey="actual" stroke="#38bdf8" fillOpacity={1} fill="url(#colorActual)" name="Actual Usage" strokeWidth={2} />
                    <Area type="monotone" dataKey="predicted" stroke="#a855f7" fillOpacity={1} fill="url(#colorPred)" name="Predicted Usage" strokeWidth={2} strokeDasharray="5 5" />
                    <Line type="monotone" dataKey="upper" stroke="#a855f7" strokeWidth={1} strokeOpacity={0.5} dot={false} activeDot={false} />
                    <Line type="monotone" dataKey="lower" stroke="#a855f7" strokeWidth={1} strokeOpacity={0.5} dot={false} activeDot={false} />
                 </AreaChart>
              </ResponsiveContainer>
           </div>
           
           <div className="space-y-4">
              <div className="p-4 bg-white/5 rounded-xl border border-white/5">
                 <div className="text-xs text-slate-500 uppercase font-bold mb-1">Forecast Horizon</div>
                 <div className="text-2xl font-bold text-white">32 Days</div>
                 <div className="text-[10px] text-slate-400 mt-1">Until storage full</div>
              </div>
              <div className="p-4 bg-white/5 rounded-xl border border-white/5">
                 <div className="text-xs text-slate-500 uppercase font-bold mb-1">Confidence Interval</div>
                 <div className="text-2xl font-bold text-[#00ff9d]">95%</div>
              </div>
              <div className="p-4 bg-[#a855f7]/10 rounded-xl border border-[#a855f7]/20">
                 <div className="text-xs text-[#a855f7] font-bold mb-2 flex items-center">
                    <Sparkles className="w-3 h-3 mr-1" /> AI Suggestion
                 </div>
                 <p className="text-xs text-slate-300">
                    Growth trend indicates exponential increase. Recommend adding 2 DataNodes (10TB each) by Nov 15th.
                 </p>
                 <button className="w-full mt-3 py-1.5 bg-[#a855f7] text-white text-xs rounded font-bold hover:bg-[#9333ea]">
                    View Plan
                 </button>
              </div>
           </div>
        </div>
      </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
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

  return (
    <>
      {activeSubView === '智能分析' && renderIntelligentAnalysis()}
      {activeSubView === '根因定位' && renderRootCauseAnalysis()}
      {activeSubView === '预测视图' && renderPredictionView()}
      {(!activeSubView || activeSubView === '') && renderOverview()}
    </>
  );
}
