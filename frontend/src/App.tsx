import { useEffect, useRef } from 'react';
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { UIProvider, useUI } from './context/UIContext';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { SearchModal } from './components/SearchModal';
import { HomePage } from './pages/HomePage';
import { ExplorePage } from './pages/ExplorePage';
import { AboutPage } from './pages/AboutPage';
import { ContactPage } from './pages/ContactPage';
import { LoginPage } from './pages/LoginPage';
import { SignUpPage } from './pages/SignUpPage';

function AppContent() {
  const { toastMessage } = useUI();
  const { pathname, hash } = useLocation();
  const previousPath = useRef(pathname);
  useEffect(() => {
    const titles: Record<string, string> = {
      '/': 'Home',
      '/explore': 'Explore',
      '/about': 'About',
      '/contact': 'Contact',
      '/login': 'Login',
      '/register': 'Register',
    };
    document.title = `${titles[pathname] ?? 'Page not found'} — AuraMeme`;
    if (hash === '#team') {
      const team = document.getElementById('team');
      team?.scrollIntoView();
      team?.focus({ preventScroll: true });
    } else {
      window.scrollTo(0, 0);
      if (previousPath.current !== pathname)
        document.getElementById('main-content')?.focus({ preventScroll: true });
    }
    previousPath.current = pathname;
  }, [pathname, hash]);

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col font-['Inter'] antialiased">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Header />
      <main id="main-content" tabIndex={-1} className="w-full min-w-0 pt-16 flex-1 flex flex-col">
        <div
          role="note"
          className="preview-note px-4 py-2.5 text-center text-xs border-b border-primary/15 bg-primary/5 text-on-surface-variant"
        >
          <strong className="text-primary">Frontend preview</strong> · Demo posts and sample counts. Accounts,
          messages and rewards are not connected.
        </div>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<SignUpPage />} />
          <Route path="/home" element={<Navigate to="/" replace />} />
          <Route path="/about-us" element={<Navigate to="/about" replace />} />
          <Route path="/team" element={<Navigate to="/about#team" replace />} />
          <Route path="/signup" element={<Navigate to="/register" replace />} />
          <Route
            path="*"
            element={
              <section className="max-w-lg mx-auto px-4 py-24 text-center">
                <span className="text-secondary font-mono">404</span>
                <h1 className="text-3xl font-bold mt-3">Page not found</h1>
                <p className="text-on-surface-variant mt-4">This page is not available.</p>
                <Link to="/" className="inline-flex mt-6 px-5 py-3 rounded-lg bg-primary text-on-primary">
                  Back to Home
                </Link>
              </section>
            }
          />
        </Routes>
      </main>
      <Footer />
      <SearchModal />
      {toastMessage && (
        <div
          role="status"
          className="fixed bottom-6 right-6 left-6 sm:left-auto sm:max-w-md z-50 p-4 rounded-xl bg-surface-container-high border border-primary/30 shadow-xl text-sm"
        >
          {toastMessage}
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <UIProvider>
      <AppContent />
    </UIProvider>
  );
}
