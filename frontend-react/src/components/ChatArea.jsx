import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  Send, 
  Paperclip, 
  Sparkles, 
  FileText, 
  Globe, 
  Activity, 
  Eye, 
  Brain, 
  Copy, 
  Check, 
  AlertCircle, 
  X, 
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Bot,
  User,
  Loader2,
  CornerDownLeft,
  FileCheck,
  BookOpen
} from 'lucide-react';
import VerificationBadge from './VerificationBadge';

const STARTER_PROMPTS = [
  {
    title: 'Real-Time Web Research',
    desc: 'Search fresh authoritative sources, policy updates, and breaking developments.',
    prompt: 'What are the most recent developments and policy updates in clean energy this month?',
    icon: Globe,
    badge: 'Live Research',
  },
  {
    title: 'Async Python Worker Pool',
    desc: 'Implement concurrency control with asyncio.Queue and task cancellation.',
    prompt: 'Implement an asynchronous background worker pool in Python with asyncio and concurrency limits.',
    icon: Activity,
    badge: 'Engineering',
  },
  {
    title: 'Document Methodology QA',
    desc: 'Extract key experimental findings, methods, and metrics from uploaded PDFs.',
    prompt: 'Summarize the methodology, benchmark results, and limitations from my uploaded document.',
    icon: FileText,
    badge: 'Document RAG',
  },
  {
    title: 'Multimodal Image Inspection',
    desc: 'Extract and analyze numerical trends, visual features, and diagram structures.',
    prompt: 'Analyze this image or diagram and identify all notable values and visual features.',
    icon: Eye,
    badge: 'Vision',
  },
];

const ROUTE_CONFIG = {
  DOCUMENT_RAG: { label: 'DOCUMENT INTELLIGENCE', variant: 'cyan', icon: FileText },
  WEB_SEARCH: { label: 'LIVE WEB RESEARCH', variant: 'cyan', icon: Globe },
  HYBRID: { label: 'HYBRID DOCS + WEB', variant: 'cyan', icon: Activity },
  VISION: { label: 'MULTIMODAL VISION', variant: 'cyan', icon: Eye },
  GENERAL_LLM: { label: 'DIRECT INTELLIGENCE', variant: 'secondary', icon: Brain },
};

export default function ChatArea({ 
  messages, 
  onSendMessage, 
  isLoading, 
  inputText, 
  setInputText,
  attachments,
  setAttachments
}) {
  const [copiedIndex, setCopiedIndex] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if ((!inputText.trim() && attachments.length === 0) || isLoading) return;
    onSendMessage(inputText.trim(), attachments);
    setInputText('');
    setAttachments([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      setAttachments(prev => [...prev, ...files]);
    }
  };

  const removeAttachment = (index) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const copyToClipboard = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#070709] relative">
      {/* Background hairline pattern */}
      <div className="absolute inset-0 bg-grid-subtle pointer-events-none opacity-30" />

      {/* Messages Scrollable Container */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-8 space-y-6 relative z-10">
        {messages.length === 0 ? (
          /* High-craft Empty State */
          <div className="max-w-2xl mx-auto py-12 space-y-8 select-none">
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-zinc-800 bg-zinc-900/80 text-xs font-mono text-zinc-300">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span>Evidence-Grounded Multimodal Intelligence</span>
              </div>
              <h1 className="text-3xl md:text-4xl font-medium tracking-tight text-white leading-tight">
                Ask a question, search the live web, or explore documents.
              </h1>
              <p className="text-sm text-zinc-400 leading-relaxed font-normal">
                Nexora seamlessly coordinates live web research, document intelligence, multimodal image understanding, and general reasoning with verified citation lineage.
              </p>
            </div>

            {/* Asymmetric Starters Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {STARTER_PROMPTS.map((s, i) => {
                const Icon = s.icon;
                return (
                  <div
                    key={i}
                    onClick={() => {
                      setInputText(s.prompt);
                      textareaRef.current?.focus();
                    }}
                    className="p-4 rounded-xl border border-zinc-800/80 bg-zinc-950/60 hover:bg-zinc-900/60 hover:border-zinc-700 cursor-pointer transition-all space-y-2 group shadow-sm"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-cyan-400" />
                        <span className="font-medium text-xs text-zinc-200 group-hover:text-white transition-colors">
                          {s.title}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-zinc-400">
                        {s.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed line-clamp-2">
                      {s.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Message Thread */
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg, index) => {
              const isUser = msg.role === 'user';
              const routeInfo = ROUTE_CONFIG[msg.route_used] || ROUTE_CONFIG.GENERAL_LLM;
              const RouteIcon = routeInfo.icon;

              return (
                <div 
                  key={index} 
                  className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  {/* Assistant Avatar */}
                  {!isUser && (
                    <div className="w-7 h-7 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0 mt-1 text-cyan-400">
                      <Activity className="w-3.5 h-3.5" />
                    </div>
                  )}

                  {/* Message Container */}
                  <div className={`max-w-[88%] md:max-w-[82%] space-y-2 ${isUser ? 'items-end' : 'items-start'}`}>
                    {/* User Bubble */}
                    {isUser ? (
                      <div className="rounded-xl rounded-tr-sm bg-zinc-900 border border-zinc-800 text-zinc-100 p-4 shadow-sm space-y-2">
                        {msg.attachments && msg.attachments.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pb-1">
                            {msg.attachments.map((att, attIdx) => (
                              <div 
                                key={attIdx} 
                                className="px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-[10px] font-mono text-zinc-300 flex items-center gap-1"
                              >
                                <FileText className="w-3 h-3 text-cyan-400" />
                                <span className="truncate max-w-[140px]">{att.name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        <p className="text-sm whitespace-pre-wrap leading-relaxed font-normal">
                          {msg.content}
                        </p>
                      </div>
                    ) : (
                      /* Assistant Bubble */
                      <div className="rounded-xl rounded-tl-sm bg-zinc-950 border border-zinc-800/90 p-5 shadow-[0_1px_1px_rgba(0,0,0,0.5),0_8px_16px_rgba(0,0,0,0.2)] space-y-4">
                        {/* Route & Actions Titlebar */}
                        <div className="flex items-center justify-between border-b border-zinc-850 pb-2.5">
                          <div className="flex items-center gap-2">
                            <Badge variant={routeInfo.variant} className="text-[10px] py-0 px-2 font-mono flex items-center gap-1">
                              <RouteIcon className="w-3 h-3" />
                              <span>{routeInfo.label}</span>
                            </Badge>
                          </div>

                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => copyToClipboard(msg.content, index)}
                              className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-colors"
                              title="Copy response"
                            >
                              {copiedIndex === index ? (
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>

                        {/* Markdown Content */}
                        <div className="prose-nexora text-sm">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>

                        {/* Verification & Fact-check Card */}
                        {msg.verification && (
                          <VerificationBadge 
                            verification={msg.verification} 
                            routing={msg.routing} 
                          />
                        )}

                        {/* Document Citations */}
                        {msg.document_citations && msg.document_citations.filter(c => c.filename && c.filename !== 'unknown').length > 0 && (
                          <div className="pt-3 border-t border-zinc-850 space-y-2">
                            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold">
                              <FileCheck className="w-3 h-3" />
                              <span>Document Citations ({msg.document_citations.filter(c => c.filename && c.filename !== 'unknown').length})</span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.document_citations.filter(c => c.filename && c.filename !== 'unknown').map((cite, cIdx) => (
                                <span 
                                  key={cIdx} 
                                  className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300 font-mono flex items-center gap-1.5"
                                >
                                  <span className="text-emerald-400">#</span>
                                  <span>{cite.filename}</span>
                                  {cite.page_number && (
                                    <span className="text-zinc-400">(p. {cite.page_number})</span>
                                  )}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Web Sources */}
                        {msg.web_citations && msg.web_citations.filter(w => w.url && !w.url.includes('unknown')).length > 0 && (
                          <div className="pt-2 border-t border-zinc-850 space-y-2">
                            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
                              <BookOpen className="w-3 h-3" />
                              <span>Live Web Citations & Sources ({msg.web_citations.filter(w => w.url && !w.url.includes('unknown')).length})</span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.web_citations.filter(w => w.url && !w.url.includes('unknown')).map((web, wIdx) => (
                                <a
                                  key={wIdx}
                                  href={web.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300 hover:text-white hover:border-zinc-700 flex items-center gap-1.5 transition-colors"
                                >
                                  <Globe className="w-3 h-3 text-cyan-400 shrink-0" />
                                  <span className="truncate max-w-[200px]">{web.title || web.url}</span>
                                  <ExternalLink className="w-3 h-3 text-zinc-400 shrink-0" />
                                </a>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Lineage Footnote */}
                        <div className="pt-2 border-t border-zinc-900 text-[10px] text-zinc-400 font-mono">
                          Evidence Grounding: verified against retrieved documents and live sources.
                        </div>
                      </div>
                    )}
                  </div>

                  {/* User Avatar */}
                  {isUser && (
                    <div className="w-7 h-7 rounded-md bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 mt-1 text-zinc-300 font-mono text-xs">
                      YOU
                    </div>
                  )}
                </div>
              );
            })}

            {/* Synthesizing / Latency Status */}
            {isLoading && (
              <div className="flex gap-3 justify-start items-center text-zinc-400 text-xs">
                <div className="w-7 h-7 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0 text-cyan-400">
                  <Activity className="w-3.5 h-3.5 animate-spin" />
                </div>
                <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-zinc-950 border border-zinc-800 font-mono text-[11px] text-zinc-300">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                  <span>Analyzing inquiry & orchestrating intelligence tools...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Premium Vercel-style Input Composer */}
      <div className="border-t border-zinc-800/80 bg-zinc-950/90 backdrop-blur-md p-4 shrink-0 relative z-10">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto space-y-2">
          {/* Attachments preview strip */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 pb-1">
              {attachments.map((file, idx) => (
                <div
                  key={idx}
                  className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-xs text-zinc-200 flex items-center gap-2"
                >
                  <FileText className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span className="truncate max-w-[160px] font-mono text-[11px]">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(idx)}
                    className="p-0.5 text-zinc-400 hover:text-red-400 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Text Input Row */}
          <div className="relative rounded-xl border border-zinc-800 bg-zinc-900/60 focus-within:border-zinc-600 focus-within:bg-zinc-900/90 transition-all shadow-sm">
            <input
              type="file"
              multiple
              ref={fileInputRef}
              onChange={handleFileSelect}
              className="hidden"
              accept=".pdf,.docx,.txt,.csv,.xlsx,.jpg,.jpeg,.png,.webp"
            />

            <textarea
              ref={textareaRef}
              rows={2}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything, search current events, explore uploaded files, or debug code..."
              className="w-full bg-transparent border-none text-zinc-100 text-sm placeholder:text-zinc-500 focus:outline-none resize-none px-4 pt-3 pb-12 leading-relaxed"
            />

            {/* Bottom Actions inside the input box */}
            <div className="absolute left-3 bottom-2.5 right-3 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
                  title="Attach document, report, or image"
                >
                  <Paperclip className="w-4 h-4" />
                </Button>
                <span className="text-[11px] text-zinc-400 font-mono hidden sm:inline">
                  Supports PDF, DOCX, TXT, CSV, PNG, JPG
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  type="submit"
                  size="sm"
                  disabled={(!inputText.trim() && attachments.length === 0) || isLoading}
                  className={`h-8 px-3 text-xs gap-1.5 ${
                    (inputText.trim() || attachments.length > 0) && !isLoading
                      ? 'bg-cyan-500 text-zinc-950 font-semibold hover:bg-cyan-400 shadow-[0_0_16px_rgba(6,182,212,0.3)]'
                      : 'bg-zinc-800 text-zinc-400 cursor-not-allowed'
                  }`}
                >
                  <span>Submit</span>
                  <CornerDownLeft className="w-3 h-3" />
                </Button>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[10px] text-zinc-400 font-mono px-1">
            <span>
              Press <kbd className="px-1 py-0.2 rounded bg-zinc-900 border border-zinc-800">Enter</kbd> to execute • <kbd className="px-1 py-0.2 rounded bg-zinc-900 border border-zinc-800">Shift+Enter</kbd> for newline
            </span>
            <span className="text-emerald-400 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" /> Post-Gen Hallucination Filtering Active
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
