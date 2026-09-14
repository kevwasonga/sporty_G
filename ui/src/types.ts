export type Status = "pending" | "sending" | "otp_sent" | "otp_verified" | "failed"

export interface Registration {
  id: number
  phone: string
  password: string | null
  status: Status
  provider: string
  provider_ref: string | null
  error: string | null
  manualSmsSelect?: boolean
  created_at: string
  updated_at: string
}

export interface SendOtpResponse {
  id: number
  phone: string
  status: Status
  provider_ref: string | null
  message: string
}

export interface VerifyOtpResponse {
  id: number
  phone: string
  status: Status
  message: string
}

export interface Stats {
  total: number
  pending: number
  sending: number
  otp_sent: number
  verified: number
  failed: number
  provider: string
  password_mode: string
}