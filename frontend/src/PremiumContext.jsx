import React, { createContext, useContext, useEffect, useState, useCallback, useSyncExternalStore } from 'react';
import { auth, MOCK_AUTH } from './auth.js';

const defaultSub = {
  tier: 'free',
  is_active: false,
  boost_multiplier: 1,
  days_remaining: 0,
};

const PremiumContext = createContext({
  subscription: defaultSub,
  loading: false,
  refresh: () => Promise.resolve(),
});

export function PremiumProvider({ children }) {
  const [subscription, setSubscription] = useState(defaultSub);
  const [loading, setLoading] = useState(false);
  const session = useSyncExternalStore(auth.subscribe, auth.snapshot);
  const isAuthenticated = !MOCK_AUTH && session.status === 'authenticated' && !!session.user;

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setSubscription(defaultSub);
      return;
    }
    setLoading(true);
    try {
      const res = await auth.read('/premium/status');
      if (res?.subscription) {
        const sub = res.subscription;
        const is_active = !!(sub.is_active || sub.active);
        const tier = (sub.tier || 'free').toLowerCase();
        setSubscription({
          tier: is_active ? tier : 'free',
          is_active,
          boost_multiplier: sub.boost_multiplier || sub.multiplier || (tier === 'prime' ? 3 : tier === 'plus' ? 2 : 1),
          days_remaining: sub.days_remaining || 0,
          expires_at: sub.expires_at || null,
        });
      } else {
        setSubscription(defaultSub);
      }
    } catch {
      // Retain or fallback gracefully
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, session.user?.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <PremiumContext.Provider value={{ subscription, loading, refresh }}>
      {children}
    </PremiumContext.Provider>
  );
}

export function usePremium() {
  return useContext(PremiumContext);
}
