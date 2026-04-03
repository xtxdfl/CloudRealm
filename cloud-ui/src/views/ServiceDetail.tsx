import { useState, useEffect } from 'react';
import { 
  Layers, Activity, BarChart3, FileText, Package, RefreshCw, Play, Square, 
  RotateCcw, ChevronRight, Server, Cpu, HardDrive, MemoryStick, Network, Clock, 
  CheckCircle, AlertTriangle, XCircle, Zap, Gauge, Database, Sparkles, 
  Workflow, MessageSquare, Radio, GitBranch, Settings, Save, Download
} from 'lucide-react';

interface ServiceInfo {
  name: string;
  version: string;
  status: string;
  role?: string;
  configVersion?: string;
  lastOperation?: string;
  lastOperationTime?: number;
  components?: string[];
}

interface ServiceMetric {
  name: string;
  value: string;
  unit: string;
  trend: 'up' | 'down';
  icon: React.ComponentType<{ className?: string }>;
  iconName: string;
}

interface ComponentInfo {
  name: string;
  host: string;
  status: 'running' | 'stopped' | 'warning';
  pid: number;
  startTime: number;
  memory: string;
  cpu: string;
}

const StatusBadge = ({ status }: { status: string }) => {
  const s = status.toUpperCase();
  if (s === 'HEALTHY') return <span className="flex items-center text-[#00ff9d]"><CheckCircle className="w-4 h-4 mr-1" /> 正常</span>;
  if (s === 'WARNING') return <span className="flex items-center text-amber-500"><AlertTriangle className="w-4 h-4 mr-1" /> 警告</span>;
  if (s === 'STOPPED') return <span className="flex items-center text-slate-500"><XCircle className="w-4 h-4 mr-1" /> 已停止</span>;
  return <span className="flex items-center text-rose-500"><XCircle className="w-4 h-4 mr-1" /> 故障</span>;
};

const getStatusColor = (status: string) => {
  switch (status.toUpperCase()) {
    case 'HEALTHY': return '#00ff9d';
    case 'WARNING': return '#fbbf24';
    case 'CRITICAL': return '#ef4444';
    case 'STOPPED': return '#94a3b8';
    default: return '#94a3b8';
  }
};

const getServiceIcon = (serviceName: string) => {
  const icons: Record<string, React.ComponentType<{ className?: string }>> = {
    'HDFS': Database,
    'YARN': Zap,
    'HIVE': Database,
    'KAFKA': MessageSquare,
    'SPARK': Sparkles,
    'HBASE': Database,
    'ZOOKEEPER': Radio,
    'FLINK': Workflow,
  };
  return icons[serviceName.toUpperCase()] || Layers;
};

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Cpu, HardDrive, MemoryStick, Network, Activity, Clock
};

const serviceMetricsConfig: Record<string, { metrics: string[]; configs: string[]; components: string[] }> = {
  'HDFS': {
    metrics: ['NameNode Heap Used', 'DataNodes Live', 'Blocks Total', 'Under Replicated', 'Pending Replication', 'Files Total'],
    configs: ['hdfs-site.xml', 'core-site.xml', 'log4j.properties', 'hdfs-ranger-security.xml'],
    components: ['NameNode', 'SecondaryNameNode', 'DataNode']
  },
  'YARN': {
    metrics: ['Apps Running', 'Apps Pending', 'Containers Running', 'Nodes Live', 'Memory Used', 'VCores Used'],
    configs: ['yarn-site.xml', 'capacity-scheduler.xml', 'log4j.properties', 'yarn-ranger-security.xml'],
    components: ['ResourceManager', 'NodeManager', 'JobHistoryServer']
  },
  'HIVE': {
    metrics: ['Queries Executed', 'Active Connections', 'Metastore Status', 'HCat Status', 'JDBC Connections', 'Tez Containers'],
    configs: ['hive-site.xml', 'hive-env.sh', 'hive-log4j.properties', 'tez-site.xml'],
    components: ['HiveServer2', 'Metastore', 'HCatalog']
  },
  'KAFKA': {
    metrics: ['Brokers Online', 'Topics Count', 'Partitions Total', 'Messages/sec', 'Bytes In/sec', 'Bytes Out/sec'],
    configs: ['server.properties', 'log4j.properties', 'producer.properties', 'consumer.properties'],
    components: ['Broker-1', 'Broker-2', 'Broker-3']
  },
  'SPARK': {
    metrics: ['Running Applications', 'Completed Applications', 'Executors Active', 'Cores Used', 'Memory Used', 'Shuffle Read'],
    configs: ['spark-defaults.conf', 'spark-env.sh', 'log4j.properties', 'metrics.properties'],
    components: ['Master', 'Worker', 'HistoryServer']
  },
  'HBASE': {
    metrics: ['Regions Online', 'Requests/sec', 'Read Latency', 'Write Latency', 'Compact Queue', 'MemStore Size'],
    configs: ['hbase-site.xml', 'hbase-env.sh', 'hbase-log4j.properties', 'regionserver.xml'],
    components: ['HMaster', 'HRegionServer', 'HQuorumPeer']
  },
  'ZOOKEEPER': {
    metrics: ['ZNodes Count', 'Watchers', 'Latency Avg', 'Connections', 'Outstandings', 'Votes'],
    configs: ['zoo.cfg', 'log4j.properties', 'zoo-env.sh'],
    components: ['QuorumPeer']
  },
  'FLINK': {
    metrics: ['Jobs Running', 'Jobs Finished', 'Task Managers', 'Slots Used', 'Task Slots', 'Checkpoint Size'],
    configs: ['flink-conf.yaml', 'log4j.properties', 'masters', 'slaves'],
    components: ['JobManager', 'TaskManager', 'HistoryServer']
  }
};

export default function ServiceDetail({ serviceName }: { serviceName: string }) {
  const [service, setService] = useState<ServiceInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'metrics' | 'configs' | 'components'>('overview');
  const [metrics, setMetrics] = useState<ServiceMetric[]>([]);
  const [components, setComponents] = useState<ComponentInfo[]>([]);

  useEffect(() => {
    fetchServiceDetails();
  }, [serviceName]);

  const fetchServiceDetails = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/services/${serviceName}`);
      if (response.ok) {
        const data = await response.json();
        setService(data);
        generateMockMetrics(data.name);
        generateMockComponents(data.name);
      }
    } catch (error) {
      console.error('Error fetching service details:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateMockMetrics = (serviceName: string) => {
    const config = serviceMetricsConfig[serviceName.toUpperCase()] || serviceMetricsConfig['HDFS'];
    const iconNames = ['Cpu', 'HardDrive', 'MemoryStick', 'Network', 'Activity', 'Clock'];
    const mockMetrics: ServiceMetric[] = config.metrics.map((name, index) => ({
      name,
      value: Math.floor(Math.random() * 10000).toString(),
      unit: name.includes('Used') || name.includes('Size') ? 'GB' : name.includes('Latency') ? 'ms' : name.includes('sec') || name.includes('/sec') ? '/s' : '',
      trend: Math.random() > 0.5 ? 'up' : 'down',
      icon: iconMap[iconNames[index % 6]],
      iconName: iconNames[index % 6]
    }));
    setMetrics(mockMetrics);
  };

  const generateMockComponents = (serviceName: string) => {
    const config = serviceMetricsConfig[serviceName.toUpperCase()] || serviceMetricsConfig['HDFS'];
    const mockComponents: ComponentInfo[] = config.components.map((name, index) => ({
      name,
      host: `worker${index + 1}.cloudrealm.local`,
      status: Math.random() > 0.1 ? 'running' : 'warning',
      pid: Math.floor(Math.random() * 60000 + 1000),
      startTime: Date.now() - Math.random() * 86400000,
      memory: `${Math.floor(Math.random() * 8 + 1)}GB`,
      cpu: `${Math.floor(Math.random() * 40 + 10)}%`
    }));
    setComponents(mockComponents);
  };

  const handleAction = async (action: 'start' | 'stop' | 'restart') => {
    try {
      const response = await fetch(`/api/services/${serviceName}/${action}`, {
        method: 'POST'
      });
      if (response.ok) {
        fetchServiceDetails();
      }
    } catch (error) {
      console.error(`Error performing ${action}:`, error);
    }
  };

  const formatTime = (timestamp?: number) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', { 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const formatUptime = (timestamp: number) => {
    const diff = Date.now() - timestamp;
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}天 ${hours % 24}小时`;
    if (hours > 0) return `${hours}小时`;
    return '< 1小时';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#00ff9d]"></div>
      </div>
    );
  }

  if (!service) {
    return <div className="text-white p-8">服务未找到</div>;
  }

  const statusColor = getStatusColor(service.status);
  const ServiceIcon = getServiceIcon(service.name);
  const config = serviceMetricsConfig[service.name.toUpperCase()] || serviceMetricsConfig['HDFS'];

  return (
    <div className="flex gap-6">
      {/* Left Navigation - Enhanced */}
      <div className="w-64 shrink-0">
        <div className="glass-panel rounded-2xl p-5 sticky top-4">
          {/* Service Header */}
          <div className="flex items-center mb-5 pb-5 border-b border-white/10">
            <div 
              className="w-12 h-12 rounded-xl flex items-center justify-center mr-3 shadow-lg"
              style={{ 
                backgroundColor: `${statusColor}20`,
                boxShadow: `0 0 20px ${statusColor}30`
              }}
            >
              <span style={{ color: statusColor }}>
                <ServiceIcon className="w-6 h-6" />
              </span>
            </div>
            <div>
              <div className="font-bold text-white text-lg">{service.name}</div>
              <div className="text-xs text-slate-500 flex items-center mt-0.5">
                <span className="w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: statusColor }}></span>
                v{service.version}
              </div>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="space-y-1.5">
            <button
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center px-4 py-3 rounded-xl text-left transition-all duration-200 group ${
                activeTab === 'overview' 
                  ? 'bg-gradient-to-r from-[#00ff9d]/20 to-transparent text-[#00ff9d] border-l-2 border-[#00ff9d]' 
                  : 'text-slate-400 hover:bg-white/5 hover:text-white border-l-2 border-transparent'
              }`}
            >
              <Activity className="w-4 h-4 mr-3" />
              <span className="text-sm font-medium">服务概览</span>
              {activeTab === 'overview' && <ChevronRight className="w-4 h-4 ml-auto" />}
            </button>
            <button
              onClick={() => setActiveTab('metrics')}
              className={`w-full flex items-center px-4 py-3 rounded-xl text-left transition-all duration-200 group ${
                activeTab === 'metrics' 
                  ? 'bg-gradient-to-r from-[#00ff9d]/20 to-transparent text-[#00ff9d] border-l-2 border-[#00ff9d]' 
                  : 'text-slate-400 hover:bg-white/5 hover:text-white border-l-2 border-transparent'
              }`}
            >
              <BarChart3 className="w-4 h-4 mr-3" />
              <span className="text-sm font-medium">监控指标</span>
              {activeTab === 'metrics' && <ChevronRight className="w-4 h-4 ml-auto" />}
            </button>
            <button
              onClick={() => setActiveTab('configs')}
              className={`w-full flex items-center px-4 py-3 rounded-xl text-left transition-all duration-200 group ${
                activeTab === 'configs' 
                  ? 'bg-gradient-to-r from-[#00ff9d]/20 to-transparent text-[#00ff9d] border-l-2 border-[#00ff9d]' 
                  : 'text-slate-400 hover:bg-white/5 hover:text-white border-l-2 border-transparent'
              }`}
            >
              <FileText className="w-4 h-4 mr-3" />
              <span className="text-sm font-medium">配置文件</span>
              {activeTab === 'configs' && <ChevronRight className="w-4 h-4 ml-auto" />}
            </button>
            <button
              onClick={() => setActiveTab('components')}
              className={`w-full flex items-center px-4 py-3 rounded-xl text-left transition-all duration-200 group ${
                activeTab === 'components' 
                  ? 'bg-gradient-to-r from-[#00ff9d]/20 to-transparent text-[#00ff9d] border-l-2 border-[#00ff9d]' 
                  : 'text-slate-400 hover:bg-white/5 hover:text-white border-l-2 border-transparent'
              }`}
            >
              <Package className="w-4 h-4 mr-3" />
              <span className="text-sm font-medium">组件详情</span>
              {activeTab === 'components' && <ChevronRight className="w-4 h-4 ml-auto" />}
            </button>
          </nav>

          {/* Component Status Summary */}
          <div className="mt-6 pt-5 border-t border-white/10">
            <div className="text-xs text-slate-500 mb-3 uppercase tracking-wider">组件状态</div>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-[#00ff9d]/10 rounded-xl p-3 text-center">
                <div className="text-xl font-bold text-[#00ff9d]">{components.filter(c => c.status === 'running').length}</div>
                <div className="text-[10px] text-slate-500 mt-1">在线</div>
              </div>
              <div className="bg-amber-500/10 rounded-xl p-3 text-center">
                <div className="text-xl font-bold text-amber-500">{components.filter(c => c.status === 'warning').length}</div>
                <div className="text-[10px] text-slate-500 mt-1">警告</div>
              </div>
              <div className="bg-rose-500/10 rounded-xl p-3 text-center">
                <div className="text-xl font-bold text-rose-500">{components.filter(c => c.status === 'stopped').length}</div>
                <div className="text-[10px] text-slate-500 mt-1">离线</div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="mt-4 pt-4 border-t border-white/10">
            <div className="text-xs text-slate-500 mb-3 uppercase tracking-wider">快捷操作</div>
            <div className="space-y-2">
              <button 
                onClick={() => handleAction('start')}
                disabled={service.status === 'HEALTHY'}
                className="w-full py-2 bg-[#00ff9d]/10 text-[#00ff9d] rounded-lg text-xs flex items-center justify-center hover:bg-[#00ff9d]/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className="w-3 h-3 mr-1.5" /> 启动服务
              </button>
              <button 
                onClick={() => handleAction('stop')}
                disabled={service.status === 'STOPPED'}
                className="w-full py-2 bg-white/5 text-slate-300 rounded-lg text-xs flex items-center justify-center hover:bg-white/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Square className="w-3 h-3 mr-1.5" /> 停止服务
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 space-y-6">
        {/* Header */}
        <div className="glass-panel p-6 rounded-2xl">
          <div className="flex justify-between items-start">
            <div className="flex items-center">
              <div 
                className="w-3 h-3 rounded-full mr-3"
                style={{ 
                  backgroundColor: statusColor,
                  boxShadow: `0 0 12px ${statusColor}`,
                  animation: 'pulse 2s infinite'
                }}
              ></div>
              <div>
                <h1 className="text-2xl font-bold text-white flex items-center">
                  {service.name}
                  <span className="ml-3 text-sm font-normal bg-white/10 px-3 py-1 rounded-full text-slate-300">
                    v{service.version}
                  </span>
                </h1>
                <p className="text-slate-500 text-sm mt-1">{service.role || '大数据服务组件'}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              <div className="px-4 py-2 bg-[#020617] border border-white/10 rounded-xl flex items-center">
                <span className="text-slate-400 mr-2 text-sm">状态:</span>
                <StatusBadge status={service.status} />
              </div>
              <button 
                onClick={fetchServiceDetails}
                className="p-2.5 bg-white/5 hover:bg-white/10 rounded-xl text-slate-300 transition-colors"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Service Info Bar */}
          <div className="grid grid-cols-5 gap-6 mt-6 pt-5 border-t border-white/5">
            <div className="bg-white/5 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">服务类型</div>
              <div className="text-sm text-white font-semibold flex items-center">
                <Gauge className="w-4 h-4 mr-2 text-[#38bdf8]" />
                {service.role || '大数据服务'}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">配置版本</div>
              <div className="text-sm text-white font-semibold flex items-center">
                <Settings className="w-4 h-4 mr-2 text-[#a855f7]" />
                {service.configVersion || 'v1'}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">组件数量</div>
              <div className="text-sm text-white font-semibold flex items-center">
                <Package className="w-4 h-4 mr-2 text-[#00ff9d]" />
                {components.length}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">最后操作</div>
              <div className="text-sm text-white font-semibold">{service.lastOperation || '-'}</div>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">操作时间</div>
              <div className="text-sm text-white font-semibold">{formatTime(service.lastOperationTime)}</div>
            </div>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {metrics.slice(0, 6).map((metric, index) => {
                const Icon = metric.icon;
                const progress = Math.random() * 70 + 20;
                return (
                  <div key={index} className="glass-panel p-5 rounded-2xl hover:border-[#00ff9d]/30 transition-all duration-300 group">
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-slate-500 text-xs uppercase font-bold tracking-wider">{metric.name}</div>
                      <Icon className="w-5 h-5 text-slate-600 group-hover:text-[#00ff9d] transition-colors" />
                    </div>
                    <div className="flex items-end mb-3">
                      <div className="text-3xl font-bold text-white">
                        {metric.value}
                      </div>
                      <div className="text-xs text-slate-500 ml-2 mb-1">{metric.unit}</div>
                    </div>
                    <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full transition-all duration-500 ${metric.trend === 'up' ? 'bg-gradient-to-r from-[#00ff9d] to-[#38bdf8]' : 'bg-gradient-to-r from-amber-500 to-orange-400'}`}
                        style={{ width: `${progress}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between mt-2">
                      <span className="text-[10px] text-slate-600">{metric.trend === 'up' ? '↑ 上升' : '↓ 下降'}</span>
                      <span className="text-[10px] text-slate-600">{progress.toFixed(0)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Quick Config Summary */}
            <div className="glass-panel p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white flex items-center">
                  <FileText className="w-5 h-5 mr-2 text-[#a855f7]" /> 配置文件概览
                </h3>
                <button 
                  onClick={() => setActiveTab('configs')}
                  className="text-sm text-[#00ff9d] hover:underline"
                >
                  查看全部 →
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {config.configs.slice(0, 4).map((cfg, index) => (
                  <div key={index} className="bg-white/5 rounded-xl p-4 hover:bg-white/10 transition-colors cursor-pointer">
                    <FileText className="w-5 h-5 text-[#a855f7] mb-2" />
                    <div className="text-sm text-white font-medium truncate">{cfg}</div>
                    <div className="text-xs text-slate-500 mt-1">已同步</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'metrics' && (
          <div className="glass-panel p-6 rounded-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white flex items-center">
                <BarChart3 className="w-5 h-5 mr-2 text-[#00ff9d]" /> 监控指标详情
              </h3>
              <div className="flex space-x-2">
                <button className="px-4 py-1.5 bg-[#00ff9d]/20 text-[#00ff9d] rounded-lg text-sm font-medium">实时</button>
                <button className="px-4 py-1.5 bg-white/5 text-slate-400 rounded-lg text-sm font-medium hover:text-white hover:bg-white/10 transition-colors">历史</button>
                <button className="px-4 py-1.5 bg-white/5 text-slate-400 rounded-lg text-sm font-medium hover:text-white hover:bg-white/10 transition-colors">告警规则</button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-4">
              {metrics.map((metric, index) => {
                const Icon = metric.icon;
                return (
                  <div key={index} className="p-5 bg-white/5 rounded-2xl border border-white/5 hover:border-[#38bdf8]/30 transition-all">
                    <div className="flex items-center mb-3">
                      <div className="p-2 bg-[#38bdf8]/10 rounded-lg mr-3">
                        <Icon className="w-4 h-4 text-[#38bdf8]" />
                      </div>
                      <span className="text-sm text-slate-400">{metric.name}</span>
                    </div>
                    <div className="text-3xl font-bold text-white mb-1">{metric.value}</div>
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-slate-500">{metric.unit}</div>
                      <div className={`text-xs flex items-center ${metric.trend === 'up' ? 'text-[#00ff9d]' : 'text-amber-500'}`}>
                        {metric.trend === 'up' ? '↑' : '↓'} {Math.random() * 20 + 5}%
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {activeTab === 'configs' && (
          <div className="glass-panel p-6 rounded-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white flex items-center">
                <FileText className="w-5 h-5 mr-2 text-[#a855f7]" /> 配置文件
              </h3>
              <div className="flex space-x-2">
                <button className="px-4 py-2 bg-white/5 text-slate-400 rounded-lg text-sm hover:text-white hover:bg-white/10 transition-colors flex items-center">
                  <RefreshCw className="w-4 h-4 mr-2" /> 刷新
                </button>
                <button className="px-4 py-2 bg-[#a855f7]/10 text-[#a855f7] rounded-lg text-sm hover:bg-[#a855f7]/20 transition-colors flex items-center">
                  <Save className="w-4 h-4 mr-2" /> 保存
                </button>
              </div>
            </div>
            <div className="space-y-3">
              {config.configs.map((configFile, index) => (
                <div 
                  key={index}
                  className="flex items-center justify-between p-4 bg-white/5 rounded-xl hover:bg-white/10 cursor-pointer transition-all border border-transparent hover:border-[#a855f7]/30 group"
                >
                  <div className="flex items-center">
                    <div className="p-2 bg-[#a855f7]/10 rounded-lg mr-4">
                      <FileText className="w-5 h-5 text-[#a855f7]" />
                    </div>
                    <div>
                      <div className="text-white font-semibold">{configFile}</div>
                      <div className="text-xs text-slate-500 flex items-center mt-1">
                        <span>路径: /etc/cloudrealm/{service.name.toLowerCase()}</span>
                        <span className="mx-2">•</span>
                        <span>上次修改: 2024-01-15</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="px-3 py-1 bg-[#00ff9d]/10 text-[#00ff9d] text-xs rounded-full font-medium">已同步</span>
                    <button className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
                      <Download className="w-4 h-4" />
                    </button>
                    <button className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors">
                      <Settings className="w-4 h-4" />
                    </button>
                    <ChevronRight className="w-4 h-4 text-slate-600" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'components' && (
          <div className="glass-panel p-6 rounded-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white flex items-center">
                <Package className="w-5 h-5 mr-2 text-[#00ff9d]" /> 组件列表
              </h3>
              <div className="flex space-x-2">
                <button className="px-4 py-2 bg-white/5 text-slate-400 rounded-lg text-sm hover:text-white hover:bg-white/10 transition-colors flex items-center">
                  <RefreshCw className="w-4 h-4 mr-2" /> 刷新
                </button>
                <button className="px-4 py-2 bg-[#00ff9d]/10 text-[#00ff9d] rounded-lg text-sm hover:bg-[#00ff9d]/20 transition-colors flex items-center">
                  <Play className="w-4 h-4 mr-2" /> 批量启动
                </button>
              </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
                  <tr>
                    <th className="px-5 py-4 font-semibold">组件名称</th>
                    <th className="px-5 py-4 font-semibold">主机</th>
                    <th className="px-5 py-4 font-semibold">状态</th>
                    <th className="px-5 py-4 font-semibold">PID</th>
                    <th className="px-5 py-4 font-semibold">内存使用</th>
                    <th className="px-5 py-4 font-semibold">CPU</th>
                    <th className="px-5 py-4 font-semibold">运行时间</th>
                    <th className="px-5 py-4 font-semibold">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {components.map((comp, i) => (
                    <tr key={i} className="hover:bg-white/5 transition-colors">
                      <td className="px-5 py-4">
                        <div className="flex items-center">
                          <div className="p-2 bg-[#38bdf8]/10 rounded-lg mr-3">
                            <Server className="w-4 h-4 text-[#38bdf8]" />
                          </div>
                          <span className="text-white font-semibold">{comp.name}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center text-slate-400">
                          <Network className="w-4 h-4 mr-2" />
                          {comp.host}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                          comp.status === 'running' 
                            ? 'bg-[#00ff9d]/10 text-[#00ff9d]' 
                            : comp.status === 'warning'
                            ? 'bg-amber-500/10 text-amber-500'
                            : 'bg-slate-500/10 text-slate-500'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                            comp.status === 'running' ? 'bg-[#00ff9d]' : comp.status === 'warning' ? 'bg-amber-500' : 'bg-slate-500'
                          }`}></span>
                          {comp.status === 'running' ? '运行中' : comp.status === 'warning' ? '警告' : '已停止'}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-slate-400 font-mono">{comp.pid}</td>
                      <td className="px-5 py-4">
                        <div className="flex items-center">
                          <div className="w-16 h-1.5 bg-white/10 rounded-full mr-2 overflow-hidden">
                            <div className="h-full bg-[#38bdf8] rounded-full" style={{ width: `${parseInt(comp.memory) / 10 * 100}%` }}></div>
                          </div>
                          <span className="text-slate-400 text-xs">{comp.memory}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center">
                          <div className="w-16 h-1.5 bg-white/10 rounded-full mr-2 overflow-hidden">
                            <div className="h-full bg-[#a855f7] rounded-full" style={{ width: comp.cpu }}></div>
                          </div>
                          <span className="text-slate-400 text-xs">{comp.cpu}</span>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-slate-400">{formatUptime(comp.startTime)}</td>
                      <td className="px-5 py-4">
                        <div className="flex items-center space-x-1">
                          <button className="p-1.5 text-slate-400 hover:text-[#00ff9d] hover:bg-white/10 rounded-lg transition-colors" title="启动">
                            <Play className="w-4 h-4" />
                          </button>
                          <button className="p-1.5 text-slate-400 hover:text-amber-500 hover:bg-white/10 rounded-lg transition-colors" title="重启">
                            <RotateCcw className="w-4 h-4" />
                          </button>
                          <button className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-white/10 rounded-lg transition-colors" title="停止">
                            <Square className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
