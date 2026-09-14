import { useRef, useState } from "react"
import { FileUp, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { api } from "@/lib/api"
import type { BulkImportResult } from "@/types"

const COUNTRIES = [
  { dial: "234", label: "Nigeria" },
  { dial: "254", label: "Kenya" },
] as const

interface Props {
  open: boolean
  onClose: () => void
  onDone: (result: BulkImportResult) => void
}

export function AddNumbersDialog({ open, onClose, onDone }: Props) {
  const [tab, setTab] = useState<"paste" | "file">("paste")
  const [country, setCountry] = useState("234")
  const [manualSms, setManualSms] = useState(false)
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<BulkImportResult | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  if (!open) return null

  function parseNumbers(raw: string): string[] {
    return raw
      .split(/[\n,;\s]+/)
      .map((s) => s.replace(/\D/g, ""))
      .filter((d) => d.length >= 7)
  }

  async function submitPaste() {
    const nums = parseNumbers(text)
    if (nums.length === 0) return
    setBusy(true)
    try {
      const res = await api.bulkRegister(nums, country, manualSms)
      setResult(res)
      onDone(res)
    } catch (e) {
      setResult({ created: [], skipped: [], errors: [e instanceof Error ? e.message : "Unknown error"] })
    } finally {
      setBusy(false)
    }
  }

  async function handleFile(file: File) {
    setBusy(true)
    try {
      const buf = await file.arrayBuffer()
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)))
      const res = await api.importContacts(file.name, b64, country, manualSms)
      setResult(res)
      onDone(res)
    } catch (e) {
      setResult({ created: [], skipped: [], errors: [e instanceof Error ? e.message : "Unknown error"] })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <Card className="mx-4 w-full max-w-lg shadow-xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-sm font-semibold">Add numbers</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        <CardContent className="space-y-4 pt-4">
          <div className="flex gap-2">
            <Button variant={tab === "paste" ? "default" : "outline"} size="sm" onClick={() => setTab("paste")}>
              Paste numbers
            </Button>
            <Button variant={tab === "file" ? "default" : "outline"} size="sm" onClick={() => setTab("file")}>
              Import file
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="mb-1 block text-xs">Default country</Label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full rounded-md border bg-background px-2 py-1.5 text-xs"
              >
                {COUNTRIES.map((c) => (
                  <option key={c.dial} value={c.dial}>
                    {c.label} +{c.dial}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end pb-0.5">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={manualSms}
                  onChange={(e) => setManualSms(e.target.checked)}
                  className="h-3.5 w-3.5"
                />
                Manual SMS selection
              </label>
            </div>
          </div>

          {tab === "paste" ? (
            <div className="space-y-1">
              <Label className="text-xs">One number per line, or comma-separated</Label>
              <Textarea
                rows={6}
                placeholder={"254712345678\n2348012345678"}
                value={text}
                onChange={(e) => setText(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          ) : (
            <div className="space-y-1">
              <Label className="text-xs">CSV / TSV / TXT / XLSX</Label>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.txt,.tsv,.xlsx,.xls"
                className="hidden"
                onChange={async (e) => {
                  const f = e.target.files?.[0]
                  if (f) await handleFile(f)
                  if (fileRef.current) fileRef.current.value = ""
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <FileUp className="mr-1 size-3.5" />
                Choose file
              </Button>
            </div>
          )}

          {tab === "paste" && (
            <Button size="sm" disabled={busy || parseNumbers(text).length === 0} onClick={submitPaste}>
              <Plus className="mr-1 size-3.5" />
              {busy ? "Adding…" : `Add ${parseNumbers(text).length} number${parseNumbers(text).length === 1 ? "" : "s"}`}
            </Button>
          )}

          {result && (
            <div className="space-y-1 rounded-md border bg-muted/40 p-3 text-xs">
              <p>
                Created <strong>{result.created.length}</strong> · Skipped{" "}
                <strong>{result.skipped.length}</strong> · Errors{" "}
                <strong>{result.errors.length}</strong>
              </p>
              {result.errors.length > 0 && (
                <ul className="max-h-32 overflow-auto text-destructive">
                  {result.errors.slice(0, 20).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
