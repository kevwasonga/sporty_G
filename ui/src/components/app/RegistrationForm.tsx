import { useEffect, useState } from "react"
import { Copy, Eye, EyeOff, KeyRound, Plus, RefreshCcw, SendHorizontal } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import type { Registration } from "@/types"

const COUNTRIES = [
  { dial: "234", label: "Nigeria" },
  { dial: "254", label: "Kenya" },
] as const

const NATIONAL_RE = /^\d{6,14}$/

function CredentialRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false)
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      /* clipboard unavailable */
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 shrink-0 text-xs text-muted-foreground">{label}</span>
      <code className={`min-w-0 flex-1 truncate rounded border bg-muted/40 px-2 py-1 text-xs ${mono ? "font-mono" : ""}`}>
        {value}
      </code>
      <Button type="button" variant="ghost" size="icon" onClick={onCopy} title={`Copy ${label}`}>
        <Copy className="size-3.5 text-muted-foreground" />
      </Button>
      {copied && <span className="text-[10px] text-muted-foreground">copied</span>}
    </div>
  )
}

export function RegistrationForm({
  onCreated,
  onAddNumbers,
}: {
  onCreated: (reg: Registration) => void
  onAddNumbers: () => void
}) {
  const [country, setCountry] = useState<string>("234")
  const [national, setNational] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [manualSmsSelect, setManualSmsSelect] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Registration | null>(null)

  useEffect(() => setError(null), [country, national, password])

  const dial = COUNTRIES.find((c) => c.dial === country)?.dial ?? "234"
  const nationalDigits = national.replace(/\D/g, "")
  const valid = NATIONAL_RE.test(nationalDigits) && !loading

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!valid) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const reg = await api.register(
        `${dial}${nationalDigits}`,
        password.trim() || null,
        manualSmsSelect,
      )
      setResult(reg)
      onCreated(reg)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-5" />
          Register a client
        </CardTitle>
        <CardDescription>
          Pick the client&apos;s country, then enter their national number. SportyBet texts a real
          OTP to the phone; you read the code back from the client and verify it below.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="country">Country</Label>
            <Select value={country} onChange={(e) => setCountry(e.target.value)} id="country">
              {COUNTRIES.map((c) => (
                <option key={c.dial} value={c.dial}>
                  {c.label} (+{c.dial})
                </option>
              ))}
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="phone">Phone number</Label>
            <div className="flex">
              <span className="inline-flex items-center gap-1 rounded-l-md rounded-r-none border border-r-0 bg-muted px-3 font-mono text-sm text-muted-foreground">
                +{dial}
              </span>
              <Input
                id="phone"
                value={national}
                onChange={(e) => setNational(e.target.value)}
                placeholder={dial === "234" ? "801 234 5678" : "712 345 678"}
                className="rounded-l-none font-mono"
                inputMode="tel"
                autoFocus
              />
            </div>
            {nationalDigits && !NATIONAL_RE.test(nationalDigits) && (
              <p className="text-xs text-destructive">Enter a valid national number (6–14 digits).</p>
            )}
            <p className="text-xs text-muted-foreground">
              Will be registered as <code className="font-mono">+{dial} {nationalDigits || "…"}</code>
            </p>
            <button
              type="button"
              onClick={onAddNumbers}
              className="flex items-center gap-1.5 rounded-md border border-dashed border-primary/40 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
            >
              <Plus className="size-3.5" />
              Add many numbers at once
            </button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password (optional)</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="auto-generated if empty"
                className="pr-9"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1/2 -translate-y-1/2"
                onClick={() => setShowPassword((v) => !v)}
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </Button>
            </div>
            {!password && (
              <p className="text-xs text-muted-foreground">
                Leave blank — a strong password (SportyBet rule: 8+ chars, upper/lower/digit) is generated.
              </p>
            )}
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <label className="flex cursor-pointer items-start gap-2.5 rounded-md border bg-muted/30 p-3">
            <input
              type="checkbox"
              checked={manualSmsSelect}
              onChange={(e) => setManualSmsSelect(e.target.checked)}
              className="mt-0.5 size-4 rounded border-input accent-primary"
            />
            <span className="text-xs leading-relaxed">
              <span className="block font-medium">Select &quot;SMS OTP&quot; manually in the browser</span>
              <span className="text-muted-foreground">
                Off (default): the system auto-selects SMS OTP and waits for the code. On: you click
                &quot;SMS OTP&quot; yourself in the parked browser window when it appears — use this
                if the system keeps getting stuck on that step.
              </span>
            </span>
          </label>

          <Button type="submit" disabled={!valid} className="w-full">
            {loading ? <RefreshCcw className="animate-spin" /> : <SendHorizontal />}
            Register &amp; request OTP
          </Button>
        </form>

        {result && (
          <div className="space-y-2 rounded-md border border-primary/30 bg-primary/5 p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-primary">
              <KeyRound className="size-3.5" />
              Credentials — email these to the client
            </p>
            <CredentialRow label="Phone" value={result.phone} mono />
            <CredentialRow label="Password" value={result.password ?? ""} mono />
            <Separator className="my-2" />
            <div className="flex items-center justify-between">
              <Badge variant="outline">status: {result.status}</Badge>
              <span className="text-[10px] text-muted-foreground">
                {result.status === "pending" ? "next: click the row's Send OTP button" : ""}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}