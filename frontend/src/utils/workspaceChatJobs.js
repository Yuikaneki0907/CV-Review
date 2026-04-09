import { chatCVGeneration } from '../api';
import {
  clearWorkspaceDraft,
  saveWorkspaceDraft,
} from './workspaceDraft';

export const WORKSPACE_CHAT_JOB_EVENT = 'workspace-chat-job-updated';

const activeJobs = new Map();

const emitJobEvent = (detail) => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(WORKSPACE_CHAT_JOB_EVENT, { detail }));
};

const buildJobKey = (userId, scope) => `${userId}:${scope}`;

export const runWorkspaceChatInBackground = async ({
  userId,
  scope,
  messages,
  title = '',
  outputFormat = 'rich_text',
}) => {
  if (!userId || !scope) {
    throw new Error('Missing userId/scope when running background chat job');
  }

  const key = buildJobKey(userId, scope);
  if (activeJobs.has(key)) {
    return activeJobs.get(key);
  }

  const normalizedMessages = Array.isArray(messages) ? messages : [];
  saveWorkspaceDraft({
    userId,
    scope,
    messages: normalizedMessages,
    inputValue: '',
    title,
    pending: true,
    outputFormat,
  });
  emitJobEvent({ userId, scope, status: 'running' });

  const jobPromise = chatCVGeneration(normalizedMessages, outputFormat)
    .then((res) => {
      const reply = res?.data?.reply || 'Mình đã xử lý xong yêu cầu.';
      const generatedCvId = res?.data?.generated_cv_id || null;
      const finalMessages = [...normalizedMessages, { role: 'assistant', content: reply }];

      saveWorkspaceDraft({
        userId,
        scope,
        messages: finalMessages,
        inputValue: '',
        title,
        pending: false,
        generatedCvId,
        outputFormat,
      });

      // Mirror to ID scope so user can reopen by /workspace/:id immediately.
      if (generatedCvId) {
        saveWorkspaceDraft({
          userId,
          scope: `id:${generatedCvId}`,
          messages: finalMessages,
          inputValue: '',
          title,
          pending: false,
          generatedCvId,
          outputFormat,
        });
      }

      emitJobEvent({
        userId,
        scope,
        status: 'done',
        generatedCvId,
      });

      return {
        reply,
        generatedCvId,
        finalMessages,
      };
    })
    .catch((error) => {
      const errText = 'Xin lỗi, đã có lỗi xảy ra trong quá trình xử lý. Bạn vui lòng thử lại nhé.';
      const finalMessages = [...normalizedMessages, { role: 'assistant', content: errText }];

      saveWorkspaceDraft({
        userId,
        scope,
        messages: finalMessages,
        inputValue: '',
        title,
        pending: false,
        outputFormat,
      });

      emitJobEvent({
        userId,
        scope,
        status: 'failed',
      });

      return {
        reply: errText,
        generatedCvId: null,
        finalMessages,
        error,
      };
    })
    .finally(() => {
      activeJobs.delete(key);
    });

  activeJobs.set(key, jobPromise);
  return jobPromise;
};

export const clearWorkspaceNewDraft = (userId) => {
  if (!userId) return;
  clearWorkspaceDraft(userId, 'new');
};
