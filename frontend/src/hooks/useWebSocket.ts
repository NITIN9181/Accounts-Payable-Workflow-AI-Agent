import { useEffect, useRef, useCallback } from 'react'
import { WebSocketEvent } from '@/types'
import { getAuthToken } from '@/lib/api'

type WebSocketEventHandler = (event: WebSocketEvent) => void

/**
 * Custom hook for WebSocket connection management
 */
export const useWebSocket = (onMessage: WebSocketEventHandler) => {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000

  const connect = useCallback(() => {
    const token = getAuthToken()
    if (!token) {
      console.warn('No auth token available for WebSocket connection')
      return
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
    const url = `${wsUrl}/stream?token=${token}`

    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
        reconnectAttemptsRef.current = 0
      }

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketEvent
          onMessage(data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected')
        // Attempt to reconnect
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Attempting to reconnect (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`)
            connect()
          }, reconnectDelay)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
  }, [onMessage])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  useEffect(() => {
    const enableWebSocket = import.meta.env.VITE_ENABLE_WEBSOCKET !== 'false'
    if (enableWebSocket) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return { send, disconnect }
}
