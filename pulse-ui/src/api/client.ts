import axios from 'axios';

const apiClient = axios.create({
  // Relative by default so the vite dev proxy (dev) or the nginx /api proxy
  // (docker/k8s) routes to pulse-api. VITE_API_URL overrides for split-origin
  // deployments.
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('pulse_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // On 401, drop the token and send the user to the login page — except
    // for the auth endpoints that own their own error UX (login attempts,
    // and logout, where the SPA transitions itself regardless).
    const url: string = error.config?.url ?? '';
    const selfHandled = url.includes('/auth/login') || url.includes('/auth/logout');
    if (error.response?.status === 401 && !selfHandled) {
      localStorage.removeItem('pulse_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/** Extract a human-readable message from an axios/backend error. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string' && detail.length > 0) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI validation errors: list of { loc, msg, type }
      return detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join('; ');
    }
    return err.message;
  }
  return err instanceof Error ? err.message : fallback;
}

export default apiClient;
