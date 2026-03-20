import React, { useState, useEffect, useRef } from 'react';
import {
  Activity, Terminal, Clock, BellRing, Search, Server,
  Play, Pause, RotateCw, AlertTriangle, CheckCircle, XCircle,
  Calendar, MoreHorizontal, Plus, Settings, Eye, Edit, Trash2
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { cn } from '@/lib/utils';

interface PrometheusConfig {
  url: string;
  refreshInterval: number; // seconds
  timeRange: string; // 5m, 1h, 24h
}

interface ELKConfig {
  elasticsearchUrl: string;
  kibanaUrl: string;
  username: string;
  password: string;
}

interface AlertRule {
  id: number;
  name: string;
  severity: 'critical' | 'warning' | 'info';
  condition: string;
  duration: string;
  receiver: string;
}

interface Task {
  id: number;
  name: string;
  type: string;
  schedule: string;
  lastRun: string;
  nextRun: string;
  status: 'running' | 'pending' | 'success' | 'failed' | 'stopped';
  progress: number;
  owner: string;
  workflow?: TaskWorkflow;
}

interface TaskWorkflow {
  nodes: { id: string; name: string; type: string }[];
  edges: { from: string; to: string }[];
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  host: string;
  source: string;
}

export default function OpsMgt({ activeSubView }: { activeSubView?: string }) {
  const [tasks, setTasks] = useState<Task[]>([
    {
      id: 1,
      name: 'Daily ETL Workflow',
      type: 'Workflow',
      schedule: '0 0 * * *',
      lastRun: '2023-10-27 00:00',
      nextRun: '2023-10-28 00:00',
      status: 'running',
      progress: 45,
      owner: 'data_eng',
      workflow: {
        nodes: [
          { id: '1', name: '数据抽取', type: 'start' },
          { id: '2', name: '数据转换', type: 'process' },
          { id: '3', name: '数据加载', type: 'end' }
        ],
        edges: [
          { from: '1', to: '2' },
          { from: '2', to: '3' }
        ]
      }
    },
    {
      id: 2,
      name: 'Hourly Aggregation',
      type: 'Spark',
      schedule: '0 * * * *',
      lastRun: '2023-10-27 10:00',
      nextRun: '2023-10-27 11:00',
      status: 'pending',
      progress: 0,
      owner: 'analyst_bob'
    },
    {
      id: 3,
      name: 'Data Cleanup',
      type: 'Shell',
      schedule: '0 2 * * *',
      lastRun: '2023-10-27 02:00',
      nextRun: '2023-10-28 02:00',
      status: 'success',
      progress: 100,
      owner: 'admin'
    },
    {
      id: 4,
      name: 'Model Retraining',
      type: 'Python',
      schedule: '0 0 * * 0',
      lastRun: '2023-10-22 00:00',
      nextRun: '2023-10-29 00:00',
      status: 'failed',
      progress: 20,
      owner: 'ds_team'
    },
    {
      id: 5,
      name: 'Log Rotation',
      type: 'System',
      schedule: '0 4 * * *',
      lastRun: '2023-10-27 04:00',
      nextRun: '2023-10-28 04:00',
      status: 'stopped',
      progress: 100,
      owner: 'ops'
    },
  ]);

  const [alertRules, setAlertRules] = useState<AlertRule[]>([
    { id: 1, name: 'CPU过载告警', severity: 'critical', condition: 'CPU > 90%', duration: '5分钟', receiver: '运维团队' },
    { id: 2, name: '内存不足告警', severity: 'warning', condition: '内存使用率 > 85%', duration: '10分钟', receiver: '运维团队' },
    { id: 3, name: '磁盘空间不足', severity: 'warning', condition: '磁盘使用率 > 80%', duration: '30分钟', receiver: '运维团队' },
  ]);

  const [prometheusConfig, setPrometheusConfig] = useState<PrometheusConfig>({
    url: 'http://prometheus:9090',
    refreshInterval: 30,
    timeRange: '1h'
  });

  const [elkConfig, setElkConfig] = useState<ELKConfig>({
    elasticsearchUrl: 'http://elasticsearch:9200',
    kibanaUrl: 'http://kibana:5601',
    username: 'elastic',
    password: 'changeme'
  });

  const [grafanaUrl, setGrafanaUrl] = useState('http://grafana:3000/d/1/cluster-monitoring?orgId=1&refresh=5s');
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editingAlert, setEditingAlert] = useState<AlertRule | null>(null);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // 模拟从Prometheus获取数据
  const fetchMetrics = async () => {
    // 实际项目中这里调用真实的Prometheus API
    console.log('Fetching metrics from Prometheus...');
  };

  // 模拟从ELK获取日志
  const fetchLogs = async (query = '') => {
    // 实际项目中这里调用ELK API
    console.log(`Searching logs with query: ${query}`);

    // 模拟日志数据
    const mockLogs: LogEntry[] = Array.from({ length: 15 }).map((_, i) => ({
      timestamp: `2024-03-10 12:${i.toString().padStart(2, '0')}:23`,
      level: i % 3 === 0 ? 'ERROR' : 'INFO',
      message: i % 3 === 0
        ? `Connection refused to host: worker-0${i % 3} - Caused by: java.net.ConnectException`
        : `Successfully processed batch id: ${1000 + i} - Records: ${Math.floor(Math.random() * 1000)}`,
      host: `worker-0${i % 5}`,
      source: i % 2 === 0 ? 'application.log' : 'system.log'
    }));

    setLogEntries(mockLogs);
  };

  // 任务操作
  const handleTaskAction = (action: 'start' | 'stop' | 'run', taskId: number) => {
    setTasks(tasks.map(task => {
      if (task.id === taskId) {
        let status: Task['status'] = task.status;
        let progress = task.progress;

        if (action === 'start') {
          status = 'running';
          progress = 0;
        } else if (action === 'stop') {
          status = 'stopped';
        } else if (action === 'run') {
          status = 'running';
          progress = 0;
        }

        return { ...task, status, progress };
      }
      return task;
    }));
  };

  // 保存任务
  const saveTask = (task: Omit<Task, 'id' | 'lastRun' | 'nextRun' | 'status' | 'progress'>) => {
    if (editingTask) {
      setTasks(tasks.map(t => t.id === editingTask.id
        ? { ...t, ...task }
        : t
      ));
    } else {
      const newTask: Task = {
        ...task,
        id: Math.max(0, ...tasks.map(t => t.id)) + 1,
        lastRun: '-',
        nextRun: '待计算',
        status: 'pending',
        progress: 0
      };
      setTasks([...tasks, newTask]);
    }
    setIsTaskModalOpen(false);
    setEditingTask(null);
  };

  // 保存告警规则
  const saveAlertRule = (rule: Omit<AlertRule, 'id'>) => {
    if (editingAlert) {
      setAlertRules(rules => rules.map(r => r.id === editingAlert.id
        ? { ...r, ...rule }
        : r
      ));
    } else {
      const newRule: AlertRule = {
        ...rule,
        id: Math.max(0, ...alertRules.map(r => r.id)) + 1
      };
      setAlertRules([...alertRules, newRule]);
    }
    setIsAlertModalOpen(false);
    setEditingAlert(null);
  };

  // 删除告警规则
  const deleteAlertRule = (id: number) => {
    setAlertRules(alertRules.filter(r => r.id !== id));
  };

  // 初始化
  useEffect(() => {
    fetchMetrics();
    fetchLogs();
  }, []);

  const renderRealTimeMonitoring = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Prometheus配置 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Activity className="w-5 h-5 mr-2 text-[#00ff9d]" /> Prometheus监控
          </h3>
          <button className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-[10px] text-slate-300 hover:bg-white/10 transition-all flex items-center">
            <Settings className="w-3 h-3 mr-1" /> 配置
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">Prometheus地址</label>
            <input
              type="text"
              value={prometheusConfig.url}
              onChange={(e) => setPrometheusConfig({...prometheusConfig, url: e.target.value})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">刷新间隔(秒)</label>
            <select
              value={prometheusConfig.refreshInterval}
              onChange={(e) => setPrometheusConfig({...prometheusConfig, refreshInterval: parseInt(e.target.value)})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            >
              <option value={15}>15秒</option>
              <option value={30}>30秒</option>
              <option value={60}>1分钟</option>
              <option value={300}>5分钟</option>
            </select>
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">时间范围</label>
            <select
              value={prometheusConfig.timeRange}
              onChange={(e) => setPrometheusConfig({...prometheusConfig, timeRange: e.target.value})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            >
              <option value="5m">最近5分钟</option>
              <option value="15m">最近15分钟</option>
              <option value="30m">最近30分钟</option>
              <option value="1h">最近1小时</option>
              <option value="6h">最近6小时</option>
              <option value="24h">最近24小时</option>
              <option value="7d">最近7天</option>
            </select>
          </div>
        </div>

        {/* Grafana面板 */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-white font-bold">Grafana监控看板</h4>
            <input
              type="text"
              value={grafanaUrl}
              onChange={(e) => setGrafanaUrl(e.target.value)}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-96 text-white text-sm"
              placeholder="输入Grafana面板URL"
            />
          </div>
          <div className="h-[600px] w-full border border-white/10 rounded-xl overflow-hidden">
            <iframe
              src={grafanaUrl}
              className="w-full h-full"
              title="Grafana监控面板"
              sandbox="allow-same-origin allow-scripts"
            />
          </div>
        </div>
      </div>

      {/* 监控图表 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-white font-bold">CPU使用率</h4>
              <span className="text-xs text-[#00ff9d]">平均: 45%</span>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={Array.from({ length: 30 }).map((_, i) => ({
                  time: i,
                  value: Math.floor(Math.random() * 60) + 20
                }))}>
                  <Area type="monotone" dataKey="value" stroke="#00ff9d" fill="#00ff9d20" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-white font-bold">内存使用率</h4>
              <span className="text-xs text-[#38bdf8]">平均: 65%</span>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={Array.from({ length: 30 }).map((_, i) => ({
                  time: i,
                  value: Math.floor(Math.random() * 40) + 50
                }))}>
                  <Area type="monotone" dataKey="value" stroke="#38bdf8" fill="#38bdf820" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderLogAnalysis = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* ELK配置 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Terminal className="w-5 h-5 mr-2 text-[#f59e0b]" /> ELK日志分析
          </h3>
          <button className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-[10px] text-slate-300 hover:bg-white/10 transition-all flex items-center">
            <Settings className="w-3 h-3 mr-1" /> 配置ELK
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">Elasticsearch地址</label>
            <input
              type="text"
              value={elkConfig.elasticsearchUrl}
              onChange={(e) => setElkConfig({...elkConfig, elasticsearchUrl: e.target.value})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">Kibana地址</label>
            <input
              type="text"
              value={elkConfig.kibanaUrl}
              onChange={(e) => setElkConfig({...elkConfig, kibanaUrl: e.target.value})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">用户名</label>
            <input
              type="text"
              value={elkConfig.username}
              onChange={(e) => setElkConfig({...elkConfig, username: e.target.value})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">密码</label>
            <input
              type="password"
              value={elkConfig.password}
              onChange={(e) => setElkConfig({...elkConfig, password: e.target.value})}
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
        </div>
      </div>

      {/* 日志搜索 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Search className="w-5 h-5 mr-2 text-[#a855f7]" /> 全局日志搜索
          </h3>
          <button
            onClick={() => fetchLogs(searchQuery)}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Search className="w-4 h-4 mr-2" /> 执行查询
          </button>
        </div>

        <div className="mb-4">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder='输入搜索查询 (例如: error AND "timeout" NOT debug)'
            className="bg-[#020617] border border-white/10 rounded-lg px-4 py-3 w-full text-white"
          />
        </div>

        {/* 日志结果 */}
        <div className="space-y-2 font-mono text-xs text-slate-400 h-[500px] overflow-y-auto custom-scrollbar p-4 bg-[#020617] rounded-lg border border-white/5">
          {logEntries.map((log, index) => (
            <div key={index} className="hover:bg-white/5 p-3 rounded cursor-pointer border-b border-white/5 last:border-b-0">
              <div className="flex justify-between items-start mb-1">
                <span className="text-[#38bdf8]">{log.timestamp}</span>
                <span className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-bold",
                  log.level === 'ERROR' ? "text-rose-500 bg-rose-500/10" :
                  log.level === 'WARN' ? "text-amber-500 bg-amber-500/10" : "text-[#00ff9d] bg-[#00ff9d]/10"
                )}>{log.level}</span>
              </div>
              <div className="text-slate-300 mb-1">{log.message}</div>
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>来源: {log.source}</span>
                <span>主机: {log.host}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderTaskScheduling = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Clock className="w-5 h-5 mr-2 text-[#a855f7]" /> 任务调度中心
          </h3>
          <div className="flex space-x-3">
            <button
              onClick={() => {}}
              className="px-3 py-1.5 bg-white/5 text-slate-300 rounded-lg text-xs hover:text-white flex items-center"
            >
              <Calendar className="w-3 h-3 mr-1" /> View Schedule
            </button>
            <button
              onClick={() => { setEditingTask(null); setIsTaskModalOpen(true); }}
              className="px-3 py-1.5 bg-[#00ff9d] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#00e68e] flex items-center"
            >
              <Plus className="w-3 h-3 mr-1" /> New Task
            </button>
          </div>
        </div>

        {/* 调度工作流视图 */}
        {selectedTask?.workflow && (
          <div className="mb-6 glass-panel p-4 rounded-xl">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-white font-bold">工作流: {selectedTask.name}</h4>
              <button
                onClick={() => setSelectedTask(null)}
                className="text-xs text-slate-400 hover:text-white"
              >
                关闭
              </button>
            </div>
            <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl">
              {selectedTask.workflow.nodes.map(node => (
                <div key={node.id} className="flex flex-col items-center">
                  <div className={cn(
                    "w-16 h-16 rounded-full flex items-center justify-center mb-2",
                    node.type === 'start' ? "bg-[#00ff9d] text-[#020617]" :
                    node.type === 'end' ? "bg-rose-500 text-white" : "bg-[#38bdf8] text-white"
                  )}>
                    {node.id}
                  </div>
                  <span className="text-xs text-white">{node.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 任务列表 */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-500 uppercase bg-white/5">
              <tr>
                <th className="px-4 py-3 rounded-l-lg">Task Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Schedule (Cron)</th>
                <th className="px-4 py-3">Last Run</th>
                <th className="px-4 py-3">Next Run</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Status / Progress</th>
                <th className="px-4 py-3 rounded-r-lg">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {tasks.map(task => (
                <tr key={task.id} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-white">{task.name}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-1 rounded text-[10px] bg-white/10 text-slate-300 border border-white/10">
                      {task.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400 font-mono text-xs">{task.schedule}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{task.lastRun}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{task.nextRun}</td>
                  <td className="px-4 py-3 text-slate-300 text-xs">{task.owner}</td>
                  <td className="px-4 py-3">
                    <div className="w-32">
                      <div className="flex justify-between items-center mb-1">
                        <span className={cn(
                          "text-[10px] font-bold",
                          task.status === 'running' ? "text-[#38bdf8]" :
                          task.status === 'success' ? "text-[#00ff9d]" :
                          task.status === 'failed' ? "text-rose-500" :
                          task.status === 'stopped' ? "text-slate-500" : "text-amber-500"
                        )}>{task.status}</span>
                        <span className="text-[10px] text-slate-500">{task.progress}%</span>
                      </div>
                      <div className="h-1 w-full bg-[#020617] rounded-full overflow-hidden">
                        <div
                          className={cn(
                            "h-full",
                            task.status === 'running' ? "bg-[#38bdf8] animate-pulse" :
                            task.status === 'success' ? "bg-[#00ff9d]" :
                            task.status === 'failed' ? "bg-rose-500" : "bg-amber-500"
                          )}
                          style={{ width: `${task.progress}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    <div className="flex space-x-2">
                      {task.status === 'running' ? (
                        <button
                          onClick={() => handleTaskAction('stop', task.id)}
                          className="p-1 hover:text-rose-500 hover:bg-rose-500/10 rounded"
                          title="Stop"
                        >
                          <Pause className="w-3 h-3" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleTaskAction('start', task.id)}
                          className="p-1 hover:text-[#00ff9d] hover:bg-[#00ff9d]/10 rounded"
                          title="Start"
                        >
                          <Play className="w-3 h-3" />
                        </button>
                      )}
                      <button
                        onClick={() => handleTaskAction('run', task.id)}
                        className="p-1 hover:text-[#38bdf8] hover:bg-[#38bdf8]/10 rounded"
                        title="Run Now"
                      >
                        <RotateCw className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => setSelectedTask(task)}
                        className="p-1 hover:text-white hover:bg-white/10 rounded"
                        title="Workflow"
                      >
                        <Server className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => {}}
                        className="p-1 hover:text-white hover:bg-white/10 rounded"
                        title="Logs"
                      >
                        <Terminal className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => { setEditingTask(task); setIsTaskModalOpen(true); }}
                        className="p-1 hover:text-white hover:bg-white/10 rounded"
                        title="Edit"
                      >
                        <Edit className="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  const renderAlertCenter = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* 告警策略配置 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <BellRing className="w-5 h-5 mr-2 text-[#a855f7]" /> 告警策略配置 (夜莺)
          </h3>
          <button
            onClick={() => { setEditingAlert(null); setIsAlertModalOpen(true); }}
            className="px-3 py-1.5 bg-[#00ff9d] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Plus className="w-3 h-3 mr-1" /> 新建策略
          </button>
        </div>

        {/* 夜莺告警配置 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">夜莺地址</label>
            <input
              type="text"
              defaultValue="http://n9e:10000"
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">API密钥</label>
            <input
              type="password"
              className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm"
            />
          </div>
          <div className="bg-white/5 p-4 rounded-xl">
            <label className="text-sm text-slate-400 mb-2 block">告警接收组</label>
            <select className="bg-[#020617] border border-white/10 rounded-lg px-3 py-2 w-full text-white text-sm">
              <option>运维团队</option>
              <option>开发团队</option>
              <option>管理层</option>
            </select>
          </div>
        </div>

        {/* 告警规则列表 */}
        <div className="space-y-3">
          {alertRules.map(rule => (
            <div key={rule.id} className="glass-panel p-4 rounded-xl flex items-center justify-between">
              <div>
                <div className="flex items-center mb-2">
                  <h4 className="text-white font-bold">{rule.name}</h4>
                  <span className={cn(
                    "ml-2 px-2 py-0.5 rounded text-[10px] font-bold",
                    rule.severity === 'critical' ? "bg-rose-500/20 text-rose-500" :
                    rule.severity === 'warning' ? "bg-amber-500/20 text-amber-500" : "bg-blue-500/20 text-blue-500"
                  )}>
                    {rule.severity === 'critical' ? '严重' : rule.severity === 'warning' ? '警告' : '信息'}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  条件: {rule.condition} | 持续: {rule.duration} | 接收者: {rule.receiver}
                </div>
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => setEditingAlert(rule)}
                  className="p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded"
                >
                  <Edit className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteAlertRule(rule.id)}
                  className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 当前告警 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <AlertTriangle className="w-5 h-5 mr-2 text-rose-500" /> 当前告警
          </h3>
          <span className="text-xs text-rose-500 flex items-center">
            <AlertTriangle className="w-3 h-3 mr-1" /> 3 Active Alerts
          </span>
        </div>

        <div className="space-y-3">
          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white font-bold">生产数据库CPU过高</span>
              <span className="text-xs text-rose-500">持续 5 分钟</span>
            </div>
            <p className="text-sm text-slate-300 mb-2">CPU使用率超过90%，当前值: 94%</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">源: db-prod-01</span>
              <button className="px-3 py-1 bg-rose-500 text-white rounded text-xs">查看详情</button>
            </div>
          </div>

          <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white font-bold">磁盘空间不足</span>
              <span className="text-xs text-amber-500">持续 15 分钟</span>
            </div>
            <p className="text-sm text-slate-300 mb-2">磁盘使用率超过85%，当前值: 87%</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">源: node-03</span>
              <button className="px-3 py-1 bg-amber-500 text-white rounded text-xs">查看详情</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* 监控概览 */}
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Activity className="w-5 h-5 mr-2 text-[#00ff9d]" /> 监控概览
          </h3>
          <button className="text-xs text-[#00ff9d] hover:underline">
            View Full Monitoring
          </button>
        </div>
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={Array.from({ length: 20 }).map((_, i) => ({
              time: i,
              cpu: Math.floor(Math.random() * 40) + 20,
              mem: Math.floor(Math.random() * 30) + 40,
            }))}>
              <defs>
                <linearGradient id="colorCpuSmall" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00ff9d" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#00ff9d" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.3} />
              <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '8px', color: '#fff'}} />
              <Area type="monotone" dataKey="cpu" stroke="#00ff9d" fillOpacity={1} fill="url(#colorCpuSmall)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 日志分析概览 */}
        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-white flex items-center">
              <Terminal className="w-5 h-5 mr-2 text-[#f59e0b]" /> 日志分析
            </h3>
            <span className="text-xs text-rose-500 flex items-center">
              <AlertTriangle className="w-3 h-3 mr-1" /> 5 Errors (1h)
            </span>
          </div>
          <div className="space-y-2 font-mono text-[10px] text-slate-400 h-[200px] overflow-y-auto custom-scrollbar p-2 bg-[#020617] rounded-lg border border-white/5">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="hover:bg-white/5 p-1 rounded cursor-pointer truncate">
                <span className="text-[#38bdf8]">12:0{i}:23</span>
                <span className={i % 3 === 0 ? "text-rose-500 ml-2" : "text-[#00ff9d] ml-2"}>
                  {i % 3 === 0 ? "[ERROR]" : "[INFO]"}
                </span>
                <span className="ml-2 text-slate-300">Connection refused to host...</span>
              </div>
            ))}
          </div>
        </div>

        {/* 任务调度概览 */}
        <div className="glass-panel p-6 rounded-2xl">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center">
            <Clock className="w-5 h-5 mr-2 text-[#a855f7]" /> 任务调度
          </h3>
          <div className="space-y-3">
            {tasks.slice(0, 3).map(task => (
              <div key={task.name} className="p-3 bg-white/5 rounded-xl border border-white/5">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-bold text-white">{task.name}</span>
                  <span className={cn(
                    "text-[10px] px-1.5 rounded",
                    task.status === 'running' ? "bg-[#38bdf8]/10 text-[#38bdf8]" :
                    task.status === 'success' ? "bg-[#00ff9d]/10 text-[#00ff9d]" : "bg-slate-700 text-slate-300"
                  )}>{task.status}</span>
                </div>
                <div className="h-1.5 w-full bg-[#020617] rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full",
                      task.status === 'running' ? "bg-[#38bdf8]" :
                      task.status === 'success' ? "bg-[#00ff9d]" : "bg-slate-500"
                    )}
                    style={{ width: `${task.progress}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // 任务表单模态框
  const TaskModal = () => {
    if (!isTaskModalOpen) return null;

    const [formData, setFormData] = useState({
      name: editingTask?.name || '',
      type: editingTask?.type || 'Shell',
      schedule: editingTask?.schedule || '0 0 * * *',
      owner: editingTask?.owner || '',
      workflow: editingTask?.workflow || undefined
    });

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-lg p-4">
        <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
          <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
            <h3 className="text-xl font-bold text-white">
              {editingTask ? '编辑任务' : '新建任务'}
            </h3>
            <button
              onClick={() => { setIsTaskModalOpen(false); setEditingTask(null); }}
              className="text-slate-400 hover:text-white"
            >
              <XCircle className="w-6 h-6" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-300 mb-1 block">任务名称 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="输入任务名称"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">任务类型 *</label>
              <select
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                value={formData.type}
                onChange={(e) => setFormData({...formData, type: e.target.value})}
              >
                <option>Shell</option>
                <option>Python</option>
                <option>Spark</option>
                <option>Workflow</option>
                <option>System</option>
              </select>
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">Cron表达式 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="0 0 * * * (每天0点)"
                value={formData.schedule}
                onChange={(e) => setFormData({...formData, schedule: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">负责人 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="输入负责人"
                value={formData.owner}
                onChange={(e) => setFormData({...formData, owner: e.target.value})}
              />
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-5 mt-4 border-t border-white/10">
            <button
              onClick={() => { setIsTaskModalOpen(false); setEditingTask(null); }}
              className="px-4 py-2 rounded-lg border border-slate-500 text-white hover:bg-white/5 transition-colors"
            >
              取消
            </button>
            <button
              onClick={() => saveTask(formData)}
              disabled={!formData.name || !formData.schedule || !formData.owner}
              className={cn(
                "px-4 py-2 rounded-lg flex items-center",
                !formData.name || !formData.schedule || !formData.owner
                  ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                  : "bg-[#00ff9d] text-[#020617] hover:bg-[#00e68e]"
              )}
            >
              {editingTask ? '更新任务' : '创建任务'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // 告警规则表单模态框
  const AlertModal = () => {
    if (!isAlertModalOpen) return null;

    const [formData, setFormData] = useState({
      name: editingAlert?.name || '',
      severity: editingAlert?.severity || 'warning',
      condition: editingAlert?.condition || '',
      duration: editingAlert?.duration || '5分钟',
      receiver: editingAlert?.receiver || '运维团队'
    });

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-lg p-4">
        <div className="glass-panel p-6 rounded-2xl w-full max-w-md">
          <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
            <h3 className="text-xl font-bold text-white">
              {editingAlert ? '编辑告警策略' : '新建告警策略'}
            </h3>
            <button
              onClick={() => { setIsAlertModalOpen(false); setEditingAlert(null); }}
              className="text-slate-400 hover:text-white"
            >
              <XCircle className="w-6 h-6" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-300 mb-1 block">策略名称 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="输入策略名称"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">严重程度 *</label>
              <select
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                value={formData.severity}
                onChange={(e) => setFormData({...formData, severity: e.target.value as any})}
              >
                <option value="info">信息</option>
                <option value="warning">警告</option>
                <option value="critical">严重</option>
              </select>
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">告警条件 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="例如: CPU > 90%"
                value={formData.condition}
                onChange={(e) => setFormData({...formData, condition: e.target.value})}
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">持续时间 *</label>
              <select
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                value={formData.duration}
                onChange={(e) => setFormData({...formData, duration: e.target.value})}
              >
                <option value="1分钟">1分钟</option>
                <option value="5分钟">5分钟</option>
                <option value="10分钟">10分钟</option>
                <option value="30分钟">30分钟</option>
                <option value="1小时">1小时</option>
              </select>
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-1 block">告警接收者 *</label>
              <input
                type="text"
                className="bg-[#111827] border border-white/10 rounded-lg px-4 py-2 w-full text-white focus:border-[#00ff9d] focus:outline-none transition-colors"
                placeholder="输入接收者"
                value={formData.receiver}
                onChange={(e) => setFormData({...formData, receiver: e.target.value})}
              />
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-5 mt-4 border-t border-white/10">
            <button
              onClick={() => { setIsAlertModalOpen(false); setEditingAlert(null); }}
              className="px-4 py-2 rounded-lg border border-slate-500 text-white hover:bg-white/5 transition-colors"
            >
              取消
            </button>
            <button
              onClick={() => saveAlertRule(formData)}
              disabled={!formData.name || !formData.condition || !formData.receiver}
              className={cn(
                "px-4 py-2 rounded-lg flex items-center",
                !formData.name || !formData.condition || !formData.receiver
                  ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                  : "bg-[#00ff9d] text-[#020617] hover:bg-[#00e68e]"
              )}
            >
              {editingAlert ? '更新策略' : '创建策略'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      {activeSubView === '实时监控' && renderRealTimeMonitoring()}
      {activeSubView === '日志分析' && renderLogAnalysis()}
      {activeSubView === '任务调度' && renderTaskScheduling()}
      {activeSubView === '告警中心' && renderAlertCenter()}
      {(!activeSubView || activeSubView === '') && renderOverview()}

      <TaskModal />
      <AlertModal />
    </>
  );
}
