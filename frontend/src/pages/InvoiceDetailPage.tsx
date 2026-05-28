import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import apiClient from '../lib/api'
import Layout from '../components/Layout'
import { 
  FileText, 
  CheckCircle, 
  Clock, 
  History, 
  User, 
  ArrowLeft, 
  ShieldAlert 
} from 'lucide-react'

const InvoiceDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: invoice, isLoading } = useQuery({
    queryKey: ['invoice-detail', id],
    queryFn: async () => {
      const response = await apiClient.get(`/invoices/${id}`)
      return response.data
    }
  })

  const { data: auditLogs } = useQuery({
    queryKey: ['invoice-audit', id],
    queryFn: async () => {
      const response = await apiClient.get(`/invoices/${id}/audit`)
      return response.data
    },
    enabled: !!id
  })

  const { data: approvals } = useQuery({
    queryKey: ['invoice-approvals', id],
    queryFn: async () => {
      const response = await apiClient.get(`/invoices/${id}/approvals`)
      return response.data
    },
    enabled: !!id
  })

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status, notes }: { id: string, status: string, notes: string }) => {
      return apiClient.put(`/invoices/${id}/status`, { status, notes })
    },
    onSuccess: () => {
      window.location.reload()
    }
  })

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex justify-between items-center">
          <button 
            onClick={() => navigate('/')}
            className="flex items-center text-sm text-gray-500 hover:text-blue-600 transition-colors"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Dashboard
          </button>
          <div className="flex items-center space-x-3">
            <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase border ${
              invoice?.status === 'APPROVED' ? 'bg-green-100 text-green-700 border-green-200' :
              invoice?.status === 'PAID' ? 'bg-blue-100 text-blue-700 border-blue-200' :
              'bg-yellow-100 text-yellow-700 border-yellow-200'
            }`}>
              {invoice?.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Invoice Summary & Details */}
          <div className="lg:col-span-2 space-y-6">
            {/* Invoice Summary Card */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-6">
                <FileText className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Invoice Summary</h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-gray-500 uppercase font-bold">Vendor</label>
                    <div className="text-sm font-medium text-gray-900">{invoice?.vendor_name}</div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase font-bold">Invoice Number</label>
                    <div className="text-sm font-medium text-gray-900">{invoice?.invoice_number}</div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase font-bold">Total Amount (USD)</label>
                    <div className="text-lg font-bold text-gray-900">${invoice?.total_amount_usd?.toLocaleString()}</div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-gray-500 uppercase font-bold">Invoice Date</label>
                    <div className="text-sm font-medium text-gray-900">{invoice?.invoice_date}</div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase font-bold">Due Date</label>
                    <div className="text-sm font-medium text-gray-900">{invoice?.due_date}</div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase font-bold">Received At</label>
                    <div className="text-sm font-medium text-gray-900">{invoice?.received_at}</div>
                  </div>
                </div>
              </div>
              
              {/* OCR Confidence Scores */}
              <div className="mt-6 pt-6 border-t border-gray-100">
                <h3 className="text-xs font-bold text-gray-500 uppercase mb-3">Extraction Confidence</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {['invoice_number', 'vendor_name', 'total_amount', 'invoice_date'].map(field => (
                    <div key={field} className="p-2 bg-gray-50 rounded border border-gray-100">
                      <div className="text-[10px] text-gray-400 uppercase">{field.replace('_', ' ')}</div>
                      <div className="text-xs font-bold text-gray-700">
                        {(invoice?.ocr_confidence?.[field] * 100).toFixed(0)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Line Items Table */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <FileText className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Line Items</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                    <tr className="border-b border-gray-100">
                      <th className="px-4 py-2">Description</th>
                      <th className="px-4 py-2">Quantity</th>
                      <th className="px-4 py-2">Unit Price</th>
                      <th className="px-4 py-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {invoice?.line_items?.map((item: any, idx: number) => (
                      <tr key={idx}>
                        <td className="px-4 py-2 text-gray-900">{item.description}</td>
                        <td className="px-4 py-2 text-gray-600">{item.quantity}</td>
                        <td className="px-4 py-2 text-gray-600">${item.unit_price}</td>
                        <td className="px-4 py-2 text-right font-medium text-gray-900">${item.line_total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Matching Status */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Matching Status</h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg border bg-gray-50 flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-500">PO Match</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    invoice?.match_status === 'PO_MATCHED' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {invoice?.match_status || 'N/A'}
                  </span>
                </div>
                <div className="p-4 rounded-lg border bg-gray-50 flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-500">Receipt Match</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    invoice?.receipt_status === 'RECEIPT_MATCHED' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {invoice?.receipt_status || 'N/A'}
                  </span>
                </div>
                <div className="p-4 rounded-lg border bg-gray-50 flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-500">Three-Way Match</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    invoice?.three_way_match === 'SUCCESS' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {invoice?.three_way_match || 'N/A'}
                  </span>
                </div>
              </div>
            </div>

            {/* Exceptions List */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <ShieldAlert className="w-5 h-5 text-red-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Exceptions</h2>
              </div>
              <div className="space-y-3">
                {invoice?.exceptions?.length === 0 ? (
                  <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                    No exceptions detected for this invoice.
                  </div>
                ) : (
                  invoice?.exceptions?.map((exc: any, idx: number) => (
                    <div key={idx} className="p-4 rounded-lg border bg-gray-50 hover:bg-white transition-colors cursor-pointer group"
                      onClick={() => navigate(`/exceptions/${exc.exception_id}`)}>
                      <div className="flex justify-between items-start mb-2">
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                          exc.severity_band === 'CRITICAL' ? 'bg-red-100 text-red-700 border-red-200' :
                          exc.severity_band === 'HIGH' ? 'bg-orange-100 text-orange-700 border-orange-200' :
                          'bg-yellow-100 text-yellow-700 border-yellow-200'
                        }`}>
                          {exc.severity_band}
                        </span>
                        <span className="text-xs text-gray-400">{exc.created_at}</span>
                      </div>
                      <div className="font-medium text-sm text-gray-900 group-hover:text-blue-600 transition-colors">
                        {exc.exception_type}
                      </div>
                      <div className="text-xs text-gray-600 line-clamp-2 italic">
                        {exc.llm_explanation}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Column: History & Audit */}
          <div className="space-y-6">
            {/* Approvals History */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <User className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Approvals History</h2>
              </div>
              <div className="space-y-4">
                {approvals?.length === 0 ? (
                  <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                    No approval records found.
                  </div>
                ) : (
                  approvals?.map((app: any, idx: number) => (
                  <div key={idx} className="flex items-start space-x-3 p-3 rounded-lg border border-gray-100 bg-gray-50">
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${
                      app.action === 'APPROVED' ? 'bg-green-500' : 
                      app.action === 'REJECTED' ? 'bg-red-500' : 'bg-yellow-500'
                    }`} />
                    <div className="flex-1">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-bold text-gray-900">{app.approver_id}</span>
                        <span className="text-[10px] text-gray-400">{app.created_at}</span>
                      </div>
                      <div className="text-xs text-gray-600">{app.action} - {app.notes}</div>
                    </div>
                  </div>
                ))
                )}
              </div>
            </div>

            {/* Audit Trail */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <History className="w-5 h-5 text-gray-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Audit Trail</h2>
              </div>
              <div className="space-y-4">
                {auditLogs?.length === 0 ? (
                  <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                    No audit logs found.
                  </div>
                ) : (
                  auditLogs?.map((log: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-lg border border-gray-100 bg-gray-50 hover:bg-white transition-colors cursor-pointer group">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-bold text-gray-900">{log.action_type}</span>
                        <span className="text-[10px] text-gray-400">{log.created_at}</span>
                      </div>
                      <div className="text-[10px] text-gray-500 italic">
                        Actor: {log.actor_id} ({log.actor_type})
                      </div>
                      <details className="mt-2">
                        <summary className="text-[10px] text-blue-600 cursor-pointer hover:underline">
                          View State Change
                        </summary>
                        <pre className="mt-2 p-2 bg-gray-100 rounded text-[10px] overflow-auto max-h-32">
                          {JSON.stringify(log.after_state, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Sticky Action Bar */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 sticky bottom-0">
              <div className="flex items-center mb-4">
                <Clock className="w-5 h-5 text-gray-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Quick Action</h2>
              </div>
              <div className="space-y-4">
                <div className="flex space-x-3">
                  <button 
                    onClick={() => updateStatusMutation.mutate({ id: id!, status: 'APPROVED', notes: 'Quick approve' })}
                    className="flex-1 py-2 px-4 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors"
                  >
                    Approve
                  </button>
                  <button 
                    onClick={() => updateStatusMutation.mutate({ id: id!, status: 'REJECTED', notes: 'Quick reject' })}
                    className="flex-1 py-2 px-4 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 transition-colors"
                  >
                    Reject
                  </button>
                </div>
                <div className="text-center text-[10px] text-gray-400 italic">
                  Full resolution available in Exception Detail page
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}

export default InvoiceDetailPage