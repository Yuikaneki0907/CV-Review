import { createContext, useContext, useState, useEffect } from 'react';
import { login as apiLogin, register as apiRegister } from './api';
import logger from './logger';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));

  useEffect(() => {
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUser({ id: payload.sub, email: payload.email });
        logger.info('Session restored from token', { email: payload.email });
      } catch {
        logger.warn('Invalid token found in localStorage — logging out');
        logout();
      }
    }
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
      await loginUser(email, password);
    } catch (err) {
      logger.error('Register FAILED', { email, status: err.response?.status });
      throw err;
    }
  };

  const logout = () => {
    logger.info('Logout');
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loginUser, registerUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
