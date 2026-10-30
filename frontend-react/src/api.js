const API_BASE = (function() {
  if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
    return import.meta.env.VITE_DEV_API_URL || 'http://localhost:8000';
  }
  return import.meta.env.VITE_API_URL || 'https://nexora-ai-2-foxj.onrender.com';
})();

// ============================================================
// Base helpers
// ============================================================

async function apiFetch(path, options = {}, accessToken = null) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || data.detail || `HTTP ${res.status}`), { status: res.status });
  return data;
}

// ============================================================
// Health & Session (public — no auth needed)
// ============================================================

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
    return res.ok;
  } catch { return false; }
}

export async function createSession() {
  const res = await fetch(`${API_BASE}/conversation/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

// ============================================================
// Documents (legacy — no auth, backward compat)
// ============================================================

export async function getDocuments(accessToken = null) {
  const headers = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  const res = await fetch(`${API_BASE}/documents`, { headers });
  if (!res.ok) throw new Error('Failed to fetch documents');
  const data = await res.json();
  return data.documents || [];
}

export async function uploadDocuments(files, sessionId = null, accessToken = null, conversationId = null) {
  const formData = new FormData();
  for (const file of files) formData.append('files', file);
  if (sessionId) formData.append('session_id', sessionId);
  if (conversationId) formData.append('conversation_id', conversationId);
  const headers = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}/documents/upload`, { method: 'POST', body: formData, headers });
  const data = await res.json().catch(() => ({ documents: [] }));
  return { status: res.status, documents: data.documents || [] };
}

export async function deleteDocument(documentId, accessToken = null) {
  const headers = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
  const res = await fetch(`${API_BASE}/documents/${documentId}`, { method: 'DELETE', headers });
  return res.ok;
}

// ============================================================
// Query (supports optional auth for persistence)
// ============================================================

export async function queryAPI({ question, sessionId, documentIds, mode = 'AUTO', conversationId = null, accessToken = null }) {
  const payload = {
    question,
    session_id: sessionId || null,
    document_ids: documentIds?.length > 0 ? documentIds : null,
    mode: mode || 'AUTO',
    conversation_id: conversationId || null,
  };

  const headers = { 'Content-Type': 'application/json' };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`API error (${res.status}): ${errText.slice(0, 160)}`);
  }
  return res.json();
}

export async function queryVisionAPI(imageFile, question, accessToken = null) {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('question', question || 'Describe this image and analyze its key visual and textual details.');
  const headers = {};
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  const res = await fetch(`${API_BASE}/vision/query`, { method: 'POST', body: formData, headers });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Vision API error (${res.status}): ${errText.slice(0, 160)}`);
  }
  return res.json();
}

// ============================================================
// Auth API (thin wrappers — most auth is done via Supabase SDK)
// ============================================================

export async function getMe(accessToken) {
  return apiFetch('/auth/me', { method: 'GET' }, accessToken);
}

// ============================================================
// Conversations API (requires auth)
// ============================================================

export async function getConversations(accessToken) {
  return apiFetch('/conversations', { method: 'GET' }, accessToken);
}

export async function createConversation(title, accessToken) {
  return apiFetch('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  }, accessToken);
}

export async function getConversation(conversationId, accessToken) {
  return apiFetch(`/conversations/${conversationId}`, { method: 'GET' }, accessToken);
}

export async function renameConversation(conversationId, title, accessToken) {
  return apiFetch(`/conversations/${conversationId}`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  }, accessToken);
}

export async function deleteConversation(conversationId, accessToken) {
  return apiFetch(`/conversations/${conversationId}`, { method: 'DELETE' }, accessToken);
}

export async function getMessages(conversationId, accessToken, offset = 0, limit = 50) {
  return apiFetch(`/conversations/${conversationId}/messages?offset=${offset}&limit=${limit}`, { method: 'GET' }, accessToken);
}
