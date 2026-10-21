const API_BASE = import.meta.env.VITE_API_URL || 'https://nexora-ai-2-foxj.onrender.com';

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
    return res.ok;
  } catch {
    return false;
  }
}

export async function createSession() {
  const res = await fetch(`${API_BASE}/conversation/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

export async function getDocuments() {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  const data = await res.json();
  return data.documents || [];
}

export async function uploadDocuments(files, sessionId = null) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  if (sessionId) {
    formData.append('session_id', sessionId);
  }

  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  // Handle 200 (all ok), 207 (partial multi-status), and 422 (failure details)
  const data = await res.json().catch(() => ({ documents: [] }));
  return {
    status: res.status,
    documents: data.documents || [],
  };
}

export async function deleteDocument(documentId) {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, {
    method: 'DELETE',
  });
  return res.ok;
}

export async function queryAPI({ question, sessionId, documentIds, mode = 'AUTO' }) {
  const payload = {
    question,
    session_id: sessionId || null,
    document_ids: documentIds && documentIds.length > 0 ? documentIds : null,
    mode: mode || 'AUTO',
  };

  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`API error (${res.status}): ${errText.slice(0, 160)}`);
  }

  return res.json();
}

export async function queryVisionAPI(imageFile, question) {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('question', question || 'Describe this image and analyze its key visual and textual details.');

  const res = await fetch(`${API_BASE}/vision/query`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Vision API error (${res.status}): ${errText.slice(0, 160)}`);
  }

  return res.json();
}
