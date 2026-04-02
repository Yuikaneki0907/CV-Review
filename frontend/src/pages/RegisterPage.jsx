import { useState } from 'react';
import { useAuth } from '../AuthContext';
import { useNavigate, Link } from 'react-router-dom';

export default function RegisterPage() {
  const { registerUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await registerUser(form.email, form.password, form.full_name);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Đăng ký thất bại');
    } finally {
      setLoading(false);
    }
  };

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <div className="logo">
            <span className="logo-icon">📄</span>
            <h1>CV Review</h1>
          </div>
          <p className="subtitle">Tạo tài khoản mới</p>
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
              placeholder="your@email.com"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="reg-password">Mật khẩu</label>
            <input
              id="reg-password"
              type="password"
              value={form.password}
              onChange={set('password')}
              placeholder="Tối thiểu 6 ký tự"
              minLength={6}
              required
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Đang xử lý...' : 'Đăng ký'}
          </button>
        </form>
        <p className="switch-link">
          Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
        </p>
      </div>
    </div>
  );
}
