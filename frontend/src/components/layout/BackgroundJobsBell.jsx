// WIR137 / NTPLT29 — Widget « Mes tâches de fond » dans l'en-tête.
//
// `core.jobs.submit` crée des `BackgroundJob` (exports lourds, imports longs)
// exposés en lecture sur `core/jobs-status/`, mais AUCUN écran ne les
// interrogeait : un gros export ne montrait ni progression ni état de fin.
// Cette cloche sonde MES jobs (doublement scopés société+utilisateur côté
// serveur), affiche un badge tant qu'un job est actif (en file / en cours), et
// liste progression + terminé/échoué dans un popover. Sondage rapide (5 s)
// tant qu'un job tourne, lent (30 s) sinon — sensible à la visibilité de
// l'onglet (mêmes économies que les autres cloches).
import { useCallback, useMemo, useState } from 'react'
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import coreApi from '../../api/coreApi'
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'
import { Popover, PopoverTrigger, PopoverContent } from '../../ui/Popover'

const ACTIFS = new Set(['queued', 'running'])

function statutMeta(statut) {
  switch (statut) {
    case 'running':
      return { label: 'En cours', icon: Loader2, spin: true, tone: 'text-info' }
    case 'queued':
      return { label: 'En file', icon: Clock, tone: 'text-muted-foreground' }
    case 'done':
      return { label: 'Terminé', icon: CheckCircle2, tone: 'text-success' }
    case 'failed':
      return { label: 'Échoué', icon: XCircle, tone: 'text-destructive' }
    default:
      return { label: statut, icon: Clock, tone: 'text-muted-foreground' }
  }
}

function JobRow({ job }) {
  const meta = statutMeta(job.statut)
  const Icon = meta.icon
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border px-2.5 py-2">
      <div className="flex items-center gap-1.5 text-xs">
        <Icon size={14} className={`${meta.tone} ${meta.spin ? 'animate-spin' : ''}`} aria-hidden="true" />
        <span className="font-medium">{job.kind}</span>
        <span className="ml-auto text-muted-foreground">{meta.label}</span>
      </div>
      {job.statut === 'running' && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${job.progress_pct ?? 0}%` }}
            role="progressbar" aria-valuenow={job.progress_pct ?? 0}
            aria-valuemin={0} aria-valuemax={100} />
        </div>
      )}
      {job.statut === 'failed' && job.message_erreur && (
        <p className="text-[11px] text-destructive">{job.message_erreur}</p>
      )}
    </div>
  )
}

export default function BackgroundJobsBell() {
  const [jobs, setJobs] = useState([])
  const [open, setOpen] = useState(false)

  const load = useCallback(() => {
    coreApi.jobsStatus.list()
      .then((r) => setJobs(r.data?.results ?? r.data ?? []))
      .catch(() => { /* best-effort : la cloche reste silencieuse */ })
  }, [])

  const actifs = useMemo(
    () => jobs.filter((j) => ACTIFS.has(j.statut)), [jobs])

  // Sondage rapide tant qu'un job tourne, lent sinon (visibility-aware).
  useVisibilityAwarePolling(
    [{ fn: load, intervalMs: actifs.length > 0 ? 5000 : 30000 }])

  // Rien à montrer tant qu'aucun job n'a jamais été lancé : cloche masquée.
  if (jobs.length === 0) return null

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" className="nb-btn"
          aria-label={`Mes tâches de fond (${actifs.length} en cours)`}
          data-testid="bg-jobs-bell">
          <Loader2 size={19} aria-hidden="true"
            className={actifs.length > 0 ? 'animate-spin' : ''} />
          {actifs.length > 0 && (
            <span className="nb-badge">{actifs.length}</span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72">
        <div className="mb-2 text-sm font-semibold">Mes tâches de fond</div>
        <div className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
          {jobs.map((job) => <JobRow key={job.id} job={job} />)}
        </div>
      </PopoverContent>
    </Popover>
  )
}
