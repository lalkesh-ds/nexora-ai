import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
  Loader2
} from 'lucide-react';
import VerificationBadge from './VerificationBadge';

const PROMPT_SUGGESTIONS = [
  {
    title: 'Summarize Clinical Records',
    desc: 'Extract diagnoses, lab findings, and medications from uploaded documents.',
    prompt: 'Summarize the patient diagnoses, lab findings, and medication history from my uploaded document.',
    icon: FileText,
    color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  },
  {
    title: 'Live 2026 Medical Research',
    desc: 'Query live web and clinical trials for latest peer-reviewed breakthroughs.',
    prompt: 'Search the web for the latest clinical trial results and FDA announcements on GLP-1 agonists in 2026.',
    icon: Globe,
    color: 'text-sky-400 bg-sky-500/10 border-sky-500/30',
  },
  {
    title: 'Hybrid Guideline Comparison',
    desc: 'Cross-reference internal patient documents with external medical guidelines.',
    prompt: 'Compare the recommendations in my uploaded medical report with current published clinical guidelines.',
    icon: Activity,
    color: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  },
  {
    title: 'Inspect Medical Imaging & Labs',
    desc: 'Analyze prescription photos, diagnostic charts, or scanned reports with vision AI.',
    prompt: 'Analyze this diagnostic image or lab chart and identify all notable values and visual features.',
    icon: Eye,
    color: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
  },
];

const ROUTE_LABELS = {
  DOCUMENT_RAG: { label: 'Document RAG', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  WEB_SEARCH: { label: 'Live Web Research', color: 'bg-sky-500/10 text-sky-400 border-sky-500/30' },
  HYBRID: { label: 'Hybrid Docs + Web', color: 'bg-orange-500/10 text-orange-400 border-orange-500/30' },
  VISION: { label: 'Multimodal Vision', color: 'bg-purple-500/10 text-purple-400 border-purple-500/30' },
  GENERAL_LLM: { label: 'Clinical Assistant', color: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30' },
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if ((!inputText.trim() && attachments.length === 0) || isLoading) return;
    onSendMessage(inputText.trim(), attachments);
    setInputText('');
    setAttachments([]);
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
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950 relative">
      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8 space-y-6">
        {messages.length === 0 ? (
          /* Empty State */
          <div className="max-w-3xl mx-auto py-10 space-y-8 select-none">
            <div className="text-center space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-800/50 bg-cyan-950/40 text-cyan-400 text-xs font-medium">
                <Sparkles size={13} />
                <span>Evidence-Grounded Multimodal Clinical Intelligence</span>
              </div>
              <h1 className="text-3xl md:text-4xl font-extrabold text-slate-100 tracking-tight">
                Welcome to Nexora AI
              </h1>
              <p className="text-slate-400 text-sm md:text-base max-w-xl mx-auto leading-relaxed">
                Analyze clinical records, search the live web, inspect medical charts, and synthesize verified multi-source answers with zero hallucinated dosages or diagnoses.
              </p>
            </div>

            {/* Prompt Starter Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {PROMPT_SUGGESTIONS.map((s, i) => {
                const Icon = s.icon;
                return (
                  <div
                    key={i}
                    onClick={() => { setInputText(s.prompt); }}
                    className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 hover:border-slate-700 cursor-pointer transition-all hover:scale-[1.01] group space-y-2"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className={`p-2 rounded-lg border ${s.color}`}>
                        <Icon size={16} />
                      </div>
                      <span className="font-semibold text-sm text-slate-200 group-hover:text-cyan-400 transition-colors">
                        {s.title}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {s.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Message List */
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg, index) => {
              const isUser = msg.role === 'user';
              const routeInfo = ROUTE_LABELS[msg.route_used] || ROUTE_LABELS.GENERAL_LLM;

              return (
                <div key={index} className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
                  {/* Assistant Avatar */}
                  {!isUser && (
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center shrink-0 shadow-md shadow-cyan-500/20 mt-1">
                      <Bot size={17} className="text-white" />
                    </div>
                  )}

                  {/* Bubble Container */}
                  <div className={`max-w-[85%] md:max-w-[80%] space-y-2 ${isUser ? 'items-end' : 'items-start'}`}>
                    {/* User Message */}
                    {isUser ? (
                      <div className="rounded-2xl rounded-tr-sm bg-gradient-to-r from-cyan-600 to-indigo-600 text-white p-3.5 shadow-md shadow-cyan-600/10 space-y-2">
                        {/* Attachments pills */}
                        {msg.attachments && msg.attachments.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pb-1">
                            {msg.attachments.map((att, attIdx) => (
                              <div key={attIdx} className="px-2 py-0.5 rounded bg-black/20 text-[11px] flex items-center gap-1 border border-white/10">
                                <FileText size={11} />
                                <span className="truncate max-w-[120px]">{att.name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      </div>
                    ) : (
                      /* Assistant Message */
                      <div className="rounded-2xl rounded-tl-sm bg-slate-900 border border-slate-800 p-4 shadow-sm space-y-3">
                        {/* Route header */}
                        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                          <span className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-wider ${routeInfo.color}`}>
                            {routeInfo.label}
                          </span>

                          <button
                            onClick={() => copyToClipboard(msg.content, index)}
                            className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                            title="Copy to clipboard"
                          >
                            {copiedIndex === index ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                          </button>
                        </div>

                        {/* Content Markdown */}
                        <div className="prose-nexora text-sm">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>

                        {/* Verification & Quality Card */}
                        {msg.verification && (
                          <VerificationBadge 
                            verification={msg.verification} 
                            routing={msg.routing} 
                          />
                        )}

                        {/* Citations Drawers */}
                        {msg.document_citations && msg.document_citations.length > 0 && (
                          <div className="mt-3 pt-2.5 border-t border-slate-800/60">
                            <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block mb-1.5">
                              Document Citations ({msg.document_citations.length})
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.document_citations.map((cite, cIdx) => (
                                <span key={cIdx} className="px-2 py-1 rounded bg-slate-950 border border-emerald-900/40 text-[11px] text-emerald-300 font-mono">
                                  {cite.filename} {cite.page_number ? `(p. ${cite.page_number})` : ''}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {msg.web_citations && msg.web_citations.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-slate-800/60">
                            <span className="text-[11px] font-semibold text-sky-400 uppercase tracking-wider block mb-1.5">
                              Web Sources ({msg.web_citations.length})
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.web_citations.map((web, wIdx) => (
                                <a
                                  key={wIdx}
                                  href={web.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="px-2 py-1 rounded bg-slate-950 border border-sky-900/40 text-[11px] text-sky-300 hover:text-sky-200 flex items-center gap-1 transition-colors"
                                >
                                  <span className="truncate max-w-[150px]">{web.title || web.url}</span>
                                  <ExternalLink size={10} />
                                </a>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Medical Disclaimer Note */}
                        <div className="mt-2 text-[10px] text-slate-400 border-t border-slate-800/40 pt-2 italic">
                          Clinical Decision Support: Grounded in retrieved evidence. Never substitutes for professional clinical judgment.
                        </div>
                      </div>
                    )}
                  </div>

                  {/* User Avatar */}
                  {isUser && (
                    <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 mt-1">
                      <User size={16} className="text-slate-300" />
                    </div>
                  )}
                </div>
              );
            })}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex gap-3.5 justify-start items-center text-slate-400 text-xs">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center shrink-0">
                  <Bot size={17} className="text-white animate-pulse" />
                </div>
                <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-900 border border-slate-800">
                  <Loader2 size={15} className="animate-spin text-cyan-400" />
                  <span>Synthesizing evidence & verifying factual grounding...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Box Area */}
      <div className="border-t border-slate-800 bg-slate-900/80 backdrop-blur-md p-3 md:p-4 shrink-0">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto space-y-2">
          {/* Attachments preview strip */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 pb-1">
              {attachments.map((file, idx) => (
                <div
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-200 flex items-center gap-1.5"
                >
                  <FileText size={13} className="text-cyan-400" />
                  <span className="truncate max-w-[140px] font-medium">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(idx)}
                    className="p-0.5 text-slate-400 hover:text-rose-400"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Text Input Row */}
          <div className="flex items-end gap-2 bg-slate-950 border border-slate-800 rounded-2xl p-2 focus-within:border-cyan-500/80 transition-colors shadow-inner">
            <input
              type="file"
              multiple
              ref={fileInputRef}
              onChange={handleFileSelect}
              className="hidden"
              accept=".pdf,.docx,.txt,.csv,.xlsx,.jpg,.jpeg,.png,.webp"
            />

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 text-slate-400 hover:text-cyan-400 hover:bg-slate-900 rounded-xl transition-colors shrink-0"
              title="Attach clinical document or image"
            >
              <Paperclip size={18} />
            </button>

            <textarea
              rows={1}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a medical question, analyze documents, or request web research..."
              className="flex-1 bg-transparent border-none text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none resize-none max-h-36 py-2 px-1 leading-relaxed"
            />

            <button
              type="submit"
              disabled={(!inputText.trim() && attachments.length === 0) || isLoading}
              className={`p-2.5 rounded-xl transition-all shrink-0 ${
                (inputText.trim() || attachments.length > 0) && !isLoading
                  ? 'bg-gradient-to-tr from-cyan-600 to-indigo-600 text-white shadow-md shadow-cyan-600/30 hover:scale-[1.03] active:scale-[0.98]'
                  : 'bg-slate-800/80 text-slate-400 cursor-not-allowed'
              }`}
              title="Submit Query"
            >
              <Send size={16} />
            </button>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
            <span>Press <kbd className="px-1 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px]">Enter</kbd> to send, <kbd className="px-1 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px]">Shift+Enter</kbd> for newline</span>
            <span className="hidden sm:inline">Nexora Clinical Guardrails Enabled</span>
          </div>
        </form>
      </div>
    </div>
  );
}
