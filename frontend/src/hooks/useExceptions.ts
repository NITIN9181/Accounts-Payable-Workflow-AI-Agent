import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../lib/api'
import { InvoiceException } from '../types'

/**
 * Fetch list of exceptions with optional filtering
 */
export const useExceptions = (filters?: {
  severity_band?: string
  resolved?: boolean
}) => {
  return useQuery({
    queryKey: ['exceptions', filters],
    queryFn: async () => {
      const response = await apiClient.get<InvoiceException[]>('/exceptions', { params: filters })
      return response.data
    },
  })
}

/**
 * Fetch single exception by ID
 */
export const useException = (exceptionId: string) => {
  return useQuery({
    queryKey: ['exceptions', exceptionId],
    queryFn: async () => {
      const response = await apiClient.get<InvoiceException>(`/exceptions/${exceptionId}`)
      return response.data
    },
    enabled: !!exceptionId,
  })
}

/**
 * Resolve exception
 */
export const useResolveException = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ exceptionId, notes }: { exceptionId: string; notes?: string }) => {
      const response = await apiClient.put<InvoiceException>(`/exceptions/${exceptionId}/resolve`, {
        notes,
      })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['exceptions', data.exception_id] })
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
    },
  })
}
