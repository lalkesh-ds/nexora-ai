import React, { useState } from 'react';
import { 
  X, 
  FileText, 
  Upload, 
  Calculator, 
  Search, 
  Trash2, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Layers, 
  ExternalLink, 
  Copy, 
  Send,
  Database,
  Cpu
} from 'lucide-react';
import { uploadDocuments, deleteDocument } from '../api';

export default function ToolsPanel({ 
  isOpen, 
  onClose, 
  documents, 
  onRefreshDocs, 
  selectedDocIds, 
  onToggleDocScope,
  latestResponse,
  onInsertPrompt,
  sessionId
}) {
  const [activeTab, setActiveTab] = useState('docs'); // 'docs' | 'evidence' | 'calc' | 'sys'
  const [uploading, setUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState([]);
  const [dragOver, setDragOver] = useState(false);

  // Clinical Calculator states
  // 1. BMI / BSA
  const [calcHeight, setCalcHeight] = useState('175'); // cm
  const [calcWeight, setCalcWeight] = useState('70');  // kg
  // 2. eGFR / Creatinine Clearance
  const [calcAge, setCalcAge] = useState('45');
  const [calcScr, setCalcScr] = useState('1.1'); // mg/dL
  const [calcSex, setCalcSex] = useState('male');
  // 3. MAP
  const [calcSys, setCalcSys] = useState('120');
  const [calcDia, setCalcDia] = useState('80');

  if (!isOpen) return null;

  // Calculators logic
  const heightM = parseFloat(calcHeight) / 100;
  const weightKg = parseFloat(calcWeight);
  const bmi = (heightM > 0 && weightKg > 0) ? (weightKg / (heightM * heightM)).toFixed(1) : null;
  const bsa = (heightM > 0 && weightKg > 0) ? (0.007184 * Math.pow(parseFloat(calcHeight), 0.725) * Math.pow(weightKg, 0.425)).toFixed(2) : null;

  const ageNum = parseFloat(calcAge);
  const scrNum = parseFloat(calcScr);
  const crcl = (ageNum > 0 && scrNum > 0 && weightKg > 0) 
    ? (((140 - ageNum) * weightKg) / (72 * scrNum) * (calcSex === 'female' ? 0.85 : 1.0)).toFixed(1)
    : null;

  const sysNum = parseFloat(calcSys);
  const diaNum = parseFloat(calcDia);
  const map = (sysNum > 0 && diaNum > 0) ? ((diaNum * 2 + sysNum) / 3).toFixed(1) : null;

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadErrors([]);
    try {
      const res = await uploadDocuments(files, sessionId);
      const issues = res.documents
        .filter(d => d.status !== 'completed')
        .map(d => `${d.filename}: ${d.error || 'Failed'}`);
      setUploadErrors(issues);
      await onRefreshDocs();
    } catch (err) {
      setUploadErrors([err.message || 'Upload failed']);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId, e) => {
    e.stopPropagation();
    if (!confirm('Remove this document from the knowledge base?')) return;
    await deleteDocument(docId);
    await onRefreshDocs();
  };

  return (
    <aside className="w-80 md:w-96 border-l border-slate-800 bg-slate-950 flex flex-col h-full shrink-0 z-20">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60">
            <Layers size={15} />
          </div>
          <span className="font-semibold text-sm text-slate-100">Advanced Clinical Tools</span>
        </div>
        <button 
          onClick={onClose} 
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Navigation tabs */}
      <div className="flex border-b border-slate-800/80 bg-slate-900/50 p-1 text-xs font-medium">
        <button
          onClick={() => setActiveTab('docs')}
          className={`flex-1 py-1.5 rounded-md transition-all ${
            activeTab === 'docs' ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Documents
        </button>
        <button
          onClick={() => setActiveTab('evidence')}
          className={`flex-1 py-1.5 rounded-md transition-all ${
            activeTab === 'evidence' ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Evidence
        </button>
        <button
          onClick={() => setActiveTab('calc')}
          className={`flex-1 py-1.5 rounded-md transition-all ${
            activeTab === 'calc' ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Calculators
        </button>
        <button
          onClick={() => setActiveTab('sys')}
          className={`flex-1 py-1.5 rounded-md transition-all ${
            activeTab === 'sys' ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          System
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
        {/* TAB 1: Documents & Ingestion */}
        {activeTab === 'docs' && (
          <div className="space-y-3.5">
            {/* Upload dropzone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                handleFileUpload(e.dataTransfer.files);
              }}
              className={`border-2 border-dashed rounded-xl p-4 text-center transition-all cursor-pointer ${
                dragOver 
                  ? 'border-cyan-500 bg-cyan-950/20' 
                  : 'border-slate-800 hover:border-slate-700 bg-slate-900/30'
              }`}
            >
              <input
                type="file"
                multiple
                id="tool-file-upload"
                className="hidden"
                onChange={(e) => handleFileUpload(e.target.files)}
                accept=".pdf,.docx,.txt,.csv,.xlsx,.jpg,.jpeg,.png,.webp"
              />
              <label htmlFor="tool-file-upload" className="cursor-pointer space-y-2 block">
                <div className="w-10 h-10 rounded-full bg-cyan-950/60 border border-cyan-800/50 flex items-center justify-center mx-auto text-cyan-400">
                  {uploading ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
                </div>
                <div className="text-xs font-medium text-slate-200">
                  {uploading ? 'Processing & Indexing Document(s)...' : 'Upload Clinical Documents'}
                </div>
                <p className="text-[10px] text-slate-400">
                  PDF, DOCX, TXT, CSV, XLSX, Scanned/Photo Images
                </p>
              </label>
            </div>

            {/* Error notifications */}
            {uploadErrors.length > 0 && (
              <div className="p-2.5 rounded-lg bg-rose-950/30 border border-rose-900/50 text-[11px] text-rose-300 space-y-1">
                <div className="font-semibold flex items-center gap-1 text-rose-400">
                  <AlertCircle size={13} />
                  <span>Upload Notice</span>
                </div>
                {uploadErrors.map((err, i) => (
                  <p key={i} className="truncate">{err}</p>
                ))}
              </div>
            )}

            {/* Document collection list */}
            <div>
              <div className="flex items-center justify-between text-xs font-medium text-slate-300 mb-2">
                <span>Knowledge Base ({documents.length})</span>
                {selectedDocIds.length > 0 && (
                  <span className="text-[10px] text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/40">
                    {selectedDocIds.length} scoped
                  </span>
                )}
              </div>

              {documents.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-xs">
                  No documents in knowledge base yet.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {documents.map((doc) => {
                    const isSelected = selectedDocIds.includes(doc.document_id);
                    return (
                      <div
                        key={doc.document_id}
                        onClick={() => onToggleDocScope(doc.document_id)}
                        className={`p-2.5 rounded-lg border text-xs transition-all flex items-center justify-between cursor-pointer ${
                          isSelected 
                            ? 'bg-cyan-950/30 border-cyan-800/60 text-slate-100' 
                            : 'bg-slate-900/50 border-slate-800/80 hover:bg-slate-800/60 text-slate-300'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 pr-2">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="rounded border-slate-700 bg-slate-800 text-cyan-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                          />
                          <FileText size={15} className={isSelected ? 'text-cyan-400 shrink-0' : 'text-slate-400 shrink-0'} />
                          <div className="min-w-0">
                            <div className="font-medium truncate text-slate-200">{doc.filename}</div>
                            <div className="text-[10px] text-slate-400 flex items-center gap-1.5">
                              <span className="uppercase">{doc.source_type}</span>
                              {doc.pages && <span>• {doc.pages}p</span>}
                              <span className={doc.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'}>
                                • {doc.status}
                              </span>
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={(e) => handleDelete(doc.document_id, e)}
                          className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded transition-colors"
                          title="Delete document"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: Evidence & CRAG Inspector */}
        {activeTab === 'evidence' && (
          <div className="space-y-3">
            <div className="text-xs font-semibold text-slate-300">
              Latest Turn Evidence Inspector
            </div>

            {!latestResponse ? (
              <p className="text-xs text-slate-400 py-6 text-center">
                Submit a question to inspect retrieved context, citations, and routing rationale.
              </p>
            ) : (
              <div className="space-y-3 text-xs">
                {/* Route used badge */}
                <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">Route Executed</span>
                  <span className="font-mono font-semibold text-cyan-400">{latestResponse.route_used}</span>
                </div>

                {/* Document citations */}
                {latestResponse.document_citations && latestResponse.document_citations.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="font-medium text-emerald-400 text-[11px] uppercase tracking-wider">
                      Document Evidence Chunks ({latestResponse.document_citations.length})
                    </div>
                    {latestResponse.document_citations.map((c, i) => (
                      <div key={i} className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                        <div className="flex items-center justify-between text-[11px] text-slate-300">
                          <span className="font-semibold text-emerald-300 truncate">{c.filename}</span>
                          <span className="font-mono text-slate-400">Page {c.page_number || 1}</span>
                        </div>
                        {c.snippet && (
                          <p className="text-[11px] text-slate-400 italic line-clamp-3 bg-slate-950/60 p-1.5 rounded border border-slate-800/40">
                            "{c.snippet}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Web citations */}
                {latestResponse.web_citations && latestResponse.web_citations.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="font-medium text-sky-400 text-[11px] uppercase tracking-wider">
                      Live Web Evidence ({latestResponse.web_citations.length})
                    </div>
                    {latestResponse.web_citations.map((w, i) => (
                      <div key={i} className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-semibold text-sky-300 truncate">{w.title || 'Web Result'}</span>
                          <a 
                            href={w.url} 
                            target="_blank" 
                            rel="noreferrer" 
                            className="text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5"
                          >
                            <ExternalLink size={11} />
                          </a>
                        </div>
                        <p className="text-[10px] text-slate-400 truncate">{w.url}</p>
                        {w.snippet && (
                          <p className="text-[11px] text-slate-400 italic line-clamp-2">
                            "{w.snippet}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: Clinical Calculators */}
        {activeTab === 'calc' && (
          <div className="space-y-4 text-xs">
            {/* BMI & BSA */}
            <div className="p-3 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2.5">
              <div className="flex items-center justify-between font-semibold text-slate-200">
                <span>BMI & Body Surface Area</span>
                <span className="text-[10px] text-cyan-400 uppercase font-mono">DuBois</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Height (cm)</label>
                  <input
                    type="number"
                    value={calcHeight}
                    onChange={(e) => setCalcHeight(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Weight (kg)</label>
                  <input
                    type="number"
                    value={calcWeight}
                    onChange={(e) => setCalcWeight(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
              <div className="p-2 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-[11px]">BMI: </span>
                  <span className="font-mono font-bold text-cyan-400">{bmi || '--'} kg/m²</span>
                </div>
                <div>
                  <span className="text-slate-400 text-[11px]">BSA: </span>
                  <span className="font-mono font-bold text-indigo-400">{bsa || '--'} m²</span>
                </div>
                <button
                  onClick={() => onInsertPrompt(`Patient profile: Height ${calcHeight} cm, Weight ${calcWeight} kg, Calculated BMI: ${bmi} kg/m², BSA: ${bsa} m². `)}
                  className="p-1 text-slate-400 hover:text-cyan-400 transition-colors"
                  title="Insert to query prompt"
                >
                  <Send size={12} />
                </button>
              </div>
            </div>

            {/* Creatinine Clearance (Cockcroft-Gault) */}
            <div className="p-3 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2.5">
              <div className="flex items-center justify-between font-semibold text-slate-200">
                <span>Creatinine Clearance (CrCl)</span>
                <span className="text-[10px] text-cyan-400 uppercase font-mono">Cockcroft</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Age</label>
                  <input
                    type="number"
                    value={calcAge}
                    onChange={(e) => setCalcAge(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">SCr (mg/dL)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={calcScr}
                    onChange={(e) => setCalcScr(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Sex</label>
                  <select
                    value={calcSex}
                    onChange={(e) => setCalcSex(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-1.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
              </div>
              <div className="p-2 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-[11px]">CrCl: </span>
                  <span className="font-mono font-bold text-emerald-400">{crcl || '--'} mL/min</span>
                </div>
                <button
                  onClick={() => onInsertPrompt(`Renal function: Age ${calcAge}, SCr ${calcScr} mg/dL, CrCl: ${crcl} mL/min. `)}
                  className="p-1 text-slate-400 hover:text-cyan-400 transition-colors"
                  title="Insert to query prompt"
                >
                  <Send size={12} />
                </button>
              </div>
            </div>

            {/* Mean Arterial Pressure (MAP) */}
            <div className="p-3 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2.5">
              <div className="flex items-center justify-between font-semibold text-slate-200">
                <span>Mean Arterial Pressure (MAP)</span>
                <span className="text-[10px] text-cyan-400 uppercase font-mono">Cardio</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Systolic BP (mmHg)</label>
                  <input
                    type="number"
                    value={calcSys}
                    onChange={(e) => setCalcSys(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Diastolic BP (mmHg)</label>
                  <input
                    type="number"
                    value={calcDia}
                    onChange={(e) => setCalcDia(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
              <div className="p-2 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-[11px]">MAP: </span>
                  <span className="font-mono font-bold text-amber-400">{map || '--'} mmHg</span>
                </div>
                <button
                  onClick={() => onInsertPrompt(`Blood pressure: ${calcSys}/${calcDia} mmHg, Calculated MAP: ${map} mmHg. `)}
                  className="p-1 text-slate-400 hover:text-cyan-400 transition-colors"
                  title="Insert to query prompt"
                >
                  <Send size={12} />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: System Telemetry */}
        {activeTab === 'sys' && (
          <div className="space-y-3 text-xs">
            <div className="text-xs font-semibold text-slate-300">
              Architecture & Health State
            </div>
            <div className="space-y-2">
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">LLM Router</span>
                <span className="text-slate-200 font-mono">Groq / GPT-OSS-120B</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">Vector Store</span>
                <span className="text-slate-200 font-mono">Pinecone Hybrid (RRF)</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">Sparse Index</span>
                <span className="text-slate-200 font-mono">Lucene BM25 (Disk-Persisted)</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">Multimodal Vision</span>
                <span className="text-slate-200 font-mono">Gemini Vision / OCR Fallback</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">Web Research</span>
                <span className="text-slate-200 font-mono">Serper Provider</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                <span className="text-slate-400">Verification Engine</span>
                <span className="text-emerald-400 font-semibold">Active (Anti-Hallucination)</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
