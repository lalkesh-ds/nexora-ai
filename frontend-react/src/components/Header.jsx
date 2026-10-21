import React from 'react';
import { 
  Sparkles, 
  Activity, 
  FileText, 
  Globe, 
  Eye, 
  Brain, 
  Sliders, 
  PanelLeftClose, 
  PanelLeft, 
  Wrench,
  ShieldCheck
} from 'lucide-react';

export const EXECUTION_MODES = [
  { id: 'AUTO', label: 'Auto Router', icon: Sparkles, color: 'text-amber-400 border-amber-500/30 bg-amber-500/10' },
  { id: 'DOCUMENT_RAG', label: 'Document RAG', icon: FileText, color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' },
  { id: 'WEB_SEARCH', label: 'Live Web', icon: Globe, color: 'text-sky-400 border-sky-500/30 bg-sky-500/10' },
  { id: 'HYBRID', label: 'Hybrid (Docs+Web)', icon: Activity, color: 'text-orange-400 border-orange-500/30 bg-orange-500/10' },
  { id: 'VISION', label: 'Vision AI', icon: Eye, color: 'text-purple-400 border-purple-500/30 bg-purple-500/10' },
  { id: 'GENERAL_LLM', label: 'General Clinical', icon: Brain, color: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/10' },
];

export default function Header({ 
  isConnected, 
  selectedMode, 
  onSelectMode, 
  documentCount, 
  sidebarOpen, 
  setSidebarOpen, 
  toolsOpen, 
  setToolsOpen 
}) {
  const currentMode = EXECUTION_MODES.find(m => m.id === selectedMode) || EXECUTION_MODES[0];
  const ModeIcon = currentMode.icon;

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md px-4 flex items-center justify-between z-20 shrink-0">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 rounded-lg transition-colors"
          title="Toggle Sidebar"
        >
          {sidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeft size={20} />}
        </button>

        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Activity className="text-white w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-100 text-lg tracking-tight">Nexora AI</span>
              <span className="px-1.5 py-0.5 text-[10px] uppercase font-semibold tracking-wider rounded bg-cyan-950 text-cyan-400 border border-cyan-800/50">
                Clinical Agent
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">Multimodal Intelligence • Verified CRAG</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Mode selector dropdown */}
        <div className="relative">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium bg-slate-800/80 border-slate-700/80 text-slate-200">
            <ModeIcon size={14} className={currentMode.color.split(' ')[0]} />
            <select
              value={selectedMode}
              onChange={(e) => onSelectMode(e.target.value)}
              className="bg-transparent border-none text-slate-200 focus:outline-none cursor-pointer pr-1 text-xs"
            >
              {EXECUTION_MODES.map((mode) => (
                <option key={mode.id} value={mode.id} className="bg-slate-900 text-slate-200">
                  {mode.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Documents count pill */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-800 bg-slate-800/40 text-xs text-slate-400">
          <FileText size={13} className="text-emerald-400" />
          <span>{documentCount} {documentCount === 1 ? 'doc' : 'docs'}</span>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-800 bg-slate-800/40 text-xs">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-rose-500'}`} />
          <span className="text-slate-300 font-medium hidden sm:inline">{isConnected ? 'Online' : 'Offline'}</span>
        </div>

        {/* Tools drawer toggle */}
        <button
          onClick={() => setToolsOpen(!toolsOpen)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            toolsOpen 
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' 
              : 'bg-slate-800/80 text-slate-300 border border-slate-700/80 hover:bg-slate-700'
          }`}
          title="Toggle Advanced Clinical Tools"
        >
          <Wrench size={14} />
          <span className="hidden sm:inline">Advanced Tools</span>
        </button>
      </div>
    </header>
  );
}
