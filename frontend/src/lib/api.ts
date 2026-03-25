import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

// Attach access token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = Cookies.get("access_token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Refresh token on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = Cookies.get("refresh_token");
      if (refresh) {
        try {
          const { data } = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
            refresh_token: refresh,
          });
          Cookies.set("access_token", data.access_token, { secure: true, sameSite: "strict" });
          Cookies.set("refresh_token", data.refresh_token, { secure: true, sameSite: "strict" });
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch {
          Cookies.remove("access_token");
          Cookies.remove("refresh_token");
          window.location.href = "/auth/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  refresh: (refresh_token: string) =>
    api.post("/auth/refresh", { refresh_token }),
  me: () => api.get("/auth/me"),
  regenerateApiKey: () => api.post("/auth/api-key/regenerate"),
};

// ── Scans ──────────────────────────────────────────────────────────────────────
export const scansApi = {
  list: (params?: Record<string, unknown>) => api.get("/scans", { params }),
  get: (id: string) => api.get(`/scans/${id}`),
  create: (data: unknown) => api.post("/scans", data),
  cancel: (id: string) => api.post(`/scans/${id}/cancel`),
  delete: (id: string) => api.delete(`/scans/${id}`),
  stats: () => api.get("/scans/stats"),
};

// ── Findings ──────────────────────────────────────────────────────────────────
export const findingsApi = {
  list: (params?: Record<string, unknown>) => api.get("/findings", { params }),
  get: (id: string) => api.get(`/findings/${id}`),
  stats: (params?: Record<string, unknown>) =>
    api.get("/findings/stats", { params }),
};

// ── Targets ──────────────────────────────────────────────────────────────────
export const targetsApi = {
  list: () => api.get("/targets"),
  create: (data: unknown) => api.post("/targets", data),
  importBulk: (data: unknown) => api.post("/targets/import", data),
  delete: (id: string) => api.delete(`/targets/${id}`),
  lists: () => api.get("/targets/lists"),
  getList: (id: string) => api.get(`/targets/lists/${id}`),
  createList: (data: unknown) => api.post("/targets/lists", data),
  deleteList: (id: string) => api.delete(`/targets/lists/${id}`),
};

// ── Webhooks ──────────────────────────────────────────────────────────────────
export const webhooksApi = {
  list: () => api.get("/webhooks"),
  create: (data: unknown) => api.post("/webhooks", data),
  update: (id: string, data: unknown) => api.patch(`/webhooks/${id}`, data),
  delete: (id: string) => api.delete(`/webhooks/${id}`),
  test: (id: string) => api.post(`/webhooks/${id}/test`),
};

// ── Templates ──────────────────────────────────────────────────────────────────
export const templatesApi = {
  list: (params?: Record<string, unknown>) => api.get("/templates", { params }),
  sync: () => api.post("/templates/sync"),
  getContent: (id: string) => api.get(`/templates/${id}/content`),
  updateContent: (id: string, content: string) =>
    api.put(`/templates/${id}/content`, { content }),
};

// ── Users ──────────────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => api.get("/users"),
  get: (id: string) => api.get(`/users/${id}`),
  create: (data: unknown) => api.post("/users", data),
  update: (id: string, data: unknown) => api.patch(`/users/${id}`, data),
  delete: (id: string) => api.delete(`/users/${id}`),
};

export default api;
