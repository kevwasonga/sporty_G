import type {
  ApproveSkipResponse,
  BulkImportResult,
  QueueResponse,
  Registration,
  SendOtpResponse,
  Stats,
  VerifyOtpResponse,
} from "@/types"

const API_BASE = import.meta.env.VITE_API_BASE ?? ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string | { msg?: string }[] }
      if (typeof body.detail === "string") detail = body.detail
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  register: (phone: string, password: string | null, manualSmsSelect = false): Promise<Registration> =>
    request<Registration>("/api/registrations", {
      method: "POST",
      body: JSON.stringify({ phone, password: password || null, manual_sms_select: manualSmsSelect }),
    }),

  list: (): Promise<Registration[]> => request<Registration[]>("/api/registrations"),

  getRegistration: (id: number): Promise<Registration> => request<Registration>(`/api/registrations/${id}`),

  sendOtp: (id: number): Promise<SendOtpResponse> =>
    request<SendOtpResponse>(`/api/registrations/${id}/send-otp`, { method: "POST" }),

  verifyOtp: (id: number, otp: string): Promise<VerifyOtpResponse> =>
    request<VerifyOtpResponse>(`/api/registrations/${id}/verify-otp`, {
      method: "POST",
      body: JSON.stringify({ otp }),
    }),

  stats: (): Promise<Stats> => request<Stats>("/api/stats"),

  bulkRegister: (numbers: string[], defaultCountry = "234", manualSmsSelect = false): Promise<BulkImportResult> =>
    request<BulkImportResult>("/api/registrations/bulk", {
      method: "POST",
      body: JSON.stringify({ numbers, default_country: defaultCountry, manual_sms_select: manualSmsSelect }),
    }),

  importContacts: (
    filename: string,
    dataBase64: string,
    defaultCountry = "234",
    manualSmsSelect = false,
  ): Promise<BulkImportResult> =>
    request<BulkImportResult>("/api/registrations/import", {
      method: "POST",
      body: JSON.stringify({ filename, data_base64: dataBase64, default_country: defaultCountry, manual_sms_select: manualSmsSelect }),
    }),

  queueNext: (): Promise<QueueResponse> => request<QueueResponse>("/api/queue/next"),

  approve: (id: number, advance = true): Promise<ApproveSkipResponse> =>
    request<ApproveSkipResponse>(`/api/registrations/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ advance }),
    }),

  skip: (id: number, advance = true): Promise<ApproveSkipResponse> =>
    request<ApproveSkipResponse>(`/api/registrations/${id}/skip`, {
      method: "POST",
      body: JSON.stringify({ advance }),
    }),

  deleteRegistrations: (ids: number[]): Promise<{ deleted: number }> =>
    request<{ deleted: number }>(`/api/registrations/${ids[0]}`, { method: "DELETE" }),
}