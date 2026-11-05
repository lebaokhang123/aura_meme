import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api, ApiError, errorMessage } from '../api';

export interface Account {
  id: string; username: string; email: string; display_name: string; roles: ('USER' | 'ADMIN')[];
  status: string; bio: string | null; birth_year: number | null; address: string | null; phone: string | null;
  avatar_media_id: string | null; cover_media_id: string | null;
}
const AuthContext = createContext<{
  user: Account | null; pending: boolean; error: string; refresh: () => Promise<void>; logout: () => Promise<void>;
} | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Account | null>(null);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState('');
  const epoch = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++epoch.current;
    setPending(true); setError('');
    try {
      const value = await api<Account>('/users/me');
      if (request === epoch.current) setUser(value);
    } catch (fault) {
      if (request !== epoch.current) return;
      if (fault instanceof ApiError && fault.status === 401) setUser(null);
      else setError(errorMessage(fault));
    } finally { if (request === epoch.current) setPending(false); }
  }, []);
  useEffect(() => { void refresh(); return () => { epoch.current++; }; }, [refresh]);
  const logout = async () => {
    await api('/auth/logout', { method: 'POST' });
    epoch.current++; setUser(null); setError(''); setPending(false);
  };
  return <AuthContext.Provider value={{ user, pending, error, refresh, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider required');
  return value;
}
