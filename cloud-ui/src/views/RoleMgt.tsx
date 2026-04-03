import React, { useState, useEffect } from 'react';
import { Users, Shield, Building2, FileText, Plus, Edit, Trash2, Check, X, Search, RefreshCcw } from 'lucide-react';

const API_BASE = '/api';

interface RoleMgtProps {
  activeSubView?: string;
}

interface Role {
  authorizationId: number;
  authorizationName: string;
  description: string;
  roleType: string;
  scope: string;
  isSystem: number;
  createTime: number;
  updateTime: number;
}

interface Tenant {
  tenantId: number;
  tenantName: string;
  tenantCode: string;
  description: string;
  status: string;
  maxUsers: number;
  maxHosts: number;
  createTime: number;
  updateTime: number;
  creator: string;
}

interface UserRole {
  id: number;
  userId: number;
  authorizationId: number;
  tenantId: number;
  isActive: number;
  createTime: number;
  creator: string;
}

interface OperationLog {
  logId: number;
  userId: number;
  userName: string;
  operationType: string;
  targetType: string;
  targetId: number;
  targetName: string;
  oldValue: string;
  newValue: string;
  ipAddress: string;
  result: string;
  errorMessage: string;
  createTime: number;
}

const mockRoles: Role[] = [
  { authorizationId: 1, authorizationName: 'Administrator', description: '系统管理员', roleType: 'SYSTEM', scope: 'GLOBAL', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
  { authorizationId: 2, authorizationName: 'Cluster Administrator', description: '集群管理员', roleType: 'ADMIN', scope: 'TENANT', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
  { authorizationId: 3, authorizationName: 'Cluster Operator', description: '集群运维人员', roleType: 'OPERATOR', scope: 'TENANT', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
  { authorizationId: 4, authorizationName: 'Service Administrator', description: '服务管理员', roleType: 'ADMIN', scope: 'TENANT', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
  { authorizationId: 5, authorizationName: 'Service Operator', description: '服务运维人员', roleType: 'OPERATOR', scope: 'TENANT', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
  { authorizationId: 6, authorizationName: 'Cluster User', description: '集群用户', roleType: 'USER', scope: 'TENANT', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
  { authorizationId: 7, authorizationName: 'View User', description: '只读用户', roleType: 'USER', scope: 'TENANT', isSystem: 1, createTime: Date.now(), updateTime: Date.now() },
];

const mockTenants: Tenant[] = [
  { tenantId: 1, tenantName: 'Default Tenant', tenantCode: 'DEFAULT', description: '默认租户', status: 'ACTIVE', maxUsers: 100, maxHosts: 50, createTime: Date.now(), updateTime: Date.now(), creator: 'admin' },
  { tenantId: 2, tenantName: 'Production', tenantCode: 'PROD', description: '生产环境', status: 'ACTIVE', maxUsers: 200, maxHosts: 100, createTime: Date.now(), updateTime: Date.now(), creator: 'admin' },
];

export default function RoleMgt({ activeSubView }: RoleMgtProps) {
  const [activeTab, setActiveTab] = useState('roles');
  const [roles, setRoles] = useState<Role[]>(mockRoles);
  const [tenants, setTenants] = useState<Tenant[]>(mockTenants);
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showTenantModal, setShowTenantModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [notification, setNotification] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  useEffect(() => {
    if (activeSubView) {
      switch (activeSubView) {
        case '角色列表':
        case '角色管理':
          setActiveTab('roles');
          break;
        case '租户配置':
          setActiveTab('tenants');
          break;
        case '角色分配':
          setActiveTab('assign');
          break;
        case '操作记录':
          setActiveTab('logs');
          break;
      }
    }
  }, [activeSubView]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [rolesRes, tenantsRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/roles`),
        fetch(`${API_BASE}/roles/tenants`),
        fetch(`${API_BASE}/roles/logs/recent?limit=50`)
      ]);

      if (rolesRes.ok) {
        const data = await rolesRes.json();
        if (data && data.length > 0) setRoles(data);
      }
      if (tenantsRes.ok) {
        const data = await tenantsRes.json();
        if (data && data.length > 0) setTenants(data);
      }
      if (logsRes.ok) {
        const data = await logsRes.json();
        if (data) setLogs(data);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const showNotification = (type: 'success' | 'error' | 'info', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000);
  };

  const handleSaveRole = async () => {
    if (!editingRole) return;
    setLoading(true);
    try {
      const url = editingRole.authorizationId ? `${API_BASE}/roles/${editingRole.authorizationId}` : `${API_BASE}/roles`;
      const method = editingRole.authorizationId ? 'PUT' : 'POST';
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingRole)
      });
      if (response.ok) {
        showNotification('success', '角色保存成功');
        setShowRoleModal(false);
        loadData();
      } else {
        showNotification('error', '角色保存失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRole = async (id: number) => {
    if (!confirm('确定要删除这个角色吗？')) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/roles/${id}`, { method: 'DELETE' });
      if (response.ok) {
        showNotification('success', '角色删除成功');
        loadData();
      } else {
        showNotification('error', '角色删除失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTenant = async () => {
    if (!editingTenant) return;
    setLoading(true);
    try {
      const url = editingTenant.tenantId ? `${API_BASE}/roles/tenants/${editingTenant.tenantId}` : `${API_BASE}/roles/tenants`;
      const method = editingTenant.tenantId ? 'PUT' : 'POST';
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingTenant)
      });
      if (response.ok) {
        showNotification('success', '租户保存成功');
        setShowTenantModal(false);
        loadData();
      } else {
        showNotification('error', '租户保存失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTenant = async (id: number) => {
    if (!confirm('确定要删除这个租户吗？')) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/roles/tenants/${id}`, { method: 'DELETE' });
      if (response.ok) {
        showNotification('success', '租户删除成功');
        loadData();
      } else {
        showNotification('error', '租户删除失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const filteredRoles = roles.filter(r => 
    r.authorizationName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredTenants = tenants.filter(t => 
    t.tenantName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.tenantCode?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN');
  };

  const getScopeBadge = (scope: string) => {
    switch (scope) {
      case 'GLOBAL': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'TENANT': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'PROJECT': return 'bg-green-500/20 text-green-400 border-green-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getStatusBadge = (status: string) => {
    return status === 'ACTIVE' 
      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' 
      : 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {notification && (
        <div className={`fixed top-4 right-4 px-4 py-2 rounded-lg text-sm z-50 ${
          notification.type === 'success' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
          notification.type === 'error' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
          'bg-blue-500/20 text-blue-400 border border-blue-500/30'
        }`}>
          {notification.message}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">角色与权限管理</h1>
        <button onClick={loadData} className="p-2 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
          <RefreshCcw className="w-5 h-5 text-slate-400" />
        </button>
      </div>

      <div className="flex space-x-1 bg-[#0f172a] p-1 rounded-xl w-fit">
        <button
          onClick={() => setActiveTab('roles')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'roles' ? 'bg-[#00ff9d] text-[#020617]' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Shield className="w-4 h-4 inline mr-2" /> 角色管理
        </button>
        <button
          onClick={() => setActiveTab('tenants')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'tenants' ? 'bg-[#00ff9d] text-[#020617]' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Building2 className="w-4 h-4 inline mr-2" /> 租户配置
        </button>
        <button
          onClick={() => setActiveTab('assign')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'assign' ? 'bg-[#00ff9d] text-[#020617]' : 'text-slate-400 hover:text-white'
          }`}
        >
          <Users className="w-4 h-4 inline mr-2" /> 角色分配
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'logs' ? 'bg-[#00ff9d] text-[#020617]' : 'text-slate-400 hover:text-white'
          }`}
        >
          <FileText className="w-4 h-4 inline mr-2" /> 操作记录
        </button>
      </div>

      {activeTab === 'roles' && (
        <div className="glass-panel rounded-2xl p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-white flex items-center">
              <Shield className="w-5 h-5 mr-2 text-[#00ff9d]" /> 角色列表
            </h3>
            <div className="flex items-center space-x-4">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="搜索角色..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white placeholder-slate-500"
                />
              </div>
              <button
                onClick={() => { setEditingRole({ authorizationId: 0, authorizationName: '', description: '', roleType: 'USER', scope: 'TENANT', isSystem: 0, createTime: 0, updateTime: 0 }); setShowRoleModal(true); }}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold flex items-center hover:bg-[#00e68e]"
              >
                <Plus className="w-4 h-4 mr-2" /> 添加角色
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="px-6 py-3">角色名称</th>
                  <th className="px-6 py-3">描述</th>
                  <th className="px-6 py-3">类型</th>
                  <th className="px-6 py-3">作用域</th>
                  <th className="px-6 py-3">系统角色</th>
                  <th className="px-6 py-3">创建时间</th>
                  <th className="px-6 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                {filteredRoles.map(role => (
                  <tr key={role.authorizationId} className="hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-bold text-white">{role.authorizationName}</div>
                    </td>
                    <td className="px-6 py-4 text-sm">{role.description || '-'}</td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold border bg-blue-500/10 text-blue-400 border-blue-500/20">
                        {role.roleType}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getScopeBadge(role.scope)}`}>
                        {role.scope}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {role.isSystem === 1 ? (
                        <span className="text-emerald-400 text-xs">是</span>
                      ) : (
                        <span className="text-slate-500 text-xs">否</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">{formatTime(role.createTime)}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => { setEditingRole(role); setShowRoleModal(true); }}
                          className="text-[#38bdf8] hover:text-white"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        {role.isSystem !== 1 && (
                          <button
                            onClick={() => handleDeleteRole(role.authorizationId)}
                            className="text-rose-400 hover:text-rose-300"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'tenants' && (
        <div className="glass-panel rounded-2xl p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-white flex items-center">
              <Building2 className="w-5 h-5 mr-2 text-[#38bdf8]" /> 租户列表
            </h3>
            <div className="flex items-center space-x-4">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="搜索租户..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white placeholder-slate-500"
                />
              </div>
              <button
                onClick={() => { setEditingTenant({ tenantId: 0, tenantName: '', tenantCode: '', description: '', status: 'ACTIVE', maxUsers: 100, maxHosts: 50, createTime: 0, updateTime: 0, creator: '' }); setShowTenantModal(true); }}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold flex items-center hover:bg-[#00e68e]"
              >
                <Plus className="w-4 h-4 mr-2" /> 添加租户
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="px-6 py-3">租户名称</th>
                  <th className="px-6 py-3">租户代码</th>
                  <th className="px-6 py-3">描述</th>
                  <th className="px-6 py-3">状态</th>
                  <th className="px-6 py-3">最大用户数</th>
                  <th className="px-6 py-3">最大主机数</th>
                  <th className="px-6 py-3">创建者</th>
                  <th className="px-6 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                {filteredTenants.map(tenant => (
                  <tr key={tenant.tenantId} className="hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-bold text-white">{tenant.tenantName}</div>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs">{tenant.tenantCode}</td>
                    <td className="px-6 py-4 text-sm">{tenant.description || '-'}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(tenant.status)}`}>
                        {tenant.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs">{tenant.maxUsers || '-'}</td>
                    <td className="px-6 py-4 text-xs">{tenant.maxHosts || '-'}</td>
                    <td className="px-6 py-4 text-xs text-slate-500">{tenant.creator || '-'}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => { setEditingTenant(tenant); setShowTenantModal(true); }}
                          className="text-[#38bdf8] hover:text-white"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteTenant(tenant.tenantId)}
                          className="text-rose-400 hover:text-rose-300"
                        >
                          <Trash2 className="w-4 h-4" />
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

      {activeTab === 'assign' && (
        <div className="glass-panel rounded-2xl p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-white flex items-center">
              <Users className="w-5 h-5 mr-2 text-[#38bdf8]" /> 用户角色分配
            </h3>
          </div>
          <div className="text-center py-12 text-slate-500">
            <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>选择用户和角色进行分配</p>
            <p className="text-xs mt-2">用户管理功能请参考用户中心模块</p>
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="glass-panel rounded-2xl p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-white flex items-center">
              <FileText className="w-5 h-5 mr-2 text-[#38bdf8]" /> 操作记录
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="px-6 py-3">操作者</th>
                  <th className="px-6 py-3">操作类型</th>
                  <th className="px-6 py-3">目标类型</th>
                  <th className="px-6 py-3">目标名称</th>
                  <th className="px-6 py-3">变更内容</th>
                  <th className="px-6 py-3">结果</th>
                  <th className="px-6 py-3">时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                      暂无操作记录
                    </td>
                  </tr>
                ) : (
                  logs.map(log => (
                    <tr key={log.logId} className="hover:bg-white/5 transition-colors">
                      <td className="px-6 py-4">
                        <div className="text-white">{log.userName || 'System'}</div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold border bg-blue-500/10 text-blue-400 border-blue-500/20">
                          {log.operationType}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs">{log.targetType}</td>
                      <td className="px-6 py-4 text-sm">{log.targetName || '-'}</td>
                      <td className="px-6 py-4 text-xs text-slate-400 max-w-xs truncate">
                        {log.oldValue && <span className="text-rose-400">{log.oldValue}</span>}
                        {log.oldValue && log.newValue && <span className="mx-1">→</span>}
                        {log.newValue && <span className="text-emerald-400">{log.newValue}</span>}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                          log.result === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/20 text-rose-400 border-rose-500/20'
                        }`}>
                          {log.result}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500">{formatTime(log.createTime)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showRoleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[500px]">
            <h3 className="text-lg font-bold text-white mb-4">
              {editingRole?.authorizationId ? '编辑角色' : '添加角色'}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">角色名称 *</label>
                <input
                  type="text"
                  value={editingRole?.authorizationName || ''}
                  onChange={(e) => setEditingRole(editingRole ? { ...editingRole, authorizationName: e.target.value } : null)}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: Custom Role"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">描述</label>
                <input
                  type="text"
                  value={editingRole?.description || ''}
                  onChange={(e) => setEditingRole(editingRole ? { ...editingRole, description: e.target.value } : null)}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">角色类型</label>
                  <select
                    value={editingRole?.roleType || 'USER'}
                    onChange={(e) => setEditingRole(editingRole ? { ...editingRole, roleType: e.target.value } : null)}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="SYSTEM">系统</option>
                    <option value="ADMIN">管理员</option>
                    <option value="OPERATOR">运维</option>
                    <option value="USER">用户</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">作用域</label>
                  <select
                    value={editingRole?.scope || 'TENANT'}
                    onChange={(e) => setEditingRole(editingRole ? { ...editingRole, scope: e.target.value } : null)}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="GLOBAL">全局</option>
                    <option value="TENANT">租户</option>
                    <option value="PROJECT">项目</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowRoleModal(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm hover:bg-white/10"
              >
                取消
              </button>
              <button
                onClick={handleSaveRole}
                disabled={loading || !editingRole?.authorizationName}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] disabled:opacity-50"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {showTenantModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[500px]">
            <h3 className="text-lg font-bold text-white mb-4">
              {editingTenant?.tenantId ? '编辑租户' : '添加租户'}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">租户名称 *</label>
                <input
                  type="text"
                  value={editingTenant?.tenantName || ''}
                  onChange={(e) => setEditingTenant(editingTenant ? { ...editingTenant, tenantName: e.target.value } : null)}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: 生产环境"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">租户代码 *</label>
                <input
                  type="text"
                  value={editingTenant?.tenantCode || ''}
                  onChange={(e) => setEditingTenant(editingTenant ? { ...editingTenant, tenantCode: e.target.value } : null)}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: PROD"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">描述</label>
                <input
                  type="text"
                  value={editingTenant?.description || ''}
                  onChange={(e) => setEditingTenant(editingTenant ? { ...editingTenant, description: e.target.value } : null)}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">最大用户数</label>
                  <input
                    type="number"
                    value={editingTenant?.maxUsers || 100}
                    onChange={(e) => setEditingTenant(editingTenant ? { ...editingTenant, maxUsers: parseInt(e.target.value) } : null)}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">最大主机数</label>
                  <input
                    type="number"
                    value={editingTenant?.maxHosts || 50}
                    onChange={(e) => setEditingTenant(editingTenant ? { ...editingTenant, maxHosts: parseInt(e.target.value) } : null)}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">状态</label>
                <select
                  value={editingTenant?.status || 'ACTIVE'}
                  onChange={(e) => setEditingTenant(editingTenant ? { ...editingTenant, status: e.target.value } : null)}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="ACTIVE">激活</option>
                  <option value="INACTIVE">停用</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowTenantModal(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm hover:bg-white/10"
              >
                取消
              </button>
              <button
                onClick={handleSaveTenant}
                disabled={loading || !editingTenant?.tenantName || !editingTenant?.tenantCode}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] disabled:opacity-50"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}