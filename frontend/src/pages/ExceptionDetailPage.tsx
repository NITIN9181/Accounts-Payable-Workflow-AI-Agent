import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import apiClient from '../lib/api'
import Layout from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { useRole } from '../hooks/useRole'
import { 
  AlertCircle, 
  CheckCircle, 
  ArrowLeft, 
  FileText, 
  Info, 
  Clock, 
  ShieldAlert,
  TrendingUp
} from 'lucide-react'

const ExceptionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()  // this is the exception_id
  const navigate = useNavigate()
  const { user } = useAuth()
  const { canApprove, isClerk, isCFO, roleLabel } = useRole()
  const [action, setAction] = useState('APPROVED')
  const [notes, setNotes] = useState('')

  // Fetch the exception
  const { data: exception, isLoading: exceptionLoading } = useQuery({
    queryKey: ['exception', id],
    queryFn: async () => {
      const response = await apiClient.get(`/exceptions/${id}`)
      return response.data
    },
    enabled: !!id,
  })

  // Fetch the invoice using the invoice_id from the exception (not the exception id)
  const { data: invoice, isLoading: invoiceLoading } = useQuery({
    queryKey: ['invoice', exception?.invoice_id],
    queryFn: async () => {
      const response = await apiClient.get(`/invoices/${exception.invoice_id}`)
      return response.data
    },
    enabled: !!exception?.invoice_id,
  })

  // Fetch the approval record for this invoice so we have the approval_id
  const { data: approvalData } = useQuery({
    queryKey: ['invoice-approvals', exception?.invoice_id],
    queryFn: async () => {
      const response = await apiClient.get(`/approvals/invoice/${exception.invoice_id}`)
      return response.data  // array of approvals
    },
    enabled: !!exception?.invoice_id,
  })

  // The pending approval for this exception (most recent PENDING one)
  const pendingApproval = Array.isArray(approvalData)
    ? approvalData.find((a: any) => a.status === 'PENDING') ?? approvalData[0]
    : null

  const { data: vendorBaseline } = useQuery({
    queryKey: ['vendor-baseline', exception?.vendor_key],
    queryFn: async () => {
      const response = await apiClient.get(`/vendors/${exception?.vendor_key}/baseline`)
      return response.data
    },
    enabled: !!exception?.vendor_key,
  })

  // Fix: use POST (not PUT) and send the approval_id, not the exception id
  const resolveMutation = useMutation({
    mutationFn: async ({ approvalId, action, notes }: { approvalId: string, action: string, notes: string }) => {
      return apiClient.post(
        `/approvals/${approvalId}/action?action=${encodeURIComponent(action)}&approver_id=${encodeURIComponent(user?.id ?? '')}&approver_role=${encodeURIComponent(user?.role ?? '')}`,
        { notes }
      )
    },
    onSuccess: () => {
      navigate('/')
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail ?? 'Failed to submit decision. Please try again.')
    },
  })

  if (exceptionLoading || invoiceLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    )
  }

  if (!exception) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <p className="text-gray-500 mb-4">Exception not found.</p>
          <button onClick={() => navigate('/')} className="text-blue-600 hover:underline text-sm">← Back to Dashboard</button>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="space-y-6">
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
              exception?.severity_band === 'CRITICAL' ? 'bg-red-100 text-red-700 border-red-200' :
              exception?.severity_band === 'HIGH' ? 'bg-orange-100 text-orange-700 border-orange-200' :
              'bg-yellow-100 text-yellow-700 border-yellow-200'
            }`}>
              {exception?.severity_band} Severity
            </span>
            {invoice && (
              <span className="text-sm text-gray-600 font-medium">
                {invoice.vendor_name} · #{invoice.invoice_number} · ${Number(invoice.total_amount_usd || 0).toLocaleString()}
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column: Document Viewer */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex flex-col h-[calc(100vh-200px)]">
            <div className="p-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium text-gray-700">Invoice Document</span>
              </div>
              <div className="flex items-center space-x-2">
                <button className="p-1 hover:bg-gray-200 rounded transition-colors text-gray-600">
                  <span className="text-xs">Zoom In</span>
                </button>
                <button className="p-1 hover:bg-gray-200 rounded transition-colors text-gray-600">
                  <span className="text-xs">Zoom Out</span>
                </button>
              </div>
            </div>
            <div className="flex-1 bg-gray-200 relative overflow-auto">
              {/* PDF Viewer Placeholder */}
              <div className="absolute inset-0 flex items-center justify-center text-gray-500 italic text-sm p-8 text-center">
                PDF Viewer Integration: 
                <br />
                Loading document from Supabase Storage...
                <br />
                <span className="text-xs mt-2 block">File: {invoice?.file_path}</span>
              </div>
              <iframe 
                src={`/api/v1/invoices/${id}/pdf`} 
                className="w-full h-full border-none"
                title="Invoice PDF"
              />
            </div>
          </div>

          {/* Right Column: Analysis Sections */}
          <div className="space-y-6 overflow-y-auto h-[calc(100vh-200px)] pr-2">
            {/* PO Comparison Table */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <ShieldAlert className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">PO Comparison</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                    <tr>
                      <th className="px-4 py-2">Item</th>
                      <th className="px-4 py-2">Invoice Qty</th>
                      <th className="px-4 py-2">PO Qty</th>
                      <th className="px-4 py-2">Variance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {invoice?.line_items?.map((item: any, idx: number) => (
                      <tr key={idx}>
                        <td className="px-4 py-2 font-medium text-gray-900">{item.description}</td>
                        <td className="px-4 py-2">{item.quantity}</td>
                        <td className="px-4 py-2">{item.po_quantity || 'N/A'}</td>
                        <td className={`px-4 py-2 font-bold ${Math.abs(item.quantity - (item.po_quantity || 0)) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                          {item.quantity - (item.po_quantity || 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Receipt Status */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Receipt Status</h2>
              </div>
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg border border-green-100">
                <div className="text-sm text-green-800">
                  All invoiced quantities have been received.
                </div>
                <div className="text-green-600 font-bold">MATCHED</div>
              </div>
            </div>

            {/* Vendor Baseline Chart Placeholder */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <TrendingUp className="w-5 h-5 text-purple-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Vendor Baseline</h2>
              </div>
              <div className="h-40 w-full bg-gray-50 rounded-lg flex items-center justify-center text-gray-400 italic text-sm">
                Bar chart of last 20 transactions with anomalous bar highlighted in red
              </div>
            </div>

            {/* LLM Explanation Card */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center mb-4">
                <Info className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">AI Analysis</h2>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-100 relative">
                <div className="text-sm text-blue-800 leading-relaxed italic">
                  {exception?.llm_explanation || (exception?.llm_explanation_ready ? 'Generating explanation...' : 'Waiting for LLM...')}
                </div>
                {exception?.llm_explanation_fallback && (
                  <div className="mt-3 text-[10px] text-blue-600 font-medium uppercase tracking-wider">
                    This explanation was generated from a template
                  </div>
                )}
              </div>
            </div>

            {/* Action Panel */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 sticky bottom-0">
              <div className="flex items-center mb-4">
                <Clock className="w-5 h-5 text-gray-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Resolution Action</h2>
              </div>

              {/* Role authority notice */}
              {exception && !canApprove(exception.total_amount) && (
                <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-800 flex items-start">
                  <AlertCircle className="w-4 h-4 mr-2 mt-0.5 shrink-0" />
                  This invoice (${exception.total_amount?.toLocaleString()}) exceeds your approval authority as {roleLabel()}. 
                  You can only escalate it.
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Decision
                  </label>
                  <select 
                    value={action} 
                    onChange={(e) => setAction(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  >
                    {/* Approve only available if within authority */}
                    {exception && canApprove(exception.total_amount) && (
                      <option value="APPROVED">Approve</option>
                    )}
                    <option value="REJECTED">Reject</option>
                    {/* Clerks and Managers can escalate; CFO escalates to external */}
                    {!isCFO && <option value="ESCALATED">Escalate to {isClerk ? 'Manager' : 'CFO'}</option>}
                    <option value="HELD">Hold for Review</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Notes
                  </label>
                  <textarea 
                    value={notes} 
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Add resolution notes..."
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-24"
                  />
                </div>
                <div className="flex space-x-3">
                  <button 
                    onClick={() => {
                      if (!pendingApproval) {
                        alert('No pending approval found for this exception.')
                        return
                      }
                      resolveMutation.mutate({ approvalId: pendingApproval.approval_id, action, notes })
                    }}
                    disabled={resolveMutation.isPending}
                    className="flex-1 py-2 px-4 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
                  >
                    {resolveMutation.isPending ? 'Processing...' : 'Submit Decision'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}

export default ExceptionDetailPage