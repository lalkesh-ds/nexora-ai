import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  getConversations,
  createConversation,
  renameConversation,
  deleteConversation,
  getMessages,
} from '@/api';

/**
 * Hook that manages the persistent conversation list and active conversation.
 * Falls back gracefully when user is not authenticated (unauthenticated session mode).
 */
export function useConversations() {
  const { user, getAccessToken } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const tokenRef = useRef(null);

  // Fetch token helper
  const getToken = useCallback(async () => {
    if (tokenRef.current) return tokenRef.current;
    const t = await getAccessToken();
    tokenRef.current = t;
    return t;
  }, [getAccessToken]);

  // Clear token when user changes
  useEffect(() => {
    tokenRef.current = null;
  }, [user?.id]);

  // Load conversation list on mount / when user changes
  const refreshConversations = useCallback(async () => {
    if (!user) return;
    try {
      const token = await getToken();
      if (!token) return;
      const data = await getConversations(token);
      setConversations(data.conversations || []);
    } catch (err) {
      console.warn('[Conversations] Failed to load conversations:', err.message);
    }
  }, [user, getToken]);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  // Load messages for a conversation
  const loadConversation = useCallback(async (conversationId) => {
    if (!user || !conversationId) return;
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const data = await getMessages(conversationId, token);
      const msgs = (data.messages || []).map(m => ({
        role: m.role,
        content: m.content,
        document_citations: m.citations?.document_citations || [],
        web_citations: m.citations?.web_citations || [],
        verification: m.metadata?.verification || null,
        routing: m.metadata?.routing || null,
        warnings: m.metadata?.warnings || [],
        route_used: m.metadata?.route_used || 'GENERAL_LLM',
      }));
      setMessages(msgs);
      setActiveConversationId(conversationId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [user, getToken]);

  // Start a new conversation (client-side; server-side created on first message)
  const startNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
  }, []);

  // Create conversation on backend and return the id
  const ensureConversation = useCallback(async (firstMessage) => {
    if (activeConversationId) return activeConversationId;
    if (!user) return null;
    try {
      const token = await getToken();
      const title = firstMessage.slice(0, 60).trim() || 'New Chat';
      const data = await createConversation(title, token);
      const conv = data.conversation;
      setActiveConversationId(conv.id);
      setConversations(prev => [conv, ...prev]);
      return conv.id;
    } catch (err) {
      console.warn('[Conversations] Failed to create conversation:', err.message);
      return null;
    }
  }, [activeConversationId, user, getToken]);

  const handleRename = useCallback(async (conversationId, newTitle) => {
    if (!user) return;
    try {
      const token = await getToken();
      await renameConversation(conversationId, newTitle, token);
      setConversations(prev =>
        prev.map(c => c.id === conversationId ? { ...c, title: newTitle } : c)
      );
    } catch (err) {
      console.warn('[Conversations] Rename failed:', err.message);
    }
  }, [user, getToken]);

  const handleDelete = useCallback(async (conversationId) => {
    if (!user) return;
    try {
      const token = await getToken();
      await deleteConversation(conversationId, token);
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      if (activeConversationId === conversationId) {
        startNewConversation();
      }
    } catch (err) {
      console.warn('[Conversations] Delete failed:', err.message);
    }
  }, [user, activeConversationId, startNewConversation, getToken]);

  // Update local conversation after receiving an assistant response
  const updateConversationLastMessage = useCallback((conversationId) => {
    setConversations(prev =>
      prev.map(c =>
        c.id === conversationId
          ? { ...c, last_message_at: new Date().toISOString() }
          : c
      ).sort((a, b) => {
        const tA = a.last_message_at || a.created_at;
        const tB = b.last_message_at || b.created_at;
        return new Date(tB) - new Date(tA);
      })
    );
  }, []);

  return {
    conversations,
    activeConversationId,
    messages,
    setMessages,
    loading,
    error,
    refreshConversations,
    loadConversation,
    startNewConversation,
    ensureConversation,
    handleRename,
    handleDelete,
    updateConversationLastMessage,
    getToken,
  };
}
