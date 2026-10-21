import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import ToolsPanel from './components/ToolsPanel';
import { 
  checkHealth, 
  createSession, 
  getDocuments, 
  uploadDocuments, 
  queryAPI, 
  queryVisionAPI 
} from './api';

const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp']);
const isImageFile = (filename) => {
  const ext = (filename || '').split('.').pop().toLowerCase();
  return IMAGE_EXTENSIONS.has(ext);
};

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [selectedMode, setSelectedMode] = useState('AUTO');
  const [documents, setDocuments] = useState([]);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [latestResponse, setLatestResponse] = useState(null);

  // Initialize connection and session
  useEffect(() => {
    async function init() {
      const ok = await checkHealth();
      setIsConnected(ok);

      try {
        const s = await createSession();
        if (s && s.session_id) {
          setSessionId(s.session_id);
        }
      } catch (err) {
        console.warn('Could not initialize session:', err);
      }

      await refreshDocs();
    }
    init();

    // Health poll every 20 seconds
    const interval = setInterval(async () => {
      const ok = await checkHealth();
      setIsConnected(ok);
    }, 20000);
    return () => clearInterval(interval);
  }, []);

  const refreshDocs = async () => {
    try {
      const docs = await getDocuments();
      setDocuments(docs);
    } catch (err) {
      console.warn('Failed to fetch documents:', err);
    }
  };

  const handleToggleDocScope = (docId) => {
    setSelectedDocIds(prev => 
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    );
  };

  const handleNewSession = async () => {
    try {
      const s = await createSession();
      if (s && s.session_id) {
        setSessionId(s.session_id);
      }
      setMessages([]);
      setSelectedDocIds([]);
      setLatestResponse(null);
    } catch (err) {
      console.error('Failed to create new session:', err);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setLatestResponse(null);
  };

  const handleSendMessage = async (text, files = []) => {
    // 1. Separate image files and document files
    const images = files.filter(f => isImageFile(f.name));
    const docs = files.filter(f => !isImageFile(f.name));

    // Append user message immediately
    const userMsg = {
      role: 'user',
      content: text || (images.length > 0 ? `Inspect image: ${images.map(img => img.name).join(', ')}` : ''),
      attachments: files.map(f => ({ name: f.name, size: f.size })),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // 2. If documents are attached, ingest them first
      if (docs.length > 0) {
        await uploadDocuments(docs, sessionId);
        await refreshDocs();
      }

      let data;
      // 3. Direct vision query if mode is VISION or image provided without other docs
      if (images.length > 0 && (selectedMode === 'VISION' || !text)) {
        data = await queryVisionAPI(images[0], text);
      } else {
        // Standard Orchestrated / CRAG Query
        data = await queryAPI({
          question: text || 'Please summarize the uploaded files.',
          sessionId,
          documentIds: selectedDocIds,
          mode: selectedMode,
        });
      }

      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
      }

      setLatestResponse(data);

      const assistantMsg = {
        role: 'assistant',
        content: data.answer || 'No answer returned.',
        route_used: data.route_used || selectedMode,
        document_citations: data.document_citations || [],
        web_citations: data.web_citations || [],
        verification: data.verification || null,
        routing: data.routing || null,
        warnings: data.warnings || [],
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        content: `**Clinical Request Notice:** Could not complete the request (${err.message}). Check that the backend server is running and try again.`,
        route_used: 'GENERAL_LLM',
        document_citations: [],
        web_citations: [],
        verification: null,
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInsertPrompt = (snippet) => {
    setInputText(prev => (prev ? `${prev} ${snippet}` : snippet));
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      {/* Top Header */}
      <Header
        isConnected={isConnected}
        selectedMode={selectedMode}
        onSelectMode={setSelectedMode}
        documentCount={documents.length}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        toolsOpen={toolsOpen}
        setToolsOpen={setToolsOpen}
      />

      {/* Main Workspace: Sidebar + ChatArea + ToolsPanel */}
      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          selectedMode={selectedMode}
          onSelectMode={setSelectedMode}
          onNewSession={handleNewSession}
          sessionId={sessionId}
          onClearChat={handleClearChat}
          messageCount={messages.length}
        />

        <ChatArea
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          inputText={inputText}
          setInputText={setInputText}
          attachments={attachments}
          setAttachments={setAttachments}
        />

        <ToolsPanel
          isOpen={toolsOpen}
          onClose={() => setToolsOpen(false)}
          documents={documents}
          onRefreshDocs={refreshDocs}
          selectedDocIds={selectedDocIds}
          onToggleDocScope={handleToggleDocScope}
          latestResponse={latestResponse}
          onInsertPrompt={handleInsertPrompt}
          sessionId={sessionId}
        />
      </div>
    </div>
  );
}
