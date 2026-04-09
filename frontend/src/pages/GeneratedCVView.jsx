import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getGeneratedCV } from '../api';

export default function GeneratedCVView() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await getGeneratedCV(id);
        setData(res.data);
      } catch (err) {
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleCopy = () => {
    if (data?.generated_content?.markdown) {
      navigator.clipboard.writeText(data.generated_content.markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="analysis-page">
        <div className="loading-state">
          <div className="pulse-ring" />
          <p>Đang tải CV...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="analysis-page">
        <div className="error-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="var(--outline)">
            <path d="M11 15h2v2h-2v-2zm0-8h2v6h-2V7zm1-5C6.47 2 2 6.5 2 12a10 10 0 0020 0c0-5.5-4.47-10-10-10zm0 18a8 8 0 110-16 8 8 0 010 16z" />
          </svg>
          <p>Không tìm thấy CV mẫu này</p>
          <Link to="/history" className="btn-secondary">
            ← Quay lại
          </Link>
        </div>
      </div>
    );
  }

  const markdownText = data.generated_content?.markdown || "Không có dữ liệu CV.";

  return (
    <div className="analysis-page">
      <div className="analysis-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Link to="/generated-cv-history" className="back-link">
            ← Danh sách CV AI
          </Link>
          <h2>CV Mẫu: {data.base_profile_data?.job_title || 'CV Unnamed'}</h2>
          <span className="status-badge status-done">{data.base_profile_data?.level || 'N/A'}</span>
        </div>
        <button className="btn-primary" onClick={handleCopy}>
          {copied ? 'Đã sao chép!' : 'Copy Markdown'}
        </button>
      </div>

      <div className="markdown-cv-container" style={{
        marginTop: '2rem',
        padding: '2.5rem',
        background: 'var(--surface)',
        borderRadius: '8px',
        border: '1px solid var(--outline)',
        lineHeight: 1.6
      }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {markdownText}
        </ReactMarkdown>
      </div>
    </div>
  );
}
