import { useEffect, useState } from "react"
import { BadgeCheck, Loader2, SkipForward, UserRound } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import type { Registration } from "@/types"

const STATUS_LABEL: Record<Registration["status"], string> = {
  pending: "Pending · not started",
  sending: "Registering · OTP on its way",
  otp_sent: "OTP sent · awaiting code",
  otp_verified: "Verified",
  failed: "Failed",
}

export function QueueCard({ refreshKey, onAction }: { refreshKey: number; onAction: () => void }) {
  const [current, setCurrent] = useState<Registration | null>(null)
  const [busy, setBusy] = useState<"approve" | "skip" | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const res = await api.queueNext()
      setCurrent(res.current)
    } catch {
      setCurrent(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = window.setInterval(load, 10_000)
    return () => window.clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey])

  async function act(kind: "approve" | "skip") {
    if (!current) return
    setBusy(kind)
    try {
      await (kind === "approve" ? api.approve(current.id) : api.skip(current.id))
      await load()
      onAction()
    } catch (e) {
      alert(e instanceof Error ? e.message : "Action failed")
      await load()
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <UserRound className="size-4" />
          Next up
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            Checking queue…
          </div>
        ) : !current ? (
          <p className="text-xs text-muted-foreground">
            Queue is empty. Add numbers, or send OTP on a pending row to start.
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate font-mono text-sm">{current.phone}</div>
                <Badge variant="outline" className="mt-1 text-[10px]">
                  {STATUS_LABEL[current.status]}
                </Badge>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                className="flex-1"
                disabled={busy !== null || current.status === "otp_verified"}
                onClick={() => act("approve")}
              >
                {busy === "approve" ? <Loader2 className="animate-spin" /> : <BadgeCheck />}
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1"
                disabled={busy !== null}
                onClick={() => act("skip")}
              >
                {busy === "skip" ? <Loader2 className="animate-spin" /> : <SkipForward />}
                Skip to next
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}