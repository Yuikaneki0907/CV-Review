import axios from 'axios';
import logger from './logger';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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

// Analysis
export const createAnalysis = (formData) =>
  api.post('/analysis/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const listAnalyses = (limit = 20, offset = 0) =>
  api.get(`/analysis/?limit=${limit}&offset=${offset}`);

export const getAnalysis = (id) => api.get(`/analysis/${id}`);

export default api;
