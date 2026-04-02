import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listAnalyses } from '../api';

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
    pending: '⏳ Chờ xử lý',
    processing: '🔄 Đang xử lý',
    completed: '✅ Hoàn thành',
    failed: '❌ Thất bại',
  };

  return (
    <div className="history-page">
      <div className="history-header">
        <h2>Lịch sử phân tích</h2>
        <Link to="/" className="btn-primary">+ Phân tích mới</Link>
      </div>

      {loading ? (
        <div className="loading-state"><div className="pulse-ring" /><p>Đang tải...</p></div>
      ) : analyses.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📋</span>
          <p>Chưa có kết quả phân tích nào</p>
          <Link to="/" className="btn-primary">Bắt đầu phân tích đầu tiên</Link>
        </div>
      ) : (
        <div className="history-list">
          {analyses.map((a) => (
            <Link key={a.id} to={`/analysis/${a.id}`} className="history-card">
              <div className="history-card-left">
                <span className="file-icon">📄</span>
                <div>
                  <h4>{a.cv_filename}</h4>
                  <p className="date">
                    {new Date(a.created_at).toLocaleDateString('vi-VN', {
                      day: '2-digit', month: '2-digit', year: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                    })}
                  </p>
                </div>
              </div>
              <div className="history-card-right">
                {a.overall_score != null && (
                  <div className={`mini-score score-${a.overall_score >= 80 ? 'green' : a.overall_score >= 50 ? 'yellow' : 'red'}`}>
                    {a.overall_score}
                  </div>
                )}
                <span className={`status-badge status-${a.status}`}>
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
