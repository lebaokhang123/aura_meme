import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function AccountBoundary({ children }: { children: ReactNode }) {
  const { pending, user, error, refresh } = useAuth();
  if (pending) return <p role="status" className="p-8">Checking your session…</p>;
  if (error) return <div className="p-8"><p role="alert">{error}</p><button className="mt-4 min-h-11 underline" onClick={() => void refresh()}>Retry session</button></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
