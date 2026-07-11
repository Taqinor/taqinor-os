// FG280 — Alarmes / défauts onduleur, DISTINCTES du ticket SAV (cycle de vie
// propre : active → acquittée → escaladée/résolue). Liste + acquitter +
// escalader (ouvre/relie un ticket SAV).
import { useEffect, useState } from 'react'
import { AlertTriangle, ShieldAlert } from 'lucide-react'
import savApi from '../../api/savApi'
import {
  TooltipProvider, Card, StatusPill, Button, Select, SelectTrigger,
  SelectValue, SelectContent, SelectItem, EmptyState, Skeleton, toast,
} from '../../ui'
import { formatDateTime } from '../../lib/format'

const GRAVITE_TONES = { info: 'neutral', warning: 'warning', critique: 'danger' }
const STATUT_TONES = {
  active: 'danger', acquittee: 'warning', resolue: 'success', escaladee: 'info',
}

const fmtDateTime = (iso) => formatDateTime(iso)

export default function SavAlarmesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [statutFiltre, setStatutFiltre] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    savApi.getAlarmes(statutFiltre ? { statut: statutFiltre } : {})
      .then((r) => setRows(r.data.results ?? r.data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { load() }, [statutFiltre])

  const acquitter = async (row) => {
    setBusyId(row.id)
    try {
      await savApi.acquitterAlarme(row.id)
      toast.success('Alarme acquittée')
      load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Acquittement impossible.') }
    finally { setBusyId(null) }
  }
  const escalader = async (row) => {
    setBusyId(row.id)
    try {
      const r = await savApi.escaladerAlarme(row.id)
      toast.success(`Alarme escaladée${r.data?.ticket_reference ? ` — ticket ${r.data.ticket_reference}` : ''}`)
      load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Escalade impossible.') }
    finally { setBusyId(null) }
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-5xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Alarmes onduleur</h1>
            <p className="text-sm text-muted-foreground">
              {rows.length} alarme{rows.length > 1 ? 's' : ''}
            </p>
          </div>
          <Select value={statutFiltre || '__all'}
                  onValueChange={(v) => setStatutFiltre(v === '__all' ? '' : v)}>
            <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous les statuts</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="acquittee">Acquittée</SelectItem>
              <SelectItem value="escaladee">Escaladée</SelectItem>
              <SelectItem value="resolue">Résolue</SelectItem>
            </SelectContent>
          </Select>
        </header>

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : rows.length === 0 ? (
          <EmptyState icon={ShieldAlert} title="Aucune alarme"
                      description="Aucune alarme onduleur pour ce filtre." />
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((a) => (
              <li key={a.id} className="rounded-lg border border-border bg-card p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone={GRAVITE_TONES[a.gravite] ?? 'neutral'} label={a.gravite_display ?? a.gravite} />
                    <StatusPill tone={STATUT_TONES[a.statut] ?? 'neutral'} label={a.statut_display ?? a.statut} />
                    <span className="font-medium">{a.code}</span>
                    {a.libelle && <span className="text-sm text-muted-foreground">— {a.libelle}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    {a.statut === 'active' && (
                      <Button size="sm" variant="outline" loading={busyId === a.id} onClick={() => acquitter(a)}>
                        Acquitter
                      </Button>
                    )}
                    {(a.statut === 'active' || a.statut === 'acquittee') && (
                      <Button size="sm" variant="outline" loading={busyId === a.id} onClick={() => escalader(a)}>
                        <AlertTriangle /> Escalader
                      </Button>
                    )}
                    {a.ticket_reference && (
                      <span className="text-xs text-muted-foreground">Ticket {a.ticket_reference}</span>
                    )}
                  </div>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {a.equipement_produit ?? '—'} — {a.equipement_serie ?? 'sans série'}
                  {' · '}détectée {fmtDateTime(a.date_detection)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </TooltipProvider>
  )
}
