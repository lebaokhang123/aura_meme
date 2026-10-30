import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { demoPosts } from '../data/demoData';

function useUIState() {
  const [isSearchOpen, setSearchOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [feedTab, setFeedTab] = useState<'hot' | 'new' | 'top'>('hot');
  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => setToastMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);
  return {
    posts: demoPosts,
    isSearchOpen,
    setSearchOpen,
    toastMessage,
    showToast: setToastMessage,
    selectedCategory,
    setSelectedCategory,
    feedTab,
    setFeedTab,
  };
}

const UIContext = createContext<ReturnType<typeof useUIState> | undefined>(undefined);
export function UIProvider({ children }: { children: ReactNode }) {
  return <UIContext.Provider value={useUIState()}>{children}</UIContext.Provider>;
}
export function useUI() {
  const context = useContext(UIContext);
  if (!context) throw new Error('useUI must be used within UIProvider');
  return context;
}
