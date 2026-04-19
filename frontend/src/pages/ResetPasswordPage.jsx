import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { resetPassword } from '../api';

const PASSWORD_REQUIREMENT = 'Chữ hoa, chữ thường, số, ký tự đặc biệt, > 8 ký tự';
const PASSWORD_ERROR = 'Mật khẩu phải có chữ hoa, chữ thường, số, ký tự đặc biệt và dài hơn 8 ký tự.';
const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{9,}$/;

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError('Liên kết đặt lại mật khẩu không hợp lệ hoặc thiếu token.');
      return;
    }

    if (!PASSWORD_PATTERN.test(password)) {
      setError(PASSWORD_ERROR);
      return;
    }

    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }

    setLoading(true);
    try {
      await resetPassword({ token, new_password: password });
      navigate('/login', {
        replace: true,
        state: {
          successMessage: 'Đặt lại mật khẩu thành công. Vui lòng đăng nhập với mật khẩu mới.',
        },
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể đặt lại mật khẩu');
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
            <span className="material-symbols-outlined">password</span>
            <span>Credential Renewal</span>
          </div>
          <div className="auth-brand-hero">
            <span className="auth-brand-tag">One-Time Access</span>
            <h1>Tạo mật khẩu mới</h1>
            <p>Đặt một mật khẩu mới để kích hoạt lại tài khoản. Sau khi hoàn tất, các token reset cũ sẽ tự bị vô hiệu hóa.</p>
          </div>
          <div className="auth-brand-stats">
            <div>
              <span className="stat-label">Security</span>
              <span className="stat-value">Hashed Token</span>
            </div>
            <div>
              <span className="stat-label">Result</span>
              <span className="stat-value">Login Again</span>
            </div>
          </div>
        </div>
        <div className="auth-brand-sphere" />
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-container">
          <div className="auth-header">
            <h2>Đặt lại mật khẩu</h2>
            <p>Tạo mật khẩu mới cho tài khoản của bạn. Mật khẩu cần có chữ hoa, chữ thường, số, ký tự đặc biệt và dài hơn 8 ký tự.</p>
          </div>

          <form onSubmit={handleSubmit}>
            {!token && (
              <div className="error-msg">
                Liên kết đặt lại mật khẩu không hợp lệ hoặc đã bị thiếu token.
              </div>
            )}
            {error && <div className="error-msg">{error}</div>}

            <div className="field">
              <label htmlFor="reset-password">Mật khẩu mới</label>
              <div className="password-wrapper">
                <input
                  id="reset-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Trên 8 ký tự"
                  minLength={9}
                  aria-describedby="reset-password-requirements"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((value) => !value)}
                >
                  <span className="material-symbols-outlined">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
              <p id="reset-password-requirements" className="password-requirements">
                {PASSWORD_REQUIREMENT}
              </p>
            </div>

            <div className="field">
              <label htmlFor="reset-confirm-password">Xác nhận mật khẩu mới</label>
              <div className="password-wrapper">
                <input
                  id="reset-confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Nhập lại mật khẩu mới"
                  minLength={9}
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowConfirmPassword((value) => !value)}
                >
                  <span className="material-symbols-outlined">
                    {showConfirmPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            <button type="submit" className="btn-primary" disabled={loading || !token}>
              {loading ? (
                <>
                  <span className="spinner" /> Đang cập nhật...
                </>
              ) : 'Lưu mật khẩu mới'}
            </button>
          </form>

          <p className="switch-link">
            Cần tạo lại liên kết?<Link to="/forgot-password">Quên mật khẩu</Link>
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
