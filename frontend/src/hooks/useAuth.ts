import { useCallback, useEffect, useRef } from 'react'
import { useAuth as useAuthContext } from '../context/AuthContext'
import apiClient, { setAuthToken, clearAuthToken, getAuthToken } from '../lib/api'

const TOKEN_REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes
const TOKEN_EXPIRY_BUFFER = 60 * 1000 // 1 minute before actual expiry

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
  return currentTime >= expiryTime - TOKEN_EXPIRY_BUFFER
}

/**
 * useAuth hook for JWT token management with automatic refresh
 * Handles token storage, retrieval, and refresh logic
 */
export const useAuthTokenManagement = () => {
  const { setUser } = useAuthContext()
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

      const { token: newToken, user } = response.data

      // Update token in storage and API client
      setAuthToken(newToken)

      // Update user in context
      if (user) {
        setUser(user)
      }

      // Schedule next refresh
      scheduleTokenRefresh(newToken)

      return true
    } catch (error) {
      console.error('Token refresh failed:', error)
      clearAuthToken()
      return false
    }
  }, [setUser])

  /**
   * Schedule automatic token refresh
   */
  const scheduleTokenRefresh = useCallback(
    (token: string) => {
      // Clear existing timeout
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }

      const decoded = decodeToken(token)
      if (!decoded || !decoded.exp) return

      const expiryTime = (decoded.exp as number) * 1000
      const currentTime = Date.now()
      const timeUntilExpiry = expiryTime - currentTime

      // Schedule refresh at TOKEN_REFRESH_INTERVAL or when token is about to expire
      const refreshDelay = Math.min(TOKEN_REFRESH_INTERVAL, Math.max(timeUntilExpiry - TOKEN_EXPIRY_BUFFER, 0))

      refreshTimeoutRef.current = setTimeout(() => {
        refreshToken()
      }, refreshDelay)
    },
    [refreshToken]
  )

  /**
   * Initialize token refresh on mount
   */
  useEffect(() => {
    const token = getAuthToken()
    if (token && !isTokenExpired(token)) {
      scheduleTokenRefresh(token)
    }

    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
    }
  }, [scheduleTokenRefresh])

  return {
    refreshToken,
    scheduleTokenRefresh,
    isTokenExpired,
  }
}

export default useAuthTokenManagement
