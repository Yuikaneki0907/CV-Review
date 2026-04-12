import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { exportGeneratedCV, getGeneratedCV, updateGeneratedCV, streamChatCVGeneration, streamChatAnalysis } from '../api';
import { useAuth } from '../AuthContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import { DocumentCheckIcon, SparklesIcon } from '@heroicons/react/24/outline';
import CvWysiwygEditor from '../components/CvWysiwygEditor';
import {
  clearWorkspaceDraft,
  getDraftScope,
  loadWorkspaceDraft,
  saveWorkspaceDraft,
} from '../utils/workspaceDraft';
import {
  WORKSPACE_CHAT_JOB_EVENT,
} from '../utils/workspaceChatJobs';
import {
  getInterviewQuestionNote,
  getJdEvaluationAdvice,
  getJdEvaluationSummary,
  getSalaryAdvice,
  getSalaryRange,
} from '../utils/analysisInsights';

const OUTPUT_FORMAT_OPTIONS = [
  { value: 'rich_text', label: 'Rich Text' },
  { value: 'markdown', label: 'Markdown' },
  { value: 'docx', label: 'DOCX' },
];

const OUTPUT_FORMAT_LABELS = {
  rich_text: 'Rich Text',
  markdown: 'Markdown',
  docx: 'DOCX',
};

const normalizeOutputFormat = (value) =>
  value === 'markdown' || value === 'docx' || value === 'rich_text' ? value : 'rich_text';

const inferOutputFormatFromDocument = (doc, fallback = 'rich_text') => {
  const content = doc?.generated_content;
  const explicitFormat = content?.format;
  if (explicitFormat === 'rich_text' || explicitFormat === 'markdown' || explicitFormat === 'docx') {
    return explicitFormat;
  }

  if (typeof content?.markdown === 'string' && content.markdown.trim().length > 0) {
    return 'markdown';
  }
  if (typeof content?.text === 'string' && content.text.trim().length > 0) {
    return 'rich_text';
  }
  return normalizeOutputFormat(fallback);
};

const extractContentFromDocument = (doc) =>
  doc?.generated_content?.content ||
  doc?.generated_content?.markdown ||
  doc?.generated_content?.text ||
  '';

const parseFilenameFromDisposition = (headerValue) => {
  if (!headerValue) return null;

  const utfMatch = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1].trim());
    } catch {
      return utfMatch[1].trim();
    }
  }

  const basicMatch = headerValue.match(/filename="?([^"]+)"?/i);
  return basicMatch?.[1]?.trim() || null;
};

export default function WorkspacePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { id } = useParams();
  const { user } = useAuth();

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [cvDocument, setCvDocument] = useState(null);
  const [editableContent, setEditableContent] = useState('');
  const [restoredDraft, setRestoredDraft] = useState(false);
  const [outputFormat, setOutputFormat] = useState('rich_text');
  const [exporting, setExporting] = useState(false);
  const [savingEdits, setSavingEdits] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  // ── CV Analysis attachment state ──────────────────
  const [attachedCvFile, setAttachedCvFile] = useState(null);
  const [attachedJdText, setAttachedJdText] = useState('');
  const [showAttachPanel, setShowAttachPanel] = useState(false);
  const [analysisMode, setAnalysisMode] = useState(false);
  const [analysisSteps, setAnalysisSteps] = useState({});
  const [analysisResults, setAnalysisResults] = useState(null);
  const cvFileRef = useRef(null);

  // ── Template state ───────────────────────────────
  const [templateId, setTemplateId] = useState(null);

  const messagesEndRef = useRef(null);
  const initializedNav = useRef(null);
  const hydratedDraftRef = useRef(false);
  const mountedRef = useRef(false);
  const scope = getDraftScope(id);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle initialization
  useEffect(() => {
    const navKey = id
      ? `id:${id}`
      : location.state?.initialPrompt
        ? `prompt:${location.key}`
        : `empty:${location.key}`;

    if (initializedNav.current === navKey) return;
    initializedNav.current = navKey;
    hydratedDraftRef.current = false;
    setRestoredDraft(false);
    setAnalysisMode(false);
    setAnalysisSteps({});
    setAnalysisResults(null);
    setShowAttachPanel(false);
    setAttachedCvFile(null);
    setAttachedJdText('');

    const initWorkspace = async () => {
      const draft = user?.id ? loadWorkspaceDraft(user.id, scope) : null;

      // If we are given an ID in URL, we are viewing an existing generated CV session
      if (id) {
        try {
          const res = await getGeneratedCV(id);
          setCvDocument(res.data);
          setEditableContent(extractContentFromDocument(res.data));
          const serverFormat = inferOutputFormatFromDocument(res.data, draft?.outputFormat || outputFormat);

          const serverMessages = res.data.generated_content?.chat_history || [];
          if (!location.state?.keepMessages) {
            if (draft?.messages?.length) {
              setMessages(draft.messages);
              setInputValue(draft.inputValue || '');
              setLoading(Boolean(draft.pending));
              setOutputFormat(normalizeOutputFormat(draft.outputFormat || serverFormat));
              setRestoredDraft(true);
            } else {
              setMessages(serverMessages);
              setInputValue('');
              setLoading(false);
              setOutputFormat(serverFormat);
            }
          }
        } catch (e) {
          console.error('Failed to load CV:', e);
          setLoading(Boolean(draft?.pending));
          setOutputFormat(normalizeOutputFormat(draft?.outputFormat));
        }
      }
      // If we came from the home page with an initial prompt
      else if (location.state?.initialPrompt) {
        if (user?.id) clearWorkspaceDraft(user.id, 'new');

        const initialPrompt = location.state.initialPrompt;
        const navTemplateId = location.state.templateId || null;
        const navTemplateContent = location.state.templateContent || '';
        setTemplateId(navTemplateId);
        const initialMsgs = [{ role: 'user', content: initialPrompt }];
        setMessages(initialMsgs);
        setInputValue('');
        setCvDocument(null);

        // If template has skeleton content, show it immediately in Document Viewer
        if (navTemplateContent) {
          setEditableContent(navTemplateContent);
          setOutputFormat('markdown');
        } else {
          setEditableContent('');
          setOutputFormat('rich_text');
        }
        setLoading(true);

        // Send to backend
        handleChatTurn(initialMsgs, navTemplateContent ? 'markdown' : 'rich_text', navTemplateId);
      } else {
        // Empty workspace or restore unfinished draft
        if (draft?.generatedCvId) {
          clearWorkspaceDraft(user.id, 'new');
          navigate(`/workspace/${draft.generatedCvId}`, { replace: true, state: { keepMessages: true } });
          return;
        }

        if (draft?.messages?.length || draft?.inputValue?.trim() || draft?.pending) {
          setMessages(draft.messages || []);
          setInputValue(draft.inputValue || '');
          setCvDocument(null);
          setEditableContent('');
          setLoading(Boolean(draft.pending));
          setOutputFormat(normalizeOutputFormat(draft.outputFormat));
          setRestoredDraft(true);
        } else {
          setMessages([]);
          setInputValue('');
          setCvDocument(null);
          setEditableContent('');
          setLoading(false);
          setOutputFormat('rich_text');
        }
      }

      hydratedDraftRef.current = true;
    };
    initWorkspace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, location.state, location.key, user?.id, scope, navigate]);

  useEffect(() => {
    if (!user?.id) return undefined;

    const onJobUpdate = (event) => {
      const detail = event.detail || {};
      if (detail.userId !== user.id || detail.scope !== scope) return;

      const draft = loadWorkspaceDraft(user.id, scope);
      if (!draft) return;

      setMessages(draft.messages || []);
      setInputValue(draft.inputValue || '');
      setLoading(Boolean(draft.pending));
      setOutputFormat(normalizeOutputFormat(draft.outputFormat));

      if (detail.generatedCvId && scope === 'new') {
        navigate(`/workspace/${detail.generatedCvId}`, { replace: true, state: { keepMessages: true } });
      }
    };

    window.addEventListener(WORKSPACE_CHAT_JOB_EVENT, onJobUpdate);
    return () => {
      window.removeEventListener(WORKSPACE_CHAT_JOB_EVENT, onJobUpdate);
    };
  }, [user?.id, scope, navigate]);

  // Persist unfinished chat drafts so user can leave and return later.
  useEffect(() => {
    if (!hydratedDraftRef.current || !user?.id) return;
    saveWorkspaceDraft({
      userId: user.id,
      scope,
      messages,
      inputValue,
      title: cvDocument?.base_profile_data?.job_title || '',
      pending: loading,
      outputFormat,
    });
  }, [user?.id, scope, messages, inputValue, cvDocument?.base_profile_data?.job_title, loading, outputFormat]);

  const prevCvDocIdRef = useRef(undefined);
  useEffect(() => {
    const prevId = prevCvDocIdRef.current;
    prevCvDocIdRef.current = cvDocument?.id;

    if (!cvDocument) {
      // Only reset editable content when a previously-loaded document is cleared,
      // NOT on initial mount when template skeleton content may already be set.
      if (prevId !== undefined) {
        setEditableContent('');
      }
      setSaveMessage('');
      return;
    }
    setEditableContent(extractContentFromDocument(cvDocument));
    setSaveMessage('');
  }, [cvDocument?.id, cvDocument?.generated_content?.content, cvDocument?.generated_content?.markdown, cvDocument?.generated_content?.text]);

  const [streamAiReply, setStreamAiReply] = useState('');
  const [streamCvText, setStreamCvText] = useState('');

  const handleChatTurn = async (currentMessages, formatOverride = outputFormat, templateOverride = templateId) => {
    if (!user?.id) return;
    setLoading(true);
    setStreamAiReply('');
    setStreamCvText('');
    setAnalysisMode(false);
    setAnalysisSteps({});
    setAnalysisResults(null);
    setShowAttachPanel(false);
    setAttachedCvFile(null);
    setAttachedJdText('');

    try {
      let finalReply = '';
      let idcv = null;
      let finalcvtext = '';

      await streamChatCVGeneration(currentMessages, normalizeOutputFormat(formatOverride), (val) => {
        const { event, data } = val;

        if (event === 'chat_chunk') {
          finalReply += data;
          setStreamAiReply(finalReply);
        } else if (event === 'cv_chunk') {
          finalcvtext += data;
          setStreamCvText(finalcvtext);
          // Auto-update editable content so user sees typing effect
          setEditableContent(finalcvtext);
        } else if (event === 'cv_id') {
          idcv = data;
        } else if (event === 'signal') {
          // Do nothing special yet
        } else if (event === 'error') {
          console.error("AI Error:", data);
        }
      }, templateOverride);

      const finalMessages = [...currentMessages, { role: 'assistant', content: finalReply || 'Mình đã xử lý xong yêu cầu.' }];

      if (mountedRef.current) {
        setMessages(finalMessages);
        setStreamAiReply('');
        setStreamCvText('');
      }

      if (idcv) {
        try {
          const cvRes = await getGeneratedCV(idcv);
          if (mountedRef.current) {
            setCvDocument(cvRes.data);
            setEditableContent(extractContentFromDocument(cvRes.data));
          }
        } catch (e) {
          console.error('Failed to load generated CV after stream finish:', e);
        }

        if (mountedRef.current && (!id || id !== idcv)) {
          navigate(`/workspace/${idcv}`, { replace: true, state: { keepMessages: true } });
        }
      } else {
        // Save the draft state
        saveWorkspaceDraft({
          userId: user.id,
          scope,
          messages: finalMessages,
          inputValue: '',
          title: cvDocument?.base_profile_data?.job_title || '',
          pending: false,
          outputFormat,
        });
      }
    } catch (e) {
      console.error(e);
      if (mountedRef.current) {
        setMessages([...currentMessages, { role: 'assistant', content: 'Xin lỗi, đã có lỗi kết nối xảy ra. Vui lòng thử lại.' }]);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  };

  // ── CV Analysis handler ───────────────────────────
  const handleAnalyze = async () => {
    if (!attachedCvFile || !attachedJdText.trim() || loading) return;

    const cvFileName = attachedCvFile.name;
    const newMsgs = [
      ...messages,
      {
        role: 'user',
        content: `📎 Phân tích CV: **${cvFileName}**\n\n**Job Description:**\n${attachedJdText.trim()}`,
      },
    ];
    setMessages(newMsgs);
    setLoading(true);
    setAnalysisMode(true);
    setAnalysisSteps({});
    setAnalysisResults(null);
    setShowAttachPanel(false);

    try {
      await streamChatAnalysis(attachedCvFile, attachedJdText, null, (val) => {
        const { event, data } = val;

        if (event === 'analysis_step') {
          setAnalysisSteps((prev) => ({
            ...prev,
            [data.step]: { status: data.status, label: data.label, duration_ms: data.duration_ms },
          }));
        } else if (event === 'analysis_result') {
          setAnalysisResults((prev) => ({
            ...(prev || {}),
            [data.type]: data.data,
          }));
          // If rewritten CV, put it in document pane
          if (data.type === 'rewritten_cv' && data.data) {
            setEditableContent(data.data);
          }
        } else if (event === 'analysis_done') {
          const analysisId = data.analysis_id;
          const finalMsgs = [
            ...newMsgs,
            {
              role: 'assistant',
              content: `✅ Phân tích CV hoàn tất! [Xem chi tiết →](/analysis/${analysisId})`,
              analysisId,
            },
          ];
          setMessages(finalMsgs);
        } else if (event === 'analysis_error') {
          setMessages([
            ...newMsgs,
            { role: 'assistant', content: `❌ Phân tích thất bại: ${data.error}` },
          ]);
        }
      });
    } catch (e) {
      console.error('Analysis failed:', e);
      setMessages([
        ...newMsgs,
        { role: 'assistant', content: 'Xin lỗi, đã có lỗi kết nối xảy ra. Vui lòng thử lại.' },
      ]);
    } finally {
      setLoading(false);
      setAnalysisMode(false);
      setAttachedCvFile(null);
      setAttachedJdText('');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // If files are attached, run analysis instead of normal chat
    if (attachedCvFile && attachedJdText.trim()) {
      handleAnalyze();
      return;
    }
    if (!inputValue.trim() || loading) return;

    const newMsgs = [...messages, { role: 'user', content: inputValue.trim() }];
    setMessages(newMsgs);
    setInputValue('');
    handleChatTurn(newMsgs, outputFormat);
  };

  const documentFormat = cvDocument
    ? inferOutputFormatFromDocument(cvDocument, outputFormat)
    : normalizeOutputFormat(outputFormat);
  const originalDocumentContent = extractContentFromDocument(cvDocument);
  const hasUnsavedEdits = Boolean(cvDocument) && editableContent !== originalDocumentContent;

  const handleSaveEdits = async () => {
    if (!cvDocument?.id || savingEdits || !hasUnsavedEdits) return true;

    setSavingEdits(true);
    setSaveMessage('Đang lưu thay đổi...');
    try {
      const res = await updateGeneratedCV(cvDocument.id, {
        content: editableContent,
        output_format: documentFormat,
      });
      setCvDocument(res.data);
      setEditableContent(extractContentFromDocument(res.data));
      setSaveMessage('Đã lưu thay đổi');
      return true;
    } catch (error) {
      console.error('Failed to save generated CV edits:', error);
      setSaveMessage('Lưu thất bại, vui lòng thử lại');
      return false;
    } finally {
      setSavingEdits(false);
    }
  };

  const handleExport = async () => {
    if (!cvDocument?.id || exporting) return;
    if (hasUnsavedEdits) {
      const ok = await handleSaveEdits();
      if (!ok) return;
    }

    const exportFormat = documentFormat === 'rich_text' ? 'text' : documentFormat;
    const fallbackExt = exportFormat === 'docx' ? 'docx' : exportFormat === 'markdown' ? 'md' : 'txt';

    setExporting(true);
    try {
      const response = await exportGeneratedCV(cvDocument.id, exportFormat);
      const headerValue = response.headers?.['content-disposition'] || response.headers?.['Content-Disposition'];
      const filename = parseFilenameFromDisposition(headerValue) || `generated_cv.${fallbackExt}`;
      const blob = response.data instanceof Blob ? response.data : new Blob([response.data]);

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export generated CV:', error);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="workspace-container fade-in">
      {/* Left Pane: Chat Interaction */}
      <div className="workspace-chat-pane">
        <div className="chat-header">
          <SparklesIcon className="chat-header-icon" />
          <span>CV Assistant</span>
        </div>
        {restoredDraft && (
          <div className="workspace-draft-banner">
            Đã khôi phục phiên chat đang làm dở.
          </div>
        )}

        <div className="chat-history auto-scroll-y">
          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-bubble-wrapper ${msg.role === 'user' ? 'user' : 'assistant'}`}>
              <div className="chat-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              </div>
            </div>
          ))}
          {streamAiReply && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble streaming-bubble">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamAiReply}</ReactMarkdown>
                <span className="blinking-cursor"></span>
              </div>
            </div>
          )}
          {loading && !streamAiReply && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}
          {streamCvText && (
            <div className="chat-tool-execution">
              <div className="tool-icon">🛠️</div>
              <div className="tool-text">
                <span className="tool-name">Using Tool | Generate CV Markdown</span>
                <span className="tool-status">Crafting document in real-time...</span>
              </div>
            </div>
          )}
          {/* Analysis pipeline progress */}
          {analysisMode && Object.keys(analysisSteps).length > 0 && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble analysis-progress-bubble">
                <div className="analysis-steps-header">🔬 Đang phân tích CV...</div>
                <div className="analysis-steps-list">
                  {['extract', 'score', 'rewrite', 'truthcheck', 'insights', 'diff'].map((key) => {
                    const step = analysisSteps[key];
                    if (!step) return null;
                    const isDone = step.status === 'done';
                    const isRunning = step.status === 'running';
                    return (
                      <div key={key} className={`analysis-step-item ${isDone ? 'done' : ''} ${isRunning ? 'running' : ''}`}>
                        <span className="analysis-step-icon">
                          {isDone ? '✅' : isRunning ? '⏳' : '⬜'}
                        </span>
                        <span className="analysis-step-label">{step.label || key}</span>
                        {isDone && step.duration_ms && (
                          <span className="analysis-step-time">{(step.duration_ms / 1000).toFixed(1)}s</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
          {/* Analysis results cards */}
          {analysisResults?.scores && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble analysis-result-bubble">
                <div className="analysis-scores-grid">
                  <div className={`analysis-score-card large score-${analysisResults.scores.overall >= 80 ? 'green' : analysisResults.scores.overall >= 50 ? 'yellow' : 'red'}`}>
                    <div className="score-value">{analysisResults.scores.overall}</div>
                    <div className="score-label">Tổng điểm</div>
                  </div>
                  <div className={`analysis-score-card score-${analysisResults.scores.skills_score >= 80 ? 'green' : analysisResults.scores.skills_score >= 50 ? 'yellow' : 'red'}`}>
                    <div className="score-value">{analysisResults.scores.skills_score}</div>
                    <div className="score-label">Kỹ năng</div>
                  </div>
                  <div className={`analysis-score-card score-${analysisResults.scores.experience_score >= 80 ? 'green' : analysisResults.scores.experience_score >= 50 ? 'yellow' : 'red'}`}>
                    <div className="score-value">{analysisResults.scores.experience_score}</div>
                    <div className="score-label">Kinh nghiệm</div>
                  </div>
                  <div className={`analysis-score-card score-${analysisResults.scores.tools_score >= 80 ? 'green' : analysisResults.scores.tools_score >= 50 ? 'yellow' : 'red'}`}>
                    <div className="score-value">{analysisResults.scores.tools_score}</div>
                    <div className="score-label">Công cụ</div>
                  </div>
                </div>
              </div>
            </div>
          )}
          {analysisResults?.skills && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble analysis-result-bubble">
                <div className="analysis-skills-section">
                  {analysisResults.skills.matched?.length > 0 && (
                    <div className="skill-group">
                      <h4>✓ Kỹ năng phù hợp</h4>
                      <div className="skill-tags">
                        {analysisResults.skills.matched.map((s, i) => (
                          <span key={i} className="skill-tag tag-matched">{s.name}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {analysisResults.skills.missing?.length > 0 && (
                    <div className="skill-group">
                      <h4>✕ Kỹ năng thiếu</h4>
                      <div className="skill-tags">
                        {analysisResults.skills.missing.map((s, i) => (
                          <span key={i} className="skill-tag tag-missing">{s.name}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {analysisResults.skills.extra?.length > 0 && (
                    <div className="skill-group">
                      <h4>+ Kỹ năng bổ sung</h4>
                      <div className="skill-tags">
                        {analysisResults.skills.extra.map((s, i) => (
                          <span key={i} className="skill-tag tag-extra">{s.name}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
          {analysisResults?.insights && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble analysis-result-bubble">
                <div className="analysis-insights">
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
                    <div className="insight-card">
                      <h4>🎤 Gợi ý phỏng vấn</h4>
                      <ul>
                        {analysisResults.insights.interview_questions.slice(0, 3).map((q, i) => (
                          <li key={i}><strong>Q:</strong> {q.question}{getInterviewQuestionNote(q) && <em style={{ display: 'block', color: 'var(--on-surface-variant)', fontSize: '0.75rem' }}>Gợi ý thêm: {getInterviewQuestionNote(q)}</em>}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-area floating-input" onSubmit={handleSubmit}>
          {/* Attach CV panel */}
          {showAttachPanel && (
            <div className="attach-panel">
              <div className="attach-panel-header">
                <span>📎 Phân tích CV</span>
                <button type="button" className="attach-close-btn" onClick={() => setShowAttachPanel(false)}>✕</button>
              </div>
              <div className="attach-panel-body">
                <div className="attach-cv-zone" onClick={() => cvFileRef.current?.click()}>
                  <input
                    ref={cvFileRef}
                    type="file"
                    accept=".pdf,.docx"
                    onChange={(e) => setAttachedCvFile(e.target.files[0])}
                    hidden
                  />
                  {attachedCvFile ? (
                    <div className="attach-file-preview">
                      <span className="material-symbols-outlined" style={{ color: 'var(--secondary)', fontSize: '1.2rem' }}>check_circle</span>
                      <span>{attachedCvFile.name}</span>
                      <small>({(attachedCvFile.size / 1024).toFixed(0)} KB)</small>
                    </div>
                  ) : (
                    <div className="attach-file-prompt">
                      <span className="material-symbols-outlined" style={{ fontSize: '1.5rem', color: 'var(--outline)' }}>upload_file</span>
                      <span>Chọn file CV (PDF/DOCX)</span>
                    </div>
                  )}
                </div>
                <textarea
                  className="attach-jd-input"
                  value={attachedJdText}
                  onChange={(e) => setAttachedJdText(e.target.value)}
                  placeholder="Dán Job Description tại đây..."
                  rows={4}
                />
                <button
                  type="button"
                  className="btn-primary attach-analyze-btn"
                  disabled={!attachedCvFile || !attachedJdText.trim() || loading}
                  onClick={handleAnalyze}
                >
                  🔬 Bắt đầu phân tích
                </button>
              </div>
            </div>
          )}
          <div className="workspace-format-selector" role="group" aria-label="Output format selector">
            <button
              type="button"
              className={`workspace-format-chip ${showAttachPanel ? 'active' : ''}`}
              onClick={() => setShowAttachPanel(!showAttachPanel)}
              disabled={loading}
              title="Phân tích CV"
            >
              📎 Phân tích CV
            </button>
            {OUTPUT_FORMAT_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`workspace-format-chip ${outputFormat === option.value ? 'active' : ''}`}
                onClick={() => setOutputFormat(option.value)}
                disabled={loading}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="chat-input-wrapper">
            <textarea
              className="chat-input"
              rows={1}
              placeholder={showAttachPanel ? 'Đính kèm CV + JD ở phía trên để phân tích...' : 'Nhập yêu cầu của bạn (VD: thêm JD, đổi title...)'}
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            <button type="submit" className={`chat-submit-btn ${inputValue.trim() ? 'active' : ''}`} disabled={!inputValue.trim() || loading}>
              <PaperAirplaneIcon className="submit-icon" />
            </button>
          </div>
        </form>
      </div>

      {/* Right Pane: Document Viewer */}
      <div className="workspace-doc-pane">
        <div className="doc-header">
          <div className="doc-title">
            <DocumentCheckIcon className="doc-icon" />
            <span>{cvDocument ? `CV - ${cvDocument.base_profile_data?.job_title || 'Generated'}` : 'Document Viewer'}</span>
            <span className="doc-format-chip">{OUTPUT_FORMAT_LABELS[documentFormat]}</span>
          </div>
          {cvDocument && (
            <div className="doc-actions">
              <button
                className="btn-ghost"
                style={hasUnsavedEdits ? { borderColor: 'var(--primary)', color: 'var(--primary)' } : {}}
                onClick={handleSaveEdits}
                disabled={savingEdits || !hasUnsavedEdits}
              >
                {savingEdits ? 'Saving...' : 'Save edits'}
              </button>
              <button
                className="btn-primary"
                style={{ padding: '0.5rem 1rem', fontSize: '0.8rem', borderRadius: 'var(--radius-sm)', width: 'auto' }}
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? 'Exporting...' : `Export ${OUTPUT_FORMAT_LABELS[documentFormat]}`}
              </button>
            </div>
          )}
        </div>
        {cvDocument && saveMessage && (
          <div className="doc-save-status">{saveMessage}</div>
        )}

        <div className="doc-content-wrapper">
          {(cvDocument || editableContent) ? (
            <div className="a4-paper cv-document">
              <CvWysiwygEditor
                value={editableContent}
                format={documentFormat}
                onChange={setEditableContent}
                readOnly={savingEdits}
              />
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon-wrapper">
                <DocumentCheckIcon className="empty-icon" />
              </div>
              <p>Chưa có tài liệu CV nào được tạo.</p>
              <p className="empty-subtext">Hãy chat với AI ở bên trái để bắt đầu tạo CV nhé.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
