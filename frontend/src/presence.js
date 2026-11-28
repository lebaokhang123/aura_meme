import { auth } from './auth.js';

export const HEARTBEAT_INTERVAL_MS = 30000;

export function startPresenceHeartbeat({
  authClient = auth,
  documentObj = typeof document !== 'undefined' ? document : null,
  nowFn = () => Date.now(),
  setIntervalFn = globalThis.setInterval,
  clearIntervalFn = globalThis.clearInterval,
} = {}) {
  let stopped = false;
  let timerId = null;
  let inFlight = false;
  let blockedUntil = 0;
  let lastAuthKey = `${authClient.snapshot().status}:${authClient.snapshot().user?.id ?? ''}`;

  const isVisible = () => !documentObj || documentObj.visibilityState !== 'hidden';

  const send = async () => {
    if (stopped || inFlight || !isVisible()) return;
    const now = nowFn();
    if (now < blockedUntil) return;
    inFlight = true;
    try {
      await authClient.read('/presence/heartbeat', { method: 'POST' });
    } catch (error) {
      if (error?.status === 429) {
        const retrySeconds = Number.isFinite(error.retryAfter) && error.retryAfter > 0 ? error.retryAfter : 60;
        blockedUntil = nowFn() + retrySeconds * 1000;
      }
    } finally {
      inFlight = false;
    }
  };

  const stopTimer = () => {
    if (timerId !== null) {
      clearIntervalFn(timerId);
      timerId = null;
    }
  };

  const startTimer = () => {
    if (stopped || timerId !== null || !isVisible()) return;
    timerId = setIntervalFn(() => {
      send();
    }, HEARTBEAT_INTERVAL_MS);
    timerId?.unref?.();
  };

  const onVisibilityChange = () => {
    if (stopped) return;
    if (isVisible()) {
      send();
      startTimer();
    } else {
      stopTimer();
    }
  };

  const unsubscribe = authClient.subscribe(() => {
    if (stopped) return;
    const snap = authClient.snapshot();
    if (snap.status === 'loading') return;
    const nextKey = `${snap.status}:${snap.user?.id ?? ''}`;
    if (nextKey !== lastAuthKey) {
      lastAuthKey = nextKey;
      send();
    }
  });

  if (documentObj) {
    documentObj.addEventListener('visibilitychange', onVisibilityChange);
  }
  if (isVisible()) {
    send();
    startTimer();
  }

  return () => {
    stopped = true;
    stopTimer();
    unsubscribe?.();
    if (documentObj) {
      documentObj.removeEventListener('visibilitychange', onVisibilityChange);
    }
  };
}
