import React, { useState } from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  ChevronDown, 
  ChevronUp, 
  CheckCircle2, 
  HelpCircle,
  Sparkles
} from 'lucide-react';

export default function VerificationBadge({ verification, routing }) {
  const [expanded, setExpanded] = useState(false);

  if (!verification) return null;

  const {
    passed,
    confidence_score,
    evidence_grounding,
    faithfulness,
    citation_support,
    evidence_coverage,
    hallucination_risk,
    unsupported_claims = [],
    repair_action,
    repair_reason,
    repair_attempts = 0,
  } = verification;

  const confPercent = Math.round((confidence_score || 0) * 100);
  const groundingPercent = Math.round((evidence_grounding || 0) * 100);
  const relevancePercent = Math.round((verification.answer_relevance || 0) * 100);
  const citationPercent = Math.round((citation_support || 0) * 100);

  const riskBadgeStyles = {
    low: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    high: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  }[hallucination_risk] || 'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <div className="mt-3 rounded-xl border border-slate-800/90 bg-slate-900/50 backdrop-blur-sm overflow-hidden text-xs">
      {/* Header bar */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="px-3.5 py-2.5 flex items-center justify-between cursor-pointer hover:bg-slate-800/40 transition-colors select-none"
      >
        <div className="flex items-center gap-2.5">
          {passed ? (
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <ShieldCheck size={15} />
              <span>Verified Answer</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-amber-400 font-medium">
              <ShieldAlert size={15} />
              <span>Needs Verification Review</span>
            </div>
          )}

          <span className="text-slate-600">•</span>

          <span className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-wider ${riskBadgeStyles}`}>
            {hallucination_risk} Hallucination Risk
          </span>

          {repair_attempts > 0 && (
            <span className="hidden sm:inline px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/50 text-[10px]">
              CRAG Repaired ({repair_attempts}x)
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-slate-300">
            <span className="text-slate-400">Confidence:</span>
            <span className="font-mono font-bold text-cyan-400">{confPercent}%</span>
          </div>
          {expanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3.5 py-3 border-t border-slate-800/80 bg-slate-950/40 space-y-3">
          {/* Progress Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                <span>Grounding</span>
                <span className="font-mono text-slate-200">{groundingPercent}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${groundingPercent >= 70 ? 'bg-emerald-500' : 'bg-amber-500'}`} 
                  style={{ width: `${groundingPercent}%` }}
                />
              </div>
            </div>

            <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                <span>Relevance</span>
                <span className="font-mono text-slate-200">{relevancePercent}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${relevancePercent >= 60 ? 'bg-cyan-500' : 'bg-amber-500'}`} 
                  style={{ width: `${relevancePercent}%` }}
                />
              </div>
            </div>

            <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                <span>Citation Support</span>
                <span className="font-mono text-slate-200">{citationPercent}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${citationPercent >= 80 ? 'bg-indigo-500' : 'bg-rose-500'}`} 
                  style={{ width: `${citationPercent}%` }}
                />
              </div>
            </div>

            <div className="p-2 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                <span>Overall Faithfulness</span>
                <span className="font-mono text-slate-200">{Math.round((faithfulness || 0) * 100)}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${(faithfulness || 0) >= 0.7 ? 'bg-emerald-500' : 'bg-amber-500'}`} 
                  style={{ width: `${Math.round((faithfulness || 0) * 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Routing rationale */}
          {routing && (
            <div className="text-[11px] text-slate-400 flex items-start gap-1.5 bg-slate-900/60 p-2 rounded-lg border border-slate-800/80">
              <Sparkles size={13} className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-300">Orchestrator Decision: </span>
                <span>{routing.reasoning}</span>
                <span className="text-slate-400 ml-1">({Math.round(routing.confidence * 100)}% confidence)</span>
              </div>
            </div>
          )}

          {/* Unsupported claims list */}
          {unsupported_claims && unsupported_claims.length > 0 && (
            <div className="rounded-lg bg-rose-950/30 border border-rose-900/50 p-2.5 space-y-1.5">
              <div className="flex items-center gap-1.5 text-rose-400 font-semibold text-[11px]">
                <AlertTriangle size={13} />
                <span>Unsupported Material Claim(s) Identified:</span>
              </div>
              <ul className="list-disc list-inside text-rose-200/80 text-[11px] space-y-0.5">
                {unsupported_claims.map((claim, idx) => (
                  <li key={idx} className="italic truncate">{claim}</li>
                ))}
              </ul>
              {repair_action && (
                <div className="text-[10px] text-rose-300/90 pt-1 border-t border-rose-900/30">
                  <span className="font-semibold">Repair Action: </span>
                  <code>{repair_action}</code> — {repair_reason}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
