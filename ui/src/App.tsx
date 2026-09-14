import { useCallback, useEffect, useRef, useState } from "react"
import { KeyRound, Moon, RefreshCcw, Sun } from "lucide-react"

import { AddNumbersDialog } from "@/components/app/AddNumbersDialog"
import { QueueCard } from "@/components/app/QueueCard"
import { StatsBar } from "@/components/app/StatsBar"
import { RegistrationForm } from "@/components/app/RegistrationForm"
import { RegistrationTable } from "@/components/app/RegistrationTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { useTheme } from "@/lib/theme"
import type { BulkImportResult, Registration, Stats } from "@/types"

export default function App() {
  const [registrations, setRegistrations] = useState<Registration[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [queueKey, setQueueKey] = useState(0)
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

  function handleBulkResult(res: BulkImportResult) {
    const n = res.created.length
    if (n > 0) setNotice(`Added ${n} number${n === 1 ? "" : "s"}.`)
    setQueueKey((k) => k + 1)
    refresh()
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <AddNumbersDialog open={addOpen} onClose={() => setAddOpen(false)} onDone={handleBulkResult} />

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
              setQueueKey((k) => k + 1)
            }}
            onAddNumbers={() => setAddOpen(true)}
          />
          <div className="lg:col-span-2 space-y-4">
            <QueueCard refreshKey={queueKey} onAction={() => { refresh(); setQueueKey((k) => k + 1) }} />
            <RegistrationTable
              registrations={registrations}
              loading={loading}
              onRefresh={refresh}
            />
          </div>
        </div>

        <footer className="pb-8 text-center text-xs text-muted-foreground">
          Authorized-use only: register clients who have explicitly requested it. The OTP is sent to
          the client&apos;s phone by SportyBet; emailing credentials is handled by your existing pipeline.
        </footer>
      </main>
    </div>
  )
}