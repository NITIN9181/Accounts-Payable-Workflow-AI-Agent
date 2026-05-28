import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import apiClient from '../lib/api'
import Layout from '../components/Layout'
import { useRole } from '../hooks/useRole'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { AlertCircle, CheckCircle, Clock, DollarSign, FileText, TrendingUp, Users } from 'lucide-react'

interface KPICardProps {
  title: string
  value: string | number
  trend?: string
  icon: React.ReactNode
  color: string
}

const KPICard: React.FC<KPICardProps> = ({ title, value, trend, icon, color }) => (
  <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 flex flex-col">
    <div className="flex justify-between items-start mb-4">
      <div className={`p-2 rounded-lg ${color}`}>{icon}</div>
      {trend && (
        <span className="text-xs font-medium px-2 py-1 rounded-full bg-green-100 text-green-700">
          {trend}
        </span>
      )}
    </div>
    <div className="text-sm text-gray-500 font-medium">{title}</div>
    <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
  </div>
)

interface ExceptionEvent {
  exception_id: string
  invoice_id: string
  vendor_name: string
  total_amount: number
  final_severity: number
  severity_band: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  exception_type: string
  llm_explanation: string
  llm_explanation_ready: boolean
}

const DashboardPage: React.FC = () => {
  const [events, setEvents] = useState<ExceptionEvent[]>([])
  const { roleLabel, myQueue, isClerk, isManager, isCFO, CLERK_THRESHOLD, MANAGER_THRESHOLD } = useRole()

  // Fetch KPIs
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ['dashboard-kpis'],
    queryFn: async () => {
      const response = await apiClient.get('/metrics/dashboard')
      return response.data
    }
  })

  // Fetch Cash Flow Data — only for Manager and CFO
  const { data: cashFlowData, isLoading: cashFlowLoading } = useQuery({
    queryKey: ['dashboard-cashflow'],
    queryFn: async () => {
      const response = await apiClient.get('/metrics/cashflow-forecast')
      return response.data
    },
    enabled: !isClerk,
  })

  // Fetch this role's approval queue
  const { data: queueData } = useQuery({
    queryKey: ['approval-queue', myQueue()],
    queryFn: async () => {
      const response = await apiClient.get(`/approvals/queue/${myQueue()}?limit=10`)
      return response.data
    },
  })

  // WebSocket for real-time exceptions
  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/ws/stream?token=${localStorage.getItem('ap_workflow_token')}`)
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'EXCEPTION_CREATED') {
        setEvents(prev => [data.payload, ...prev].slice(0, 10))
      }
    }

    return () => ws.close()
  }, [])

  const getSeverityColor = (band: string) => {
    switch (band) {
      case 'CRITICAL': return 'bg-red-100 text-red-700 border-red-200'
      case 'HIGH': return 'bg-orange-100 text-orange-700 border-orange-200'
      case 'MEDIUM': return 'bg-yellow-100 text-yellow-700 border-yellow-200'
      case 'LOW': return 'bg-blue-100 text-blue-700 border-blue-200'
      default: return 'bg-gray-100 text-gray-700 border-gray-200'
    }
  }

  if (kpisLoading || (!isClerk && cashFlowLoading)) {
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
            <h1 className="text-2xl font-bold text-gray-900">Financial Dashboard</h1>
            <p className="text-gray-500">
              {isClerk && 'Review and process incoming invoices'}
              {isManager && 'Manage escalated invoices and team performance'}
              {isCFO && 'Real-time AP performance and cash flow monitoring'}
            </p>
          </div>
          <div className="text-sm text-gray-500 flex items-center">
            <Clock className="w-4 h-4 mr-2" />
            Last updated: {new Date().toLocaleTimeString()}
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <KPICard 
            title="Invoices Processed (24h)" 
            value={kpis?.invoices_processed_24h || 0} 
            trend="+12%" 
            icon={<FileText className="w-5 h-5 text-blue-600" />} 
            color="bg-blue-50" 
          />
          <KPICard 
            title="Touchless Rate (7d)" 
            value={`${kpis?.touchless_rate_7d || 0}%`} 
            trend="+2.4%" 
            icon={<CheckCircle className="w-5 h-5 text-green-600" />} 
            color="bg-green-50" 
          />
          <KPICard 
            title="Avg Cycle Time" 
            value={`${kpis?.avg_cycle_time_hours || 0}h`} 
            trend="-1.2h" 
            icon={<Clock className="w-5 h-5 text-purple-600" />} 
            color="bg-purple-50" 
          />
          {/* Discounts captured — only relevant for Manager/CFO */}
          {!isClerk && (
            <KPICard 
              title="Discounts Captured (30d)" 
              value={`$${kpis?.discount_captured_30d || 0}`} 
              trend="+5.1%" 
              icon={<DollarSign className="w-5 h-5 text-orange-600" />} 
              color="bg-orange-50" 
            />
          )}
          {/* Clerk sees their pending queue count instead */}
          {isClerk && (
            <KPICard 
              title="Pending in My Queue" 
              value={queueData?.total_count || 0}
              icon={<Users className="w-5 h-5 text-orange-600" />} 
              color="bg-orange-50" 
            />
          )}
        </div>

        {/* Approval threshold reminder for Clerk */}
        {isClerk && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-800 flex items-center">
            <AlertCircle className="w-4 h-4 mr-2 shrink-0" />
            You can approve invoices up to <strong className="mx-1">${CLERK_THRESHOLD.toLocaleString()}</strong>. 
            Anything above that will be escalated to the Manager.
          </div>
        )}
        {isManager && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-800 flex items-center">
            <AlertCircle className="w-4 h-4 mr-2 shrink-0" />
            You can approve invoices up to <strong className="mx-1">${MANAGER_THRESHOLD.toLocaleString()}</strong>. 
            Anything above that will be escalated to the CFO.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Cash Flow Forecast Chart — Manager and CFO only */}
          {!isClerk && (
          <div className="lg:col-span-2 bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-bold text-gray-900">Cash Flow Forecast (30 Days)</h2>
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span>Projected Outflow</span>
              </div>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={cashFlowData}>
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
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 p-3 bg-blue-50 rounded-lg flex items-center text-sm text-blue-700">
              <AlertCircle className="w-4 h-4 mr-2" />
              <span>Safety threshold: $50,000. Projected outflows are within limits.</span>
            </div>
          </div>
          )}

          {/* Clerk: show their pending queue instead of cash flow */}
          {isClerk && (
          <div className="lg:col-span-2 bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-bold text-gray-900">My Approval Queue</h2>
              <span className="text-xs text-gray-500">{queueData?.total_count || 0} pending</span>
            </div>
            <div className="space-y-3 overflow-y-auto max-h-[400px]">
              {(!queueData?.approvals || queueData.approvals.length === 0) ? (
                <div className="text-center py-12 text-gray-400 italic text-sm">
                  No invoices pending your review
                </div>
              ) : (
                queueData.approvals.map((approval: any) => (
                  <div
                    key={approval.approval_id}
                    className="p-4 rounded-lg border bg-gray-50 hover:bg-white hover:shadow-md transition-all cursor-pointer"
                    onClick={() => window.location.href = `/invoices/${approval.invoice_id}`}
                  >
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-sm font-medium text-gray-900">{approval.vendor_name}</span>
                      <span className="text-sm font-bold text-gray-900">${Number(approval.amount || 0).toLocaleString()}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      Invoice #{approval.invoice_number}
                      {approval.due_date && ` · Due ${approval.due_date}`}
                    </div>
                    {approval.exception_id && (
                      <div className="mt-2">
                        <span
                          className="text-xs text-blue-600 hover:underline cursor-pointer"
                          onClick={(e) => { e.stopPropagation(); window.location.href = `/exceptions/${approval.exception_id}` }}
                        >
                          View exception →
                        </span>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
          )}

          {/* Exception Feed Sidebar */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 flex flex-col h-full">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-bold text-gray-900">Real-time Exceptions</h2>
              <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-600 rounded-full animate-pulse">
                LIVE
              </span>
            </div>
            <div className="space-y-4 overflow-y-auto max-h-[500px] pr-2">
              {events.length === 0 ? (
                <div className="text-center py-12 text-gray-400 italic text-sm">
                  No active exceptions detected
                </div>
              ) : (
                events.map(event => (
                  <div 
                    key={event.exception_id} 
                    className="p-4 rounded-lg border bg-gray-50 hover:bg-white hover:shadow-md transition-all cursor-pointer group"
                    onClick={() => window.location.href = `/exceptions/${event.exception_id}`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${getSeverityColor(event.severity_band)}`}>
                        {event.severity_band}
                      </span>
                      <span className="text-xs text-gray-400">{new Date().toLocaleTimeString()}</span>
                    </div>
                    <div className="font-medium text-sm text-gray-900 group-hover:text-blue-600 transition-colors">
                      {event.vendor_name}
                    </div>
                    <div className="text-xs text-gray-500 mb-2">
                      ${event.total_amount.toLocaleString()} - {event.exception_type}
                    </div>
                    <div className="text-xs text-gray-600 line-clamp-2 italic bg-white p-2 rounded border border-gray-100">
                      {event.llm_explanation || (event.llm_explanation_ready ? 'Generating explanation...' : 'Waiting for LLM...')}
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

export default DashboardPage