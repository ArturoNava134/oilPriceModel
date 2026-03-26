import React from 'react';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const navigate = useNavigate();

  const handleEnter = () => {
    navigate('/panel');
  };

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center overflow-hidden bg-black">
      
      {/* VIDEO BACKGROUND */}
      {/* Replace 'bg-video.mp4' with your generated file path */}
      <video 
        autoPlay 
        loop 
        muted 
        playsInline
        className="absolute z-0 w-auto min-w-full min-h-full max-w-none object-cover opacity-60"
      >
        <source src="/bg-video.mp4" type="video/mp4" />
        Your browser does not support the video tag.
      </video>

      {/* OVERLAY GRADIENT (Helps with text legibility) */}
      <div className="absolute inset-0 z-10 bg-gradient-to-b from-[#002D72]/40 via-transparent to-black/80"></div>

      {/* GLASS CARD */}
      <div className="relative z-20 w-full max-w-md mx-4">
        <div className="bg-white/10 backdrop-blur-2xl border border-white/20 p-10 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.5)] text-center">
          
          {/* Citi Logo Branding */}
          <div className="mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-blue-600 rounded-2xl mb-6 shadow-xl shadow-blue-500/30 ring-1 ring-white/30">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Citi Risk Terminal</h1>
            <p className="text-blue-200/70 text-sm mt-3 font-semibold tracking-widest uppercase">
              Oil Price Risk Factor Challenge
            </p>
          </div>

          <div className="space-y-6">
            <p className="text-slate-300 text-sm leading-relaxed">
              Welcome to the proprietary Risk Factor Analysis Engine. <br/> 
              Press below to initialize the dashboard.
            </p>

            <button
              onClick={handleEnter}
              className="group relative w-full py-4 bg-white text-[#002D72] font-bold rounded-xl overflow-hidden transition-all hover:scale-[1.02] active:scale-[0.98] shadow-2xl"
            >
              <span className="relative z-10">INITIALIZE DASHBOARD</span>
              <div className="absolute inset-0 bg-blue-50 transform scale-x-0 group-hover:scale-x-100 transition-transform origin-left duration-300"></div>
            </button>
          </div>

          <div className="mt-10 pt-6 border-t border-white/10">
            <p className="text-[10px] text-slate-400 font-medium tracking-widest uppercase">
              Secure Access Gate • Citi Institutional Clients Group
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;