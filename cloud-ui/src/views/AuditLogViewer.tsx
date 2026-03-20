// AuditLogViewer.tsx
const AuditLogViewer = () => {
  const [logs, setLogs] =AuditLog[]>([]);

  const fetchLogs = async (params: LogQueryParams) => {
    const res = await axios.get('/api/v1/audit/logs', { params });
    setLogs(res.data);
  };

  return <LogTable data={logs} onSearch={fetchLogs} />;
};