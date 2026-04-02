import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAnalysis } from '../api';

export default function AnalysisPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');

  const fetchData = async () => {
    try {
      const res = await getAnalysis(id);
      setData(res.data);
      if (res.data.status === 'processing' || res.data.status === 'pending') {
        setTimeout(fetchData, 3000);
      }
    } catch {
      setData({ error: true });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  if (loading) {
    return (
      <div className="analysis-page">
        <div className="loading-state">
          <div className="pulse-ring" />
          <p>Đang tải kết quả...</p>
        </div>
      </div>
    );
  }

  if (data?.error) {
    return (
      <div className="analysis-page">
        <div className="error-state">
          <p>Không tìm thấy kết quả phân tích</p>
          <Link to="/" className="btn-secondary">← Quay lại</Link>
        </div>
      </div>
    );
  }

  if (data.status === 'pending' || data.status === 'processing') {
    return (
      <div className="analysis-page">
        <div className="loading-state">
          <div className="pulse-ring" />
          <h3>Đang phân tích CV...</h3>
          <p>Quá trình phân tích mất khoảng 30-60 giây</p>
          <div className="progress-steps">
            <Step label="Trích xuất thông tin CV" done />
            <Step label="Phân tích JD" done={data.jd_extracted} />
            <Step label="Matching & Scoring" done={data.score} />
            <Step label="Viết lại CV" done={data.rewritten_cv} />
            <Step label="Kiểm tra hallucination" done={data.hallucination_warnings} />
          </div>
        </div>
      </div>
    );
  }

  if (data.status === 'failed') {
    return (
      <div className="analysis-page">
        <div className="error-state">
          <h3>⚠️ Phân tích thất bại</h3>
          <p>Vui lòng thử lại</p>
          <Link to="/" className="btn-primary">Thử lại</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="analysis-page">
      <div className="analysis-header">
        <Link to="/history" className="back-link">← Danh sách</Link>
        <h2>{data.cv_filename}</h2>
        <span className={`status-badge status-${data.status}`}>{data.status}</span>
      </div>

      {/* Score Cards */}
      {data.score && (
        <div className="score-section">
          <ScoreCard label="Tổng điểm" value={data.score.overall} large />
          <ScoreCard label="Kỹ năng" value={data.score.skills_score} />
          <ScoreCard label="Kinh nghiệm" value={data.score.experience_score} />
          <ScoreCard label="Công cụ" value={data.score.tools_score} />
        </div>
      )}

      {/* Tabs */}
      <div className="tab-bar">
        <button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>
          Tổng quan
        </button>
        <button className={tab === 'diff' ? 'active' : ''} onClick={() => setTab('diff')}>
          So sánh CV
        </button>
        <button className={tab === 'warnings' ? 'active' : ''} onClick={() => setTab('warnings')}>
          Cảnh báo ({data.hallucination_warnings?.length || 0})
        </button>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {tab === 'overview' && (
          <div className="overview-tab">
            <div className="skills-grid">
              <SkillList title="✅ Kỹ năng phù hợp" items={data.matched_skills} type="matched" />
              <SkillList title="❌ Kỹ năng thiếu" items={data.missing_skills} type="missing" />
              <SkillList title="➕ Kỹ năng bổ sung" items={data.extra_skills} type="extra" />
            </div>
          </div>
        )}

        {tab === 'diff' && (
          <div className="diff-tab">
            <h3>CV gốc vs CV đề xuất</h3>
            {data.diff_segments ? (
              <div className="diff-view">
                {data.diff_segments.map((seg, i) => (
                  <span key={i} className={`diff-${seg.diff_type}`}>{seg.text}</span>
                ))}
              </div>
            ) : (
              <p className="empty">Chưa có dữ liệu so sánh</p>
            )}
          </div>
        )}

        {tab === 'warnings' && (
          <div className="warnings-tab">
            {data.hallucination_warnings?.length > 0 ? (
              data.hallucination_warnings.map((w, i) => (
                <div key={i} className={`warning-card level-${w.level}`}>
                  <div className="warning-header">
                    <span className="warning-level">{w.level.toUpperCase()}</span>
                    <span className="warning-type">{w.issue_type}</span>
                  </div>
                  <p className="warning-section">Phần: {w.section}</p>
                  <div className="warning-comparison">
                    <div>
                      <strong>Bản gốc:</strong>
                      <p>{w.original_text}</p>
                    </div>
                    <div>
                      <strong>Bản viết lại:</strong>
                      <p>{w.rewritten_text}</p>
                    </div>
                  </div>
                  <p className="warning-explanation">{w.explanation}</p>
                </div>
              ))
            ) : (
              <div className="empty-warnings">
                <span>✅</span>
                <p>Không phát hiện hallucination</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreCard({ label, value, large }) {
  const color = value >= 80 ? 'green' : value >= 50 ? 'yellow' : 'red';
  return (
    <div className={`score-card ${large ? 'large' : ''} score-${color}`}>
      <div className="score-value">{value ?? '—'}</div>
      <div className="score-label">{label}</div>
    </div>
  );
}

function SkillList({ title, items, type }) {
  return (
    <div className="skill-list">
      <h4>{title}</h4>
      <div className="skill-tags">
        {items?.map((s, i) => (
          <span key={i} className={`skill-tag tag-${type}`}>
            {s.name}
            {s.category && <small>{s.category}</small>}
          </span>
        ))}
        {(!items || items.length === 0) && <span className="empty">Không có</span>}
      </div>
    </div>
  );
}

function Step({ label, done }) {
  return (
    <div className={`step ${done ? 'done' : ''}`}>
      <span className="step-icon">{done ? '✅' : '⏳'}</span>
      <span>{label}</span>
    </div>
  );
}
