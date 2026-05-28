import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import apiClient from '../lib/api'
import Layout from '../components/Layout'
import { 
  Calendar, 
  DollarSign, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  ArrowRight, 
  TrendingUp 
} from 'lucide-react'
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  AreaChart, 
  Area 
} from 'recharts'

const PaymentSchedulePage: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const { data: schedule, isLoading } = useQuery({
    queryKey: ['payment-schedule'],
    queryFn: async () => {
      const response = await apiClient.get('/payments/schedule')
      return response.data
    }
  })

  const { data: cashFlow } = useQuery({
    queryKey: ['payment-cashflow'],
    queryFn: async () => {
      const response = await apiClient.get('/payments/cashflow-forecast')
      return response.data
    }
  })

  const captureDiscountMutation = useMutation({
    mutationFn: async ({ invoiceId }: { invoiceId: string }) => {
      return apiClient.post(`/payments/capture-discount`, { invoiceId })
    },
    onSuccess: () => {
      window.location.reload()
    }
  })

  const rescheduleMutation = useMutation({
    mutationFn: async ({ invoiceId, newDate }: { invoiceId: string, newDate: string }) => {
      return apiClient.put(`/payments/reschedule`, { invoiceId, newDate })
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
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Payment Schedule</h1>
            <p className="text-gray-500">Cash flow planning and discount optimization</p>
          </div>
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-white rounded-lg border border-gray-200 shadow-sm flex items-center space-x-2">
              <DollarSign className="w-4 h-4 text-green-600" />
              <span className="text-sm font-bold text-gray-900">
                Total Scheduled: ${schedule?.total_outflow?.toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Cash Flow Forecast Chart */}
          <div className="lg:col-span-2 bg-white rounded-xl p-6 shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center">
                <TrendingUp className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-bold text-gray-900">Cash Flow Forecast (30 Days)</h2>
              </div>
              <div className="flex items-center space-x-4 text-xs text-gray-500">
                <div className="flex items-center">
                  <div className="w-3 h-3 bg-blue-500 rounded-full mr-1"></div>
                  <span>Projected Outflow</span>
                </div>
                <div className="flex items-center">
                  <div className="w-3 h-3 bg-red-500 rounded-full mr-1"></div>
                  <span>Safety Threshold ($50K)</span>
                </div>
              </div>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={cashFlow}>
                  <defs>
                    <linearGradient id="colorOutflow" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                  <XAxis dataKey="date" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="amount" 
                    stroke="#3b82f6" 
                    fillOpacity={1} 
                    fill="url(#colorOutflow)" 
                    strokeWidth={2}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="threshold" 
                    stroke="#ef4444" 
                    strokeDasharray="5 5" 
                    strokeWidth={2} 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Discount Opportunities */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
            <div className="flex items-center mb-6">
              <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Discount Opportunities</h2>
            </div>
            <div className="space-y-4 overflow-y-auto max-h-[400px] pr-2">
              {schedule?.discounts?.length === 0 ? (
                <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                  No available discounts
                </div>
              ) : (
                schedule?.discounts?.map((disc: any, idx: number) => (
                  <div key={idx} className="p-4 rounded-lg border bg-gray-50 hover:bg-white transition-all cursor-pointer group relative">
                    <div className="flex justify-between items-start mb-2">
                      <div className="font-medium text-sm text-gray-900">{disc.vendor_name}</div>
                      <div className="text-xs font-bold text-green-600">${disc.amount}</div>
                    </div>
                    <div className="text-xs text-gray-500 mb-3 flex items-center">
                      <Clock className="w-3 h-3 mr-1" />
                      Deadline: {disc.deadline} ({disc.days_until_deadline} days left)
                    </div>
                    <button 
                      onClick={() => captureDiscountMutation.mutate({ invoiceId: disc.invoice_id })}
                      className="w-full py-1.5 px-3 bg-green-600 text-white text-xs font-bold rounded hover:bg-green-700 transition-colors"
                    >
                      Capture Discount
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Calendar View / Scheduled Payments */}
          <div className="lg:col-span-2 bg-white rounded-xl p-6 shadow-sm border border-gray-200">
            <div className="flex items-center mb-6">
              <Calendar className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Scheduled Payments</h2>
            </div>
            <div className="space-y-6">
              {schedule?.batches?.length === 0 ? (
                <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                  No payments scheduled
                </div>
              ) : (
                schedule?.batches?.map((batch: any, idx: number) => (
                  <div key={idx} className="border rounded-lg overflow-hidden">
                    <div className="p-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
                      <div className="flex items-center font-bold text-sm text-gray-700">
                        <Calendar className="w-4 h-4 mr-2" />
                        {batch.date}
                      </div>
                      <div className="text-sm font-bold text-gray-900">
                        Total: ${batch.total_amount?.toLocaleString()}
                      </div>
                    </div>
                    <div className="divide-y divide-gray-100">
                      {batch.invoices.map((inv: any, invIdx: number) => (
                        <div key={invIdx} className="p-4 flex justify-between items-center hover:bg-gray-50 transition-colors">
                          <div className="flex items-center space-x-3">
                            <div className="text-sm font-medium text-gray-900">{inv.vendor_name}</div>
                            <div className="text-xs text-gray-500">{inv.invoice_number}</div>
                          </div>
                          <div className="flex items-center space-x-4">
                            <div className="text-sm font-bold text-gray-900">${inv.amount?.toLocaleString()}</div>
                            <button 
                              onClick={() => {
                                const newDate = prompt('Enter new payment date (YYYY-MM-DD):')
                                if (newDate) rescheduleMutation.mutate({ invoiceId: inv.invoice_id, newDate })
                              }}
                              className="text-xs text-blue-600 hover:text-blue-800 font-bold transition-colors"
                            >
                              Reschedule
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Risk Alerts */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
            <div className="flex items-center mb-6">
              <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
              <h2 className="text-lg font-bold text-gray-900">Risk Alerts</h2>
            </div>
            <div className="space-y-4">
              {schedule?.alerts?.length === 0 ? (
                <div className="text-sm text-gray-500 italic p-4 bg-gray-50 rounded-lg text-center">
                  No critical risks detected
                </div>
              ) : (
                schedule?.alerts?.map((alert: any, idx: number) => (
                  <div key={idx} className="p-4 rounded-lg border bg-red-50 border-red-100 flex items-start space-x-3">
                    <AlertTriangle className="w-4 h-4 text-red-600 mt-1 shrink-0" />
                    <div className="text-xs text-red-800 leading-relaxed">
                      {alert.message}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}

export default PaymentSchedulePage