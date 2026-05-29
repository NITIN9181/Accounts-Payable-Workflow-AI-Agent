import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const JWT_STORAGE_KEY = import.meta.env.VITE_JWT_STORAGE_KEY || 'ap_workflow_token'

/**
 * Create axios instance with base configuration
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Request interceptor: Add JWT token to Authorization header
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(JWT_STORAGE_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

/**
 * Response interceptor: Handle token expiration and errors
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Handle 401 Unauthorized - token expired or invalid
    if (error.response?.status === 401) {
      localStorage.removeItem(JWT_STORAGE_KEY)
      window.location.href = '/login'
    }

    // Handle 403 Forbidden - insufficient permissions
    if (error.response?.status === 403) {
      console.error('Access denied:', error.response.data)
    }

    // Handle 500 Server Error
    if (error.response?.status === 500) {
      console.error('Server error:', error.response.data)
    }

    return Promise.reject(error)
  }
)

/**
 * Set JWT token in localStorage and update Authorization header
 */
export const setAuthToken = (token: string): void => {
  localStorage.setItem(JWT_STORAGE_KEY, token)
  apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

/**
 * Clear JWT token from localStorage and remove Authorization header
 */
export const clearAuthToken = (): void => {
  localStorage.removeItem(JWT_STORAGE_KEY)
  delete apiClient.defaults.headers.common['Authorization']
}

/**
 * Get current JWT token from localStorage
 */
export const getAuthToken = (): string | null => {
  return localStorage.getItem(JWT_STORAGE_KEY)
}

export default apiClient
