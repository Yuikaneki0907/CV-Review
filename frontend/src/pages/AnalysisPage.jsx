import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { API_BASE, getAnalysis } from '../api';

const PIPELINE_STEPS = [
  { key: 'extract', label: 'Trích xuất thông tin CV' },
  { key: 'score', label: 'Matching & Scoring' },
  { key: 'rewrite', label: 'Viết lại CV' },
  { key: 'truthcheck', label: 'Kiểm tra hallucination' },
  { key: 'insights', label: 'Tạo gợi ý (AI Insights)' },
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

  // Handle step event from SSE
  const handleStepEvent = useCallback((event) => {
    const { step, status, duration_ms } = event;

    if (step === 'pipeline') {
      if (status === 'done' || status === 'completed' || status === 'failed') {
        // Pipeline finished, fetch final data
        setTimeout(() => fetchData(), 500);
      }
      return;
    }

    setStepStates(prev => ({
      ...prev,
      [step]: { status, duration_ms },
    }));
  }, [fetchData]);

  // Fallback: poll every 3s if SSE fails
  const fallbackPolling = useCallback(() => {
    const poll = async () => {
      const result = await fetchData();
      if (result && (result.status === 'processing' || result.status === 'pending')) {
        setTimeout(poll, 3000);
      }
    };
    poll();
  }, [fetchData]);

  // Connect to SSE for real-time streaming
  const connectSSE = useCallback(() => {
    const token = localStorage.getItem('token');
    if (!token) return;
    eventSourceRef.current?.abort?.();

    // EventSource doesn't support custom headers, so we use fetch-based SSE
    const url = `${API_BASE}/analysis/${id}/stream`;
    const controller = new AbortController();
    eventSourceRef.current = controller;

    const fetchSSE = async () => {
      try {
        const response = await fetch(url, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'text/event-stream',
          },
          signal: controller.signal,
        });

        if (!response.ok) {
          console.warn('SSE connection failed, falling back to polling');
          fallbackPolling();
          return;
        }

        if (!response.body) {
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
              } catch {
                // ignore parse errors
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
      if (eventSourceRef.current) {
        eventSourceRef.current.abort();
      }
    };
  }, [connectSSE, fetchData, id]);

  const hasJdEvaluation = data?.jd_evaluation && Object.keys(data.jd_evaluation).length > 0;
  const hasSalaryData = data?.salary_negotiation && Object.keys(data.salary_negotiation).length > 0;
  const jdSummary = data?.jd_evaluation?.summary || data?.jd_evaluation?.core_requirements;
  const jdDifficulty = [
    data?.jd_evaluation?.level,
    data?.jd_evaluation?.difficulty,
    data?.jd_evaluation?.years_of_experience,
  ].filter(Boolean).join(' · ') || data?.jd_evaluation?.difficulty_level;
  const jdAdvice = data?.jd_evaluation?.strategic_advice
    || (data?.jd_evaluation?.missing_info?.length
      ? `Thiếu thông tin: ${data.jd_evaluation.missing_info.join(', ')}`
      : '');
  const salaryRange = data?.salary_negotiation?.expected_salary_range || data?.salary_negotiation?.estimated_range;
  const salaryContext = data?.salary_negotiation?.market_context || data?.salary_negotiation?.negotiation_strategy;
  const salaryTips = data?.salary_negotiation?.negotiation_tips
    || [
      ...(data?.salary_negotiation?.cv_strengths || []).map((item) => `Điểm mạnh: ${item}`),
      ...(data?.salary_negotiation?.cv_weaknesses || []).map((item) => `Cần chuẩn bị: ${item}`),
    ];
  const generatedMeta = data?.analysis_meta?.source === 'generated_cv' ? data.analysis_meta : null;
  const sectionDiffs = Array.isArray(data?.section_diffs) ? data.section_diffs : [];
  const diffStats = getSectionDiffStats(sectionDiffs);

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

      {generatedMeta && (
        <GeneratedCvAnalysisNote meta={generatedMeta} scoreBreakdown={data.score_breakdown} />
      )}

      {/* Tabs */}
      <div className="tab-bar" style={{ overflowX: 'auto', display: 'flex', whiteSpace: 'nowrap' }}>
        <button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>
          Tổng quan
        </button>
        <button className={tab === 'jd_eval' ? 'active' : ''} onClick={() => setTab('jd_eval')}>
          Phân tích JD
        </button>
        <button className={tab === 'salary' ? 'active' : ''} onClick={() => setTab('salary')}>
          Đề xuất Lương
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

        {tab === 'jd_eval' && (
          <div className="jd-eval-tab fade-in">
            <h3>Phân tích JD</h3>
            {hasJdEvaluation ? (
              <div className="card-grid">
                <div className="card">
                  <h4>Yêu cầu chính</h4>
                  <p>{jdSummary || 'Chưa có tóm tắt JD'}</p>
                </div>
                <div className="card">
                  <h4>Mức độ phù hợp</h4>
                  <p>{jdDifficulty || 'Chưa xác định'}</p>
                </div>
                <div className="card">
                  <h4>Nhận xét</h4>
                  <p>{jdAdvice || 'Chưa có nhận xét bổ sung'}</p>
                </div>
              </div>
            ) : (
              <p className="empty">Chưa có dữ liệu phân tích JD</p>
            )}
          </div>
        )}

        {tab === 'salary' && (
          <div className="salary-tab fade-in">
            <h3>Đề xuất Deal Lương</h3>
            {hasSalaryData ? (
              <div className="salary-content">
                <div className="salary-range card primary-card">
                  <h4>Khoảng lương dự kiến</h4>
                  <div className="range-value">{salaryRange || 'Chưa có dữ liệu'}</div>
                  <p>{salaryContext || 'Chưa có phân tích chiến lược đàm phán'}</p>
                </div>
                <div className="card">
                  <h4>Chiến lược đàm phán</h4>
                  <ul>
                    {salaryTips?.map((tip, i) => (
                      <li key={i}>{tip}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="empty">Chưa có dữ liệu đề xuất lương</p>
            )}
          </div>
        )}

        {tab === 'diff' && (
          <div className="diff-tab">
            <h3>CV gốc vs CV đề xuất</h3>
            {sectionDiffs.length > 0 ? (
              <div className="section-diff-shell">
                <div className="section-diff-toolbar">
                  <span>Đã sửa {diffStats.modified} mục · Thêm {diffStats.added} · Xóa {diffStats.removed}</span>
                  <div className="section-diff-legend">
                    <span><i className="legend-box removed" /> Bản gốc</span>
                    <span><i className="legend-box added" /> Bản đề xuất</span>
                  </div>
                </div>
                <div className="section-diff-list">
                  {sectionDiffs.map((section, index) => (
                    <SectionDiffCard key={`${section.key}-${index}`} section={section} />
                  ))}
                </div>
              </div>
            ) : (
              <p className="empty">Không có thay đổi đáng kể để hiển thị</p>
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

function getSectionDiffStats(sections = []) {
  const added = sections.filter((section) => section.status === 'added').length;
  const removed = sections.filter((section) => section.status === 'removed').length;
  const modified = sections.filter((section) => section.status === 'modified').length;
  return {
    added,
    removed,
    modified,
  };
}

function SectionDiffCard({ section }) {
  const statusLabel = {
    added: 'Thêm mới',
    removed: 'Đã xoá',
    modified: 'Đã sửa',
  }[section.status] || 'Đã sửa';
  const removedText = section.changes?.filter((change) => change.type === 'removed').map((change) => change.text).join('\n\n');
  const addedText = section.changes?.filter((change) => change.type === 'added').map((change) => change.text).join('\n\n');

  return (
    <article className={`section-diff-card status-${section.status || 'modified'}`}>
      <header className="section-diff-card-header">
        <div>
          <span className="section-diff-kicker">Section</span>
          <h4>{section.title || 'Khác'}</h4>
        </div>
        <span className="section-diff-status">{statusLabel}</span>
      </header>
      <p className="section-diff-reason">{section.reason || 'Nội dung được điều chỉnh để phù hợp hơn.'}</p>
      <div className="section-diff-comparison">
        {removedText && (
          <div className="section-diff-panel removed">
            <strong>Bản gốc</strong>
            <pre>{removedText}</pre>
          </div>
        )}
        {addedText && (
          <div className="section-diff-panel added">
            <strong>Bản đề xuất</strong>
            <pre>{addedText}</pre>
          </div>
        )}
      </div>
    </article>
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
          <span
            key={i}
            className={`skill-tag tag-${s.category === 'needs_user_info' ? 'needs-info' : type}`}
            title={s.reason || ''}
          >
            {s.name}
            {s.category === 'needs_user_info' ? <small>Cần bổ sung dữ liệu</small> : s.category && <small>{s.category}</small>}
          </span>
        ))}
        {(!items || items.length === 0) && <span className="empty">Không có</span>}
      </div>
    </div>
  );
}

function GeneratedCvAnalysisNote({ meta, scoreBreakdown }) {
  const needs = meta?.needs_user_info || scoreBreakdown?.needs_user_info || [];
  return (
    <div className={`generated-analysis-note ${meta?.pass_ready ? 'ready' : 'needs-info'}`}>
      <div>
        <h3>{meta?.pass_ready ? 'CV generated đã sẵn sàng phân tích' : 'CV generated cần bổ sung dữ liệu thật'}</h3>
        <p>{meta?.explanation || scoreBreakdown?.note || 'Hệ thống chỉ tính các kỹ năng có bằng chứng trong CV.'}</p>
      </div>
      <div className="generated-analysis-meta">
        <span>Chế độ: {meta?.generation_mode === 'personalized' ? 'Cá nhân hóa' : 'Template/nháp'}</span>
        <span>Placeholder: {meta?.placeholder_count ?? 0}</span>
        <span>Kỹ năng cần chứng minh: {needs.length}</span>
      </div>
      {needs.length > 0 && (
        <div className="generated-analysis-skills">
          {needs.slice(0, 8).map((skill, index) => (
            <span key={`${skill}-${index}`}>{skill}</span>
          ))}
        </div>
      )}
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
