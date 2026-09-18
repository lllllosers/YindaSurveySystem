import axios from "axios";

const CSRF_KEY = "yinda_csrf_token";

export function getCsrfToken(): string {
  return sessionStorage.getItem(CSRF_KEY) ?? "";
}

export function setCsrfToken(token: string | null): void {
  if (token) {
    sessionStorage.setItem(CSRF_KEY, token);
  } else {
    sessionStorage.removeItem(CSRF_KEY);
  }
}

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    config.headers.delete("Content-Type");
  }

  const method = (config.method ?? "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const token = getCsrfToken();
    if (token) {
      config.headers["X-CSRF-Token"] = token;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error?.response?.status === 401 &&
      window.location.pathname !== "/login"
    ) {
      setCsrfToken(null);
      window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);
