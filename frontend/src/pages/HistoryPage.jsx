import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listAnalyses } from '../api';

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

  useEffect(() => {
    listAnalyses().then((res) => {
      setAnalyses(res.data);
      setLoading(false);
    });
  }, []);

  const statusLabel = {
    pending: 'Chờ xử lý',
    processing: 'Đang xử lý',
    completed: 'Hoàn thành',
    failed: 'Thất bại',
  };

  return (
    <div className="history-page">
      <div className="history-header">
        <h2>Lịch sử phân tích</h2>
        <Link to="/" className="btn-primary">
          + Phân tích mới
        </Link>
      </div>

      {loading ? (
        <div className="loading-state"><div className="pulse-ring" /><p>Đang tải...</p></div>
      ) : analyses.length === 0 ? (
        <div className="empty-state">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="var(--outline)">
            <path d="M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z" />
          </svg>
          <p>Chưa có kết quả phân tích nào</p>
          <Link to="/" className="btn-primary" style={{ width: 'auto', padding: '0.6rem 1.5rem' }}>Bắt đầu phân tích đầu tiên</Link>
        </div>
      ) : (
        <div className="history-list">
          {analyses.map((a) => (
            <Link key={a.id} to={`/analysis/${a.id}`} className="history-card">
              <div className="history-card-left">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="var(--primary)">
                  <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
                </svg>
                <div>
                  <h4>{a.cv_filename}</h4>
                  <p className="date">{formatDate(a.created_at)}</p>
                </div>
              </div>
              <div className="history-card-right">
                {a.overall_score != null && (
                  <div className={`mini-score score-${a.overall_score >= 80 ? 'green' : a.overall_score >= 50 ? 'yellow' : 'red'}`}>
                    {a.overall_score}
                  </div>
                )}
                <span className={`status-badge status-${a.status}`}>
                  {a.status === 'completed' ? '✓ ' : a.status === 'failed' ? '✕ ' : '⏳ '}
                  {statusLabel[a.status] || a.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
