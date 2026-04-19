import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  createGeneratedCVVersion,
  downloadGeneratedCV,
  getGeneratedCV,
  getGeneratedCVVersions,
  streamChatAnalysis,
  streamChatCVGeneration,
} from '../api';
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
  getInterviewQuestionNote,
  getJdEvaluationAdvice,
  getJdEvaluationSummary,
  getSalaryAdvice,
  getSalaryRange,
} from '../utils/analysisInsights';
import { notifyGeneratedCvHistoryChanged } from '../utils/generatedCvHistory';
import { TEMPLATE_SKELETONS } from '../utils/templateSkeletons';

const TEMPLATE_TITLES = {
  ats_clean: 'ATS-Friendly',
  executive: 'Executive / Senior',
  tech_engineer: 'Tech / Engineer',
  fresh_graduate: 'Fresh Graduate',
};

const OUTPUT_FORMAT_OPTIONS = [
  { value: 'markdown', label: 'Markdown' },
  { value: 'docx', label: 'DOCX' },
];

const OUTPUT_FORMAT_LABELS = {
  markdown: 'Markdown',
  docx: 'DOCX',
};

const LAYOUT_MODES = [
  { value: 'document', label: 'Ưu tiên CV' },
  { value: 'balanced', label: 'Cân bằng' },
  { value: 'chat', label: 'Ưu tiên chat' },
];

const EMPTY_CHAT_PROMPTS = [
  'Rút gọn phần Summary theo hướng senior hơn',
  'Viết lại kinh nghiệm để nổi bật vai trò Backend Engineer',
  'Tối ưu CV này theo JD tôi sắp dán vào',
];

const CHAT_INPUT_MIN_HEIGHT = 72;
const CHAT_INPUT_MAX_HEIGHT = 170;

const resizeChatInput = (textarea) => {
  if (!textarea) return;

  textarea.style.height = 'auto';
  const nextHeight = Math.min(
    Math.max(textarea.scrollHeight, CHAT_INPUT_MIN_HEIGHT),
    CHAT_INPUT_MAX_HEIGHT
  );
  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY = textarea.scrollHeight > CHAT_INPUT_MAX_HEIGHT ? 'auto' : 'hidden';
};

const normalizeOutputFormat = (value) =>
  value === 'markdown' || value === 'docx' ? value : 'markdown';

const inferOutputFormatFromDocument = (doc, fallback = 'markdown') => {
  const content = doc?.generated_content;
  const explicitFormat = content?.format;
  if (explicitFormat === 'markdown' || explicitFormat === 'docx') {
    return explicitFormat;
  }

  if (typeof content?.markdown === 'string' && content.markdown.trim().length > 0) {
    return 'markdown';
  }
  return normalizeOutputFormat(fallback);
};

const extractEditorStateFromDocument = (doc) => {
  const payload = doc?.generated_content || {};
  const markdown =
    payload.content ||
    payload.markdown ||
    payload.text ||
    '';
  const html = payload.html || '';
  const useHtml = payload.import_preview_format === 'html' && typeof html === 'string' && html.trim().length > 0;

  return {
    value: useHtml ? html : markdown,
    valueFormat: useHtml ? 'html' : 'markdown',
    markdown,
  };
};

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

const buildClientExportFilename = (title, ext) => {
  const normalized = String(title || 'generated_cv')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 60);

  return `${normalized || 'generated_cv'}.${ext}`;
};

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  const [editableContentFormat, setEditableContentFormat] = useState('markdown');
  const [editableMarkdown, setEditableMarkdown] = useState('');
  const [documentDirty, setDocumentDirty] = useState(false);
  const [restoredDraft, setRestoredDraft] = useState(false);
  const [outputFormat, setOutputFormat] = useState('markdown');
  const [exporting, setExporting] = useState(false);
  const [savingEdits, setSavingEdits] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [chatStatus, setChatStatus] = useState(null);
  const [versionHistory, setVersionHistory] = useState([]);
  const [layoutMode, setLayoutMode] = useState('balanced');
  const [staticTemplateTitle, setStaticTemplateTitle] = useState('');
  const [editorInstanceKey, setEditorInstanceKey] = useState('empty');

  // ── CV Analysis attachment state ──────────────────
  const [attachedCvFile, setAttachedCvFile] = useState(null);
  const [attachedJdText, setAttachedJdText] = useState('');
  const [showAttachPanel, setShowAttachPanel] = useState(false);
  const [analysisMode, setAnalysisMode] = useState(false);
  const [analysisSteps, setAnalysisSteps] = useState({});
  const [analysisResults, setAnalysisResults] = useState(null);
  const cvFileRef = useRef(null);
  const chatInputRef = useRef(null);

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

  useEffect(() => {
    resizeChatInput(chatInputRef.current);
  }, [inputValue, showAttachPanel]);

  // Handle initialization
  useEffect(() => {
    const routeTemplateId = new URLSearchParams(location.search).get('template');
    const routeTemplateContent = routeTemplateId ? TEMPLATE_SKELETONS[routeTemplateId] || '' : '';
    const navTemplateIdFromState = location.state?.templateId || null;
    const navTemplateContentFromState = location.state?.templateContent || '';
    const activeTemplateId = routeTemplateId || navTemplateIdFromState;
    const activeTemplateContent = routeTemplateContent || navTemplateContentFromState;

    const navKey = id
      ? `id:${id}`
      : activeTemplateContent
        ? `template:${activeTemplateId || 'custom'}:${location.search || location.key}`
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
    setChatStatus(null);
    setVersionHistory([]);

    const initWorkspace = async () => {
      const draft = user?.id ? loadWorkspaceDraft(user.id, scope) : null;

      // If we are given an ID in URL, we are viewing an existing generated CV session
      if (id) {
        setTemplateId(null);
        try {
          const res = await getGeneratedCV(id);
          setTemplateId(null);
          setStaticTemplateTitle('');
          setEditorInstanceKey(`doc:${res.data.id}`);
          setCvDocument(res.data);
          const editorState = extractEditorStateFromDocument(res.data);
          setEditableContent(editorState.value);
          setEditableContentFormat(editorState.valueFormat);
          setEditableMarkdown(editorState.markdown);
          setDocumentDirty(false);
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
      // If we came from a template card, open the static skeleton without sending a prompt.
      else if (activeTemplateContent) {
        if (user?.id) clearWorkspaceDraft(user.id, 'new');

        const navTemplateId = activeTemplateId || null;
        const navTemplateContent = activeTemplateContent;
        setTemplateId(navTemplateId);
        setStaticTemplateTitle(location.state?.templateTitle || TEMPLATE_TITLES[navTemplateId] || 'Mẫu CV có sẵn');
        setEditorInstanceKey(`template:${navTemplateId || 'custom'}:${location.search || location.key}`);
        setMessages([]);
        setInputValue('');
        setCvDocument(null);
        setEditableContent(navTemplateContent);
        setEditableContentFormat('markdown');
        setEditableMarkdown(navTemplateContent);
        setDocumentDirty(false);
        setOutputFormat('markdown');
        setLoading(false);
      }
      // If we came from the home page with an initial prompt
      else if (location.state?.initialPrompt) {
        if (user?.id) clearWorkspaceDraft(user.id, 'new');

        const initialPrompt = location.state.initialPrompt;
        const navTemplateId = location.state.templateId || null;
        const navTemplateContent = location.state.templateContent || '';
        setTemplateId(navTemplateId);
        setStaticTemplateTitle('');
        setEditorInstanceKey(navTemplateContent ? `prompt-template:${navTemplateId || 'custom'}:${location.key}` : `prompt:${location.key}`);
        const initialMsgs = [{ role: 'user', content: initialPrompt }];
        setMessages(initialMsgs);
        setInputValue('');
        setCvDocument(null);

        // If template has skeleton content, show it immediately in Document Viewer
        if (navTemplateContent) {
          setEditableContent(navTemplateContent);
          setEditableContentFormat('markdown');
          setEditableMarkdown(navTemplateContent);
          setDocumentDirty(false);
          setOutputFormat('markdown');
        } else {
          setEditableContent('');
          setEditableContentFormat('markdown');
          setEditableMarkdown('');
          setDocumentDirty(false);
          setOutputFormat('markdown');
        }
        setLoading(true);

        // Send to backend
        handleChatTurn(initialMsgs, 'markdown', navTemplateId);
      } else {
        // Empty workspace or restore unfinished draft
        setTemplateId(null);
        setStaticTemplateTitle('');
        setEditorInstanceKey(`empty:${location.key}`);

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
          setEditableContentFormat('markdown');
          setEditableMarkdown('');
          setDocumentDirty(false);
          setLoading(Boolean(draft.pending));
          setOutputFormat(normalizeOutputFormat(draft.outputFormat));
          setRestoredDraft(true);
        } else {
          setMessages([]);
          setInputValue('');
          setCvDocument(null);
          setEditableContent('');
          setEditableContentFormat('markdown');
          setEditableMarkdown('');
          setDocumentDirty(false);
          setLoading(false);
          setOutputFormat('markdown');
        }
      }

      hydratedDraftRef.current = true;
    };
    initWorkspace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, location.state, location.key, location.search, user?.id, scope, navigate]);

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
      generatedCvId: cvDocument?.id || null,
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
        setEditableContentFormat('markdown');
        setEditableMarkdown('');
        setDocumentDirty(false);
      }
      setSaveMessage('');
      return;
    }
    const editorState = extractEditorStateFromDocument(cvDocument);
    setEditableContent(editorState.value);
    setEditableContentFormat(editorState.valueFormat);
    setEditableMarkdown(editorState.markdown);
    setDocumentDirty(false);
    setSaveMessage('');
  }, [cvDocument?.id, cvDocument?.generated_content?.content, cvDocument?.generated_content?.markdown, cvDocument?.generated_content?.html, cvDocument?.generated_content?.import_preview_format]);

  useEffect(() => {
    let mounted = true;

    if (!cvDocument?.id) {
      setVersionHistory([]);
      return undefined;
    }

    getGeneratedCVVersions(cvDocument.id)
      .then((res) => {
        if (mounted) {
          setVersionHistory(Array.isArray(res?.data) ? res.data : []);
        }
      })
      .catch((error) => {
        console.error('Failed to load generated CV versions:', error);
        if (mounted) setVersionHistory([]);
      });

    return () => {
      mounted = false;
    };
  }, [cvDocument?.id]);

  const [streamAiReply, setStreamAiReply] = useState('');
  const [streamCvText, setStreamCvText] = useState('');

  const handleChatTurn = async (currentMessages, formatOverride = outputFormat, templateOverride = templateId) => {
    if (!user?.id) return;
    setLoading(true);
    setStreamAiReply('');
    setStreamCvText('');
    setChatStatus({ state: 'reasoning', label: 'AI đang phân tích yêu cầu...' });
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
      const activeCvId = cvDocument?.id || null;

      await streamChatCVGeneration(currentMessages, normalizeOutputFormat(formatOverride), (val) => {
        const { event, data } = val;

        if (event === 'status') {
          setChatStatus(data);
        } else if (event === 'chat_chunk') {
          finalReply += data;
          setStreamAiReply(finalReply);
        } else if (event === 'cv_chunk') {
          finalcvtext += data;
          setStreamCvText(finalcvtext);
          // Auto-update editable content so user sees typing effect
          setEditableContent(finalcvtext);
          setEditableContentFormat('markdown');
          setEditableMarkdown(finalcvtext);
        } else if (event === 'cv_id') {
          idcv = data;
        } else if (event === 'signal') {
          // Do nothing special yet
        } else if (event === 'error') {
          console.error("AI Error:", data);
        }
      }, templateOverride, activeCvId);

      const finalMessages = [...currentMessages, { role: 'assistant', content: finalReply || 'Mình đã xử lý xong yêu cầu.' }];

      if (mountedRef.current) {
        setMessages(finalMessages);
        setStreamAiReply('');
        setStreamCvText('');
        setChatStatus(null);
      }

      if (idcv) {
        let loadedCv = null;
        try {
          const cvRes = await getGeneratedCV(idcv);
          loadedCv = cvRes.data;
          if (mountedRef.current) {
            setStaticTemplateTitle('');
            setEditorInstanceKey(`doc:${loadedCv.id}`);
            setCvDocument(loadedCv);
            const editorState = extractEditorStateFromDocument(loadedCv);
            setEditableContent(editorState.value);
            setEditableContentFormat(editorState.valueFormat);
            setEditableMarkdown(editorState.markdown);
            setDocumentDirty(false);
          }
        } catch (e) {
          console.error('Failed to load generated CV after stream finish:', e);
        }

        if (user?.id) {
          const nextScope = getDraftScope(idcv);
          saveWorkspaceDraft({
            userId: user.id,
            scope: nextScope,
            messages: finalMessages,
            inputValue: '',
            title: loadedCv?.base_profile_data?.job_title || cvDocument?.base_profile_data?.job_title || '',
            pending: false,
            generatedCvId: idcv,
            outputFormat: normalizeOutputFormat(formatOverride),
          });
          if (scope !== nextScope) {
            clearWorkspaceDraft(user.id, scope);
          }
        }
        notifyGeneratedCvHistoryChanged();

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
        setChatStatus(null);
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
    setChatStatus(null);
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
            setEditableContentFormat('markdown');
            setEditableMarkdown(data.data);
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
    window.requestAnimationFrame(() => resizeChatInput(chatInputRef.current));
    handleChatTurn(newMsgs, outputFormat);
  };

  const documentFormat = cvDocument
    ? inferOutputFormatFromDocument(cvDocument, outputFormat)
    : normalizeOutputFormat(outputFormat);
  const hasUnsavedEdits = Boolean(cvDocument) && documentDirty;
  const isImportedDocument = cvDocument?.generated_content?.import_preview_format === 'html';
  const isStaticTemplate = Boolean(!cvDocument && templateId && editableContent);
  const documentTitle = cvDocument
    ? cvDocument.base_profile_data?.job_title || (isImportedDocument ? 'CV đã import' : 'CV đã tạo')
    : isStaticTemplate
      ? staticTemplateTitle || 'Mẫu CV có sẵn'
      : 'Workspace CV';
  const documentSubtitle = cvDocument
    ? isImportedDocument
      ? 'Nội dung đã được chuyển thành bản chỉnh sửa trực tiếp từ file PDF/DOCX.'
      : 'Chỉnh sửa nội dung và lưu mỗi lần thành một version mới.'
    : isStaticTemplate
      ? 'Mẫu CV có sẵn đã được mở trực tiếp. Chỉnh nội dung trong editor hoặc chat tiếp nếu cần biến đổi bằng AI.'
      : 'Tài liệu sẽ xuất hiện tại đây sau khi bạn tạo hoặc import CV.';
  const showChatStarter = !messages.length && !streamAiReply && !loading && !analysisMode && !analysisResults;

  const handleSaveEdits = async () => {
    if (!cvDocument?.id || savingEdits) return null;
    if (!hasUnsavedEdits) return cvDocument;

    setSavingEdits(true);
    setSaveMessage('Đang lưu thành phiên bản mới...');
    try {
      const res = await createGeneratedCVVersion(cvDocument.id, {
        content: editableMarkdown,
        output_format: documentFormat,
      });
      setCvDocument(res.data);
      const editorState = extractEditorStateFromDocument(res.data);
      setEditableContent(editorState.value);
      setEditableContentFormat(editorState.valueFormat);
      setEditableMarkdown(editorState.markdown);
      setDocumentDirty(false);
      setSaveMessage(`Đã lưu phiên bản v${res.data.version}`);
      if (user?.id) {
        const nextScope = getDraftScope(res.data.id);
        saveWorkspaceDraft({
          userId: user.id,
          scope: nextScope,
          messages,
          inputValue,
          title: res.data.base_profile_data?.job_title || '',
          pending: false,
          generatedCvId: res.data.id,
          outputFormat: documentFormat,
        });
        if (scope !== nextScope) {
          clearWorkspaceDraft(user.id, scope);
        }
      }
      notifyGeneratedCvHistoryChanged();
      if (mountedRef.current && res.data?.id && res.data.id !== id) {
        navigate(`/workspace/${res.data.id}`, { replace: true, state: { keepMessages: true } });
      }
      return res.data;
    } catch (error) {
      console.error('Failed to save generated CV edits:', error);
      setSaveMessage('Lưu thất bại, vui lòng thử lại');
      return null;
    } finally {
      setSavingEdits(false);
    }
  };

  const handleExport = async () => {
    if (exporting) return;

    const exportFormat = cvDocument
      ? inferOutputFormatFromDocument(cvDocument, documentFormat)
      : normalizeOutputFormat(documentFormat);
    const fallbackExt = exportFormat === 'docx' ? 'docx' : 'md';
    const localMarkdown = editableMarkdown || (editableContentFormat === 'markdown' ? editableContent : '');

    setExporting(true);
    try {
      if (exportFormat === 'markdown') {
        if (!localMarkdown.trim()) {
          setSaveMessage('CV không có nội dung để download.');
          return;
        }

        downloadBlob(
          new Blob([localMarkdown], { type: 'text/markdown;charset=utf-8' }),
          buildClientExportFilename(
            cvDocument?.base_profile_data?.job_title || staticTemplateTitle || documentTitle,
            fallbackExt
          )
        );
        return;
      }

      if (!cvDocument?.id) {
        setSaveMessage('Download DOCX chỉ khả dụng sau khi CV đã được tạo hoặc lưu.');
        return;
      }

      let activeDocument = cvDocument;
      if (hasUnsavedEdits) {
        const savedDocument = await handleSaveEdits();
        if (!savedDocument) return;
        activeDocument = savedDocument;
      }

      const response = await downloadGeneratedCV(activeDocument.id, exportFormat);
      const headerValue = response.headers?.['content-disposition'] || response.headers?.['Content-Disposition'];
      const filename = parseFilenameFromDisposition(headerValue) || `generated_cv.${fallbackExt}`;
      const blob = response.data instanceof Blob ? response.data : new Blob([response.data]);
      downloadBlob(blob, filename);
    } catch (error) {
      console.error('Failed to export generated CV:', error);
      setSaveMessage('Download thất bại, vui lòng thử lại.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className={`workspace-container workspace-layout-${layoutMode} fade-in`}>
      {/* Left Pane: Chat Interaction */}
      <div className="workspace-chat-pane">
        <div className="chat-header">
          <div className="chat-header-main">
            <div className="chat-header-title">
              <SparklesIcon className="chat-header-icon" />
              <div className="chat-header-copy">
                <span>CV Assistant</span>
                <small>
                  {cvDocument
                    ? 'Mô tả thay đổi ở bên trái, tài liệu sẽ cập nhật và lưu theo version.'
                    : 'Tạo, phân tích và chỉnh sửa CV trên cùng một màn hình.'}
                </small>
              </div>
            </div>
          </div>
          <span className={`chat-header-status ${loading ? 'busy' : ''}`}>
            {loading ? 'Đang xử lý' : 'Sẵn sàng'}
          </span>
        </div>
        {restoredDraft && (
          <div className="workspace-draft-banner">
            Đã khôi phục phiên chat đang làm dở.
          </div>
        )}

        <div className="chat-history auto-scroll-y">
          {showChatStarter && (
            <div className="workspace-chat-intro">
              <span className="workspace-chat-intro-badge">
                {cvDocument ? 'CV đã sẵn sàng' : 'Bắt đầu nhanh'}
              </span>
              <h3>
                {cvDocument
                  ? 'Bạn muốn AI sửa CV theo hướng nào?'
                  : 'Bắt đầu tạo hoặc phân tích CV ngay tại đây'}
              </h3>
              <p>
                {cvDocument
                  ? 'Gửi yêu cầu ngắn gọn như viết lại kinh nghiệm, tối ưu theo JD, rút gọn summary hoặc đánh bóng thông tin ứng tuyển.'
                  : 'Nhập prompt để tạo CV mới, hoặc mở chế độ phân tích ở phía dưới để upload CV và job description.'}
              </p>
              <div className="workspace-chat-suggestions">
                {EMPTY_CHAT_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="workspace-chat-suggestion"
                    onClick={() => setInputValue(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
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
                <div className="chat-waiting-copy">
                  <div className="chat-waiting-dots">
                    <span></span><span></span><span></span>
                  </div>
                  <strong>{chatStatus?.label || 'AI đang suy luận...'}</strong>
                  <small>
                    {cvDocument
                      ? 'Yêu cầu sẽ được áp vào CV hiện tại và lưu thành phiên bản mới.'
                      : 'Hệ thống đang chuẩn bị phản hồi và tài liệu cho bạn.'}
                  </small>
                </div>
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
          <div className="workspace-composer">
            <div className="workspace-composer-top">
              <div className="workspace-composer-toolbar">
                <button
                  type="button"
                  className={`workspace-mode-chip ${showAttachPanel ? 'active' : ''}`}
                  onClick={() => setShowAttachPanel(!showAttachPanel)}
                  disabled={loading}
                  title="Phân tích CV"
                >
                  <span className="workspace-mode-chip-icon">📎</span>
                  <span>Phân tích CV</span>
                </button>
                <div className="workspace-format-selector" role="group" aria-label="Output format selector">
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
              </div>
              <span className="workspace-composer-meta">
                {showAttachPanel
                  ? 'Đính kèm CV và JD ở phía trên để chấm điểm, phân tích và tối ưu.'
                  : 'Enter để gửi. Shift + Enter để xuống dòng.'}
              </span>
            </div>
            <div className="chat-input-wrapper" onClick={() => chatInputRef.current?.focus()}>
              <textarea
                ref={chatInputRef}
                className="chat-input"
                rows={2}
                placeholder={showAttachPanel ? 'Đính kèm CV + JD ở phía trên để phân tích...' : 'Nhập yêu cầu của bạn (VD: thêm JD, đổi title...)'}
                value={inputValue}
                onChange={(e) => {
                  setInputValue(e.target.value);
                  resizeChatInput(e.target);
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
          </div>
        </form>
      </div>

      {/* Right Pane: Document Viewer */}
      <div className="workspace-doc-pane">
        <div className="doc-header">
          <div className="doc-header-main">
            <div className="doc-title">
              <div className="doc-icon-shell">
                <DocumentCheckIcon className="doc-icon" />
              </div>
              <div className="doc-title-copy">
                <span className="doc-title-text">{documentTitle}</span>
                <span className="doc-title-caption">{documentSubtitle}</span>
              </div>
            </div>
            {(cvDocument || editableContent) && (
              <div className="doc-meta">
                <span className="doc-format-chip">{OUTPUT_FORMAT_LABELS[documentFormat]}</span>
                {cvDocument?.version ? (
                  <span className="doc-version-chip">{`v${cvDocument.version}`}</span>
                ) : null}
                {hasUnsavedEdits ? <span className="doc-dirty-chip">Chưa lưu</span> : null}
              </div>
            )}
          </div>
          {(cvDocument || editableContent) && (
            <div className="doc-actions">
              <div className="workspace-layout-switch" role="group" aria-label="Điều chỉnh bố cục workspace">
                {LAYOUT_MODES.map((mode) => (
                  <button
                    key={mode.value}
                    type="button"
                    className={`workspace-layout-chip ${layoutMode === mode.value ? 'active' : ''}`}
                    onClick={() => setLayoutMode(mode.value)}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
              {cvDocument && versionHistory.length > 0 && (
                <label className="doc-version-select-wrap">
                  <span>Phiên bản</span>
                  <select
                    className="doc-version-select"
                    value={cvDocument.id}
                    onChange={(e) => navigate(`/workspace/${e.target.value}`, { replace: true, state: { keepMessages: true } })}
                  >
                    {versionHistory.map((version) => (
                      <option key={version.id} value={version.id}>
                        {`v${version.version}`}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {cvDocument && (
                <button
                  type="button"
                  className={`btn-ghost doc-action-btn ${hasUnsavedEdits ? 'doc-action-btn-highlight' : ''}`}
                  onClick={handleSaveEdits}
                  disabled={savingEdits || !hasUnsavedEdits}
                >
                  {savingEdits ? 'Đang lưu...' : 'Lưu thành version mới'}
                </button>
              )}
              <button
                type="button"
                className="btn-primary doc-download-btn"
                onClick={handleExport}
                disabled={exporting || !editableContent}
              >
                {exporting ? 'Đang tải...' : `Download ${OUTPUT_FORMAT_LABELS[documentFormat]}`}
              </button>
            </div>
          )}
        </div>
        {(cvDocument || editableContent) && saveMessage && (
          <div className="doc-save-status">{saveMessage}</div>
        )}

        <div className="doc-content-wrapper">
          {(cvDocument || editableContent) ? (
            <div className="a4-paper cv-document">
              <CvWysiwygEditor
                key={editorInstanceKey}
                value={editableContent}
                valueFormat={editableContentFormat}
                format={documentFormat}
                onChange={({ markdown, html }) => {
                  setEditableContent(html);
                  setEditableContentFormat('html');
                  setEditableMarkdown(markdown);
                  setDocumentDirty(true);
                }}
                readOnly={savingEdits}
              />
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon-wrapper">
                <DocumentCheckIcon className="empty-icon" />
              </div>
              <p className="empty-title">Chưa có CV để chỉnh sửa</p>
              <p className="empty-subtext">Hãy chat với AI ở bên trái để bắt đầu tạo CV nhé.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
