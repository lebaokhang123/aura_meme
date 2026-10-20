import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { user, posts } from '../data/mockData';

function useUIState() {
  const [isSearchOpen, setSearchOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [feedTab, setFeedTab] = useState<'hot' | 'new' | 'top'>('hot');

  useEffect(() => {
    if (!toastMessage) return;
    const timer = window.setTimeout(() => setToastMessage(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toastMessage]);

  const showToast = (message: string) => setToastMessage(message);
  const showDemo = () => showToast('UI prototype only — this feature is not implemented.');

  return {
    user, posts, toastMessage, showToast,
    isSearchOpen, setSearchOpen,
    selectedCategory, setSelectedCategory, feedTab, setFeedTab,
    // Shared presentation actions keep mock Aura and Nitro values unchanged.
    toggleReaction: showDemo, awardAuraToPost: showDemo, toggleBookmark: showDemo,
    claimDailyBonus: showDemo, dailyBonusClaimed: false,
    showNitroPreview: showDemo, showCreatePostPreview: showDemo,
    communityTeamAura: 420, boostCommunityTeamAura: showDemo,
  };
}

const UIContext = createContext<ReturnType<typeof useUIState> | undefined>(undefined);

export function UIProvider({ children }: { children: ReactNode }) {
  const value = useUIState();
  return <UIContext.Provider value={value}>{children}</UIContext.Provider>;
}

export function useUI() {
  const context = useContext(UIContext);
  if (!context) throw new Error('useUI must be used within UIProvider');
  return context;
}
