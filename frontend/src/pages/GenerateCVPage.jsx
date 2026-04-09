import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SparklesIcon, DocumentTextIcon, UserGroupIcon, CodeBracketIcon } from '@heroicons/react/24/outline';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';

export default function GenerateCVPage() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    
    // Pass the initial prompt to the workspace where the chat lives
    navigate('/workspace', { state: { initialPrompt: prompt } });
  };

  const handleSuggestionClick = (text) => {
    navigate('/workspace', { state: { initialPrompt: text } });
  };

  return (
    <div className="prompter-page fade-in">
      <div className="prompter-container">
        <div className="prompter-header">
          <div className="ai-badge">
            <SparklesIcon className="badge-icon" />
            <span>AI Resume Builder</span>
          </div>
          <h1 className="prompter-title">Khởi tạo CV Chuyên Nghiệp</h1>
          <p className="prompter-subtitle">Nói cho AI biết bạn muốn tạo CV cho vị trí nào. Chúng tôi sẽ hỏi thêm chi tiết nếu cần thiết.</p>
        </div>

        <form className="prompter-form" onSubmit={handleSubmit}>
          <div className="prompter-input-wrapper">
            <input
              type="text"
              className="prompter-input"
              placeholder="VD: Tạo cho tôi một CV Frontend Developer..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              autoFocus
            />
            <button 
              type="submit" 
              className={`prompter-submit-btn ${prompt.trim() ? 'active' : ''}`}
              disabled={!prompt.trim()}
            >
              <PaperAirplaneIcon className="submit-icon" />
            </button>
          </div>
        </form>

        <div className="prompter-suggestions">
          <p className="suggestions-label">Start with an example:</p>
          <div className="suggestions-grid">
            <button onClick={() => handleSuggestionClick("Tôi muốn tạo CV Frontend Developer (ReactJS)")} className="suggestion-card">
              <CodeBracketIcon className="suggestion-icon text-blue" />
              <span>Frontend Developer (ReactJS)</span>
            </button>
            <button onClick={() => handleSuggestionClick("Tạo CV chuyên nghiệp cho vị trí Data Analyst")} className="suggestion-card">
              <DocumentTextIcon className="suggestion-icon text-green" />
              <span>Data Analyst (Python, SQL)</span>
            </button>
            <button onClick={() => handleSuggestionClick("Viết cho tôi CV Product Manager")} className="suggestion-card">
              <UserGroupIcon className="suggestion-icon text-purple" />
              <span>Product Manager</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
