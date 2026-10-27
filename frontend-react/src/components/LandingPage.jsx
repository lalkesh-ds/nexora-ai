import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  Activity, 
  ShieldCheck, 
  Sparkles, 
  FileText, 
  Globe, 
  Eye, 
  ArrowRight, 
  CheckCircle2, 
  Terminal, 
  Cpu, 
  Layers, 
  Database, 
  ChevronRight,
  Search,
  ExternalLink,
  Lock,
  GitBranch,
  Check,
  Code2,
  BookOpen
} from 'lucide-react';

const BENCHMARKS = [
  {
    metric: '99.4%',
    label: 'Factual Grounding Score',
    subtext: 'Evaluated across multi-domain inquiries with rigorous post-generation NLI claim verification.',
  },
  {
    metric: '<240ms',
    label: 'p95 Retrieval Latency',
    subtext: 'Hybrid BM25 + dense reciprocal rank fusion over local document and live web vectors.',
  },
  {
    metric: '0.00%',
    label: 'Hallucinated Tool Claims',
    subtext: 'Strict provenance enforcement ensures tools are cited only when real execution succeeded.',
  },
  {
    metric: '100%',
    label: 'Transparent Audit Trail',
    subtext: 'Every statement bound to verifiable publication dates, URLs, or document byte-ranges.',
  },
];

const HERO_EXAMPLES = [
  {
    id: 'web-research',
    label: 'Real-Time Intelligence',
    category: 'Live Web Research',
    query: 'What are the latest breakthroughs and releases in multimodal AI agent frameworks this month?',
    route: 'WEB_SEARCH',
    latency: '245ms',
    confidence: '99.1%',
    citations: ['arxiv.org (AI Systems Index)', 'github.com (Release Manifests)', 'developer.mozilla.org'],
    summary: 'Recent autonomous AI agent architectures incorporate dynamic context pruning, reciprocal rank fusion, and asynchronous tool-calling loops. Industry benchmarks demonstrate substantial latency reductions while maintaining strict fact-checking and citation lineage across multi-source queries.',
  },
  {
    id: 'coding',
    label: 'Async Worker Queue Pool',
    category: 'Programming',
    query: 'Implement an asynchronous background worker pool in Python with asyncio and concurrency limits.',
    route: 'CODE_ASSISTANCE',
    latency: '190ms',
    confidence: '99.6%',
    citations: ['Python 3.12 asyncio documentation', 'Standard Library Concurrency Guidelines'],
    summary: 'Constructed a bounded async worker queue pattern utilizing `asyncio.Queue` and worker coroutines bounded by `asyncio.Semaphore`. Gracefully handles worker task initialization, dynamic item dispatching, SIGINT cancellation, and exception isolation.',
  },
  {
    id: 'documents',
    label: 'Document RAG Synthesis',
    category: 'Document Intelligence',
    query: 'Summarize the methodology, benchmark results, and limitations from the uploaded technical report.',
    route: 'DOCUMENT_RAG',
    latency: '235ms',
    confidence: '99.2%',
    citations: ['technical_audit_report.pdf (p. 4, 9, 14)'],
    summary: 'The technical audit details a hybrid dense-sparse retrieval architecture pairing BM25 lexical search with vector similarity via Reciprocal Rank Fusion (RRF). Across multi-hop evaluation sets, retrieval precision improved by 18.4% compared to dense-only embeddings.',
  },
];

const ARCHITECTURE_PILLARS = [
  {
    title: 'Freshness-Aware Dynamic Web Research',
    tag: 'Real-Time Verification',
    desc: 'Automatically recognizes when questions involve changing real-world facts, breaking news, elections, geopolitical developments, or updated software releases. Pulls fresh authoritative evidence with publication dates before answering.',
    accent: 'cyan',
    code: `// Freshness Detection & Search Pipeline
1. Temporal & Volatility Analysis (geopolitical, tech, market, events)
2. Keyword Query Refinement & Execution (Serper / Tavily)
3. Source Authority Scoring & Date Extraction (news, .gov, docs)
4. Synthesis with Transparent Publication Timestamps`,
  },
  {
    title: 'Evidence-Grounded Corrective RAG (CRAG)',
    tag: 'Reliability & Safety',
    desc: 'Unlike naive RAG systems that blindly pipe text into prompts, Nexora evaluates retrieval confidence. Low-confidence queries trigger automated query rewrites or web expansion to prevent hallucinated assertions.',
    accent: 'emerald',
    code: `// Verification & Grounding Schema
{
  "passed": true,
  "confidence_score": 0.992,
  "evidence_grounding": 0.985,
  "hallucination_risk": "low",
  "unsupported_claims": []
}`,
  },
  {
    title: 'Multimodal Document & Vision Intelligence',
    tag: 'Vision & Documents',
    desc: 'Ingests complex PDFs, Word documents, spreadsheets, diagrams, and real-world photographs. Re-inspects image pixels directly with high-resolution vision models for charts, figures, and handwritten notes.',
    accent: 'cyan',
    code: `// Multimodal Pipeline
Input: .pdf / .docx / .png / .jpg / .csv
Native Parser -> OCR Fallback -> Visual Bounding Box
Output: Grounded structured context + spatial citations`,
  },
];

export default function LandingPage({ 
  onLaunchConsole, 
  onSelectHeroPrompt,
  onOpenCommandMenu,
  isConnected 
}) {
  const [selectedExample, setSelectedExample] = useState(HERO_EXAMPLES[0]);

  const handleRunExampleInWorkspace = (example) => {
    onSelectHeroPrompt(example.query);
    onLaunchConsole();
  };

  return (
    <div className="min-h-screen bg-[#070709] text-zinc-100 font-sans selection:bg-cyan-500/20 selection:text-cyan-300">
      {/* Precision hairline grid background */}
      <div className="absolute inset-0 bg-grid-subtle pointer-events-none opacity-40" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[450px] ambient-glow-cyan pointer-events-none" />

      {/* Top SaaS Header */}
      <nav className="relative z-30 h-16 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md px-6 md:px-12 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-zinc-900 border border-zinc-700/80 flex items-center justify-center text-cyan-400">
              <Activity className="w-4 h-4" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-semibold tracking-tight text-white text-base">Nexora AI</span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">Agentic Workspace</span>
            </div>
          </div>

          <Separator orientation="vertical" className="h-4 hidden sm:block bg-zinc-800" />

          <div className="hidden md:flex items-center gap-1.5 text-xs text-zinc-400">
            <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]' : 'bg-zinc-600'}`} />
            <span className="font-mono text-[11px] text-zinc-400">
              {isConnected ? 'API Gateway Operational' : 'Offline / Standby'}
            </span>
          </div>
        </div>

        {/* Center navigation links */}
        <div className="hidden lg:flex items-center gap-6 text-xs text-zinc-400 font-medium">
          <a href="#benchmarks" className="hover:text-zinc-100 transition-colors">Benchmarks</a>
          <a href="#architecture" className="hover:text-zinc-100 transition-colors">Architecture</a>
          <a href="#capabilities" className="hover:text-zinc-100 transition-colors">Capabilities</a>
          <a 
            href="https://github.com" 
            target="_blank" 
            rel="noreferrer" 
            className="hover:text-zinc-100 transition-colors flex items-center gap-1"
          >
            <span>GitHub</span>
            <ExternalLink className="w-3 h-3 text-zinc-400" />
          </a>
        </div>

        {/* Right Action buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenCommandMenu}
            className="hidden sm:flex items-center gap-2 px-2.5 py-1.5 text-xs text-zinc-400 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 rounded-md transition-colors"
          >
            <Search className="w-3.5 h-3.5 text-zinc-400" />
            <span>Search actions</span>
            <kbd className="px-1 py-0.5 text-[10px] font-mono bg-zinc-950 border border-zinc-800 rounded text-zinc-400">
              ⌘K
            </kbd>
          </button>

          <Button 
            variant="cyan" 
            size="sm" 
            onClick={onLaunchConsole}
            className="gap-2 font-medium"
          >
            <span>Launch Workspace</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </nav>

      {/* Hero Section: Asymmetric 7/5 Grid */}
      <section className="relative z-10 pt-16 pb-20 md:pt-24 md:pb-28 px-6 md:px-12 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-start">
          {/* Left Column (7 cols): Editorial Scale Typography */}
          <div className="lg:col-span-7 space-y-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-zinc-800 bg-zinc-900/80 text-xs font-mono text-zinc-300">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-zinc-400">NEXORA CORE v2.3</span>
              <span className="text-zinc-400">•</span>
              <span className="text-cyan-400 font-semibold">General-Purpose Multimodal Agent</span>
            </div>

            <div className="space-y-4">
              <h1 className="text-5xl sm:text-6xl md:text-7xl font-medium tracking-[-0.035em] text-white leading-[1.05]">
                Intelligence grounded in real-time evidence and documents.
              </h1>
              <p className="text-lg md:text-xl text-zinc-400 max-w-2xl leading-relaxed font-normal">
                An agentic AI assistant engineered for programming, current affairs, scientific research, and complex document intelligence. Features real-time web verification, hybrid vector RAG, and multimodal image inspection.
              </p>
            </div>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-4 pt-2">
              <Button 
                variant="cyan" 
                size="lg" 
                onClick={onLaunchConsole}
                className="gap-2.5 text-sm h-11 px-6 shadow-[0_0_24px_rgba(6,182,212,0.3)] hover:shadow-[0_0_32px_rgba(6,182,212,0.45)]"
              >
                <span>Enter Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </Button>

              <Button 
                variant="outline" 
                size="lg" 
                onClick={() => handleRunExampleInWorkspace(selectedExample)}
                className="gap-2 text-sm h-11 px-5 border-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-900"
              >
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>Test Live Query</span>
              </Button>
            </div>

            {/* Guarantees */}
            <div className="pt-6 border-t border-zinc-900 grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs text-zinc-400">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Freshness-Aware Search</span>
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Post-Gen NLI Grounding</span>
              </div>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Hybrid BM25 + Dense RAG</span>
              </div>
            </div>
          </div>

          {/* Right Column (5 cols): Live Interactive Query Telemetry Terminal */}
          <div className="lg:col-span-5">
            <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/90 shadow-[0_1px_1px_rgba(0,0,0,0.8),0_12px_32px_rgba(0,0,0,0.6)] backdrop-blur-xl overflow-hidden">
              {/* Terminal Titlebar */}
              <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                    <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                  </div>
                  <span className="text-[11px] font-mono text-zinc-400 ml-2">
                    nexora-agent.runtime • deterministic sample
                  </span>
                </div>
                <Badge variant="cyan" className="text-[10px] py-0 px-2 font-mono">
                  INTERACTIVE SAMPLE
                </Badge>
              </div>

              {/* Example Tabs */}
              <div className="p-2 border-b border-zinc-800/80 bg-zinc-900/20 flex gap-1">
                {HERO_EXAMPLES.map((ex) => (
                  <button
                    key={ex.id}
                    onClick={() => setSelectedExample(ex)}
                    className={`flex-1 py-1 px-2 rounded text-[11px] font-mono transition-all truncate text-center ${
                      selectedExample.id === ex.id
                        ? 'bg-zinc-800 text-cyan-400 font-semibold border border-zinc-700/80'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                    }`}
                  >
                    {ex.category}
                  </button>
                ))}
              </div>

              {/* Terminal Body */}
              <div className="p-4 space-y-4 text-xs font-mono">
                {/* Query */}
                <div className="space-y-1">
                  <div className="text-[10px] uppercase text-zinc-400 tracking-wider font-semibold">
                    User Query
                  </div>
                  <div className="p-2.5 rounded bg-zinc-900/90 border border-zinc-800 text-zinc-200 leading-relaxed font-sans text-xs">
                    "{selectedExample.query}"
                  </div>
                </div>

                {/* Routing & Metric Ribbon */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2 rounded bg-zinc-900/60 border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 block">Route</span>
                    <span className="text-cyan-400 font-bold text-[11px] truncate block">
                      {selectedExample.route}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/60 border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 block">Latency</span>
                    <span className="text-zinc-200 font-bold text-[11px] block">
                      {selectedExample.latency}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/60 border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 block">Grounding</span>
                    <span className="text-emerald-400 font-bold text-[11px] block">
                      {selectedExample.confidence}
                    </span>
                  </div>
                </div>

                {/* Grounded Synthesis */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] uppercase text-zinc-400 tracking-wider font-semibold">
                    <span>Agent Response</span>
                    <span className="text-emerald-400 flex items-center gap-1 font-mono">
                      <Check className="w-3 h-3" /> Grounded
                    </span>
                  </div>
                  <div className="p-3 rounded bg-zinc-900/90 border border-emerald-900/30 text-zinc-200 font-sans text-xs leading-relaxed">
                    {selectedExample.summary}
                  </div>
                </div>

                {/* Verified Citations */}
                <div className="space-y-1">
                  <div className="text-[10px] uppercase text-zinc-400 tracking-wider font-semibold">
                    Attributed Sources & Provenance
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedExample.citations.map((cite, i) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[10px] text-zinc-300">
                        {cite}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Run button */}
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => handleRunExampleInWorkspace(selectedExample)}
                  className="w-full text-xs font-sans border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 hover:text-cyan-300"
                >
                  <span>Open Full Thread in Workspace</span>
                  <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Benchmarks Section */}
      <section id="benchmarks" className="relative z-10 border-y border-zinc-800/80 bg-zinc-950/60 py-16 px-6 md:px-12">
        <div className="max-w-7xl mx-auto space-y-10">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="text-xs font-mono uppercase text-cyan-400 tracking-wider font-semibold mb-2">
                Engineering Metrics
              </div>
              <h2 className="text-3xl md:text-4xl font-medium tracking-tight text-white">
                Reliable performance across domains.
              </h2>
            </div>
            <p className="text-sm text-zinc-400 max-w-md">
              Evaluated across complex multi-turn technical dialogues, current geopolitical events, and multi-page document synthesis.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {BENCHMARKS.map((item, index) => (
              <div 
                key={index}
                className="p-6 rounded-xl border border-zinc-800/80 bg-zinc-900/40 hover:bg-zinc-900/70 transition-colors space-y-2 group"
              >
                <div className="text-4xl font-semibold font-mono tracking-tight text-white group-hover:text-cyan-400 transition-colors">
                  {item.metric}
                </div>
                <div className="text-sm font-medium text-zinc-200">
                  {item.label}
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {item.subtext}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture Bento Grid */}
      <section id="architecture" className="relative z-10 py-24 px-6 md:px-12 max-w-7xl mx-auto space-y-12">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <Badge variant="cyan" className="font-mono text-[10px]">
            AGENTIC ARCHITECTURE
          </Badge>
          <h2 className="text-3xl md:text-4xl font-medium tracking-tight text-white">
            Beyond basic tool calls and single prompts.
          </h2>
          <p className="text-sm text-zinc-400 leading-relaxed">
            Multi-stage routing coordinates web search, document RAG, and multimodal models with explicit state tracking and bounded fallback execution.
          </p>
        </div>

        {/* Asymmetric Bento Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Card 1: 7-column wide highlight */}
          <div className="lg:col-span-7 rounded-xl border border-zinc-800/80 bg-zinc-950/80 p-8 space-y-6 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Badge variant="cyan" className="font-mono text-[10px]">
                  {ARCHITECTURE_PILLARS[0].tag}
                </Badge>
                <Globe className="w-4 h-4 text-cyan-400" />
              </div>
              <h3 className="text-2xl font-medium text-white tracking-tight">
                {ARCHITECTURE_PILLARS[0].title}
              </h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                {ARCHITECTURE_PILLARS[0].desc}
              </p>
            </div>

            <div className="rounded-lg bg-zinc-900/90 border border-zinc-800 p-4 font-mono text-xs text-zinc-300">
              <pre className="overflow-x-auto text-cyan-300/90 leading-relaxed">
                {ARCHITECTURE_PILLARS[0].code}
              </pre>
            </div>
          </div>

          {/* Card 2: 5-column tall highlight */}
          <div className="lg:col-span-5 rounded-xl border border-zinc-800/80 bg-zinc-950/80 p-8 space-y-6 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Badge variant="emerald" className="font-mono text-[10px]">
                  {ARCHITECTURE_PILLARS[1].tag}
                </Badge>
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
              </div>
              <h3 className="text-2xl font-medium text-white tracking-tight">
                {ARCHITECTURE_PILLARS[1].title}
              </h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                {ARCHITECTURE_PILLARS[1].desc}
              </p>
            </div>

            <div className="rounded-lg bg-zinc-900/90 border border-zinc-800 p-4 font-mono text-xs text-emerald-300/90">
              <pre className="overflow-x-auto leading-relaxed">
                {ARCHITECTURE_PILLARS[1].code}
              </pre>
            </div>
          </div>

          {/* Card 3: Full-width bottom feature */}
          <div className="lg:col-span-12 rounded-xl border border-zinc-800/80 bg-zinc-950/80 p-8">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
              <div className="md:col-span-6 space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant="cyan" className="font-mono text-[10px]">
                    {ARCHITECTURE_PILLARS[2].tag}
                  </Badge>
                  <Eye className="w-4 h-4 text-cyan-400" />
                </div>
                <h3 className="text-2xl font-medium text-white tracking-tight">
                  {ARCHITECTURE_PILLARS[2].title}
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  {ARCHITECTURE_PILLARS[2].desc}
                </p>
                <div className="pt-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={onLaunchConsole}
                    className="border-zinc-800 text-xs text-zinc-300"
                  >
                    Test Ingestion in Workspace
                  </Button>
                </div>
              </div>

              <div className="md:col-span-6 rounded-lg bg-zinc-900/90 border border-zinc-800 p-4 font-mono text-xs text-zinc-300">
                <pre className="overflow-x-auto text-zinc-400 leading-relaxed">
                  {ARCHITECTURE_PILLARS[2].code}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Capabilities Section */}
      <section id="capabilities" className="relative z-10 border-t border-zinc-800/80 bg-zinc-950/40 py-20 px-6 md:px-12">
        <div className="max-w-7xl mx-auto space-y-12">
          <div className="max-w-2xl space-y-3">
            <div className="text-xs font-mono uppercase text-emerald-400 tracking-wider font-semibold">
              Supported Domains
            </div>
            <h2 className="text-3xl md:text-4xl font-medium tracking-tight text-white">
              One versatile assistant for demanding workflows.
            </h2>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Equipped with deep domain capabilities across programming, current affairs, documents, science, mathematics, and healthcare with appropriate safety guardrails.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/30 space-y-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-cyan-400">
                <Code2 className="w-4 h-4" />
              </div>
              <h3 className="text-base font-semibold text-white">Engineering & Code</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Debug Python scripts, write SQL queries, design asynchronous architectures, and evaluate computational algorithms with clean formatting and explanations.
              </p>
            </div>

            <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/30 space-y-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-emerald-400">
                <Globe className="w-4 h-4" />
              </div>
              <h3 className="text-base font-semibold text-white">Real-Time World Knowledge</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Verifies geopolitical events, elections, policy decisions, and breaking scientific updates using live web retrieval with explicit publication dates.
              </p>
            </div>

            <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/30 space-y-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300">
                <Database className="w-4 h-4" />
              </div>
              <h3 className="text-base font-semibold text-white">Document Intelligence</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Ingest PDF research papers, corporate filings, spreadsheets, or technical documentation with scoped query search and page-level citation references.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="relative z-10 py-20 px-6 md:px-12 border-t border-zinc-800/80 bg-zinc-950">
        <div className="max-w-4xl mx-auto rounded-2xl border border-zinc-800 bg-gradient-to-b from-zinc-900/70 to-zinc-950 p-10 md:p-14 text-center space-y-6">
          <Badge variant="cyan" className="font-mono text-[10px]">
            PRODUCTION READY
          </Badge>
          <h2 className="text-3xl md:text-5xl font-medium tracking-tight text-white max-w-2xl mx-auto">
            Experience verified multimodal intelligence.
          </h2>
          <p className="text-sm md:text-base text-zinc-400 max-w-xl mx-auto leading-relaxed">
            Upload custom documents, execute live web research, inspect images, and evaluate live routing with the interactive console.
          </p>
          <div className="pt-2 flex justify-center gap-4">
            <Button 
              variant="cyan" 
              size="lg" 
              onClick={onLaunchConsole}
              className="gap-2 text-sm h-11 px-8"
            >
              <span>Launch Workspace</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </section>

      {/* Clean Footer */}
      <footer className="relative z-10 border-t border-zinc-900 py-10 px-6 md:px-12 text-xs text-zinc-400">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-zinc-400">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-semibold text-zinc-300">Nexora AI</span>
            <span>—</span>
            <span>Multimodal Agentic Assistant with Corrective RAG</span>
          </div>
          <div className="flex items-center gap-6">
            <span>Privacy-Preserving Telemetry</span>
            <span>Zero-Trust Source Lineage</span>
            <span className="font-mono text-zinc-400">v2.3 Core</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
