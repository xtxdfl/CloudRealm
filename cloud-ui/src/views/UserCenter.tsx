import React, { useState, useEffect } from 'react';
import { 
  Users, Shield, Fingerprint, Plus, Edit, Trash2, Search, X, Check, Save
} from 'lucide-react';

const API_BASE = '/api';

interface User {
  userId: number;
  userName: string;
  displayName: string;
  active: number;
  createTime: number;
  localUsername: string;
}

interface Role {
  authorizationId: string;
  authorizationName: string;
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
  result: string;
  createTime: number;
}

const mockUsers: User[] = [
  { userId: 1, userName: 'admin', displayName: 'Administrator', active: 1, createTime: Date.now(), localUsername: 'admin' },
  { userId: 2, userName: 'dataeng', displayName: 'Data Engineer', active: 1, createTime: Date.now(), localUsername: 'dataeng' },
  { userId: 3, userName: 'analyst', displayName: 'Data Analyst', active: 1, createTime: Date.now(), localUsername: 'analyst' },
  { userId: 4, userName: 'viewer', displayName: 'Viewer', active: 0, createTime: Date.now(), localUsername: 'viewer' },
];

const mockRoles: Role[] = [
  { authorizationId: 'Administrator', authorizationName: 'Administrator' },
  { authorizationId: 'ClusterAdministrator', authorizationName: 'Cluster Administrator' },
  { authorizationId: 'ClusterOperator', authorizationName: 'Cluster Operator' },
  { authorizationId: 'ServiceAdministrator', authorizationName: 'Service Administrator' },
  { authorizationId: 'ServiceOperator', authorizationName: 'Service Operator' },
  { authorizationId: 'ClusterUser', authorizationName: 'Cluster User' },
  { authorizationId: 'ViewUser', authorizationName: 'View User' },
];

const mockTenants: Tenant[] = [
  { tenantId: 1, tenantName: 'Default Tenant', tenantCode: 'DEFAULT', description: '默认租户', status: 'ACTIVE', maxUsers: 100, maxHosts: 50, createTime: Date.now(), updateTime: Date.now() },
  { tenantId: 2, tenantName: 'Production', tenantCode: 'PROD', description: '生产环境', status: 'ACTIVE', maxUsers: 200, maxHosts: 100, createTime: Date.now(), updateTime: Date.now() },
];

export default function UserCenter({ activeSubView }: { activeSubView?: string }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [users, setUsers] = useState<User[]>(mockUsers);
  const [roles, setRoles] = useState<Role[]>(mockRoles);
  const [tenants, setTenants] = useState<Tenant[]>(mockTenants);
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);
  
  const [showUserModal, setShowUserModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showTenantModal, setShowTenantModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [newUser, setNewUser] = useState({ userName: '', displayName: '', localUsername: '', active: 1 });
  const [newRole, setNewRole] = useState({ authorizationId: '', authorizationName: '' });
  const [newTenant, setNewTenant] = useState({ tenantName: '', tenantCode: '', description: '', status: 'ACTIVE', maxUsers: 100, maxHosts: 50 });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [usersRes, rolesRes, tenantsRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/users`),
        fetch(`${API_BASE}/users/roles`),
        fetch(`${API_BASE}/users/tenants`),
        fetch(`${API_BASE}/users/logs/recent?limit=50`)
      ]);

      if (usersRes.ok) {
        const data = await usersRes.json();
        if (data && data.length > 0) setUsers(data);
      }
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

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN');
  };

  const handleCreateUser = async () => {
    if (!newUser.userName || !newUser.displayName) {
      showNotification('error', '请填写用户名和显示名称');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newUser, createTime: Date.now(), version: 0, principalId: Date.now() })
      });
      if (response.ok) {
        showNotification('success', '用户创建成功');
        setShowUserModal(false);
        setNewUser({ userName: '', displayName: '', localUsername: '', active: 1 });
        loadData();
      } else {
        showNotification('error', '用户创建失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!editingUser) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${editingUser.userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingUser)
      });
      if (response.ok) {
        showNotification('success', '用户更新成功');
        setEditingUser(null);
        loadData();
      } else {
        showNotification('error', '用户更新失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('确定要删除该用户吗？')) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/${userId}`, { method: 'DELETE' });
      if (response.ok) {
        showNotification('success', '用户删除成功');
        loadData();
      } else {
        showNotification('error', '用户删除失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRole = async () => {
    if (!newRole.authorizationName) {
      showNotification('error', '请填写角色名称');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/roles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newRole, authorizationId: newRole.authorizationId || newRole.authorizationName.toUpperCase().replace(/\s+/g, '_') })
      });
      if (response.ok) {
        showNotification('success', '角色创建成功');
        setShowRoleModal(false);
        setNewRole({ authorizationId: '', authorizationName: '' });
        loadData();
      } else {
        showNotification('error', '角色创建失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateRole = async () => {
    if (!editingRole) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/roles/${editingRole.authorizationId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingRole)
      });
      if (response.ok) {
        showNotification('success', '角色更新成功');
        setEditingRole(null);
        loadData();
      } else {
        showNotification('error', '角色更新失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRole = async (roleId: string) => {
    if (!confirm('确定要删除该角色吗？')) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/roles/${roleId}`, { method: 'DELETE' });
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

  const handleCreateTenant = async () => {
    if (!newTenant.tenantName || !newTenant.tenantCode) {
      showNotification('error', '请填写租户名称和代码');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/tenants`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newTenant, createTime: Date.now(), updateTime: Date.now() })
      });
      if (response.ok) {
        showNotification('success', '租户创建成功');
        setShowTenantModal(false);
        setNewTenant({ tenantName: '', tenantCode: '', description: '', status: 'ACTIVE', maxUsers: 100, maxHosts: 50 });
        loadData();
      } else {
        showNotification('error', '租户创建失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTenant = async () => {
    if (!editingTenant) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/tenants/${editingTenant.tenantId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...editingTenant, updateTime: Date.now() })
      });
      if (response.ok) {
        showNotification('success', '租户更新成功');
        setEditingTenant(null);
        loadData();
      } else {
        showNotification('error', '租户更新失败');
      }
    } catch (error) {
      showNotification('error', '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTenant = async (tenantId: number) => {
    if (!confirm('确定要删除该租户吗？')) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/users/tenants/${tenantId}`, { method: 'DELETE' });
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

  const filteredUsers = users.filter(u => 
    u.userName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.displayName?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredRoles = roles.filter(r => 
    r.authorizationName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.authorizationId?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredTenants = tenants.filter(t => 
    t.tenantName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.tenantCode?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const renderUserList = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Users className="w-5 h-5 mr-2 text-[#38bdf8]" /> 用户列表
          </h3>
          <button 
            onClick={() => setShowUserModal(true)}
            className="px-4 py-2 bg-[#38bdf8] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#0ea5e9] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加用户
          </button>
        </div>
        
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="搜索用户..." 
            className="w-full pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white focus:border-[#38bdf8] outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-4 py-3">用户名</th>
                <th className="px-4 py-3">显示名称</th>
                <th className="px-4 py-3">本地用户名</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">创建时间</th>
                <th className="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {filteredUsers.map(user => (
                <tr key={user.userId} className="hover:bg-white/5">
                  <td className="px-4 py-3 font-bold text-white">{user.userName}</td>
                  <td className="px-4 py-3">{user.displayName}</td>
                  <td className="px-4 py-3 text-slate-400">{user.localUsername}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-[10px] font-bold ${
                      user.active === 1 ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                    }`}>
                      {user.active === 1 ? '激活' : '停用'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{formatTime(user.createTime)}</td>
                  <td className="px-4 py-3">
                    <div className="flex space-x-2">
                      <button 
                        onClick={() => setEditingUser({...user})}
                        className="p-1.5 text-[#38bdf8] hover:bg-[#38bdf8]/10 rounded"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleDeleteUser(user.userId)}
                        className="p-1.5 text-rose-400 hover:bg-rose-500/10 rounded"
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
    </div>
  );

  const renderRoleManagement = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Shield className="w-5 h-5 mr-2 text-[#00ff9d]" /> 角色管理
          </h3>
          <button 
            onClick={() => setShowRoleModal(true)}
            className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#00e68e] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 创建角色
          </button>
        </div>
        
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="搜索角色..." 
            className="w-full pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white focus:border-[#00ff9d] outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRoles.map(role => (
            <div key={role.authorizationId} className="p-4 bg-white/5 border border-white/5 rounded-xl hover:border-white/10 transition-all">
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="font-bold text-white">{role.authorizationName}</h4>
                  <p className="text-xs text-slate-500 mt-1">ID: {role.authorizationId}</p>
                </div>
                <div className="flex space-x-1">
                  <button 
                    onClick={() => setEditingRole({...role})}
                    className="p-1.5 text-[#38bdf8] hover:bg-[#38bdf8]/10 rounded"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => handleDeleteRole(role.authorizationId)}
                    className="p-1.5 text-rose-400 hover:bg-rose-500/10 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderTenantConfig = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Shield className="w-5 h-5 mr-2 text-[#f59e0b]" /> 租户配置
          </h3>
          <button 
            onClick={() => setShowTenantModal(true)}
            className="px-4 py-2 bg-[#f59e0b] text-[#020617] rounded-lg text-xs font-bold hover:bg-[#d97706] flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" /> 添加租户
          </button>
        </div>
        
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="搜索租户..." 
            className="w-full pl-10 pr-4 py-2 bg-[#020617] border border-white/10 rounded-lg text-sm text-white focus:border-[#f59e0b] outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredTenants.map(tenant => (
            <div key={tenant.tenantId} className="p-6 bg-white/5 border border-white/5 rounded-xl hover:border-white/10 transition-all">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h4 className="text-lg font-bold text-white">{tenant.tenantName}</h4>
                  <p className="text-xs text-slate-500 mt-1">代码: {tenant.tenantCode}</p>
                </div>
                <span className={`px-2 py-1 text-[10px] font-bold rounded border ${
                  tenant.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                }`}>
                  {tenant.status}
                </span>
              </div>
              <p className="text-sm text-slate-400 mb-4">{tenant.description}</p>
              <div className="grid grid-cols-2 gap-2 text-xs mb-4">
                <div className="p-2 bg-[#020617] rounded">
                  <span className="text-slate-500">最大用户</span>
                  <p className="text-white font-mono">{tenant.maxUsers}</p>
                </div>
                <div className="p-2 bg-[#020617] rounded">
                  <span className="text-slate-500">最大主机</span>
                  <p className="text-white font-mono">{tenant.maxHosts}</p>
                </div>
              </div>
              <div className="flex space-x-2">
                <button 
                  onClick={() => setEditingTenant({...tenant})}
                  className="flex-1 py-2 bg-[#38bdf8]/10 text-[#38bdf8] rounded-lg text-xs font-bold hover:bg-[#38bdf8]/20"
                >
                  <Edit className="w-3 h-3 inline mr-1" /> 编辑
                </button>
                <button 
                  onClick={() => handleDeleteTenant(tenant.tenantId)}
                  className="flex-1 py-2 bg-rose-500/10 text-rose-400 rounded-lg text-xs font-bold hover:bg-rose-500/20"
                >
                  <Trash2 className="w-3 h-3 inline mr-1" /> 删除
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderOperationRecords = () => (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="glass-panel p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-white flex items-center">
            <Fingerprint className="w-5 h-5 mr-2 text-[#f59e0b]" /> 操作记录
          </h3>
          <div className="flex items-center bg-[#020617] border border-white/10 rounded-lg px-3 py-1.5 w-64">
            <Search className="w-4 h-4 text-slate-500 mr-2" />
            <input 
              type="text" 
              placeholder="搜索记录..." 
              className="bg-transparent border-none text-xs text-white focus:ring-0 w-full"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-4 py-3">时间</th>
                <th className="px-4 py-3">操作者</th>
                <th className="px-4 py-3">操作类型</th>
                <th className="px-4 py-3">目标类型</th>
                <th className="px-4 py-3">目标名称</th>
                <th className="px-4 py-3">变更内容</th>
                <th className="px-4 py-3">结果</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    暂无操作记录
                  </td>
                </tr>
              ) : (
                logs.filter(log => 
                  searchTerm === '' || 
                  log.userName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                  log.operationType?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                  log.targetName?.toLowerCase().includes(searchTerm.toLowerCase())
                ).map(log => (
                  <tr key={log.logId} className="hover:bg-white/5">
                    <td className="px-4 py-3 text-slate-500 text-xs">{formatTime(log.createTime)}</td>
                    <td className="px-4 py-3 font-bold text-white">{log.userName || 'System'}</td>
                    <td className="px-4 py-3 text-[#38bdf8]">{log.operationType}</td>
                    <td className="px-4 py-3 text-slate-400">{log.targetType}</td>
                    <td className="px-4 py-3">{log.targetName || '-'}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {log.oldValue && <span className="text-rose-400">{log.oldValue}</span>}
                      {log.oldValue && log.newValue && <span className="mx-1">→</span>}
                      {log.newValue && <span className="text-emerald-400">{log.newValue}</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-[10px] font-bold ${
                        log.result === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                      }`}>
                        {log.result}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {notification && (
        <div className={`fixed top-4 right-4 px-4 py-2 rounded-lg text-sm z-50 ${
          notification.type === 'success' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
          notification.type === 'error' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
          'bg-blue-500/20 text-blue-400 border border-blue-500/30'
        }`}>
          {notification.message}
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-40">
          <div className="animate-spin w-8 h-8 border-2 border-[#00ff9d] border-t-transparent rounded-full"></div>
        </div>
      )}

      {activeSubView === '用户列表' && renderUserList()}
      {activeSubView === '角色管理' && renderRoleManagement()}
      {activeSubView === '租户配置' && renderTenantConfig()}
      {activeSubView === '操作记录' && renderOperationRecords()}
      {(!activeSubView || activeSubView === '') && renderUserList()}

      {showUserModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[450px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">添加用户</h3>
              <button onClick={() => setShowUserModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">用户名 *</label>
                <input
                  type="text"
                  value={newUser.userName}
                  onChange={(e) => setNewUser({...newUser, userName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: john"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">显示名称 *</label>
                <input
                  type="text"
                  value={newUser.displayName}
                  onChange={(e) => setNewUser({...newUser, displayName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: John Doe"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">本地用户名</label>
                <input
                  type="text"
                  value={newUser.localUsername}
                  onChange={(e) => setNewUser({...newUser, localUsername: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowUserModal(false)}
                className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm hover:bg-white/10"
              >
                取消
              </button>
              <button
                onClick={handleCreateUser}
                disabled={loading}
                className="px-4 py-2 bg-[#38bdf8] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#0ea5e9] disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {editingUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[450px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">编辑用户</h3>
              <button onClick={() => setEditingUser(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">用户名</label>
                <input
                  type="text"
                  value={editingUser.userName || ''}
                  onChange={(e) => setEditingUser({...editingUser, userName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  disabled
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">显示名称</label>
                <input
                  type="text"
                  value={editingUser.displayName || ''}
                  onChange={(e) => setEditingUser({...editingUser, displayName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">状态</label>
                <select
                  value={editingUser.active}
                  onChange={(e) => setEditingUser({...editingUser, active: parseInt(e.target.value)})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value={1}>激活</option>
                  <option value={0}>停用</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setEditingUser(null)}
                className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm hover:bg-white/10"
              >
                取消
              </button>
              <button
                onClick={handleUpdateUser}
                disabled={loading}
                className="px-4 py-2 bg-[#38bdf8] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#0ea5e9] disabled:opacity-50"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {showRoleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[450px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">创建角色</h3>
              <button onClick={() => setShowRoleModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">角色名称 *</label>
                <input
                  type="text"
                  value={newRole.authorizationName}
                  onChange={(e) => setNewRole({...newRole, authorizationName: e.target.value, authorizationId: e.target.value.toUpperCase().replace(/\s+/g, '_')})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: Data Analyst"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">角色ID</label>
                <input
                  type="text"
                  value={newRole.authorizationId}
                  onChange={(e) => setNewRole({...newRole, authorizationId: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="自动生成"
                />
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
                onClick={handleCreateRole}
                disabled={loading}
                className="px-4 py-2 bg-[#00ff9d] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#00e68e] disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {editingRole && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[450px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">编辑角色</h3>
              <button onClick={() => setEditingRole(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">角色名称</label>
                <input
                  type="text"
                  value={editingRole.authorizationName || ''}
                  onChange={(e) => setEditingRole({...editingRole, authorizationName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">角色ID</label>
                <input
                  type="text"
                  value={editingRole.authorizationId || ''}
                  onChange={(e) => setEditingRole({...editingRole, authorizationId: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  disabled
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setEditingRole(null)}
                className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm hover:bg-white/10"
              >
                取消
              </button>
              <button
                onClick={handleUpdateRole}
                disabled={loading}
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
          <div className="glass-panel p-6 rounded-2xl w-[450px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">添加租户</h3>
              <button onClick={() => setShowTenantModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">租户名称 *</label>
                <input
                  type="text"
                  value={newTenant.tenantName}
                  onChange={(e) => setNewTenant({...newTenant, tenantName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: 生产环境"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">租户代码 *</label>
                <input
                  type="text"
                  value={newTenant.tenantCode}
                  onChange={(e) => setNewTenant({...newTenant, tenantCode: e.target.value.toUpperCase()})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="例如: PROD"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">描述</label>
                <input
                  type="text"
                  value={newTenant.description}
                  onChange={(e) => setNewTenant({...newTenant, description: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">最大用户数</label>
                  <input
                    type="number"
                    value={newTenant.maxUsers}
                    onChange={(e) => setNewTenant({...newTenant, maxUsers: parseInt(e.target.value)})}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">最大主机数</label>
                  <input
                    type="number"
                    value={newTenant.maxHosts}
                    onChange={(e) => setNewTenant({...newTenant, maxHosts: parseInt(e.target.value)})}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  />
                </div>
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
                onClick={handleCreateTenant}
                disabled={loading}
                className="px-4 py-2 bg-[#f59e0b] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#d97706] disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {editingTenant && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="glass-panel p-6 rounded-2xl w-[450px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">编辑租户</h3>
              <button onClick={() => setEditingTenant(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">租户名称</label>
                <input
                  type="text"
                  value={editingTenant.tenantName || ''}
                  onChange={(e) => setEditingTenant({...editingTenant, tenantName: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">租户代码</label>
                <input
                  type="text"
                  value={editingTenant.tenantCode || ''}
                  onChange={(e) => setEditingTenant({...editingTenant, tenantCode: e.target.value.toUpperCase()})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  disabled
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">描述</label>
                <input
                  type="text"
                  value={editingTenant.description || ''}
                  onChange={(e) => setEditingTenant({...editingTenant, description: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">状态</label>
                <select
                  value={editingTenant.status}
                  onChange={(e) => setEditingTenant({...editingTenant, status: e.target.value})}
                  className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="ACTIVE">激活</option>
                  <option value="INACTIVE">停用</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">最大用户数</label>
                  <input
                    type="number"
                    value={editingTenant.maxUsers || 0}
                    onChange={(e) => setEditingTenant({...editingTenant, maxUsers: parseInt(e.target.value)})}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">最大主机数</label>
                  <input
                    type="number"
                    value={editingTenant.maxHosts || 0}
                    onChange={(e) => setEditingTenant({...editingTenant, maxHosts: parseInt(e.target.value)})}
                    className="w-full bg-[#020617] border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setEditingTenant(null)}
                className="px-4 py-2 bg-white/5 border border-white/10 text-white rounded-lg text-sm hover:bg-white/10"
              >
                取消
              </button>
              <button
                onClick={handleUpdateTenant}
                disabled={loading}
                className="px-4 py-2 bg-[#f59e0b] text-[#020617] rounded-lg text-sm font-bold hover:bg-[#d97706] disabled:opacity-50"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}