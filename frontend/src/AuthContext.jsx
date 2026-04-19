import { createContext, useContext, useState, useEffect } from 'react';
import {
  getCurrentUserProfile,
  login as apiLogin,
  register as apiRegister,
  updateCurrentUserProfile,
} from './api';
import logger from './logger';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));

  const refreshUser = async () => {
    const res = await getCurrentUserProfile();
    setUser(res.data);
    logger.info('User profile refreshed', { email: res.data.email });
    return res.data;
  };

  const logout = () => {
    logger.info('Logout');
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }

    let cancelled = false;

    const restoreSession = async () => {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (!payload?.sub) {
          throw new Error('Missing sub claim');
        }

        setUser((prev) => ({ id: payload.sub, email: prev?.email || '' }));

        const res = await getCurrentUserProfile();
        if (cancelled) return;

        setUser(res.data);
        logger.info('Session restored from API', { email: res.data.email });
      } catch (error) {
        if (cancelled) return;

        logger.warn('Session restore failed — logging out', { error: error?.message });
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
      }
    };

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, [token]);

  const loginUser = async (email, password) => {
    logger.info('Login attempt', { email });
    try {
      const res = await apiLogin({ email, password });
      const t = res.data.access_token;
      localStorage.setItem('token', t);
      setToken(t);
      logger.info('Login SUCCESS', { email });
    } catch (err) {
      logger.error('Login FAILED', { email, status: err.response?.status });
      throw err;
    }
  };

  const registerUser = async (email, password, full_name) => {
    logger.info('Register attempt', { email });
    try {
      await apiRegister({ email, password, full_name });
      logger.info('Register SUCCESS', { email });
    } catch (err) {
      logger.error('Register FAILED', { email, status: err.response?.status });
      throw err;
    }
  };

  const updateUser = async (payload) => {
    const res = await updateCurrentUserProfile(payload);
    setUser(res.data);
    logger.info('User profile updated', { email: res.data.email });
    return res.data;
  };

  return (
    <AuthContext.Provider value={{ user, token, loginUser, registerUser, logout, refreshUser, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
