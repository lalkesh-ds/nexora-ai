import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
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
  Cpu,
  ShieldCheck,
  Activity,
  FileCheck,
  Check
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
  const [activeTab, setActiveTab] = useState('docs');
  const [uploading, setUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState([]);
  const [dragOver, setDragOver] = useState(false);

  // Clinical Calculator states
  const [calcHeight, setCalcHeight] = useState('175');
  const [calcWeight, setCalcWeight] = useState('70');
  const [calcAge, setCalcAge] = useState('45');
  const [calcScr, setCalcScr] = useState('1.1');
  const [calcSex, setCalcSex] = useState('male');
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
      const issues = (res.documents || [])
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
    if (!confirm('Remove this document from knowledge base?')) return;
    await deleteDocument(docId);
    await onRefreshDocs();
  };

  return (
    <aside className="w-80 md:w-96 border-l border-zinc-800/80 bg-zinc-950 flex flex-col h-full shrink-0 z-20 select-none">
      {/* Titlebar */}
      <div className="h-14 px-4 border-b border-zinc-800/80 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span className="font-medium text-xs text-white">Document Corpus & Telemetry</span>
        </div>
        <button 
          onClick={onClose} 
          className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-900 rounded-md transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Segmented Navigation */}
      <div className="p-2 border-b border-zinc-800/80 bg-zinc-900/30">
        <div className="grid grid-cols-4 gap-1 bg-zinc-900/80 p-1 rounded-md border border-zinc-800">
          <button
            onClick={() => setActiveTab('docs')}
            className={`py-1 rounded text-[11px] font-medium transition-colors ${
              activeTab === 'docs' 
                ? 'bg-zinc-800 text-white font-semibold' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Corpus
          </button>
          <button
            onClick={() => setActiveTab('evidence')}
            className={`py-1 rounded text-[11px] font-medium transition-colors ${
              activeTab === 'evidence' 
                ? 'bg-zinc-800 text-white font-semibold' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Evidence
          </button>
          <button
            onClick={() => setActiveTab('calc')}
            className={`py-1 rounded text-[11px] font-medium transition-colors ${
              activeTab === 'calc' 
                ? 'bg-zinc-800 text-white font-semibold' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Calculators
          </button>
          <button
            onClick={() => setActiveTab('sys')}
            className={`py-1 rounded text-[11px] font-medium transition-colors ${
              activeTab === 'sys' 
                ? 'bg-zinc-800 text-white font-semibold' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            System
          </button>
        </div>
      </div>

      {/* Tab Contents */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* TAB 1: Documents & Knowledge Base */}
        {activeTab === 'docs' && (
          <div className="space-y-4">
            {/* Upload Zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                handleFileUpload(e.dataTransfer.files);
              }}
              className={`border border-dashed rounded-lg p-5 text-center transition-all cursor-pointer ${
                dragOver 
                  ? 'border-cyan-400 bg-cyan-950/20' 
                  : 'border-zinc-800 hover:border-zinc-700 bg-zinc-900/30'
              }`}
            >
              <input
                type="file"
                multiple
                id="panel-file-upload"
                className="hidden"
                onChange={(e) => handleFileUpload(e.target.files)}
                accept=".pdf,.docx,.txt,.csv,.xlsx,.jpg,.jpeg,.png,.webp"
              />
              <label htmlFor="panel-file-upload" className="cursor-pointer space-y-2 block">
                <div className="w-8 h-8 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto text-cyan-400">
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                </div>
                <div className="text-xs font-medium text-zinc-200">
                  {uploading ? 'Parsing & Indexing Vectors...' : 'Upload Documents & Files'}
                </div>
                <p className="text-[10px] text-zinc-400 font-mono">
                  PDF, DOCX, TXT, CSV, XLSX, Images
                </p>
              </label>
            </div>

            {uploadErrors.length > 0 && (
              <div className="p-2.5 rounded-md bg-red-950/30 border border-red-900/50 text-[11px] text-red-300 space-y-1">
                <div className="font-semibold flex items-center gap-1 text-red-400">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Upload Notice</span>
                </div>
                {uploadErrors.map((err, i) => (
                  <p key={i} className="truncate">{err}</p>
                ))}
              </div>
            )}

            {/* Document Collection List */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-zinc-300">Indexed Corpus</span>
                <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono">
                  {documents.length} docs
                </Badge>
              </div>

              {documents.length === 0 ? (
                <div className="text-center py-8 text-zinc-400 text-xs">
                  No documents uploaded yet.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {documents.map((doc) => {
                    const isSelected = selectedDocIds.includes(doc.document_id);
                    return (
                      <div
                        key={doc.document_id}
                        onClick={() => onToggleDocScope(doc.document_id)}
                        className={`p-2.5 rounded-md border text-xs transition-colors flex items-center justify-between cursor-pointer ${
                          isSelected 
                            ? 'bg-zinc-900 border-cyan-500/40 text-white' 
                            : 'bg-zinc-900/40 border-zinc-800/80 hover:bg-zinc-900 text-zinc-300'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 pr-2">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="rounded border-zinc-700 bg-zinc-800 text-cyan-400 focus:ring-0 cursor-pointer"
                          />
                          <FileText className={`w-3.5 h-3.5 shrink-0 ${isSelected ? 'text-cyan-400' : 'text-zinc-400'}`} />
                          <div className="min-w-0">
                            <div className="font-medium truncate text-zinc-200">{doc.filename}</div>
                            <div className="text-[10px] text-zinc-400 font-mono flex items-center gap-1.5">
                              <span>{doc.source_type}</span>
                              {doc.pages && <span>• {doc.pages}p</span>}
                              <span className={doc.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'}>
                                • {doc.status}
                              </span>
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={(e) => handleDelete(doc.document_id, e)}
                          className="p-1 text-zinc-400 hover:text-red-400 transition-colors"
                          title="Remove document"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: Evidence & Citations */}
        {activeTab === 'evidence' && (
          <div className="space-y-3">
            <div className="text-xs font-semibold text-zinc-300">
              Turn Evidence Inspector
            </div>

            {!latestResponse ? (
              <p className="text-xs text-zinc-400 py-8 text-center font-mono">
                Submit a query to inspect live retrieved chunks and citations.
              </p>
            ) : (
              <div className="space-y-3 text-xs">
                <div className="p-2.5 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-between font-mono">
                  <span className="text-zinc-400">Route Executed</span>
                  <Badge variant="cyan" className="text-[10px] py-0 px-2">
                    {latestResponse.route_used}
                  </Badge>
                </div>

                {latestResponse.document_citations && latestResponse.document_citations.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="font-mono text-[10px] uppercase text-emerald-400 font-semibold">
                      Document Chunks ({latestResponse.document_citations.length})
                    </div>
                    {latestResponse.document_citations.map((c, i) => (
                      <div key={i} className="p-2.5 rounded-md bg-zinc-900/60 border border-zinc-800 space-y-1">
                        <div className="flex items-center justify-between text-[11px] font-mono">
                          <span className="font-semibold text-emerald-400 truncate">{c.filename}</span>
                          <span className="text-zinc-400">p. {c.page_number || 1}</span>
                        </div>
                        {c.snippet && (
                          <p className="text-[11px] text-zinc-300 italic bg-zinc-950 p-2 rounded border border-zinc-850">
                            "{c.snippet}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {latestResponse.web_citations && latestResponse.web_citations.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="font-mono text-[10px] uppercase text-cyan-400 font-semibold">
                      Live Web Sources ({latestResponse.web_citations.length})
                    </div>
                    {latestResponse.web_citations.map((w, i) => (
                      <div key={i} className="p-2.5 rounded-md bg-zinc-900/60 border border-zinc-800 space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-medium text-cyan-300 truncate">{w.title || 'Web Result'}</span>
                          <a 
                            href={w.url} 
                            target="_blank" 
                            rel="noreferrer" 
                            className="text-zinc-400 hover:text-white"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <p className="text-[10px] font-mono text-zinc-400 truncate">{w.url}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: Calculators */}
        {activeTab === 'calc' && (
          <div className="space-y-4 text-xs">
            {/* BMI & BSA */}
            <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <div className="flex items-center justify-between font-medium text-zinc-200">
                <span>BMI & Body Surface Area</span>
                <span className="text-[10px] font-mono text-cyan-400">DuBois</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">Height (cm)</label>
                  <Input
                    type="number"
                    value={calcHeight}
                    onChange={(e) => setCalcHeight(e.target.value)}
                    className="h-7 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">Weight (kg)</label>
                  <Input
                    type="number"
                    value={calcWeight}
                    onChange={(e) => setCalcWeight(e.target.value)}
                    className="h-7 text-xs font-mono"
                  />
                </div>
              </div>
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800 flex items-center justify-between font-mono">
                <div>
                  <span className="text-zinc-400 text-[10px]">BMI: </span>
                  <span className="font-bold text-cyan-400">{bmi || '--'} kg/m²</span>
                </div>
                <div>
                  <span className="text-zinc-400 text-[10px]">BSA: </span>
                  <span className="font-bold text-zinc-200">{bsa || '--'} m²</span>
                </div>
                <button
                  onClick={() => onInsertPrompt(`Patient profile: Height ${calcHeight} cm, Weight ${calcWeight} kg, Calculated BMI: ${bmi} kg/m², BSA: ${bsa} m². `)}
                  className="p-1 text-zinc-400 hover:text-cyan-400"
                  title="Insert to query prompt"
                >
                  <Send className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Creatinine Clearance (Cockcroft-Gault) */}
            <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <div className="flex items-center justify-between font-medium text-zinc-200">
                <span>Creatinine Clearance (CrCl)</span>
                <span className="text-[10px] font-mono text-emerald-400">Cockcroft</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">Age</label>
                  <Input
                    type="number"
                    value={calcAge}
                    onChange={(e) => setCalcAge(e.target.value)}
                    className="h-7 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">SCr (mg/dL)</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={calcScr}
                    onChange={(e) => setCalcScr(e.target.value)}
                    className="h-7 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">Sex</label>
                  <select
                    value={calcSex}
                    onChange={(e) => setCalcSex(e.target.value)}
                    className="w-full h-7 bg-zinc-950 border border-zinc-800 rounded px-1.5 text-xs text-zinc-200 focus:outline-none"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
              </div>
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800 flex items-center justify-between font-mono">
                <div>
                  <span className="text-zinc-400 text-[10px]">CrCl: </span>
                  <span className="font-bold text-emerald-400">{crcl || '--'} mL/min</span>
                </div>
                <button
                  onClick={() => onInsertPrompt(`Renal function: Age ${calcAge}, SCr ${calcScr} mg/dL, CrCl: ${crcl} mL/min. `)}
                  className="p-1 text-zinc-400 hover:text-cyan-400"
                  title="Insert to query prompt"
                >
                  <Send className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* MAP */}
            <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <div className="flex items-center justify-between font-medium text-zinc-200">
                <span>Mean Arterial Pressure (MAP)</span>
                <span className="text-[10px] font-mono text-cyan-400">Cardio</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">Systolic BP</label>
                  <Input
                    type="number"
                    value={calcSys}
                    onChange={(e) => setCalcSys(e.target.value)}
                    className="h-7 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-400 block mb-1">Diastolic BP</label>
                  <Input
                    type="number"
                    value={calcDia}
                    onChange={(e) => setCalcDia(e.target.value)}
                    className="h-7 text-xs font-mono"
                  />
                </div>
              </div>
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800 flex items-center justify-between font-mono">
                <div>
                  <span className="text-zinc-400 text-[10px]">MAP: </span>
                  <span className="font-bold text-cyan-400">{map || '--'} mmHg</span>
                </div>
                <button
                  onClick={() => onInsertPrompt(`Blood pressure: ${calcSys}/${calcDia} mmHg, Calculated MAP: ${map} mmHg. `)}
                  className="p-1 text-zinc-400 hover:text-cyan-400"
                  title="Insert to query prompt"
                >
                  <Send className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: System Specs */}
        {activeTab === 'sys' && (
          <div className="space-y-2 text-xs font-mono">
            <div className="text-xs font-semibold text-zinc-300 font-sans mb-3">
              Telemetry & Engine State
            </div>
            <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800 flex items-center justify-between">
              <span className="text-zinc-400">Orchestrator</span>
              <span className="text-zinc-200">Corrective RAG (CRAG)</span>
            </div>
            <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800 flex items-center justify-between">
              <span className="text-zinc-400">Dense Index</span>
              <span className="text-zinc-200">Pinecone RRF Fusion</span>
            </div>
            <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800 flex items-center justify-between">
              <span className="text-zinc-400">Sparse Lexical</span>
              <span className="text-zinc-200">BM25 Token Inverted</span>
            </div>
            <div className="p-2.5 rounded bg-zinc-900/60 border border-zinc-800 flex items-center justify-between">
              <span className="text-zinc-400">Safety Guard</span>
              <span className="text-emerald-400">Sentence NLI Active</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
