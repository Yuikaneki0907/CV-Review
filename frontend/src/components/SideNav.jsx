import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { listGeneratedCVs } from '../api';
import { listWorkspaceDrafts, WORKSPACE_DRAFT_EVENT } from '../utils/workspaceDraft';
import { 
  HomeIcon, 
  SparklesIcon, 
  ClockIcon, 
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  ChatBubbleLeftRightIcon,
  Bars3Icon,
  MagnifyingGlassIcon,
  CubeTransparentIcon
} from '@heroicons/react/24/outline';
import { 
  SparklesIcon as SparklesSolid, 
  ClockIcon as ClockSolid, 
  ChatBubbleLeftRightIcon as ChatSolid,
  CubeTransparentIcon as CubeSolid
} from '@heroicons/react/24/solid';

export default function SideNav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [history, setHistory] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  const isAuth = location.pathname === '/login' || location.pathname === '/register' || location.pathname === '/';

  useEffect(() => {
    if (user && !isAuth) {
      listGeneratedCVs().then(res => {
        setHistory(res.data || []);
      }).catch(err => {
        console.error("Error fetching history", err);
      });

      setDrafts(listWorkspaceDrafts(user.id));
    }
  }, [user, isAuth, location.pathname]); // Refetch when location changes to capture new CVs

  useEffect(() => {
    if (!user || isAuth) return;

    const refreshDrafts = () => setDrafts(listWorkspaceDrafts(user.id));
    window.addEventListener(WORKSPACE_DRAFT_EVENT, refreshDrafts);
    return () => {
      window.removeEventListener(WORKSPACE_DRAFT_EVENT, refreshDrafts);
    };
  }, [user, isAuth]);

  if (isAuth || !user) return null;

  const getIcon = (path, OutlineIcon, SolidIcon) => {
    return location.pathname === path ? <SolidIcon className="sidenav-icon active-icon" /> : <OutlineIcon className="sidenav-icon" />;
  };

  const filteredHistory = history.filter(item => 
    (item.job_title || 'CV Chưa Đặt Tên').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="sidenav-wrapper">
      {/* Primary Narrow Sidebar */}
      <nav className="sidenav">
        <div className="sidenav-top">
          <div className="sidenav-logo-container">
            <Link to="/generate-cv" className="sidenav-logo" title="Trang chủ">
              <SparklesIcon className="sidenav-logo-icon" />
            </Link>
          </div>
          
          <Link to="/generate-cv" className={`sidenav-item-wrapped ${location.pathname === '/generate-cv' ? 'active' : ''}`} title="Tạo CV mới">
            <div className="sidenav-item">
              <HomeIcon className="sidenav-icon" />
            </div>
            <span className="sidenav-text">New</span>
          </Link>

          <div 
            role="button"
            tabIndex={0}
            className={`sidenav-item-wrapped ${isSidebarOpen ? 'active' : ''}`} 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            title="Lịch sử Chat"
          >
            <div className="sidenav-item">
              {isSidebarOpen ? <CubeSolid className="sidenav-icon active-icon" /> : <CubeTransparentIcon className="sidenav-icon" />}
            </div>
            <span className="sidenav-text">Claw</span>
          </div>
          
          <div className="sidenav-divider" />
          
          <Link to="/upload" className={`sidenav-item-wrapped ${location.pathname === '/upload' ? 'active' : ''}`} title="Phân Tích Bằng Tay">
            <div className="sidenav-item">
              {getIcon('/upload', ChatBubbleLeftRightIcon, ChatSolid)}
            </div>
            <span className="sidenav-text">Upload</span>
          </Link>
          
          <Link to="/history" className={`sidenav-item-wrapped ${location.pathname === '/history' ? 'active' : ''}`} title="Lịch sử Dịch">
            <div className="sidenav-item">
              {getIcon('/history', ClockIcon, ClockSolid)}
            </div>
            <span className="sidenav-text">History</span>
          </Link>
        </div>

        <div className="sidenav-bottom">
          <div className="sidenav-item-wrapped" title={user.email}>
            <div className="sidenav-item">
              <UserCircleIcon className="sidenav-icon" />
            </div>
          </div>
          <div role="button" tabIndex={0} className="sidenav-item-wrapped" onClick={logout} title="Đăng xuất">
            <div className="sidenav-item">
              <ArrowRightOnRectangleIcon className="sidenav-icon" />
            </div>
          </div>
        </div>
      </nav>

      {/* Secondary Task List Sidebar */}
      <div className={`task-list-sidebar ${isSidebarOpen ? '' : 'closed'}`}>
        <div className="task-list-header">
          <h3>Task List</h3>
          <button className="task-list-toggle" onClick={() => setIsSidebarOpen(false)}>
            <Bars3Icon className="sidenav-icon" />
          </button>
        </div>
        
        <div className="task-list-search">
          <div className="task-list-search-wrap">
            <MagnifyingGlassIcon className="task-list-search-icon" />
            <input 
              type="text" 
              className="task-list-search-input" 
              placeholder="Search Chats" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="task-list-content">
          {drafts.length > 0 && (
            <>
              <div className="task-item-group">Đang làm dở</div>
              {drafts.map((item) => {
                const to = item.id ? `/workspace/${item.id}` : '/workspace';
                const isActive = location.pathname === to;
                return (
                  <Link
                    key={item.key}
                    to={to}
                    className={`task-item ${isActive ? 'active' : ''}`}
                    title={item.title}
                  >
                    <SparklesIcon className="task-item-icon" />
                    <span className="task-title">
                      {item.pending ? '[Đang xử lý] ' : ''}
                      {item.title}
                    </span>
                  </Link>
                );
              })}
            </>
          )}

          <div className="task-item-group">Today</div>
          {filteredHistory.map(item => {
            const isActive = location.pathname === `/workspace/${item.id}`;
            return (
              <Link 
                key={item.id} 
                to={`/workspace/${item.id}`} 
                className={`task-item ${isActive ? 'active' : ''}`}
                title={item.job_title || 'CV Chưa Đặt Tên'}
              >
                <ClockIcon className="task-item-icon" />
                <span className="task-title">
                  {item.job_title || 'Mẫu CV HTML Kỹ Sư...'}
                </span>
              </Link>
            );
          })}
          {filteredHistory.length === 0 && (
            <div style={{ padding: '1rem', color: 'var(--outline-variant)', fontSize: '0.8rem', textAlign: 'center' }}>
              Không có dữ liệu
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
