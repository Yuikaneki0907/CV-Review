import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowPathIcon,
  ArrowUpTrayIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  DocumentMagnifyingGlassIcon,
  DocumentPlusIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
  LightBulbIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import { createAnalysisFromGeneratedCV, getAnalysis, listGeneratedCVs, streamChatAnalysis } from '../api';
import {
  getJdEvaluationAdvice,
  getJdEvaluationSummary,
  getSalaryAdvice,
  getSalaryRange,
} from '../utils/analysisInsights';

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return dateStr;
  return date.toLocaleString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'Asia/Ho_Chi_Minh',
  });
};

const getCvTitle = (item) =>
  item?.chat_title || item?.job_title || item?.source_filename || 'CV chưa đặt tên';

const mapAnalysisResponseToResults = (analysis) => ({
  scores: analysis?.score || null,
  skills: {
    matched: Array.isArray(analysis?.matched_skills) ? analysis.matched_skills : [],
    missing: Array.isArray(analysis?.missing_skills) ? analysis.missing_skills : [],
    extra: Array.isArray(analysis?.extra_skills) ? analysis.extra_skills : [],
  },
  insights: {
    jd_evaluation: analysis?.jd_evaluation || null,
    salary_negotiation: analysis?.salary_negotiation || null,
    interview_questions: Array.isArray(analysis?.interview_questions) ? analysis.interview_questions : [],
  },
  rewritten_cv: analysis?.rewritten_cv || '',
  analysis_meta: analysis?.analysis_meta || null,
  score_breakdown: analysis?.score_breakdown || null,
});

export default function GenerateCVPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState('create');

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
  const [selectedCvFromLibrary, setSelectedCvFromLibrary] = useState(null);
  const [cvSourceType, setCvSourceType] = useState(null);
  const [cvPickerOpen, setCvPickerOpen] = useState(false);
  const [cvPickerFilter, setCvPickerFilter] = useState('all');
  const [cvLibrary, setCvLibrary] = useState([]);
  const [cvLibraryLoading, setCvLibraryLoading] = useState(false);
  const [cvLibraryError, setCvLibraryError] = useState('');
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

  const handleAnalyze = async () => {
    const hasJdInput = jdMode === 'file' ? Boolean(jdFile) : Boolean(jdText.trim());
    const hasCvSource = cvSourceType === 'file' ? Boolean(cvFile) : cvSourceType === 'library' ? Boolean(selectedCvFromLibrary?.id) : false;
    if (!hasCvSource || !hasJdInput || analyzing) return;
    setAnalyzing(true);
    setAnalysisSteps({});
    setAnalysisResults(null);
    setAnalysisError('');
    setAnalysisId(null);

    try {
      if (cvSourceType === 'library' && selectedCvFromLibrary?.id) {
        setAnalysisSteps({
          extract: { status: 'running', label: 'Chuẩn bị dữ liệu CV đã chọn...' },
        });

        const createRes = await createAnalysisFromGeneratedCV(
          selectedCvFromLibrary.id,
          jdMode === 'text' ? jdText : '',
          jdMode === 'file' ? jdFile : null
        );

        const createdAnalysisId = createRes?.data?.id;
        if (!createdAnalysisId) {
          throw new Error('Không nhận được mã phân tích');
        }
        setAnalysisId(createdAnalysisId);
        setAnalysisSteps({
          extract: { status: 'done', label: 'Đã tạo tác vụ phân tích' },
          score: { status: 'running', label: 'Đang xử lý phân tích...' },
        });

        const pollStart = Date.now();
        let finalData = null;
        while (Date.now() - pollStart < 120000) {
          const pollRes = await getAnalysis(createdAnalysisId);
          const payload = pollRes?.data;
          const status = String(payload?.status || '').toLowerCase();
          if (status === 'completed') {
            finalData = payload;
            break;
          }
          if (status === 'failed') {
            throw new Error('Phân tích thất bại. Vui lòng thử lại.');
          }
          // Poll short interval for background pipeline completion.
          await new Promise((resolve) => setTimeout(resolve, 1500));
        }

        if (!finalData) {
          throw new Error('Phân tích đang xử lý lâu hơn dự kiến. Vui lòng mở lại trang lịch sử để xem kết quả sau.');
        }

        setAnalysisResults(mapAnalysisResponseToResults(finalData));
        setAnalysisSteps({
          extract: { status: 'done', label: 'Trích xuất dữ liệu' },
          score: { status: 'done', label: 'Chấm điểm' },
          rewrite: { status: 'done', label: 'Tối ưu nội dung' },
          truthcheck: { status: 'done', label: 'Kiểm tra nhất quán' },
          insights: { status: 'done', label: 'Gợi ý nâng cao' },
          diff: { status: 'done', label: 'So sánh kết quả' },
        });
      } else {
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
      }
    } catch (e) {
      console.error('Analysis failed:', e);
      setAnalysisError(e?.response?.data?.detail || e?.message || 'Kết nối thất bại. Vui lòng thử lại.');
    } finally {
      setAnalyzing(false);
    }
  };

  const loadCvLibrary = async () => {
    setCvLibraryLoading(true);
    setCvLibraryError('');
    try {
      const res = await listGeneratedCVs(200, 0);
      setCvLibrary(Array.isArray(res?.data) ? res.data : []);
    } catch (error) {
      console.error('Failed to load CV library for picker:', error);
      setCvLibraryError('Không thể tải danh sách CV. Vui lòng thử lại.');
    } finally {
      setCvLibraryLoading(false);
    }
  };

  const openCvPicker = async () => {
    setCvPickerOpen(true);
    if (cvLibrary.length === 0 && !cvLibraryLoading) {
      await loadCvLibrary();
    }
  };

  const filteredCvLibrary = cvLibrary.filter((item) => {
    if (cvPickerFilter === 'uploaded') return item?.source_type === 'uploaded_cv';
    if (cvPickerFilter === 'system') return item?.source_type !== 'uploaded_cv';
    return true;
  });

  const handleSelectCvFromLibrary = (item) => {
    setSelectedCvFromLibrary(item);
    setCvSourceType('library');
    setCvPickerOpen(false);
  };

  const STEP_KEYS = ['extract', 'score', 'rewrite', 'truthcheck', 'insights', 'diff'];

  const ModeTitleIcon = mode === 'create' ? DocumentPlusIcon : DocumentMagnifyingGlassIcon;
  const StepStateIcon = ({ step }) => {
    if (!step) return <span className="step-dot pending" aria-hidden="true" />;
    if (step.status === 'done') return <CheckCircleIcon className="step-state-icon done" />;
    if (step.status === 'running') return <ClockIcon className="step-state-icon running" />;
    return <span className="step-dot pending" aria-hidden="true" />;
  };

  return (
    <div className="prompter-page fade-in">
      <div className="prompter-container">
        <div className="prompter-header">
          <div className="ai-badge">
            <span>Trợ lý tạo CV</span>
          </div>
          <h1 className="prompter-title">
            <ModeTitleIcon className="prompter-title-icon" />
            <span>{mode === 'create' ? 'Tạo CV mới' : 'Phân tích CV'}</span>
          </h1>
          <p className="prompter-subtitle">
            {mode === 'create'
              ? 'Nhập prompt để bắt đầu từ blank document.'
              : 'Upload CV và thêm Mô tả công việc (JD) bằng text hoặc file để phân tích, chấm điểm và tối ưu.'}
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
              Ô nhập phía trên là luồng tạo CV mới từ trắng.
            </p>
          </div>
        )}

        {/* ═══ ANALYZE MODE ═══ */}
        {mode === 'analyze' && (
          <div className="analyze-section">
            <div className="analyze-upload-grid">
              <div className="analyze-upload-card">
                <h3><DocumentTextIcon className="analyze-heading-icon" /> CV / Resume</h3>
                <div className="analyze-cv-source-actions">
                  <button
                    type="button"
                    className="analyze-cv-picker-btn"
                    onClick={openCvPicker}
                  >
                    Chọn CV từ quản lí
                  </button>
                  <span className="analyze-cv-source-hint">
                    {cvSourceType === 'library' && selectedCvFromLibrary
                      ? `Đang dùng: ${getCvTitle(selectedCvFromLibrary)}`
                      : cvSourceType === 'file' && cvFile
                        ? `Đang dùng file: ${cvFile.name}`
                        : 'Chọn CV từ popup hoặc upload file'}
                  </span>
                </div>
                <div className="analyze-dropzone" onClick={() => cvFileRef.current?.click()}>
                  <input
                    ref={cvFileRef}
                    type="file"
                    accept=".pdf,.docx"
                    onChange={(e) => {
                      const file = e.target.files[0];
                      setCvFile(file || null);
                      if (file) setCvSourceType('file');
                    }}
                    hidden
                  />
                  {cvSourceType === 'library' && selectedCvFromLibrary ? (
                    <div className="analyze-file-selected">
                      <CheckCircleIcon className="upload-state-icon selected" />
                      <span className="analyze-file-name">{getCvTitle(selectedCvFromLibrary)}</span>
                      <small style={{ color: 'var(--on-surface-variant)' }}>
                        {selectedCvFromLibrary.source_type === 'uploaded_cv' ? 'Nguồn: CV tải lên' : 'Nguồn: CV hệ thống'}
                      </small>
                    </div>
                  ) : cvFile ? (
                    <div className="analyze-file-selected">
                      <CheckCircleIcon className="upload-state-icon selected" />
                      <span className="analyze-file-name">{cvFile.name}</span>
                      <small style={{ color: 'var(--on-surface-variant)' }}>({(cvFile.size / 1024).toFixed(0)} KB)</small>
                    </div>
                  ) : (
                    <div className="analyze-file-empty">
                      <ArrowUpTrayIcon className="upload-state-icon" />
                      <span>Kéo thả file hoặc click để chọn</span>
                      <small>PDF, DOCX</small>
                    </div>
                  )}
                </div>
              </div>
              <div className="analyze-upload-card">
                <h3><ClipboardDocumentListIcon className="analyze-heading-icon" /> Mô tả công việc (JD)</h3>
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
                    placeholder={"Dán nội dung Mô tả công việc (JD) tại đây...\n\nVí dụ:\n- Yêu cầu 3 năm kinh nghiệm Python...\n- Kỹ năng: FastAPI, Docker, PostgreSQL..."}
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
                        <CheckCircleIcon className="upload-state-icon selected" />
                        <span className="analyze-file-name">{jdFile.name}</span>
                        <small style={{ color: 'var(--on-surface-variant)' }}>({(jdFile.size / 1024).toFixed(0)} KB)</small>
                      </div>
                    ) : (
                      <div className="analyze-file-empty">
                        <ArrowUpTrayIcon className="upload-state-icon" />
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
              disabled={(!((cvSourceType === 'file' && cvFile) || (cvSourceType === 'library' && selectedCvFromLibrary)) || (jdMode === 'text' ? !jdText.trim() : !jdFile) || analyzing)}
              onClick={handleAnalyze}
            >
              {analyzing ? 'Đang phân tích...' : 'Bắt đầu phân tích'}
            </button>

            {Object.keys(analysisSteps).length > 0 && (
              <div className="analyze-progress-card">
                <h3><ArrowPathIcon className="analyze-heading-icon" /> Tiến trình phân tích</h3>
                <div className="analyze-steps">
                  {STEP_KEYS.map((key) => {
                    const step = analysisSteps[key];
                    if (!step) return <div key={key} className="analyze-step pending"><StepStateIcon step={step} /> <span>{key}</span></div>;
                    const isDone = step.status === 'done';
                    const isRunning = step.status === 'running';
                    return (
                      <div key={key} className={`analyze-step ${isDone ? 'done' : ''} ${isRunning ? 'running' : ''}`}>
                        <StepStateIcon step={step} />
                        <span className="step-text">{step.label || key}</span>
                        {isDone && step.duration_ms && <span className="step-time">{(step.duration_ms / 1000).toFixed(1)}s</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {analysisError && <div className="analyze-error"><ExclamationCircleIcon className="inline-status-icon" /> {analysisError}</div>}

            {analysisResults?.scores && (
              <div className="analyze-results-section">
                <h3><ChartBarIcon className="analyze-heading-icon" /> Điểm số</h3>
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

            {analysisResults?.analysis_meta?.source === 'generated_cv' && (
              <GeneratedCvAnalysisNote
                meta={analysisResults.analysis_meta}
                scoreBreakdown={analysisResults.score_breakdown}
              />
            )}

            {analysisResults?.skills && (
              <div className="analyze-results-section">
                <h3><CheckCircleIcon className="analyze-heading-icon" /> Kỹ năng</h3>
                <div className="analyze-skills-groups">
                  {analysisResults.skills.matched?.length > 0 && (
                    <div className="skill-group"><h4>✓ Phù hợp ({analysisResults.skills.matched.length})</h4><div className="skill-tags">{analysisResults.skills.matched.map((s, i) => <span key={i} className="skill-tag tag-matched">{s.name}</span>)}</div></div>
                  )}
                  {analysisResults.skills.missing?.length > 0 && (
                    <div className="skill-group"><h4>✕ Thiếu ({analysisResults.skills.missing.length})</h4><div className="skill-tags">{analysisResults.skills.missing.map((s, i) => <span key={i} className={`skill-tag tag-${s.category === 'needs_user_info' ? 'needs-info' : 'missing'}`} title={s.reason || ''}>{s.name}{s.category === 'needs_user_info' && <small>Cần bổ sung dữ liệu</small>}</span>)}</div></div>
                  )}
                  {analysisResults.skills.extra?.length > 0 && (
                    <div className="skill-group"><h4>+ Bổ sung ({analysisResults.skills.extra.length})</h4><div className="skill-tags">{analysisResults.skills.extra.map((s, i) => <span key={i} className="skill-tag tag-extra">{s.name}</span>)}</div></div>
                  )}
                </div>
              </div>
            )}

            {analysisResults?.insights && (
              <div className="analyze-results-section">
                <h3><LightBulbIcon className="analyze-heading-icon" /> Phân tích nâng cao</h3>
                <div className="analyze-insights-grid">
                  {analysisResults.insights.jd_evaluation && (
                    <div className="insight-card">
                      <h4>Phân tích JD</h4>
                      <p><strong>Tóm tắt:</strong> {getJdEvaluationSummary(analysisResults.insights.jd_evaluation) || 'Chưa có dữ liệu'}</p>
                      <p><strong>Nhận xét:</strong> {getJdEvaluationAdvice(analysisResults.insights.jd_evaluation) || 'Chưa có dữ liệu'}</p>
                    </div>
                  )}
                  {analysisResults.insights.salary_negotiation && (
                    <div className="insight-card">
                      <h4>Đề xuất lương</h4>
                      <p className="salary-range">{getSalaryRange(analysisResults.insights.salary_negotiation) || 'Chưa có dữ liệu'}</p>
                      <p>{getSalaryAdvice(analysisResults.insights.salary_negotiation) || 'Chưa có dữ liệu'}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {analysisResults?.rewritten_cv && (
              <div className="analyze-results-section">
                <h3><DocumentTextIcon className="analyze-heading-icon" /> CV tối ưu đề xuất</h3>
                <div className="analyze-rewritten-cv"><pre>{analysisResults.rewritten_cv}</pre></div>
              </div>
            )}

            {analysisId && (
              <div className="analyze-done-banner">
                <CheckCircleIcon className="inline-status-icon" />
                Phân tích hoàn tất!{' '}
                <a href={`/analysis/${analysisId}`} className="analyze-detail-link">Xem chi tiết đầy đủ →</a>
              </div>
            )}
          </div>
        )}
      </div>

      {cvPickerOpen && (
        <div className="cv-picker-backdrop" role="presentation" onClick={() => setCvPickerOpen(false)}>
          <div className="cv-picker-modal" role="dialog" aria-modal="true" aria-labelledby="cv-picker-title" onClick={(event) => event.stopPropagation()}>
            <div className="cv-picker-header">
              <h3 id="cv-picker-title">Chọn CV từ quản lí</h3>
              <button type="button" className="cv-picker-close" onClick={() => setCvPickerOpen(false)} aria-label="Đóng">
                <XMarkIcon className="cv-picker-close-icon" />
              </button>
            </div>
            <div className="cv-picker-filters">
              <button type="button" className={`cv-picker-filter ${cvPickerFilter === 'all' ? 'active' : ''}`} onClick={() => setCvPickerFilter('all')}>Tất cả</button>
              <button type="button" className={`cv-picker-filter ${cvPickerFilter === 'system' ? 'active' : ''}`} onClick={() => setCvPickerFilter('system')}>CV từ hệ thống</button>
              <button type="button" className={`cv-picker-filter ${cvPickerFilter === 'uploaded' ? 'active' : ''}`} onClick={() => setCvPickerFilter('uploaded')}>CV tải lên</button>
            </div>
            {cvLibraryError && <div className="cv-picker-error">{cvLibraryError}</div>}
            <div className="cv-picker-list">
              {cvLibraryLoading && <div className="cv-picker-empty">Đang tải danh sách CV...</div>}
              {!cvLibraryLoading && filteredCvLibrary.length === 0 && (
                <div className="cv-picker-empty">Không có CV phù hợp bộ lọc.</div>
              )}
              {!cvLibraryLoading && filteredCvLibrary.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className="cv-picker-row"
                  onClick={() => handleSelectCvFromLibrary(item)}
                >
                  <div className="cv-picker-row-main">
                    <strong>{getCvTitle(item)}</strong>
                    <span>
                      {item.source_type === 'uploaded_cv' ? 'CV tải lên' : 'CV hệ thống'}
                      {' • '}
                      v{item.version}
                      {' • '}
                      {formatDate(item.created_at)}
                    </span>
                  </div>
                  <span className="cv-picker-row-action">Chọn</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function GeneratedCvAnalysisNote({ meta, scoreBreakdown }) {
  const needs = meta?.needs_user_info || scoreBreakdown?.needs_user_info || [];
  return (
    <div className={`generated-analysis-note ${meta?.pass_ready ? 'ready' : 'needs-info'}`}>
      <div>
        <h3>{meta?.pass_ready ? 'CV generated đã đủ dữ liệu' : 'CV generated cần bổ sung dữ liệu thật'}</h3>
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
