import axios, { type AxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth-store";

const apiClient = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// Track whether a token refresh is already in progress to avoid concurrent refreshes
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
  config: AxiosRequestConfig;
}> = [];

function processQueue(error: unknown) {
  failedQueue.forEach(({ reject }) => {
    reject(error);
  });
  failedQueue = [];
}

function retryQueue(newToken: string) {
  failedQueue.forEach(({ resolve, config }) => {
    if (config.headers) {
      config.headers.Authorization = `Bearer ${newToken}`;
    }
    resolve(apiClient(config));
  });
  failedQueue = [];
}

// Request interceptor: attach auth token and org context
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      const orgId = localStorage.getItem("org_id");
      if (orgId) {
        config.headers["X-Org-ID"] = orgId;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response) {
      const { status } = error.response;

      if (status === 401 && !originalRequest._retry) {
        // Prevent infinite retry loops
        originalRequest._retry = true;

        const refreshToken =
          typeof window !== "undefined"
            ? localStorage.getItem("refresh_token")
            : null;

        if (!refreshToken) {
          // No refresh token available, logout via store
          useAuthStore.getState().logout();
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
          return Promise.reject(error);
        }

        if (isRefreshing) {
          // Another refresh is in progress, queue this request
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject, config: originalRequest });
          });
        }

        isRefreshing = true;

        try {
          // Attempt to refresh the token
          const response = await axios.post("/api/v1/auth/refresh", {
            refresh_token: refreshToken,
          });

          const { access_token: newAccessToken, refresh_token: newRefreshToken } =
            response.data;

          // Update localStorage
          localStorage.setItem("access_token", newAccessToken);
          if (newRefreshToken) {
            localStorage.setItem("refresh_token", newRefreshToken);
          }

          // Update Zustand store
          const authState = useAuthStore.getState();
          if (authState.tokens) {
            useAuthStore.setState({
              tokens: {
                ...authState.tokens,
                access_token: newAccessToken,
                refresh_token: newRefreshToken || authState.tokens.refresh_token,
              },
              isAuthenticated: true,
            });
          }

          // Retry queued requests
          retryQueue(newAccessToken);

          // Retry the original request with the new token
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          return apiClient(originalRequest);
        } catch (refreshError) {
          // Refresh failed - clear everything via store and redirect
          processQueue(refreshError);
          useAuthStore.getState().logout();
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      if (status === 403) {
        // Forbidden - insufficient permissions
        console.error("Access denied: insufficient permissions");
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
