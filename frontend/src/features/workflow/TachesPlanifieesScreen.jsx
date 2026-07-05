import { useCallback, useMemo, useState } from 'react'
import { PlayCircle } from 'lucide-react'
import { Button, Badge, toast } from '../../ui'
import { ListShell } from '../../ui/module'
import coreApi from '../../api/coreApi'
import useWorkflowResource from './useWorkflowResource'
import { normaliserJobs } from './workflow'

/* ============================================================================
   XPLT8 — « Tâches planifiées » (`/workflow/taches-planifiees`).
   ----------------------------------------------------------------------------
   Câble FG368 (`GET/POST core/jobs/`) : liste des jobs Celery Beat configurés
   (nom, tâche, planification, dernier run) + bouton « Exécuter » (admin) qui
   déclenche `POST core/jobs/run/`. Le backend refuse déjà toute tâche hors
   planification (400) et dégrade en 503 si le broker est injoignable — ces
   deux cas s'affichent en toast, jamais un throw.
   ========================================================================== */

export default function TachesPlanifieesScreen() {
  const { data, loading, error, reload } = useWorkflowResource(
    () => coreApi.jobs.list(),
  )
  const jobs = useMemo(() => normaliserJobs(data), [data])
  const [runningTask, setRunningTask] = useState(null)

  const executer = useCallback(async (job) => {
    const task = job?.task
    if (!task || runningTask) return
    setRunningTask(task)
    try {
      const res = await coreApi.jobs.run(task)
      toast.success(
        `Tâche envoyée (id ${res?.data?.task_id || '—'}).`,
      )
      reload()
    } catch (err) {
      const status = err?.response?.status
      const detail = err?.response?.data?.detail
      if (status === 503) {
        toast.error(detail || 'File de tâches indisponible pour le moment.')
      } else {
        toast.error(detail || "Impossible d'exécuter cette tâche.")
      }
    } finally {
      setRunningTask(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runningTask])

  const columns = useMemo(() => [
    { id: 'name', header: 'Job', width: 220, accessor: (r) => r.name, cell: (v) => v || '—' },
    {
      id: 'task',
      header: 'Tâche Celery',
      width: 260,
      accessor: (r) => r.task,
      cell: (v) => (v ? <span className="font-mono text-xs">{v}</span> : '—'),
    },
    { id: 'schedule', header: 'Planification', width: 160, accessor: (r) => r.schedule, cell: (v) => v || '—' },
    {
      id: 'enabled',
      header: 'Actif',
      width: 90,
      accessor: (r) => r.enabled,
      cell: (v) => (v ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>),
    },
    { id: 'source', header: 'Source', width: 110, accessor: (r) => r.source, cell: (v) => v || '—' },
    {
      id: 'last_run',
      header: 'Dernier run',
      width: 180,
      accessor: (r) => r.last_run,
      cell: (v) => v || 'Jamais exécuté',
    },
  ], [])

  const rowActions = useCallback((row) => [
    {
      id: 'executer',
      label: runningTask === row?.task ? 'Exécution…' : 'Exécuter',
      icon: PlayCircle,
      onClick: () => executer(row),
    },
  ], [runningTask, executer])

  return (
    <ListShell
      title="Tâches planifiées"
      subtitle="Jobs Celery Beat configurés — historique du dernier run et exécution manuelle."
      columns={columns}
      rows={jobs}
      loading={loading}
      error={error}
      rowActions={rowActions}
      searchable
      searchPlaceholder="Rechercher un job…"
      emptyTitle="Aucun job planifié"
      emptyDescription="Aucune tâche Celery Beat n'est configurée pour le moment."
      actions={
        <Button variant="secondary" onClick={reload} data-testid="wf-jobs-refresh">
          Rafraîchir
        </Button>
      }
    />
  )
}
