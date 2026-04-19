import { useEffect, useState } from 'react';
import { useAuth } from '../AuthContext';

export default function ProfilePage() {
  const { user, updateUser, refreshUser } = useAuth();
  const [form, setForm] = useState({ full_name: '', phone_number: '' });
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setForm({
      full_name: user?.full_name || '',
      phone_number: user?.phone_number || '',
    });
  }, [user?.full_name, user?.phone_number]);

  const set = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }));
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setError('');
    try {
      await refreshUser();
      setSuccessMessage('Đã làm mới thông tin tài khoản.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải lại thông tin tài khoản.');
    } finally {
      setRefreshing(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setSuccessMessage('');
    try {
      await updateUser({
        full_name: form.full_name.trim(),
        phone_number: form.phone_number.trim(),
      });
      setSuccessMessage('Thông tin hồ sơ đã được cập nhật.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể cập nhật hồ sơ.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="profile-page fade-in">
      <div className="profile-shell">
        <div className="profile-hero">
          <div>
            <span className="profile-eyebrow">Account Profile</span>
            <h1>Thông tin cá nhân</h1>
            <p>Cập nhật họ tên và số điện thoại để các workspace CV tái sử dụng thông tin chính xác hơn.</p>
          </div>
          <button
            type="button"
            className="btn-ghost profile-refresh-btn"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? 'Đang tải...' : 'Làm mới'}
          </button>
        </div>

        <div className="profile-grid">
          <section className="profile-summary-card">
            <div className="profile-avatar">
              {(user?.full_name || user?.email || 'U').trim().charAt(0).toUpperCase()}
            </div>
            <div className="profile-summary-copy">
              <h2>{user?.full_name || 'Chưa cập nhật họ tên'}</h2>
              <p>{user?.email || 'Không có email'}</p>
            </div>
            <div className="profile-summary-meta">
              <div>
                <span>Email</span>
                <strong>{user?.email || '--'}</strong>
              </div>
              <div>
                <span>Số điện thoại</span>
                <strong>{user?.phone_number || '--'}</strong>
              </div>
            </div>
          </section>

          <section className="profile-form-card">
            <div className="profile-form-header">
              <h2>Chỉnh sửa hồ sơ</h2>
              <p>Email là định danh đăng nhập nên đang để ở chế độ chỉ đọc.</p>
            </div>

            <form className="profile-form" onSubmit={handleSubmit}>
              {successMessage ? <div className="success-msg">{successMessage}</div> : null}
              {error ? <div className="error-msg">{error}</div> : null}

              <div className="field">
                <label htmlFor="profile-full-name">Họ tên</label>
                <input
                  id="profile-full-name"
                  type="text"
                  value={form.full_name}
                  onChange={set('full_name')}
                  placeholder="Nguyễn Văn A"
                  required
                />
              </div>

              <div className="field">
                <label htmlFor="profile-email">Email</label>
                <input
                  id="profile-email"
                  type="email"
                  value={user?.email || ''}
                  readOnly
                  disabled
                />
              </div>

              <div className="field">
                <label htmlFor="profile-phone">Số điện thoại</label>
                <input
                  id="profile-phone"
                  type="tel"
                  value={form.phone_number}
                  onChange={set('phone_number')}
                  placeholder="0912 345 678"
                />
              </div>

              <button type="submit" className="btn-primary profile-save-btn" disabled={loading}>
                {loading ? 'Đang lưu...' : 'Lưu thay đổi'}
              </button>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}
