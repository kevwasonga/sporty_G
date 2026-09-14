import { useCallback, useEffect, useRef, useState } from "react"
import { KeyRound, Moon, RefreshCcw, Sun } from "lucide-react"

import { StatsBar } from "@/components/app/StatsBar"
import { RegistrationForm } from "@/components/app/RegistrationForm"
import { RegistrationTable } from "@/components/app/RegistrationTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { useTheme } from "@/lib/theme"
import type { Registration, Stats } from "@/types"

export default function App() {
  const [registrations, setRegistrations] = useState<Registration[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)
  const timer = useRef<number | null>(null)
  const { theme, toggle } = useTheme()

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [rows, s] = await Promise.all([api.list(), api.stats()])
      setRegistrations(rows)
      setStats(s)
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "API unreachable — is the backend running?")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    timer.current = window.setInterval(refresh, 10_000)
    return () => {
      if (timer.current) window.clearInterval(timer.current)
    }
  }, [refresh])

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-2">
            <KeyRound className="size-6 text-primary" />
            <div>
              <h1 className="text-lg font-semibold leading-none">Sporty OTP Lab</h1>
              <p className="text-xs text-muted-foreground">
                Phone → generated password → real SportyBet registration → OTP delivery tracking
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {stats && (
              <Badge variant="default">
                provider: {stats.provider}
              </Badge>
            )}
            <Button variant="outline" size="icon" onClick={toggle} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>
            <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
              <RefreshCcw className={loading ? "animate-spin" : ""} /> Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6">
        {notice && (
          <div className="rounded-md border border-amber-400/40 bg-amber-400/10 p-3 text-sm text-amber-700 dark:text-amber-300">
            {notice}
          </div>
        )}

        {stats && <StatsBar stats={stats} />}

        <div className="grid gap-6 lg:grid-cols-3">
          <RegistrationForm
            onCreated={(reg) => {
              setNotice(`Client ${reg.phone} registered — email them ${reg.password ?? ""}.`)
              refresh()
            }}
          />
          <RegistrationTable registrations={registrations} loading={loading} onRefresh={refresh} />
        </div>

        <footer className="pb-8 text-center text-xs text-muted-foreground">
          Authorized-use only: register clients who have explicitly requested it. The OTP is sent to
          the client&apos;s phone by SportyBet; emailing credentials is handled by your existing pipeline.
        </footer>
      </main>
    </div>
  )
}