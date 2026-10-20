import { useEffect } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { UIProvider, useUI } from './context/UIContext';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { SearchModal } from './components/SearchModal';
import { HomePage } from './pages/HomePage';
import { AboutPage } from './pages/AboutPage';
import { TeamPage } from './pages/TeamPage';
import { ContactPage } from './pages/ContactPage';
import { LoginPage } from './pages/LoginPage';
import { SignUpPage } from './pages/SignUpPage';
import { ExplorePage } from './pages/ExplorePage';

function AppContent() {
  const { toastMessage } = useUI();
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col font-['Inter'] antialiased">
      <Header />
      <main className="w-full pt-16 flex-1 flex flex-col">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/about-us" element={<AboutPage />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<SignUpPage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/signup" element={<Navigate to="/register" replace />} />
          <Route path="*" element={<div className="p-12 text-center"><h1>Page not found</h1><Link to="/">Back to Home</Link></div>} />
        </Routes>
      </main>
      <Footer />
      <SearchModal />
      {toastMessage && <div role="status" className="fixed bottom-6 right-6 left-6 sm:left-auto z-50 p-4 rounded-xl bg-surface-container-high border border-primary/30 shadow-xl">{toastMessage}</div>}
    </div>
  );
}

export default function App() {
  return <UIProvider><AppContent /></UIProvider>;
}
