const DRAFT_PREFIX = 'cv_workspace_draft_v1';
export const WORKSPACE_DRAFT_EVENT = 'workspace-draft-updated';

const isBrowser = () => typeof window !== 'undefined' && typeof localStorage !== 'undefined';

const emitDraftEvent = () => {
  if (!isBrowser()) return;
  window.dispatchEvent(new CustomEvent(WORKSPACE_DRAFT_EVENT));
};

const buildKey = (userId, scope) => `${DRAFT_PREFIX}:${userId}:${scope}`;

export const getDraftScope = (id) => (id ? `id:${id}` : 'new');

const normalizeOutputFormat = (value) =>
  value === 'markdown' || value === 'docx' ? value : 'markdown';

const normalizeMessages = (messages) => {
  if (!Array.isArray(messages)) return [];
  return messages
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .map((m) => ({ role: m.role, content: m.content }))
    .slice(-120);
};

const buildConversationTitle = (messages, inputValue = '') => {
  const firstUserMessage = messages.find((m) => m.role === 'user' && m.content.trim());
  const rawTitle = firstUserMessage?.content || inputValue || '';
  const normalized = rawTitle
    .replace(/\s+/g, ' ')
    .replace(/^#+\s*/, '')
    .trim();
  return normalized ? normalized.slice(0, 64) : '';
};

export const loadWorkspaceDraft = (userId, scope) => {
  if (!isBrowser() || !userId || !scope) return null;
  const raw = localStorage.getItem(buildKey(userId, scope));
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    return {
      scope,
      updatedAt: parsed.updatedAt || null,
      messages: normalizeMessages(parsed.messages),
      inputValue: typeof parsed.inputValue === 'string' ? parsed.inputValue : '',
      title: typeof parsed.title === 'string' ? parsed.title : '',
      pending: Boolean(parsed.pending),
      generatedCvId: typeof parsed.generatedCvId === 'string' ? parsed.generatedCvId : null,
      outputFormat: normalizeOutputFormat(parsed.outputFormat),
      previewContent: typeof parsed.previewContent === 'string' ? parsed.previewContent : '',
      previewFormat: parsed.previewFormat === 'html' ? 'html' : 'markdown',
      previewMarkdown: typeof parsed.previewMarkdown === 'string' ? parsed.previewMarkdown : '',
    };
  } catch {
    return null;
  }
};

export const saveWorkspaceDraft = ({
  userId,
  scope,
  messages,
  inputValue = '',
  title = '',
  pending = undefined,
  generatedCvId = undefined,
  outputFormat = undefined,
  previewContent = undefined,
  previewFormat = undefined,
  previewMarkdown = undefined,
}) => {
  if (!isBrowser() || !userId || !scope) return;

  const existingDraft = loadWorkspaceDraft(userId, scope);
  const normalizedMessages = normalizeMessages(messages);
  const normalizedInput = typeof inputValue === 'string' ? inputValue : '';
  const normalizedPending = typeof pending === 'boolean' ? pending : Boolean(existingDraft?.pending);
  const normalizedGeneratedCvId =
    generatedCvId === undefined ? existingDraft?.generatedCvId || null : generatedCvId || null;
  const normalizedOutputFormat = normalizeOutputFormat(
    outputFormat === undefined ? existingDraft?.outputFormat : outputFormat
  );
  const normalizedPreviewContent =
    previewContent === undefined ? existingDraft?.previewContent || '' : String(previewContent || '');
  const normalizedPreviewFormat =
    previewFormat === undefined
      ? existingDraft?.previewFormat || 'markdown'
      : previewFormat === 'html'
        ? 'html'
        : 'markdown';
  const normalizedPreviewMarkdown =
    previewMarkdown === undefined ? existingDraft?.previewMarkdown || '' : String(previewMarkdown || '');
  const hasContent =
    normalizedMessages.length > 0 ||
    normalizedInput.trim().length > 0 ||
    normalizedPending ||
    Boolean(normalizedGeneratedCvId) ||
    normalizedPreviewContent.trim().length > 0 ||
    normalizedPreviewMarkdown.trim().length > 0;

  if (!hasContent) {
    clearWorkspaceDraft(userId, scope);
    return;
  }

  const payload = {
    updatedAt: new Date().toISOString(),
    messages: normalizedMessages,
    inputValue: normalizedInput,
    title: typeof title === 'string' ? title : '',
    pending: normalizedPending,
    generatedCvId: normalizedGeneratedCvId,
    outputFormat: normalizedOutputFormat,
    previewContent: normalizedPreviewContent,
    previewFormat: normalizedPreviewFormat,
    previewMarkdown: normalizedPreviewMarkdown,
  };

  localStorage.setItem(buildKey(userId, scope), JSON.stringify(payload));
  emitDraftEvent();
};

export const clearWorkspaceDraft = (userId, scope) => {
  if (!isBrowser() || !userId || !scope) return;
  localStorage.removeItem(buildKey(userId, scope));
  emitDraftEvent();
};

export const listWorkspaceDrafts = (userId) => {
  if (!isBrowser() || !userId) return [];
  const prefix = `${DRAFT_PREFIX}:${userId}:`;
  const drafts = [];

  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(prefix)) continue;

    const scope = key.slice(prefix.length);
    const draft = loadWorkspaceDraft(userId, scope);
    if (!draft) continue;

    const hasContent =
      draft.messages.length > 0 ||
      draft.inputValue.trim().length > 0 ||
      draft.pending ||
      Boolean(draft.generatedCvId) ||
      draft.previewContent.trim().length > 0 ||
      draft.previewMarkdown.trim().length > 0;
    if (!hasContent) continue;

    const id = scope.startsWith('id:') ? scope.slice(3) : null;
    const conversationTitle = buildConversationTitle(draft.messages, draft.inputValue);

    drafts.push({
      key,
      scope,
      id,
      updatedAt: draft.updatedAt ? new Date(draft.updatedAt).getTime() : 0,
      pending: draft.pending,
      title:
        conversationTitle ||
        draft.title ||
        `Workspace #${id?.slice(0, 8) || 'mới'}`,
    });
  }

  drafts.sort((a, b) => b.updatedAt - a.updatedAt);
  return drafts;
};
