import React from 'react';
import { 
  PlusCircle, 
  Sparkles, 
  FileText, 
  Globe, 
  Activity, 
  Eye, 
  Brain, 
  ShieldCheck, 
  AlertTriangle, 
  Trash2, 
  ExternalLink,
  MessageSquare
} from 'lucide-react';
import { EXECUTION_MODES } from './Header';

export default function Sidebar({ 
  isOpen, 
  onClose, 
  selectedMode, 
  onSelectMode, 
  onNewSession, 
  sessionId, 
  onClearChat,
  messageCount 
}) {
  if (!isOpen) return null;

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-950 flex flex-col h-full shrink-0 z-10 transition-all select-none">
      {/* New Consultation button */}
      <div className="p-3 border-b border-slate-800/80">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-medium text-sm shadow-md shadow-cyan-600/20 transition-all active:scale-[0.98]"
        >
          <PlusCircle size={16} />
          <span>New Consultation</span>
        </button>
      </div>

      {/* Mode navigation */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        <div>
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-2 mb-2">
            Routing Mode
          </div>
          <div className="space-y-1">
            {EXECUTION_MODES.map((mode) => {
              const Icon = mode.icon;
              const isActive = selectedMode === mode.id;
              return (
                <button
                  key={mode.id}
                  onClick={() => onSelectMode(mode.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all text-left ${
                    isActive
                      ? `${mode.color} border shadow-sm`
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                  }`}
                >
                  <Icon size={15} />
                  <span>{mode.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Clinical Guardrails card */}
        <div className="rounded-xl border border-cyan-900/40 bg-gradient-to-br from-cyan-950/40 to-slate-900/60 p-3 space-y-2.5">
          <div className="flex items-center gap-2 text-cyan-400 text-xs font-semibold">
            <ShieldCheck size={16} />
            <span>Clinical Verification Active</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Every clinical response is evaluated post-generation for factual grounding, citation accuracy, and hallucination risk before delivery.
          </p>
          <div className="space-y-1.5 pt-1 text-[11px]">
            <div className="flex items-center justify-between text-slate-400">
              <span>Grounding Threshold</span>
              <span className="font-mono text-emerald-400 font-medium">≥ 70%</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span>Dosage / Diagnosis Safeguards</span>
              <span className="text-cyan-400 font-medium">Strict</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span>CRAG Retrieval Retries</span>
              <span className="text-slate-300 font-medium">Enabled (Max 2)</span>
            </div>
          </div>
        </div>

        {/* Current session info */}
        {sessionId && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="font-medium">Active Session</span>
              <span className="font-mono text-[10px] text-slate-400 truncate max-w-[90px]">{sessionId}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Exchanges in turn</span>
              <span className="font-semibold text-slate-200">{messageCount}</span>
            </div>
            {messageCount > 0 && (
              <button
                onClick={onClearChat}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-950/30 rounded-lg transition-colors border border-rose-900/30 mt-1"
              >
                <Trash2 size={13} />
                <span>Clear Conversation</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
        <span>Nexora AI v2.2</span>
        <a 
          href="http://localhost:8501" 
          target="_blank" 
          rel="noreferrer"
          className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
          title="Open Streamlit interface in new tab"
        >
          <span>Streamlit UI</span>
          <ExternalLink size={11} />
        </a>
      </div>
    </aside>
  );
}
