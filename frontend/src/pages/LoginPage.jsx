import { useState } from 'react';
import { useAuth } from '../AuthContext';
import { useNavigate, Link } from 'react-router-dom';

export default function LoginPage() {
  const { loginUser } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginUser(email, password);
      navigate('/upload');
    } catch (err) {
      setError(err.response?.data?.detail || 'Đăng nhập thất bại');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      {/* Left: Brand Panel */}
      <section className="auth-brand">
        <div className="auth-brand-gradient" />
        <div className="auth-brand-content">
          <div className="auth-brand-logo">
            <span className="material-symbols-outlined">auto_stories</span>
            <span>Editorial Intelligence</span>
          </div>
          <div className="auth-brand-hero">
            <span className="auth-brand-tag">The Digital Curator</span>
            <h1>AI-Powered CV Optimization</h1>
            <p>Refine your professional story with precision and purpose. We transform technical data into career-shaping narratives.</p>
          </div>
          <div className="auth-brand-stats">
            <div>
              <span className="stat-label">Active Users</span>
              <span className="stat-value">12k+</span>
            </div>
            <div>
              <span className="stat-label">Success Rate</span>
              <span className="stat-value">98.4%</span>
            </div>
          </div>
        </div>
        <div className="auth-brand-sphere" />
      </section>

      {/* Right: Login Form */}
      <section className="auth-form-panel">
        <div className="auth-form-container">
          <div className="auth-header">
            <h2>Đăng nhập</h2>
            <p>Chào mừng trở lại. Hãy tối ưu hóa sự nghiệp của bạn.</p>
          </div>

          <form onSubmit={handleSubmit}>
            {error && <div className="error-msg">{error}</div>}

            <div className="field">
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
              />
            </div>

            <div className="field">
              <div className="field-row">
                <label htmlFor="login-password">Mật khẩu</label>
                <a href="#" className="field-link">Quên mật khẩu?</a>
              </div>
              <div className="password-wrapper">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  <span className="material-symbols-outlined">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? (
                <>
                  <span className="spinner" /> Đang xử lý...
                </>
              ) : 'Đăng nhập'}
            </button>
          </form>

          <div className="auth-divider">
            <div className="line" />
            <span>hoặc</span>
          </div>

          <p className="switch-link">
            Chưa có tài khoản?<Link to="/register">Đăng ký ngay</Link>
          </p>
        </div>

        <footer className="auth-footer">
          <a href="#">Điều khoản</a>
          <a href="#">Bảo mật</a>
          <a href="#">Hỗ trợ</a>
        </footer>
      </section>
    </div>
  );
}
