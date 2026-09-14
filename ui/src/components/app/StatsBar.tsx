import type { ReactNode } from "react"
import { CheckCircle2, CircleDashed, Loader2, ShieldCheck, XCircle } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import type { Stats } from "@/types"

function Stat({
  icon,
  label,
  value,
  tone = "default",
}: {
  icon: ReactNode
  label: string
  value: number
  tone?: "default" | "success" | "danger"
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <span className={tone === "success" ? "text-primary" : tone === "danger" ? "text-destructive" : "text-muted-foreground"}>
          {icon}
        </span>
        <div>
          <div className="text-2xl font-semibold leading-none">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  )
}

export function StatsBar({ stats }: { stats: Stats }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
      <Stat icon={<CircleDashed className="size-5" />} label="Total" value={stats.total} />
      <Stat icon={<CircleDashed className="size-5" />} label="Pending" value={stats.pending} />
      <Stat icon={<Loader2 className="size-5 animate-spin" />} label="Sending OTP" value={stats.sending} />
      <Stat icon={<CheckCircle2 className="size-5" />} label="OTP sent" value={stats.otp_sent} tone="success" />
      <Stat icon={<ShieldCheck className="size-5" />} label="Verified" value={stats.verified} tone="success" />
      <Stat icon={<XCircle className="size-5" />} label="Failed" value={stats.failed} tone="danger" />
    </div>
  )
}