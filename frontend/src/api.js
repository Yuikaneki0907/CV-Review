import axios from 'axios';
import logger from './logger';

export const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
});

// ── Request interceptor: inject JWT + log ────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Attach timing metadata
  config.metadata = { startTime: performance.now() };
  logger.debug(`▶ ${config.method?.toUpperCase()} ${config.url}`);

  return config;
});

// ── Response interceptor: log success ────────────────────────────
api.interceptors.response.use(
  (response) => {
    const duration = Math.round(performance.now() - (response.config.metadata?.startTime || 0));
    logger.info(
      `◀ ${response.config.method?.toUpperCase()} ${response.config.url} → ${response.status} (${duration}ms)`
    );
    return response;
  },
  (error) => {
    const config = error.config || {};
    const duration = Math.round(performance.now() - (config.metadata?.startTime || 0));
    const status = error.response?.status || 'NETWORK_ERROR';
    const detail = error.response?.data?.detail || error.message;

    logger.error(
      `✖ ${config.method?.toUpperCase()} ${config.url} → ${status} (${duration}ms) — ${detail}`
    );

    return Promise.reject(error);
  }
);

// Auth
export const register = (data) => api.post('/auth/register', data);
export const login = (data) => api.post('/auth/login', data);
export const forgotPassword = (data) => api.post('/auth/forgot-password', data);
export const resetPassword = (data) => api.post('/auth/reset-password', data);
export const getCurrentUserProfile = () => api.get('/auth/me');
export const updateCurrentUserProfile = (data) => api.put('/auth/me', data);

// Analysis
export const createAnalysis = (formData) =>
  api.post('/analysis/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const listAnalyses = (limit = 20, offset = 0) =>
  api.get(`/analysis/?limit=${limit}&offset=${offset}`);

export const getAnalysis = (id) => api.get(`/analysis/${id}`);

export const createAnalysisFromGeneratedCV = (id, jdText, jdFile = null) => {
  if (jdFile) {
    const formData = new FormData();
    formData.append('jd_file', jdFile);
    formData.append('jd_text', jdText || '');
    return api.post(`/analysis/from-generated-cv/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }
  return api.post(`/analysis/from-generated-cv/${id}`, { jd_text: jdText });
};

export const deleteAnalysis = (id) => api.delete(`/analysis/${id}`);

// Generated CV
export const createGeneratedCV = (data) => api.post('/generated-cvs/', data);

// Phase 3: generate-and-improve. One-shot — waits for the full loop to
// finish server-side before returning the persisted CV.
export const improveGeneratedCV = (data) =>
  api.post('/generated-cvs/', { ...data, improve: true });

// Phase 3 streaming: SSE per-iteration progress. ``onEvent`` receives
// ``{event, data}`` objects matching the backend events:
//   loop_start | iteration_done | loop_done | loop_error
export const streamImproveGeneratedCV = async (data, onEvent) => {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}/generated-cvs/improve/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ ...data, improve: true }),
  });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `HTTP Error: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let eventText = '';
      let dataText = '';
      for (const line of chunk.split('\n')) {
        if (line.startsWith('event:')) eventText = line.substring(6).trim();
        else if (line.startsWith('data:')) dataText = line.substring(5).trim();
      }
      if (eventText && dataText) {
        let parsed = dataText;
        try { parsed = JSON.parse(dataText); } catch { /* leave as string */ }
        onEvent({ event: eventText, data: parsed });
      }
      boundary = buffer.indexOf('\n\n');
    }
  }
};
export const importGeneratedCV = (formData) =>
  api.post('/generated-cvs/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
export const importGeneratedCVVersion = (id, cvFile) => {
  const formData = new FormData();
  formData.append('cv_file', cvFile);
  return api.post(`/generated-cvs/${id}/import-version`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const listGeneratedCVs = (limit = 20, offset = 0) => api.get(`/generated-cvs/?limit=${limit}&offset=${offset}`);
export const getGeneratedCV = (id) => api.get(`/generated-cvs/${id}`);
export const getGeneratedCVVersions = (id) => api.get(`/generated-cvs/${id}/versions`);
export const deleteGeneratedCV = (id) => api.delete(`/generated-cvs/${id}`);
export const createGeneratedCVVersion = (id, data) => api.post(`/generated-cvs/${id}/versions`, data);
export const updateGeneratedCV = (id, data) => api.patch(`/generated-cvs/${id}`, data);
export const chatCVGeneration = (messages, outputFormat = 'markdown', templateId = null, currentCvId = null, conversationId = null) =>
  api.post('/generated-cvs/chat', {
    messages,
    output_format: outputFormat,
    ...(templateId && { template_id: templateId }),
    ...(currentCvId && { current_cv_id: currentCvId }),
    ...(conversationId && { conversation_id: conversationId }),
  });
export const createChatSession = () => api.post('/generated-cvs/chat-sessions');
export const listChatSessions = (limit = 50, offset = 0) =>
  api.get(`/generated-cvs/chat-sessions?limit=${limit}&offset=${offset}`);
export const getChatSession = (conversationId) =>
  api.get(`/generated-cvs/chat-sessions/${conversationId}`);
export const getLatestConversationCV = (conversationId) =>
  api.get(`/generated-cvs/chat-sessions/${conversationId}/latest-cv`);
export const deleteChatSession = (conversationId) =>
  api.delete(`/generated-cvs/chat-sessions/${conversationId}`);
export const updateChatSessionMessages = (conversationId, messages) =>
  api.put(`/generated-cvs/chat-sessions/${conversationId}/messages`, { messages });
export const downloadGeneratedCV = (id, format = 'markdown') =>
  api.get(`/generated-cvs/${id}/download`, {
    params: { format },
    responseType: 'blob',
  });
export const exportPreviewDocx = (content, title = '') =>
  api.post(
    '/generated-cvs/export-preview-docx',
    { content, title },
    { responseType: 'blob' }
  );
export const exportGeneratedCV = downloadGeneratedCV;

export const streamChatCVGeneration = async (
  messages,
  outputFormat = 'markdown',
  onEvent,
  templateId = null,
  currentCvId = null,
  conversationId = null
) => {
  const controller = new AbortController();
  const STREAM_IDLE_TIMEOUT_MS = 60000;
  let idleTimer = null;
  const resetIdleTimer = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      controller.abort();
    }, STREAM_IDLE_TIMEOUT_MS);
  };

  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}/generated-cvs/chat/stream`, {
    method: 'POST',
    headers,
    signal: controller.signal,
    body: JSON.stringify({
      messages,
      output_format: outputFormat,
      ...(templateId && { template_id: templateId }),
      ...(currentCvId && { current_cv_id: currentCvId }),
      ...(conversationId && { conversation_id: conversationId }),
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP Error: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    resetIdleTimer();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      resetIdleTimer();

      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const chunk = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        const lines = chunk.split('\n');
        let eventText = '';
        let dataText = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventText = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            dataText = line.substring(5).trim();
          }
        }

        if (eventText && dataText) {
          let parsedData = dataText;
          try {
            parsedData = JSON.parse(dataText);
          } catch {
            // fallback to raw text
          }
          onEvent({ event: eventText, data: parsedData });
        }

        boundary = buffer.indexOf('\n\n');
      }
    }
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('Kết nối tới AI bị gián đoạn do không có phản hồi trong 60 giây. Vui lòng thử lại.');
    }
    throw error;
  } finally {
    if (idleTimer) clearTimeout(idleTimer);
  }
};

/**
 * Stream CV analysis via SSE — sends CV file + JD text as multipart form,
 * receives analysis pipeline progress and results.
 */
export const streamChatAnalysis = async (cvFile, jdText, jdFile, onEvent) => {
  const token = localStorage.getItem('token');
  const formData = new FormData();
  formData.append('cv_file', cvFile);
  if (jdFile) {
    formData.append('jd_file', jdFile);
  }
  formData.append('jd_text', jdText || '');

  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}/analysis/chat-analyze/stream`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `HTTP Error: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const lines = chunk.split('\n');
      let eventText = '';
      let dataText = '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventText = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          dataText = line.substring(5).trim();
        }
      }

      if (eventText && dataText) {
        let parsedData = dataText;
        try {
          parsedData = JSON.parse(dataText);
        } catch {
          // fallback to raw text
        }
        onEvent({ event: eventText, data: parsedData });
      }

      boundary = buffer.indexOf('\n\n');
    }
  }
};

export default api;
