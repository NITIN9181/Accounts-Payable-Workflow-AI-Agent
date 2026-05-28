import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import apiClient, { getAuthToken, setAuthToken, clearAuthToken } from '../lib/api'

interface User {
  id: string
  email: string
  role: 'AP_CLERK' | 'MANAGER' | 'CFO'
  department?: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User | null) => void
  refreshToken: () => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Decode JWT token to extract payload
 */
const decodeToken = (token: string): Record<string, unknown> | null => {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null

    const decoded = JSON.parse(atob(parts[1]))
    return decoded
  } catch (error) {
    console.error('Failed to decode token:', error)
    return null
  }
}

/**
 * Check if token is expired
 */
const isTokenExpired = (token: string): boolean => {
  const decoded = decodeToken(token)
  if (!decoded || !decoded.exp) return true

  const expiryTime = (decoded.exp as number) * 1000
  const currentTime = Date.now()
  const bufferTime = 60 * 1000 // 1 minute buffer
  return currentTime >= expiryTime - bufferTime
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [refreshTimeoutId, setRefreshTimeoutId] = useState<ReturnType<typeof setTimeout> | null>(null)

  /**
   * Fetch user profile from API
   */
  const fetchUserProfile = useCallback(async (authToken: string): Promise<User | null> => {
    try {
      const response = await apiClient.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      })
      return response.data.user
    } catch (error) {
      console.error('Failed to fetch user profile:', error)
      return null
    }
  }, [])

  /**
   * Refresh JWT token from the server
   */
  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const currentToken = getAuthToken()
      if (!currentToken) return false

      const response = await apiClient.post('/auth/refresh', {
        token: currentToken,
      })

      const { token: newToken, user: userData } = response.data

      // Update token in storage and API client
      setAuthToken(newToken)
      setToken(newToken)

      // Update user in context
      if (userData) {
        setUser(userData)
      }

      // Schedule next refresh
      scheduleTokenRefresh(newToken)

      return true
    } catch (error) {
      console.error('Token refresh failed:', error)
      clearAuthToken()
      setToken(null)
      setUser(null)
      return false
    }
  }, [])

  /**
   * Schedule automatic token refresh
   */
  const scheduleTokenRefresh = useCallback(
    (authToken: string) => {
      // Clear existing timeout
      if (refreshTimeoutId) {
        clearTimeout(refreshTimeoutId)
      }

      const decoded = decodeToken(authToken)
      if (!decoded || !decoded.exp) return

      const expiryTime = (decoded.exp as number) * 1000
      const currentTime = Date.now()
      const timeUntilExpiry = expiryTime - currentTime
      const refreshInterval = 5 * 60 * 1000 // 5 minutes
      const bufferTime = 60 * 1000 // 1 minute before expiry

      // Schedule refresh at refreshInterval or when token is about to expire
      const refreshDelay = Math.min(refreshInterval, Math.max(timeUntilExpiry - bufferTime, 0))

      const timeoutId = setTimeout(() => {
        refreshToken()
      }, refreshDelay)

      setRefreshTimeoutId(timeoutId)
    },
    [refreshToken, refreshTimeoutId]
  )

  /**
   * Initialize auth state from localStorage on mount
   */
  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = getAuthToken()
      if (storedToken && !isTokenExpired(storedToken)) {
        setToken(storedToken)
        const userProfile = await fetchUserProfile(storedToken)
        if (userProfile) {
          setUser(userProfile)
          scheduleTokenRefresh(storedToken)
        } else {
          // Token is valid but user profile fetch failed
          clearAuthToken()
          setToken(null)
        }
      } else if (storedToken && isTokenExpired(storedToken)) {
        // Token is expired, try to refresh
        const refreshed = await refreshToken()
        if (!refreshed) {
          clearAuthToken()
          setToken(null)
        }
      }
      setIsLoading(false)
    }

    initializeAuth()

    return () => {
      if (refreshTimeoutId) {
        clearTimeout(refreshTimeoutId)
      }
    }
  }, [fetchUserProfile, scheduleTokenRefresh, refreshToken, refreshTimeoutId])

  /**
   * Login with email and password
   */
  const login = async (email: string, password: string): Promise<void> => {
    try {
      const response = await apiClient.post('/auth/login', { email, password })
      const { token: newToken, user: userData } = response.data

      // Store token
      setAuthToken(newToken)
      setToken(newToken)
      setUser(userData)

      // Schedule token refresh
      scheduleTokenRefresh(newToken)
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : 'Login failed. Please check your credentials and try again.'
      throw new Error(errorMessage)
    }
  }

  /**
   * Logout user
   */
  const logout = (): void => {
    clearAuthToken()
    setToken(null)
    setUser(null)

    if (refreshTimeoutId) {
      clearTimeout(refreshTimeoutId)
      setRefreshTimeoutId(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        isLoading,
        login,
        logout,
        setUser,
        refreshToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
