import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createAnalysis } from '../api';

export default function UploadPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const jdFileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [jdFile, setJdFile] = useState(null);
  const [jdMode, setJdMode] = useState('text');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [jdDragActive, setJdDragActive] = useState(false);

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

  const handleJdDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setJdDragActive(true);
    else if (e.type === 'dragleave') setJdDragActive(false);
  };

  const handleJdDrop = (e) => {
    e.preventDefault();
    setJdDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith('.pdf') || dropped.name.endsWith('.docx'))) {
      setJdFile(dropped);
    } else {
      setError('JD: Chỉ hỗ trợ file PDF hoặc DOCX');
    }
  };

  const isJdReady = jdMode === 'text' ? jdText.trim() : jdFile;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !isJdReady) return;
    setError('');
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('cv_file', file);
      if (jdMode === 'file' && jdFile) {
        fd.append('jd_file', jdFile);
      } else {
        fd.append('jd_text', jdText);
      }
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
        <p>Upload CV và nhập Job Description để bắt đầu phân tích</p>
      </div>

      <form onSubmit={handleSubmit} className="upload-form">
        {error && <div className="error-msg">{error}</div>}

        <div className="upload-grid">
          {/* CV Upload */}
          <div className="upload-section">
            <h3>
              <span className="material-symbols-outlined" style={{ fontSize: '1.1rem', color: 'var(--primary)' }}>description</span>
              CV / Resume
            </h3>
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
                  <span className="material-symbols-outlined" style={{ color: 'var(--secondary)', fontSize: '1.5rem' }}>check_circle</span>
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">({(file.size / 1024).toFixed(0)} KB)</span>
                </div>
              ) : (
                <div className="drop-prompt">
                  <span className="material-symbols-outlined" style={{ fontSize: '2.5rem', color: 'var(--outline)', display: 'block', marginBottom: '0.75rem' }}>cloud_upload</span>
                  <p>Kéo thả file hoặc click để chọn</p>
                  <p className="hint">PDF, DOCX</p>
                </div>
              )}
            </div>
          </div>

          {/* JD Input */}
          <div className="upload-section">
            <h3>
              <span className="material-symbols-outlined" style={{ fontSize: '1.1rem', color: 'var(--primary)' }}>work</span>
              Job Description
            </h3>

            <div className="jd-mode-toggle">
              <button
                type="button"
                className={`jd-tab ${jdMode === 'text' ? 'active' : ''}`}
                onClick={() => setJdMode('text')}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '0.9rem', verticalAlign: 'middle', marginRight: '0.25rem' }}>edit_note</span>
                Nhập text
              </button>
              <button
                type="button"
                className={`jd-tab ${jdMode === 'file' ? 'active' : ''}`}
                onClick={() => setJdMode('file')}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '0.9rem', verticalAlign: 'middle', marginRight: '0.25rem' }}>upload_file</span>
                Upload file
              </button>
            </div>

            {jdMode === 'text' ? (
              <textarea
                className="jd-input"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder={"Dán nội dung Job Description tại đây...\n\nVí dụ:\n- Yêu cầu: 3 năm kinh nghiệm Python\n- Kỹ năng: FastAPI, Docker, PostgreSQL..."}
                rows={10}
              />
            ) : (
              <div
                className={`drop-zone ${jdDragActive ? 'active' : ''} ${jdFile ? 'has-file' : ''}`}
                onDragEnter={handleJdDrag}
                onDragOver={handleJdDrag}
                onDragLeave={handleJdDrag}
                onDrop={handleJdDrop}
                onClick={() => jdFileRef.current?.click()}
              >
                <input
                  ref={jdFileRef}
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setJdFile(e.target.files[0])}
                  hidden
                />
                {jdFile ? (
                  <div className="file-preview">
                    <span className="material-symbols-outlined" style={{ color: 'var(--secondary)', fontSize: '1.5rem' }}>check_circle</span>
                    <span className="file-name">{jdFile.name}</span>
                    <span className="file-size">({(jdFile.size / 1024).toFixed(0)} KB)</span>
                  </div>
                ) : (
                  <div className="drop-prompt">
                    <span className="material-symbols-outlined" style={{ fontSize: '2.5rem', color: 'var(--outline)', display: 'block', marginBottom: '0.75rem' }}>cloud_upload</span>
                    <p>Kéo thả file JD hoặc click để chọn</p>
                    <p className="hint">PDF, DOCX</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <button
          type="submit"
          className="btn-primary btn-lg"
          disabled={!file || !isJdReady || loading}
        >
          {loading ? (
            <>
              <span className="spinner" /> Đang phân tích...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined" style={{ fontSize: '1.2rem' }}>search</span>
              Bắt đầu phân tích
            </>
          )}
        </button>
      </form>
    </div>
  );
}
