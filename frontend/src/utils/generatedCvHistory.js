export const GENERATED_CV_HISTORY_EVENT = 'generated-cv-history-updated';

export const notifyGeneratedCvHistoryChanged = () => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(GENERATED_CV_HISTORY_EVENT));
};
