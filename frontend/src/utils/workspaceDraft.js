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
  const hasContent =
    normalizedMessages.length > 0 ||
    normalizedInput.trim().length > 0 ||
    normalizedPending ||
    Boolean(normalizedGeneratedCvId);

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
      Boolean(draft.generatedCvId);
    if (!hasContent) continue;

    const id = scope.startsWith('id:') ? scope.slice(3) : null;
    const fallbackTitle = draft.messages
      .filter((m) => m.role === 'user')
      .slice(-1)[0]?.content?.trim();

    drafts.push({
      key,
      scope,
      id,
      updatedAt: draft.updatedAt ? new Date(draft.updatedAt).getTime() : 0,
      pending: draft.pending,
      title:
        draft.title ||
        (scope === 'new'
          ? 'Phiên chat chưa hoàn tất'
          : fallbackTitle?.slice(0, 48) || `Phiên #${id?.slice(0, 8)}`),
    });
  }

  drafts.sort((a, b) => b.updatedAt - a.updatedAt);
  return drafts;
};
