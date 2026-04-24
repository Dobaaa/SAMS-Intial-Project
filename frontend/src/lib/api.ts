import axios, { AxiosError, type AxiosRequestConfig } from "axios";

import { useAuth } from "../stores/auth";

export const api = axios.create({ baseURL: "/api" });

// Attach the current access token to every outgoing request.
api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, try a single refresh round-trip, then replay the original request.
// If refresh also fails, clear the session and surface the original error so
// the route guard can redirect to /login.
let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setAccessToken, clear } = useAuth.getState();
  if (!refreshToken) {
    clear();
    return null;
  }
  try {
    const resp = await axios.post<{ access_token: string }>("/api/auth/refresh", {
      refresh_token: refreshToken,
    });
    const newToken = resp.data?.access_token ?? null;
    if (newToken) {
      setAccessToken(newToken);
      return newToken;
    }
    clear();
    return null;
  } catch {
    clear();
    return null;
  }
}

type RetryConfig = AxiosRequestConfig & { _retry?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    if (!original || error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }
    // Don't try to refresh the refresh endpoint itself or the login endpoint.
    if (original.url?.includes("/auth/refresh") || original.url?.includes("/auth/login")) {
      return Promise.reject(error);
    }

    original._retry = true;
    refreshInFlight = refreshInFlight ?? refreshAccessToken();
    const newToken = await refreshInFlight;
    refreshInFlight = null;

    if (!newToken) {
      return Promise.reject(error);
    }
    original.headers = original.headers ?? {};
    (original.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
    return api.request(original);
  }
);
