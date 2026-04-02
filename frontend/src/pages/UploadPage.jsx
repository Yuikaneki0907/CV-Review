import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createAnalysis } from '../api';

export default function UploadPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith('.pdf') || dropped.name.endsWith('.docx'))) {
      setFile(dropped);
    } else {
      setError('Chỉ hỗ trợ file PDF hoặc DOCX');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !jdText.trim()) return;
    setError('');
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('cv_file', file);
      fd.append('jd_text', jdText);
      const res = await createAnalysis(fd);
      navigate(`/analysis/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Có lỗi xảy ra');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-header">
        <h2>Phân tích CV</h2>
        <p>Upload CV và nhập Job Description để bắt đầu</p>
      </div>

      <form onSubmit={handleSubmit} className="upload-form">
        {error && <div className="error-msg">{error}</div>}

        <div className="upload-grid">
          {/* CV Upload */}
          <div className="upload-section">
            <h3>📄 CV / Resume</h3>
            <div
              className={`drop-zone ${dragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files[0])}
                hidden
              />
              {file ? (
                <div className="file-preview">
                  <span className="file-icon">✅</span>
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">({(file.size / 1024).toFixed(0)} KB)</span>
                </div>
              ) : (
                <div className="drop-prompt">
                  <span className="drop-icon">📁</span>
                  <p>Kéo thả file hoặc click để chọn</p>
                  <p className="hint">PDF, DOCX</p>
                </div>
              )}
            </div>
          </div>

          {/* JD Input */}
          <div className="upload-section">
            <h3>💼 Job Description</h3>
            <textarea
              className="jd-input"
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Dán nội dung Job Description tại đây...&#10;&#10;Ví dụ:&#10;- Yêu cầu: 3 năm kinh nghiệm Python&#10;- Kỹ năng: FastAPI, Docker, PostgreSQL..."
              rows={12}
              required
            />
          </div>
        </div>

        <button
          type="submit"
          className="btn-primary btn-lg"
          disabled={!file || !jdText.trim() || loading}
        >
          {loading ? (
            <>
              <span className="spinner" /> Đang phân tích...
            </>
          ) : (
            '🔍 Bắt đầu phân tích'
          )}
        </button>
      </form>
    </div>
  );
}
