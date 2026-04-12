import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { SparklesIcon } from '@heroicons/react/24/outline';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import { streamChatAnalysis } from '../api';
import {
  getInterviewQuestionNote,
  getJdEvaluationAdvice,
  getJdEvaluationSummary,
  getSalaryAdvice,
  getSalaryRange,
} from '../utils/analysisInsights';
import { TEMPLATE_SKELETONS } from '../utils/templateSkeletons';

export default function GenerateCVPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState('create');
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  // Analysis state
  const [cvFile, setCvFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [jdFile, setJdFile] = useState(null);
  const [jdMode, setJdMode] = useState('text');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisSteps, setAnalysisSteps] = useState({});
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analysisError, setAnalysisError] = useState('');
  const [analysisId, setAnalysisId] = useState(null);
  const cvFileRef = useRef(null);
  const jdFileRef = useRef(null);

  useEffect(() => {
    if (location.state?.mode === 'analyze') {
      setMode('analyze');
    }
  }, [location.state]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    navigate('/workspace', { state: { initialPrompt: prompt, templateId: selectedTemplate } });
  };

  const handleTemplateClick = (templateId) => {
    const labels = {
      ats_clean: 'Tạo CV ATS-Friendly cho tôi',
      executive: 'Tạo CV Executive/Senior cho tôi',
      tech_engineer: 'Tạo CV Software Engineer cho tôi',
      fresh_graduate: 'Tạo CV Fresh Graduate cho tôi',
    };
    navigate('/workspace', {
      state: {
        initialPrompt: labels[templateId],
        templateId,
        templateContent: TEMPLATE_SKELETONS[templateId] || '',
      },
    });
  };

  const handleAnalyze = async () => {
    const hasJdInput = jdMode === 'file' ? Boolean(jdFile) : Boolean(jdText.trim());
    if (!cvFile || !hasJdInput || analyzing) return;
    setAnalyzing(true);
    setAnalysisSteps({});
    setAnalysisResults(null);
    setAnalysisError('');
    setAnalysisId(null);

    try {
      await streamChatAnalysis(cvFile, jdMode === 'text' ? jdText : '', jdMode === 'file' ? jdFile : null, ({ event, data }) => {
        if (event === 'analysis_step') {
          setAnalysisSteps((prev) => ({ ...prev, [data.step]: { status: data.status, label: data.label, duration_ms: data.duration_ms } }));
        } else if (event === 'analysis_result') {
          setAnalysisResults((prev) => ({ ...(prev || {}), [data.type]: data.data }));
        } else if (event === 'analysis_done') {
          setAnalysisId(data.analysis_id);
        } else if (event === 'analysis_error') {
          setAnalysisError(data.error || 'Có lỗi xảy ra');
        }
      });
    } catch (e) {
      console.error('Analysis failed:', e);
      setAnalysisError('Kết nối thất bại. Vui lòng thử lại.');
    } finally {
      setAnalyzing(false);
    }
  };

  const STEP_KEYS = ['extract', 'score', 'rewrite', 'truthcheck', 'insights', 'diff'];

  return (
    <div className="prompter-page fade-in">
      <div className="prompter-container" style={{ maxWidth: mode === 'analyze' ? '860px' : '900px' }}>
        <div className="prompter-header">
          <div className="ai-badge">
            <SparklesIcon className="badge-icon" />
            <span>AI Resume Builder</span>
          </div>
          <h1 className="prompter-title">
            {mode === 'create' ? 'Khởi tạo CV Chuyên Nghiệp' : '🔬 Phân tích CV'}
          </h1>
          <p className="prompter-subtitle">
            {mode === 'create'
              ? 'Mô tả vị trí bạn muốn ứng tuyển hoặc chọn một mẫu CV bên dưới.'
              : 'Upload CV và thêm Job Description bằng text hoặc file để AI phân tích, chấm điểm và tối ưu.'}
          </p>
        </div>

        {/* Mode Toggle */}
        <div className="prompter-mode-toggle">
          <button className={`mode-tab ${mode === 'create' ? 'active' : ''}`} onClick={() => setMode('create')}>
            ✨ Tạo CV mới
          </button>
          <button className={`mode-tab ${mode === 'analyze' ? 'active' : ''}`} onClick={() => setMode('analyze')}>
            📎 Phân tích CV
          </button>
        </div>

        {/* ═══ CREATE MODE ═══ */}
        {mode === 'create' && (
          <>
            <form className="prompter-form" onSubmit={handleSubmit}>
              <div className="prompter-input-wrapper">
                <input
                  type="text"
                  className="prompter-input"
                  placeholder="Mô tả CV bạn muốn tạo (VD: Senior Frontend Developer 5 năm kinh nghiệm React)..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  autoFocus
                />
                <button type="submit" className={`prompter-submit-btn ${prompt.trim() ? 'active' : ''}`} disabled={!prompt.trim()}>
                  <PaperAirplaneIcon className="submit-icon" />
                </button>
              </div>
            </form>

            {/* ── Template Gallery ── */}
            <div className="tpl-gallery">
              <div className="tpl-gallery-grid">
                {/* Blank */}
                <button className="tpl-preview-card" onClick={() => { setSelectedTemplate(null); }}>
                  <div className="tpl-page blank">
                    <span className="tpl-blank-plus">+</span>
                  </div>
                  <span className="tpl-card-name">Blank document</span>
                </button>

                {/* ATS-Friendly */}
                <button className="tpl-preview-card" onClick={() => handleTemplateClick('ats_clean')}>
                  <div className="tpl-page">
                    <div className="tpl-m-name">NGUYEN VAN A</div>
                    <div className="tpl-m-sub">Software Engineer</div>
                    <div className="tpl-m-hr"></div>
                    <div className="tpl-m-h">PROFESSIONAL SUMMARY</div>
                    <div className="tpl-m-line w80"></div>
                    <div className="tpl-m-line w65"></div>
                    <div className="tpl-m-h">EXPERIENCE</div>
                    <div className="tpl-m-line w90"></div>
                    <div className="tpl-m-line w70"></div>
                    <div className="tpl-m-line w55"></div>
                    <div className="tpl-m-h">EDUCATION</div>
                    <div className="tpl-m-line w75"></div>
                    <div className="tpl-m-h">SKILLS</div>
                    <div className="tpl-m-line w85"></div>
                  </div>
                  <span className="tpl-card-name">ATS-Friendly</span>
                </button>

                {/* Executive */}
                <button className="tpl-preview-card" onClick={() => handleTemplateClick('executive')}>
                  <div className="tpl-page">
                    <div className="tpl-m-bar navy"></div>
                    <div className="tpl-m-name" style={{ marginTop: '2px' }}>TRAN THI B</div>
                    <div className="tpl-m-sub">Director of Operations</div>
                    <div className="tpl-m-h">EXECUTIVE SUMMARY</div>
                    <div className="tpl-m-line w85"></div>
                    <div className="tpl-m-line w70"></div>
                    <div className="tpl-m-h">KEY ACHIEVEMENTS</div>
                    <div className="tpl-m-bullet w80"></div>
                    <div className="tpl-m-bullet w65"></div>
                    <div className="tpl-m-bullet w75"></div>
                    <div className="tpl-m-h">EXPERIENCE</div>
                    <div className="tpl-m-line w90"></div>
                    <div className="tpl-m-line w60"></div>
                  </div>
                  <span className="tpl-card-name">Executive / Senior</span>
                </button>

                {/* Tech */}
                <button className="tpl-preview-card" onClick={() => handleTemplateClick('tech_engineer')}>
                  <div className="tpl-page with-sidebar">
                    <div className="tpl-m-sidebar">
                      <div className="tpl-m-sh">SKILLS</div>
                      <div className="tpl-m-sline"></div>
                      <div className="tpl-m-sline short"></div>
                      <div className="tpl-m-sline"></div>
                      <div className="tpl-m-sh">TOOLS</div>
                      <div className="tpl-m-sline short"></div>
                      <div className="tpl-m-sline"></div>
                    </div>
                    <div className="tpl-m-main">
                      <div className="tpl-m-name">LE VAN C</div>
                      <div className="tpl-m-sub">Full-Stack Developer</div>
                      <div className="tpl-m-h">EXPERIENCE</div>
                      <div className="tpl-m-line w85"></div>
                      <div className="tpl-m-line w70"></div>
                      <div className="tpl-m-h">PROJECTS</div>
                      <div className="tpl-m-line w80"></div>
                      <div className="tpl-m-line w55"></div>
                    </div>
                  </div>
                  <span className="tpl-card-name">Tech / Engineer</span>
                </button>

                {/* Fresh Graduate */}
                <button className="tpl-preview-card" onClick={() => handleTemplateClick('fresh_graduate')}>
                  <div className="tpl-page">
                    <div className="tpl-m-name center">PHAM THI D</div>
                    <div className="tpl-m-sub center">Marketing Intern</div>
                    <div className="tpl-m-hr accent"></div>
                    <div className="tpl-m-h orange">OBJECTIVE</div>
                    <div className="tpl-m-line w80"></div>
                    <div className="tpl-m-h orange">EDUCATION</div>
                    <div className="tpl-m-line w75"></div>
                    <div className="tpl-m-line w55"></div>
                    <div className="tpl-m-h orange">PROJECTS</div>
                    <div className="tpl-m-line w85"></div>
                    <div className="tpl-m-h orange">ACTIVITIES</div>
                    <div className="tpl-m-line w70"></div>
                  </div>
                  <span className="tpl-card-name">Fresh Graduate</span>
                </button>
              </div>
            </div>
          </>
        )}

        {/* ═══ ANALYZE MODE ═══ */}
        {mode === 'analyze' && (
          <div className="analyze-section">
            <div className="analyze-upload-grid">
              <div className="analyze-upload-card">
                <h3>📄 CV / Resume</h3>
                <div className="analyze-dropzone" onClick={() => cvFileRef.current?.click()}>
                  <input ref={cvFileRef} type="file" accept=".pdf,.docx" onChange={(e) => setCvFile(e.target.files[0])} hidden />
                  {cvFile ? (
                    <div className="analyze-file-selected">
                      <span style={{ color: 'var(--secondary)', fontSize: '1.5rem' }}>✓</span>
                      <span className="analyze-file-name">{cvFile.name}</span>
                      <small style={{ color: 'var(--on-surface-variant)' }}>({(cvFile.size / 1024).toFixed(0)} KB)</small>
                    </div>
                  ) : (
                    <div className="analyze-file-empty">
                      <span style={{ fontSize: '2rem', color: 'var(--outline)' }}>📤</span>
                      <span>Kéo thả file hoặc click để chọn</span>
                      <small>PDF, DOCX</small>
                    </div>
                  )}
                </div>
              </div>
              <div className="analyze-upload-card">
                <h3>📋 Job Description</h3>
                <div className="jd-mode-toggle" style={{ marginBottom: '1rem' }}>
                  <button
                    type="button"
                    className={`jd-tab ${jdMode === 'text' ? 'active' : ''}`}
                    onClick={() => setJdMode('text')}
                  >
                    Nhập text
                  </button>
                  <button
                    type="button"
                    className={`jd-tab ${jdMode === 'file' ? 'active' : ''}`}
                    onClick={() => setJdMode('file')}
                  >
                    Upload file
                  </button>
                </div>
                {jdMode === 'text' ? (
                  <textarea
                    className="analyze-jd-textarea"
                    value={jdText}
                    onChange={(e) => setJdText(e.target.value)}
                    placeholder={"Dán nội dung Job Description tại đây...\n\nVí dụ:\n- Yêu cầu 3 năm kinh nghiệm Python...\n- Kỹ năng: FastAPI, Docker, PostgreSQL..."}
                    rows={8}
                  />
                ) : (
                  <div className="analyze-dropzone" onClick={() => jdFileRef.current?.click()}>
                    <input
                      ref={jdFileRef}
                      type="file"
                      accept=".pdf,.docx"
                      onChange={(e) => setJdFile(e.target.files[0])}
                      hidden
                    />
                    {jdFile ? (
                      <div className="analyze-file-selected">
                        <span style={{ color: 'var(--secondary)', fontSize: '1.5rem' }}>✓</span>
                        <span className="analyze-file-name">{jdFile.name}</span>
                        <small style={{ color: 'var(--on-surface-variant)' }}>({(jdFile.size / 1024).toFixed(0)} KB)</small>
                      </div>
                    ) : (
                      <div className="analyze-file-empty">
                        <span style={{ fontSize: '2rem', color: 'var(--outline)' }}>📤</span>
                        <span>Chọn file JD</span>
                        <small>PDF, DOCX</small>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <button
              className="btn-primary analyze-start-btn"
              disabled={!cvFile || (jdMode === 'text' ? !jdText.trim() : !jdFile) || analyzing}
              onClick={handleAnalyze}
            >
              {analyzing ? '⏳ Đang phân tích...' : '🔬 Bắt đầu phân tích'}
            </button>

            {Object.keys(analysisSteps).length > 0 && (
              <div className="analyze-progress-card">
                <h3>🔬 Tiến trình phân tích</h3>
                <div className="analyze-steps">
                  {STEP_KEYS.map((key) => {
                    const step = analysisSteps[key];
                    if (!step) return <div key={key} className="analyze-step pending"><span className="step-dot">⬜</span> <span>{key}</span></div>;
                    const isDone = step.status === 'done';
                    const isRunning = step.status === 'running';
                    return (
                      <div key={key} className={`analyze-step ${isDone ? 'done' : ''} ${isRunning ? 'running' : ''}`}>
                        <span className="step-dot">{isDone ? '✅' : isRunning ? '⏳' : '⬜'}</span>
                        <span className="step-text">{step.label || key}</span>
                        {isDone && step.duration_ms && <span className="step-time">{(step.duration_ms / 1000).toFixed(1)}s</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {analysisError && <div className="analyze-error">❌ {analysisError}</div>}

            {analysisResults?.scores && (
              <div className="analyze-results-section">
                <h3>📊 Điểm số</h3>
                <div className="analyze-scores-grid">
                  {[
                    { label: 'Tổng điểm', value: analysisResults.scores.overall, large: true },
                    { label: 'Kỹ năng', value: analysisResults.scores.skills_score },
                    { label: 'Kinh nghiệm', value: analysisResults.scores.experience_score },
                    { label: 'Công cụ', value: analysisResults.scores.tools_score },
                  ].map((s, i) => {
                    const color = s.value >= 80 ? 'green' : s.value >= 50 ? 'yellow' : 'red';
                    return (
                      <div key={i} className={`analyze-score-card score-${color} ${s.large ? 'large' : ''}`}>
                        <div className="score-value">{s.value}</div>
                        <div className="score-label">{s.label}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {analysisResults?.skills && (
              <div className="analyze-results-section">
                <h3>🎯 Kỹ năng</h3>
                <div className="analyze-skills-groups">
                  {analysisResults.skills.matched?.length > 0 && (
                    <div className="skill-group"><h4>✓ Phù hợp ({analysisResults.skills.matched.length})</h4><div className="skill-tags">{analysisResults.skills.matched.map((s, i) => <span key={i} className="skill-tag tag-matched">{s.name}</span>)}</div></div>
                  )}
                  {analysisResults.skills.missing?.length > 0 && (
                    <div className="skill-group"><h4>✕ Thiếu ({analysisResults.skills.missing.length})</h4><div className="skill-tags">{analysisResults.skills.missing.map((s, i) => <span key={i} className="skill-tag tag-missing">{s.name}</span>)}</div></div>
                  )}
                  {analysisResults.skills.extra?.length > 0 && (
                    <div className="skill-group"><h4>+ Bổ sung ({analysisResults.skills.extra.length})</h4><div className="skill-tags">{analysisResults.skills.extra.map((s, i) => <span key={i} className="skill-tag tag-extra">{s.name}</span>)}</div></div>
                  )}
                </div>
              </div>
            )}

            {analysisResults?.insights && (
              <div className="analyze-results-section">
                <h3>💡 Phân tích nâng cao</h3>
                <div className="analyze-insights-grid">
                  {analysisResults.insights.jd_evaluation && (
                    <div className="insight-card">
                      <h4>📋 Phân tích JD</h4>
                      <p><strong>Tóm tắt:</strong> {getJdEvaluationSummary(analysisResults.insights.jd_evaluation) || 'Chưa có dữ liệu'}</p>
                      <p><strong>Nhận xét:</strong> {getJdEvaluationAdvice(analysisResults.insights.jd_evaluation) || 'Chưa có dữ liệu'}</p>
                    </div>
                  )}
                  {analysisResults.insights.salary_negotiation && (
                    <div className="insight-card">
                      <h4>💰 Đề xuất lương</h4>
                      <p className="salary-range">{getSalaryRange(analysisResults.insights.salary_negotiation) || 'Chưa có dữ liệu'}</p>
                      <p>{getSalaryAdvice(analysisResults.insights.salary_negotiation) || 'Chưa có dữ liệu'}</p>
                    </div>
                  )}
                  {analysisResults.insights.interview_questions?.length > 0 && (
                    <div className="insight-card full-width">
                      <h4>🎤 Gợi ý câu hỏi phỏng vấn</h4>
                      <ul>
                        {analysisResults.insights.interview_questions.map((q, i) => (
                          <li key={i}><strong>Q:</strong> {q.question}{getInterviewQuestionNote(q) && <em style={{ display: 'block', color: 'var(--on-surface-variant)', fontSize: '0.75rem' }}>Gợi ý thêm: {getInterviewQuestionNote(q)}</em>}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {analysisResults?.rewritten_cv && (
              <div className="analyze-results-section">
                <h3>📝 CV Tối ưu (Đề xuất)</h3>
                <div className="analyze-rewritten-cv"><pre>{analysisResults.rewritten_cv}</pre></div>
              </div>
            )}

            {analysisId && (
              <div className="analyze-done-banner">
                ✅ Phân tích hoàn tất!{' '}
                <a href={`/analysis/${analysisId}`} className="analyze-detail-link">Xem chi tiết đầy đủ →</a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
