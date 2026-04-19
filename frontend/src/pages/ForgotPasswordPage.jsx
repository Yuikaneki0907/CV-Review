import { useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '../api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [debugResetUrl, setDebugResetUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setDebugResetUrl('');
    setLoading(true);

    try {
      const res = await forgotPassword({ email });
      setMessage(res.data.message || 'Nếu email tồn tại, hệ thống sẽ gửi hướng dẫn đặt lại mật khẩu.');
      setDebugResetUrl(res.data.debug_reset_url || '');
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể xử lý yêu cầu quên mật khẩu');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <section className="auth-brand">
        <div className="auth-brand-gradient" />
        <div className="auth-brand-content">
          <div className="auth-brand-logo">
            <span className="material-symbols-outlined">lock_reset</span>
            <span>Password Recovery</span>
          </div>
          <div className="auth-brand-hero">
            <span className="auth-brand-tag">Secure Recovery Flow</span>
            <h1>Lấy lại quyền truy cập tài khoản</h1>
            <p>Nhập email đã đăng ký để nhận liên kết đặt lại mật khẩu. Liên kết chỉ dùng được một lần và sẽ tự hết hạn.</p>
          </div>
          <div className="auth-brand-stats">
            <div>
              <span className="stat-label">Reset Token</span>
              <span className="stat-value">One-time</span>
            </div>
            <div>
              <span className="stat-label">Validity</span>
              <span className="stat-value">30 min</span>
            </div>
          </div>
        </div>
        <div className="auth-brand-sphere" />
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-container">
          <div className="auth-header">
            <h2>Quên mật khẩu</h2>
            <p>Nhập email của bạn. Nếu tài khoản tồn tại, hệ thống sẽ tạo liên kết đặt lại mật khẩu.</p>
          </div>

          <form onSubmit={handleSubmit}>
            {message && <div className="success-msg">{message}</div>}
            {error && <div className="error-msg">{error}</div>}

            <div className="field">
              <label htmlFor="forgot-email">Email</label>
              <input
                id="forgot-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
              />
            </div>

            {debugResetUrl && (
              <div className="debug-reset-card">
                <p className="debug-reset-title">Môi trường debug chưa cấu hình email.</p>
                <p className="debug-reset-text">Dùng liên kết dưới đây để tiếp tục luồng reset ngay trên server hiện tại.</p>
                <a className="debug-reset-link" href={debugResetUrl}>
                  Mở trang đặt lại mật khẩu
                </a>
              </div>
            )}

            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? (
                <>
                  <span className="spinner" /> Đang gửi yêu cầu...
                </>
              ) : 'Gửi liên kết đặt lại'}
            </button>
          </form>

          <p className="switch-link">
            Nhớ lại mật khẩu?<Link to="/login">Đăng nhập</Link>
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
