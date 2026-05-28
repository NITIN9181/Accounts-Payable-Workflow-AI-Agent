import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../lib/api'
import { Invoice } from '../types'

/**
 * Fetch list of invoices with optional filtering
 */
export const useInvoices = (filters?: {
  status?: string
  vendor_key?: string
  startDate?: string
  endDate?: string
}) => {
  return useQuery({
    queryKey: ['invoices', filters],
    queryFn: async () => {
      const response = await apiClient.get<Invoice[]>('/invoices', { params: filters })
      return response.data
    },
  })
}

/**
 * Fetch single invoice by ID
 */
export const useInvoice = (invoiceId: string) => {
  return useQuery({
    queryKey: ['invoices', invoiceId],
    queryFn: async () => {
      const response = await apiClient.get<Invoice>(`/invoices/${invoiceId}`)
      return response.data
    },
    enabled: !!invoiceId,
  })
}

/**
 * Upload invoice file
 */
export const useUploadInvoice = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await apiClient.post<Invoice>('/invoices/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })
}

/**
 * Create manual invoice entry
 */
export const useCreateManualInvoice = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: {
      vendor_name: string
      invoice_number: string
      total_amount: number
      invoice_date: string
      due_date: string
      po_reference?: string
    }) => {
      const response = await apiClient.post<Invoice>('/invoices/manual', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })
}

/**
 * Update invoice status
 */
export const useUpdateInvoiceStatus = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ invoiceId, status }: { invoiceId: string; status: string }) => {
      const response = await apiClient.put<Invoice>(`/invoices/${invoiceId}/status`, { status })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['invoices', data.invoice_id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })
}
