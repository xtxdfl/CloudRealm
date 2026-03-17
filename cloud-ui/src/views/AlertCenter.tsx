import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, TrendingUp, AlertCircle, BellRing, Settings2, Share2, Terminal } from 'lucide-react';

const trendData = Array.from({ length: 24 }).map((_, i) => ({
  time: `${i}:00`,
  value: Math.floor(Math.random() * 100) + 20,
  lastWeek: Math.floor(Math.random() * 100) + 10,
}));

export default function AlertCenter() {
  return (
    <div className="space-y-6">
      {/* 1. 历史分析与趋势 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 glass-panel p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
              <TrendingUp className="w-5 h-5 mr-2 text-[#00ff9d]" /> 历史趋势分析
            </h3>
            <div className="flex space-x-2">
              {['1H', '5H', '24H', '3D', '7D'].map(t => (
                <button key={t} className={`px-3 py-1 rounded text-[10px] font-bold transition-all ${
                  t === '24H' ? 'bg-[#00ff9d] text-[#020617]' : 'bg-white/5 text-slate-400 hover:text-white'
                }`}>{t}</button>
              ))}
            </div>
          </div>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00ff9d" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#00ff9d" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                <XAxis dataKey="time" hide />
                <YAxis hide />
                <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '8px'}} />
                <Area type="monotone" dataKey="value" stroke="#00ff9d" fill="url(#colorVal)" strokeWidth={2} name="当前" />
                <Area type="monotone" dataKey="lastWeek" stroke="#38bdf8" fill="none" strokeWidth={1} strokeDasharray="5 5" name="同比" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 2. 容量预测 */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-amber-500" /> 容量预测
          </h3>
          <div className="space-y-6 flex-1 flex flex-col justify-center">
            <div className="text-center">
              <div className="text-4xl font-bold text-[#00ff9d] neon-text">14 Days</div>
              <div className="text-xs text-slate-500 mt-2">预计 HDFS 存储将满</div>
            </div>
            <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-[#00ff9d] to-amber-500 w-[85%]"></div>
            </div>
            <p className="text-[10px] text-slate-400 text-center">基于过去 7 天的数据增长率计算</p>
          </div>
          <button className="w-full py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10">查看扩容建议</button>
        </div>
      </div>

      {/* 3. 告警中心 (策略与事件) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 告警策略 */}
        <div className="glass-panel p-6 rounded-2xl">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center">
            <Settings2 className="w-5 h-5 mr-2 text-[#38bdf8]" /> 策略配置
          </h3>
          <div className="space-y-3">
            {[
              { name: 'CPU 使用率过高', threshold: '> 90%', type: '动态阈值' },
              { name: 'DataNode 丢失', threshold: '> 1', type: '固定阈值' },
              { name: 'Kafka 堆积', threshold: '> 100k', type: '智能基线' },
            ].map(policy => (
              <div key={policy.name} className="p-4 bg-[#020617] border border-white/5 rounded-xl flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold text-white">{policy.name}</div>
                  <div className="text-[10px] text-slate-500 font-mono mt-1">{policy.type} • {policy.threshold}</div>
                </div>
                <div className="flex items-center space-x-2">
                   <div className="w-8 h-4 bg-[#00ff9d] rounded-full relative p-1 cursor-pointer">
                      <div className="w-2 h-2 bg-[#020617] rounded-full absolute right-1"></div>
                   </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 告警事件播报 */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center">
            <BellRing className="w-5 h-5 mr-2 text-rose-500" /> 事件流
          </h3>
          <div className="space-y-4 flex-1 overflow-y-auto custom-scrollbar pr-2 max-h-[300px]">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="flex space-x-4">
                <div className="shrink-0 mt-1">
                  <div className={`w-2 h-2 rounded-full ${i % 2 === 0 ? 'bg-rose-500 shadow-[0_0_5px_#f43f5e]' : 'bg-amber-500 shadow-[0_0_5px_#f59e0b]'}`}></div>
                </div>
                <div className="flex-1 pb-4 border-b border-white/5">
                  <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                    <span>{i % 2 === 0 ? 'Critical • High CPU Usage' : 'Warning • Memory Leak Detected'}</span>
                    <span>10:2{i} AM</span>
                  </div>
                  <p className="text-xs text-slate-300 font-mono">HIVE_METASTORE process exited unexpectedly on worker-0{i}.</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
