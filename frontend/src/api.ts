export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(status === 401 ? 'Invalid email or password, or your session has expired.'
      : status === 403 ? 'Request not permitted. Refresh your session and try again.'
      : status === 404 ? 'The requested item was not found.'
      : status === 409 ? 'The request conflicts with existing data. Check your values.'
      : status === 422 ? 'Check the entered fields and try again.'
      : status === 429 ? 'Too many requests. Please wait before trying again.'
      : 'Unable to complete the request. Check your connection and try again.');
  }
}

export async function api<T>(path: string, options: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = {};
  if (method !== 'GET') {
    const { csrf_token } = await api<{ csrf_token: string }>('/auth/csrf');
    headers['X-CSRF-Token'] = csrf_token;
  }
  const multipart = options.body instanceof FormData;
  if (options.body !== undefined && !multipart) headers['Content-Type'] = 'application/json';
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, { method, headers, credentials: 'include', cache: 'no-store',
      signal: options.signal, body: options.body === undefined ? undefined : multipart ? options.body as FormData : JSON.stringify(options.body) });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'NETWORK_ERROR');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.error?.code ?? 'REQUEST_FAILED');
  }
  return response.status === 204 ? undefined as T : response.json();
}

export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Request failed. Please try again.';
