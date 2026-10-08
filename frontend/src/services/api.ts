import type {
  Appointment, AppointmentDetail, AppointmentStatus, ChatResponse, DayOfWeekStat, Department, DepartmentStats,
  Doctor, DoctorSchedule, ExplainResponse, HighRiskAppointment, ModelInfo, Overview, Page, Patient, PatientDetail,
  PatientInput, Prediction, ReminderChannel, ReminderResponse, ReminderTone, RetrainStatus, RiskDistribution,
  SummaryResponse, Token, TrendPoint, User,
} from '../types'

const TOKEN_KEY = 'caresight.token'

export const tokenStore = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set(token: string) {
    try { localStorage.setItem(TOKEN_KEY, token) } catch { /* storage unavailable */ }
  },
  clear() {
    try { localStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ }
  },
}

export class ApiError extends Error {
  status: number
  errors?: { field: string; message: string }[]
  constructor(status: number, message: string, errors?: { field: string; message: string }[]) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(handler: () => void) { onUnauthorized = handler }

type Query = Record<string, string | number | boolean | null | undefined>

function qs(params?: Query): string {
  if (!params) return ''
  const search = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') search.set(k, String(v)) })
  const s = search.toString()
  return s ? `?${s}` : ''
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload: BodyInit | undefined
  if (body instanceof URLSearchParams) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }

  const res = await fetch(`/api${path}${qs(query)}`, { method, headers, body: payload })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/login')) onUnauthorized?.()
    const detail = typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`
    const fieldErrors = data.errors as { field: string; message: string }[] | undefined
    const message = fieldErrors?.length ? `${detail}: ${fieldErrors.map((e) => `${e.field || 'request'} - ${e.message}`).join('; ')}` : detail
    throw new ApiError(res.status, message, fieldErrors)
  }
  return data as T
}

export interface AppointmentFilters {
  status?: AppointmentStatus | ''; department_id?: number | ''; doctor_id?: number | ''; patient_id?: number
  date_from?: string; date_to?: string; search?: string; sort?: 'newest' | 'oldest'; limit?: number; offset?: number
}
export interface PeriodFilter { date_from?: string; date_to?: string; department_id?: number | '' }

export const api = {
  login: (email: string, password: string) =>
    request<Token>('POST', '/auth/login', new URLSearchParams({ username: email, password })),
  me: () => request<User>('GET', '/auth/me'),

  patients: (search = '', limit = 20, offset = 0) => request<Page<Patient>>('GET', '/patients', undefined, { search, limit, offset }),
  patient: (id: number) => request<PatientDetail>('GET', `/patients/${id}`),
  createPatient: (p: PatientInput) => request<Patient>('POST', '/patients', p),
  updatePatient: (id: number, p: Partial<PatientInput>) => request<Patient>('PUT', `/patients/${id}`, p),
  deletePatient: (id: number) => request<void>('DELETE', `/patients/${id}`),

  departments: () => request<Department[]>('GET', '/departments'),
  createDepartment: (d: { name: string; description?: string }) => request<Department>('POST', '/departments', d),

  doctors: (params: { department_id?: number | ''; search?: string; limit?: number; offset?: number } = {}) =>
    request<Page<Doctor>>('GET', '/doctors', undefined, { limit: 100, ...params }),
  createDoctor: (d: Omit<Doctor, 'id' | 'created_at' | 'department_name'>) => request<Doctor>('POST', '/doctors', d),
  doctorSchedule: (id: number, date: string) => request<DoctorSchedule>('GET', `/doctors/${id}/schedule`, undefined, { date }),

  appointments: (f: AppointmentFilters = {}) => request<Page<Appointment>>('GET', '/appointments', undefined, { limit: 25, ...f }),
  appointment: (id: number) => request<AppointmentDetail>('GET', `/appointments/${id}`),
  bookAppointment: (a: { patient_id: number; doctor_id: number; appointment_date: string; appointment_time: string }) =>
    request<AppointmentDetail>('POST', '/appointments', a),
  reschedule: (id: number, a: { doctor_id?: number; appointment_date?: string; appointment_time?: string }) =>
    request<AppointmentDetail>('PATCH', `/appointments/${id}`, a),
  changeStatus: (id: number, status: AppointmentStatus, notes?: string) =>
    request<AppointmentDetail>('PATCH', `/appointments/${id}/status`, { status, notes }),

  predict: (id: number) => request<Prediction>('POST', `/appointments/${id}/predict-no-show`),
  latestPrediction: (id: number) => request<Prediction>('GET', `/appointments/${id}/prediction`),
  batchPredict: (days_ahead: number) => request<{ scored: number; risk_counts: Record<string, number>; model_version: string }>('POST', '/predictions/batch', { days_ahead }),
  modelInfo: () => request<ModelInfo>('GET', '/predictions/model'),
  retrain: (source: 'db' | 'csv') => request<RetrainStatus>('POST', '/predictions/retrain', { source }),
  retrainStatus: () => request<RetrainStatus>('GET', '/predictions/retrain/status'),

  overview: (f: PeriodFilter = {}) => request<Overview>('GET', '/analytics/overview', undefined, { ...f }),
  departmentStats: (f: PeriodFilter = {}) => request<DepartmentStats[]>('GET', '/analytics/departments', undefined, { date_from: f.date_from, date_to: f.date_to }),
  trends: (granularity: 'day' | 'week' | 'month', f: PeriodFilter = {}) =>
    request<{ granularity: string; points: TrendPoint[] }>('GET', '/analytics/no-show-trends', undefined, { granularity, ...f }),
  dayOfWeek: (f: PeriodFilter = {}) => request<DayOfWeekStat[]>('GET', '/analytics/day-of-week', undefined, { ...f }),
  riskDistribution: (days_ahead = 30) => request<RiskDistribution>('GET', '/analytics/risk-distribution', undefined, { days_ahead }),
  highRisk: (days_ahead = 14, limit = 10, min_probability?: number) =>
    request<HighRiskAppointment[]>('GET', '/analytics/high-risk-upcoming', undefined, { days_ahead, limit, min_probability }),

  explain: (appointment_id: number, refresh = false) => request<ExplainResponse>('POST', '/ai/explain-prediction', { appointment_id, refresh }),
  reminder: (appointment_id: number, channel: ReminderChannel, tone: ReminderTone) =>
    request<ReminderResponse>('POST', '/ai/generate-reminder', { appointment_id, channel, tone, request_confirmation: true }),
  departmentSummary: (body: { department_id?: number; period: string; date_from?: string; date_to?: string }) =>
    request<SummaryResponse>('POST', '/ai/department-summary', body),
  chat: (question: string) => request<ChatResponse>('POST', '/ai/chat', { question }),
}
