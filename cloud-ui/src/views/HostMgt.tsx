import React, { useState, useEffect } from 'react';
import {
  Server, UserPlus, Play, Square, RefreshCcw, ShieldCheck, ShoppingCart,
  Settings2, Activity, Cpu, HardDrive, Network, Map, AlertTriangle, CheckCircle,
  Thermometer, Search, Filter, Trash2, X
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { cn } from '@/lib/utils';

// API Base URL
const API_BASE = '/api';

// Types
interface HostInfo {
  hostId?: number;
  hostname?: string;
  name?: string;  // alias for hostname in some data
  ip: string;
  role?: string;
  status?: string;
  agentStatus?: string;
  cores?: number;
  memory?: string;
  mem?: string;  // alias for memory
  totalMemory?: number;
  cpuUsage?: number;
  memUsage?: number;  // alias for memoryUsage
  memoryUsage?: number;
  diskUsage?: number;
  disk?: string;  // alias for disk
  totalDisk?: number;
  usedDisk?: number;
  osType?: string;
  osArch?: string;
  rackInfo?: string;
  rack?: string;  // alias for rackInfo
  agentVersion?: string;
  tags?: string[];
  components?: string[];
  uptime?: string;
}

// Mock Data
const mockHosts: HostInfo[] = [
  { name: 'Master01', ip: '192.168.1.10', status: 'Running', cores: 8, mem: '32GB', disk: '500GB', role: 'Control Plane', rack: 'rack-01', cpuUsage: 45, memUsage: 60 },
  { name: 'Worker01', ip: '192.168.1.11', status: 'Running', cores: 16, mem: '64GB', disk: '2TB', role: 'Worker', rack: 'rack-01', cpuUsage: 78, memUsage: 85 },
  { name: 'Worker02', ip: '192.168.1.12', status: 'Running', cores: 16, mem: '64GB', disk: '2TB', role: 'Worker', rack: 'rack-02', cpuUsage: 62, memUsage: 70 },
  { name: 'Worker03', ip: '192.168.1.13', status: 'Maintenance', cores: 16, mem: '64GB', disk: '2TB', role: 'Worker', rack: 'rack-02', cpuUsage: 0, memUsage: 0 },
  { name: 'Worker04', ip: '192.168.1.14', status: 'Running', cores: 32, mem: '128GB', disk: '4TB', role: 'Worker', rack: 'rack-03', cpuUsage: 55, memUsage: 45 },
];

const hardwareHealth = [
  { host: 'Master01', diskHealth: 'Healthy', temp: 42, smartStatus: 'Pass', networkErrors: 0 },
  { host: 'Worker01', diskHealth: 'Warning', temp: 55, smartStatus: 'Review', networkErrors: 12 },
  { host: 'Worker02', diskHealth: 'Healthy', temp: 45, smartStatus: 'Pass', networkErrors: 0 },
  { host: 'Worker03', diskHealth: 'Unknown', temp: 0, smartStatus: 'Unknown', networkErrors: 0 },
  { host: 'Worker04', diskHealth: 'Healthy', temp: 40, smartStatus: 'Pass', networkErrors: 2 },
];

const resourceTrend = Array.from({ length: 20 }).map((_, i) => ({
  time: i,
  cpu: Math.floor(Math.random() * 30) + 40,
  mem: Math.floor(Math.random() * 20) + 50,
}));

export default function HostMgt({ activeSubView }: { activeSubView?: string }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [hosts, setHosts] = useState<HostInfo[]>(mockHosts);
  const [selectedHosts, setSelectedHosts] = useState<string[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  // 新增主机表单状态
  const [newHost, setNewHost] = useState<HostInfo>({ hostname: '', ip: '' });

  // 加载主机列表
  const loadHosts = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/hosts`);
      if (response.ok) {
        const data = await response.json();
        if (data && data.length > 0) {
          setHosts(data);
        }
      }
    } catch (error) {
      console.error('Failed to load hosts:', error);
      // 使用mock数据
      setHosts(mockHosts);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHosts();
  }, []);

  // 显示通知消息
  const showNotification = (type: 'success' | 'error' | 'info', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000);
  };

  // 添加主机
  const handleAddHost = async () => {
    if (!newHost.hostname || !newHost.ip) {
      showNotification('error', '请填写主机名和IP地址');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/hosts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newHost)
      });

      const data = await response.json();
      if (data.success) {
        showNotification('success', '主机添加成功');
        setShowAddModal(false);
        setNewHost({ hostname: '', ip: '' });
        loadHosts();
      } else {
        showNotification('error', data.message || '添加主机失败');
      }
    } catch (error) {
      console.error('Failed to add host:', error);
      // Mock模式下直接添加
      setHosts([...hosts, { ...newHost, status: 'Running', role: 'Worker' }]);
      showNotification('success', '主机添加成功 (Mock)');
      setShowAddModal(false);
      setNewHost({ hostname: '', ip: '' });
    } finally {
      setLoading(false);
    }
  };

  // 批量启动主机
  const handleBatchStart = async () => {
    const hostnames = selectedHosts.length > 0 ? selectedHosts : hosts.map(h => h.hostname || h.name);
    if (hostnames.length === 0) {
      showNotification('error', '没有可启动的主机');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/hosts/batch/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(hostnames)
      });

      const data = await response.json();
      if (data.success) {
        showNotification('success', `已启动 ${hostnames.length} 台主机`);
        loadHosts();
      } else {
        showNotification('error', data.message || '启动失败');
      }
    } catch (error) {
      console.error('Failed to start hosts:', error);
      // Mock模式
      setHosts(hosts.map(h => hostnames.includes(h.hostname || h.name) ? { ...h, status: 'Running' } : h));
      showNotification('success', `已启动 ${hostnames.length} 台主机 (Mock)`);
    } finally {
      setLoading(false);
      setSelectedHosts([]);
    }
  };

  // 批量停止主机
  const handleBatchStop = async () => {
    const hostnames = selectedHosts.length > 0 ? selectedHosts : hosts.map(h => h.hostname || h.name);
    if (hostnames.length === 0) {
      showNotification('error', '没有可停止的主机');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/hosts/batch/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(hostnames)
      });

      const data = await response.json();
      if (data.success) {
        showNotification('success', `已停止 ${hostnames.length} 台主机`);
        loadHosts();
      } else {
        showNotification('error', data.message || '停止失败');
      }
    } catch (error) {
      console.error('Failed to stop hosts:', error);
      // Mock模式
      setHosts(hosts.map(h => hostnames.includes(h.hostname || h.name) ? { ...h, status: 'Stopped' } : h));
      showNotification('success', `已停止 ${hostnames.length} 台主机 (Mock)`);
    } finally {
      setLoading(false);
      setSelectedHosts([]);
    }
  };

  // 批量重启主机
  const handleBatchRestart = async () => {
    const hostnames = selectedHosts.length > 0 ? selectedHosts : hosts.map(h => h.hostname || h.name);
    if (hostnames.length === 0) {
      showNotification('error', '没有可重启的主机');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/hosts/batch/restart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(hostnames)
      });

      const data = await response.json();
      if (data.success) {
        showNotification('success', `已重启 ${hostnames.length} 台主机`);
        loadHosts();
      } else {
        showNotification('error', data.message || '重启失败');
      }
    } catch (error) {
      console.error('Failed to restart hosts:', error);
      // Mock模式
      setHosts(hosts.map(h => hostnames.includes(h.hostname || h.name) ? { ...h, status: 'Running' } : h));
      showNotification('success', `已重启 ${hostnames.length} 台主机 (Mock)`);
    } finally {
      setLoading(false);
      setSelectedHosts([]);
    }
  };

  // 删除主机
  const handleDeleteHost = async (hostname: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/hosts/${hostname}`, {
        method: 'DELETE'
      });

      const data = await response.json();
      if (data.success) {
        showNotification('success', '主机删除成功');
        loadHosts();
      } else {
        showNotification('error', data.message || '删除失败');
      }
    } catch (error) {
      console.error('Failed to delete host:', error);
      // Mock模式 - handle both hostname and name fields
      setHosts(hosts.filter(h => (h.hostname || h.name) !== hostname));
      showNotification('success', '主机删除成功 (Mock)');
    } finally {
      setLoading(false);
      setShowDeleteConfirm(false);
    }
  };

  // 切换主机选中状态
  const toggleHostSelection = (hostname: string) => {
    // Also handle 'name' field which is used in mock data
    const hostName = hostname || '';
    setSelectedHosts(prev =>
      prev.includes(hostName)
        ? prev.filter(h => h !== hostName)
        : [...prev, hostName]
    );
  };

  // Helper to get hostname from host object
  const getHostName = (host: HostInfo): string => {
    return host.hostname || host.name || '';
  };

  const renderResourceMonitoring = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
         {/* Charts */}
         <div className="lg:col-span-2 glass-panel p-6 rounded-2xl">
            <div className="flex items-center justify-between mb-6">
               <h3 className="text-lg font-bold text-white flex items-center">
                  <Activity className="w-5 h-5 mr-2 text-[#00ff9d]" /> 集群资源监控 (Cluster Resources)
               </h3>
               <div className="flex space-x-2">
                  <span className="text-xs text-slate-400">Total Cores: 88</span>
                  <span className="text-xs text-slate-400">Total Mem: 352GB</span>
               </div>
            </div>
            <div className="h-[250px]">
               <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={resourceTrend}>
                     <defs>
                        <linearGradient id="colorCpuHost" x1="0" y1="0" x2="0" y2="1">
                           <stop offset="5%" stopColor="#00ff9d" stopOpacity={0.2}/>
                           <stop offset="95%" stopColor="#00ff9d" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorMemHost" x1="0" y1="0" x2="0" y2="1">
                           <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.2}/>
                           <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}/>
                        </linearGradient>
                     </defs>
                     <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
                     <XAxis dataKey="time" hide />
                     <YAxis hide />
                     <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '8px', color: '#fff'}} />
                     <Area type="monotone" dataKey="cpu" stroke="#00ff9d" fillOpacity={1} fill="url(#colorCpuHost)" name="Aggregated CPU" />
                     <Area type="monotone" dataKey="mem" stroke="#38bdf8" fillOpacity={1} fill="url(#colorMemHost)" name="Aggregated Mem" />
                  </AreaChart>
               </ResponsiveContainer>
            </div>
         </div>

         {/* Stats */}
         <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
            <h3 className="font-bold text-white mb-4">Node Status</h3>
            <div className="space-y-4">
               <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center">
                     <div className="w-2 h-2 rounded-full bg-[#00ff9d] mr-2"></div>
                     <span className="text-sm text-slate-300">Healthy</span>
                  </div>
                  <span className="font-bold text-white">4</span>
               </div>
               <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center">
                     <div className="w-2 h-2 rounded-full bg-amber-500 mr-2"></div>
                     <span className="text-sm text-slate-300">Warning</span>
                  </div>
                  <span className="font-bold text-white">0</span>
               </div>
               <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center">
                     <div className="w-2 h-2 rounded-full bg-slate-500 mr-2"></div>
                     <span className="text-sm text-slate-300">Maintenance</span>
                  </div>
                  <span className="font-bold text-white">1</span>
               </div>
            </div>
            <button className="w-full mt-4 py-2 bg-[#38bdf8]/10 text-[#38bdf8] rounded-lg text-xs font-bold hover:bg-[#38bdf8]/20">
               Manage Alerts
            </button>
         </div>
      </div>

      {/* Host List */}
      <div className="glass-panel p-6 rounded-2xl">
         <div className="flex items-center justify-between mb-6">
            <h3 className="font-bold text-white flex items-center">
               <Server className="w-5 h-5 mr-2 text-[#38bdf8]" /> 节点资源详情
            </h3>
            <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
               <Search className="w-4 h-4 text-slate-500 mr-2" />
               <input 
                  type="text" 
                  placeholder="Search hosts..." 
                  className="bg-transparent border-none text-xs text-white focus:ring-0 w-full"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
               />
            </div>
         </div>
         <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
               <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
                  <tr>
                     <th className="px-6 py-3">Host</th>
                     <th className="px-6 py-3">Role</th>
                     <th className="px-6 py-3">CPU Usage</th>
                     <th className="px-6 py-3">Mem Usage</th>
                     <th className="px-6 py-3">Status</th>
                     <th className="px-6 py-3">Action</th>
                  </tr>
               </thead>
               <tbody className="divide-y divide-white/5 text-slate-300">
                  {hosts.map(host => (
                     <tr key={host.name} className="hover:bg-white/5 transition-colors">
                        <td className="px-6 py-4">
                           <div className="font-bold text-white">{host.name}</div>
                           <div className="text-xs text-slate-500">{host.ip}</div>
                        </td>
                        <td className="px-6 py-4 text-xs">{host.role}</td>
                        <td className="px-6 py-4">
                           <div className="flex items-center">
                              <span className="text-xs w-8">{host.cpuUsage || 0}%</span>
                              <div className="h-1.5 w-24 bg-[#020617] rounded-full overflow-hidden ml-2">
                                 <div
                                    className={cn("h-full", (host.cpuUsage || 0) > 80 ? "bg-rose-500" : "bg-[#00ff9d]")}
                                    style={{width: `${host.cpuUsage || 0}%`}}
                                 ></div>
                              </div>
                           </div>
                        </td>
                        <td className="px-6 py-4">
                           <div className="flex items-center">
                              <span className="text-xs w-8">{host.memUsage || 0}%</span>
                              <div className="h-1.5 w-24 bg-[#020617] rounded-full overflow-hidden ml-2">
                                 <div
                                    className={cn("h-full", (host.memUsage || 0) > 80 ? "bg-rose-500" : "bg-[#38bdf8]")}
                                    style={{width: `${host.memUsage || 0}%`}}
                                 ></div>
                              </div>
                           </div>
                        </td>
                        <td className="px-6 py-4">
                           <span className={cn(
                              "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                              host.status === 'Running' ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-slate-500/10 text-slate-400 border-slate-500/20"
                           )}>
                              {host.status}
                           </span>
                        </td>
                        <td className="px-6 py-4">
                           <button className="text-[#38bdf8] hover:text-white text-xs">Detail</button>
                        </td>
                     </tr>
                  ))}
               </tbody>
            </table>
         </div>
      </div>
    </div>
  );

  const renderClusterTopology = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
         <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
               <Map className="w-5 h-5 mr-2 text-[#a855f7]" /> 集群拓扑 (Rack Awareness)
            </h3>
            <div className="flex space-x-2">
               <button className="px-3 py-1.5 bg-white/5 rounded-lg text-xs text-slate-300 hover:text-white">Refresh Topology</button>
               <button className="px-3 py-1.5 bg-white/5 rounded-lg text-xs text-slate-300 hover:text-white">Edit Racks</button>
            </div>
         </div>
         
         <div className="bg-[#020617] border border-white/5 rounded-xl p-8 min-h-[500px] relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
            <div className="relative z-10 grid grid-cols-1 md:grid-cols-3 gap-8">
               {['rack-01', 'rack-02', 'rack-03'].map(rack => (
                  <div key={rack} className="border border-slate-700 bg-slate-800/50 rounded-xl p-4">
                     <div className="flex justify-between items-center mb-4 border-b border-slate-700 pb-2">
                        <span className="font-bold text-slate-300 uppercase text-xs">{rack}</span>
                        <Server className="w-4 h-4 text-slate-500" />
                     </div>
                     <div className="space-y-3">
                        {hosts.filter(h => h.rack === rack).map(host => (
                           <div key={host.name} className="bg-[#0f172a] p-3 rounded-lg border border-slate-700 flex items-center justify-between group hover:border-[#38bdf8] transition-colors cursor-pointer">
                              <div className="flex items-center">
                                 <div className={cn(
                                    "w-2 h-2 rounded-full mr-2",
                                    host.status === 'Running' ? "bg-[#00ff9d] shadow-[0_0_5px_#00ff9d]" : "bg-slate-500"
                                 )}></div>
                                 <div>
                                    <div className="text-xs font-bold text-white group-hover:text-[#38bdf8]">{host.name}</div>
                                    <div className="text-[10px] text-slate-500">{host.ip}</div>
                                 </div>
                              </div>
                              <div className="text-[10px] text-slate-400">{host.role === 'Control Plane' ? 'Master' : 'Worker'}</div>
                           </div>
                        ))}
                        {hosts.filter(h => h.rack === rack).length === 0 && (
                           <div className="text-center py-4 text-xs text-slate-600 italic">Empty Rack</div>
                        )}
                     </div>
                  </div>
               ))}
            </div>
         </div>
      </div>
    </div>
  );

  const renderHardwareDiagnosis = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
         <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
               <StethoscopeIcon className="w-5 h-5 mr-2 text-rose-500" /> 硬件诊断 (Hardware Health)
            </h3>
            <button className="px-3 py-1.5 bg-rose-500/10 text-rose-500 border border-rose-500/20 rounded-lg text-xs font-bold hover:bg-rose-500/20">
               Run Full Diagnostic
            </button>
         </div>

         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {hardwareHealth.map(h => (
               <div key={h.host} className="p-4 bg-white/5 border border-white/5 rounded-xl hover:border-white/10 transition-all">
                  <div className="flex justify-between items-center mb-3">
                     <span className="font-bold text-white text-sm">{h.host}</span>
                     <span className={cn(
                        "text-[10px] px-1.5 py-0.5 rounded",
                        h.diskHealth === 'Healthy' ? "bg-[#00ff9d]/10 text-[#00ff9d]" : 
                        h.diskHealth === 'Warning' ? "bg-amber-500/10 text-amber-500" : "bg-slate-700 text-slate-400"
                     )}>{h.diskHealth}</span>
                  </div>
                  <div className="space-y-2 text-xs text-slate-400">
                     <div className="flex justify-between">
                        <span className="flex items-center"><HardDrive className="w-3 h-3 mr-1" /> SMART</span>
                        <span className={h.smartStatus === 'Pass' ? "text-[#00ff9d]" : "text-amber-500"}>{h.smartStatus}</span>
                     </div>
                     <div className="flex justify-between">
                        <span className="flex items-center"><Thermometer className="w-3 h-3 mr-1" /> Temp</span>
                        <span className={h.temp > 50 ? "text-amber-500" : "text-slate-300"}>{h.temp > 0 ? h.temp + '°C' : 'N/A'}</span>
                     </div>
                     <div className="flex justify-between">
                        <span className="flex items-center"><Network className="w-3 h-3 mr-1" /> Net Err</span>
                        <span className={h.networkErrors > 0 ? "text-rose-500" : "text-slate-300"}>{h.networkErrors}</span>
                     </div>
                  </div>
               </div>
            ))}
         </div>
         
         <div className="glass-panel bg-[#020617] border border-white/5 rounded-xl p-4">
            <h4 className="font-bold text-white mb-2 text-sm">Diagnostic Log</h4>
            <div className="font-mono text-[10px] text-slate-400 space-y-1">
               <div>[2023-10-27 10:00:01] Starting cluster-wide hardware scan...</div>
               <div>[2023-10-27 10:00:05] Checking Worker01 disk /dev/sdb... <span className="text-amber-500">WARNING: Reallocated Sector Count increased</span></div>
               <div>[2023-10-27 10:00:12] Checking Network interfaces... <span className="text-[#00ff9d]">OK</span></div>
               <div>[2023-10-27 10:00:15] Checking CPU Temperatures... <span className="text-[#00ff9d]">OK (Avg 42°C)</span></div>
               <div>[2023-10-27 10:00:20] Scan complete. Found 1 warning.</div>
            </div>
         </div>
      </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Notification */}
      {notification && (
        <div className={cn(
          "fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center",
          notification.type === 'success' ? 'bg-emerald-500/90 text-white' :
          notification.type === 'error' ? 'bg-rose-500/90 text-white' :
          'bg-blue-500/90 text-white'
        )}>
          {notification.type === 'success' && <CheckCircle className="w-5 h-5 mr-2" />}
          {notification.type === 'error' && <AlertTriangle className="w-5 h-5 mr-2" />}
          {notification.message}
        </div>
      )}

      {/* 功能工具栏 */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold flex items-center hover:bg-[#00e68e] transition-all"
        >
          <UserPlus className="w-4 h-4 mr-2" /> 添加主机
        </button>
        <button
          onClick={handleBatchStart}
          disabled={loading}
          className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/10 flex items-center transition-all disabled:opacity-50"
        >
          <Play className="w-4 h-4 mr-2 text-[#00ff9d]" /> 批量启动
        </button>
        <button
          onClick={handleBatchStop}
          disabled={loading}
          className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/10 flex items-center transition-all disabled:opacity-50"
        >
          <Square className="w-4 h-4 mr-2 text-rose-500" /> 批量停止
        </button>
        <button
          onClick={handleBatchRestart}
          disabled={loading}
          className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm font-medium hover:bg-white/10 flex items-center transition-all disabled:opacity-50"
        >
          <RefreshCcw className="w-4 h-4 mr-2 text-[#38bdf8]" /> 批量重启
        </button>
        {selectedHosts.length > 0 && (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="px-4 py-2 bg-rose-500/20 border border-rose-500/30 text-rose-400 rounded-lg text-sm font-medium hover:bg-rose-500/30 flex items-center transition-all"
          >
            <Trash2 className="w-4 h-4 mr-2" /> 删除选中 ({selectedHosts.length})
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 1. 主机管理列表 */}
        <div className="lg:col-span-2 glass-panel rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-white/5 flex justify-between items-center">
            <h3 className="font-bold text-white flex items-center">
              <Server className="w-5 h-5 mr-2 text-[#38bdf8]" /> 主机列表
            </h3>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-6 py-3">主机名 / IP</th>
                <th className="px-6 py-3">角色</th>
                <th className="px-6 py-3">资源 (C/M)</th>
                <th className="px-6 py-3">状态</th>
                <th className="px-6 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {hosts.map(host => (
                 <tr key={host.hostname || host.name} className="hover:bg-white/5 transition-colors">
                  <td className="px-6 py-4">
                    <input
                      type="checkbox"
                      checked={selectedHosts.includes(host.hostname || host.name || '')}
                      onChange={() => toggleHostSelection(host.hostname || host.name || '')}
                      className="w-4 h-4 rounded border-white/20 bg-white/5 text-[#00ff9d] focus:ring-[#00ff9d] mr-3"
                    />
                    <div className="font-medium text-white inline">{host.hostname || host.name}</div>
                    <div className="text-xs text-slate-500 ml-7">{host.ip}</div>
                  </td>
                  <td className="px-6 py-4 text-xs">{host.role}</td>
                  <td className="px-6 py-4 text-xs font-mono">{host.cores}C / {host.mem}</td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                      host.status === 'Running' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    )}>
                      {host.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => {
                        setSelectedHosts([host.hostname || host.name || '']);
                        setShowDeleteConfirm(true);
                      }}
                      className="text-rose-400 hover:text-rose-300 text-xs mr-3"
                    >
                      删除
                    </button>
                    <button className="text-[#38bdf8] hover:underline text-xs">详情</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 2. Agent & Worker 管理 */}
        <div className="space-y-6">
          <div className="glass-panel p-6 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center">
              <ShieldCheck className="w-5 h-5 mr-2 text-[#00ff9d]" /> Agent 管理
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-white/5">
                <span className="text-sm">运行状态</span>
                <span className="text-xs text-[#00ff9d] font-bold">142 Active</span>
              </div>
              <button className="w-full py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10 transition-all">
                版本热升级 (JMX/Exporter)
              </button>
              <button className="w-full py-2 bg-white/5 border border-white/10 rounded-lg text-xs hover:bg-white/10 transition-all">
                配置模板库
              </button>
            </div>
          </div>

          <div className="glass-panel p-6 rounded-2xl">
            <h3 className="font-bold text-white mb-4 flex items-center">
              <ShoppingCart className="w-5 h-5 mr-2 text-amber-500" /> 插件市场
            </h3>
            <p className="text-xs text-slate-500 mb-4">扩展集群监控能力，一键安装 Exporter</p>
            <div className="grid grid-cols-2 gap-2">
              {['MySQL Exp', 'Redis Exp', 'Nginx Exp', 'ES Exp'].map(plugin => (
                <div key={plugin} className="p-2 bg-white/5 border border-white/5 rounded text-[10px] text-center hover:border-[#38bdf8] cursor-pointer">
                  {plugin}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* 添加主机模态框 */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[400px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">添加主机</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">主机名 *</label>
                <input
                  type="text"
                  value={newHost.hostname}
                  onChange={(e) => setNewHost({ ...newHost, hostname: e.target.value })}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: worker01"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">IP地址 *</label>
                <input
                  type="text"
                  value={newHost.ip}
                  onChange={(e) => setNewHost({ ...newHost, ip: e.target.value })}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: 192.168.1.100"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Rack</label>
                <input
                  type="text"
                  value={newHost.rackInfo || ''}
                  onChange={(e) => setNewHost({ ...newHost, rackInfo: e.target.value })}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: rack-01"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">角色</label>
                <select
                  value={newHost.role || 'Worker'}
                  onChange={(e) => setNewHost({ ...newHost, role: e.target.value })}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="Master">Master</option>
                  <option value="Worker">Worker</option>
                  <option value="Gateway">Gateway</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-white/5 text-white rounded-lg text-sm hover:bg-white/10"
                >
                  取消
                </button>
                <button
                  onClick={handleAddHost}
                  disabled={loading}
                  className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] disabled:opacity-50"
                >
                  {loading ? '添加中...' : '添加'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认模态框 */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[400px]">
            <div className="text-center">
              <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">确认删除</h3>
              <p className="text-sm text-slate-400 mb-6">
                确定要删除选中的 {selectedHosts.length} 台主机吗？此操作不可恢复。
              </p>
              <div className="flex justify-center gap-2">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-4 py-2 bg-white/5 text-white rounded-lg text-sm hover:bg-white/10"
                >
                  取消
                </button>
                <button
                  onClick={async () => {
                    for (const hostname of selectedHosts) {
                      await handleDeleteHost(hostname);
                    }
                  }}
                  disabled={loading}
                  className="px-4 py-2 bg-rose-500 text-white rounded-lg text-sm font-bold hover:bg-rose-600 disabled:opacity-50"
                >
                  {loading ? '删除中...' : '确认删除'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeSubView === '资源监控' && renderResourceMonitoring()}
      {activeSubView === '集群拓扑' && renderClusterTopology()}
      {activeSubView === '硬件诊断' && renderHardwareDiagnosis()}
      {(!activeSubView || activeSubView === '') && renderOverview()}
    </>
  );
}

function StethoscopeIcon(props: React.SVGProps<SVGSVGElement>) {
   return (
      <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
      <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" />
      <circle cx="20" cy="10" r="2" />
    </svg>
   )
}
