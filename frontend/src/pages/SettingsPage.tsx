import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import apiClient from '../lib/api'
import Layout from '../components/Layout'
import { useRole } from '../hooks/useRole'
import { 
  Settings, 
  ShieldCheck, 
  Activity, 
  Link as LinkIcon, 
  CheckCircle2, 
  XCircle,
  Lock
} from 'lucide-react'

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'baselines' | 'workflow' | 'health' | 'integrations'>('baselines')
  const { isClerk, isCFO } = useRole()

  // Clerks have no access to settings
  if (isClerk) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <Lock className="w-12 h-12 text-gray-300 mb-4" />
          <h2 className="text-xl font-bold text-gray-700 mb-2">Access Restricted</h2>
          <p className="text-gray-500 max-w-sm">
            Settings are only available to Managers and CFOs. 
            Contact your manager to change workflow configuration.
          </p>
        </div>
      </Layout>
    )
  }

  // Vendor Baselines Data
  const { data: vendors, isLoading: vendorsLoading } = useQuery({
    queryKey: ['vendor-baselines'],
    queryFn: async () => {
      const response = await apiClient.get('/vendors/baselines')
      return response.data
    }
  })

  const updateBaselineMutation = useMutation({
    mutationFn: async ({ vendor_key, updates }: { vendor_key: string, updates: any }) => {
      return apiClient.put(`/vendors/${vendor_key}/baseline`, updates)
    },
    onSuccess: () => {
      window.location.reload()
    }
  })

  // Workflow Config Data
  const { data: workflowConfig, isLoading: configLoading } = useQuery({
    queryKey: ['workflow-config'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/workflow')
      return response.data
    }
  })

  const updateConfigMutation = useMutation({
    mutationFn: async (updates: any) => {
      return apiClient.put('/settings/workflow', updates)
    },
    onSuccess: () => {
      window.location.reload()
    }
  })

  // System Health Data
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: async () => {
      const response = await apiClient.get('/health')
      return response.data
    },
    refetchInterval: 30000
  })

  if (vendorsLoading || configLoading || healthLoading) {
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">System Settings</h1>
            <p className="text-gray-500">Configure vendor baselines, approval workflows, and monitor health</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-xl w-fit">
          {[
            { id: 'baselines', label: 'Vendor Baselines', icon: <ShieldCheck className="w-4 h-4" /> },
            { id: 'workflow', label: 'Approval Workflow', icon: <Settings className="w-4 h-4" /> },
            { id: 'health', label: 'System Health', icon: <Activity className="w-4 h-4" /> },
            { id: 'integrations', label: 'Integrations', icon: <LinkIcon className="w-4 h-4" /> },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="mt-6">
          {activeTab === 'baselines' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900">Vendor Baseline Management</h2>
                <p className="text-sm text-gray-500">Configure auto-approval thresholds and monitor statistical profiles</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                    <tr className="border-b border-gray-100">
                      <th className="px-6 py-3">Vendor Name</th>
                      <th className="px-6 py-3">Txn Count</th>
                      <th className="px-6 py-3">Mean (30d)</th>
                      <th className="px-6 py-3">Auto-Approve</th>
                      <th className="px-6 py-3">Max Amount</th>
                      <th className="px-6 py-3">Max Z-Score</th>
                      <th className="px-6 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {vendors?.map((vendor: any) => (
                      <tr key={vendor.vendor_key} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4 font-medium text-gray-900">{vendor.vendor_name}</td>
                        <td className="px-6 py-4 text-gray-600">{vendor.txn_count_total}</td>
                        <td className="px-6 py-4 text-gray-600">${vendor.mean_invoice_amount_30d?.toLocaleString()}</td>
                        <td className="px-6 py-4">
                          <button 
                            onClick={() => updateBaselineMutation.mutate({ 
                              vendor_key: vendor.vendor_key, 
                              updates: { auto_approve_enabled: !vendor.auto_approve_enabled } 
                            })}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              vendor.auto_approve_enabled ? 'bg-blue-600' : 'bg-gray-300'
                            }`}
                          >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              vendor.auto_approve_enabled ? 'translate-x-6' : 'translate-x-1'
                            }`} />
                          </button>
                        </td>
                        <td className="px-6 py-4">
                          <input 
                            type="number" 
                            defaultValue={vendor.auto_approve_max_amount}
                            onBlur={(e) => updateBaselineMutation.mutate({ 
                              vendor_key: vendor.vendor_key, 
                              updates: { auto_approve_max_amount: parseFloat(e.target.value) } 
                            })}
                            className="w-24 px-2 py-1 border border-gray-300 rounded text-xs"
                          />
                        </td>
                        <td className="px-6 py-4">
                          <input 
                            type="number" 
                            step="0.1"
                            defaultValue={vendor.auto_approve_max_zscore}
                            onBlur={(e) => updateBaselineMutation.mutate({ 
                              vendor_key: vendor.vendor_key, 
                              updates: { auto_approve_max_zscore: parseFloat(e.target.value) } 
                            })}
                            className="w-16 px-2 py-1 border border-gray-300 rounded text-xs"
                          />
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button className="text-blue-600 hover:text-blue-800 text-xs font-bold">View Analytics</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'workflow' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 max-w-3xl">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-gray-900">Approval Workflow Configuration</h2>
                {!isCFO && (
                  <span className="flex items-center text-xs text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
                    <Lock className="w-3 h-3 mr-1" /> View only — CFO can edit
                  </span>
                )}
              </div>
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Department Approval Threshold ($)</label>
                    <input 
                      type="number" 
                      value={workflowConfig?.department_threshold}
                      readOnly={!isCFO}
                      onChange={(e) => isCFO && updateConfigMutation.mutate({ department_threshold: parseFloat(e.target.value) })}
                      className={`w-full px-4 py-2 border border-gray-300 rounded-lg outline-none ${isCFO ? 'focus:ring-2 focus:ring-blue-500' : 'bg-gray-50 cursor-not-allowed text-gray-500'}`}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Manager Approval Threshold ($)</label>
                    <input 
                      type="number" 
                      value={workflowConfig?.manager_threshold}
                      readOnly={!isCFO}
                      onChange={(e) => isCFO && updateConfigMutation.mutate({ manager_threshold: parseFloat(e.target.value) })}
                      className={`w-full px-4 py-2 border border-gray-300 rounded-lg outline-none ${isCFO ? 'focus:ring-2 focus:ring-blue-500' : 'bg-gray-50 cursor-not-allowed text-gray-500'}`}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">CFO Escalation Threshold ($)</label>
                  <input 
                    type="number" 
                    value={workflowConfig?.cfo_threshold}
                    readOnly={!isCFO}
                    onChange={(e) => isCFO && updateConfigMutation.mutate({ cfo_threshold: parseFloat(e.target.value) })}
                    className={`w-full px-4 py-2 border border-gray-300 rounded-lg outline-none ${isCFO ? 'focus:ring-2 focus:ring-blue-500' : 'bg-gray-50 cursor-not-allowed text-gray-500'}`}
                  />
                </div>
                <div className="pt-6 border-t border-gray-100">
                  <h3 className="text-sm font-bold text-gray-900 mb-4">SLA Settings (Hours)</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <label className="text-xs text-gray-500 uppercase font-bold">AP Clerk</label>
                      <input 
                        type="number" 
                        value={workflowConfig?.sla_clerk}
                        readOnly={!isCFO}
                        onChange={(e) => isCFO && updateConfigMutation.mutate({ sla_clerk: parseInt(e.target.value) })}
                        className={`w-full px-4 py-2 border border-gray-300 rounded-lg text-sm ${!isCFO ? 'bg-gray-50 cursor-not-allowed text-gray-500' : ''}`}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs text-gray-500 uppercase font-bold">Manager</label>
                      <input 
                        type="number" 
                        value={workflowConfig?.sla_manager}
                        readOnly={!isCFO}
                        onChange={(e) => isCFO && updateConfigMutation.mutate({ sla_manager: parseInt(e.target.value) })}
                        className={`w-full px-4 py-2 border border-gray-300 rounded-lg text-sm ${!isCFO ? 'bg-gray-50 cursor-not-allowed text-gray-500' : ''}`}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs text-gray-500 uppercase font-bold">CFO</label>
                      <input 
                        type="number" 
                        value={workflowConfig?.sla_cfo}
                        readOnly={!isCFO}
                        onChange={(e) => isCFO && updateConfigMutation.mutate({ sla_cfo: parseInt(e.target.value) })}
                        className={`w-full px-4 py-2 border border-gray-300 rounded-lg text-sm ${!isCFO ? 'bg-gray-50 cursor-not-allowed text-gray-500' : ''}`}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'health' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                { name: 'PostgreSQL Database', status: health?.database, icon: <ShieldCheck /> },
                { name: 'Redis Cache', status: health?.redis, icon: <ShieldCheck /> },
                { name: 'Tesseract OCR', status: health?.ocr, icon: <ShieldCheck /> },
                { name: 'NVIDIA NIM LLM', status: health?.llm, icon: <ShieldCheck /> },
                { name: 'Gmail IMAP', status: health?.gmail, icon: <ShieldCheck /> },
                { name: 'ERP System', status: health?.erp, icon: <ShieldCheck /> },
              ].map(service => (
                <div key={service.name} className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-gray-50 rounded-lg text-gray-600">
                      {service.icon}
                    </div>
                    <span className="font-medium text-gray-900">{service.name}</span>
                  </div>
                  <div className={`flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-bold ${
                    service.status === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {service.status === 'ok' ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                    <span>{service.status?.toUpperCase() || 'UNKNOWN'}</span>
                  </div>
                </div>
              ))}
              <div className="lg:col-span-3 bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h2 className="text-lg font-bold text-gray-900 mb-4">Queue Metrics</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                    <div className="text-xs text-gray-500 uppercase font-bold mb-1">LLM Queue Depth</div>
                    <div className="text-2xl font-bold text-gray-900">{health?.llm_queue_depth || 0}</div>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                    <div className="text-xs text-gray-500 uppercase font-bold mb-1">OCR Queue Depth</div>
                    <div className="text-2xl font-bold text-gray-900">{health?.ocr_queue_depth || 0}</div>
                  </div>
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                    <div className="text-xs text-gray-500 uppercase font-bold mb-1">Matching Queue Depth</div>
                    <div className="text-2xl font-bold text-gray-900">{health?.matching_queue_depth || 0}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-6">Integration Status</h2>
              <div className="space-y-4">
                {[
                  { name: 'Gmail IMAP', status: health?.gmail, lastSync: health?.gmail_last_sync },
                  { name: 'ERP API', status: health?.erp, lastSync: health?.erp_last_sync },
                  { name: 'NVIDIA NIM', status: health?.llm, lastSync: health?.llm_last_sync },
                ].map(int => (
                  <div key={int.name} className="flex items-center justify-between p-4 rounded-lg border border-gray-100 bg-gray-50">
                    <div className="flex items-center space-x-3">
                      <LinkIcon className="w-4 h-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-900">{int.name}</span>
                    </div>
                    <div className="flex items-center space-x-4">
                      <span className="text-xs text-gray-500">Last Sync: {int.lastSync || 'Never'}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                        int.status === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {int.status?.toUpperCase() || 'OFFLINE'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}

export default SettingsPage
