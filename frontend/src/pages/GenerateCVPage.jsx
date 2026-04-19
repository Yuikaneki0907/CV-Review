import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowUpTrayIcon, DocumentMagnifyingGlassIcon, DocumentPlusIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import { importGeneratedCV, streamChatAnalysis } from '../api';
import { notifyGeneratedCvHistoryChanged } from '../utils/generatedCvHistory';
import {
  getInterviewQuestionNote,
  getJdEvaluationAdvice,
  getJdEvaluationSummary,
  getSalaryAdvice,
  getSalaryRange,
} from '../utils/analysisInsights';
import { TEMPLATE_SKELETONS } from '../utils/templateSkeletons';

const TEMPLATE_CARDS = [
  { id: 'ats_clean', label: 'ATS-Friendly', accent: 'blue' },
  { id: 'executive', label: 'Executive / Senior', accent: 'navy' },
  { id: 'tech_engineer', label: 'Tech / Engineer', accent: 'tech' },
  { id: 'fresh_graduate', label: 'Fresh Graduate', accent: 'orange' },
];

const parseTemplatePreview = (templateId) => {
  const content = TEMPLATE_SKELETONS[templateId] || '';
  const lines = content.split('\n').map((line) => line.trim()).filter(Boolean);
  const titleIndex = lines.findIndex((line) => line.startsWith('# '));
  const name = titleIndex >= 0 ? lines[titleIndex].replace(/^#\s+/, '') : 'Template CV';
  const subtitle = titleIndex >= 0 && lines[titleIndex + 1] && !lines[titleIndex + 1].startsWith('#')
    ? lines[titleIndex + 1]
    : '';
  const sections = lines
    .filter((line) => line.startsWith('## '))
    .map((line) => line.replace(/^##\s+/, ''))
    .slice(0, 5);

  return { name, subtitle, sections };
};

function TemplatePreviewCard({ template, onClick }) {
  const preview = parseTemplatePreview(template.id);
  const centered = template.accent === 'orange' || template.accent === 'blue';
  const sectionClass = template.accent === 'orange' ? 'tpl-m-h orange' : 'tpl-m-h';

  return (
    <button className="tpl-preview-card" onClick={() => onClick(template.id)}>
      <div className={`tpl-page tpl-template-preview tpl-preview-${template.accent}`}>
        {template.accent === 'navy' && <div className="tpl-m-bar navy" />}
        {template.accent === 'tech' && <div className="tpl-m-bar tech" />}
        <div className={`tpl-m-name ${centered ? 'center' : ''}`}>{preview.name}</div>
        {preview.subtitle && <div className={`tpl-m-sub ${centered ? 'center' : ''}`}>{preview.subtitle}</div>}
        <div className={`tpl-m-hr ${template.accent === 'orange' ? 'accent' : ''}`} />
        {preview.sections.map((section, index) => (
          <div key={section} className="tpl-section-preview">
            <div className={sectionClass}>{section}</div>
            {index < 3 ? (
              <>
                <div className={`tpl-m-line ${index % 2 === 0 ? 'w85' : 'w75'}`} />
                <div className={`tpl-m-line ${index % 2 === 0 ? 'w65' : 'w55'}`} />
              </>
            ) : (
              <div className="tpl-m-line w70" />
            )}
          </div>
        ))}
      </div>
      <span className="tpl-card-name">{template.label}</span>
    </button>
  );
}

export default function GenerateCVPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState('create');
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const importFileRef = useRef(null);

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
    navigate('/workspace', { state: { initialPrompt: prompt } });
  };

  const handleTemplateClick = (templateId) => {
    const templateTitles = {
      ats_clean: 'ATS-Friendly',
      executive: 'Executive / Senior',
      tech_engineer: 'Tech / Engineer',
      fresh_graduate: 'Fresh Graduate',
    };
    navigate(`/workspace?template=${templateId}`, {
      state: {
        templateId,
        templateTitle: templateTitles[templateId] || 'Template CV',
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

  const handleImportCv = async (file) => {
    if (!file || importing) return;

    setImportError('');
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append('cv_file', file);
      const res = await importGeneratedCV(formData);
      notifyGeneratedCvHistoryChanged();
      navigate(`/workspace/${res.data.id}`);
    } catch (error) {
      console.error('Failed to import CV into workspace:', error);
      setImportError(error.response?.data?.detail || 'Không thể import CV vào workspace');
    } finally {
      if (importFileRef.current) {
        importFileRef.current.value = '';
      }
      setImporting(false);
    }
  };

  const STEP_KEYS = ['extract', 'score', 'rewrite', 'truthcheck', 'insights', 'diff'];

  const ModeTitleIcon = mode === 'create' ? DocumentPlusIcon : DocumentMagnifyingGlassIcon;

  return (
    <div className="prompter-page fade-in">
      <div className="prompter-container">
        <div className="prompter-header">
          <div className="ai-badge">
            <SparklesIcon className="badge-icon" />
            <span>AI Resume Builder</span>
          </div>
          <h1 className="prompter-title">
            <ModeTitleIcon className="prompter-title-icon" />
            <span>{mode === 'create' ? 'Tạo CV mới' : 'Phân tích CV'}</span>
          </h1>
          <p className="prompter-subtitle">
            {mode === 'create'
              ? 'Nhập prompt để bắt đầu từ blank document, hoặc chọn template hay upload CV có sẵn ở bên dưới.'
              : 'Upload CV và thêm Job Description bằng text hoặc file để AI phân tích, chấm điểm và tối ưu.'}
          </p>
        </div>

        {/* Mode Toggle */}
        <div className="prompter-mode-toggle">
          <button type="button" className={`mode-tab ${mode === 'create' ? 'active' : ''}`} onClick={() => setMode('create')}>
            <DocumentPlusIcon className="mode-tab-icon" />
            <span>Tạo CV mới</span>
          </button>
          <button type="button" className={`mode-tab ${mode === 'analyze' ? 'active' : ''}`} onClick={() => setMode('analyze')}>
            <DocumentMagnifyingGlassIcon className="mode-tab-icon" />
            <span>Phân tích CV</span>
          </button>
        </div>

        {/* ═══ CREATE MODE ═══ */}
        {mode === 'create' && (
          <>
            {importError && <div className="analyze-error">{importError}</div>}
            <div className="prompter-create-stack">
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
              <p className="prompter-helper-text">
                Ô nhập phía trên là luồng tạo CV mới từ trắng. Nếu đã có CV sẵn, dùng thẻ upload ở ngay bên dưới để mở vào workspace và chỉnh sửa tiếp.
              </p>

              {/* ── Template Gallery ── */}
              <div className="tpl-gallery">
                <div className="tpl-gallery-grid">
                  <button
                    className="tpl-preview-card"
                    onClick={() => importFileRef.current?.click()}
                    disabled={importing}
                  >
                    <input
                      ref={importFileRef}
                      type="file"
                      accept=".pdf,.docx"
                      hidden
                      onChange={(e) => handleImportCv(e.target.files[0])}
                    />
                    <div className="tpl-page import-card">
                      <div className="tpl-import-icon-wrap">
                        <ArrowUpTrayIcon className="tpl-import-icon" />
                      </div>
                      <div className="tpl-import-title">
                        {importing ? 'Đang import...' : 'Upload CV để sửa'}
                      </div>
                      <div className="tpl-import-subtitle">
                        {importing ? 'Đang trích xuất nội dung và mở workspace' : 'PDF hoặc DOCX'}
                      </div>
                      <div className="tpl-import-steps">
                        <span>Import</span>
                        <span>Edit</span>
                        <span>Version</span>
                      </div>
                    </div>
                    <span className="tpl-card-name">Upload CV để sửa</span>
                  </button>

                  {TEMPLATE_CARDS.map((template) => (
                    <TemplatePreviewCard
                      key={template.id}
                      template={template}
                      onClick={handleTemplateClick}
                    />
                  ))}
                </div>
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
                      accept=".pdf,.docx,.txt,.md"
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
                        <small>PDF, DOCX, TXT, MD</small>
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
