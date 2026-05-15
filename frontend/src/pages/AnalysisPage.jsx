import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { API_BASE, getAnalysis } from '../api';

// Mirrors backend/app/application/use_cases/analyze_cv.py:STEPS
const PIPELINE_STEPS = [
  { key: 'extract', label: 'Trích xuất thông tin CV & JD' },
  { key: 'score', label: 'Chấm điểm 5 chiều' },
  { key: 'done', label: 'Hoàn tất' },
];

// Canonical dimension order — matches DIMENSION_WEIGHTS in
// backend/app/domain/schemas/analysis_schema.py
const DIMENSIONS = [
  { key: 'relevance',           label: 'Phù hợp với JD',       weight: 30 },
  { key: 'keyword_coverage',    label: 'Phủ từ khoá',          weight: 25 },
  { key: 'achievement_quality', label: 'Chất lượng thành tích', weight: 20 },
  { key: 'structure',           label: 'Cấu trúc CV',           weight: 15 },
  { key: 'summary_alignment',   label: 'Summary bám JD',        weight: 10 },
];

const VERDICT_LABEL = {
  PASS: 'Đạt yêu cầu',
  BORDERLINE: 'Cận biên',
  FAIL: 'Chưa đạt',
};

const SHORT_CIRCUIT_LABEL = {
  insufficient_jd: 'JD không đủ thông tin để chấm điểm.',
  template_only_cv: 'CV vẫn còn quá nhiều placeholder, chưa có dữ kiện thật.',
};

const verdictFromScore = (score) => {
  if (score == null) return null;
  if (score >= 70) return 'PASS';
  if (score >= 50) return 'BORDERLINE';
  return 'FAIL';
};

const colorBucket = (value) => {
  if (value == null) return 'gray';
  if (value >= 80) return 'green';
  if (value >= 50) return 'yellow';
  return 'red';
};

export default function AnalysisPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stepStates, setStepStates] = useState({});
  const eventSourceRef = useRef(null);

  const fetchData = useCallback(async () => {
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
  }, [id]);

  const handleStepEvent = useCallback((event) => {
    const { step, status, duration_ms } = event;
    if (step === 'pipeline') {
      if (status === 'done' || status === 'completed' || status === 'failed') {
        setTimeout(() => fetchData(), 500);
      }
      return;
    }
    setStepStates((prev) => ({ ...prev, [step]: { status, duration_ms } }));
  }, [fetchData]);

  const fallbackPolling = useCallback(() => {
    const poll = async () => {
      const result = await fetchData();
      if (result && (result.status === 'processing' || result.status === 'pending')) {
        setTimeout(poll, 3000);
      }
    };
    poll();
  }, [fetchData]);

  const connectSSE = useCallback(() => {
    const token = localStorage.getItem('token');
    if (!token) return;
    eventSourceRef.current?.abort?.();

    const url = `${API_BASE}/analysis/${id}/stream`;
    const controller = new AbortController();
    eventSourceRef.current = controller;

    const fetchSSE = async () => {
      try {
        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'text/event-stream',
          },
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
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
                handleStepEvent(JSON.parse(line.slice(6)));
              } catch {
                /* ignore parse errors */
              }
            }
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        console.warn('SSE error, falling back to polling:', err);
        fallbackPolling();
      } finally {
        if (eventSourceRef.current === controller) {
          eventSourceRef.current = null;
        }
      }
    };

    fetchSSE();
  }, [fallbackPolling, handleStepEvent, id]);

  useEffect(() => {
    const init = async () => {
      const result = await fetchData();
      if (result && (result.status === 'processing' || result.status === 'pending')) {
        connectSSE();
      }
    };
    init();
    return () => {
      eventSourceRef.current?.abort?.();
    };
  }, [connectSSE, fetchData, id]);

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
          <h3>Không tìm thấy kết quả phân tích</h3>
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
          <p style={{ color: 'var(--on-surface-variant)' }}>
            Quá trình phân tích thường mất 15-40 giây.
          </p>
          <div className="progress-steps">
            {PIPELINE_STEPS.map((step) => {
              const state = stepStates[step.key];
              return (
                <Step
                  key={step.key}
                  label={step.label}
                  done={state?.status === 'done'}
                  running={state?.status === 'running'}
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
          <h3>Phân tích thất bại</h3>
          <p style={{ color: 'var(--on-surface-variant)' }}>Vui lòng thử lại.</p>
          <Link to="/" className="btn-primary" style={{ width: 'auto', padding: '0.6rem 1.5rem' }}>
            Thử lại
          </Link>
        </div>
      </div>
    );
  }

  // ─── New-schema panels ─────────────────────────────────────────
  const breakdown = data?.score_breakdown || {};
  const verdict = breakdown.verdict || verdictFromScore(data?.score?.overall);
  const dimensionScores = breakdown.dimension_scores || {};
  const gapAnalysis = breakdown.gap_analysis || { critical_missing: [], improvable: [] };
  const keywordReport = breakdown.keyword_report || { found: [], missing: [], density_ok: true };
  const suggestions = Array.isArray(breakdown.suggestions) ? breakdown.suggestions : [];
  const shortCircuit = data?.analysis_meta?.short_circuit || null;
  const hasNewSchema = Boolean(breakdown.dimension_scores);

  return (
    <div className="analysis-page">
      <div className="analysis-header">
        <Link to="/history" className="back-link">← Danh sách</Link>
        <h2>{data.cv_filename}</h2>
        <span className={`status-badge status-${data.status}`}>{data.status}</span>
      </div>

      {/* Headline: overall score + verdict */}
      {data.score && (
        <div className="analysis-headline">
          <ScoreCard label="Tổng điểm" value={data.score.overall} large />
          {verdict && <VerdictBadge verdict={verdict} />}
        </div>
      )}

      {shortCircuit && (
        <div className="analysis-shortcircuit-note">
          <strong>Phân tích dừng sớm:</strong>{' '}
          {SHORT_CIRCUIT_LABEL[shortCircuit] || `Lý do: ${shortCircuit}`}
        </div>
      )}

      {/* 5-dimension breakdown */}
      {hasNewSchema && (
        <section className="analysis-section">
          <h3>Phân tích 5 chiều</h3>
          <div className="dimension-grid">
            {DIMENSIONS.map((dim) => {
              const entry = dimensionScores[dim.key];
              if (!entry) return null;
              return (
                <DimensionCard
                  key={dim.key}
                  label={dim.label}
                  weight={dim.weight}
                  score={entry.score}
                  reason={entry.reason}
                />
              );
            })}
          </div>
        </section>
      )}

      {/* Keyword report */}
      {hasNewSchema && (
        <section className="analysis-section">
          <h3>Phủ từ khoá JD</h3>
          <KeywordReportPanel report={keywordReport} />
        </section>
      )}

      {/* Gap analysis — what to fix */}
      {hasNewSchema && (
        <section className="analysis-section">
          <h3>Cần cải thiện</h3>
          <GapAnalysisPanel gap={gapAnalysis} />
        </section>
      )}

      {/* Concrete rewrite suggestions */}
      {hasNewSchema && suggestions.length > 0 && (
        <section className="analysis-section">
          <h3>Gợi ý chỉnh sửa cụ thể ({suggestions.length})</h3>
          <SuggestionsPanel suggestions={suggestions} />
        </section>
      )}

      {/* Defensive fallback for old analyses without new schema */}
      {!hasNewSchema && (data.matched_skills || data.missing_skills) && (
        <section className="analysis-section">
          <h3>Kỹ năng (legacy)</h3>
          <div className="skills-grid">
            <SkillList title="Kỹ năng phù hợp" icon="✓" items={data.matched_skills} type="matched" />
            <SkillList title="Kỹ năng thiếu" icon="✕" items={data.missing_skills} type="missing" />
          </div>
        </section>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Sub-components
// ────────────────────────────────────────────────────────────────

function VerdictBadge({ verdict }) {
  const cls = `verdict-badge verdict-${verdict.toLowerCase()}`;
  return (
    <span className={cls}>
      <strong>{verdict}</strong>
      <small>{VERDICT_LABEL[verdict] || ''}</small>
    </span>
  );
}

function ScoreCard({ label, value, large }) {
  const color = colorBucket(value);
  return (
    <div className={`score-card ${large ? 'large' : ''} score-${color}`}>
      <div className="score-value">{value ?? '—'}</div>
      <div className="score-label">{label}</div>
    </div>
  );
}

function DimensionCard({ label, weight, score, reason }) {
  const color = colorBucket(score);
  return (
    <div className={`dimension-card score-${color}`}>
      <div className="dimension-card-head">
        <span className="dimension-card-label">{label}</span>
        <span className="dimension-card-weight">{weight}%</span>
      </div>
      <div className="dimension-card-score">{Math.round(score ?? 0)}</div>
      {reason && <p className="dimension-card-reason">{reason}</p>}
    </div>
  );
}

function KeywordReportPanel({ report }) {
  const found = Array.isArray(report?.found) ? report.found : [];
  const missing = Array.isArray(report?.missing) ? report.missing : [];
  const densityOk = Boolean(report?.density_ok);
  return (
    <div className="keyword-report">
      <div className="keyword-density">
        <span className={`density-pill ${densityOk ? 'density-ok' : 'density-low'}`}>
          {densityOk ? '✓ Mật độ từ khoá đạt ngưỡng ATS' : '⚠ Mật độ từ khoá dưới ngưỡng ATS'}
        </span>
      </div>
      <div className="keyword-cols">
        <div className="keyword-col">
          <h4>Có trong CV ({found.length})</h4>
          <div className="keyword-tags">
            {found.length > 0
              ? found.map((kw, i) => <span key={i} className="keyword-tag tag-matched">{kw}</span>)
              : <span className="empty">Chưa có từ khoá nào trùng JD.</span>}
          </div>
        </div>
        <div className="keyword-col">
          <h4>Thiếu so với JD ({missing.length})</h4>
          <div className="keyword-tags">
            {missing.length > 0
              ? missing.map((kw, i) => <span key={i} className="keyword-tag tag-missing">{kw}</span>)
              : <span className="empty">Đã phủ kín từ khoá JD.</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

function GapAnalysisPanel({ gap }) {
  const critical = Array.isArray(gap?.critical_missing) ? gap.critical_missing : [];
  const improvable = Array.isArray(gap?.improvable) ? gap.improvable : [];
  if (critical.length === 0 && improvable.length === 0) {
    return <p className="empty">Không phát hiện điểm yếu lớn nào.</p>;
  }
  return (
    <div className="gap-analysis">
      {critical.length > 0 && (
        <div className="gap-bucket gap-critical">
          <h4>Bắt buộc sửa ({critical.length})</h4>
          <ul>
            {critical.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}
      {improvable.length > 0 && (
        <div className="gap-bucket gap-improvable">
          <h4>Có thể cải thiện ({improvable.length})</h4>
          <ul>
            {improvable.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function SuggestionsPanel({ suggestions }) {
  return (
    <div className="suggestions-list">
      {suggestions.map((s, i) => (
        <article key={i} className="suggestion-card">
          <header>
            <span className="suggestion-section">{s.section}</span>
            <span className="suggestion-issue">{s.issue}</span>
          </header>
          {s.current && (
            <div className="suggestion-row">
              <strong>Hiện tại:</strong>
              <p className="suggestion-current">{s.current}</p>
            </div>
          )}
          {s.suggested && (
            <div className="suggestion-row">
              <strong>Đề xuất:</strong>
              <p className="suggestion-suggested">{s.suggested}</p>
            </div>
          )}
        </article>
      ))}
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
          <span key={i} className={`skill-tag tag-${type}`}>{s.name}</span>
        ))}
        {(!items || items.length === 0) && <span className="empty">Không có</span>}
      </div>
    </div>
  );
}

function Step({ label, done, running, durationMs }) {
  let className = 'step';
  let iconSvg;
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
      {done && durationMs && <span className="step-duration">{(durationMs / 1000).toFixed(1)}s</span>}
    </div>
  );
}
