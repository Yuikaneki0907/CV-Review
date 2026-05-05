import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowUpTrayIcon,
  PencilSquareIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import {
  createChatSession,
  deleteGeneratedCV,
  importGeneratedCV,
  listGeneratedCVs,
} from '../api';
import { notifyGeneratedCvHistoryChanged } from '../utils/generatedCvHistory';
import { CV_UPLOAD_MAX_SIZE_MB, validateCvUploadFile } from '../utils/cvUploadValidation';

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
  item.chat_title || item.job_title || item.source_filename || 'CV chưa đặt tên';

const getPreviewMarkdown = (item) =>
  String(
    item?.preview_markdown ||
      item?.generated_content?.markdown ||
      item?.generated_content?.content ||
      ''
  ).trim();

const getPreviewHtml = (item) =>
  String(item?.preview_html || item?.generated_content?.html || '').trim();

export default function CVManagementPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [cvs, setCvs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [creatingChatSession, setCreatingChatSession] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDeleteItem, setConfirmDeleteItem] = useState(null);
  const [previewItem, setPreviewItem] = useState(null);
  const [error, setError] = useState('');
  const [uploadNotice, setUploadNotice] = useState(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadModalError, setUploadModalError] = useState('');
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const loadCVs = async () => {
    setError('');
    try {
      const res = await listGeneratedCVs(200, 0);
      setCvs(Array.isArray(res?.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load CV management list:', err);
      setError('Không thể tải danh sách CV. Vui lòng thử lại.');
    }
  };

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      setLoading(true);
      try {
        const res = await listGeneratedCVs(200, 0);
        if (!mounted) return;
        setCvs(Array.isArray(res?.data) ? res.data : []);
      } catch (err) {
        console.error('Failed to initialize CV management page:', err);
        if (mounted) setError('Không thể tải danh sách CV. Vui lòng thử lại.');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    init();
    return () => {
      mounted = false;
    };
  }, []);

  const grouped = useMemo(() => {
    const uploaded = [];
    const systemGenerated = [];

    cvs.forEach((item) => {
      if (item?.source_type === 'uploaded_cv') {
        uploaded.push(item);
      } else {
        systemGenerated.push(item);
      }
    });

    return { uploaded, systemGenerated };
  }, [cvs]);

  const handleSelectUploadFile = (file) => {
    if (!file) return;
    const validation = validateCvUploadFile(file, CV_UPLOAD_MAX_SIZE_MB);
    if (!validation.valid) {
      setUploadModalError(validation.message);
      setSelectedUploadFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    setUploadModalError('');
    setSelectedUploadFile(file);
  };

  const handleUpload = async () => {
    if (!selectedUploadFile || uploading) return false;

    setUploading(true);
    setError('');
    setUploadModalError('');
    setUploadNotice(null);
    try {
      const formData = new FormData();
      formData.append('cv_file', selectedUploadFile);
      await importGeneratedCV(formData);
      await loadCVs();
      notifyGeneratedCvHistoryChanged();
      setUploadNotice({
        type: 'success',
        message: 'Tải CV lên thành công. Bạn có thể xem trước hoặc xóa CV đã tải lên.',
      });
      return true;
    } catch (err) {
      console.error('Failed to upload/import CV:', err);
      setUploadNotice({
        type: 'error',
        message: err.response?.data?.detail || 'Không thể tải lên CV. Vui lòng thử lại.',
      });
      setUploadModalError(err.response?.data?.detail || 'Không thể tải lên CV. Vui lòng thử lại.');
      return false;
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDrag = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.type === 'dragenter' || event.type === 'dragover') {
      setDragActive(true);
    } else if (event.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    const droppedFile = event.dataTransfer?.files?.[0] || null;
    handleSelectUploadFile(droppedFile);
  };

  const openUploadModal = () => {
    setUploadModalOpen(true);
    setUploadModalError('');
    setSelectedUploadFile(null);
    setDragActive(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const closeUploadModal = () => {
    if (uploading) return;
    setUploadModalOpen(false);
    setUploadModalError('');
    setSelectedUploadFile(null);
    setDragActive(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleConfirmUploadModal = async () => {
    const success = await handleUpload();
    if (success) {
      setUploadModalOpen(false);
      setSelectedUploadFile(null);
      setDragActive(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirmDeleteItem || deletingId) return;

    const targetId = confirmDeleteItem.id;
    setDeletingId(targetId);
    setError('');

    try {
      await deleteGeneratedCV(targetId);
      setConfirmDeleteItem(null);
      await loadCVs();
      notifyGeneratedCvHistoryChanged();
    } catch (err) {
      console.error('Failed to delete CV:', err);
      setError(err.response?.data?.detail || 'Không thể xóa CV. Vui lòng thử lại.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleCreateNewCvSession = async () => {
    if (creatingChatSession) return;
    setCreatingChatSession(true);
    setError('');
    setUploadNotice(null);
    try {
      const res = await createChatSession();
      const conversationId = res?.data?.conversation_id;
      if (!conversationId) {
        throw new Error('Missing conversation_id');
      }
      navigate(`/workspace?conversation=${conversationId}`);
    } catch (err) {
      console.error('Failed to create new chat session from CV management:', err);
      setError(err.response?.data?.detail || 'Không thể tạo phiên chat mới. Vui lòng thử lại.');
    } finally {
      setCreatingChatSession(false);
    }
  };

  return (
    <div className="cv-management-page">
      <div className="cv-management-hero">
        <div>
          <span className="cv-management-eyebrow">Workspace</span>
          <h1>Quản lí CV</h1>
          <p>Quản lí nhanh CV được tạo bởi hệ thống và CV bạn tải lên để tiếp tục chỉnh sửa bằng AI.</p>
        </div>
        <div className="cv-management-header-actions">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            hidden
            onChange={(e) => handleSelectUploadFile(e.target.files?.[0])}
          />
          <button
            type="button"
            className="cv-management-btn cv-management-btn-upload"
            onClick={openUploadModal}
            disabled={uploading}
          >
            <ArrowUpTrayIcon className="cv-management-btn-icon" />
            {uploading ? 'Đang tải lên...' : 'Tải lên CV'}
          </button>
          <button
            type="button"
            className="cv-management-btn cv-management-btn-create"
            onClick={handleCreateNewCvSession}
            disabled={creatingChatSession}
          >
            <PlusIcon className="cv-management-btn-icon" />
            {creatingChatSession ? 'Đang tạo...' : 'Tạo CV mới'}
          </button>
        </div>
      </div>

      {error && <div className="cv-management-error">{error}</div>}
      {uploadNotice && (
        <div className={`cv-management-upload-notice ${uploadNotice.type === 'success' ? 'success' : 'error'}`}>
          {uploadNotice.message}
        </div>
      )}

      {loading ? (
        <div className="cv-management-loading">Đang tải danh sách CV...</div>
      ) : (
        <div className="cv-management-sections">
          <section className="cv-management-section">
            <h2>CV tạo từ hệ thống</h2>
            {grouped.systemGenerated.length === 0 ? (
              <div className="cv-management-empty">Chưa có CV tạo từ hệ thống.</div>
            ) : (
              <div className="cv-management-list">
                {grouped.systemGenerated.map((item) => (
                  <div key={item.id} className="cv-management-row">
                    <div className="cv-management-row-main">
                      <h3>{getCvTitle(item)}</h3>
                      <p>
                        v{item.version} • {formatDate(item.created_at)}
                      </p>
                    </div>
                    <div className="cv-management-row-actions">
                      {item.is_editable && item.source_type !== 'uploaded_cv' && (
                        <button
                          type="button"
                          className="cv-management-action-btn edit"
                          onClick={() => navigate(`/workspace/${item.id}`)}
                        >
                          <PencilSquareIcon className="cv-management-action-icon" />
                          Chỉnh sửa
                        </button>
                      )}
                      <button
                        type="button"
                        className="cv-management-action-btn delete"
                        onClick={() => setConfirmDeleteItem(item)}
                        disabled={deletingId === item.id}
                      >
                        <TrashIcon className="cv-management-action-icon" />
                        Xóa
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="cv-management-section">
            <h2>CV tải lên</h2>
            {grouped.uploaded.length === 0 ? (
              <div className="cv-management-empty">Chưa có CV tải lên.</div>
            ) : (
              <div className="cv-management-list">
                {grouped.uploaded.map((item) => (
                  <div key={item.id} className="cv-management-row">
                    <div className="cv-management-row-main">
                      <h3>{getCvTitle(item)}</h3>
                      <p>
                        {item.source_filename ? `${item.source_filename} • ` : ''}
                        v{item.version} • {formatDate(item.created_at)}
                      </p>
                    </div>
                    <div className="cv-management-row-actions">
                      <button
                        type="button"
                        className="cv-management-action-btn preview"
                        onClick={() => setPreviewItem(item)}
                      >
                        Xem trước
                      </button>
                      <button
                        type="button"
                        className="cv-management-action-btn delete"
                        onClick={() => setConfirmDeleteItem(item)}
                        disabled={deletingId === item.id}
                      >
                        <TrashIcon className="cv-management-action-icon" />
                        Xóa
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {previewItem && (
        <div className="cv-management-modal-backdrop" role="presentation" onClick={() => setPreviewItem(null)}>
          <div className="cv-preview-modal" role="dialog" aria-modal="true" aria-labelledby="cv-preview-title" onClick={(event) => event.stopPropagation()}>
            <div className="cv-preview-modal-header">
              <div>
                <h3 id="cv-preview-title">{getCvTitle(previewItem)}</h3>
                <p>{previewItem.source_filename || 'CV tải lên'} • v{previewItem.version}</p>
              </div>
              <button type="button" className="cv-upload-close" onClick={() => setPreviewItem(null)}>×</button>
            </div>
            <div className="cv-preview-modal-body">
              {getPreviewHtml(previewItem) && previewItem.preview_format === 'html' ? (
                <div className="cv-upload-preview-html" dangerouslySetInnerHTML={{ __html: getPreviewHtml(previewItem) }} />
              ) : getPreviewMarkdown(previewItem) ? (
                <div className="cv-upload-preview-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{getPreviewMarkdown(previewItem)}</ReactMarkdown>
                </div>
              ) : (
                <div className="cv-management-empty">Chưa có nội dung preview cho CV này.</div>
              )}
            </div>
            <div className="cv-upload-modal-actions">
              <button type="button" className="cv-management-modal-btn cancel" onClick={() => setPreviewItem(null)}>Đóng</button>
            </div>
          </div>
        </div>
      )}

      {confirmDeleteItem && (
        <div className="cv-management-modal-backdrop" role="presentation">
          <div className="cv-management-modal" role="dialog" aria-modal="true" aria-labelledby="cv-delete-title">
            <h3 id="cv-delete-title">Xác nhận xóa CV</h3>
            <p>
              Bạn có chắc muốn xóa <strong>{getCvTitle(confirmDeleteItem)}</strong> không?
            </p>
            <div className="cv-management-modal-actions">
              <button
                type="button"
                className="cv-management-modal-btn cancel"
                onClick={() => setConfirmDeleteItem(null)}
                disabled={Boolean(deletingId)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="cv-management-modal-btn danger"
                onClick={handleConfirmDelete}
                disabled={Boolean(deletingId)}
              >
                {deletingId ? 'Đang xóa...' : 'Xác nhận xóa'}
              </button>
            </div>
          </div>
        </div>
      )}

      {uploadModalOpen && (
        <div className="cv-management-modal-backdrop" role="presentation">
          <div className="cv-upload-modal" role="dialog" aria-modal="true" aria-labelledby="cv-upload-title">
            <div className="cv-upload-modal-header">
              <h3 id="cv-upload-title">Tải lên CV</h3>
              <button type="button" className="cv-upload-close" onClick={closeUploadModal} disabled={uploading}>×</button>
            </div>
            <div className="cv-upload-modal-body">
              <div
                className={`cv-management-dropzone ${dragActive ? 'active' : ''} ${uploading ? 'disabled' : ''}`}
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => !uploading && fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if ((event.key === 'Enter' || event.key === ' ') && !uploading) {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
              >
                <ArrowUpTrayIcon className="cv-management-dropzone-icon" />
                <p className="cv-management-dropzone-title">
                  Kéo thả CV vào đây hoặc bấm để chọn tệp
                </p>
                <p className="cv-management-dropzone-subtitle">
                  Hỗ trợ .pdf, .docx • tối đa {CV_UPLOAD_MAX_SIZE_MB}MB
                </p>
              </div>
              {selectedUploadFile && (
                <div className="cv-upload-selected-file">
                  Đã chọn: <strong>{selectedUploadFile.name}</strong> ({(selectedUploadFile.size / 1024).toFixed(0)} KB)
                </div>
              )}
              {uploadModalError && (
                <div className="cv-management-upload-notice error">{uploadModalError}</div>
              )}
            </div>
            <div className="cv-upload-modal-actions">
              <button type="button" className="cv-management-modal-btn cancel" onClick={closeUploadModal} disabled={uploading}>Hủy</button>
              <button
                type="button"
                className="cv-management-modal-btn danger"
                onClick={handleConfirmUploadModal}
                disabled={!selectedUploadFile || uploading}
              >
                {uploading ? 'Đang tải lên...' : 'Tải lên'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
