import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { 
  Sparkles, 
  Activity, 
  FileText, 
  Globe, 
  Eye, 
  Brain, 
  PanelLeftClose, 
  PanelLeft, 
  Wrench,
  ChevronDown,
  Search,
  ArrowLeft,
  Terminal,
  Layers,
  Copy,
  Check
} from 'lucide-react';

export const EXECUTION_MODES = [
  { id: 'AUTO', label: 'Auto-Orchestrator', icon: Sparkles, desc: 'Automatically selects Web Research, Document RAG, Vision, or Reasoning', badge: 'Auto' },
  { id: 'DOCUMENT_RAG', label: 'Document Intelligence', icon: FileText, desc: 'Passage retrieval from indexed files and documents', badge: 'Docs' },
  { id: 'WEB_SEARCH', label: 'Live Web Research', icon: Globe, desc: 'Real-time web research across authoritative sources', badge: 'Web' },
  { id: 'HYBRID', label: 'Hybrid Docs + Web', icon: Activity, desc: 'Cross-reference documents with live web evidence', badge: 'Hybrid' },
  { id: 'VISION', label: 'Multimodal Vision', icon: Eye, desc: 'Photos, diagrams, charts, and OCR inspection', badge: 'Vision' },
  { id: 'GENERAL_LLM', label: 'Direct Reasoning', icon: Brain, desc: 'Direct assistant intelligence and programming', badge: 'LLM' },
];

export default function Header({ 
  isConnected, 
  selectedMode, 
  onSelectMode, 
  documentCount, 
  sidebarOpen, 
  setSidebarOpen, 
  toolsOpen, 
  setToolsOpen,
  onBackToLanding,
  onOpenCommandMenu,
  sessionId
}) {
  const currentMode = EXECUTION_MODES.find(m => m.id === selectedMode) || EXECUTION_MODES[0];
  const ModeIcon = currentMode.icon;
  const [copiedSession, setCopiedSession] = React.useState(false);

  const handleCopySession = () => {
    if (!sessionId) return;
    navigator.clipboard.writeText(sessionId);
    setCopiedSession(true);
    setTimeout(() => setCopiedSession(false), 2000);
  };

  return (
    <header className="h-14 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-md px-4 md:px-6 flex items-center justify-between z-20 shrink-0 select-none">
      {/* Left section: Sidebar toggle + Brand + Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900 rounded-md transition-colors"
          title="Toggle Navigation Rail"
        >
          {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
        </button>

        <Separator orientation="vertical" className="h-4 bg-zinc-800" />

        {/* Brand & Breadcrumbs */}
        <div className="flex items-center gap-2">
          <button 
            onClick={onBackToLanding}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            title="Return to Product Overview"
          >
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-semibold text-zinc-200">Nexora</span>
          </button>
          <span className="text-zinc-600 text-xs">/</span>
          <span className="text-xs font-mono text-zinc-300">Console</span>
          {sessionId && (
            <>
              <span className="text-zinc-600 text-xs hidden sm:inline">/</span>
              <button
                onClick={handleCopySession}
                className="hidden sm:flex items-center gap-1 text-[11px] font-mono text-zinc-400 hover:text-zinc-200 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800 transition-colors"
                title="Click to copy session ID"
              >
                <span>{sessionId.slice(0, 8)}...</span>
                {copiedSession ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Center / Right controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Mode Selector Dropdown (shadcn) */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button 
              variant="outline" 
              size="sm" 
              className="h-8 gap-2 border-zinc-800 bg-zinc-900/60 text-xs text-zinc-200 hover:border-zinc-700"
            >
              <ModeIcon className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline font-medium">{currentMode.label}</span>
              <span className="sm:hidden font-mono">{currentMode.badge}</span>
              <ChevronDown className="w-3 h-3 text-zinc-400" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72 bg-zinc-950 border-zinc-800 p-1">
            <DropdownMenuLabel className="text-[10px] text-zinc-400 font-mono">
              Intelligence Orchestration
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-zinc-800" />
            {EXECUTION_MODES.map((mode) => {
              const Icon = mode.icon;
              const isSelected = selectedMode === mode.id;
              return (
                <DropdownMenuItem
                  key={mode.id}
                  onClick={() => onSelectMode(mode.id)}
                  className={`flex items-start gap-2.5 p-2 rounded-md cursor-pointer transition-colors ${
                    isSelected ? 'bg-zinc-900 text-white' : 'text-zinc-300 hover:bg-zinc-900/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${isSelected ? 'text-cyan-400' : 'text-zinc-400'}`} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-xs text-zinc-200">{mode.label}</span>
                      {mode.id === 'AUTO' && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-mono">
                          Auto
                        </span>
                      )}
                      {isSelected && (
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 ml-auto" />
                      )}
                    </div>
                    <p className="text-[10px] text-zinc-400 leading-tight mt-0.5">
                      {mode.desc}
                    </p>
                  </div>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Command Menu Trigger */}
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenCommandMenu}
          className="hidden md:flex h-8 gap-2 border-zinc-800 bg-zinc-900/40 text-xs text-zinc-400 hover:text-zinc-200"
        >
          <Search className="w-3 h-3 text-zinc-400" />
          <span>Actions</span>
          <kbd className="px-1 py-0.5 text-[9px] font-mono bg-zinc-950 border border-zinc-800 rounded">
            ⌘K
          </kbd>
        </Button>

        {/* Document Ingestion Badge */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-800 bg-zinc-900/40 text-xs text-zinc-400">
          <FileText className="w-3 h-3 text-emerald-400" />
          <span className="font-mono text-[11px]">{documentCount} {documentCount === 1 ? 'doc' : 'docs'}</span>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md border border-zinc-800 bg-zinc-900/40 text-xs">
          <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'bg-red-400'}`} />
          <span className="font-mono text-[10px] text-zinc-400 hidden sm:inline">
            {isConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>

        {/* Advanced Tools drawer toggle */}
        <Button
          variant={toolsOpen ? "secondary" : "outline"}
          size="sm"
          onClick={() => setToolsOpen(!toolsOpen)}
          className={`h-8 gap-1.5 text-xs transition-colors ${
            toolsOpen 
              ? 'border-cyan-500/40 bg-cyan-950/30 text-cyan-300' 
              : 'border-zinc-800 text-zinc-300 hover:text-white'
          }`}
          title="Toggle Diagnostics & Documents Panel"
        >
          <Wrench className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Diagnostics & Docs</span>
        </Button>

        {/* Overview button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onBackToLanding}
          className="h-8 text-xs text-zinc-400 hover:text-zinc-200"
        >
          <span className="hidden sm:inline">Landing</span>
          <ArrowLeft className="w-3 h-3 sm:hidden" />
        </Button>
      </div>
    </header>
  );
}
