import { useState } from "react"
import {
  CheckCircle2,
  CircleDashed,
  Copy,
  Download,
  Eye,
  EyeOff,
  Loader2,
  MessageSquare,
  SendHorizontal,
  Trash2,
  XCircle,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api } from "@/lib/api"
import type { Registration, Status } from "@/types"

const STATUS_META: Record<Status, { label: string; variant: "secondary" | "default" | "destructive" | "outline" }> = {
  pending: { label: "Pending", variant: "outline" },
  sending: { label: "Awaiting OTP · sending…", variant: "default" },
  otp_sent: { label: "Requested · check phone", variant: "default" },
  otp_verified: { label: "Verified", variant: "secondary" },
  failed: { label: "Failed", variant: "destructive" },
}

function StatusBadge({ status }: { status: Status }) {
  if (status === "sending") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
        <Loader2 className="size-3.5 animate-spin" />
        Awaiting OTP…
      </span>
    )
  }
  const meta = STATUS_META[status]
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

function failureCategory(error: string | null): { category: string; full: string } {
  const full = (error ?? "").trim() || "Unknown failure"
  const low = full.toLowerCase()
  if (low.includes("captcha")) return { category: "CAPTCHA", full }
  if (low.includes("not found") || low.includes("selectors")) return { category: "FORM", full }
  if (low.includes("timeout") || low.includes("timed out")) return { category: "TIMEOUT", full }
  if (low.includes("network") || low.includes("unreachable")) return { category: "NETWORK", full }
  return { category: "FAILED", full }
}

function PasswordCell({ password }: { password: string | null }) {
  const [revealed, setRevealed] = useState(false)
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex items-center gap-1">
      <code
        className="max-w-[140px] truncate font-mono text-xs"
        title={password && revealed ? password : undefined}
      >
        {password ? (revealed ? password : "••••••••••••") : "—"}
      </code>
      {password && (
        <>
          <Button type="button" variant="ghost" size="icon" onClick={() => setRevealed((v) => !v)}>
            {revealed ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(password)
              } catch {
                /* clipboard unavailable */
              }
              setCopied(true)
              setTimeout(() => setCopied(false), 1200)
            }}
          >
            <Copy className="size-3.5 text-muted-foreground" />
          </Button>
          {copied && <span className="text-[10px] text-muted-foreground">copied</span>}
        </>
      )}
    </div>
  )
}

interface RowState {
  otp: string
  busy: boolean
  feedback: string | null
}

function RegistrationRow({
  row,
  onRefresh,
}: {
  row: Registration
  onRefresh: () => void
}) {
  const [state, setState] = useState<RowState>({ otp: "", busy: false, feedback: null })

  async function sendOtp() {
    setState((s) => ({ ...s, busy: true, feedback: null }))
    try {
      const res = await api.sendOtp(row.id)
      setState((s) => ({ ...s, feedback: res.message }))
      onRefresh()
    } catch (e) {
      setState((s) => ({ ...s, feedback: e instanceof Error ? e.message : "Failed" }))
    } finally {
      setState((s) => ({ ...s, busy: false }))
    }
  }

  async function verify() {
    if (!state.otp.trim()) return
    setState((s) => ({ ...s, busy: true, feedback: null }))
    try {
      const res = await api.verifyOtp(row.id, state.otp.trim())
      setState((s) => ({ ...s, feedback: res.message, otp: "" }))
      onRefresh()
    } catch (e) {
      setState((s) => ({ ...s, feedback: e instanceof Error ? e.message : "Failed" }))
    } finally {
      setState((s) => ({ ...s, busy: false }))
    }
  }

  async function deleteRow() {
    if (!window.confirm("Delete this number?")) return
    try {
      await api.deleteRegistrations([row.id])
      onRefresh()
    } catch (e) {
      setState((s) => ({ ...s, feedback: e instanceof Error ? e.message : "Delete failed" }))
    }
  }

  const otpOutstanding = row.status === "otp_sent"
  const failure = failureCategory(row.error)

  return (
    <TableRow>
      <TableCell>
        <div className="font-mono text-sm">{row.phone}</div>
      </TableCell>
      <TableCell>
        <StatusBadge status={row.status} />
      </TableCell>
      <TableCell>
        <PasswordCell password={row.password} />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          {(row.status === "pending" || row.status === "failed") && (
            <Button size="sm" variant="outline" onClick={sendOtp} disabled={state.busy}>
              {state.busy ? <CircleDashed className="animate-spin" /> : <SendHorizontal />}
              Send OTP
            </Button>
          )}
          {row.status === "sending" && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-4 animate-spin text-primary" />
              Registering · OTP on its way
            </span>
          )}
          {otpOutstanding && (
            <>
              <Input
                value={state.otp}
                onChange={(e) => setState((s) => ({ ...s, otp: e.target.value }))}
                placeholder="Enter OTP from client"
                className="h-8 w-32 font-mono text-xs"
                maxLength={8}
              />
              <Button size="sm" onClick={verify} disabled={state.busy || state.otp.trim().length === 0}>
                {state.busy ? <CircleDashed className="animate-spin" /> : <CheckCircle2 />}
                Verify
              </Button>
            </>
          )}
          {row.status === "otp_verified" && <CheckCircle2 className="size-4 text-primary" />}
          {row.status === "failed" && <XCircle className="size-4 text-destructive" />}
          <Button type="button" size="sm" variant="ghost" onClick={deleteRow} title="Delete this number">
            <Trash2 className="size-3.5 text-destructive" />
          </Button>
        </div>
      </TableCell>
      <TableCell className="max-w-[240px]">
        {state.feedback && <p className="text-xs text-muted-foreground">{state.feedback}</p>}
        {row.error && (
          <p className="break-words text-xs text-destructive" title={failure.full}>
            {failure.category}: {failure.full}
          </p>
        )}
      </TableCell>
    </TableRow>
  )
}

function downloadCsv(rows: Registration[]) {
  if (rows.length === 0) return
  const headers = ["Phone", "Status", "Password", "Registered At"]
  const lines = rows.map((r) =>
    [r.phone, r.status, r.password || "", r.created_at]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(","),
  )
  const blob = new Blob([[headers.join(","), ...lines].join("\n")], { type: "text/csv" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `sporty-clients-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function RegistrationTable({
  registrations,
  loading,
  onRefresh,
}: {
  registrations: Registration[]
  loading: boolean
  onRefresh: () => void
}) {
  const [statusFilter, setStatusFilter] = useState<"all" | Status>("all")

  const statusCounts = (status: Status) => registrations.filter((r) => r.status === status).length
  const failedCount = statusCounts("failed")
  const visible = statusFilter === "all" ? registrations : registrations.filter((r) => r.status === statusFilter)

  const FILTER_TABS: { key: "all" | Status; label: string }[] = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "sending", label: "Sending" },
    { key: "otp_sent", label: "Awaiting code" },
    { key: "failed", label: `Failed (${failedCount})` },
    { key: "otp_verified", label: "Verified" },
  ]

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <MessageSquare className="size-5" />
            Registrations
          </span>
          <button
            onClick={() => downloadCsv(registrations)}
            disabled={registrations.length === 0}
            className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
          >
            <Download className="size-3.5" />
            Download CSV
          </button>
        </CardTitle>
        <CardDescription>
          Per client: the OTP the phone received, and verification. SportyBet requires only phone
          &amp; password.
        </CardDescription>
      </CardHeader>

      {failedCount > 0 && (
        <CardContent className="pt-0">
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3">
            <p className="mb-1.5 text-xs font-semibold text-destructive">
              FAILURE REPORT — {failedCount} number{failedCount === 1 ? "" : "s"} need attention
            </p>
            <div className="space-y-1.5">
              {registrations
                .filter((r) => r.status === "failed")
                .map((r) => {
                  const cat = failureCategory(r.error)
                  return (
                    <div key={r.id} className="flex flex-wrap items-start gap-2 rounded border border-destructive/20 bg-background px-2 py-1.5 text-xs">
                      <span className="font-mono">{r.phone}</span>
                      <Badge variant="destructive">{cat.category}</Badge>
                      <span className="min-w-0 flex-1 break-words text-muted-foreground">{cat.full}</span>
                    </div>
                  )
                })}
            </div>
          </div>
        </CardContent>
      )}

      <CardContent>
        {registrations.length > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-1">
            {FILTER_TABS.map((tab) => {
              const active = statusFilter === tab.key
              const count = tab.key === "all" ? registrations.length : statusCounts(tab.key as Status)
              return (
                <button
                  key={tab.key}
                  onClick={() => setStatusFilter(tab.key)}
                  className={`rounded-full border px-2.5 py-1 text-xs ${
                    active ? "border-primary bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-accent"
                  }`}
                >
                  {tab.label}
                  <span className="ml-1 opacity-70">{count}</span>
                </button>
              )
            })}
          </div>
        )}

        {loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Loading…</div>
        ) : registrations.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            No clients yet. Add a phone number on the left to get started.
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Phone</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Password</TableHead>
                <TableHead>Actions</TableHead>
                <TableHead className="text-right">Feedback</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                    No rows match this filter.
                  </TableCell>
                </TableRow>
              ) : (
                visible.map((row) => (
                  <RegistrationRow key={row.id} row={row} onRefresh={onRefresh} />
                ))
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}