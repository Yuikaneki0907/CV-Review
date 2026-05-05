const DEFAULT_MAX_SIZE_MB = 5;
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx']);

const getExtension = (filename = '') => {
  const normalized = String(filename).trim().toLowerCase();
  const idx = normalized.lastIndexOf('.');
  if (idx < 0) return '';
  return normalized.slice(idx + 1);
};

export const validateCvUploadFile = (file, maxSizeMb = DEFAULT_MAX_SIZE_MB) => {
  if (!file) {
    return { valid: false, message: 'Vui lòng chọn tệp CV để tải lên.' };
  }

  const ext = getExtension(file.name);
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return { valid: false, message: 'Chỉ hỗ trợ tệp CV định dạng .pdf hoặc .docx.' };
  }

  const maxBytes = maxSizeMb * 1024 * 1024;
  if (file.size > maxBytes) {
    return { valid: false, message: `Tệp vượt quá giới hạn ${maxSizeMb}MB.` };
  }

  return { valid: true, message: '' };
};

export const CV_UPLOAD_MAX_SIZE_MB = DEFAULT_MAX_SIZE_MB;
