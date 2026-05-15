import { useState, useEffect, useMemo, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  classifyDocument,
  createAnalysisFromGeneratedCV,
  createChatSession,
  createGeneratedCVVersion,
  downloadGeneratedCV,
  exportPreviewDocx,
  getChatSession,
  getLatestConversationCV,
  getGeneratedCV,
  getGeneratedCVVersions,
  importGeneratedCV,
  importGeneratedCVVersion,
  normalizeImportedCV,
  streamChatAnalysis,
  streamChatCVGeneration,
  updateChatSessionMessages,
} from '../api';
import { useAuth } from '../AuthContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import { DocumentCheckIcon } from '@heroicons/react/24/outline';
import CvWysiwygEditor from '../components/CvWysiwygEditor';
import {
  clearWorkspaceDraft,
  getDraftScope,
  loadWorkspaceDraft,
  saveWorkspaceDraft,
} from '../utils/workspaceDraft';
import {
  getJdEvaluationAdvice,
  getJdEvaluationSummary,
  getSalaryAdvice,
  getSalaryRange,
} from '../utils/analysisInsights';
import { notifyGeneratedCvHistoryChanged } from '../utils/generatedCvHistory';
import { TEMPLATE_SKELETONS } from '../utils/templateSkeletons';

const TEMPLATE_TITLES = {
  ats_clean: 'Chuẩn ATS',
  executive: 'Quản lý / Chuyên gia',
  tech_engineer: 'Kỹ sư / CNTT',
  fresh_graduate: 'Sinh viên mới tốt nghiệp',
};

const EMPTY_CHAT_PROMPTS = [
  'Rút gọn phần Summary theo hướng quản lý hơn',
  'Viết lại kinh nghiệm để nổi bật vai trò Kỹ sư Backend',
  'Tối ưu CV này theo JD tôi sắp dán vào',
];

const CHAT_INPUT_MIN_HEIGHT = 52;
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

const GENERIC_CONVERSATION_TITLES = new Set([
  'cv từ chatbot',
  'cv tu chatbot',
  'cv đã tạo',
  'cv da tao',
  'generated_cv',
  'generated cv',
  'cuộc trò chuyện mới',
  'cuoc tro chuyen moi',
]);

const normalizeConversationTitleText = (value, limit = 72) => String(value || '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/\[(.*?)\]\((.*?)\)/g, '$1')
  .replace(/[*_`>#]+/g, ' ')
  .replace(/https?:\/\/\S+/g, ' ')
  .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .replace(/^[-:.,;]+|[-:.,;]+$/g, '')
  .slice(0, limit)
  .replace(/[-:.,;]+$/g, '');

const isGenericConversationTitle = (value) => {
  const normalized = normalizeConversationTitleText(value, 120).toLowerCase();
  return !normalized || GENERIC_CONVERSATION_TITLES.has(normalized);
};

const toRoleTitle = (value) => {
  const cleaned = normalizeConversationTitleText(value, 64)
    .replace(/\b(mà|ma|và|va|với|voi|theo|cho|của|cua|này|nay|đó|do|nó|no|match|khớp|khop)\b.*$/i, '')
    .trim();
  if (!cleaned) return '';

  const aliasMap = {
    aie: 'AI Engineer',
    'ai engineer': 'AI Engineer',
    'ai intern': 'AI Intern',
    'ai/ml intern': 'AI/ML Intern',
    'ml intern': 'ML Intern',
    'backend intern': 'Backend Intern',
    'frontend intern': 'Frontend Intern',
    'software engineer': 'Software Engineer',
    'software engineer intern': 'Software Engineer Intern',
    'data analyst': 'Data Analyst',
    'data analyst intern': 'Data Analyst Intern',
  };
  const lowered = cleaned.toLowerCase();
  if (aliasMap[lowered]) return aliasMap[lowered];
  const aieMatch = lowered.match(/^(?:(intern|fresher|junior|senior)\s+)?aie$/);
  if (aieMatch) {
    const level = aieMatch[1];
    return level ? `${level.charAt(0).toUpperCase() + level.slice(1)} AI Engineer` : 'AI Engineer';
  }

  return cleaned.split(/\s+/).map((word) => {
    const lowerWord = word.toLowerCase();
    if (['ai', 'ml', 'qa', 'ba', 'ui', 'ux', 'jd', 'cv'].includes(lowerWord)) return lowerWord.toUpperCase();
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ');
};

const extractRoleTitle = (text) => {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return '';

  const rolePatterns = [
    /\b(?:ai|machine learning|ml|data|backend|frontend|fullstack|full-stack|software|web|mobile|devops|qa|tester|business analyst|ba)\s+(?:engineer|developer|intern|fresher|analyst|specialist)\b/i,
    /\b(?:intern|fresher|junior|middle|mid-level|senior)\s+(?:ai|machine learning|ml|data|backend|frontend|fullstack|full-stack|software|web|mobile|devops|qa|tester|developer|engineer|analyst)\b/i,
    /\b(?:java|python|react|node(?:\.js)?|php|\.net|c#|golang|android|ios)\s+(?:developer|engineer|intern|fresher)\b/i,
  ];
  for (const pattern of rolePatterns) {
    const match = normalized.match(pattern);
    if (match?.[0]) return toRoleTitle(match[0]);
  }

  const markerMatch = normalized.match(/(?:role|vị trí|vi tri|ứng tuyển|ung tuyen|apply|cho anh cv|tạo cv|tao cv|viết cv|viet cv)\s+(?:là|la|cho|role|vị trí|vi tri)?\s*[:-]?\s*([a-zA-ZÀ-ỹ0-9+#./ -]{3,60})/i);
  if (markerMatch?.[1]) {
    const candidate = toRoleTitle(markerMatch[1]);
    if (candidate && candidate.split(/\s+/).length <= 6) return candidate;
  }

  return '';
};

const buildFirstQueryTitle = (messages) => {
  if (!Array.isArray(messages)) return '';
  const firstUserMessage = messages.find((message) => (
    message?.role === 'user' && String(message.content || '').trim()
  ));
  if (!firstUserMessage) return '';

  const lines = String(firstUserMessage.content || '')
    .split(/\r?\n/)
    .map((line) => normalizeConversationTitleText(line, 180))
    .filter(Boolean);
  return lines[0] || normalizeConversationTitleText(firstUserMessage.content, 180);
};

const buildConversationTitle = (messages, fallback = '') => {
  const firstQueryTitle = buildFirstQueryTitle(messages);
  if (firstQueryTitle) return firstQueryTitle;

  if (!isGenericConversationTitle(fallback)) {
    const fallbackTitle = toRoleTitle(fallback);
    if (fallbackTitle.toLowerCase().includes('mẫu cv')) {
      return normalizeConversationTitleText(fallbackTitle, 72);
    }
    return normalizeConversationTitleText(
      fallbackTitle.toLowerCase().startsWith('cv ') ? fallbackTitle : `CV ${fallbackTitle}`,
      72
    );
  }

  const userMessages = Array.isArray(messages)
    ? messages
      .filter((message) => message?.role === 'user' && String(message.content || '').trim())
      .map((message) => String(message.content || '').trim())
    : [];
  if (!userMessages.length) return 'Cuộc trò chuyện mới';

  const combined = userMessages.join('\n');
  const lowered = combined.toLowerCase();

  if (lowered.includes('jd') && lowered.includes('cv') && ['match', 'khớp', 'khop', 'tương ứng', 'tuong ung'].some((token) => lowered.includes(token))) {
    return 'Tạo JD và CV khớp nhau';
  }
  if (['phân tích cv', 'phan tich cv', 'phân tích tài liệu', 'phan tich tai lieu'].some((token) => lowered.includes(token))
    && ['jd', 'job', 'mô tả', 'mo ta'].some((token) => lowered.includes(token))) {
    return 'Phân tích CV theo JD';
  }
  if (lowered.includes('tài liệu đính kèm') || lowered.includes('tai lieu dinh kem')) return 'Xử lý tài liệu đính kèm';
  if (['mẫu cv', 'mau cv', 'template cv', 'các mẫu', 'cac mau'].some((token) => lowered.includes(token))) return 'Tư vấn mẫu CV';

  const roleTitle = extractRoleTitle(combined);
  if (roleTitle && ['cv', 'resume', 'hồ sơ', 'ho so', 'ứng tuyển', 'ung tuyen'].some((token) => lowered.includes(token))) {
    return roleTitle.toLowerCase().startsWith('cv ') ? roleTitle : `CV ${roleTitle}`;
  }
  if (['gen cv', 'tạo cv', 'tao cv', 'viết cv', 'viet cv'].some((token) => lowered.includes(token))) return 'Tạo CV bằng AI';
  if (['sửa cv', 'sua cv', 'chỉnh cv', 'chinh cv', 'rewrite', 'cập nhật', 'cap nhat'].some((token) => lowered.includes(token))) return 'Chỉnh sửa CV';
  if (['tôi tên', 'toi ten', 'anh tên', 'em tên', 'học trường', 'hoc truong', 'chuyên ngành', 'chuyen nganh', 'kinh nghiệm', 'kinh nghiem', 'dự án', 'du an'].some((token) => lowered.includes(token))) {
    return 'Hoàn thiện thông tin CV';
  }

  const shortFallback = normalizeConversationTitleText(userMessages[0], 48);
  return shortFallback && shortFallback.split(/\s+/).length <= 8 ? shortFallback : 'Cuộc trò chuyện CV';
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
  const routeConversationId = useMemo(
    () => new URLSearchParams(location.search).get('conversation'),
    [location.search]
  );

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [cvDocument, setCvDocument] = useState(null);
  const [editableContent, setEditableContent] = useState('');
  const [editableContentFormat, setEditableContentFormat] = useState('markdown');
  const [editableMarkdown, setEditableMarkdown] = useState('');
  const [documentDirty, setDocumentDirty] = useState(false);
  const [outputFormat, setOutputFormat] = useState('markdown');
  const [exporting, setExporting] = useState(false);
  const [analyzingCurrentCv, setAnalyzingCurrentCv] = useState(false);
  const [savingEdits, setSavingEdits] = useState(false);
  const [normalizingImport, setNormalizingImport] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [chatStatus, setChatStatus] = useState(null);
  const [versionHistory, setVersionHistory] = useState([]);
  const [chatPaneWidth, setChatPaneWidth] = useState(null);
  const [staticTemplateTitle, setStaticTemplateTitle] = useState('');
  const [editorInstanceKey, setEditorInstanceKey] = useState('empty');
  const [conversationId, setConversationId] = useState(null);

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
  const workspaceRef = useRef(null);
  const resizeCleanupRef = useRef(null);
  const initializedNav = useRef(null);
  const hydratedDraftRef = useRef(false);
  const mountedRef = useRef(false);
  const scope = id ? getDraftScope(id) : (routeConversationId ? `conversation:${routeConversationId}` : 'new');

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      resizeCleanupRef.current?.();
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
    const searchParams = new URLSearchParams(location.search);
    const routeTemplateId = searchParams.get('template');
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
          : routeConversationId
            ? `conversation:${routeConversationId}`
            : `empty:${location.key}`;

    if (initializedNav.current === navKey) return;
    initializedNav.current = navKey;
    hydratedDraftRef.current = false;
    setAnalysisMode(false);
    setAnalysisSteps({});
    setAnalysisResults(null);
    setShowAttachPanel(false);
    setAttachedCvFile(null);
    setAttachedJdText('');
    setChatStatus(null);
    setVersionHistory([]);
    setConversationId(routeConversationId || null);

    const initWorkspace = async () => {
      const draft = user?.id ? loadWorkspaceDraft(user.id, scope) : null;

      // If we are given an ID in URL, we are viewing an existing generated CV session
      if (id) {
        setTemplateId(null);
        try {
          const res = await getGeneratedCV(id);
          setTemplateId(null);
          setConversationId(res.data.conversation_id || null);
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
            if (draft?.pending && draft?.messages?.length) {
              setMessages(draft.messages);
              setInputValue(draft.inputValue || '');
              setLoading(Boolean(draft.pending));
              setOutputFormat(normalizeOutputFormat(draft.outputFormat || serverFormat));
            } else {
              setMessages(serverMessages);
              setInputValue(draft?.inputValue || '');
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
      } else if (routeConversationId) {
        setTemplateId(null);
        setStaticTemplateTitle('');
        setEditorInstanceKey(`conversation:${routeConversationId}`);
        try {
          const res = await getChatSession(routeConversationId);
          let latestConversationCv = null;
          try {
            const latestCvRes = await getLatestConversationCV(routeConversationId);
            latestConversationCv = latestCvRes?.data || null;
          } catch {
            // A conversation can exist without any generated CV yet.
            latestConversationCv = null;
          }

          setConversationId(res.data.conversation_id || routeConversationId);
          const serverMessages = Array.isArray(res.data.messages) ? res.data.messages : [];
          const draftMessages = Array.isArray(draft?.messages) ? draft.messages : [];
          setMessages(draftMessages.length > 0 ? draftMessages : serverMessages);
          setInputValue('');
          setCvDocument(latestConversationCv);
          if (latestConversationCv) {
            setEditorInstanceKey(`doc:${latestConversationCv.id}`);
            const editorState = extractEditorStateFromDocument(latestConversationCv);
            setEditableContent(editorState.value);
            setEditableContentFormat(editorState.valueFormat);
            setEditableMarkdown(editorState.markdown);
            setOutputFormat(inferOutputFormatFromDocument(latestConversationCv, draft?.outputFormat || 'markdown'));
          } else {
            setEditableContent(draft?.previewContent || draft?.previewMarkdown || '');
            setEditableContentFormat(draft?.previewFormat || 'markdown');
            setEditableMarkdown(draft?.previewMarkdown || draft?.previewContent || '');
            setOutputFormat(normalizeOutputFormat(draft?.outputFormat || 'markdown'));
          }
          setDocumentDirty(false);
          setLoading(false);
        } catch (error) {
          console.error('Failed to load chat session:', error);
          setMessages(draft?.messages || []);
          setInputValue('');
          setCvDocument(null);
          setEditableContent(draft?.previewContent || draft?.previewMarkdown || '');
          setEditableContentFormat(draft?.previewFormat || 'markdown');
          setEditableMarkdown(draft?.previewMarkdown || draft?.previewContent || '');
          setDocumentDirty(false);
          setLoading(false);
          setOutputFormat(normalizeOutputFormat(draft?.outputFormat || 'markdown'));
        }
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

        if (
          draft?.messages?.length ||
          draft?.inputValue?.trim() ||
          draft?.pending ||
          draft?.previewContent?.trim() ||
          draft?.previewMarkdown?.trim()
        ) {
          setMessages(draft.messages || []);
          setInputValue(draft.inputValue || '');
          setCvDocument(null);
          setEditableContent(draft.previewContent || draft.previewMarkdown || '');
          setEditableContentFormat(draft.previewFormat || 'markdown');
          setEditableMarkdown(draft.previewMarkdown || draft.previewContent || '');
          setDocumentDirty(false);
          setLoading(Boolean(draft.pending));
          setOutputFormat(normalizeOutputFormat(draft.outputFormat));
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
      previewContent: editableContent,
      previewFormat: editableContentFormat,
      previewMarkdown: editableMarkdown,
    });
  }, [
    user?.id,
    scope,
    messages,
    inputValue,
    cvDocument?.base_profile_data?.job_title,
    cvDocument?.id,
    loading,
    outputFormat,
    editableContent,
    editableContentFormat,
    editableMarkdown,
  ]);

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
  }, [cvDocument]);

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

  const ensureConversationId = async () => {
    if (cvDocument?.conversation_id) return cvDocument.conversation_id;
    if (conversationId) return conversationId;
    const res = await createChatSession();
    const nextConversationId = res.data.conversation_id;
    setConversationId(nextConversationId);
    return nextConversationId;
  };

  const persistChatMessages = async (nextMessages) => {
    const activeConversationId = await ensureConversationId();
    await updateChatSessionMessages(activeConversationId, nextMessages);
    return activeConversationId;
  };

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
      let activeConversationId = await ensureConversationId();
      const activeCvId = cvDocument?.id || null;

      await streamChatCVGeneration(currentMessages, normalizeOutputFormat(formatOverride), (val) => {
        const { event, data } = val;

        if (event === 'conversation_id') {
          activeConversationId = data;
          setConversationId(data);
        } else if (event === 'status') {
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
      }, templateOverride, activeCvId, activeConversationId);

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
            setConversationId(loadedCv.conversation_id || activeConversationId);
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
          const previewState = loadedCv
            ? extractEditorStateFromDocument(loadedCv)
            : { value: finalcvtext, valueFormat: 'markdown', markdown: finalcvtext };
          saveWorkspaceDraft({
            userId: user.id,
            scope: nextScope,
            messages: finalMessages,
            inputValue: '',
            title: loadedCv?.base_profile_data?.job_title || cvDocument?.base_profile_data?.job_title || '',
            pending: false,
            generatedCvId: idcv,
            outputFormat: normalizeOutputFormat(formatOverride),
            previewContent: previewState.value,
            previewFormat: previewState.valueFormat,
            previewMarkdown: previewState.markdown,
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
        if (activeConversationId && mountedRef.current) {
          setConversationId(activeConversationId);
          const nextSearch = `?conversation=${activeConversationId}`;
          if (!id && location.search !== nextSearch) {
            navigate(`/workspace${nextSearch}`, { replace: true, state: { keepMessages: true } });
          }
        }
        // Save the draft state
        saveWorkspaceDraft({
          userId: user.id,
          scope,
          messages: finalMessages,
          inputValue: '',
          title: cvDocument?.base_profile_data?.job_title || '',
          pending: false,
          outputFormat,
          previewContent: finalcvtext || editableContent,
          previewFormat: finalcvtext ? 'markdown' : editableContentFormat,
          previewMarkdown: finalcvtext || editableMarkdown,
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
    const analysisText = (showAttachPanel ? inputValue : attachedJdText).trim();
    const hasAttachedText = analysisText.length > 0;
    const hasAttachedFile = Boolean(attachedCvFile);
    if (loading || (!hasAttachedText && !hasAttachedFile)) return;

    if (cvDocument?.id) {
      const fileLabel = attachedCvFile ? `\n\n**Tài liệu đính kèm:** ${attachedCvFile.name}` : '';
      const userContent = attachedCvFile && !hasAttachedText
        ? `Xử lý tài liệu đính kèm cho CV hiện tại:${fileLabel}`
        : `Phân tích CV hiện tại theo JD sau:${fileLabel}${hasAttachedText ? `\n\n${analysisText}` : ''}`;
      const newMsgs = [
        ...messages,
        {
          role: 'user',
          content: userContent,
        },
      ];
      setMessages(newMsgs);
      setLoading(true);
      setAnalyzingCurrentCv(true);
      setChatStatus({ state: 'analysis', label: 'Đang tạo phiên phân tích từ CV hiện tại...' });
      setShowAttachPanel(false);
      let activeDocument = cvDocument;

      try {
        if (hasUnsavedEdits) {
          const savedDocument = await handleSaveEdits();
          if (!savedDocument) return;
          activeDocument = savedDocument;
        }
        const res = await createAnalysisFromGeneratedCV(
          activeDocument.id,
          analysisText,
          attachedCvFile
        );
        const analysisId = res.data.id;
        const finalMsgs = [
          ...newMsgs,
          {
            role: 'assistant',
            content: `Đã tạo phiên phân tích từ CV hiện tại. [Xem kết quả phân tích](/analysis/${analysisId})`,
            analysisId,
          },
        ];
        setMessages(finalMsgs);
        await persistChatMessages(finalMsgs);
        if (user?.id) {
          saveWorkspaceDraft({
            userId: user.id,
            scope: getDraftScope(activeDocument.id),
            messages: finalMsgs,
            inputValue: '',
            title: activeDocument.base_profile_data?.job_title || '',
            pending: false,
            generatedCvId: activeDocument.id,
            outputFormat: documentFormat,
            previewContent: editableContent,
            previewFormat: editableContentFormat,
            previewMarkdown: editableMarkdown,
          });
        }
        setSaveMessage('Đã tạo phiên phân tích. Bạn có thể mở link kết quả ngay trong đoạn chat.');
      } catch (error) {
        console.error('Failed to analyze generated CV:', error);
        const detail = error.response?.data?.detail || '';
        const shouldImportAttachedCv = attachedCvFile && detail.includes('có vẻ là CV');
        let finalMsgs = [];

        if (shouldImportAttachedCv) {
          try {
            setChatStatus({ state: 'importing_cv', label: 'Đang thay CV đính kèm vào workspace hiện tại...' });
            const importRes = await importGeneratedCVVersion(activeDocument.id, attachedCvFile);
            const importedDocument = importRes.data;
            const editorState = extractEditorStateFromDocument(importedDocument);
            finalMsgs = [
              ...newMsgs,
              {
                role: 'assistant',
                content: `Tài liệu đính kèm là CV. Mình đã thay CV này vào workspace hiện tại và lưu thành v${importedDocument.version}.`,
              },
            ];
            setCvDocument(importedDocument);
            setStaticTemplateTitle('');
            setEditorInstanceKey(`doc:${importedDocument.id}`);
            setEditableContent(editorState.value);
            setEditableContentFormat(editorState.valueFormat);
            setEditableMarkdown(editorState.markdown);
            setDocumentDirty(false);
            setOutputFormat(inferOutputFormatFromDocument(importedDocument, documentFormat));
            setMessages(finalMsgs);
            await persistChatMessages(finalMsgs);
            if (user?.id) {
              const nextScope = getDraftScope(importedDocument.id);
              saveWorkspaceDraft({
                userId: user.id,
                scope: nextScope,
                messages: finalMsgs,
                inputValue: '',
                title: importedDocument.base_profile_data?.job_title || '',
                pending: false,
                generatedCvId: importedDocument.id,
                outputFormat: inferOutputFormatFromDocument(importedDocument, documentFormat),
                previewContent: editorState.value,
                previewFormat: editorState.valueFormat,
                previewMarkdown: editorState.markdown,
              });
              if (scope !== nextScope) {
                clearWorkspaceDraft(user.id, scope);
              }
            }
            notifyGeneratedCvHistoryChanged();
            if (importedDocument.id && importedDocument.id !== id) {
              navigate(`/workspace/${importedDocument.id}`, { replace: true, state: { keepMessages: true } });
            }
            return;
          } catch (importError) {
            console.error('Failed to import attached CV into workspace:', importError);
            finalMsgs = [
              ...newMsgs,
              {
                role: 'assistant',
                content: importError.response?.data?.detail || 'Tài liệu đính kèm là CV nhưng chưa thể thay vào workspace hiện tại.',
              },
            ];
          }
        } else {
          finalMsgs = [
            ...newMsgs,
            { role: 'assistant', content: detail || 'Không thể tạo phiên phân tích từ CV này.' },
          ];
        }

        setMessages(finalMsgs);
        await persistChatMessages(finalMsgs);
        if (user?.id) {
          saveWorkspaceDraft({
            userId: user.id,
            scope: getDraftScope(activeDocument?.id || cvDocument.id),
            messages: finalMsgs,
            inputValue: '',
            title: activeDocument?.base_profile_data?.job_title || cvDocument.base_profile_data?.job_title || '',
            pending: false,
            generatedCvId: activeDocument?.id || cvDocument.id,
            outputFormat: documentFormat,
            previewContent: editableContent,
            previewFormat: editableContentFormat,
            previewMarkdown: editableMarkdown,
          });
        }
      } finally {
        setLoading(false);
        setAnalyzingCurrentCv(false);
        setChatStatus(null);
        setAttachedCvFile(null);
        setAttachedJdText('');
        setInputValue('');
      }
      return;
    }

    if (!attachedCvFile) return;

    // No CV is open yet → we don't know up front whether the attachment is a
    // CV or a JD. Ask the backend to classify it so we route correctly instead
    // of hard-coding "file = CV, text = JD".
    const MIN_JD_CHARS = 60;
    const cvFileName = attachedCvFile.name;
    const userBubble = analysisText
      ? `Đính kèm tài liệu: **${cvFileName}**\n\n${analysisText}`
      : `Đính kèm tài liệu: **${cvFileName}**`;
    const baseMsgs = [...messages, { role: 'user', content: userBubble }];
    setMessages(baseMsgs);
    setLoading(true);
    setChatStatus({ state: 'classifying', label: 'Đang xác định tài liệu là CV hay JD...' });
    setShowAttachPanel(false);

    let classification;
    try {
      const res = await classifyDocument(attachedCvFile);
      classification = res.data;
    } catch (err) {
      console.error('Failed to classify attached document:', err);
      const detail = err.response?.data?.detail || 'Không đọc được tài liệu đính kèm. Vui lòng thử lại.';
      const failedMsgs = [...baseMsgs, { role: 'assistant', content: detail }];
      setMessages(failedMsgs);
      await persistChatMessages(failedMsgs);
      setLoading(false);
      setChatStatus(null);
      setAttachedCvFile(null);
      setAttachedJdText('');
      setInputValue('');
      return;
    }

    const documentType = classification?.document_type;
    const isCv = documentType === 'cv';
    const isJd = documentType === 'job_description';

    if (!isCv) {
      const fallbackMsg = isJd
        ? `Tài liệu **${cvFileName}** có vẻ là Job Description, không phải CV. Hãy đính kèm CV của bạn để mình bắt đầu phân tích nhé.`
        : `Mình chưa xác định được tài liệu **${cvFileName}** là CV hay JD (${classification?.reason || 'không đủ tín hiệu'}). Bạn có thể tải lại file CV rõ ràng hơn không?`;
      const finalMsgs = [...baseMsgs, { role: 'assistant', content: fallbackMsg }];
      setMessages(finalMsgs);
      await persistChatMessages(finalMsgs);
      setLoading(false);
      setChatStatus(null);
      setAttachedCvFile(null);
      setAttachedJdText('');
      setInputValue('');
      return;
    }

    // File is classified as a CV. If the user did NOT type a JD-sized blob,
    // treat the upload as "import this CV into the workspace" instead of
    // forcing the (useless) analyze pipeline with a non-JD text as JD.
    if (analysisText.length < MIN_JD_CHARS) {
      try {
        setChatStatus({ state: 'importing_cv', label: 'Đang import CV vào workspace...' });
        const formData = new FormData();
        formData.append('cv_file', attachedCvFile);
        const importRes = await importGeneratedCV(formData);
        const importedDocument = importRes.data;
        const editorState = extractEditorStateFromDocument(importedDocument);
        const importMsg = analysisText
          ? `Mình đã nhận diện đây là CV và import vào workspace. Mình sẽ tiếp tục dựa trên nội dung CV này. Ghi chú thêm của bạn: "${analysisText}"`
          : `Mình đã nhận diện đây là CV và import vào workspace. Bạn muốn mình giúp gì tiếp theo? (ví dụ: dán JD để chấm điểm, hoặc yêu cầu chỉnh sửa.)`;
        const finalMsgs = [...baseMsgs, { role: 'assistant', content: importMsg }];
        setCvDocument(importedDocument);
        setStaticTemplateTitle('');
        setEditorInstanceKey(`doc:${importedDocument.id}`);
        setEditableContent(editorState.value);
        setEditableContentFormat(editorState.valueFormat);
        setEditableMarkdown(editorState.markdown);
        setDocumentDirty(false);
        setOutputFormat(inferOutputFormatFromDocument(importedDocument, outputFormat));
        setMessages(finalMsgs);
        await persistChatMessages(finalMsgs);
        notifyGeneratedCvHistoryChanged();
        if (importedDocument.id && importedDocument.id !== id) {
          navigate(`/workspace/${importedDocument.id}`, { replace: true, state: { keepMessages: true } });
        }
      } catch (err) {
        console.error('Failed to import classified CV into workspace:', err);
        const detail = err.response?.data?.detail || 'Không thể import CV vào workspace. Vui lòng thử lại.';
        const finalMsgs = [...baseMsgs, { role: 'assistant', content: detail }];
        setMessages(finalMsgs);
        await persistChatMessages(finalMsgs);
      } finally {
        setLoading(false);
        setChatStatus(null);
        setAttachedCvFile(null);
        setAttachedJdText('');
        setInputValue('');
      }
      return;
    }

    // CV + substantive JD text → run the original analyze pipeline.
    const newMsgs = baseMsgs;
    setChatStatus(null);
    setAnalysisMode(true);
    setAnalysisSteps({});
    setAnalysisResults(null);
    let finalMessagesToPersist = null;

    try {
      await streamChatAnalysis(attachedCvFile, analysisText, null, (val) => {
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
              content: `Phân tích CV hoàn tất. [Xem chi tiết](/analysis/${analysisId})`,
              analysisId,
            },
          ];
          setMessages(finalMsgs);
          finalMessagesToPersist = finalMsgs;
        } else if (event === 'analysis_error') {
          finalMessagesToPersist = [
            ...newMsgs,
            { role: 'assistant', content: `Phân tích thất bại: ${data.error}` },
          ];
          setMessages(finalMessagesToPersist);
        }
      });
      if (finalMessagesToPersist) {
        await persistChatMessages(finalMessagesToPersist);
      }
    } catch (e) {
      console.error('Analysis failed:', e);
      finalMessagesToPersist = [
        ...newMsgs,
        { role: 'assistant', content: 'Xin lỗi, đã có lỗi kết nối xảy ra. Vui lòng thử lại.' },
      ];
      setMessages(finalMessagesToPersist);
      await persistChatMessages(finalMessagesToPersist);
    } finally {
      setLoading(false);
      setAnalysisMode(false);
      setAttachedCvFile(null);
      setAttachedJdText('');
      setInputValue('');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // In attachment mode, the composer text is used as JD/context for analysis.
    if (
      showAttachPanel &&
      (
        (cvDocument && (attachedCvFile || inputValue.trim())) ||
        (!cvDocument && attachedCvFile)
      )
    ) {
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
  const importedSourceType = cvDocument?.base_profile_data?.source_type || null;
  // Raw imported CV = parsed straight from the user's PDF/DOCX, no AI cleanup
  // has run on it yet. We expose the "AI sắp xếp lại" button only in this
  // state, and label it "Bản trích nháp" so the user knows the structure may
  // be lossy.
  const isRawImportedDraft = importedSourceType === 'uploaded_cv';
  const isNormalizedImport = importedSourceType === 'uploaded_cv_normalized';
  const isImportedDocument = isRawImportedDraft
    || isNormalizedImport
    || cvDocument?.generated_content?.import_preview_format === 'html';
  const isStaticTemplate = Boolean(!cvDocument && templateId && editableContent);
  const documentTitle = cvDocument
    ? cvDocument.base_profile_data?.job_title
      || (isRawImportedDraft
        ? 'Bản trích nháp'
        : isNormalizedImport
          ? 'CV đã import (đã chuẩn hoá)'
          : isImportedDocument
            ? 'CV đã import'
            : 'CV đã tạo')
    : isStaticTemplate
      ? staticTemplateTitle || 'Mẫu CV có sẵn'
      : 'Workspace CV';
  const documentSubtitle = cvDocument
    ? isRawImportedDraft
      ? 'Đây là bản trích thô từ file PDF/DOCX, có thể chưa chuẩn cấu trúc. Bấm "AI sắp xếp lại" để bố cục gọn hơn (không thêm/bớt nội dung).'
      : isNormalizedImport
        ? 'AI đã sắp xếp lại bố cục. Nội dung gốc được giữ nguyên — bạn có thể chỉnh sửa tiếp như bình thường.'
        : isImportedDocument
          ? 'Nội dung đã được chuyển thành bản chỉnh sửa trực tiếp từ file PDF/DOCX.'
          : 'Chỉnh sửa nội dung và lưu mỗi lần thành một version mới.'
    : isStaticTemplate
      ? 'Mẫu CV có sẵn đã được mở trực tiếp. Chỉnh nội dung trong editor hoặc chat tiếp nếu cần biến đổi bằng AI.'
      : 'Tài liệu sẽ xuất hiện tại đây sau khi bạn tạo hoặc import CV.';
  const showChatStarter = !messages.length && !streamAiReply && !loading && !analysisMode && !analysisResults;

  const startWorkspaceResize = (event) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    const container = workspaceRef.current;
    if (!container) return;

    event.preventDefault();
    resizeCleanupRef.current?.();

    const bounds = container.getBoundingClientRect();
    const minChat = Math.min(420, Math.max(320, bounds.width * 0.35));
    const minPreview = Math.min(520, Math.max(360, bounds.width * 0.32));

    const handleMove = (moveEvent) => {
      const nextWidth = moveEvent.clientX - bounds.left;
      const clampedWidth = Math.min(
        Math.max(nextWidth, minChat),
        Math.max(minChat, bounds.width - minPreview)
      );
      setChatPaneWidth(Math.round(clampedWidth));
    };

    const stopResize = () => {
      document.body.classList.remove('workspace-resizing');
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', stopResize);
      window.removeEventListener('pointercancel', stopResize);
      resizeCleanupRef.current = null;
    };

    document.body.classList.add('workspace-resizing');
    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', stopResize);
    window.addEventListener('pointercancel', stopResize);
    resizeCleanupRef.current = stopResize;
  };

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
          previewContent: editorState.value,
          previewFormat: editorState.valueFormat,
          previewMarkdown: editorState.markdown,
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

    const exportFormat = 'docx';
    const fallbackExt = 'docx';

    setExporting(true);
    try {
      const currentMarkdown = String(editableMarkdown || '').trim();
      if (!currentMarkdown) {
        setSaveMessage('CV chưa có nội dung để tải DOCX.');
        return;
      }

      const shouldSaveBeforeExport = Boolean(cvDocument?.id && hasUnsavedEdits);
      let activeDocument = cvDocument;
      if (shouldSaveBeforeExport) {
        const savedDocument = await handleSaveEdits();
        if (!savedDocument) return;
        activeDocument = savedDocument;
      }

      const response = activeDocument?.id
        ? await downloadGeneratedCV(activeDocument.id, exportFormat)
        : await exportPreviewDocx(
            currentMarkdown,
            cvDocument?.base_profile_data?.job_title || staticTemplateTitle || conversationTitle
          );
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

  const handleAnalyzeCurrentCv = async () => {
    if (!cvDocument?.id || analyzingCurrentCv) return;

    setShowAttachPanel(true);
    setAttachedCvFile(null);
    setAttachedJdText('');
    setInputValue('');
    setSaveMessage('Dán JD hoặc đính kèm tài liệu trong khung chat. Hệ thống sẽ kiểm tra file là CV hay job trước khi phân tích.');
    window.requestAnimationFrame(() => chatInputRef.current?.focus());
  };

  const handleNormalizeImport = async () => {
    if (!cvDocument?.id || normalizingImport) return;
    if (hasUnsavedEdits) {
      setSaveMessage('Bạn đang có chỉnh sửa chưa lưu. Lưu phiên bản mới trước khi chạy AI sắp xếp.');
      return;
    }

    setNormalizingImport(true);
    setSaveMessage('AI đang sắp xếp lại bố cục (không thay đổi nội dung)...');
    try {
      const res = await normalizeImportedCV(cvDocument.id);
      const data = res.data || {};
      if (!data.normalize_changed) {
        const warnings = Array.isArray(data.normalize_warnings) ? data.normalize_warnings : [];
        const reasonMap = {
          ai_provider_failed: 'AI provider lỗi',
          ai_returned_empty: 'AI không trả về nội dung',
          cv_too_short: 'Kết quả quá ngắn',
          content_loss_detected: 'AI làm mất nội dung, đã giữ bản gốc',
          input_empty: 'CV rỗng',
        };
        const detail = warnings.map((w) => reasonMap[w] || w).join('; ') || 'không có thay đổi';
        setSaveMessage(`Chưa sắp xếp lại được: ${detail}.`);
        return;
      }

      const normalizedDocument = data;
      const editorState = extractEditorStateFromDocument(normalizedDocument);
      setCvDocument(normalizedDocument);
      setEditorInstanceKey(`doc:${normalizedDocument.id}`);
      setEditableContent(editorState.value);
      setEditableContentFormat(editorState.valueFormat);
      setEditableMarkdown(editorState.markdown);
      setDocumentDirty(false);
      setOutputFormat(inferOutputFormatFromDocument(normalizedDocument, documentFormat));
      setSaveMessage(`AI đã chuẩn hoá bố cục → lưu thành v${normalizedDocument.version}.`);
      notifyGeneratedCvHistoryChanged();
      if (normalizedDocument.id && normalizedDocument.id !== id) {
        navigate(`/workspace/${normalizedDocument.id}`, { replace: true, state: { keepMessages: true } });
      }
    } catch (err) {
      console.error('Failed to normalize imported CV:', err);
      const detail = err.response?.data?.detail || 'Không thể chuẩn hoá CV. Vui lòng thử lại.';
      setSaveMessage(detail);
    } finally {
      setNormalizingImport(false);
    }
  };

  const isAttachMode = showAttachPanel;
  const canSubmitComposer = loading
    ? false
    : isAttachMode
      ? cvDocument
        ? Boolean(attachedCvFile || inputValue.trim())
        : Boolean(attachedCvFile)
      : Boolean(inputValue.trim());
  const composerPlaceholder = isAttachMode
    ? cvDocument
      ? 'Dán JD hoặc đính kèm tài liệu...'
      : 'Đính kèm CV (dán JD nếu muốn chấm điểm)...'
    : 'Nhập yêu cầu hoặc đính kèm tài liệu...';
  const composerMeta = isAttachMode
    ? cvDocument
      ? 'Hệ thống sẽ kiểm tra tài liệu đính kèm là CV hay job trước khi phân tích.'
      : 'Đính kèm CV để mở vào workspace, hoặc kèm JD đủ dài để chấm điểm ngay.'
    : 'Enter để gửi. Shift + Enter để xuống dòng.';
  const attachButtonTitle = cvDocument
    ? 'Đính kèm tài liệu'
    : 'Đính kèm file CV';
  const conversationTitleFallback = cvDocument?.base_profile_data?.source_type === 'uploaded_cv' && cvDocument?.base_profile_data?.source_filename
    ? `CV tải lên: ${cvDocument.base_profile_data.source_filename}`
    : cvDocument?.base_profile_data?.job_title || staticTemplateTitle;
  const conversationTitle = buildConversationTitle(
    messages,
    conversationTitleFallback
  );

  return (
    <div
      ref={workspaceRef}
      className="workspace-container fade-in"
      style={chatPaneWidth ? {
        '--workspace-chat-basis': `${chatPaneWidth}px`,
        '--workspace-chat-max': `${chatPaneWidth}px`,
      } : undefined}
    >
      {/* Left Pane: Chat Interaction */}
      <div className="workspace-chat-pane">
        <div className="chat-header">
          <h2 className="chat-conversation-title" title={conversationTitle}>
            {conversationTitle}
          </h2>
        </div>
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
                  : 'Nhập yêu cầu để tạo CV mới, hoặc dùng nút đính kèm để gửi tài liệu ứng tuyển.'}
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
              <div className="tool-icon">
                <span className="material-symbols-outlined">description</span>
              </div>
              <div className="tool-text">
                <span className="tool-name">Công cụ | Đang tạo CV Markdown</span>
                <span className="tool-status">Đang soạn thảo tài liệu...</span>
              </div>
            </div>
          )}
          {/* Analysis pipeline progress */}
          {analysisMode && Object.keys(analysisSteps).length > 0 && (
            <div className="chat-bubble-wrapper assistant">
              <div className="chat-bubble analysis-progress-bubble">
                <div className="analysis-steps-header">Đang phân tích CV...</div>
                <div className="analysis-steps-list">
                  {['extract', 'score', 'rewrite', 'truthcheck', 'insights', 'diff'].map((key) => {
                    const step = analysisSteps[key];
                    if (!step) return null;
                    const isDone = step.status === 'done';
                    const isRunning = step.status === 'running';
                    return (
                      <div key={key} className={`analysis-step-item ${isDone ? 'done' : ''} ${isRunning ? 'running' : ''}`}>
                        <span className="analysis-step-icon">
                          <span className="material-symbols-outlined">
                            {isDone ? 'check_circle' : isRunning ? 'progress_activity' : 'radio_button_unchecked'}
                          </span>
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
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-area floating-input" onSubmit={handleSubmit}>
          <div className="workspace-composer">
            {attachedCvFile && (
              <div className="composer-file-chip">
                <span className="material-symbols-outlined">description</span>
                <span className="composer-file-name">{attachedCvFile.name}</span>
                <small>{(attachedCvFile.size / 1024).toFixed(0)} KB</small>
                <button
                  type="button"
                  className="composer-file-remove"
                  onClick={() => {
                    setAttachedCvFile(null);
                    if (cvFileRef.current) cvFileRef.current.value = '';
                  }}
                  aria-label="Bỏ tài liệu đính kèm"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
            )}
            <div className={`chat-input-wrapper ${isAttachMode ? 'attach-mode' : ''}`} onClick={() => chatInputRef.current?.focus()}>
              <input
                ref={cvFileRef}
                type="file"
                accept={cvDocument ? '.pdf,.docx,.txt,.md' : '.pdf,.docx'}
                onChange={(e) => {
                  setAttachedCvFile(e.target.files[0] || null);
                  setShowAttachPanel(true);
                  window.requestAnimationFrame(() => chatInputRef.current?.focus());
                }}
                hidden
              />
              <button
                type="button"
                className={`composer-attach-btn ${isAttachMode ? 'active' : ''}`}
                onClick={(event) => {
                  event.stopPropagation();
                  setShowAttachPanel(true);
                  cvFileRef.current?.click();
                }}
                disabled={loading}
                title={attachButtonTitle}
                aria-label={attachButtonTitle}
              >
                <span className="material-symbols-outlined">attach_file</span>
              </button>
              <textarea
                ref={chatInputRef}
                className="chat-input"
                rows={1}
                placeholder={composerPlaceholder}
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
              {isAttachMode && !attachedCvFile && (
                <button
                  type="button"
                  className="composer-attach-clear"
                  onClick={(event) => {
                    event.stopPropagation();
                    setShowAttachPanel(false);
                    setAttachedCvFile(null);
                    setAttachedJdText('');
                    setInputValue('');
                  }}
                  aria-label="Thoát chế độ đính kèm"
                  title="Thoát chế độ đính kèm"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              )}
              <button type="submit" className={`chat-submit-btn ${canSubmitComposer ? 'active' : ''}`} disabled={!canSubmitComposer}>
                <PaperAirplaneIcon className="submit-icon" />
              </button>
            </div>
            <span className="workspace-composer-meta">{composerMeta}</span>
          </div>
        </form>
      </div>

      <div
        className="workspace-resizer"
        role="separator"
        aria-orientation="vertical"
        aria-label="Kéo để thay đổi kích thước chat và preview"
        onPointerDown={startWorkspaceResize}
      />

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
                <span className="doc-format-chip">DOCX</span>
                {cvDocument?.version ? (
                  <span className="doc-version-chip">{`v${cvDocument.version}`}</span>
                ) : null}
                {hasUnsavedEdits ? <span className="doc-dirty-chip">Chưa lưu</span> : null}
              </div>
            )}
          </div>
          {(cvDocument || editableContent) && (
            <div className="doc-actions">
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
              {cvDocument && isRawImportedDraft && (
                <button
                  type="button"
                  className="btn-ghost doc-action-btn"
                  onClick={handleNormalizeImport}
                  disabled={normalizingImport || hasUnsavedEdits}
                  title={hasUnsavedEdits
                    ? 'Lưu các chỉnh sửa hiện tại trước khi chạy AI sắp xếp'
                    : 'AI sẽ tái cấu trúc bố cục mà KHÔNG thêm/bớt/sửa nội dung gốc'}
                >
                  {normalizingImport ? 'AI đang sắp xếp...' : 'AI sắp xếp lại'}
                </button>
              )}
              {cvDocument && (
                <button
                  type="button"
                  className="btn-ghost doc-action-btn"
                  onClick={handleAnalyzeCurrentCv}
                  disabled={analyzingCurrentCv}
                >
                  {analyzingCurrentCv ? 'Đang tạo phân tích...' : 'Phân tích CV này'}
                </button>
              )}
              <button
                type="button"
                className="btn-primary doc-download-btn"
                onClick={handleExport}
                disabled={exporting || !editableMarkdown.trim()}
                title={editableMarkdown.trim() ? 'Tải xuống DOCX của nội dung hiện tại' : 'CV chưa có nội dung để tải DOCX'}
              >
                {exporting ? 'Đang tải...' : 'Tải DOCX'}
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
