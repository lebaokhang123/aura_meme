import { useCallback, useEffect, useState } from 'react';
import { api, ApiError, errorMessage } from '../api';
import { useAuth } from '../context/AuthContext';

export function useResource<T>(path: string | null) {
  const [attempt, setAttempt] = useState(0);
  const { refresh } = useAuth();
  const [state, setState] = useState<{ path: string | null; attempt: number; data: T | null; pending: boolean; error: string }>({ path: null, attempt: 0, data: null, pending: false, error: '' });
  useEffect(() => {
    if (!path) { setState({ path, attempt, data: null, pending: false, error: '' }); return; }
    const controller = new AbortController();
    setState({ path, attempt, data: null, pending: true, error: '' });
    api<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ path, attempt, data, pending: false, error: '' });
    }).catch(fault => {
      if (controller.signal.aborted) return;
      setState({ path, attempt, data: null, pending: false, error: errorMessage(fault) });
      if (fault instanceof ApiError && (fault.status === 401 || (fault.status === 403 && path.startsWith('/admin/')))) void refresh();
    });
    return () => controller.abort();
  }, [path, attempt, refresh]);
  const current = state.path === path && state.attempt === attempt;
  return { data: current ? state.data : null, error: current ? state.error : '',
    pending: !!path && (!current || state.pending), reload: useCallback(() => setAttempt(value => value + 1), []) };
}
