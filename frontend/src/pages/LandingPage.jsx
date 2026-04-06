import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function LandingPage() {
    const { token } = useAuth();
    if (token) return <Navigate to="/upload" replace />;

    return (
        <div className="landing-page">
            {/* Hero */}
            <section className="landing-hero">
                <div className="hero-content">
                    <div className="hero-badge">⭐ AI-Powered CV Optimization</div>
                    <h1>
                        Tối ưu CV cho<br />
                        <span className="hero-gradient-text">vị trí mơ ước</span>
                    </h1>
                    <p className="hero-subtitle">
                        AI phân tích CV, chấm điểm chi tiết, viết lại CV tối ưu, kiểm tra
                        hallucination — chỉ trong 60 giây. Đưa sự nghiệp của bạn lên tầm
                        cao mới với công nghệ trí tuệ nhân tạo.
                    </p>
                    <div className="hero-cta-group">
                        <Link to="/register" className="btn-hero-primary">
                            Bắt đầu miễn phí
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8-8-8z" /></svg>
                        </Link>
                        <Link to="/login" className="btn-hero-ghost">Đã có tài khoản</Link>
                    </div>
                    <div className="hero-stats">
                        <div className="hero-stat">
                            <span className="stat-number">500+</span>
                            <span className="stat-label">CV đã phân tích</span>
                        </div>
                        <div className="hero-stat">
                            <span className="stat-number">85%</span>
                            <span className="stat-label">Cải thiện điểm</span>
                        </div>
                        <div className="hero-stat">
                            <span className="stat-number">60s</span>
                            <span className="stat-label">Thời gian phân tích</span>
                        </div>
                    </div>
                </div>

                {/* Floating mockup card */}
                <div className="hero-visual">
                    <div className="hero-glow" />
                    <div className="hero-card">
                        <div className="hero-card-top">
                            <div>
                                <h3>Kết quả phân tích</h3>
                                <span className="hero-card-sub">Senior Backend Engineer</span>
                            </div>
                            <div className="hero-score-ring">
                                <svg viewBox="0 0 100 100">
                                    <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(45,52,72,0.6)" strokeWidth="7" />
                                    <circle cx="50" cy="50" r="42" fill="none" stroke="#adc6ff" strokeWidth="7"
                                        strokeDasharray="210 264" strokeLinecap="round"
                                        style={{ transform: 'rotate(-90deg)', transformOrigin: 'center' }} />
                                </svg>
                                <span className="ring-number">78.5</span>
                            </div>
                        </div>
                        <div className="hero-card-section">
                            <span className="hero-card-label">Kỹ năng cốt lõi</span>
                            <div className="hero-card-skills">
                                <span className="skill-chip matched">Python ✓</span>
                                <span className="skill-chip matched">FastAPI ✓</span>
                                <span className="skill-chip matched">Docker ✓</span>
                                <span className="skill-chip missing">AWS ✕</span>
                                <span className="skill-chip missing">K8s ✕</span>
                                <span className="skill-chip extra">CLIP +</span>
                            </div>
                        </div>
                        <div className="hero-card-tip">
                            <div className="tip-header">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="#adc6ff"><path d="M9 21c0 .5.4 1 1 1h4c.6 0 1-.5 1-1v-1H9v1zm3-19C8.1 2 5 5.1 5 9c0 2.4 1.2 4.5 3 5.7V17c0 .5.4 1 1 1h6c.6 0 1-.5 1-1v-2.3c1.8-1.3 3-3.4 3-5.7 0-3.9-3.1-7-7-7z" /></svg>
                                <span>Gợi ý từ AI</span>
                            </div>
                            <p>"Cần bổ sung chi tiết về các dự án xử lý phân tán để phù hợp hơn với yêu cầu hệ thống lớn."</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* How it works */}
            <section className="landing-steps">
                <h2 className="section-title">Quy trình thông minh</h2>
                <p className="section-subtitle">Chỉ 3 bước đơn giản để có một bản CV hoàn hảo</p>
                <div className="steps-grid">
                    <div className="step-card">
                        <div className="step-icon-wrap">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="#adc6ff"><path d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z" /></svg>
                        </div>
                        <span className="step-number">1</span>
                        <h3>Upload CV & JD</h3>
                        <p>Tải lên bản CV hiện tại và mô tả công việc bạn đang ứng tuyển.</p>
                    </div>
                    <div className="step-connector-line" />
                    <div className="step-card">
                        <div className="step-icon-wrap">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="#adc6ff"><path d="M20.5 11H19V7c0-1.1-.9-2-2-2h-4V3.5C13 2.12 11.88 1 10.5 1S8 2.12 8 3.5V5H4c-1.1 0-2 .9-2 2v3.8h1.5c1.38 0 2.5 1.12 2.5 2.5S4.88 15.8 3.5 15.8H2V19c0 1.1.9 2 2 2h3.8v-1.5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5V21H17c1.1 0 2-.9 2-2v-4h1.5c1.38 0 2.5-1.12 2.5-2.5S21.88 11 20.5 11z" /></svg>
                        </div>
                        <span className="step-number">2</span>
                        <h3>AI Phân tích</h3>
                        <p>AI so khớp kỹ năng, kiểm tra tính xác thực và tìm ra lỗ hổng.</p>
                    </div>
                    <div className="step-connector-line" />
                    <div className="step-card">
                        <div className="step-icon-wrap">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="#4edea3"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" /></svg>
                        </div>
                        <span className="step-number">3</span>
                        <h3>Nhận kết quả</h3>
                        <p>Nhận bản CV đã tối ưu kèm theo báo cáo chi tiết.</p>
                    </div>
                </div>
            </section>

            {/* Features */}
            <section className="landing-features">
                <div className="features-grid">
                    <FeatureCard icon="🎯" color="#3b82f6" title="Skill Matching thông minh"
                        desc="Phân tích sâu sự tương đồng giữa kỹ năng của bạn và yêu cầu nhà tuyển dụng." />
                    <FeatureCard icon="✏️" color="#4edea3" title="CV Rewrite bằng AI"
                        desc="Tự động viết lại với văn phong chuyên nghiệp, chuẩn quốc tế." />
                    <FeatureCard icon="🛡️" color="#ffb4ab" title="Hallucination Check"
                        desc="Phát hiện thông tin không chính xác hoặc phóng đại quá mức." />
                    <FeatureCard icon="📊" color="#f59e42" title="Visual Diff"
                        desc="So sánh trực quan giữa bản gốc và bản tối ưu, highlight mọi thay đổi." />
                </div>
            </section>

            {/* CTA */}
            <section className="landing-cta">
                <div className="cta-glow" />
                <div className="cta-content">
                    <div>
                        <h2>Sẵn sàng tối ưu CV?</h2>
                        <p>Tham gia cùng hàng nghìn ứng viên đã thành công trong việc chinh phục các công ty công nghệ hàng đầu.</p>
                    </div>
                    <Link to="/register" className="btn-hero-primary">
                        Bắt đầu ngay
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8-8-8z" /></svg>
                    </Link>
                </div>
            </section>

            {/* Footer */}
            <footer className="landing-footer">
                <div className="footer-content">
                    <div className="footer-brand">
                        <strong>Editorial Intelligence</strong>
                        <p>Nền tảng trí tuệ nhân tạo hàng đầu cho việc tối ưu hóa hồ sơ năng lực.</p>
                    </div>
                    <div className="footer-links">
                        <a href="#">Tính năng</a>
                        <a href="#">Về chúng tôi</a>
                        <a href="#">Điều khoản</a>
                        <a href="#">Bảo mật</a>
                    </div>
                    <span className="footer-copy">© 2026 Editorial Intelligence — Powered by AI</span>
                </div>
            </footer>
        </div>
    );
}

function FeatureCard({ icon, color, title, desc }) {
    return (
        <div className="feature-card">
            <div className="feature-icon" style={{ background: `${color}15`, borderColor: `${color}30` }}>
                <span style={{ fontSize: '1.4rem' }}>{icon}</span>
            </div>
            <h3>{title}</h3>
            <p>{desc}</p>
        </div>
    );
}
