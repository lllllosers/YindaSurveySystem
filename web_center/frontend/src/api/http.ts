import axios from "axios";

const CSRF_COOKIE_NAME = "yd_csrf";

function readCookie(
  name: string,
): string {
  const prefix = `${name}=`;

  for (
    const part
    of document.cookie.split(";")
  ) {
    const value = part.trim();

    if (value.startsWith(prefix)) {
      return decodeURIComponent(
        value.slice(prefix.length),
      );
    }
  }

  return "";
}

export function getCsrfToken(): string {
  return readCookie(CSRF_COOKIE_NAME);
}

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  withCredentials: true,
});

api.interceptors.request.use(
  (config) => {
    if (
      config.data instanceof FormData
    ) {
      config.headers.delete(
        "Content-Type",
      );
    }

    const method = (
      config.method ?? "get"
    ).toLowerCase();

    if (
      [
        "post",
        "put",
        "patch",
        "delete",
      ].includes(method)
    ) {
      const token = getCsrfToken();

      if (token) {
        config.headers[
          "X-CSRF-Token"
        ] = token;
      }
    }

    return config;
  },
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error?.response?.status === 401
      && window.location.pathname !== "/login"
    ) {
      window.location.assign(
        "/login",
      );
    }

    return Promise.reject(error);
  },
);
