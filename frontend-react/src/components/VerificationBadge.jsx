import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  ChevronDown, 
  ChevronUp, 
  CheckCircle2, 
  Sparkles,
  RefreshCw,
  FileCheck
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

  const isLowRisk = hallucination_risk === 'low';

  return (
    <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/70 overflow-hidden text-xs">
      {/* Top summary row */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-zinc-900/60 transition-colors select-none"
      >
        <div className="flex items-center gap-2 flex-wrap">
          {passed ? (
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Grounded Evidence</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-amber-400 font-medium">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Verification Review Needed</span>
            </div>
          )}

          <span className="text-zinc-700">•</span>

          <Badge 
            variant={isLowRisk ? "emerald" : "destructive"} 
            className="text-[10px] py-0 px-1.5 font-mono"
          >
            {hallucination_risk ? `${hallucination_risk.toUpperCase()} RISK` : 'VERIFIED'}
          </Badge>

          {repair_attempts > 0 && (
            <Badge variant="cyan" className="text-[10px] py-0 px-1.5 font-mono">
              <RefreshCw className="w-2.5 h-2.5 mr-1" />
              CRAG REPAIRED ({repair_attempts}x)
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1 text-zinc-300 font-mono text-[11px]">
            <span className="text-zinc-400">Score:</span>
            <span className="font-semibold text-cyan-400">{confPercent}%</span>
          </div>
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </div>
      </div>

      {/* Expanded Metrics Details */}
      {expanded && (
        <div className="p-3 border-t border-zinc-800/80 bg-zinc-900/40 space-y-3">
          {/* Progress Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="p-2 rounded bg-zinc-950/80 border border-zinc-800">
              <div className="flex justify-between text-[10px] text-zinc-400 mb-1">
                <span>Grounding</span>
                <span className="font-mono text-zinc-200">{groundingPercent}%</span>
              </div>
              <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${groundingPercent >= 70 ? 'bg-emerald-400' : 'bg-cyan-400'}`} 
                  style={{ width: `${groundingPercent}%` }}
                />
              </div>
            </div>

            <div className="p-2 rounded bg-zinc-950/80 border border-zinc-800">
              <div className="flex justify-between text-[10px] text-zinc-400 mb-1">
                <span>Relevance</span>
                <span className="font-mono text-zinc-200">{relevancePercent}%</span>
              </div>
              <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className="h-full rounded-full bg-cyan-400" 
                  style={{ width: `${relevancePercent}%` }}
                />
              </div>
            </div>

            <div className="p-2 rounded bg-zinc-950/80 border border-zinc-800">
              <div className="flex justify-between text-[10px] text-zinc-400 mb-1">
                <span>Citations</span>
                <span className="font-mono text-zinc-200">{citationPercent}%</span>
              </div>
              <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full ${citationPercent >= 80 ? 'bg-emerald-400' : 'bg-zinc-500'}`} 
                  style={{ width: `${citationPercent}%` }}
                />
              </div>
            </div>

            <div className="p-2 rounded bg-zinc-950/80 border border-zinc-800">
              <div className="flex justify-between text-[10px] text-zinc-400 mb-1">
                <span>Faithfulness</span>
                <span className="font-mono text-zinc-200">{Math.round((faithfulness || 0) * 100)}%</span>
              </div>
              <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className="h-full rounded-full bg-emerald-400" 
                  style={{ width: `${Math.round((faithfulness || 0) * 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Routing Decision Rationale */}
          {routing && (
            <div className="p-2 rounded bg-zinc-950 border border-zinc-800 text-[11px] text-zinc-400 flex items-start gap-2">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-zinc-200">Orchestrator Logic: </span>
                <span>{routing.reasoning}</span>
                <span className="text-zinc-400 ml-1 font-mono">
                  ({Math.round(routing.confidence * 100)}% route confidence)
                </span>
              </div>
            </div>
          )}

          {/* Unsupported Material Claims (if any) */}
          {unsupported_claims && unsupported_claims.length > 0 && (
            <div className="p-2.5 rounded bg-red-950/20 border border-red-900/40 space-y-1.5">
              <div className="flex items-center gap-1.5 text-red-400 font-semibold text-[11px]">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Unverified Claim(s) Detected:</span>
              </div>
              <ul className="list-disc list-inside text-red-300 text-[11px] space-y-0.5">
                {unsupported_claims.map((claim, idx) => (
                  <li key={idx} className="italic truncate">{claim}</li>
                ))}
              </ul>
              {repair_action && (
                <div className="text-[10px] text-zinc-400 pt-1 border-t border-red-900/30">
                  <span className="font-semibold text-zinc-300">Action: </span>
                  <code className="text-red-300">{repair_action}</code> — {repair_reason}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
