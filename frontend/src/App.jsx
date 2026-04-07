import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import UploadPage from './pages/UploadPage';
import AnalysisPage from './pages/AnalysisPage';
import HistoryPage from './pages/HistoryPage';

function PrivateRoute({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" />;
}

function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isLanding = location.pathname === '/';
  const isAuth = location.pathname === '/login' || location.pathname === '/register';

  // Don't show navbar on auth pages
  if (isAuth) return null;

  return (
    <nav className={`navbar ${isLanding && !user ? 'navbar-landing' : ''}`}>
      <div className="nav-left">
        <Link to="/" className="nav-logo">
          <span className="logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 4.5c-1.09-.07-3.3.2-5 1.32V19.5c1.7-1 3.91-1.3 5-1.24V4.5ZM14 5.82C12.3 4.7 10.09 4.43 9 4.5v13.76c1.09-.06 3.3.24 5 1.24V5.82ZM3 4.5v13.76c1.09-.07 3.3.2 5 1.32V5.82C6.3 4.7 4.09 4.43 3 4.5Z" />
            </svg>
          </span>
          <span>Editorial Intelligence</span>
        </Link>
        {user && (
          <>
            <div className="nav-divider" />
            <Link to="/upload" className={`nav-link ${location.pathname === '/upload' ? 'active' : ''}`}>
              Phân tích
            </Link>
            <Link to="/history" className={`nav-link ${location.pathname === '/history' ? 'active' : ''}`}>
              Lịch sử
            </Link>
          </>
        )}
      </div>
      <div className="nav-right">
        {user ? (
          <>
            <span className="nav-user">{user.email}</span>
            <button className="btn-ghost" onClick={logout}>Đăng xuất</button>
          </>
        ) : (
          <>
            <Link to="/login" className="btn-ghost">Đăng nhập</Link>
            <Link to="/register" className="btn-nav-primary">Đăng ký miễn phí</Link>
          </>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app">
          <Navbar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/upload" element={<PrivateRoute><UploadPage /></PrivateRoute>} />
              <Route path="/analysis/:id" element={<PrivateRoute><AnalysisPage /></PrivateRoute>} />
              <Route path="/history" element={<PrivateRoute><HistoryPage /></PrivateRoute>} />
            </Routes>
          </main>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
