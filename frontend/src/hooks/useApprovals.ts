import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api'
import { Approval } from '@/types'

/**
 * Fetch list of approvals with optional filtering
 */
export const useApprovals = (filters?: {
  queue?: string
  status?: string
}) => {
  return useQuery({
    queryKey: ['approvals', filters],
    queryFn: async () => {
      const response = await apiClient.get<Approval[]>('/approvals', { params: filters })
      return response.data
    },
  })
}

/**
 * Fetch single approval by ID
 */
export const useApproval = (approvalId: string) => {
  return useQuery({
    queryKey: ['approvals', approvalId],
    queryFn: async () => {
      const response = await apiClient.get<Approval>(`/approvals/${approvalId}`)
      return response.data
    },
    enabled: !!approvalId,
  })
}

/**
 * Take approval action (approve, reject, escalate)
 */
export const useApprovalAction = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      approvalId,
      action,
      notes,
    }: {
      approvalId: string
      action: 'APPROVED' | 'REJECTED' | 'ESCALATED'
      notes?: string
    }) => {
      const response = await apiClient.post<Approval>(`/approvals/${approvalId}/action`, {
        action,
        notes,
      })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['approvals', data.approval_id] })
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })
}
