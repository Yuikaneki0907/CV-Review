import { useState } from 'react';
import { useAuth } from '../AuthContext';
import { useNavigate, Link } from 'react-router-dom';

export default function RegisterPage() {
  const { registerUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await registerUser(form.email, form.password, form.full_name);
      navigate('/upload');
    } catch (err) {
      setError(err.response?.data?.detail || 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

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
            <p>Join thousands of professionals who have elevated their careers with intelligent resume optimization.</p>
          </div>
          <div className="auth-brand-stats">
            <div>
              <span className="stat-label">CVs Optimized</span>
              <span className="stat-value">50k+</span>
            </div>
            <div>
              <span className="stat-label">Avg Score Boost</span>
              <span className="stat-value">+34%</span>
            </div>
          </div>
        </div>
        <div className="auth-brand-sphere" />
      </section>

      {/* Right: Register Form */}
      <section className="auth-form-panel">
        <div className="auth-form-container">
          <div className="auth-header">
            <h2>Tạo tài khoản</h2>
            <p>Bắt đầu tối ưu hóa CV của bạn ngay hôm nay.</p>
          </div>

          <form onSubmit={handleSubmit}>
            {error && <div className="error-msg">{error}</div>}

            <div className="field">
              <label htmlFor="reg-name">Họ tên</label>
              <input
                id="reg-name"
                type="text"
                value={form.full_name}
                onChange={set('full_name')}
                placeholder="Nguyễn Văn A"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="reg-email">Email</label>
              <input
                id="reg-email"
                type="email"
                value={form.email}
                onChange={set('email')}
                placeholder="name@company.com"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="reg-password">Mật khẩu</label>
              <div className="password-wrapper">
                <input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={set('password')}
                  placeholder="Tối thiểu 6 ký tự"
                  minLength={6}
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
              ) : 'Đăng ký'}
            </button>
          </form>

          <p className="switch-link">
            Đã có tài khoản?<Link to="/login">Đăng nhập</Link>
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
