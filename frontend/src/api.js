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
export const getCurrentUserProfile = () => api.get('/auth/me');

// Analysis
export const createAnalysis = (formData) =>
  api.post('/analysis/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const listAnalyses = (limit = 20, offset = 0) =>
  api.get(`/analysis/?limit=${limit}&offset=${offset}`);

export const getAnalysis = (id) => api.get(`/analysis/${id}`);

export const deleteAnalysis = (id) => api.delete(`/analysis/${id}`);

// Generated CV
export const createGeneratedCV = (data) => api.post('/generated-cvs/', data);
export const listGeneratedCVs = (limit = 20, offset = 0) => api.get(`/generated-cvs/?limit=${limit}&offset=${offset}`);
export const getGeneratedCV = (id) => api.get(`/generated-cvs/${id}`);
export const getGeneratedCVVersions = (id) => api.get(`/generated-cvs/${id}/versions`);
export const deleteGeneratedCV = (id) => api.delete(`/generated-cvs/${id}`);
export const createGeneratedCVVersion = (id, data) => api.post(`/generated-cvs/${id}/versions`, data);
export const updateGeneratedCV = (id, data) => api.patch(`/generated-cvs/${id}`, data);
export const chatCVGeneration = (messages, outputFormat = 'markdown', templateId = null, currentCvId = null) =>
  api.post('/generated-cvs/chat', {
    messages,
    output_format: outputFormat,
    ...(templateId && { template_id: templateId }),
    ...(currentCvId && { current_cv_id: currentCvId }),
  });
export const downloadGeneratedCV = (id, format = 'markdown') =>
  api.get(`/generated-cvs/${id}/download`, {
    params: { format },
    responseType: 'blob',
  });
export const exportGeneratedCV = downloadGeneratedCV;

export const streamChatCVGeneration = async (messages, outputFormat = 'markdown', onEvent, templateId = null, currentCvId = null) => {
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
    body: JSON.stringify({
      messages,
      output_format: outputFormat,
      ...(templateId && { template_id: templateId }),
      ...(currentCvId && { current_cv_id: currentCvId }),
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP Error: ${response.status}`);
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
        } catch (e) {
          // fallback to raw text
        }
        onEvent({ event: eventText, data: parsedData });
      }

      boundary = buffer.indexOf('\n\n');
    }
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
        } catch (e) {
          // fallback to raw text
        }
        onEvent({ event: eventText, data: parsedData });
      }

      boundary = buffer.indexOf('\n\n');
    }
  }
};

export default api;
