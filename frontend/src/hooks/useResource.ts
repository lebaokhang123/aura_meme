import { useCallback, useEffect, useState } from 'react';
import { api, ApiError, errorMessage } from '../api';
import { useAuth } from '../context/AuthContext';

export function useResource<T>(path: string | null) {
  const [attempt, setAttempt] = useState(0);
  const { refresh } = useAuth();
  const [state, setState] = useState<{ path: string | null; data: T | null; pending: boolean; error: string }>({ path: null, data: null, pending: false, error: '' });
  useEffect(() => {
    if (!path) { setState({ path, data: null, pending: false, error: '' }); return; }
    const controller = new AbortController();
    setState({ path, data: null, pending: true, error: '' });
    api<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ path, data, pending: false, error: '' });
    }).catch(fault => {
      if (controller.signal.aborted) return;
      setState({ path, data: null, pending: false, error: errorMessage(fault) });
      if (fault instanceof ApiError && fault.status === 401) void refresh();
    });
    return () => controller.abort();
  }, [path, attempt, refresh]);
  return { data: state.path === path ? state.data : null, error: state.path === path ? state.error : '',
    pending: !!path && (state.path !== path || state.pending), reload: useCallback(() => setAttempt(value => value + 1), []) };
}
