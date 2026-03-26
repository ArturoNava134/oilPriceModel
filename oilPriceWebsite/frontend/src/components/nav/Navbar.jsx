import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, ChevronDown, Activity, Bell, Settings, ShieldCheck } from 'lucide-react';

const Navbar = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('user');
      if (stored) setUser(JSON.parse(stored));
    } catch (e) {
      console.error('Failed to parse user:', e);
    }
  }, []);

  useEffect(() => {
    const handleClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const initials = user?.name
    ? user.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : '??';

  return (
    <nav className="sticky top-0 z-[100] w-full bg-[#0a0e1a] border-b border-blue-500/20 shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
      {/* Visual Accent: Top neon glow line */}
      <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-blue-500/40 to-transparent" />
      
      <div className="max-w-[1600px] mx-auto px-6 h-14 flex items-center justify-between">
        
        {/* Left — Brand & Live Status */}
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3 group cursor-pointer" onClick={() => navigate('/')}>
            <div className="relative">
              {/* Glow effect behind logo */}
              <div className="absolute -inset-1 bg-blue-500/20 rounded-lg blur-sm group-hover:bg-blue-500/40 transition-all" />
              <div className="relative w-9 h-9 bg-[#0f172a] border border-blue-500/40 rounded-lg flex items-center justify-center">
                <Activity size={20} className="text-blue-400 group-hover:text-blue-300 transition-colors" />
              </div>
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-black text-white tracking-widest uppercase leading-none">
                Oil Risk <span className="text-blue-500">Terminal</span>
              </span>
              <span className="text-[9px] font-mono text-slate-500 mt-1 uppercase tracking-[0.2em]">
                Citibank Challenge v1.0
              </span>
            </div>
          </div>

          {/* System Status Badge — Matches Dashboard Buttons */}
          <div className="hidden md:flex items-center gap-3 px-3 py-1.5 bg-emerald-500/5 border border-emerald-500/20 rounded-md">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-mono text-emerald-400 font-bold uppercase tracking-wider">
              Network Stable
            </span>
          </div>
        </div>

        {/* Right — User Actions */}
        <div className="flex items-center gap-6">
          {/* Utility Icons */}
          <div className="hidden lg:flex items-center gap-5 text-slate-500">
             <Bell size={18} className="hover:text-blue-400 cursor-pointer transition-colors" />
             <Settings size={18} className="hover:text-blue-400 cursor-pointer transition-colors" />
          </div>

          <div className="h-6 w-px bg-white/10" />

          {user ? (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-3 group"
              >
                <div className="text-right hidden sm:block">
                  <p className="text-xs text-slate-200 font-bold uppercase tracking-tighter leading-none">{user.name}</p>
                  <p className="text-[9px] text-blue-500/70 font-mono mt-1 uppercase tracking-widest">
                    Authorized
                  </p>
                </div>
                
                <div className="relative">
                  <div className={`absolute -inset-1 rounded-full blur-sm transition-opacity duration-300 ${dropdownOpen ? 'bg-blue-500/40 opacity-100' : 'bg-blue-500/10 opacity-0 group-hover:opacity-100'}`} />
                  <div className="relative w-9 h-9 rounded-full bg-[#0f172a] border border-blue-500/40 flex items-center justify-center text-[11px] font-mono font-bold text-blue-400">
                    {initials}
                  </div>
                </div>
                <ChevronDown size={14} className={`text-slate-600 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {/* Dropdown Menu — High Contrast Terminal Style */}
              {dropdownOpen && (
                <div className="absolute right-0 top-full mt-3 w-60 bg-[#0f172a] border border-blue-500/20 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.8)] overflow-hidden">
                  <div className="px-4 py-4 bg-blue-500/5 border-b border-white/5">
                    <p className="text-[9px] text-slate-500 uppercase font-black tracking-widest mb-1">Authenticated Session</p>
                    <p className="text-xs text-white font-medium truncate font-mono">{user.email}</p>
                  </div>

                  <div className="p-2">
                    <button className="w-full flex items-center gap-3 px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-white/5 rounded-lg transition-all group">
                      <ShieldCheck size={16} className="text-blue-500/50 group-hover:text-blue-400" />
                      Security Logs
                    </button>
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-3 px-3 py-2.5 mt-1 text-xs text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all group"
                    >
                      <LogOut size={16} className="group-hover:translate-x-1 transition-transform" />
                      <span className="font-bold uppercase">Terminate Session</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="px-5 py-2 text-[10px] font-black uppercase tracking-[0.2em] text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-lg shadow-blue-900/40 border border-blue-400/20"
            >
              System Login
            </button>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;