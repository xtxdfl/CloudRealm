import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User, ArrowRight, Zap, Database, Activity, ShieldCheck, Cpu } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [activeField, setActiveField] = useState<string | null>(null);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    // Simulate login delay
    setTimeout(() => {
      setLoading(false);
      navigate('/dashboard');
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center relative overflow-hidden font-sans selection:bg-[#00ff9d] selection:text-[#020617]">
      
      {/* --- Animated Background Layers --- */}
      
      {/* 1. Base Grid */}
      <div className="absolute inset-0 cyber-grid opacity-40 pointer-events-none"></div>
      
      {/* 2. Radial Glows */}
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-blue-600/20 rounded-full blur-[120px] mix-blend-screen animate-pulse duration-[4000ms]"></div>
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-[#00ff9d]/10 rounded-full blur-[120px] mix-blend-screen animate-pulse duration-[6000ms]"></div>

      {/* 3. Floating Tech Elements (Decorations) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[20%] left-[10%] opacity-20 animate-spin-slow">
            <Cpu className="w-24 h-24 text-slate-500" />
        </div>
        <div className="absolute bottom-[20%] right-[10%] opacity-20 animate-spin-slow" style={{ animationDirection: 'reverse' }}>
            <Activity className="w-32 h-32 text-slate-500" />
        </div>
      </div>

      {/* --- Main Login Card --- */}
      <motion.div 
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="relative z-10 w-full max-w-[440px] px-4"
      >
        {/* Card Container */}
        <div className="relative group">
            {/* Glowing Border Gradient */}
            <div className="absolute -inset-0.5 bg-gradient-to-r from-[#00ff9d] via-[#38bdf8] to-[#00ff9d] rounded-2xl opacity-30 group-hover:opacity-60 blur transition duration-1000 group-hover:duration-200 animate-gradient-xy"></div>
            
            <div className="relative bg-[#0f172a]/90 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl overflow-hidden">
                {/* Scanline Effect inside card */}
                <div className="absolute inset-0 scanline-overlay opacity-10 pointer-events-none"></div>

                {/* Header */}
                <div className="flex flex-col items-center mb-10">
                    <div className="relative mb-6">
                        <div className="absolute inset-0 bg-[#00ff9d] blur-xl opacity-20"></div>
                        <div className="w-20 h-20 bg-[#020617] border border-[#00ff9d]/30 rounded-2xl flex items-center justify-center relative overflow-hidden group-hover:border-[#00ff9d]/60 transition-colors">
                            <div className="absolute inset-0 bg-gradient-to-br from-[#00ff9d]/10 to-transparent"></div>
                            <Database className="w-10 h-10 text-[#00ff9d] relative z-10" />
                            {/* Corner Accents */}
                            <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-[#00ff9d]"></div>
                            <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-[#00ff9d]"></div>
                        </div>
                    </div>
                    <h1 className="text-3xl font-bold text-white tracking-tight flex items-center">
                        CLOUD<span className="text-[#00ff9d]">REALM</span>
                    </h1>
                    <div className="flex items-center mt-2 space-x-2">
                        <span className="h-[1px] w-8 bg-slate-700"></span>
                        <p className="text-xs text-[#38bdf8] uppercase tracking-[0.2em]">Data Operations Core</p>
                        <span className="h-[1px] w-8 bg-slate-700"></span>
                    </div>
                </div>

                {/* Form */}
                <form onSubmit={handleLogin} className="space-y-6 relative z-10">
                    
                    {/* Username Field */}
                    <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider ml-1">Identity</label>
                        <div className="relative group/input">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                <User className={`h-5 w-5 transition-colors ${activeField === 'username' ? 'text-[#00ff9d]' : 'text-slate-500'}`} />
                            </div>
                            <input
                                type="text"
                                onFocus={() => setActiveField('username')}
                                onBlur={() => setActiveField(null)}
                                className="block w-full pl-11 pr-4 py-3.5 bg-[#020617]/50 border border-slate-700 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-[#00ff9d] focus:ring-1 focus:ring-[#00ff9d]/50 transition-all font-mono text-sm"
                                placeholder="ACCESS ID"
                                defaultValue="admin"
                            />
                            {/* Tech decorations on focus */}
                            {activeField === 'username' && (
                                <motion.div layoutId="input-highlight" className="absolute right-3 top-3.5 w-2 h-2 bg-[#00ff9d] rounded-full shadow-[0_0_10px_#00ff9d]" />
                            )}
                        </div>
                    </div>

                    {/* Password Field */}
                    <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider ml-1">Secure Key</label>
                        <div className="relative group/input">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                <Lock className={`h-5 w-5 transition-colors ${activeField === 'password' ? 'text-[#38bdf8]' : 'text-slate-500'}`} />
                            </div>
                            <input
                                type="password"
                                onFocus={() => setActiveField('password')}
                                onBlur={() => setActiveField(null)}
                                className="block w-full pl-11 pr-4 py-3.5 bg-[#020617]/50 border border-slate-700 rounded-lg text-white placeholder-slate-600 focus:outline-none focus:border-[#38bdf8] focus:ring-1 focus:ring-[#38bdf8]/50 transition-all font-mono text-sm"
                                placeholder="••••••••••••"
                                defaultValue="admin"
                            />
                            {activeField === 'password' && (
                                <motion.div layoutId="input-highlight" className="absolute right-3 top-3.5 w-2 h-2 bg-[#38bdf8] rounded-full shadow-[0_0_10px_#38bdf8]" />
                            )}
                        </div>
                    </div>

                    {/* Footer Options */}
                    <div className="flex items-center justify-between text-xs">
                        <label className="flex items-center space-x-2 cursor-pointer group/check">
                            <div className="w-4 h-4 border border-slate-600 rounded bg-[#020617] flex items-center justify-center transition-colors group-hover/check:border-[#00ff9d]">
                                <div className="w-2 h-2 bg-[#00ff9d] rounded-sm opacity-0 group-hover/check:opacity-100 transition-opacity"></div>
                            </div>
                            <span className="text-slate-400 group-hover/check:text-slate-300 transition-colors">Persist Session</span>
                        </label>
                        <a href="#" className="text-slate-400 hover:text-[#38bdf8] transition-colors">Reset Credentials</a>
                    </div>

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full group relative py-3.5 px-4 bg-transparent overflow-hidden rounded-lg transition-all"
                    >
                        {/* Button Background with Glitch Effect on Hover */}
                        <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-[#00ff9d] to-[#38bdf8] opacity-90 group-hover:opacity-100 transition-opacity"></div>
                        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
                        
                        {/* Content */}
                        <div className="relative flex items-center justify-center font-bold tracking-wider text-[#020617]">
                            {loading ? (
                                <div className="flex items-center">
                                    <Zap className="animate-spin h-5 w-5 mr-2" />
                                    <span>AUTHENTICATING...</span>
                                </div>
                            ) : (
                                <>
                                    <span>INITIALIZE</span>
                                    <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </div>
                    </button>

                </form>

                {/* System Status Footer */}
                <div className="mt-8 pt-6 border-t border-white/5 flex justify-between items-center text-[10px] text-slate-500 font-mono">
                    <div className="flex items-center">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-2 animate-pulse"></div>
                        SYSTEM OPERATIONAL
                    </div>
                    <div>v2.4.0-RC1</div>
                </div>

            </div>
        </div>

        {/* Bottom text */}
        <p className="text-center text-slate-600 text-xs mt-6 font-mono">
            UNAUTHORIZED ACCESS IS STRICTLY PROHIBITED
        </p>

      </motion.div>
    </div>
  );
}
