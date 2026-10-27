import React, { useEffect, useState } from 'react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle 
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Search, 
  Sparkles, 
  FileText, 
  Globe, 
  Activity, 
  Eye, 
  Upload, 
  Calculator, 
  Trash2, 
  ArrowRight,
  Terminal
} from 'lucide-react';

export default function CommandMenu({ 
  open, 
  onOpenChange, 
  onSelectMode, 
  onNewSession, 
  onOpenTools,
  onOpenLanding,
  onOpenWorkspace,
  currentView
}) {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onOpenChange]);

  const commands = [
    {
      group: 'Navigation',
      items: [
        {
          label: currentView === 'landing' ? 'Launch Workspace' : 'Switch to Overview',
          desc: currentView === 'landing' ? 'Open the interactive agentic workspace' : 'Return to product landing page',
          icon: Terminal,
          action: () => {
            if (currentView === 'landing') onOpenWorkspace();
            else onOpenLanding();
            onOpenChange(false);
          },
        },
        {
          label: 'New Chat Session',
          desc: 'Reset conversation context and start fresh session',
          icon: Sparkles,
          action: () => {
            onNewSession();
            onOpenWorkspace();
            onOpenChange(false);
          },
        },
        {
          label: 'Open Document Intelligence & Tools',
          desc: 'Manage uploaded files, calculators, and execution telemetry',
          icon: FileText,
          action: () => {
            onOpenWorkspace();
            onOpenTools();
            onOpenChange(false);
          },
        },
      ],
    },
    {
      group: 'Routing Modes',
      items: [
        {
          label: 'Auto Router (CRAG)',
          desc: 'Dynamically routes between local documents, live web search, and general reasoning',
          badge: 'CRAG',
          icon: Sparkles,
          action: () => {
            onSelectMode('AUTO');
            onOpenWorkspace();
            onOpenChange(false);
          },
        },
        {
          label: 'Document RAG Only',
          desc: 'Strictly bounds answer generation to uploaded files and documents',
          badge: 'Local',
          icon: FileText,
          action: () => {
            onSelectMode('DOCUMENT_RAG');
            onOpenWorkspace();
            onOpenChange(false);
          },
        },
        {
          label: 'Live Web Research',
          desc: 'Real-time web research for current events, fresh documentation, and news',
          badge: 'Live',
          icon: Globe,
          action: () => {
            onSelectMode('WEB_SEARCH');
            onOpenWorkspace();
            onOpenChange(false);
          },
        },
        {
          label: 'Multimodal Vision',
          desc: 'Inspect real-world photographs, charts, diagrams, and OCR text',
          badge: 'Vision',
          icon: Eye,
          action: () => {
            onSelectMode('VISION');
            onOpenWorkspace();
            onOpenChange(false);
          },
        },
      ],
    },
  ];

  const filteredGroups = commands.map((grp) => ({
    ...grp,
    items: grp.items.filter((item) =>
      item.label.toLowerCase().includes(query.toLowerCase()) ||
      item.desc.toLowerCase().includes(query.toLowerCase())
    ),
  })).filter((grp) => grp.items.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl p-0 overflow-hidden bg-zinc-950 border-zinc-800 shadow-2xl">
        <DialogHeader className="sr-only">
          <DialogTitle>Command Palette</DialogTitle>
        </DialogHeader>
        
        {/* Search header */}
        <div className="flex items-center px-4 py-3 border-b border-zinc-800/80 bg-zinc-900/40">
          <Search className="w-4 h-4 text-zinc-400 mr-2 shrink-0" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search action..."
            className="border-none bg-transparent shadow-none px-0 text-sm focus-visible:ring-0 placeholder:text-zinc-500"
            autoFocus
          />
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-400 bg-zinc-900 border border-zinc-800 rounded">
            ESC
          </kbd>
        </div>

        {/* Command list */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-4">
          {filteredGroups.length === 0 ? (
            <div className="py-8 text-center text-xs text-zinc-500">
              No matching actions found.
            </div>
          ) : (
            filteredGroups.map((group, gIdx) => (
              <div key={gIdx} className="space-y-1">
                <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                  {group.group}
                </div>
                {group.items.map((item, iIdx) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={iIdx}
                      onClick={item.action}
                      className="flex items-center justify-between px-3 py-2.5 rounded-md hover:bg-zinc-900 cursor-pointer text-xs transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-300 group-hover:text-cyan-400 group-hover:border-cyan-500/30 transition-colors">
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="truncate">
                          <div className="font-medium text-zinc-200 group-hover:text-white flex items-center gap-2">
                            <span>{item.label}</span>
                            {item.badge && (
                              <Badge variant="cyan" className="text-[9px] py-0 px-1.5">
                                {item.badge}
                              </Badge>
                            )}
                          </div>
                          <div className="text-[11px] text-zinc-400 truncate">
                            {item.desc}
                          </div>
                        </div>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-zinc-400 group-hover:text-cyan-400 transition-colors shrink-0" />
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="px-4 py-2 border-t border-zinc-900 bg-zinc-950/80 flex items-center justify-between text-[11px] text-zinc-400">
          <span className="flex items-center gap-1.5">
            <kbd className="px-1 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[10px]">↑</kbd>
            <kbd className="px-1 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[10px]">↓</kbd>
            <span>Navigate</span>
          </span>
          <span className="font-mono text-[10px] text-zinc-400">
            NEXORA // MULTIMODAL AGENTIC ENGINE
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
