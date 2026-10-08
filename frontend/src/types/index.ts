export type Role = 'ADMIN' | 'DOCTOR' | 'STAFF'
export type AppointmentStatus = 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface User { id: number; email: string; full_name: string; role: Role; is_active: boolean; doctor_id: number | null }
export interface Token { access_token: string; token_type: string; expires_in_minutes: number; user: User }

export interface Department { id: number; name: string; description: string | null; created_at: string; doctor_count: number }
export interface Doctor {
  id: number; name: string; department_id: number; department_name: string | null
  specialization: string | null; email: string; phone: string | null; created_at: string
}
export interface ScheduleSlot { time: string; available: boolean; appointment_id: number | null }
export interface DoctorSchedule { doctor_id: number; date: string; slots: ScheduleSlot[] }

export interface Patient {
  id: number; name: string; date_of_birth: string; gender: string
  phone: string | null; email: string | null; created_at: string; updated_at: string
}
export interface PatientDetail extends Patient {
  stats: { total_appointments: number; completed: number; no_shows: number; cancellations: number; upcoming: number }
}
export interface PatientInput { name: string; date_of_birth: string; gender: string; phone?: string | null; email?: string | null }

export interface LatestPrediction { no_show_probability: number; risk_level: RiskLevel; created_at: string }
export interface Appointment {
  id: number; patient_id: number; patient_name: string | null; doctor_id: number; doctor_name: string | null
  department_id: number; department_name: string | null; appointment_date: string; appointment_time: string
  booking_date: string; status: AppointmentStatus; created_at: string; updated_at: string
  latest_prediction: LatestPrediction | null
}
export interface StatusHistory { id: number; old_status: string | null; new_status: string; changed_at: string; changed_by: string }
export interface AppointmentDetail extends Appointment { status_history: StatusHistory[] }

export interface Factor {
  feature: string; label: string; value: unknown; display_value: string
  contribution: number; direction: 'increases_risk' | 'decreases_risk'
}
export interface Prediction {
  appointment_id: number; no_show_probability: number; risk_level: RiskLevel; flagged_by_model: boolean
  top_factors: string[]; factors: Factor[]; explanation_note: string; model_name: string; model_version: string; predicted_at: string
}

export interface ModelTestMetrics {
  threshold: number; accuracy: number; roc_auc: number; pr_auc: number; brier_score: number
  no_show_precision: number; no_show_recall: number; no_show_f1: number; macro_f1: number
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number }
}
export interface ModelMetrics {
  model_version: string; trained_at: string; data_source: string; synthetic_data: boolean; selected_model: string
  selection_criterion: string; split_strategy: string
  dataset: { raw_rows: number; labelled_rows: number; unique_patients: number; no_show_rate: number }
  models: Record<string, { display_name: string; params: Record<string, unknown>; decision_threshold: number; validation: ModelTestMetrics; test: ModelTestMetrics }>
  global_feature_importance: { feature: string; label: string; mean_abs_shap: number }[]
}
export interface ModelInfo {
  loaded: boolean; model_name: string | null; model_version: string | null; decision_threshold: number | null
  risk_thresholds: { low_max: number; medium_max: number }; metrics: ModelMetrics | null
}
export interface RetrainStatus { state: 'idle' | 'running' | 'succeeded' | 'failed'; detail: string | null; started_at: string | null; finished_at: string | null; model_version: string | null }

export interface Overview {
  total_appointments: number; completed: number; cancelled: number; no_shows: number; upcoming: number
  high_risk_upcoming: number; no_show_rate: number | null; cancellation_rate: number | null; no_show_rate_definition: string
  status_counts: Record<'total' | AppointmentStatus, number>
}
export interface DepartmentStats {
  department_id: number; department_name: string; total_appointments: number; completed: number; no_shows: number
  cancelled: number; upcoming: number; no_show_rate: number | null; cancellation_rate: number | null
  avg_booking_lead_days: number | null; high_risk_upcoming: number; avg_predicted_risk_upcoming: number | null
}
export interface TrendPoint { period: string; total: number; completed: number; no_shows: number; cancelled: number; no_show_rate: number | null }
export interface DayOfWeekStat { day: string; day_index: number; total: number; no_shows: number; no_show_rate: number | null }
export interface RiskDistribution {
  days_ahead: number; scored_upcoming: number; unscored_upcoming: number
  by_level: { risk_level: RiskLevel; count: number }[]; histogram: { bucket: string; count: number }[]
}
export interface HighRiskAppointment {
  appointment_id: number; patient_id: number; patient_name: string; department_name: string; doctor_name: string
  appointment_date: string; appointment_time: string; status: AppointmentStatus; no_show_probability: number
  risk_level: RiskLevel; top_factor: string | null
}

export interface AIMeta { llm_used: boolean; provider: string; model: string | null; grounding_check: string }
export interface ExplainResponse { appointment_id: number; explanation: string; prediction: Prediction; disclaimer: string; meta: AIMeta }
export type ReminderChannel = 'sms' | 'email' | 'whatsapp'
export type ReminderTone = 'professional' | 'friendly'
export interface ReminderResponse { appointment_id: number; channel: ReminderChannel; tone: ReminderTone; subject: string | null; message: string; character_count: number; meta: AIMeta }
export interface SummaryResponse { summary: string; period_label: string; date_from: string | null; date_to: string | null; department_name: string | null; statistics: Record<string, unknown>; meta: AIMeta }
export interface ChatResponse { question: string; answer: string; intent: string; period_label: string; department_name: string | null; data: Record<string, unknown>; meta: AIMeta }
