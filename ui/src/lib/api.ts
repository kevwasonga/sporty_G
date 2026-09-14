import type { Registration, SendOtpResponse, Stats, VerifyOtpResponse } from "@/types"

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
  register: (phone: string, password: string | null): Promise<Registration> =>
    request<Registration>("/api/registrations", {
      method: "POST",
      body: JSON.stringify({ phone, password: password || null }),
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

  deleteRegistrations: (ids: number[]): Promise<{ deleted: number }> =>
    request<{ deleted: number }>(`/api/registrations/${ids[0]}`, { method: "DELETE" }),
}