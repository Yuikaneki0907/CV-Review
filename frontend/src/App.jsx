import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import SideNav from './components/SideNav';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AnalysisPage from './pages/AnalysisPage';
import HistoryPage from './pages/HistoryPage';
import GenerateCVPage from './pages/GenerateCVPage';
import WorkspacePage from './pages/WorkspacePage';


function PrivateRoute({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app">
          <SideNav />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route
                path="/upload"
                element={(
                  <PrivateRoute>
                    <Navigate to="/generate-cv" replace state={{ mode: 'analyze' }} />
                  </PrivateRoute>
                )}
              />
              <Route path="/analysis/:id" element={<PrivateRoute><AnalysisPage /></PrivateRoute>} />
              <Route path="/history" element={<PrivateRoute><HistoryPage /></PrivateRoute>} />
              <Route path="/generate-cv" element={<PrivateRoute><GenerateCVPage /></PrivateRoute>} />
              <Route path="/workspace" element={<PrivateRoute><WorkspacePage /></PrivateRoute>} />
              <Route path="/workspace/:id" element={<PrivateRoute><WorkspacePage /></PrivateRoute>} />

            </Routes>
          </main>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
