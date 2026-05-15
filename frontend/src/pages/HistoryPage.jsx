import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EllipsisHorizontalIcon } from '@heroicons/react/24/outline';
import { deleteAnalysis, listAnalyses } from '../api';

function formatDate(dateStr) {
  if (!dateStr) return '';
  // Backend returns UTC time. Ensure we parse as UTC, then display as local.
  let d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  // If no timezone indicator, treat as UTC
  if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('T')) {
    d = new Date(dateStr + 'Z');
  }
  return d.toLocaleString('vi-VN', {
    hour: '2-digit', minute: '2-digit',
    day: '2-digit', month: '2-digit', year: 'numeric',
    timeZone: 'Asia/Ho_Chi_Minh',
  });
}

export default function HistoryPage() {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [openMenuId, setOpenMenuId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    let mounted = true;

    listAnalyses()
      .then((res) => {
        if (!mounted) return;
        setAnalyses(Array.isArray(res?.data) ? res.data : []);
      })
      .catch(() => {
        if (!mounted) return;
        setError('Không thể tải danh sách phân tích. Vui lòng thử lại sau.');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const closeMenu = () => setOpenMenuId(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const statusLabel = {
    pending: 'Chờ xử lý',
    processing: 'Đang xử lý',
    completed: 'Hoàn thành',
    failed: 'Thất bại',
  };

  const filterOptions = [
    { key: 'all', label: 'Tất cả' },
    { key: 'pending', label: 'Chờ xử lý' },
    { key: 'processing', label: 'Đang xử lý' },
    { key: 'completed', label: 'Hoàn thành' },
    { key: 'failed', label: 'Thất bại' },
  ];

  const filteredAnalyses = useMemo(() => {
    if (activeFilter === 'all') return analyses;
    return analyses.filter((item) => item.status === activeFilter);
  }, [activeFilter, analyses]);

  const stats = useMemo(() => {
    const total = analyses.length;
    const completed = analyses.filter((item) => item.status === 'completed').length;
    const pending = analyses.filter((item) => item.status === 'pending' || item.status === 'processing').length;
    const scored = analyses.filter((item) => typeof item.overall_score === 'number');
    const averageScore = scored.length
      ? Math.round(scored.reduce((sum, item) => sum + item.overall_score, 0) / scored.length)
      : null;

    return { total, completed, pending, averageScore };
  }, [analyses]);

  const requestDeleteAnalysis = (event, analysis) => {
    event.preventDefault();
    event.stopPropagation();
    setOpenMenuId(null);
    setDeleteError('');
    setDeleteTarget(analysis);
  };

  const handleConfirmDeleteAnalysis = async () => {
    if (!deleteTarget || deletingId) return;
    setDeletingId(deleteTarget.id);
    try {
      await deleteAnalysis(deleteTarget.id);
      setAnalyses((prev) => prev.filter((item) => item.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      console.error('Failed to delete analysis:', err);
      setDeleteError(err.response?.data?.detail || 'Không thể xóa bản phân tích này.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="history-page">
      <div className="history-hero">
        <div className="history-hero-content">
          <span className="history-eyebrow">Editorial Intelligence</span>
          <h2>Lịch sử phân tích</h2>
          <p>Theo dõi tiến trình chấm CV, xem điểm và mở nhanh bản phân tích chi tiết. Lịch sử workspace và phiên bản CV được quản lý riêng trong thanh bên trái.</p>
        </div>
        <Link to="/generate-cv" state={{ mode: 'analyze' }} className="history-new-btn">
          + Phân tích mới
        </Link>
      </div>

      <div className="history-stats-grid">
        <div className="history-stat-card">
          <span>Tổng phân tích</span>
          <strong>{stats.total}</strong>
        </div>
        <div className="history-stat-card">
          <span>Hoàn thành</span>
          <strong>{stats.completed}</strong>
        </div>
        <div className="history-stat-card">
          <span>Đang chờ / xử lý</span>
          <strong>{stats.pending}</strong>
        </div>
        <div className="history-stat-card">
          <span>Điểm trung bình</span>
          <strong>{stats.averageScore != null ? stats.averageScore : '--'}</strong>
        </div>
      </div>

      <div className="history-toolbar">
        <div className="history-filters">
          {filterOptions.map((opt) => (
            <button
              key={opt.key}
              type="button"
              className={`history-filter-btn ${activeFilter === opt.key ? 'active' : ''}`}
              onClick={() => setActiveFilter(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <span className="history-count">{filteredAnalyses.length} kết quả</span>
      </div>

      {loading ? (
        <div className="history-loading-state">
          <div className="pulse-ring" />
          <p>Đang tải danh sách phân tích...</p>
        </div>
      ) : error ? (
        <div className="history-empty-state">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="var(--red)">
            <path d="M11 15h2v2h-2zm0-8h2v6h-2zm1-5C5.925 2 1 6.925 1 13s4.925 11 11 11 11-4.925 11-11S18.075 2 12 2zm0 20c-4.962 0-9-4.037-9-9s4.038-9 9-9 9 4.037 9 9-4.038 9-9 9z" />
          </svg>
          <p>{error}</p>
          <Link to="/generate-cv" state={{ mode: 'analyze' }} className="history-empty-cta">Tạo phân tích mới</Link>
        </div>
      ) : filteredAnalyses.length === 0 ? (
        <div className="history-empty-state">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="var(--outline)">
            <path d="M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z" />
          </svg>
          <p>{analyses.length === 0 ? 'Chưa có kết quả phân tích nào' : 'Không có kết quả phù hợp bộ lọc hiện tại'}</p>
          <Link to="/generate-cv" state={{ mode: 'analyze' }} className="history-empty-cta">Bắt đầu phân tích mới</Link>
        </div>
      ) : (
        <div className="history-list">
          {filteredAnalyses.map((a) => (
            <Link key={a.id} to={`/analysis/${a.id}`} className="history-card">
              <div className="history-card-left">
                <div className="history-file-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="var(--primary)">
                    <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
                  </svg>
                </div>
                <div>
                  <h4>{a.cv_filename}</h4>
                  <p className="date">{formatDate(a.created_at)}</p>
                </div>
              </div>
              <div className="history-card-right">
                {a.overall_score != null && (
                  <>
                    <span className={`verdict-pill verdict-${a.overall_score >= 70 ? 'pass' : a.overall_score >= 50 ? 'borderline' : 'fail'}`}>
                      {a.overall_score >= 70 ? 'PASS' : a.overall_score >= 50 ? 'BORDERLINE' : 'FAIL'}
                    </span>
                    <div className={`mini-score score-${a.overall_score >= 80 ? 'green' : a.overall_score >= 50 ? 'yellow' : 'red'}`}>
                      {a.overall_score}
                    </div>
                  </>
                )}
                <span className={`status-badge status-${a.status}`}>
                  {a.status === 'completed' ? '✓ ' : a.status === 'failed' ? '✕ ' : '◔ '}
                  {statusLabel[a.status] || a.status}
                </span>
                <div className="history-card-actions" onClick={(event) => event.stopPropagation()}>
                  <button
                    type="button"
                    className="history-menu-btn"
                    title="Tùy chọn"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setOpenMenuId((prev) => (prev === a.id ? null : a.id));
                    }}
                    disabled={deletingId === a.id}
                  >
                    <EllipsisHorizontalIcon className="history-menu-icon" />
                  </button>
                  {openMenuId === a.id && (
                    <div className="history-menu-popover">
                      <button
                        type="button"
                        className="history-menu-delete"
                        onClick={(event) => requestDeleteAnalysis(event, a)}
                        disabled={deletingId === a.id}
                      >
                        {deletingId === a.id ? 'Đang xóa...' : 'Xóa'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
      {deleteTarget && (
        <div className="confirm-modal-backdrop" role="presentation">
          <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-delete-history">
            <h3 id="confirm-delete-history">Xác nhận xóa phân tích</h3>
            <p>
              Bạn có chắc muốn xóa <strong>{deleteTarget.cv_filename}</strong> không?
            </p>
            {deleteError && <div className="confirm-modal-error">{deleteError}</div>}
            <div className="confirm-modal-actions">
              <button
                type="button"
                className="confirm-modal-btn cancel"
                onClick={() => setDeleteTarget(null)}
                disabled={Boolean(deletingId)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="confirm-modal-btn danger"
                onClick={handleConfirmDeleteAnalysis}
                disabled={Boolean(deletingId)}
              >
                {deletingId ? 'Đang xóa...' : 'Xóa'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
