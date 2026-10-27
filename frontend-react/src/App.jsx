import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import { RequireAuth, RedirectIfAuth } from './components/auth/ProtectedRoute';
import { useConversations } from './hooks/useConversations';

// Auth pages
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import AuthCallbackPage from './pages/AuthCallbackPage';

// Workspace components
import LandingPage from './components/LandingPage';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import ToolsPanel from './components/ToolsPanel';
import CommandMenu from './components/CommandMenu';

import {
  checkHealth,
  createSession,
  getDocuments,
  uploadDocuments,
  queryAPI,
  queryVisionAPI,
} from './api';

const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp']);
const isImageFile = (filename) => {
  const ext = (filename || '').split('.').pop().toLowerCase();
  return IMAGE_EXTENSIONS.has(ext);
};

// ─── Landing Page Route ─────────────────────────────────────────────────────
function LandingRoute() {
  const navigate = useNavigate();
  const [isConnected, setIsConnected] = useState(false);
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);

  useEffect(() => {
    checkHealth().then(setIsConnected);
    const iv = setInterval(() => checkHealth().then(setIsConnected), 20000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#070709] text-zinc-100 font-sans selection:bg-cyan-500/20 selection:text-cyan-300">
      <CommandMenu
        open={commandMenuOpen}
        onOpenChange={setCommandMenuOpen}
        onSelectMode={() => {}}
        onNewSession={() => {}}
        onOpenTools={() => {}}
        onOpenLanding={() => {}}
        onOpenWorkspace={() => navigate('/workspace')}
        currentView="landing"
      />
      <div className="flex-1 overflow-y-auto">
        <LandingPage
          onLaunchConsole={() => navigate('/workspace')}
          onSelectHeroPrompt={(p) => navigate('/workspace', { state: { initialPrompt: p } })}
          onOpenCommandMenu={() => setCommandMenuOpen(true)}
          isConnected={isConnected}
        />
      </div>
    </div>
  );
}

// ─── Workspace Layout ───────────────────────────────────────────────────────
function WorkspaceLayout({ initialPrompt }) {
  const navigate = useNavigate();
  const { getAccessToken } = useAuth();

  const [isConnected, setIsConnected] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [selectedMode, setSelectedMode] = useState('AUTO');
  const [documents, setDocuments] = useState([]);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [inputText, setInputText] = useState(initialPrompt || '');
  const [attachments, setAttachments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);
  const [latestResponse, setLatestResponse] = useState(null);

  // Conversation persistence hook
  const convHook = useConversations();
  const {
    conversations,
    activeConversationId,
    messages,
    setMessages,
    loadConversation,
    startNewConversation,
    ensureConversation,
    handleRename,
    handleDelete,
    updateConversationLastMessage,
    getToken,
  } = convHook;

  // Init connection & session
  useEffect(() => {
    async function init() {
      const ok = await checkHealth();
      setIsConnected(ok);
      try {
        const s = await createSession();
        if (s?.session_id) setSessionId(s.session_id);
      } catch (err) {
        console.warn('Could not initialize session:', err);
      }
      await refreshDocs();
    }
    init();
    const iv = setInterval(() => checkHealth().then(setIsConnected), 20000);
    return () => clearInterval(iv);
  }, []);

  const refreshDocs = async () => {
    try {
      const docs = await getDocuments();
      setDocuments(docs || []);
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
      if (s?.session_id) setSessionId(s.session_id);
    } catch (err) {
      console.error('Failed to create new session:', err);
    }
    startNewConversation();
    setSelectedDocIds([]);
    setLatestResponse(null);
  };

  const handleClearChat = () => {
    setMessages([]);
    setLatestResponse(null);
  };

  const handleSendMessage = async (text, files = []) => {
    const images = files.filter(f => isImageFile(f.name));
    const docs = files.filter(f => !isImageFile(f.name));

    const userMsg = {
      role: 'user',
      content: text || (images.length > 0 ? `Inspect image: ${images.map(i => i.name).join(', ')}` : ''),
      attachments: files.map(f => ({ name: f.name, size: f.size })),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      if (docs.length > 0) {
        await uploadDocuments(docs, sessionId);
        await refreshDocs();
      }

      // Ensure a persistent conversation exists for authenticated users
      const token = await getAccessToken();
      const convId = token ? await ensureConversation(text) : null;

      let data;
      if (images.length > 0 && (selectedMode === 'VISION' || !text)) {
        data = await queryVisionAPI(images[0], text);
      } else {
        data = await queryAPI({
          question: text || 'Please summarize the uploaded document.',
          sessionId,
          documentIds: selectedDocIds,
          mode: selectedMode,
          conversationId: convId,
          accessToken: token,
        });
      }

      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id);
      }

      setLatestResponse(data);

      const assistantMsg = {
        role: 'assistant',
        content: data.answer || 'No response returned.',
        route_used: data.route_used || selectedMode,
        document_citations: data.document_citations || [],
        web_citations: data.web_citations || [],
        verification: data.verification || null,
        routing: data.routing || null,
        warnings: data.warnings || [],
      };

      setMessages(prev => [...prev, assistantMsg]);

      if (convId) {
        updateConversationLastMessage(convId);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `**System Notice:** Could not complete the request (${err.message}). Check backend status and try again.`,
        route_used: 'GENERAL_LLM',
        document_citations: [],
        web_citations: [],
        verification: null,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPreset = (prompt) => setInputText(prompt);
  const handleInsertPrompt = (snippet) => setInputText(prev => prev ? `${prev} ${snippet}` : snippet);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#070709] text-zinc-100 font-sans selection:bg-cyan-500/20 selection:text-cyan-300">
      <CommandMenu
        open={commandMenuOpen}
        onOpenChange={setCommandMenuOpen}
        onSelectMode={setSelectedMode}
        onNewSession={handleNewSession}
        onOpenTools={() => setToolsOpen(true)}
        onOpenLanding={() => navigate('/')}
        onOpenWorkspace={() => {}}
        currentView="workspace"
      />

      <Header
        isConnected={isConnected}
        selectedMode={selectedMode}
        onSelectMode={setSelectedMode}
        documentCount={documents.length}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        toolsOpen={toolsOpen}
        setToolsOpen={setToolsOpen}
        onBackToLanding={() => navigate('/')}
        onOpenCommandMenu={() => setCommandMenuOpen(true)}
        sessionId={sessionId}
      />

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
          onSelectPreset={handleSelectPreset}
          // Conversation persistence props
          conversations={conversations}
          activeConversationId={activeConversationId}
          onLoadConversation={loadConversation}
          onRenameConversation={handleRename}
          onDeleteConversation={handleDelete}
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

// ─── Workspace Route (reads location state for initial prompt) ──────────────
function WorkspaceRoute() {
  const location = useLocation();
  return <WorkspaceLayout initialPrompt={location.state?.initialPrompt} />;
}

// ─── Root App with Router ───────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public landing */}
        <Route path="/" element={<LandingRoute />} />

        {/* Auth pages — redirect away if already logged in */}
        <Route path="/login" element={<RedirectIfAuth><LoginPage /></RedirectIfAuth>} />
        <Route path="/signup" element={<RedirectIfAuth><SignupPage /></RedirectIfAuth>} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />

        {/* Protected workspace */}
        <Route
          path="/workspace"
          element={
            <RequireAuth>
              <WorkspaceRoute />
            </RequireAuth>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
