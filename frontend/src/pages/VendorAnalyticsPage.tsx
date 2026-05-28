import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import apiClient from '../lib/api'
import Layout from '../components/Layout'
import { 
  TrendingUp, 
  BarChart3, 
  Clock, 
  AlertTriangle, 
  FileText, 
  ArrowUpRight 
} from 'lucide-react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  Cell 
} from 'recharts'

const VendorAnalyticsPage: React.FC = () => {
  const { vendor_key } = useParams<{ vendor_key: string }>()
  const navigate = useNavigate()

  const { data: vendorData, isLoading } = useQuery({
    queryKey: ['vendor-analytics', vendor_key],
    queryFn: async () => {
      const response = await apiClient.get(`/vendors/${vendor_key}/analytics`)
      return response.data
    },
    enabled: !!vendor_key
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
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{vendorData?.vendor_name} Analytics</h1>
            <p className="text-gray-500">Vendor key: {vendor_key}</p>
          </div>
          <div className="flex items-center space-x-3">
            <div className={`px-3 py-1 rounded-full text-xs font-bold uppercase border ${
              vendorData?.auto_approve_enabled ? 'bg-green-100 text-green-700 border-green-200' : 'bg-gray-100 text-gray-700 border-gray-200'
            }`}>
              {vendorData?.auto_approve_enabled ? 'Auto-Approve Enabled' : 'Manual Review Only'}
            </div>
          </div>
        </div>

        {/* Top Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="text-xs font-bold text-gray-500 uppercase mb-1">Total Spend (30d)</div>
            <div className="text-2xl font-bold text-gray-900">${vendorData?.total_spend_30d?.toLocaleString()}</div>
            <div className="text-xs text-green-600 flex items-center mt-1">
              <ArrowUpRight className="w-3 h-3 mr-1" />
              +4.2% vs last month
            </div>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="text-xs font-bold text-gray-500 uppercase mb-1">Total Spend (90d)</div>
            <div className="text-2xl font-bold text-gray-900">${vendorData?.total_spend_90d?.toLocaleString()}</div>
            <div className="text-xs text-gray-400 flex items-center mt-1">
              Stable trend
            </div>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="text-xs font-bold text-gray-500 uppercase mb-1">Txn Count (30d)</div>
            <div className="text-2xl font-bold text-gray-900">{vendorData?.transaction_count_30d}</div>
            <div className="text-xs text-gray-400 flex items-center mt-1">
              Avg 0.8 invoices/day
            </div>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="text-xs font-bold text-gray-500 uppercase mb-1">Anomaly Rate</div>
            <div className="text-2xl font-bold text-red-600">{vendorData?.anomaly_rate}%</div>
            <div className="text-xs text-red-500 flex items-center mt-1">
              <AlertTriangle className="w-3 h-3 mr-1" />
              High risk vendor
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Spend Trend Chart */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center mb-6">
              <TrendingUp className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Spend Trend (12 Months)</h2>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={vendorData?.spend_trend}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                  <XAxis dataKey="month" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Line type="monotone" dataKey="amount" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Invoice Amount Distribution */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center mb-6">
              <BarChart3 className="w-5 h-5 text-purple-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Amount Distribution</h2>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={vendorData?.amount_distribution}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                  <XAxis dataKey="bin" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Bar dataKey="count" fill="#8b5cf6">
                    {vendorData?.amount_distribution?.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.is_anomalous ? '#ef4444' : '#8b5cf6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Payment Velocity Chart */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 lg:col-span-1">
            <div className="flex items-center mb-4">
              <Clock className="w-5 h-5 text-orange-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Payment Velocity</h2>
            </div>
            <div className="h-64 w-full bg-gray-50 rounded-lg flex items-center justify-center text-gray-400 italic text-sm text-center p-4">
              Box plot of days_to_pay for the past 90 days
              <br />
              (Median, Quartiles, Outliers)
            </div>
            <div className="mt-4 p-3 bg-orange-50 rounded-lg border border-orange-100 flex items-center justify-between">
              <span className="text-xs text-orange-800 font-medium">Avg Days to Pay:</span>
              <span className="text-sm font-bold text-orange-900">{vendorData?.avg_days_to_pay_90d} days</span>
            </div>
          </div>

          {/* Anomaly History */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 lg:col-span-2">
            <div className="flex items-center mb-4">
              <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Anomaly History (90d)</h2>
            </div>
            <div className="space-y-3">
              {vendorData?.anomalies?.length === 0 ? (
                <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                  No anomalies detected for this vendor in the last 90 days.
                </div>
              ) : (
                vendorData?.anomalies?.map((anomaly: any, idx: number) => (
                  <div key={idx} className="p-4 rounded-lg border bg-gray-50 hover:bg-white transition-colors cursor-pointer group flex justify-between items-center"
                    onClick={() => window.location.href = `/exceptions/${anomaly.exception_id}`}>
                    <div className="flex items-center space-x-3">
                      <div className={`w-2 h-2 rounded-full ${
                        anomaly.severity_band === 'CRITICAL' ? 'bg-red-600' : 
                        anomaly.severity_band === 'HIGH' ? 'bg-orange-500' : 'bg-yellow-500'
                      }`} />
                      <div>
                        <div className="text-sm font-medium text-gray-900 group-hover:text-blue-600 transition-colors">
                          {anomaly.exception_type}
                        </div>
                        <div className="text-xs text-gray-500">
                          {anomaly.invoice_number} • {anomaly.invoice_date}
                        </div>
                      </div>
                    </div>
                    <div className="text-xs font-bold text-gray-400">
                      ${anomaly.amount}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Recent Invoices Table */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center mb-4">
            <FileText className="w-5 h-5 text-blue-600 mr-2" />
            <h2 className="text-lg font-bold text-gray-900">Recent Invoices</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                <tr className="border-b border-gray-100">
                  <th className="px-4 py-2">Invoice #</th>
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Amount (USD)</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Exceptions</th>
                  <th className="px-4 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {vendorData?.recent_invoices?.map((inv: any, idx: number) => (
                  <tr key={idx} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2 font-medium text-gray-900">{inv.invoice_number}</td>
                    <td className="px-4 py-2 text-gray-600">{inv.invoice_date}</td>
                    <td className="px-4 py-2 text-gray-600">${inv.total_amount_usd?.toLocaleString()}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                        inv.status === 'APPROVED' ? 'bg-green-100 text-green-700 border-green-200' :
                        inv.status === 'PAID' ? 'bg-blue-100 text-blue-700 border-blue-200' :
                        'bg-yellow-100 text-yellow-700 border-yellow-200'
                      }`}>
                        {inv.status}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center space-x-1">
                        <span className="text-xs text-gray-600">{inv.exception_count}</span>
                        {inv.exception_count > 0 && <AlertTriangle className="w-3 h-3 text-red-500" />}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button 
                        onClick={() => navigate(`/invoices/${inv.invoice_id}`)}
                        className="text-blue-600 hover:text-blue-800 text-xs font-bold transition-colors"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  )
}

export default VendorAnalyticsPage