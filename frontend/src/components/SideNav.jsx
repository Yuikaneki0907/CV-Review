import { createElement, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { deleteChatSession, listChatSessions } from '../api';
import { WORKSPACE_DRAFT_EVENT } from '../utils/workspaceDraft';
import { GENERATED_CV_HISTORY_EVENT, notifyGeneratedCvHistoryChanged } from '../utils/generatedCvHistory';
import {
  HomeIcon,
  SparklesIcon,
  ClockIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  Bars3Icon,
  MagnifyingGlassIcon,
  CubeTransparentIcon,
  UserIcon,
  FolderIcon,
  EllipsisHorizontalIcon,
} from '@heroicons/react/24/outline';
import {
  ClockIcon as ClockSolid,
  CubeTransparentIcon as CubeSolid,
  FolderIcon as FolderSolid,
} from '@heroicons/react/24/solid';

export default function SideNav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [chatSessions, setChatSessions] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [openMenuKey, setOpenMenuKey] = useState(null);
  const [deletingKey, setDeletingKey] = useState(null);
  const [deleteConfirmTarget, setDeleteConfirmTarget] = useState(null);
  const [deleteError, setDeleteError] = useState('');

  const isAuth = location.pathname === '/login' || location.pathname === '/register' || location.pathname === '/';

  useEffect(() => {
    if (!user || isAuth) return undefined;

    let cancelled = false;

    const refreshWorkspaceHistory = async () => {
      setHistoryLoading(true);
      try {
        const sessionRes = await listChatSessions(50, 0);
        if (!cancelled) {
          setChatSessions(Array.isArray(sessionRes?.data) ? sessionRes.data : []);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Error fetching workspace history', err);
        }
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    };

    const handleVisibilityRefresh = () => {
      if (document.visibilityState === 'visible') {
        refreshWorkspaceHistory();
      }
    };
    const handleStorage = () => {
      refreshWorkspaceHistory();
    };

    refreshWorkspaceHistory();

    window.addEventListener(WORKSPACE_DRAFT_EVENT, refreshWorkspaceHistory);
    window.addEventListener(GENERATED_CV_HISTORY_EVENT, refreshWorkspaceHistory);
    window.addEventListener('focus', refreshWorkspaceHistory);
    window.addEventListener('storage', handleStorage);
    document.addEventListener('visibilitychange', handleVisibilityRefresh);

    return () => {
      cancelled = true;
      window.removeEventListener(WORKSPACE_DRAFT_EVENT, refreshWorkspaceHistory);
      window.removeEventListener(GENERATED_CV_HISTORY_EVENT, refreshWorkspaceHistory);
      window.removeEventListener('focus', refreshWorkspaceHistory);
      window.removeEventListener('storage', handleStorage);
      document.removeEventListener('visibilitychange', handleVisibilityRefresh);
    };
  }, [user, isAuth]);

  const filteredChatSessions = useMemo(() => chatSessions.filter((item) =>
    (item.chat_title || 'Cuộc trò chuyện mới').toLowerCase().includes(searchTerm.toLowerCase())
  ), [chatSessions, searchTerm]);

  useEffect(() => {
    const closeMenus = () => setOpenMenuKey(null);
    window.addEventListener('click', closeMenus);
    return () => window.removeEventListener('click', closeMenus);
  }, []);

  if (isAuth || !user) return null;

  const getIcon = (path, OutlineIcon, SolidIcon) => {
    const Icon = location.pathname === path ? SolidIcon : OutlineIcon;
    return createElement(Icon, {
      className: `sidenav-icon ${location.pathname === path ? 'active-icon' : ''}`.trim(),
    });
  };

  const openContextMenu = (event, menuKey) => {
    event.preventDefault();
    event.stopPropagation();
    setOpenMenuKey((prev) => (prev === menuKey ? null : menuKey));
  };

  const requestDeleteChatSession = (event, sessionItem) => {
    event.preventDefault();
    event.stopPropagation();
    setOpenMenuKey(null);
    setDeleteError('');
    setDeleteConfirmTarget({
      type: 'chat',
      key: `chat:${sessionItem.conversation_id}`,
      id: sessionItem.conversation_id,
      title: sessionItem.chat_title || 'Cuộc trò chuyện mới',
    });
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirmTarget || deletingKey) return;
    const { key, id } = deleteConfirmTarget;
    setDeletingKey(key);
    try {
      await deleteChatSession(id);
      setChatSessions((prev) => prev.filter((item) => item.conversation_id !== id));
      const activeConversation = new URLSearchParams(location.search).get('conversation');
      const isWorkspaceConversationRoute = location.pathname === '/workspace' && activeConversation === id;
      const isWorkspaceCvRoute = location.pathname.startsWith('/workspace/');
      if (isWorkspaceConversationRoute || isWorkspaceCvRoute) {
        navigate('/generate-cv', { replace: true });
      }
      setDeleteConfirmTarget(null);
      notifyGeneratedCvHistoryChanged();
    } catch (err) {
      console.error('Error deleting item', err);
      setDeleteError(err.response?.data?.detail || 'Không thể xóa mục này.');
    } finally {
      setDeletingKey(null);
    }
  };

  return (
    <div className="sidenav-wrapper">
      {/* Primary Narrow Sidebar */}
      <nav className="sidenav">
        <div className="sidenav-top">
          <div className="sidenav-logo-container">
            <Link to="/generate-cv" className="sidenav-logo" data-tooltip="Trang chủ" aria-label="Trang chủ">
              <SparklesIcon className="sidenav-logo-icon" />
            </Link>
          </div>

          <Link to="/generate-cv" className={`sidenav-item-wrapped ${location.pathname === '/generate-cv' ? 'active' : ''}`} data-tooltip="Tạo CV mới" aria-label="Tạo CV mới">
            <div className="sidenav-item">
              <HomeIcon className="sidenav-icon" />
            </div>
            <span className="sidenav-text">Mới</span>
          </Link>

          <div
            role="button"
            tabIndex={0}
            className={`sidenav-item-wrapped ${isSidebarOpen ? 'active' : ''}`}
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            data-tooltip="Lịch sử Chat"
            aria-label="Lịch sử Chat"
          >
            <div className="sidenav-item">
              {isSidebarOpen ? <CubeSolid className="sidenav-icon active-icon" /> : <CubeTransparentIcon className="sidenav-icon" />}
            </div>
            <span className="sidenav-text">Không gian làm việc</span>
          </div>


          <Link to="/history" className={`sidenav-item-wrapped ${location.pathname === '/history' ? 'active' : ''}`} data-tooltip="Lịch sử phân tích" aria-label="Lịch sử phân tích">
            <div className="sidenav-item">
              {getIcon('/history', ClockIcon, ClockSolid)}
            </div>
            <span className="sidenav-text">Phân tích</span>
          </Link>

          <Link to="/cv-management" className={`sidenav-item-wrapped ${location.pathname === '/cv-management' ? 'active' : ''}`} data-tooltip="Quản lí CV" aria-label="Quản lí CV">
            <div className="sidenav-item">
              {getIcon('/cv-management', FolderIcon, FolderSolid)}
            </div>
            <span className="sidenav-text">Quản lí CV</span>
          </Link>
        </div>

        <div className="sidenav-bottom">
          <Link
            to="/profile"
            className={`sidenav-item-wrapped ${location.pathname === '/profile' ? 'active' : ''}`}
            data-tooltip="Hồ sơ cá nhân"
            aria-label="Hồ sơ cá nhân"
          >
            <div className="sidenav-item">
              {location.pathname === '/profile' ? <UserCircleIcon className="sidenav-icon active-icon" /> : <UserIcon className="sidenav-icon" />}
            </div>
            <span className="sidenav-text">Hồ sơ</span>
          </Link>
          <div role="button" tabIndex={0} className="sidenav-item-wrapped" onClick={logout} data-tooltip="Đăng xuất" aria-label="Đăng xuất">
            <div className="sidenav-item">
              <ArrowRightOnRectangleIcon className="sidenav-icon" />
            </div>
          </div>
        </div>
      </nav>

      {/* Secondary Task List Sidebar */}
      <div className={`task-list-sidebar ${isSidebarOpen ? '' : 'closed'}`}>
        <div className="task-list-header">
          <h3>Không gian làm việc</h3>
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
              placeholder="Tìm workspace"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="task-list-content">
          {filteredChatSessions.length > 0 && (
            <>
              <div className="task-item-group">Gần đây</div>
              {filteredChatSessions.map((item) => {
                const to = `/workspace?conversation=${item.conversation_id}`;
                const activeConversation = new URLSearchParams(location.search).get('conversation');
                const isActive = location.pathname === '/workspace' && activeConversation === item.conversation_id;
                const title = item.chat_title || 'Cuộc trò chuyện mới';
                const menuKey = `chat:${item.conversation_id}`;
                return (
                  <div key={item.conversation_id} className="task-item-row">
                    <Link
                      to={to}
                      className={`task-item ${isActive ? 'active' : ''}`}
                      title={title}
                    >
                      <SparklesIcon className="task-item-icon" />
                      <span className="task-title">
                        {title}
                      </span>
                    </Link>
                    <div className="task-item-actions" onClick={(event) => event.stopPropagation()}>
                      <button
                        type="button"
                        className="task-item-menu-btn"
                        title="Tùy chọn"
                        onClick={(event) => openContextMenu(event, menuKey)}
                        disabled={deletingKey === menuKey}
                      >
                        <EllipsisHorizontalIcon className="task-item-menu-icon" />
                      </button>
                      {openMenuKey === menuKey && (
                        <div className="task-item-menu">
                          <button
                            type="button"
                            className="task-item-menu-delete"
                            onClick={(event) => requestDeleteChatSession(event, item)}
                            disabled={deletingKey === menuKey}
                          >
                            {deletingKey === menuKey ? 'Đang xóa...' : 'Xóa'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {historyLoading && (
            <div style={{ padding: '1rem', color: 'var(--outline-variant)', fontSize: '0.8rem', textAlign: 'center' }}>
              Đang tải workspace...
            </div>
          )}
          {!historyLoading && filteredChatSessions.length === 0 && (
            <div style={{ padding: '1rem', color: 'var(--outline-variant)', fontSize: '0.8rem', textAlign: 'center' }}>
              Chưa có workspace nào
            </div>
          )}
        </div>
      </div>
      {deleteConfirmTarget && (
        <div className="confirm-modal-backdrop" role="presentation">
          <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-delete-sidenav">
            <h3 id="confirm-delete-sidenav">Xác nhận xóa</h3>
            <p>
              Bạn có chắc muốn xóa <strong>{deleteConfirmTarget.title}</strong> không?
            </p>
            {deleteError && <div className="confirm-modal-error">{deleteError}</div>}
            <div className="confirm-modal-actions">
              <button
                type="button"
                className="confirm-modal-btn cancel"
                onClick={() => setDeleteConfirmTarget(null)}
                disabled={Boolean(deletingKey)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="confirm-modal-btn danger"
                onClick={handleConfirmDelete}
                disabled={Boolean(deletingKey)}
              >
                {deletingKey ? 'Đang xóa...' : 'Xóa'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
