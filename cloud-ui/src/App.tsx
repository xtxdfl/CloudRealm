import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Server, Activity, Users, Settings, LogOut, Database, Network } from 'lucide-react';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

// Placeholder components for other routes
const Services = () => <div className="p-8"><h1 className="text-2xl font-bold text-slate-800">Service Management</h1></div>;
const Hosts = () => <div className="p-8"><h1 className="text-2xl font-bold text-slate-800">Host Management</h1></div>;

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/services" element={<Dashboard><Services /></Dashboard>} /> 
        {/* Note: In a real app, Dashboard would be a Layout wrapper. For simplicity, I'll structure it differently inside Dashboard or use a Layout component. */}
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
