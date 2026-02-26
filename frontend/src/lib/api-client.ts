import axios from "axios";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

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
  (error) => {
    if (error.response) {
      const { status } = error.response;

      if (status === 401) {
        // Token expired or invalid - redirect to login
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
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
