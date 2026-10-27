import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Plus,
  MessageSquare,
  Trash2,
  Pencil,
  Check,
  X,
  Loader2,
  LogOut,
  User,
  ChevronRight,
  Sparkles,
  Globe,
  FileText,
  Brain,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const WORKFLOW_PRESETS = [
  { title: 'Current Events Research', tag: 'Live Search', prompt: 'What are the latest technological and policy developments in clean energy this month?' },
  { title: 'Async Python Worker Pool', tag: 'Engineering', prompt: 'Implement an asynchronous background worker pool in Python with asyncio and concurrency limits.' },
  { title: 'Document Methodology QA', tag: 'Document RAG', prompt: 'Summarize the methodology, benchmark results, and limitations from my uploaded document.' },
  { title: 'Statistical Regularization', tag: 'Mathematics', prompt: 'Explain the mathematical difference between Ridge and Lasso regularization with penalty formulas.' },
];

function ConversationItem({ conv, isActive, onSelect, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conv.title);
  const [deleting, setDeleting] = useState(false);

  const handleRenameSubmit = () => {
    if (draft.trim() && draft.trim() !== conv.title) {
      onRename(conv.id, draft.trim());
    }
    setEditing(false);
  };

  const handleDelete = async () => {
    setDeleting(true);
    await onDelete(conv.id);
    setDeleting(false);
  };

  const timeLabel = (() => {
    const date = new Date(conv.last_message_at || conv.created_at);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffH = Math.floor(diffMins / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  })();

  return (
    <div
      className={`group relative rounded-lg px-2.5 py-2 cursor-pointer transition-all ${
        isActive ? 'bg-white/8 border border-white/10' : 'hover:bg-white/4'
      }`}
      onClick={() => !editing && onSelect(conv.id)}
    >
      {editing ? (
        <div className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
          <input
            autoFocus
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleRenameSubmit(); if (e.key === 'Escape') setEditing(false); }}
            className="flex-1 bg-white/8 border border-white/15 rounded px-2 py-0.5 text-xs text-zinc-100 outline-none min-w-0"
          />
          <button onClick={handleRenameSubmit} className="text-emerald-400 hover:text-emerald-300 p-0.5">
            <Check className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setEditing(false)} className="text-zinc-500 hover:text-zinc-300 p-0.5">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-1.5">
          <div className="flex-1 min-w-0">
            <p className="text-zinc-200 text-xs font-medium truncate leading-snug">{conv.title || 'Untitled'}</p>
            <p className="text-zinc-600 text-[10px] mt-0.5">{timeLabel}</p>
          </div>
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5">
            <button
              onClick={e => { e.stopPropagation(); setEditing(true); setDraft(conv.title); }}
              className="p-1 text-zinc-500 hover:text-zinc-300 rounded transition-colors"
              title="Rename"
            >
              <Pencil className="w-3 h-3" />
            </button>
            <button
              onClick={e => { e.stopPropagation(); handleDelete(); }}
              disabled={deleting}
              className="p-1 text-zinc-500 hover:text-red-400 rounded transition-colors"
              title="Delete"
            >
              {deleting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({
  isOpen,
  onClose,
  onNewSession,
  onSelectPreset,
  conversations = [],
  activeConversationId,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
  conversationsLoading = false,
}) {
  const { user, signOut } = useAuth();

  const handleSignOut = async () => {
    await signOut();
  };

  if (!isOpen) return null;

  return (
    <aside className="w-64 shrink-0 flex flex-col h-full bg-zinc-950/80 border-r border-white/6 overflow-hidden">
      {/* Header */}
      <div className="px-3 pt-4 pb-3 flex items-center justify-between">
        <span className="text-zinc-400 text-xs font-semibold uppercase tracking-widest">Workspace</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-zinc-500 hover:text-zinc-300 hover:bg-white/5"
          onClick={onClose}
          aria-label="Close sidebar"
        >
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* New Chat button */}
      <div className="px-3 pb-2">
        <Button
          onClick={onNewSession}
          className="w-full justify-start gap-2 h-8 bg-white/5 hover:bg-white/10 border border-white/8 text-zinc-300 hover:text-zinc-100 text-xs font-medium"
          variant="ghost"
        >
          <Plus className="w-3.5 h-3.5" />
          New Chat
        </Button>
      </div>

      <Separator className="bg-white/6 mx-3" />

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto px-2 py-2 scrollbar-thin">
        {user ? (
          <>
            <p className="px-1.5 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">Recent chats</p>
            {conversationsLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="w-4 h-4 animate-spin text-zinc-600" />
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-center py-6 px-2">
                <MessageSquare className="w-6 h-6 text-zinc-700 mx-auto mb-2" />
                <p className="text-zinc-600 text-xs">No conversations yet.</p>
                <p className="text-zinc-700 text-[10px] mt-0.5">Start a chat to begin.</p>
              </div>
            ) : (
              <div className="space-y-0.5">
                {conversations.map(conv => (
                  <ConversationItem
                    key={conv.id}
                    conv={conv}
                    isActive={conv.id === activeConversationId}
                    onSelect={onSelectConversation}
                    onRename={onRenameConversation}
                    onDelete={onDeleteConversation}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="px-2 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 mb-2">Quick starters</p>
            <div className="space-y-1">
              {WORKFLOW_PRESETS.map(p => (
                <button
                  key={p.title}
                  onClick={() => onSelectPreset(p.prompt)}
                  className="w-full text-left rounded-lg px-2.5 py-2 hover:bg-white/5 transition-colors group"
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-zinc-300 text-xs font-medium truncate">{p.title}</span>
                    <ChevronRight className="w-3 h-3 text-zinc-600 group-hover:text-zinc-400 shrink-0 transition-colors" />
                  </div>
                  <span className="text-[10px] text-zinc-600">{p.tag}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <Separator className="bg-white/6 mx-3" />

      {/* Auto-Orchestrator info */}
      <div className="px-3 py-2.5">
        <div className="rounded-lg bg-cyan-500/5 border border-cyan-500/15 px-2.5 py-2">
          <p className="text-[10px] font-semibold text-cyan-400/80 uppercase tracking-widest mb-1.5">Auto-Orchestrator</p>
          <div className="space-y-1">
            {[
              { icon: Globe, label: 'Live Web Research' },
              { icon: FileText, label: 'Document Intelligence' },
              { icon: Brain, label: 'General Reasoning' },
              { icon: Sparkles, label: 'Multimodal Vision' },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-1.5 text-zinc-500">
                <Icon className="w-2.5 h-2.5 text-cyan-500/60" />
                <span className="text-[10px]">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* User info / sign out */}
      {user && (
        <>
          <Separator className="bg-white/6 mx-3" />
          <div className="px-3 py-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-6 h-6 rounded-full bg-cyan-500/15 border border-cyan-500/25 flex items-center justify-center shrink-0">
                  <User className="w-3 h-3 text-cyan-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-zinc-300 text-xs font-medium truncate">
                    {user.user_metadata?.full_name || user.email?.split('@')[0] || 'User'}
                  </p>
                  <p className="text-zinc-600 text-[10px] truncate">{user.email}</p>
                </div>
              </div>
              <button
                onClick={handleSignOut}
                title="Sign out"
                className="p-1.5 text-zinc-600 hover:text-zinc-300 transition-colors rounded shrink-0"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
