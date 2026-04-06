import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAnalysis } from '../api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const PIPELINE_STEPS = [
  { key: 'extract', label: 'Trích xuất thông tin CV' },
  { key: 'score', label: 'Matching & Scoring' },
  { key: 'rewrite', label: 'Viết lại CV' },
  { key: 'truthcheck', label: 'Kiểm tra hallucination' },
  { key: 'diff', label: 'Tạo visual diff' },
];

export default function AnalysisPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');
  const [stepStates, setStepStates] = useState({});
  const eventSourceRef = useRef(null);

  // Fetch full analysis data
  const fetchData = async () => {
    try {
      const res = await getAnalysis(id);
      setData(res.data);
      return res.data;
    } catch {
      setData({ error: true });
      return null;
    } finally {
      setLoading(false);
    }
  };

  // Connect to SSE for real-time streaming
  const connectSSE = () => {
    const token = localStorage.getItem('token');
    if (!token) return;

    // EventSource doesn't support custom headers, so we use fetch-based SSE
    const url = `${API_BASE}/analysis/${id}/stream`;

    const fetchSSE = async () => {
      try {
        const response = await fetch(url, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'text/event-stream',
          },
        });

        if (!response.ok) {
          console.warn('SSE connection failed, falling back to polling');
          fallbackPolling();
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6));
                handleStepEvent(event);
              } catch (e) {
                // ignore parse errors
              }
            }
          }
        }
      } catch (err) {
        console.warn('SSE error, falling back to polling:', err);
        fallbackPolling();
      }
    };

    fetchSSE();
  };

  // Handle step event from SSE
  const handleStepEvent = (event) => {
    const { step, status, duration_ms } = event;

    if (step === 'pipeline') {
      if (status === 'done' || status === 'failed') {
        // Pipeline finished, fetch final data
        setTimeout(() => fetchData(), 500);
      }
      return;
    }

    setStepStates(prev => ({
      ...prev,
      [step]: { status, duration_ms },
    }));
  };

  // Fallback: poll every 3s if SSE fails
  const fallbackPolling = () => {
    const poll = async () => {
      const result = await fetchData();
      if (result && (result.status === 'processing' || result.status === 'pending')) {
        setTimeout(poll, 3000);
      }
    };
    poll();
  };

  useEffect(() => {
    const init = async () => {
      const result = await fetchData();
      if (result && (result.status === 'processing' || result.status === 'pending')) {
        connectSSE();
      }
    };
    init();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [id]);

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
          <svg width="48" height="48" viewBox="0 0 24 24" fill="var(--outline)">
            <path d="M11 15h2v2h-2v-2zm0-8h2v6h-2V7zm1-5C6.47 2 2 6.5 2 12a10 10 0 0020 0c0-5.5-4.47-10-10-10zm0 18a8 8 0 110-16 8 8 0 010 16z" />
          </svg>
          <p>Không tìm thấy kết quả phân tích</p>
          <Link to="/" className="btn-secondary">
            ← Quay lại
          </Link>
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
          <p style={{ color: 'var(--on-surface-variant)' }}>Quá trình phân tích mất khoảng 30-60 giây</p>
          <div className="progress-steps">
            {PIPELINE_STEPS.map((step) => {
              const state = stepStates[step.key];
              const isDone = state?.status === 'done';
              const isRunning = state?.status === 'running';
              return (
                <Step
                  key={step.key}
                  label={step.label}
                  done={isDone}
                  running={isRunning}
                  durationMs={state?.duration_ms}
                />
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  if (data.status === 'failed') {
    return (
      <div className="analysis-page">
        <div className="error-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="var(--error)">
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
          </svg>
          <h3>Phân tích thất bại</h3>
          <p style={{ color: 'var(--on-surface-variant)' }}>Vui lòng thử lại</p>
          <Link to="/" className="btn-primary" style={{ width: 'auto', padding: '0.6rem 1.5rem' }}>Thử lại</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="analysis-page">
      <div className="analysis-header">
        <Link to="/history" className="back-link">
          ← Danh sách
        </Link>
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
              <SkillList title="Kỹ năng phù hợp" icon="✓" items={data.matched_skills} type="matched" />
              <SkillList title="Kỹ năng thiếu" icon="✕" items={data.missing_skills} type="missing" />
              <SkillList title="Kỹ năng bổ sung" icon="+" items={data.extra_skills} type="extra" />
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
                      <strong>Bản gốc</strong>
                      <p>{w.original_text}</p>
                    </div>
                    <div>
                      <strong>Bản viết lại</strong>
                      <p>{w.rewritten_text}</p>
                    </div>
                  </div>
                  <p className="warning-explanation">{w.explanation}</p>
                </div>
              ))
            ) : (
              <div className="empty-warnings">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="var(--secondary)">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                </svg>
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

function SkillList({ title, icon, items, type }) {
  return (
    <div className="skill-list">
      <h4>
        <span style={{
          marginRight: '0.35rem',
          color: type === 'matched' ? 'var(--secondary)' : type === 'missing' ? 'var(--error)' : 'var(--tertiary)'
        }}>{icon}</span>
        {title}
      </h4>
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

function Step({ label, done, running, durationMs }) {
  let iconSvg;
  let className = 'step';

  if (done) {
    className += ' done';
    iconSvg = (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="var(--secondary)">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
      </svg>
    );
  } else if (running) {
    className += ' running';
    iconSvg = (
      <svg width="18" height="18" viewBox="0 0 24 24" className="spin-icon" fill="var(--primary)">
        <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0020 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 004 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z" />
      </svg>
    );
  } else {
    iconSvg = (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="var(--outline-variant)">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z" />
      </svg>
    );
  }

  return (
    <div className={className}>
      <span className="step-icon">{iconSvg}</span>
      <span>{label}</span>
      {done && durationMs && (
        <span className="step-duration">{(durationMs / 1000).toFixed(1)}s</span>
      )}
    </div>
  );
}
