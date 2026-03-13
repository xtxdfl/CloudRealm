import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { cn } from '@/lib/utils';
import { Zap, LayoutGrid, Activity, Server, Layers, Users, Bell, FileText, ArrowRight, Cpu, HardDrive, AlertTriangle, AlertCircle, Info } from 'lucide-react';

const heatmapData = Array.from({ length: 40 }).map((_, i) => ({
  id: i,
  usage: Math.floor(Math.random() * 100),
  name: `Node-${i + 1}`
}));

const topHostsData = Array.from({ length: 10 }).map((_, i) => ({
  name: `Worker-${String(i + 1).padStart(2, '0')}`,
  cpu: Math.floor(Math.random() * 40) + 50, // 50-90%
  mem: Math.floor(Math.random() * 50) + 40,
  disk: Math.floor(Math.random() * 30) + 60,
})).sort((a, b) => b.cpu - a.cpu);

const alertsData = [
  { id: 1, level: 'critical', msg: 'DataNode (Worker-03) 心跳丢失', time: '2分钟前', source: 'HDFS' },
  { id: 2, level: 'warning', msg: 'YARN 队列 (root.default) 资源使用率 > 90%', time: '15分钟前', source: 'YARN' },
  { id: 3, level: 'critical', msg: 'Hive Metastore 连接超时', time: '32分钟前', source: 'HIVE' },
  { id: 4, level: 'warning', msg: 'Kafka Topic (logs) 消费积压', time: '1小时前', source: 'KAFKA' },
  { id: 5, level: 'info', msg: '集群配置变更：hdfs-site.xml', time: '2小时前', source: 'Ambari' },
  { id: 6, level: 'info', msg: 'Spark Job (Daily-ETL) 完成', time: '3小时前', source: 'SPARK' },
];

const matrixData = [
  { node: 'Master01', hdfs: 'NM', yarn: 'RM', hive: '未监控', spark: '未监控' },
  { node: 'Worker01', hdfs: 'DN', yarn: 'NM', hive: 'HS2', spark: 'Exec' },
  { node: 'Worker02', hdfs: 'DN', yarn: 'NM', hive: 'HS2', spark: 'Exec' },
  { node: 'Worker03', hdfs: 'DN', yarn: 'NM', hive: 'HS2', spark: 'Exec' },
];

const StatusIcon = ({ status }: { status: string }) => {
  if (status === '正常' || status === 'healthy' || status === 'DN' || status === 'NM' || status === 'RM' || status === 'HS2' || status === 'Exec') 
    return <div className="w-3 h-3 bg-[#00ff9d] rounded-sm shadow-[0_0_5px_#00ff9d]"></div>;
  if (status === '警告') 
    return <div className="w-3 h-3 bg-amber-500 rounded-sm shadow-[0_0_5px_#f59e0b]"></div>;
  if (status === '故障') 
    return <div className="w-3 h-3 bg-rose-500 rounded-sm shadow-[0_0_5px_#f43f5e]"></div>;
  return <div className="w-3 h-3 bg-slate-700 rounded-sm"></div>;
};

// Props interface for navigation
interface OverviewProps {
  onNavigate?: (view: string) => void;
}

export default function Overview({ onNavigate }: OverviewProps) {
  
  const navCards = [
    { id: 'HostMgt', title: '主机管理', desc: '节点监控与Agent管控', icon: Server, color: '#38bdf8' },
    { id: 'ClusterMgt', title: '集群管理', desc: '服务治理与配置中心', icon: Layers, color: '#00ff9d' },
    { id: 'UserCenter', title: '用户中心', desc: '权限认证与审计', icon: Users, color: '#a855f7' },
    { id: 'AlertCenter', title: '告警管理', desc: '智能监控与策略', icon: Bell, color: '#f59e0b' },
    { id: 'LogCenter', title: '日志中心', desc: '日志采集与分析', icon: FileText, color: '#f43f5e' },
  ];

  return (
    <div className="space-y-6">
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 3.1 资源热力图 */}

        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
              <LayoutGrid className="w-5 h-5 mr-2 text-[#00ff9d]" />
              资源热力图
            </h3>
            <div className="flex space-x-4 text-xs">
              <div className="flex items-center"><div className="w-2 h-2 bg-slate-800 mr-2 rounded-sm"></div> 0%</div>
              <div className="flex items-center"><div className="w-2 h-2 bg-[#00ff9d] mr-2 rounded-sm"></div> 100%</div>
            </div>
          </div>
          <div className="grid grid-cols-8 gap-2">
            {heatmapData.map((node) => (
              <div 
                key={node.id} 
                className="aspect-square rounded-sm transition-all hover:scale-110 cursor-pointer group relative"
                style={{ 
                  backgroundColor: `rgba(0, 255, 157, ${node.usage / 100})`,
                  border: node.usage > 80 ? '1px solid #00ff9d' : 'none'
                }}
              >
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-black text-[10px] text-white rounded opacity-0 group-hover:opacity-100 whitespace-nowrap z-20 pointer-events-none">
                  {node.name}: {node.usage}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 3.2 服务状态矩阵 */}
        <div className="glass-panel p-6 rounded-2xl">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-[#38bdf8]" />
            服务状态矩阵
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-slate-500 border-b border-white/5">
                  <th className="pb-4 font-medium">节点</th>
                  <th className="pb-4 font-medium text-center">HDFS</th>
                  <th className="pb-4 font-medium text-center">YARN</th>
                  <th className="pb-4 font-medium text-center">HIVE</th>
                  <th className="pb-4 font-medium text-center">SPARK</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {matrixData.map((row) => (
                  <tr key={row.node} className="group hover:bg-white/5 transition-colors">
                    <td className="py-4 font-medium text-slate-300">{row.node}</td>
                    <td className="py-4 text-center"><StatusIcon status={row.hdfs} /></td>
                    <td className="py-4 text-center"><StatusIcon status={row.yarn} /></td>
                    <td className="py-4 text-center"><StatusIcon status={row.hive} /></td>
                    <td className="py-4 text-center"><StatusIcon status={row.spark} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 4. Top 10 Hosts & Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 4.1 Top 10 Hosts */}
        <div className="glass-panel p-6 rounded-2xl">
           <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white flex items-center">
                <Server className="w-5 h-5 mr-2 text-rose-500" /> 资源消耗 Top 10
              </h3>
              <span className="text-xs text-slate-500 bg-white/5 px-2 py-1 rounded">Sort by: CPU</span>
           </div>
           <div className="space-y-4">
              {topHostsData.map((host, idx) => (
                 <div key={host.name} className="flex items-center space-x-4 text-xs">
                    <div className="w-6 text-slate-500 font-mono">#{idx + 1}</div>
                    <div className="w-24 font-bold text-slate-300 truncate">{host.name}</div>
                    <div className="flex-1 grid grid-cols-3 gap-4">
                       {/* CPU */}
                       <div className="flex flex-col justify-center">
                          <div className="flex justify-between mb-1 text-[10px] text-slate-500">
                             <span>CPU</span>
                             <span className={host.cpu > 80 ? 'text-rose-500' : 'text-slate-400'}>{host.cpu}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                             <div 
                               className={`h-full rounded-full ${host.cpu > 80 ? 'bg-rose-500' : 'bg-[#38bdf8]'}`} 
                               style={{ width: `${host.cpu}%` }}
                             ></div>
                          </div>
                       </div>
                       {/* MEM */}
                       <div className="flex flex-col justify-center">
                          <div className="flex justify-between mb-1 text-[10px] text-slate-500">
                             <span>MEM</span>
                             <span>{host.mem}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                             <div 
                               className="h-full bg-[#a855f7] rounded-full" 
                               style={{ width: `${host.mem}%` }}
                             ></div>
                          </div>
                       </div>
                       {/* DISK */}
                       <div className="flex flex-col justify-center">
                          <div className="flex justify-between mb-1 text-[10px] text-slate-500">
                             <span>DISK</span>
                             <span>{host.disk}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                             <div 
                               className="h-full bg-[#f59e0b] rounded-full" 
                               style={{ width: `${host.disk}%` }}
                             ></div>
                          </div>
                       </div>
                    </div>
                 </div>
              ))}
           </div>
        </div>

        {/* 4.2 Alerts */}
        <div className="glass-panel p-6 rounded-2xl">
           <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white flex items-center">
                <Bell className="w-5 h-5 mr-2 text-[#f59e0b]" /> 实时告警动态
              </h3>
              <button className="text-xs text-[#38bdf8] hover:text-white transition-colors">View All</button>
           </div>
           <div className="space-y-3">
              {alertsData.map((alert) => (
                 <div key={alert.id} className="p-3 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-all group flex items-start space-x-3">
                    <div className="mt-0.5">
                       {alert.level === 'critical' && <AlertCircle className="w-4 h-4 text-rose-500" />}
                       {alert.level === 'warning' && <AlertTriangle className="w-4 h-4 text-[#f59e0b]" />}
                       {alert.level === 'info' && <Info className="w-4 h-4 text-[#38bdf8]" />}
                    </div>
                    <div className="flex-1">
                       <div className="flex justify-between items-start">
                          <span className={`text-sm font-bold ${
                             alert.level === 'critical' ? 'text-rose-400' : 
                             alert.level === 'warning' ? 'text-amber-400' : 'text-slate-300'
                          }`}>
                             {alert.msg}
                          </span>
                          <span className="text-[10px] text-slate-500 whitespace-nowrap ml-2">{alert.time}</span>
                       </div>
                       <div className="mt-1 flex items-center justify-between">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 uppercase tracking-wider">
                             {alert.source}
                          </span>
                          <button className="text-[10px] text-[#38bdf8] opacity-0 group-hover:opacity-100 transition-opacity">
                             查看详情 &rarr;
                          </button>
                       </div>
                    </div>
                 </div>
              ))}
           </div>
        </div>
      </div>

    </div>
  );
}
