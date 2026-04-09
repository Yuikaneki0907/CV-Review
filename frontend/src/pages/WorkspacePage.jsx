import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { exportGeneratedCV, getGeneratedCV, updateGeneratedCV, streamChatCVGeneration } from '../api';
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
  runWorkspaceChatInBackground,
  WORKSPACE_CHAT_JOB_EVENT,
} from '../utils/workspaceChatJobs';

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
        const initialMsgs = [{ role: 'user', content: initialPrompt }];
        setMessages(initialMsgs);
        setInputValue('');
        setCvDocument(null);
        setEditableContent('');
        setOutputFormat('rich_text');
        setLoading(true);

        // Send to backend
        handleChatTurn(initialMsgs, 'rich_text');
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

  useEffect(() => {
    if (!cvDocument) {
      setEditableContent('');
      setSaveMessage('');
      return;
    }
    setEditableContent(extractContentFromDocument(cvDocument));
    setSaveMessage('');
  }, [cvDocument?.id, cvDocument?.generated_content?.content, cvDocument?.generated_content?.markdown, cvDocument?.generated_content?.text]);

  const [streamAiReply, setStreamAiReply] = useState('');
  const [streamCvText, setStreamCvText] = useState('');
  const [isBotThinking, setIsBotThinking] = useState(false);

  const handleChatTurn = async (currentMessages, formatOverride = outputFormat) => {
    if (!user?.id) return;
    setLoading(true);
    setStreamAiReply('');
    setStreamCvText('');
    setIsBotThinking(true);

    try {
      let finalReply = '';
      let idcv = null;
      let finalcvtext = '';

      await streamChatCVGeneration(currentMessages, normalizeOutputFormat(formatOverride), (val) => {
        setIsBotThinking(false);
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
      });

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
        setIsBotThinking(false);
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
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
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-area floating-input" onSubmit={handleSubmit}>
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
          <div className="chat-input-wrapper">
            <textarea
              className="chat-input"
              rows={1}
              placeholder="Nhập yêu cầu của bạn (VD: thêm JD, đổi title...)"
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
          {cvDocument ? (
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
