import { useState, useEffect } from 'react';

interface Policy {
  id: number;
  name: string;
  description: string;
  resource: string;
  action: string;
  effect: string;
  priority: number;
  status: string;
}

interface PolicyCreateRequest {
  name: string;
  description: string;
  resource: string;
  action: string;
  effect: string;
}

export default function PolicyManagement() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchPolicies = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/security/policies');
      const data = await res.json();
      setPolicies(data || []);
    } catch (error) {
      console.error('Failed to fetch policies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePolicy = async (policy: PolicyCreateRequest) => {
    try {
      await fetch('/api/v1/security/policies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(policy)
      });
      fetchPolicies();
    } catch (error) {
      console.error('Failed to create policy:', error);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  return (
    <div className="space-y-6">
      <div className="glass-panel p-6 rounded-2xl">
        <h2 className="text-xl font-bold text-white mb-4">策略管理</h2>
        {loading ? (
          <div className="text-center py-8 text-slate-400">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  <th className="px-4 py-2">名称</th>
                  <th className="px-4 py-2">描述</th>
                  <th className="px-4 py-2">资源</th>
                  <th className="px-4 py-2">操作</th>
                  <th className="px-4 py-2">效果</th>
                  <th className="px-4 py-2">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {policies.map(policy => (
                  <tr key={policy.id} className="hover:bg-white/5">
                    <td className="px-4 py-2 text-white font-bold">{policy.name}</td>
                    <td className="px-4 py-2 text-slate-300">{policy.description}</td>
                    <td className="px-4 py-2 text-slate-300">{policy.resource}</td>
                    <td className="px-4 py-2 text-[#38bdf8]">{policy.action}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-1 rounded text-xs ${
                        policy.effect === 'ALLOW' 
                          ? 'bg-emerald-500/20 text-emerald-400' 
                          : 'bg-rose-500/20 text-rose-400'
                      }`}>
                        {policy.effect}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-1 rounded text-xs ${
                        policy.status === 'ENABLED' 
                          ? 'bg-emerald-500/20 text-emerald-400' 
                          : 'bg-slate-500/20 text-slate-400'
                      }`}>
                        {policy.status}
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
