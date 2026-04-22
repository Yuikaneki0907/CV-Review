import { useState, useEffect } from 'react';
import { useAuth } from '../AuthContext';
import { useLocation, useNavigate, Link } from 'react-router-dom';

const PASSWORD_ERROR = 'Mật khẩu phải có chữ hoa, chữ thường, số, ký tự đặc biệt và dài hơn 8 ký tự.';
const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{9,}$/;

export default function AuthSwitchPage() {
  const { loginUser, registerUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Switcher state
  const [isRightPanelActive, setIsRightPanelActive] = useState(false);

  // Form states
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ full_name: '', email: '', password: '' });

  // UI states
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  
  const [loginError, setLoginError] = useState('');
  const [registerError, setRegisterError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  
  const [loginLoading, setLoginLoading] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);

  useEffect(() => {
    // If navigating to /register or passing state
    if (location.pathname === '/register') {
      setIsRightPanelActive(true);
    }
    if (location.state?.email) {
      setLoginForm((prev) => ({ ...prev, email: location.state.email }));
    }
    if (location.state?.successMessage) {
      setSuccessMessage(location.state.successMessage);
    }
  }, [location.pathname, location.state]);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoginError('');
    setSuccessMessage('');
    setLoginLoading(true);
    try {
      await loginUser(loginForm.email, loginForm.password);
      navigate('/generate-cv');
    } catch (err) {
      setLoginError(err.response?.data?.detail || 'Đăng nhập thất bại');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setRegisterError('');

    if (!PASSWORD_PATTERN.test(registerForm.password)) {
      setRegisterError(PASSWORD_ERROR);
      return;
    }

    setRegisterLoading(true);
    try {
      await registerUser(registerForm.email, registerForm.password, registerForm.full_name);
      // Switch back to Login with success message
      setIsRightPanelActive(false);
      setSuccessMessage('Đăng ký thành công. Vui lòng đăng nhập để tiếp tục.');
      setLoginForm((prev) => ({ ...prev, email: registerForm.email }));
      setRegisterForm({ full_name: '', email: '', password: '' });
    } catch (err) {
      setRegisterError(err.response?.data?.detail || 'Đăng ký thất bại');
    } finally {
      setRegisterLoading(false);
    }
  };

  const setLogin = (key) => (e) => setLoginForm({ ...loginForm, [key]: e.target.value });
  const setRegister = (key) => (e) => setRegisterForm({ ...registerForm, [key]: e.target.value });

  return (
    <div className="auth-wrapper">
      <div className={`auth-container ${isRightPanelActive ? 'right-panel-active' : ''}`}>
        
        {/* SIGN UP PANEL */}
        <div className="form-container sign-up-container">
          <div className="auth-form-content">
            <div className="auth-header text-center">
              <h2>Tạo tài khoản</h2>
            </div>
            
            <form onSubmit={handleRegisterSubmit}>
              {registerError && <div className="error-msg">{registerError}</div>}
              
              <div className="field">
                <input
                  type="text"
                  value={registerForm.full_name}
                  onChange={setRegister('full_name')}
                  placeholder="Họ tên"
                  required
                />
              </div>

              <div className="field">
                <input
                  type="email"
                  value={registerForm.email}
                  onChange={setRegister('email')}
                  placeholder="Email"
                  required
                />
              </div>

              <div className="field">
                <div className="password-wrapper">
                  <input
                    type={showRegisterPassword ? 'text' : 'password'}
                    value={registerForm.password}
                    onChange={setRegister('password')}
                    placeholder="Mật khẩu (>8 ký tự)"
                    minLength={9}
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowRegisterPassword(!showRegisterPassword)}
                  >
                    <span className="material-symbols-outlined">
                      {showRegisterPassword ? 'visibility_off' : 'visibility'}
                    </span>
                  </button>
                </div>
              </div>

              <button type="submit" className="btn-primary" disabled={registerLoading}>
                {registerLoading ? <><span className="spinner" /> Đang xử lý...</> : 'Đăng ký'}
              </button>

              <p className="mobile-switch-link">
                Đã có tài khoản? <span onClick={() => setIsRightPanelActive(false)}>Đăng nhập</span>
              </p>
            </form>
          </div>
        </div>

        {/* SIGN IN PANEL */}
        <div className="form-container sign-in-container">
          <div className="auth-form-content">
            <div className="auth-header text-center">
              <h2>Đăng nhập</h2>
            </div>

            <form onSubmit={handleLoginSubmit}>
              {successMessage && <div className="success-msg">{successMessage}</div>}
              {loginError && <div className="error-msg">{loginError}</div>}

              <div className="field">
                <input
                  type="email"
                  value={loginForm.email}
                  onChange={setLogin('email')}
                  placeholder="Email"
                  required
                />
              </div>

              <div className="field">
                <div className="password-wrapper">
                  <input
                    type={showLoginPassword ? 'text' : 'password'}
                    value={loginForm.password}
                    onChange={setLogin('password')}
                    placeholder="Mật khẩu"
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                  >
                    <span className="material-symbols-outlined">
                      {showLoginPassword ? 'visibility_off' : 'visibility'}
                    </span>
                  </button>
                </div>
                <Link to="/forgot-password" className="field-link field-link-center">
                  Quên mật khẩu?
                </Link>
              </div>

              <button type="submit" className="btn-primary" disabled={loginLoading}>
                {loginLoading ? <><span className="spinner" /> Đang xử lý...</> : 'Đăng nhập'}
              </button>

              <p className="mobile-switch-link">
                Chưa có tài khoản? <span onClick={() => setIsRightPanelActive(true)}>Đăng ký ngay</span>
              </p>
            </form>
          </div>
        </div>

        {/* OVERLAY PANEL */}
        <div className="overlay-container">
          <div className="overlay">
            {/* Left Overlay (shown when Sign Up is active, clicking shifts to Sign In) */}
            <div className="overlay-panel overlay-left">
              <h1>Chào Mừng Trở Lại!</h1>
              <p>Để duy trì kết nối với chúng tôi, vui lòng đăng nhập bằng tài khoản cá nhân của bạn.</p>
              <button className="ghost-btn" onClick={() => setIsRightPanelActive(false)}>
                Đăng nhập
              </button>
            </div>
            
            {/* Right Overlay (shown when Sign In is active, clicking shifts to Sign Up) */}
            <div className="overlay-panel overlay-right">
              <h1>Xin Chào!</h1>
              <p>Hãy cung cấp thông tin của bạn và bắt đầu hành trình xây dựng sự nghiệp cùng chúng tôi.</p>
              <button className="ghost-btn" onClick={() => setIsRightPanelActive(true)}>
                Đăng ký ngay
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
