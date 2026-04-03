import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

interface AuditLog {
  id: number;
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  status: string;
  details?: string;
}

interface LogQueryParams {
  page?: number;
  pageSize?: number;
  startTime?: number;
  endTime?: number;
  user?: string;
  action?: string;
}

export default function AuditLogViewer() {
  const [searchParams] = useSearchParams();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchLogs = async (params: LogQueryParams = {}) => {
    setLoading(true);
    try {
      const queryString = new URLSearchParams(params as any).toString();
      const res = await fetch(`/api/v1/audit/logs?${queryString}`);
      const data = await res.json();
      setLogs(data || []);
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [searchParams]);

  return (
    <div className="space-y-6">
      <div className="glass-panel p-6 rounded-2xl">
        <h2 className="text-xl font-bold text-white mb-4">审计日志</h2>
        {loading ? (
          <div className="text-center py-8 text-slate-400">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  <th className="px-4 py-2">时间</th>
                  <th className="px-4 py-2">用户</th>
                  <th className="px-4 py-2">操作</th>
                  <th className="px-4 py-2">资源</th>
                  <th className="px-4 py-2">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {logs.map(log => (
                  <tr key={log.id} className="hover:bg-white/5">
                    <td className="px-4 py-2 text-slate-300">{log.timestamp}</td>
                    <td className="px-4 py-2 text-white">{log.user}</td>
                    <td className="px-4 py-2 text-[#38bdf8]">{log.action}</td>
                    <td className="px-4 py-2 text-slate-300">{log.resource}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-1 rounded text-xs ${
                        log.status === 'SUCCESS' 
                          ? 'bg-emerald-500/20 text-emerald-400' 
                          : 'bg-rose-500/20 text-rose-400'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
